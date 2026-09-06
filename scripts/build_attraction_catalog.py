"""Refresh mapped park boundaries from OpenStreetMap (ODbL)."""
import json
from pathlib import Path
import requests

PARKS = [('way', 4521936, 'Bakken'), ('way', 34963526, 'Legoland'),
         ('way', 105806946, 'BonBon-Land'), ('relation', 18514035, 'Knuthenborg Safaripark'),
         ('relation', 6388844, 'Københavns Zoo')]


def rings(parts):
    result = []
    while parts:
        chain = list(parts.pop())
        while chain[0] != chain[-1]:
            for i, other in enumerate(parts):
                if chain[-1] in (other[0], other[-1]):
                    if chain[-1] == other[-1]:
                        other = list(reversed(other))
                    chain.extend(other[1:])
                    parts.pop(i)
                    break
            else:
                raise ValueError('Unclosed park boundary')
        result.append(chain)
    return result


def build():
    catalog = []
    for kind, osm_id, name in PARKS:
        response = requests.get(f'https://www.openstreetmap.org/api/0.6/{kind}/{osm_id}/full.json', timeout=20)
        response.raise_for_status()
        elements = response.json()['elements']
        nodes = {e['id']: [e['lat'], e['lon']] for e in elements if e['type'] == 'node'}
        ways = {e['id']: e for e in elements if e['type'] == 'way'}
        feature = next(e for e in elements if e['type'] == kind and e['id'] == osm_id)
        if kind == 'way':
            outer, inner = [feature['nodes']], []
        else:
            outer = [ways[m['ref']]['nodes'] for m in feature['members'] if m['type'] == 'way' and m['role'] == 'outer']
            inner = [ways[m['ref']]['nodes'] for m in feature['members'] if m['type'] == 'way' and m['role'] == 'inner']
        polygons = {key: [[nodes[n] for n in ring] for ring in rings(list(parts))] for key, parts in [('outer', outer), ('inner', inner)]}
        assert polygons['outer'], name
        catalog.append(dict(name=name, osm_type=kind, osm_id=osm_id, category=feature['tags']['tourism'], **polygons))
    target = Path(__file__).resolve().parents[1] / 'resources' / 'attraction_catalog.json'
    target.write_text(json.dumps(catalog, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'{len(catalog)} park boundaries')


if __name__ == '__main__':
    build()
