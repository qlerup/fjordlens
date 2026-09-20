import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from conversion_jobs import ConversionJob


class ConversionJobTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

    def test_status_and_exclusion_are_shared_between_independent_instances(self):
        owner = ConversionJob(self.directory.name, 'heic')
        reader = ConversionJob(self.directory.name, 'heic')
        self.assertIsNone(reader.status()['result'])
        with owner.acquire():
            self.assertIsNone(reader.acquire())
            self.assertTrue(reader.status()['running'])
            owner.save({'running': True, 'progress': {'total': 10, 'processed': 3}})
            self.assertEqual(reader.status()['progress']['processed'], 3)
            # Other media types may run independently.
            with ConversionJob(self.directory.name, 'mov').acquire():
                pass
            owner.save({'running': False, 'result': {'ok': True, 'total': 10}, 'progress': None})
        self.assertFalse(reader.status()['running'])
        self.assertEqual(reader.status()['result']['total'], 10)

    def test_process_crash_releases_lock_and_reports_interruption(self):
        code = '''
import sys
from conversion_jobs import ConversionJob
job = ConversionJob(sys.argv[1], 'raw')
lock = job.acquire()
assert lock is not None
job.save({'running': True, 'progress': {'processed': 4}})
print('ready', flush=True)
sys.stdin.readline()
'''
        process = subprocess.Popen([sys.executable, '-u', '-c', code, self.directory.name],
                                   cwd=Path(__file__).resolve().parents[1], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), 'ready')
            job = ConversionJob(self.directory.name, 'raw')
            self.assertIsNone(job.acquire())
            self.assertEqual(job.status()['progress']['processed'], 4)
            process.kill()
            process.wait(timeout=10)
            status = job.status()
            self.assertFalse(status['running'])
            self.assertFalse(status['result']['ok'])
            with job.acquire():
                pass
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)
