from datetime import datetime, timedelta
from moments_engine import curate


def test_dense_morning_burst_does_not_hide_rest_of_day():
    base = datetime(2026, 6, 26, 10)
    offsets = list(range(200)) + [3600*i for i in range(1, 11)]
    rows = [dict(id=i, captured_at=(base+timedelta(seconds=t)).isoformat()) for i,t in enumerate(offsets)]
    selected = curate(rows, 12)
    assert selected[0]['id'] == 0
    assert selected[-1]['id'] == len(rows)-1
    assert sum(r['id'] >= 200 for r in selected) >= 9
    assert selected == sorted(selected, key=lambda r:r['captured_at'])
    assert selected == curate(list(reversed(rows)), 12)


def test_burst_is_not_used_to_pad_slideshow_when_hashes_are_missing():
    rows = [dict(id=i,captured_at=f'2026-06-26T10:00:{i:02}') for i in range(15)]
    assert len(curate(rows, 60)) == 1
