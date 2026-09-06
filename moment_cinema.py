"""Shared cinematic timeline and typography for browser playback and MP4 export."""
import subprocess
import shutil
from pathlib import Path
import re
import json
import math
import moment_titles

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

from moments_engine import photo_date, location, DA_COUNTRIES

VERSION = 6
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
        return not script or (not script[0].get('script_edited') and script[0].get('design_version') != VERSION)
    except (ValueError, TypeError, AttributeError, IndexError):
        return True


def weather_label(row):
    try:
        weather = json.loads(row.get('metadata_json') or '{}').get('weather') or {}
        label = str(weather.get('weather_label_da') or '').strip()
        temperature = weather.get('temperature_2m')
        degrees = f'{float(temperature):.0f} °C' if temperature is not None and math.isfinite(float(temperature)) else ''
        return ' · '.join(filter(None, (label, degrees)))
    except (ValueError, TypeError, AttributeError):
        return ''


def timeline(moment, rows, *, title=None, subtitle=None, cards=(), video_exts=()):
    if not rows:
        return []
    rows = [dict(r) for r in rows]
    period = date_range(moment['start_date'], moment['end_date'])
    film_title = title or moment['title'] or 'Et øjeblik at huske'
    if not moment.get('user_edited'):
        evidence = moment.get('evidence') or json.loads(moment.get('evidence_json') or '{}')
        folder = evidence.get('folder_title') or {}
        if evidence.get('title_source') == 'folder' and film_title == folder.get('generated_title', folder.get('name')):
            film_title = folder.get('name') or film_title
        film_title = moment_titles.base_title(film_title)
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
                           photo_id=row['id'], duration=None if str(row.get('ext') or '').lower() in video_exts else 5.2,
                           motion=index % 4, layout='right' if index % 2 else 'left',
                           fit='contain' if (row.get('height') or 0) > (row.get('width') or 0) else 'cover',
                           label=city if show_label else '', eyebrow=country if show_label else '',
                           detail=' · '.join(filter(None, (label_date, clock))) if show_label else '',
                           weather=weather_label(row) if show_label else '',
                           design_version=VERSION))
        if index and index % 12 == 0 and quotes:
            script.append(dict(type='text', style='quote', text=quotes.pop(0), eyebrow='ET ØJEBLIK UNDERVEJS',
                               detail='', background_photo_id=row['id'], duration=4.2, design_version=VERSION))
        last_place, last_day = place or last_place, day or last_day
    script.append(dict(type='text', style='outro', text='Minder at vende tilbage til',
                       eyebrow=moment['primary_place'] or 'DIT MOMENT', detail=period,
                       background_photo_id=rows[-1]['id'], duration=3.8, design_version=VERSION))
    # Pair occasional adjacent portraits from the same part of an outing.
    # Keep the opening/closing photographs and chronological selection intact.
    by_id = {r['id']: r for r in rows}
    paired, index, last_pair = [], 0, -3
    while index < len(script):
        slide = script[index]
        following = script[index+1] if index+1 < len(script) else {}
        if index-last_pair >= 6 and following.get('photo_id') != rows[-1]['id'] and slide.get('type') == following.get('type') == 'photo' and slide.get('fit') == following.get('fit') == 'contain':
            a, b = by_id[slide['photo_id']], by_id[following['photo_id']]
            da, db = photo_date(a), photo_date(b)
            if da and db and da.date() == db.date() and 0 <= (db-da).total_seconds() <= 1800 and location(a)['name'] == location(b)['name']:
                slide = dict(slide, type='pair', second_photo_id=following['photo_id'], duration=6.5, fit='contain')
                index += 1
                last_pair = index
        paired.append(slide)
        index += 1
    return paired


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
    detail = ' · '.join(filter(None, (str(item.get('detail') or '')[:180], str(item.get('weather') or '')[:180])))
    side = not card and item.get('fit') == 'contain' and item.get('type') != 'pair'
    position = item.get('text_position')
    if not any((text, eyebrow, detail)):
        return canvas
    # Dark photographic scrim keeps white type readable over bright snow/sky.
    for y in range(h):
        alpha = 110 if card else 90 if side else int(145 * max(0, (y/h-.7)/.3))
        left, edge = (int(w*.74), w) if right else (0, int(w*.26))
        if position:
            draw.line((0, y, w, y), fill=(7, 14, 18, 110 if card else 85))
        else:
            draw.line((left if side else 0, y, edge if side else w, y), fill=(7, 14, 18, alpha))
    margin, max_width = int(w*(.035 if side else .06)), int(w*(.78 if card else .20 if side else .75))
    font_size = h * (.085 if card else .052 if side else .027)
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
    y = int((h-block_h)/2) if card or side else int(h*.91-block_h)
    block_width = max([draw.textlength(line, font=font) for line in lines] +
                      [draw.textlength(line, font=small) for line in details+eyebrows] + [0])
    if position:
        block_x = max(0, w-block_width) * max(0, min(1, position['x']))
        y = int(max(0, h-block_h) * max(0, min(1, position['y'])))

    def line_at(value, selected_font, color):
        length = draw.textlength(value, font=selected_font)
        x = (w-length)/2 if card else w-margin-length if right else margin
        if position:
            x = block_x + ((block_width-length)/2 if card else block_width-length if right else 0)
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


