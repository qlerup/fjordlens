"""Discover nearby venues worldwide, then check every photo against their geometry."""
import json
import math
import os
import time
from collections import Counter, defaultdict
from contextlib import closing

import requests
from moments_engine import distance

ENDPOINTS = ('https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter')
CELL = .02


def in_ring(lat, lon, ring):
    inside = False
    for a, b in zip(ring, ring[1:]):
        if (a[0] > lat) != (b[0] > lat) and lon < a[1] + (lat-a[0])*(b[1]-a[1])/(b[0]-a[0]):
            inside = not inside
    return inside


def join_rings(parts):
    rings = []
    while parts:
        chain = list(parts.pop())
        while chain and chain[0] != chain[-1]:
            for index, part in enumerate(parts):
                if chain[-1] in (part[0], part[-1]):
                    chain.extend((part if chain[-1] == part[0] else list(reversed(part)))[1:])
                    parts.pop(index)
                    break
            else:
                chain = []  # Never treat an incomplete outline as a closed area.
        if len(chain) >= 4:
            rings.append(chain)
    return rings


def parse_venue(item):
    tags = item.get('tags', {})
    name = tags.get('name:da') or tags.get('name')
    if not name:
        return None
    venue = dict(name=name[:160], osm_id=item['id'], osm_type=item['type'],
                 category=tags.get('tourism') or tags.get('leisure'), source='OpenStreetMap')
    def points(geometry):
        return [[p['lat'], p['lon']] for p in geometry if 'lat' in p and 'lon' in p]
    if item['type'] == 'node':
        venue.update(lat=item['lat'], lon=item['lon'], outer=[], inner=[])
    elif item['type'] == 'way':
        venue.update(outer=join_rings([points(item.get('geometry', []))]), inner=[])
    else:
        parts = defaultdict(list)
        for member in item.get('members', []):
            if member.get('role') in ('outer', 'inner') and member.get('geometry'):
                parts[member['role']].append(points(member['geometry']))
        venue.update(outer=join_rings(parts['outer']), inner=join_rings(parts['inner']))
    if venue['outer']:
        pts = [p for ring in venue['outer'] for p in ring]
        venue['bounds'] = [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]
    return venue if venue['outer'] or venue.get('lat') is not None else None


def lookup_region(cell, *, deadline):
    south, west = cell[0]*CELL, cell[1]*CELL
    north, east = min(90, south+CELL), min(180, west+CELL)
    lat, lon = (south+north)/2, (west+east)/2
    bbox = f'{max(-90,south-.001):.5f},{max(-180,west-.001):.5f},{min(90,north+.001):.5f},{min(180,east+.001):.5f}'
    selectors = ('["tourism"~"^(theme_park|zoo|museum|aquarium|attraction)$"]["name"]', '["leisure"="water_park"]["name"]')
    queries = ''.join(f'nwr({bbox}){selector};way(pivot.inside){selector};rel(pivot.inside){selector};' for selector in selectors)
    query = f'[out:json][timeout:10];is_in({lat:.5f},{lon:.5f})->.inside;({queries});out geom;'
    for index, endpoint in enumerate(ENDPOINTS):
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            raise requests.Timeout('Place lookup time budget exhausted')
        try:
            response = requests.post(endpoint, data={'data': query}, timeout=(min(2,remaining/2),min(10,remaining/2)),
                                     headers={'User-Agent': 'FjordLens/1.0 (github.com/qlerup/fjordlens)'})
            response.raise_for_status()
            payload = response.json()
            if payload.get('remark'):
                raise ValueError('Incomplete venue geometry')
            return [venue for item in payload.get('elements', []) if (venue := parse_venue(item))]
        except (requests.RequestException, ValueError):
            if index == len(ENDPOINTS)-1:
                raise


def matches(venue, point):
    lat, lon = point
    if not venue['outer']:
        km = distance(dict(lat=lat,lon=lon), venue)
        return km is not None and km <= .075
    s,w,n,e = venue['bounds']
    return (s <= lat <= n and w <= lon <= e and any(in_ring(lat,lon,r) for r in venue['outer'])
            and not any(in_ring(lat,lon,r) for r in venue['inner']))


