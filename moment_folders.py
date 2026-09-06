"""Use the dominant source folder only when a moment still has a generic title."""
from collections import Counter
import json
import re
from datetime import date

MIN_FOLDER_PERCENT = 75


def clean_name(value):
    # Handle multiple and nested parenthesized notes without losing Danish letters.
    depth, output = 0, []
    for char in str(value):
        if char == '(':
            depth += 1
            if depth == 1:
                output.append(' ')
        elif char == ')' and depth:
            depth -= 1
        elif not depth:
            output.append(char)
    return re.sub(r'\s+', ' ', ''.join(output)).strip(' -_·')[:240]


def folder_key(rel_path):
    parts = str(rel_path or '').replace('\\', '/').strip('/').split('/')[:-1]
    if parts and parts[0].casefold() == 'uploads':
        parts = parts[1:]
        if parts and parts[0].casefold() in ('originals', 'converted'):
            parts = parts[1:]
    return '/'.join(parts)


def generic_title(candidate):
    info = candidate.get('evidence') or {}
    if info.get('attraction') or info.get('occasion'):
        return False
    if info.get('title_source') in ('journey', 'trip', 'activity', 'occasion', 'folder'):
        return False
    title = re.sub(r'\s*·\s*\d{2}\.\d{2}\.\d{4}$', '', candidate.get('title') or '')
    place = candidate.get('primary_place')
    return title in ('Dagens oplevelser', 'Oplevelser') or bool(place and title == f'En dag i {place}')


def apply(candidates, rows):
    folders = {r['id']: folder_key(r['rel_path']) for r in rows}
    changed = 0
    for candidate in candidates:
        if not generic_title(candidate):
            continue
        counts = Counter(folders.get(pid, '') for pid in set(candidate['photo_ids']))
        if not counts:
            continue
        folder, count = min(counts.items(), key=lambda entry: (-entry[1], entry[0].casefold(), entry[0]))
        total = len(set(candidate['photo_ids']))
        if count * 100 < MIN_FOLDER_PERCENT * total:
            continue
        name = clean_name(folder.rsplit('/', 1)[-1])
        # Storage roots, camera folders and date-only names don't describe an event.
        if not name or name.casefold() in {'uploads', 'originals', 'converted', 'photos', 'pictures', 'images',
                'billeder', 'fotos', 'dcim', 'camera', 'camera roll', 'screenshots', 'downloads', 'thumbs'}:
            continue
        if re.fullmatch(r'[\d\W_]+|\d{3}[A-Za-z_]+', name):
            continue
        info = candidate['evidence']
        fallback_title = candidate['title']
        fallback_source = info.get('title_source', 'place' if candidate.get('primary_place') else 'generic')
        candidate['title'] = name
        info['title_source'] = 'folder'
        info['folder_title'] = dict(name=name, photo_count=count, total_photos=total,
                                   fallback_title=fallback_title, fallback_source=fallback_source)
        info.setdefault('reasons', []).append(f'Titlen kommer fra mappen “{name}”, som bidrager med {count} af {total} billeder (mindst {MIN_FOLDER_PERCENT} %). Parenteser er fjernet.')
        changed += 1
    return changed


def upgrade_suggestions(conn):
    """Refresh existing automatic generic suggestions without a full GPS rescan."""
    candidates, before = [], {}
    for row in conn.execute("""SELECT * FROM moments WHERE status='suggested' AND user_edited=0
            AND kind!='year_review' AND COALESCE(video_status,'none') NOT IN ('queued','running','rendering')"""):
        candidate = dict(row)
        candidate['evidence'] = json.loads(row['evidence_json'] or '{}')
        candidate['photo_ids'] = json.loads(row['photo_ids_json'] or '[]')
        info = candidate['evidence']
        before[row['id']] = (row['title'], json.dumps(info, sort_keys=True))
        if info.get('title_source') == 'folder' and not (info.get('attraction') or info.get('occasion')):
            previous = info.get('folder_title') or {}
            # Only reconsider the title we generated, never a subsequently chosen name.
            if candidate['title'] != previous.get('name'):
                continue
            fallback = previous.get('fallback_title')
            if not fallback:
                place = candidate.get('primary_place')
                single_day = candidate['start_date'] == candidate['end_date']
                fallback = (f'En dag i {place}' if single_day else f'Tur til {place}') if place else ('Dagens oplevelser' if single_day else 'Oplevelser')
                fallback += f" · {date.fromisoformat(candidate['start_date']).strftime('%d.%m.%Y')}"
            candidate['title'] = fallback
            info['title_source'] = previous.get('fallback_source', 'place' if candidate.get('primary_place') else 'generic')
            info.pop('folder_title', None)
            info['reasons'] = [r for r in info.get('reasons', []) if not r.startswith('Titlen kommer fra mappen')]
        if generic_title(candidate):
            candidates.append(candidate)
    ids = sorted({pid for c in candidates for pid in c['photo_ids']})
    rows = []
    for offset in range(0, len(ids), 500):
        batch = ids[offset:offset+500]
        rows.extend(conn.execute(f"SELECT id,rel_path FROM photos WHERE id IN ({','.join('?' for _ in batch)})", batch))
    apply(candidates, rows)
    for candidate in candidates:
        if (candidate['title'], json.dumps(candidate['evidence'], sort_keys=True)) == before[candidate['id']]:
            continue
        conn.execute("""UPDATE moments SET title=?,evidence_json=?,script_json=NULL,subtitle=NULL,
            video_status='none',video_rel_path=NULL,video_error=NULL,revision=revision+1,
            updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?""",
            (candidate['title'], json.dumps(candidate['evidence'], ensure_ascii=False), candidate['id']))