def backdrop(src, size, contain=False, second_src=None):
    if second_src:
        background = Image.new('RGB', size, '#10232a')
        gap, margin = int(size[0]*.025), int(size[0]*.05)
        cell = ((size[0]-2*margin-gap)//2, int(size[1]*.82))
        for index, path in enumerate((src, second_src)):
            with Image.open(path) as opened:
                photo = ImageOps.contain(ImageOps.exif_transpose(opened).convert('RGB'), cell)
                x = margin + index*(cell[0]+gap) + (cell[0]-photo.width)//2
                background.paste(photo, (x, int(size[1]*.04)+(cell[1]-photo.height)//2))
        return background
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


def poster(item, size=(1920, 1080), src=None, second_src=None):
    base = backdrop(src, size, item.get('fit') == 'contain', second_src=second_src).convert('RGBA')
    base.alpha_composite(overlay(item, size))
    return base.convert('RGB')


def render_segment(ffmpeg, item, src, out_path, *, size=(1920, 1080), fps=25, timeout=120, second_src=None):
    w, h = size
    duration = float(item.get('duration') or 5.2)
    duration = min(60, max(1, duration))
    overlay_path = Path(out_path).with_suffix('.overlay.png')
    overlay(item, size).save(overlay_path)
    is_video = item.get('type') == 'video'
    if is_video:
        probe = Path(ffmpeg).with_name('ffprobe.exe' if str(ffmpeg).endswith('.exe') else 'ffprobe')
        probe = str(probe) if probe.exists() else shutil.which('ffprobe')
        if probe:
            result = subprocess.run([probe, '-v', 'error', '-show_entries', 'format=duration',
                                     '-of', 'default=noprint_wrappers=1:nokey=1', str(src)],
                                    check=True, capture_output=True, text=True, timeout=30)
            duration = float(result.stdout.strip())
        else:
            result = subprocess.run([ffmpeg, '-hide_banner', '-i', str(src)], capture_output=True, text=True, timeout=30)
            match = re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)', result.stderr)
            if not match:
                raise ValueError('Could not read video duration')
            duration = sum(float(v)*scale for v,scale in zip(match.groups(), (3600,60,1)))
        timeout = max(timeout, duration * 10 + 60)
        cmd = [ffmpeg, '-y', '-hide_banner', '-loglevel', 'error', '-i', str(src)]
        base_filter = f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x10232a,setsar=1,fps={fps},tpad=stop_mode=clone:stop_duration={1/fps}'
    else:
        background_path = Path(out_path).with_suffix('.background.jpg')
        backdrop(src, (w*2, h*2), item.get('fit') == 'contain', second_src=second_src).save(background_path, quality=94)
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
    cmd += ['-filter_complex', filters, '-map', '[out]']
    # For clips this is the probed source duration, never the still-image dwell.
    cmd += ['-t', str(duration)]
    cmd += ['-r', str(fps),
            '-an', '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', '-movflags', '+faststart', str(out_path)]
    subprocess.run(cmd, check=True, timeout=timeout, capture_output=True)
    return Path(out_path).exists() and Path(out_path).stat().st_size > 0
