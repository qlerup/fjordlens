"""Shared cinematic timeline and typography for browser playback and MP4 export."""
import subprocess
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

from moments_engine import photo_date, location, DA_COUNTRIES

VERSION = 3
MONTHS = ('januar februar marts april maj juni juli august september oktober november december').split()


def date_label(value):
    dt = photo_date({'captured_at': value})
    return f'{dt.day}. {MONTHS[dt.month-1]} {dt.year}' if dt else ''


def date_range(start, end):
    return date_label(start) if start == end else ' – '.join(filter(None, (date_label(start), date_label(end))))


def needs_upgrade(script_json):
    import json
    try:
        script = json.loads(script_json or '[]')
        return not script or script[0].get('design_version') != VERSION
    except (ValueError, TypeError, AttributeError, IndexError):
        return True


def timeline(moment, rows, *, title=None, subtitle=None, cards=(), video_exts=()):
    if not rows:
        return []
    rows = [dict(r) for r in rows]
    period = date_range(moment['start_date'], moment['end_date'])
    film_title = title or moment['title'] or 'Et øjeblik at huske'
    if not moment.get('user_edited'):
        film_title = re.sub(r'\s*·\s*(?:\d{4}-\d{2}-\d{2}|\d{2}\.\d{2}\.\d{4})$', '', film_title)
    script = [dict(type='text', style='intro', text=film_title,
                   eyebrow=moment['primary_place'] or 'ET MOMENT', detail=period,
                   background_photo_id=rows[0]['id'], duration=4.6, design_version=VERSION)]
    last_place, last_day, last_chapter = None, None, 0
    quotes = [str(c).strip() for c in cards if str(c).strip()][:2]
    if subtitle and not quotes:
        quotes = [subtitle]
    for index, row in enumerate(rows):
        loc = location(row)
        place = loc['name']
        city = place.split(',')[0].strip() if place else ''
        country = DA_COUNTRIES.get(loc['country'], loc['country'] or '')
        dt = photo_date(row)
        day = dt.date().isoformat() if dt else None
        changed = bool(index and ((place and place != last_place) or (day and day != last_day)))
        if changed and index-last_chapter >= 4:
            script.append(dict(type='text', style='chapter', text=city or date_label(day),
                               eyebrow=country or 'NÆSTE KAPITEL', detail=date_label(day) if city else '',
                               background_photo_id=row['id'], duration=3.2, design_version=VERSION))
            last_chapter = index
        show_label = index == 0 or changed or index % 3 == 0
        # Do not present import/file times as the time of an experience.
        captured = photo_date({'captured_at': row.get('captured_at')})
        clock = captured.strftime('%H:%M') if captured and index % 3 == 0 else ''
        label_date = date_label(day) if row.get('captured_at') else ''
        script.append(dict(type='video' if str(row.get('ext') or '').lower() in video_exts else 'photo',
                           photo_id=row['id'], duration=7.0 if str(row.get('ext') or '').lower() in video_exts else 5.2,
                           motion=index % 4, layout='right' if index % 2 else 'left',
                           fit='contain' if (row.get('height') or 0) > (row.get('width') or 0) else 'cover',
                           label=city if show_label else '', eyebrow=country if show_label else '',
                           detail=' · '.join(filter(None, (label_date, clock))) if show_label else '',
                           design_version=VERSION))
        if index and index % 12 == 0 and quotes:
            script.append(dict(type='text', style='quote', text=quotes.pop(0), eyebrow='ET ØJEBLIK UNDERVEJS',
                               detail='', background_photo_id=row['id'], duration=4.2, design_version=VERSION))
        last_place, last_day = place or last_place, day or last_day
    script.append(dict(type='text', style='outro', text='Minder at vende tilbage til',
                       eyebrow=moment['primary_place'] or 'DIT MOMENT', detail=period,
                       background_photo_id=rows[-1]['id'], duration=3.8, design_version=VERSION))
    return script