def enrich(candidates, rows, get_conn, budget=18, time_budget=20, progress=None):
    stats = dict(lookups=0, pending=0, failed=0)
    if os.environ.get('MOMENT_POI_LOOKUP','1').lower() in ('0','false','no'):
        return stats
    deadline = time.monotonic()+time_budget
    by_id = {r['id']: dict(r) for r in rows}
    failures = 0
    memory = {}
    events = sorted((c for c in candidates if c['kind'] != 'year_review'), key=lambda c:c['start_date'], reverse=True)
    for index, candidate in enumerate(events,1):
        points = []
        for pid in candidate['photo_ids']:
            row = by_id.get(pid,{})
            loc = dict(lat=row.get('gps_lat'),lon=row.get('gps_lon'))
            if distance(loc,loc) is not None:
                points.append((float(loc['lat']),float(loc['lon'])))
        cells = Counter((min(4499,math.floor(lat/CELL)),min(8999,math.floor(lon/CELL))) for lat,lon in points)
        venues = {}
        incomplete = False
        for cell_index, (cell, _) in enumerate(cells.most_common(),1):
            if progress:
                progress(dict(phase='places',current=index,total=len(events),region=cell_index,regions=len(cells),photos=len(points)))
            key = f'venue-v1:{cell[0]}:{cell[1]}'
            if key not in memory:
                with closing(get_conn()) as conn:
                    cached = conn.execute('SELECT result_json,expires FROM moment_place_cache WHERE point=?',(key,)).fetchone()
                if cached and cached['expires'] > time.time():
                    memory[key] = json.loads(cached['result_json'])
                elif stats['lookups'] < budget and time.monotonic() < deadline and failures < 2:
                    stats['lookups'] += 1
                    try:
                        memory[key] = lookup_region(cell,deadline=deadline)
                        failures = 0
                        ttl = 30*86400 if memory[key] else 7*86400
                    except (requests.RequestException,ValueError,KeyError,TypeError):
                        memory[key], ttl = None, 300
                        failures += 1
                    with closing(get_conn()) as conn:
                        conn.execute('INSERT INTO moment_place_cache(point,result_json,expires) VALUES(?,?,?) ON CONFLICT(point) DO UPDATE SET result_json=excluded.result_json,expires=excluded.expires',
                                     (key,json.dumps(memory[key],ensure_ascii=False),time.time()+ttl))
                        conn.commit()
                else:
                    stats['pending'] += 1
                    incomplete = True
                    continue
            if memory[key] is None:
                stats['failed'] += 1
                incomplete = True
                continue
            for venue in memory[key]:
                venues[(venue['osm_type'],venue['osm_id'])] = venue
        if incomplete:
            candidate['evidence']['attraction_lookup_pending'] = True
        if not venues or not points:
            continue
        # Count photos, not a handful of representative coordinate samples.
        counts = [(sum(matches(venue,point) for point in points),venue) for venue in venues.values()]
        count, venue = max(counts,key=lambda pair:(pair[0],pair[1]['category'] in ('theme_park','zoo','aquarium','water_park'),bool(pair[1]['outer'])))
        if count < 5 or count < len(points)*.6 or count < len(candidate['photo_ids'])*.5:
            continue
        inside = bool(venue['outer'])
        info = {k:venue[k] for k in ('name','osm_type','osm_id','category','source')}
        info.update(match='inside' if inside else 'nearby',confidence='high' if inside else 'possible',
                    photo_matches=count,photo_total=len(candidate['photo_ids']),gps_photo_total=len(points))
        candidate['evidence']['attraction'] = info
        candidate['title'] = f"En tur til {venue['name']}"
        candidate['primary_place'] = venue['name']
        where = 'inde i det kortlagte område for' if inside else 'tæt ved'
        candidate['evidence']['reasons'].append(f"{count} af {len(candidate['photo_ids'])} billeder er taget {where} {venue['name']}. Steddata: © OpenStreetMap-bidragydere.")
    return stats
