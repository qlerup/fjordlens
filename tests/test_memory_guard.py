import os
from pathlib import Path
import tempfile
import time
import threading
import io
import json
import unittest
from unittest.mock import patch, Mock

from ai_service import memory_budget as admission
from updater_service import memory_governor as governor

GIB = 1024**3


class MemoryGuardTests(unittest.TestCase):
    def test_tiny_updater_resize_does_not_pause_the_face_queue(self):
        # Actual stall: 16 MiB updater shrinks 129 -> 128 MiB. It must not
        # inherit the web worker's 512 MiB safety margin and freeze all jobs.
        config = dict(Memory=129*governor.MIB, MemorySwap=129*governor.MIB)
        def api(method, path, body=None):
            if path.startswith('/containers/json?'):
                return [dict(Id='updater', Labels={'com.docker.compose.service': 'fjordlens-updater'})]
            if path.endswith('/json'):
                return dict(State={'Running': True}, HostConfig=config)
            if '/stats?' in path:
                return dict(memory_stats={'usage': 16*governor.MIB})
            if path.endswith('/update'):
                config.update(body)
                return {}
            self.fail(path)
        state = governor.MemoryGovernor(api=api).sample()
        self.assertFalse(state['pressure'])
        self.assertFalse(state.get('deferred_resize', False))
        self.assertEqual(config['Memory'], 128*governor.MIB)

    def test_live_shrink_that_would_kill_work_is_deferred(self):
        updates = []
        def api(method, path, body=None):
            if path.startswith('/containers/json?'):
                return [dict(Id='ai', Labels={'com.docker.compose.service': 'fjordlens-ai'})]
            if path.endswith('/json'):
                return dict(State={'Running': True}, HostConfig={'Memory': 6*GIB, 'MemorySwap': 6*GIB})
            if '/stats?' in path:
                return dict(memory_stats={'usage': 5*GIB})
            updates.append(body)
            return {}
        state = governor.MemoryGovernor(api=api).sample()
        self.assertEqual(updates, [])
        self.assertTrue(state['pressure'])
        self.assertTrue(state['deferred_resize'])
        self.assertEqual(state['containers']['fjordlens-ai']['limit_bytes'], 6*GIB)

    def test_admission_respects_newer_actual_hard_limit(self):
        client = admission.MemoryBudget('fjordlens-ai')
        status = dict(ok=True, containers={'fjordlens-ai': {'limit_bytes': 4*GIB}})
        with patch.object(Path, 'read_text', return_value=str(GIB)), patch.object(admission, 'current_memory', return_value=GIB//2):
            self.assertEqual(client.available(status), GIB//2 - 64*admission.MIB)

    def memory_files(self, usage, stats, legacy=False):
        root = '/sys/fs/cgroup/memory/' if legacy else '/sys/fs/cgroup/'
        files = {root + ('memory.usage_in_bytes' if legacy else 'memory.current'): str(usage),
                 root + 'memory.stat': stats}
        def read(path, *args, **kwargs):
            value = files.get(path.as_posix())
            if value is None:
                raise FileNotFoundError(path)
            return value
        return patch.object(Path, 'read_text', read)

    def test_measured_metadata_stall_admits_job_with_clean_inactive_cache(self):
        raw, cap = 2398507008, 2526019584
        stats = 'anon 1417490432\nfile 966291456\ninactive_file 965853184\nshmem 0\nfile_dirty 0\nfile_writeback 0\n'
        client = admission.MemoryBudget('fjordlens')
        client.enabled = True
        status = dict(ok=True, pressure=False, containers={'fjordlens': {'limit_bytes': cap}})
        self.assertLess(cap - raw - 64*admission.MIB, 128*admission.MIB)
        with self.memory_files(raw, stats), patch.object(client, 'status', return_value=status):
            self.assertEqual(admission.current_memory(), raw - 965853184)
            with client.slot(128*admission.MIB, timeout=0):
                self.assertEqual(client.reserved, 128*admission.MIB)
            self.assertEqual(client.reserved, 0)
            with patch.object(client, 'status', return_value=dict(status, pressure=True)):
                with self.assertRaises(RuntimeError):
                    with client.slot(128*admission.MIB, timeout=0):
                        self.fail('Host reserve pressure must still block jobs')

    def test_cache_discount_excludes_active_shared_dirty_and_writeback_pages(self):
        stats = 'file 900\ninactive_file 700\nactive_file 200\nshmem 100\nfile_dirty 150\nfile_writeback 50\n'
        with self.memory_files(2000, stats):
            self.assertEqual(admission.current_memory(), 1600)

    def test_v1_cache_uses_hierarchical_stats(self):
        stats = 'cache 800\ninactive_file 600\ntotal_cache 900\ntotal_inactive_file 700\ntotal_shmem 100\ntotal_dirty 150\ntotal_writeback 50\n'
        with self.memory_files(2000, stats, legacy=True):
            self.assertEqual(admission.current_memory(), 1600)

    def test_missing_invalid_or_inconsistent_cache_stats_use_raw_usage(self):
        for stats in (None, '', 'file nope', 'file 2000\ninactive_file 2000',
                      'file 900\ninactive_file -1', 'file 900'):
            with self.subTest(stats=stats), self.memory_files(1000, stats):
                self.assertEqual(admission.current_memory(), 1000)

    def test_dirty_cache_cannot_create_admission_headroom(self):
        stats = 'file 900\ninactive_file 700\nshmem 200\nfile_dirty 400\nfile_writeback 300\n'
        with self.memory_files(2000, stats):
            self.assertEqual(admission.current_memory(), 2000)

    def setUp(self):
        budget = dict(ok=True, enabled=True, source='fjordhub', measured_at=time.time(),
                      total_bytes=10*GIB, used_bytes=5*GIB, other_bytes=3*GIB,
                      budget_bytes=5*GIB, reserve_bytes=2*GIB, pressure=False)
        self.env_patch = patch.dict(os.environ, {'FJORDHUB_URL': 'http://hub', 'FJORDHUB_API_KEY': 'test'})
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)
        self.fetch_patch = patch.object(governor, 'urlopen', side_effect=lambda *a, **kw: io.StringIO(json.dumps(budget)))
        self.fetch_patch.start()
        self.addCleanup(self.fetch_patch.stop)

    def containers(self):
        return [dict(id=name, service=name, usage=GIB//2) for name in governor.FLOORS]

    def test_budget_tracks_other_apps_and_caps_sum(self):
        for other in (3, 4, 6):
            budget, measured, caps = governor.allocate(10*GIB, (other+2)*GIB, self.containers())
            self.assertEqual(budget, (8-other)*GIB)
            self.assertEqual(measured, other*GIB)
            self.assertLessEqual(sum(caps.values()), budget)
            self.assertTrue(all(cap > 0 for cap in caps.values()))

    def test_reported_conversion_stall_gets_enough_room_without_exceeding_hub_budget(self):
        usage = {'fjordlens': 2673397760, 'fjordlens-ai': 1489231872,
                 'fjordlens-convert': 1358319616, 'fjordlens-updater': 20570112}
        containers = [dict(id=name, service=name, usage=value) for name, value in usage.items()]
        budget = 7727738880
        _, _, caps = governor.allocate(budget + governor.RESERVE, sum(usage.values()), containers)
        client = admission.MemoryBudget('fjordlens-convert')
        client.enabled = True
        status = dict(ok=True, pressure=False, containers={'fjordlens-convert': {'limit_bytes': 1914699776}})
        with patch.object(admission, 'current_memory', return_value=1373515776):
            self.assertLess(client.available(status), 512*governor.MIB, 'old measured limit reproduces the stall')
            status['containers']['fjordlens-convert']['limit_bytes'] = caps['fjordlens-convert']
            with patch.object(client, 'status', return_value=status):
                with client.slot(512*governor.MIB, timeout=0):
                    self.assertEqual(client.reserved, 512*governor.MIB)
        self.assertLessEqual(sum(caps.values()), budget)

    def test_conversion_headroom_never_overrides_a_small_budget(self):
        containers = self.containers()
        for budget in (256*governor.MIB, GIB, 2*GIB):
            _, _, caps = governor.allocate(budget+governor.RESERVE, 2*GIB, containers)
            self.assertLessEqual(sum(caps.values()), budget)

    def test_conversion_waits_past_old_timeout_then_resumes_when_budget_returns(self):
        client = admission.MemoryBudget('fjordlens-convert')
        client.enabled = True
        ready = dict(ok=True, pressure=False, containers={'fjordlens-convert': {'limit_bytes': 2*GIB}})
        statuses = [{'ok': False, 'error': 'Hub unavailable'}, dict(ready, pressure=True), ready]
        with patch.object(client, 'status', side_effect=statuses), \
             patch.object(admission, 'current_memory', return_value=GIB), \
             patch.object(admission.time, 'monotonic', side_effect=[0, 100, 200, 300]), \
             patch.object(admission.time, 'sleep') as sleep:
            with client.slot(512*governor.MIB, timeout=None):
                self.assertEqual(client.reserved, 512*governor.MIB)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(client.reserved, 0)

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

    def test_missing_hub_never_falls_back_to_host_measurement(self):
        api = Mock()
        with patch.object(governor, 'urlopen', side_effect=OSError('Hub offline')):
            with self.assertRaises(OSError):
                governor.MemoryGovernor(api=api).sample()
        api.assert_not_called()

    def test_expired_hub_budget_is_rejected_before_changing_limits(self):
        api = Mock()
        response = io.StringIO(json.dumps(dict(ok=True, source='fjordhub', measured_at=time.time()-30, reserve_bytes=2*GIB)))
        with patch.object(governor, 'urlopen', return_value=response):
            with self.assertRaisesRegex(RuntimeError, 'fresh'):
                governor.MemoryGovernor(api=api).sample()
        api.assert_not_called()


if __name__ == '__main__':
    unittest.main()
