"""A failed lease acquisition must use the import worker's normal cleanup."""
import sqlite3
from unittest.mock import patch

import app as fl


class InlineThread:
    def __init__(self, target, **kwargs):
        self.target = target

    def start(self):
        self.target()


def test_startup_database_error_clears_running_and_active_files():
    rel = 'uploads/originals/Trip/video.mp4'
    with (patch.object(fl, 'UPLOAD_POSTPROCESS_BY_USER', {}),
          patch.object(fl, 'DIRECT_UPLOAD_POSTPROCESS_ACTIVE_RELS', set()),
          patch.object(fl, '_is_managed_preserved_upload_original', return_value=False),
          patch.object(fl, 'faces_auto_index_enabled', return_value=False),
          patch.object(fl, 'ai_auto_ingest_enabled', return_value=False),
          patch.object(fl, 'ai_desc_auto_ingest_enabled', return_value=False),
          patch.object(fl, 'log_event'),
          patch.object(fl, '_notify_upload_summary') as notify,
          patch.object(fl, '_run_postprocess_serialized') as pipeline,
          patch.object(fl.media_activity, 'processing', side_effect=sqlite3.OperationalError('database is locked')),
          patch.object(fl.threading, 'Thread', InlineThread)):
        fl.UPLOAD_POSTPROCESS_STOP_EVENT.clear()
        assert fl._start_direct_upload_postprocess([rel])
        state = fl._get_upload_postprocess_state(fl.DIRECT_UPLOAD_POSTPROCESS_USER)
        assert state['running'] is False
        assert state['phase'] == 'error'
        assert state['error'] == 'database is locked'
        assert not fl.DIRECT_UPLOAD_POSTPROCESS_ACTIVE_RELS
        pipeline.assert_not_called()
        assert notify.call_args.kwargs['failed'] is True
