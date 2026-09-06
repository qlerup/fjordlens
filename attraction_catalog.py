"""Count photos inside mapped park boundaries, including multipolygons and holes."""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def parks():
    items = json.loads((Path(__file__).parent / 'resources/attraction_catalog.json').read_text(encoding='utf-8'))
    for item in items:
        points = [p for ring in item['outer'] for p in ring]
        item['bounds'] = (min(p[0] for p in points), min(p[1] for p in points),
                          max(p[0] for p in points), max(p[1] for p in points))
    return items


def in_ring(lat, lon, ring):
    inside = False
    for a, b in zip(ring, ring[1:]):
        if (a[0] > lat) != (b[0] > lat):
            crossing = a[1] + (lat-a[0]) * (b[1]-a[1]) / (b[0]-a[0])
            if lon < crossing:
                inside = not inside
    return inside


def contains(park, lat, lon):
    south, west, north, east = park['bounds']
    return (south <= lat <= north and west <= lon <= east
            and any(in_ring(lat, lon, ring) for ring in park['outer'])
            and not any(in_ring(lat, lon, ring) for ring in park['inner']))


def visit(rows, total):
    points = []
    for row in rows:
        try:
            lat, lon = float(row['gps_lat']), float(row['gps_lon'])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                points.append((lat, lon))
        except (TypeError, ValueError, KeyError):
            pass
    matches = [(sum(contains(park, *point) for point in points), park) for park in parks()]
    count, park = max(matches, key=lambda match: match[0])
    # A few passing photos must not rename a trip containing other destinations.
    if count < 5 or count < len(points) * .6 or count < total * .5:
        return None
    return dict(name=park['name'], osm_type=park['osm_type'], osm_id=park['osm_id'],
                category=park['category'], match='inside', confidence='high',
                source='OpenStreetMap', photo_matches=count, photo_total=total, gps_photo_total=len(points))
