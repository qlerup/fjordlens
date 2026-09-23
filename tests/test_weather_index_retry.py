import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class WeatherIndexRetryTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / 'app.py'
        tree = ast.parse(source.read_text(encoding='utf-8-sig'))
        function = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef)
                        and node.name == '_enrich_metadata_weather')
        self.fetch = Mock()
        self.log = Mock()
        self.sleep = Mock()
        env = dict(WEATHER_AUTO_FETCH=True, get_or_fetch_weather_payload=self.fetch,
                   log_event=self.log, time=SimpleNamespace(sleep=self.sleep))
        code = 'from __future__ import annotations\n' + ast.unparse(function)
        exec(compile(code, str(source), 'exec'), env)
        self.enrich = env['_enrich_metadata_weather']
        self.metadata = dict(rel_path='uploads/video.mp4', captured_at='2026-09-20',
                             gps_lat=55, gps_lon=12, metadata_json={})
        self.payload = {'temperature_2m': 15}

    def test_success_does_not_wait_or_retry(self):
        self.fetch.return_value = (self.payload, 'api')
        self.enrich(self.metadata)
        self.fetch.assert_called_once()
        self.sleep.assert_not_called()
        self.assertEqual(self.metadata['metadata_json']['weather'], self.payload)

    def test_retry_waits_then_reuses_same_file_and_saves_weather(self):
        self.fetch.side_effect = [TimeoutError('timeout'), (self.payload, 'api')]

        def waiting(seconds):
            self.assertEqual(seconds, 30)
            self.assertEqual(self.fetch.call_count, 1)
            self.assertEqual(self.log.call_args.args, ('weather_index_retry',))
            self.assertNotIn('error', self.log.call_args.kwargs)
            self.assertIn('30 sekunder', self.log.call_args.kwargs['message'])
            self.assertEqual(self.log.call_args.kwargs['rel_path'], 'uploads/video.mp4')

        self.sleep.side_effect = waiting
        self.enrich(self.metadata)
        self.sleep.assert_called_once_with(30)
        self.assertEqual(self.fetch.call_count, 2)
        self.assertEqual(*self.fetch.call_args_list)
        self.assertEqual(self.metadata['metadata_json']['weather'], self.payload)
        self.assertEqual([call.args[0] for call in self.log.call_args_list],
                         ['weather_index_retry', 'weather_indexed'])

    def test_second_failure_logs_final_error_and_returns(self):
        self.fetch.side_effect = [TimeoutError('first'), TimeoutError('second')]
        self.enrich(self.metadata)
        self.assertEqual(self.fetch.call_count, 2)
        self.sleep.assert_called_once_with(30)
        self.assertNotIn('weather', self.metadata['metadata_json'])
        self.assertEqual([call.args[0] for call in self.log.call_args_list],
                         ['weather_index_retry', 'error'])
        self.assertIn('second', self.log.call_args.kwargs['error'])

    def test_missing_location_or_date_still_skips_without_retry(self):
        self.fetch.side_effect = ValueError('Billedet mangler dato/tid')
        self.enrich(self.metadata)
        self.fetch.assert_called_once()
        self.sleep.assert_not_called()
        self.log.assert_not_called()


if __name__ == '__main__':
    unittest.main()
