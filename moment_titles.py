"""Consistent dates on automatic moment titles, separate from slideshow text."""
from datetime import date
import json
import re


def base_title(title):
    value = str(title or '').strip()
    # Remove an existing trailing date/year, including one from a folder name.
    match = re.search(r'\s+(?:[·–—-]\s*)?(\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4}|\d{4})$', value)
    if match:
        token = match[1]
        try:
            if '.' in token:
                day, month, year = map(int, token.split('.'))
                date(year, month, day)
            elif '-' in token:
                date.fromisoformat(token)
            elif not 1000 <= int(token) <= 2999:
                return value
        except ValueError:
            return value
        return value[:match.start()].rstrip(' ·–—-') or value
    return value


def format_title(title, start, end, dominant_date=None):
    try:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
    except (ValueError, TypeError):
        return title
    year = first.year
    if dominant_date:
        try:
            dominant = date.fromisoformat(dominant_date)
            if first <= dominant <= last:
                year = dominant.year
        except (ValueError, TypeError):
            pass
    suffix = first.strftime('%d.%m.%Y') if first == last else str(year)
    return f'{base_title(title)} · {suffix}'


def apply(candidate):
    info = candidate.get('evidence') or {}
    folder = info.get('folder_title') or {}
    candidate['title'] = format_title(candidate['title'], candidate.get('start_date'),
                                     candidate.get('end_date'), folder.get('dominant_date'))
    if info.get('title_source') == 'folder':
        folder['generated_title'] = candidate['title']


def upgrade(conn):
    for row in conn.execute("""SELECT * FROM moments WHERE status IN ('suggested','saved') AND user_edited=0
            AND COALESCE(video_status,'none') NOT IN ('queued','running','rendering')""").fetchall():
        candidate = dict(row, evidence=json.loads(row['evidence_json'] or '{}'))
        apply(candidate)
        if candidate['title'] == row['title']:
            continue
        conn.execute("""UPDATE moments SET title=?,evidence_json=?,script_json=NULL,subtitle=NULL,
            video_status='none',video_rel_path=NULL,video_error=NULL,revision=revision+1,
            updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?""",
            (candidate['title'], json.dumps(candidate['evidence'], ensure_ascii=False), row['id']))