def _font(size, serif=False):
    candidates = (['/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf', 'C:/Windows/Fonts/georgia.ttf'] if serif else
                  ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/segoeui.ttf'])
    for filename in candidates:
        try:
            return ImageFont.truetype(filename, max(10, int(size)))
        except OSError:
            pass
    return ImageFont.load_default(size=max(10, int(size)))


def _wrap(draw, text, font, max_width):
    lines, line = [], ''
    # Splitting long words also keeps filenames/unbroken titles within the frame.
    for word in str(text or '').split():
        if line and draw.textlength(line + ' ' + word, font=font) > max_width:
            lines.append(line)
            line = ''
        if draw.textlength(word, font=font) > max_width:
            for char in word:
                if draw.textlength(line + char, font=font) > max_width:
                    lines.append(line)
                    line = ''
                line += char
        else:
            line = (line + ' ' + word).strip()
    if line:
        lines.append(line)
    return lines


def overlay(item, size):
    """Render typography to transparent pixels; never interpolate user text in ffmpeg."""
    w, h = size
    canvas = Image.new('RGBA', size)
    draw = ImageDraw.Draw(canvas)
    card = item.get('type') == 'text'
    right = item.get('layout') == 'right' and not card
    text = str(item.get('text') if card else item.get('label') or '')[:500]
    eyebrow = str(item.get('eyebrow') or '')[:100].upper()
    detail = str(item.get('detail') or '')[:180]
    if not any((text, eyebrow, detail)):
        return canvas
    # Dark photographic scrim keeps white type readable over bright snow/sky.
    for y in range(h):
        alpha = 110 if card else int(175 * max(0, (y/h-.40)/.60))
        draw.line((0, y, w, y), fill=(7, 14, 18, alpha))
    margin, max_width = int(w*.08), int(w*(.78 if card else .66))
    font_size = h * (.085 if card else .061)
    while True:
        font = _font(font_size, serif=True)
        lines = _wrap(draw, text, font, max_width)
        if len(lines) <= (4 if card else 2) or font_size <= h*.025:
            break
        font_size *= .9
    line_h = int(font_size*1.3)
    small = _font(h*.022)
    details = _wrap(draw, detail, small, max_width)
    eyebrows = _wrap(draw, eyebrow, small, max_width)
    small_h = int(h*.035)
    block_h = len(lines)*line_h + (len(details)+len(eyebrows))*small_h + int(h*.07)
    y = int((h-block_h)/2) if card else int(h*.85-block_h)

    def line_at(value, selected_font, color):
        length = draw.textlength(value, font=selected_font)
        x = (w-length)/2 if card else w-margin-length if right else margin
        draw.text((int(x), y), value, font=selected_font, fill=color, stroke_width=0)

    for line in eyebrows:
        line_at(line, small, '#ddc29a')
        y += small_h
    y += int(h*.025)
    for line in lines:
        line_at(line, font, '#fff9ef')
        y += line_h
    y += int(h*.025)
    for line in details:
        line_at(line, small, '#ece8df')
        y += small_h
    return canvas


def backdrop(src, size, contain=False):
    if src:
        with Image.open(src) as opened:
            photo = ImageOps.exif_transpose(opened).convert('RGB')
            if contain:
                background = ImageOps.fit(photo, size).filter(ImageFilter.GaussianBlur(size[1]*.025))
                foreground = ImageOps.contain(photo, (int(size[0]*.88), int(size[1]*.90)))
                background.paste(foreground, ((size[0]-foreground.width)//2, (size[1]-foreground.height)//2))
                return background
            return ImageOps.fit(photo, size)
    return Image.new('RGB', size, '#10232a')


def poster(item, size=(1920, 1080), src=None):
    base = backdrop(src, size, item.get('fit') == 'contain').convert('RGBA')
    base.alpha_composite(overlay(item, size))
    return base.convert('RGB')


def render_segment(ffmpeg, item, src, out_path, *, size=(1920, 1080), fps=25, timeout=120):
    w, h = size
    duration = float(item.get('duration', 5.2))
    duration = min(12, max(2, duration))
    overlay_path = Path(out_path).with_suffix('.overlay.png')
    overlay(item, size).save(overlay_path)
    is_video = item.get('type') == 'video'
    if is_video:
        cmd = [ffmpeg, '-y', '-hide_banner', '-loglevel', 'error', '-i', str(src)]
        base_filter = f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x10232a,setsar=1,fps={fps},tpad=stop_mode=clone:stop_duration={duration}'
    else:
        background_path = Path(out_path).with_suffix('.background.jpg')
        backdrop(src, (w*2, h*2), item.get('fit') == 'contain').save(background_path, quality=94)
        cmd = [ffmpeg, '-y', '-hide_banner', '-loglevel', 'error', '-i', str(background_path)]
        frames = int(round(duration*fps))
        variant = int(item.get('motion', 0)) % 4
        zoom = f'1.06-0.04*on/{frames}' if variant % 2 else f'1+0.05*on/{frames}'
        x = 'iw/2-iw/zoom/2' if variant < 2 else f'(iw-iw/zoom)*on/{frames}'
        base_filter = f"zoompan=z='{zoom}':x='{x}':y='ih/2-ih/zoom/2':d={frames}:s={w}x{h}:fps={fps},setsar=1"
    cmd += ['-loop', '1', '-i', str(overlay_path)]
    # Short fades through charcoal provide a consistent transition between every
    # segment, including clips shorter than the usual photo duration.
    filters = f"[0:v]{base_filter}[base];[1:v]format=rgba,fade=t=in:st=0.2:d=0.8:alpha=1[type];[base][type]overlay=x=0:y='16*max(0,1-t/1.05)':shortest=1,fade=t=in:st=0:d=0.35:color=0x10232a,fade=t=out:st={duration-.35}:d=0.35:color=0x10232a,format=yuv420p[out]"
    cmd += ['-filter_complex', filters, '-map', '[out]', '-t', str(duration), '-r', str(fps),
            '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-movflags', '+faststart', str(out_path)]
    subprocess.run(cmd, check=True, timeout=timeout, capture_output=True)
    return Path(out_path).exists() and Path(out_path).stat().st_size > 0
