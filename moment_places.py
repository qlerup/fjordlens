"""Cached, bounded attraction lookups. Only coordinates leave the server.

Queries use OSM polygon containment first; nearby nodes are explicitly uncertain.
See https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL#Query_for_areas_(is_in)
"""
import json
import os
import time
from collections import Counter
from contextlib import closing

import requests
import attraction_catalog

from moments_engine import distance

ENDPOINT = 'https://overpass-api.de/api/interpreter'
FALLBACK_ENDPOINT = 'https://overpass.private.coffee/api/interpreter'


def attraction_title(attraction):
    name = str(attraction.get('name') or '').strip()
    if not name:
        return None
    return f'En tur til {name}'


def lookup(lat, lon, *, deadline=None):
    lat, lon = float(lat), float(lon)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return []
    query = f'''[out:json][timeout:10];
        is_in({lat:.5f},{lon:.5f})->.inside;
        (area.inside["tourism"~"^(theme_park|zoo|museum|aquarium|attraction)$"]["name"];
         area.inside["leisure"="water_park"]["name"];);out tags;
        (nwr(around:100,{lat:.5f},{lon:.5f})["tourism"~"^(theme_park|zoo|museum|aquarium|attraction)$"]["name"];
         nwr(around:100,{lat:.5f},{lon:.5f})["leisure"="water_park"]["name"];);out center;'''
    payload = None
    for endpoint in (ENDPOINT, FALLBACK_ENDPOINT):
        try:
            remaining = deadline - time.monotonic() if deadline is not None else 20
            if remaining <= 0:
                raise requests.Timeout('Attraction lookup time budget exhausted')
            response = requests.post(endpoint, data={'data': query}, timeout=(min(2, remaining / 2), min(10, remaining / 2)),
                                     headers={'User-Agent': 'FjordLens/1.0 (moment place lookup; github.com/qlerup/fjordlens)'})
            response.raise_for_status()
            payload = response.json()
            if payload.get('remark'):
                raise ValueError('Incomplete attraction lookup')
            break
        except (requests.RequestException, ValueError):
            if endpoint == FALLBACK_ENDPOINT:
                raise
    results = []
    for item in payload.get('elements', []):
        tags = item.get('tags', {})
        name = tags.get('name:da') or tags.get('name')
        if not name:
            continue
        inside = item.get('type') == 'area'
        results.append(dict(name=name[:160], osm_id=item['id'], osm_type=item['type'],
                            category=tags.get('tourism') or tags.get('leisure'),
                            match='inside' if inside else 'nearby', source='OpenStreetMap'))
    return sorted(results, key=lambda r: (r['match'] != 'inside', r['category'] not in ('theme_park', 'zoo', 'water_park')))


def enrich(candidates, rows, get_conn, budget=18, time_budget=20, progress=None):
    if os.environ.get('MOMENT_POI_LOOKUP', '1').lower() in ('0', 'false', 'no'):
        return dict(lookups=0, pending=0, failed=0)
    by_id = {r['id']: dict(r) for r in rows}
    stats = dict(lookups=0, pending=0, failed=0)
    deadline = time.monotonic() + time_budget
    consecutive_failures = 0
    events = sorted((c for c in candidates if c['kind'] != 'year_review'), key=lambda c: c['start_date'], reverse=True)
    for index, candidate in enumerate(events, 1):
        if progress:
            progress(dict(phase='places', current=index, total=len(events)))
        visit = attraction_catalog.visit([by_id[pid] for pid in candidate['photo_ids'] if pid in by_id], len(candidate['photo_ids']))
        if visit:
            candidate['evidence']['attraction'] = visit
            candidate['title'] = attraction_title(visit)
            candidate['primary_place'] = visit['name']
            candidate['evidence']['reasons'].append(f"{visit['photo_matches']} af {visit['photo_total']} billeder er taget inde i {visit['name']}. Steddata: © OpenStreetMap-bidragydere.")
            continue
        points = []
        seen_points = set()
        for pid in candidate['photo_ids']:
            row = by_id.get(pid, {})
            loc = dict(lat=row.get('gps_lat'), lon=row.get('gps_lon'))
            if distance(loc, loc) is not None:
                point = (round(float(loc['lat']), 5), round(float(loc['lon']), 5))
                if point not in seen_points:
                    points.append(point)
                    seen_points.add(point)
        if not points:
            continue
        sample = list(dict.fromkeys(points[i] for i in (0, len(points)//2, len(points)-1)))
        hits = []
        unresolved = False
        for lat, lon in sample:
            key = f'v2:{lat:.5f},{lon:.5f}'
            with closing(get_conn()) as conn:
                cached = conn.execute('SELECT result_json,expires FROM moment_place_cache WHERE point=?', (key,)).fetchone()
            if cached and cached['expires'] > time.time():
                result = json.loads(cached['result_json'])
                if result is None:
                    unresolved = True
                    stats['failed'] += 1
                    continue
            elif stats['lookups'] < budget and time.monotonic() < deadline and consecutive_failures < 2:
                if stats['lookups']:
                    time.sleep(1)
                stats['lookups'] += 1
                try:
                    result = lookup(lat, lon, deadline=deadline)
                    consecutive_failures = 0
                    ttl = 30*86400 if result else 7*86400
                except (requests.RequestException, ValueError, KeyError, TypeError):
                    stats['failed'] += 1
                    consecutive_failures += 1
                    result, ttl = None, 3600
                    unresolved = True
                with closing(get_conn()) as conn:
                    conn.execute('INSERT INTO moment_place_cache(point,result_json,expires) VALUES(?,?,?) ON CONFLICT(point) DO UPDATE SET result_json=excluded.result_json,expires=excluded.expires',
                                 (key, json.dumps(result, ensure_ascii=False), time.time()+ttl))
                    conn.commit()
            else:
                stats['pending'] += 1
                unresolved = True
                continue
            if result:
                hits.append(result[0])
        if not hits:
            continue
        counts = Counter((hit['osm_type'], hit['osm_id']) for hit in hits)
        winner, count = counts.most_common(1)[0]
        selected = next(h for h in hits if (h['osm_type'], h['osm_id']) == winner)
        confident = selected['match'] == 'inside' and count > len(sample)/2 and not unresolved
        info = candidate['evidence']
        info['attraction'] = dict(selected, confidence='high' if confident else 'possible', sample_matches=count, sample_size=len(sample))
        candidate['title'] = attraction_title(info['attraction'])
        if confident:
            candidate['primary_place'] = selected['name']
            info['reasons'].append(f"GPS-positionerne ligger i det kortlagte område for {selected['name']}. Steddata: © OpenStreetMap-bidragydere.")
        else:
            info['reasons'].append(f"Muligt besøg ved {selected['name']}; koordinaterne giver ikke et sikkert match. Steddata: © OpenStreetMap-bidragydere.")
    return stats
