"""Restore known Nordic place spellings without guessing at arbitrary text."""
import json
import gettext
import pycountry
import unicodedata
from functools import lru_cache
from pathlib import Path

COUNTRIES = {'dk': 'DK', 'danmark': 'DK', 'denmark': 'DK',
             'no': 'NO', 'norge': 'NO', 'norway': 'NO',
             'se': 'SE', 'sverige': 'SE', 'sweden': 'SE'}


@lru_cache(maxsize=1)
def country_names():
    translate = gettext.translation('iso3166-1', pycountry.LOCALES_DIR, languages=['da']).gettext
    names = {c.alpha_2: translate(getattr(c, 'common_name', c.name)) for c in pycountry.countries}
    names.update(TR='Tyrkiet', GB='Storbritannien', US='USA', NL='Nederlandene',
                 CZ='Tjekkiet', KR='Sydkorea', KP='Nordkorea', RU='Rusland',
                 VN='Vietnam', IR='Iran', SY='Syrien', TW='Taiwan', LA='Laos',
                 BO='Bolivia', VE='Venezuela', MD='Moldova', TZ='Tanzania')
    return names


@lru_cache(maxsize=1)
def country_aliases():
    result = dict(COUNTRIES)
    for c in pycountry.countries:
        for name in (c.alpha_2, c.alpha_3, c.name, getattr(c, 'official_name', ''),
                     getattr(c, 'common_name', ''), country_names()[c.alpha_2]):
            if name:
                result[unicodedata.normalize('NFC', name).casefold()] = c.alpha_2
    result.update({'turkey':'TR', 'türkiye':'TR', 'turkiye':'TR', 'deutschland':'DE', 'holland':'NL', 'uk':'GB'})
    return result


def country_code(name):
    return country_aliases().get(unicodedata.normalize('NFC', str(name or '').strip()).casefold())


def country_name(name):
    return country_names().get(country_code(name), name)


@lru_cache(maxsize=1)
def aliases():
    return json.loads((Path(__file__).parent / 'resources/place_name_aliases.json').read_text(encoding='utf-8'))


def city_name(name, country):
    if not isinstance(name, str):
        return name
    name = unicodedata.normalize('NFC', name)
    cc = country_code(country)
    return aliases().get(cc, {}).get(name.strip().casefold(), name)


def place_name(name, country=None):
    if not isinstance(name, str):
        return name
    if ',' in name:
        city, suffix = name.rsplit(',', 1)
        return city_name(city.strip(), suffix) + ', ' + country_name(suffix.strip())
    return city_name(name, country) if country else country_name(name)


def photo_places(photo):
    """Normalize only location fields, preserving captions, paths and other metadata."""
    photo['gps_name'] = place_name(photo.get('gps_name'))
    meta = photo.get('metadata_json')
    if isinstance(meta, dict) and isinstance(meta.get('geo'), dict):
        geo = meta['geo']
        if geo.get('city'):
            geo['city'] = city_name(geo['city'], geo.get('country'))
        if geo.get('country'):
            geo['country'] = country_name(geo['country'])
    return photo


def migrate(conn):
    marker = 'native_place_names_v2_danish_countries'
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
            country = country_name(row['country'])
            if city != row['city'] or country != row['country']:
                conn.execute(f'UPDATE {table} SET city=?,country=? WHERE rowid=?', (city, country, row['cache_rowid']))
    for row in conn.execute("SELECT * FROM moments WHERE COALESCE(video_status,'none') NOT IN ('queued','running','rendering')").fetchall():
        old = row['primary_place']
        new = place_name(old)
        if old and new != old:
            title = row['title']
            if not row['user_edited']:
                title = title.replace(old, new)
            evidence = row['evidence_json']
            if evidence:
                # Replace a known full place label in the structured evidence only.
                evidence = json.dumps(json.loads(evidence), ensure_ascii=False).replace(old, new)
            conn.execute("""UPDATE moments SET title=?,primary_place=?,evidence_json=?,
                script_json=NULL,subtitle=NULL,video_status='none',video_rel_path=NULL,
                video_error=NULL,revision=revision+1 WHERE id=?""", (title, new, evidence, row['id']))
    conn.execute('INSERT INTO settings(key,value) VALUES(?,?)', (marker, '1'))
