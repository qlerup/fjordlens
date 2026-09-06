from moments_engine import discover


def test_home_country_separates_distant_domestic_outings_but_keeps_foreign_trip():
    home = dict(name='Næstved, Danmark',lat=55.23,lon=11.76)
    rows = [dict(id=day*100+i, captured_at=f'2026-05-{day:02}T{10+i:02}:00:00',
                 gps_name=name,gps_lat=lat,gps_lon=lon) for day,name,lat,lon in
            [(24,'Klampenborg, Danmark',55.775,12.577),(27,'Starup, Danmark',55.24,9.55)] for i in range(4)]
    candidates,_,_=discover(rows,min_photos=3,min_hours=1,manual_home=home)
    assert len(candidates)==2
    assert all(c['start_date']==c['end_date'] for c in candidates)
    for row in rows:
        row.update(gps_name='Antalya, Tyrkiet',gps_lat=36.9,gps_lon=30.7)
    candidates,_,_=discover(rows,min_photos=3,min_hours=1,manual_home=home)
    assert len(candidates)==1
    assert candidates[0]['title'].startswith('Rejse til Tyrkiet')
