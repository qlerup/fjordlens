import os
from pathlib import Path
import tempfile
import time
import threading
import unittest
from unittest.mock import patch, Mock

from ai_service import memory_budget as admission
from updater_service import memory_governor as governor

GIB = 1024**3


class MemoryGuardTests(unittest.TestCase):
    def containers(self):
        return [dict(id=name, service=name, usage=GIB//2) for name in governor.FLOORS]

    def test_budget_tracks_other_apps_and_caps_sum(self):
        for other in (3, 4, 6):
            budget, measured, caps = governor.allocate(10*GIB, (other+2)*GIB, self.containers())
            self.assertEqual(budget, (8-other)*GIB)
            self.assertEqual(measured, other*GIB)
            self.assertLessEqual(sum(caps.values()), budget)
            self.assertTrue(all(cap > 0 for cap in caps.values()))

    def test_wrong_host_scope_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, 'does not include'):
            governor.allocate(10*GIB, GIB, self.containers())

    def test_lxc_limit_overrides_physical_ram(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'meminfo').write_text('MemTotal: 67108864 kB\nMemFree: 33554432 kB\n')
            (root/'memory.max').write_text(str(10*GIB))
            (root/'memory.current').write_text(str(5*GIB))
            self.assertEqual(governor.host_memory(root, root), (10*GIB, 5*GIB))

    def test_standalone_never_starts_governor_or_queries_memory(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(governor.threading, 'Thread') as thread:
            guard = governor.MemoryGovernor(api=Mock())
            guard.start()
            self.assertFalse(guard.enabled)
            thread.assert_not_called()
            guard.api.assert_not_called()
            client = admission.MemoryBudget()
            with patch.object(admission, 'urlopen', side_effect=AssertionError), patch.object(admission, 'current_memory', side_effect=AssertionError):
                self.assertEqual(client.status(), {'ok': True, 'enabled': False})
                with client.slot(100*GIB):
                    pass

    def test_stale_measurement_blocks_admission(self):
        with patch.dict(os.environ, {'FJORDLENS_MEMORY_GUARD': '1'}):
            guard = governor.MemoryGovernor()
            guard.state = dict(ok=True, enabled=True, _sample_at=time.monotonic()-6)
            client = admission.MemoryBudget()
            with patch.object(client, 'status', side_effect=guard.snapshot):
                with self.assertRaisesRegex(RuntimeError, 'RAM-budget'):
                    with client.slot(GIB, timeout=0):
                        self.fail('Work must not start')

    def test_reservations_are_nested_and_released_on_failure(self):
        with patch.dict(os.environ, {'FJORDLENS_MEMORY_GUARD': '1'}):
            client = admission.MemoryBudget('fjordlens-ai')
        status = dict(ok=True, containers={'fjordlens-ai': dict(limit_bytes=3*GIB)})
        with patch.object(client, 'status', return_value=status), patch.object(admission, 'current_memory', return_value=GIB):
            with self.assertRaisesRegex(ValueError, 'job failed'):
                with client.slot(GIB):
                    with client.slot(GIB//2):
                        self.assertEqual(client.reserved, GIB)
                    with self.assertRaises(RuntimeError):
                        with client.slot(3*GIB, timeout=0):
                            self.fail('Over budget')
                    raise ValueError('job failed')
            self.assertEqual(client.reserved, 0)

    def test_docker_limits_are_verified_before_advertising_budget(self):
        configs = {name: dict(Memory=GIB, MemorySwap=GIB) for name in governor.FLOORS}
        def api(method, path, body=None):
            if path.startswith('/containers/json?'):
                return [dict(Id=name, Labels={'com.docker.compose.service': name}) for name in configs]
            name = path.split('/')[2]
            if path.endswith('/json'):
                return dict(State={'Running': True}, HostConfig=configs[name])
            if '/stats?' in path:
                return dict(memory_stats={'usage': GIB//2})
            if path.endswith('/update'):
                configs[name].update(body)
                return {}
            self.fail(path)
        guard = governor.MemoryGovernor(api=api)
        with patch.object(governor, 'host_memory', return_value=(10*GIB, 5*GIB)):
            result = guard.sample()
        self.assertTrue(result['ok'])
        self.assertEqual(result['budget_bytes'], 5*GIB)
        self.assertLessEqual(sum(v['Memory'] for v in configs.values()), 5*GIB)
        self.assertTrue(all(v['Memory'] == v['MemorySwap'] for v in configs.values()))

    def test_concurrent_jobs_cannot_reserve_the_same_memory(self):
        with patch.dict(os.environ, {'FJORDLENS_MEMORY_GUARD': '1'}):
            client = admission.MemoryBudget('fjordlens-ai')
        entered = threading.Event()
        release = threading.Event()
        status = dict(ok=True, containers={'fjordlens-ai': dict(limit_bytes=2*GIB)})
        def hold():
            with client.slot(GIB):
                entered.set()
                release.wait(timeout=3)
        with patch.object(client, 'status', return_value=status), patch.object(admission, 'current_memory', return_value=GIB//2):
            thread = threading.Thread(target=hold)
            thread.start()
            try:
                self.assertTrue(entered.wait(timeout=2))
                with self.assertRaises(RuntimeError):
                    with client.slot(GIB, timeout=0):
                        self.fail('Second job exceeds budget')
            finally:
                release.set()
                thread.join(timeout=3)
            self.assertEqual(client.reserved, 0)

    def test_docker_ignoring_limits_is_an_error(self):
        def api(method, path, body=None):
            if path.startswith('/containers/json?'):
                return [dict(Id='ai', Labels={'com.docker.compose.service': 'fjordlens-ai'})]
            if path.endswith('/json'):
                return dict(State={'Running': True}, HostConfig={'Memory': 0, 'MemorySwap': 0})
            if '/stats?' in path:
                return dict(memory_stats={'usage': GIB})
            return {}
        with patch.object(governor, 'host_memory', return_value=(10*GIB, 4*GIB)):
            with self.assertRaisesRegex(RuntimeError, 'did not apply'):
                governor.MemoryGovernor(api=api).sample()


if __name__ == '__main__':
    unittest.main()
