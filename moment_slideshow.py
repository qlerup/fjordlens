"""Validate and save the editable slideshow without changing moment membership."""
import json
import math
from contextlib import closing
from flask import request, jsonify
import moment_cinema
import moment_music
import moments_service as service


def retain_edited_script(script_json, member_ids):
    """Keep manual edits when moment dates/membership change, dropping removed media."""
    try:
        script = json.loads(script_json or '[]')
        if not script or not script[0].get('script_edited'):
            return None
        music = script[0].get('music')
        ids, result = set(member_ids), []
        for slide in script:
            if slide['type'] == 'text':
                if slide.get('background_photo_id') not in ids:
                    slide.pop('background_photo_id', None)
            elif slide['type'] == 'pair':
                remaining = [pid for pid in (slide['photo_id'], slide['second_photo_id']) if pid in ids]
                if not remaining:
                    continue
                if len(remaining) == 1:
                    slide.update(type='photo', photo_id=remaining[0])
                    slide.pop('second_photo_id')
            elif slide.get('photo_id') not in ids:
                continue
            result.append(slide)
        if result:
            result[0]['script_edited'] = True
            if music is not None:
                result[0]['music'] = music
            return json.dumps(result, ensure_ascii=False)
    except (ValueError, KeyError, TypeError, AttributeError):
        pass
    return None


def validate(script, photos, video_exts):
    if not isinstance(script, list) or not 1 <= len(script) <= 300:
        raise service.EditError('Diasshowet skal indeholde mellem 1 og 300 slides.')
    result = []
    for source in script:
        if not isinstance(source, dict) or source.get('type') not in ('text', 'photo', 'video', 'pair'):
            raise service.EditError('Ugyldig slide.')
        kind = source['type']
        item = dict(type=kind, design_version=moment_cinema.VERSION)
        keys = ('background_photo_id',) if kind == 'text' else ('photo_id', 'second_photo_id') if kind == 'pair' else ('photo_id',)
        for key in keys:
            pid = source.get(key)
            if key == 'background_photo_id' and pid is None:
                continue
            if type(pid) is not int or pid not in photos:
                raise service.EditError('Alle billeder og videoer skal høre til momentet.')
            is_video = str(photos[pid].get('ext') or '').lower() in video_exts
            if is_video != (kind == 'video'):
                raise service.EditError('Vælg et billede til billedslides og en video til videoklip.')
            item[key] = pid
        if kind == 'pair' and item['photo_id'] == item['second_photo_id']:
            raise service.EditError('Vælg to forskellige billeder.')
        for key, limit in (('text', 500), ('label', 240), ('eyebrow', 100), ('detail', 180), ('weather', 180)):
            value = source.get(key, '')
            if not isinstance(value, str) or len(value) > limit:
                raise service.EditError(f'Teksten er for lang (maks. {limit} tegn).')
            item[key] = value.strip()
        if kind == 'video':
            item['duration'] = None
        else:
            value = source.get('duration', 5.2)
            if type(value) not in (int, float) or not math.isfinite(value) or not 1 <= value <= 60:
                raise service.EditError('Visningstiden skal være mellem 1 og 60 sekunder.')
            item['duration'] = round(value, 2)
        for key, allowed, default in (('layout', ('left', 'right'), 'left'), ('fit', ('cover', 'contain'), 'cover'),
                                       ('style', ('intro', 'chapter', 'quote', 'outro'), 'chapter')):
            value = source.get(key, default)
            if value not in allowed:
                raise service.EditError('Ugyldigt layout.')
            item[key] = value
        motion = source.get('motion', 0)
        position = source.get('text_position')
        elements = source.get('text_elements')
        if elements is not None:
            if not isinstance(elements, dict) or set(elements) - {'heading','eyebrow','detail','weather'}:
                raise service.EditError('Ugyldige tekstfelter.')
            item['text_elements'] = {}
            for key, box in elements.items():
                if (not isinstance(box, dict) or set(box) != {'x','y','width','height','font_size'} or
                    any(type(v) not in (int,float) or not math.isfinite(v) for v in box.values()) or
                    not 0 <= box['x'] <= 1 or not 0 <= box['y'] <= 1 or
                    not .005 <= box['width'] <= 1 or not .005 <= box['height'] <= 1 or
                    not .003 <= box['font_size'] <= .3 or
                    box['x'] + box['width'] > 1.00001 or box['y'] + box['height'] > 1.00001):
                    raise service.EditError('Teksten skal have en gyldig størrelse og være inden for billedet.')
                item['text_elements'][key] = {k:round(v,6) for k,v in box.items()}
        if position is not None:
            if (not isinstance(position, dict) or set(position) != {'x', 'y'} or
                    any(type(position[k]) not in (int, float) or not math.isfinite(position[k])
                        or not 0 <= position[k] <= 1 for k in ('x', 'y'))):
                raise service.EditError('Tekstens placering skal være inden for billedet.')
            item['text_position'] = {k: round(position[k], 5) for k in ('x', 'y')}
        item['motion'] = motion if type(motion) is int and 0 <= motion <= 3 else 0
        result.append(item)
    result[0]['script_edited'] = True
    if 'music' in script[0]:
        try:
            result[0]['music'] = moment_music.validate(script[0]['music'])
        except ValueError as error:
            raise service.EditError(str(error))
    return result


def register(app, g, managed):
    @app.put('/api/moments/<int:moment_id>/slideshow')
    @managed
    def save_moment_slideshow(moment_id):
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or 'revision' not in body:
            raise service.EditError('Åbn diasshowet igen før redigering.')
        with closing(g['get_conn']()) as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = service._get(conn, moment_id, body['revision'])
            photos = {p['id']: p for p in service._photos(conn, sorted(service.members(row)))}
            script = validate(body.get('script'), photos, g['VIDEO_EXTS'])
            if 'music' not in script[0]:
                script[0]['music'] = moment_music.choice(json.loads(row['script_json'] or '[]'), row['title'])
            conn.execute("""UPDATE moments SET script_json=?,user_edited=1,revision=revision+1,
                video_status='none',video_rel_path=NULL,video_error=NULL,updated_at=? WHERE id=?""",
                (json.dumps(script, ensure_ascii=False), g['now_iso'](), moment_id))
            conn.commit()
        return jsonify(ok=True, revision=row['revision']+1, script=script)
