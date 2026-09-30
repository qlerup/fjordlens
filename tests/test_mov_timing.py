import unittest
from mov_timing import INTENT, slow_motion_factor, timing_args


class SlowMotionTests(unittest.TestCase):
    def metadata(self, intent='0', rate='120/1', average='82400/687'):
        return {'format': {'tags': {INTENT:intent}}, 'streams': [
            {'codec_type':'audio'}, {'codec_type':'video', 'r_frame_rate':rate, 'avg_frame_rate':average}]}

    def test_explicit_slow_motion_only(self):
        self.assertEqual(slow_motion_factor(self.metadata()),4)
        self.assertEqual(slow_motion_factor(self.metadata(rate='240/1',average='240/1')),8)
        for data in [self.metadata(intent='1'),self.metadata(intent=''),{},
                     self.metadata(rate='60/1',average='60/1'),self.metadata(average='30/1'),
                     self.metadata(average='0/0'),self.metadata(rate='invalid')]:
            self.assertEqual(slow_motion_factor(data),1)

    def test_matching_audio_video_timing_and_no_double_slowdown_tag(self):
        args=timing_args(4,True)
        self.assertIn('setpts=4*(PTS-STARTPTS)',args)
        self.assertIn('asetpts=PTS-STARTPTS,atempo=0.5,atempo=0.5',args)
        self.assertIn(INTENT+'=1',args)
        self.assertNotIn('-af',timing_args(4,False))
        self.assertEqual(timing_args(1,True),[])

if __name__=='__main__':
    unittest.main()
