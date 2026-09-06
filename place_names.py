"""Restore known Nordic place spellings without guessing at arbitrary text."""
import json
import unicodedata
from functools import lru_cache
from pathlib import Path

COUNTRIES = {'dk': 'DK', 'danmark': 'DK', 'denmark': 'DK',
             'no': 'NO', 'norge': 'NO', 'norway': 'NO',
             'se': 'SE', 'sverige': 'SE', 'sweden': 'SE'}


@lru_cache(maxsize=1)
def aliases():
    return json.loads((Path(__file__).parent / 'resources/place_name_aliases.json').read_text(encoding='utf-8'))


def city_name(name, country):
    if not isinstance(name, str):
        return name
    name = unicodedata.normalize('NFC', name)
    cc = COUNTRIES.get(str(country or '').strip().casefold())
    return aliases().get(cc, {}).get(name.strip().casefold(), name)


def place_name(name, country=None):
    if not isinstance(name, str):
        return name
    if ',' in name:
        city, suffix = name.rsplit(',', 1)
        return city_name(city.strip(), suffix) + ',' + suffix
    return city_name(name, country)


def photo_places(photo):
    """Normalize only location fields, preserving captions, paths and other metadata."""
    photo['gps_name'] = place_name(photo.get('gps_name'))
    meta = photo.get('metadata_json')
    if isinstance(meta, dict) and isinstance(meta.get('geo'), dict):
        geo = meta['geo']
        if geo.get('city'):
            geo['city'] = city_name(geo['city'], geo.get('country'))
    return photo


def migrate(conn):
    marker = 'native_place_names_v1'
    if conn.execute('SELECT 1 FROM settings WHERE key=?', (marker,)).fetchone():
        return
    for row in conn.execute('SELECT id,gps_name,metadata_json FROM photos').fetchall():
        try:
            meta = json.loads(row['metadata_json'] or '{}')
        except (ValueError, TypeError):
            meta = None
        original = json.dumps(meta, ensure_ascii=False)
        fixed = photo_places(dict(gps_name=row['gps_name'], metadata_json=meta))
        encoded = json.dumps(meta, ensure_ascii=False)
        if fixed['gps_name'] != row['gps_name'] or encoded != original:
            conn.execute('UPDATE photos SET gps_name=?,metadata_json=? WHERE id=?',
                         (fixed['gps_name'], encoded if encoded != original else row['metadata_json'], row['id']))
    for table in ('geo_cache', 'place_geocode_cache'):
        for row in conn.execute(f'SELECT rowid AS cache_rowid,city,country FROM {table}').fetchall():
            city = city_name(row['city'], row['country'])
            if city != row['city']:
                conn.execute(f'UPDATE {table} SET city=? WHERE rowid=?', (city, row['cache_rowid']))
    for row in conn.execute("SELECT * FROM moments WHERE COALESCE(video_status,'none') NOT IN ('queued','running','rendering')").fetchall():
        old = row['primary_place']
        new = place_name(old)
        if old and new != old:
            title = row['title']
            if row['status'] == 'suggested' and not row['user_edited']:
                title = title.replace(old, new)
            evidence = row['evidence_json']
            if evidence:
                # Replace a known full place label in the structured evidence only.
                evidence = json.dumps(json.loads(evidence), ensure_ascii=False).replace(old, new)
            conn.execute("""UPDATE moments SET title=?,primary_place=?,evidence_json=?,
                script_json=NULL,subtitle=NULL,video_status='none',video_rel_path=NULL,
                video_error=NULL,revision=revision+1 WHERE id=?""", (title, new, evidence, row['id']))
    conn.execute('INSERT INTO settings(key,value) VALUES(?,?)', (marker, '1'))
