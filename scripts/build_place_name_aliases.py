"""Rebuild the bundled Nordic place spellings from GeoNames (CC BY 4.0)."""
import io
import json
import unicodedata
import zipfile
from collections import defaultdict
from pathlib import Path

import requests


def build():
    output = {}
    for country in ('DK', 'NO', 'SE'):
        response = requests.get(f'https://download.geonames.org/export/dump/{country}.zip', timeout=60)
        response.raise_for_status()
        archive = zipfile.ZipFile(io.BytesIO(response.content))
        rows = [line.split('\t') for line in archive.read(f'{country}.txt').decode('utf-8').splitlines()]
        rows = [r for r in rows if r[6] == 'P']
        canonical = {r[1].casefold() for r in rows}
        candidates = defaultdict(set)
        for row in rows:
            name = row[1]
            aliases = {row[2], name.translate(str.maketrans({'æ': 'ae', 'Æ': 'Ae', 'ø': 'oe', 'Ø': 'Oe', 'å': 'aa', 'Å': 'Aa'}))}
            for alias in aliases:
                alias = ''.join(c for c in unicodedata.normalize('NFKD', alias) if not unicodedata.combining(c))
                if alias.casefold() != name.casefold():
                    candidates[alias.casefold()].add(name)
        output[country] = {alias: next(iter(names)) for alias, names in candidates.items()
                           if len(names) == 1 and alias not in canonical}
    output['DK'].update({'copenhagen': 'København', 'kobenhavn': 'København', 'koebenhavn': 'København'})
    for name in ('Aarhus', 'Aalborg', 'Aabenraa'):
        output['DK'].pop(name.casefold(), None)
    target = Path(__file__).resolve().parents[1] / 'resources' / 'place_name_aliases.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    print({country: len(names) for country, names in output.items()})


if __name__ == '__main__':
    build()
