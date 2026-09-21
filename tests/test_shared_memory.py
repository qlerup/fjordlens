import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from ai_service.memory_budget import MemoryBudget
from updater_service.memory_governor import MemoryGovernor, RESERVE, SERVICES
from updater_service import app as updater

GIB = 1024**3


class SharedMemoryTests(unittest.TestCase):
    def guard(self, path=None):
        guard = MemoryGovernor(lease_path=path)
        guard.enabled = True
        guard.state = dict(ok=True, enabled=True, total_bytes=10*GIB,
                           used_bytes=5*GIB, reserve_bytes=RESERVE,
                           measured_at=time.time(), pressure=False)
        return guard

    def request(self, service='fjordlens-ai', amount=GIB):
        return dict(service=service, token=uuid.uuid4().hex, bytes=amount)

    def test_whole_container_usage_includes_all_apps(self):
        guard = self.guard()
        self.assertEqual(guard.snapshot()['available_bytes'], 3*GIB)
        guard.state['used_bytes'] = 6*GIB
        self.assertEqual(guard.snapshot()['available_bytes'], 2*GIB)

    def test_all_services_compete_for_one_atomic_budget(self):
        guard = self.guard()
        barrier = threading.Barrier(8)
        def reserve(i):
            barrier.wait(timeout=5)
            return guard.reservation('reserve', self.request(list(sorted(SERVICES))[i % 4]))['granted']
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(reserve, range(8)))
        self.assertEqual(sum(results), 3)
        self.assertEqual(guard.snapshot()['available_bytes'], 0)

    def test_reserve_is_idempotent_and_release_waits_for_a_new_sample(self):
        guard = self.guard()
        request = self.request()
        for _ in range(2):
            self.assertTrue(guard.reservation('reserve', request)['granted'])
        self.assertEqual(guard.snapshot()['reserved_bytes'], GIB)
        guard.reservation('release', request)
        self.assertEqual(guard.snapshot()['reserved_bytes'], GIB)
        guard.state['measured_at'] = time.time()
        self.assertEqual(guard.snapshot()['reserved_bytes'], 0)

    def test_expired_sample_and_host_pressure_block_new_jobs(self):
        guard = self.guard()
        guard.state['measured_at'] -= 11
        self.assertFalse(guard.reservation('reserve', self.request())['granted'])
        guard.state.update(measured_at=time.time(), used_bytes=9*GIB)
        self.assertFalse(guard.reservation('reserve', self.request(amount=1))['granted'])

    def test_reservations_survive_updater_restart_and_expire_after_client_crash(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'FJORDLENS_MEMORY_GUARD': '1'}):
            path = Path(tmp) / 'leases.json'
            guard = self.guard(path)
            request = self.request()
            guard.reservation('reserve', request)
            restarted = self.guard(path)
            self.assertEqual(restarted.snapshot()['reserved_bytes'], GIB)
            restarted.reservation('renew', request)
            self.assertTrue(restarted.leases[request['token']]['expires'] > time.time()+100)
            restarted.leases[request['token']]['expires'] = time.time()-1
            self.assertEqual(restarted.snapshot()['reserved_bytes'], 0)

    def test_http_clients_share_budget_and_release_on_exception(self):
        guard = self.guard()
        with patch.object(updater, 'MEMORY_GOVERNOR', guard):
            server = ThreadingHTTPServer(('127.0.0.1', 0), updater.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                a, b = MemoryBudget('fjordlens'), MemoryBudget('fjordlens-ai')
                for client in (a, b):
                    client.enabled = True
                    client.url = f'http://127.0.0.1:{server.server_port}/memory'
                with self.assertRaisesRegex(ValueError, 'job failed'):
                    with a.slot(2*GIB, timeout=0):
                        with a.slot(GIB, timeout=0):
                            self.assertEqual(guard.snapshot()['reserved_bytes'], 2*GIB)
                        with self.assertRaises(RuntimeError):
                            with b.slot(2*GIB, timeout=0):
                                self.fail('Other service reused occupied RAM')
                        with b.slot(GIB, timeout=0):
                            self.assertEqual(guard.snapshot()['reserved_bytes'], 3*GIB)
                        raise ValueError('job failed')
                guard.state['measured_at'] = time.time()
                self.assertEqual(guard.snapshot()['reserved_bytes'], 0)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_old_partitions_are_replaced_with_host_ceiling_only_for_own_services(self):
        configs = {name: dict(Memory=GIB, MemorySwap=GIB) for name in SERVICES}
        calls = []
        def api(method, path, body=None):
            calls.append((method, path))
            if path.startswith('/containers/json?'):
                return [dict(Id=n, Labels={'com.docker.compose.service': n}) for n in configs] + [dict(Id='other', Labels={'com.docker.compose.service': 'other'})]
            name = path.split('/')[2]
            if path.endswith('/json'):
                return dict(HostConfig=configs[name])
            if path.endswith('/update'):
                configs[name].update(body)
                return {}
            self.fail(path)
        measurement = dict(ok=True, source='fjordhub', measured_at=time.time(), total_bytes=10*GIB, used_bytes=5*GIB)
        with patch.dict(os.environ, {'FJORDHUB_URL': 'http://hub', 'FJORDHUB_API_KEY': 'test'}), \
             patch('updater_service.memory_governor.urlopen', return_value=io.StringIO(json.dumps(measurement))):
            state = MemoryGovernor(api=api).sample()
        self.assertEqual(state['budget_bytes'], 3*GIB)
        self.assertNotIn('containers', state)  # old clients fail closed during upgrade
        self.assertTrue(all(c['Memory'] == 10*GIB and c['MemorySwap'] == 10*GIB for c in configs.values()))
        self.assertFalse(any('/other/' in path for _, path in calls))
