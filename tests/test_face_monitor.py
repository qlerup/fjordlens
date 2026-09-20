import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import io

spec = importlib.util.spec_from_file_location('face_monitor', Path(__file__).resolve().parents[1] / 'ai_service/face_monitor.py')
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


class FaceMonitorTests(unittest.TestCase):
    def test_eight_fixed_rows_and_replacement_in_same_slot(self):
        row = dict(instance=3, stage='inference', percent=None, elapsed_sec=2.1, file='first.jpg')
        first = monitor.render([row], 8, 100).splitlines()
        row['file'] = 'next.jpg'
        second = monitor.render([row], 8, 100).splitlines()
        self.assertEqual(len(first), 10)
        self.assertIn('first.jpg', first[4])
        self.assertIn('next.jpg', second[4])
        self.assertIn('Ledig', first[2])
        self.assertIn('--', first[4])

    def test_filename_cannot_inject_terminal_commands(self):
        row = dict(instance=1, stage='inference', percent=None, elapsed_sec=0, file='x\n\x1b[2J.jpg')
        screen = monitor.render([row], 8, 100)
        self.assertEqual(len(screen.splitlines()), 10)
        self.assertNotIn('\x1b[2J', screen)

    def test_ctrl_c_restores_terminal_and_only_reads_status(self):
        output = io.StringIO()
        output.isatty = lambda: True
        response = Mock()
        response.__enter__ = Mock(return_value=io.StringIO('{"instances": []}'))
        response.__exit__ = Mock(return_value=False)
        with (patch.object(monitor.sys, 'argv', ['face_monitor.py']),
              patch.object(monitor.sys, 'stdout', output),
              patch.object(monitor, 'urlopen', return_value=response) as request,
              patch.object(monitor.time, 'sleep', side_effect=KeyboardInterrupt)):
            monitor.main()
        request.assert_called_once_with('http://127.0.0.1:8000/faces/status', timeout=2)
        self.assertTrue(output.getvalue().endswith('\x1b[?25h\x1b[?1049l'))


if __name__ == '__main__':
    unittest.main()
