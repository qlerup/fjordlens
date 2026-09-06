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



from moment_venues import enrich
