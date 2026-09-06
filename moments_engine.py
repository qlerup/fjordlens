"""Metadata-only moment discovery. No image uploads or external AI calls.

Dates are photographic evidence, not claims about departure/arrival. Unknown
locations only join a journey when bracketed by compatible evidence from the
same uploader and camera. All membership is retained; curation is separate.
"""
from collections import Counter, defaultdict, deque
from datetime import datetime, timedelta
from math import radians, sin, cos, asin, sqrt
from statistics import median
from functools import lru_cache
import re

import pycountry
from place_names import place_name, city_name, country_names, country_code
from moment_calendar import occasion_for_dates, title_for


COUNTRIES = {
    "danmark": "DK", "denmark": "DK", "tyskland": "DE", "germany": "DE",
    "deutschland": "DE", "sverige": "SE", "sweden": "SE", "norge": "NO",
    "norway": "NO", "italien": "IT", "italy": "IT", "spanien": "ES",
    "spain": "ES", "frankrig": "FR", "france": "FR", "østrig": "AT",
    "austria": "AT", "schweiz": "CH", "switzerland": "CH", "holland": "NL",
    "nederlandene": "NL", "netherlands": "NL", "storbritannien": "GB",
    "grækenland": "GR", "greece": "GR", "portugal": "PT", "polen": "PL",
    "poland": "PL", "usa": "US", "united states": "US",
}
DA_COUNTRIES = country_names()


def photo_date(row):
    for field in ("captured_at", "modified_fs", "created_fs"):
        try:
            # Preserve local photographic calendar dates, including mixed EXIF offsets.
            return datetime.fromisoformat(str(row.get(field) or "")).replace(tzinfo=None)
        except (ValueError, TypeError):
            pass
    return None


@lru_cache(maxsize=8192)
def country_for_name(name):
    country = None
    for part in reversed(re.split(r"[,;/|]", name)):
        part = part.strip()
        country = country_code(part) or COUNTRIES.get(part.casefold())
        if not country and part:
            try:
                country = pycountry.countries.lookup(part).alpha_2
            except LookupError:
                pass
        if country:
            break
    return country


def location(row):
    name = place_name(str(row.get("gps_name") or "").strip())
    loc = {"name": name, "country": country_for_name(name),
           "lat": row.get("gps_lat"), "lon": row.get("gps_lon")}
    if distance(loc, loc) is None:
        loc["lat"] = loc["lon"] = None
    else:
        loc["lat"], loc["lon"] = float(loc["lat"]), float(loc["lon"])
    return loc


def distance(a, b):
    try:
        lat1, lon1, lat2, lon2 = [float(v) for v in (a["lat"], a["lon"], b["lat"], b["lon"])]
        if not (-90 <= lat1 <= 90 and -90 <= lat2 <= 90 and -180 <= lon1 <= 180 and -180 <= lon2 <= 180):
            return None
        dlat, dlon = radians(lat2-lat1), radians(lon2-lon1)
        return 6371 * 2 * asin(sqrt(min(1, sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2)))
    except (TypeError, ValueError, KeyError):
        return None


def nearby(a, b, radius=40):
    km = distance(a, b)
    if km is not None:
        return km <= radius
    if a["country"] and b["country"] and a["country"] != b["country"]:
        return False
    return bool(a["name"] and a["name"].split(',')[0].strip().casefold() == b["name"].split(',')[0].strip().casefold())


def infer_home(rows, manual=None):
    if manual:
        home = location({"gps_name": manual.get("name"), "gps_lat": manual.get("lat"), "gps_lon": manual.get("lon")})
        if not home['country']:
            home['country'] = next((r['_loc']['country'] for r in rows if r['_loc']['country'] and nearby(home, r['_loc'])), None)
        if not home['country'] and home['lat'] is not None and home['lon'] is not None:
            try:
                import reverse_geocoder
                home['country'] = reverse_geocoder.search((home['lat'], home['lon']), mode=1, verbose=False)[0].get('cc')
            except Exception:
                pass
        return home
    places = {}
    for r in rows:
        loc = r["_loc"]
        if not loc["name"] and loc["lat"] is None:
            continue
        key = loc["name"].casefold() or str((round(loc["lat"], 1), round(loc["lon"], 1)))
        entry = places.setdefault(key, {"loc": loc, "days": set()})
        entry["days"].add(r["_dt"].date())
    candidates = []
    for entry in places.values():
        days = entry["days"]
        # A dense holiday cannot establish home. Require recurring visits over time.
        if len(days) >= 5 and (max(days)-min(days)).days >= 45:
            candidates.append(entry)
    return max(candidates, key=lambda p: len(p["days"]))["loc"] if candidates else None


def _source(row):
    return (str(row.get("uploaded_by") or ""), str(row.get("camera_make") or ""), str(row.get("camera_model") or ""))


def curate(rows, limit):
    """Spread highlights across elapsed time, suppress bursts, then play chronologically."""
    import random
    rows = sorted((dict(r) for r in rows), key=lambda r: (photo_date(r) or datetime.min, r['id']))
    if limit <= 0 or not rows:
        return []
    rng = random.Random(','.join(str(r['id']) for r in rows))
    dates = [photo_date(r) for r in rows]
    origin = next((d for d in dates if d), datetime.min)
    times = [(d-origin).total_seconds() if d else float(i) for i,d in enumerate(dates)]
    hashes = []
    for row in rows:
        try:
            raw = row.get('phash_dct') or row.get('phash')
            hashes.append(int(raw, 16) if raw else None)
        except (ValueError, TypeError):
            hashes.append(None)
    chosen = []
    def distinct(i):
        for j in chosen:
            if hashes[i] is not None and hashes[j] is not None:
                difference = (hashes[i] ^ hashes[j]).bit_count()
                if difference <= 6 or (difference <= 10 and dates[i] and dates[j] and abs(times[i]-times[j]) < 300):
                    return False
            # Rapid sequences should not dominate even when visual hashes are missing.
            if dates[i] and dates[j] and abs(times[i]-times[j]) < 20:
                return False
        return True
    chosen.append(0)
    if limit > 1 and len(rows) > 1 and distinct(len(rows)-1):
        chosen.append(len(rows)-1)
    remaining = set(range(len(rows))) - set(chosen)
    while remaining and len(chosen) < limit:
        remaining = {i for i in remaining if distinct(i)}
        if not remaining:
            break
        distances = {i: min(abs(times[i]-times[j]) for j in chosen) for i in remaining}
        widest = max(distances.values())
        # Random choice among similarly well-spaced candidates; favorites get extra weight.
        pool = sorted(i for i in remaining if distances[i] >= widest * .8)
        picked = rng.choices(pool, weights=[3 if rows[i].get('favorite') else 1 for i in pool], k=1)[0]
        chosen.append(picked)
        remaining.remove(picked)
    return [rows[i] for i in sorted(chosen)]


def combine_day_segments(segments):
    """Reconcile camera/uploader lanes after segmentation, before minimum counts.

    Unknown-place photos can join exactly one overlapping destination that day.
    They never inherit GPS, and two geographically conflicting events stay apart.
    """
    days, result = defaultdict(list), []
    for segment, home in segments:
        if segment[0]['_dt'].date() == segment[-1]['_dt'].date():
            days[segment[0]['_dt'].date()].append((segment, home))
        else:
            result.append((segment, home))
    for groups in days.values():
        known, unknown = [], []
        for segment, home in groups:
            locs = [r['_loc'] for r in segment if r['_loc']['name'] or r['_loc']['lat'] is not None]
            (known if locs else unknown).append((segment, home))

        def close_in_time(a, b, hours):
            return max(a[0]['_dt'], b[0]['_dt']) - min(a[-1]['_dt'], b[-1]['_dt']) <= timedelta(hours=hours)

        merged = []
        for segment, home in sorted(known, key=lambda pair: pair[0][0]['_dt']):
            locs = [r['_loc'] for r in segment if r['_loc']['name'] or r['_loc']['lat'] is not None]
            target = None
            for existing, _ in merged:
                other = [r['_loc'] for r in existing if r['_loc']['name'] or r['_loc']['lat'] is not None]
                if close_in_time(segment, existing, 6) and all(any(nearby(a, b, 8) for b in other) for a in locs):
                    target = existing
                    break
            if target is None:
                merged.append((list(segment), home))
            else:
                target.extend(segment)
                target.sort(key=lambda r: (r['_dt'], r['id']))
        for segment, home in unknown:
            matches = [existing for existing, _ in merged if close_in_time(segment, existing, 1)]
            if len(matches) == 1:
                for r in segment:
                    r['_day_inferred'] = True
                matches[0].extend(segment)
                matches[0].sort(key=lambda r: (r['_dt'], r['id']))
            else:
                # Keep ambiguous/no-destination events separate, but reconcile
                # overlapping unknown-camera groups from the same day.
                target = next((existing for existing, _ in result if existing[0]['_dt'].date() == segment[0]['_dt'].date()
                               and all(not r['_loc']['name'] and r['_loc']['lat'] is None for r in existing)
                               and close_in_time(segment, existing, 1)), None)
                if target is None:
                    result.append((list(segment), home))
                else:
                    target.extend(segment)
                    target.sort(key=lambda r: (r['_dt'], r['id']))
        result.extend(merged)
    return sorted(result, key=lambda pair: pair[0][0]['_dt'])


def discover(raw_rows, *, min_photos=10, min_hours=4, gap_hours=30, manual_home=None):
    from moment_folders import folder_key
    stats = dict(scanned=len(raw_rows), dated=0, segments=0, created=0, updated=0, retired=0,
                 rejected_too_few=0, rejected_too_short=0, rejected_home_only=0,
                 rejected_already_covered=0)
    rows = []
    for raw in raw_rows:
        r = dict(raw)
        dt = photo_date(r)
        if dt:
            r.update(_dt=dt, _loc=location(r))
            rows.append(r)
    # GPS-only photos can still establish city/country, using the bundled offline
    # database. Batch distinct coordinates instead of making per-photo requests.
    unresolved = {}
    for r in rows:
        loc = r["_loc"]
        if not loc["country"] and distance(loc, loc) is not None:
            key = (round(float(loc["lat"]), 3), round(float(loc["lon"]), 3))
            unresolved.setdefault(key, []).append(loc)
    if unresolved:
        import reverse_geocoder
        results = reverse_geocoder.search(list(unresolved), mode=1, verbose=False)
        for locs, found in zip(unresolved.values(), results):
            for loc in locs:
                loc["country"] = found.get("cc")
                if not loc["name"]:
                    loc["name"] = ", ".join(v for v in (city_name(found.get("name"), found.get("cc")), DA_COUNTRIES.get(found.get("cc"), found.get("cc"))) if v)
    rows.sort(key=lambda r: (r["_dt"], r["id"]))
    stats["dated"] = len(rows)
    home = infer_home(rows, manual_home)
    # Independently segment uploaders to avoid another person's home photos ending a trip.
    streams = defaultdict(list)
    for r in rows:
        streams[str(r.get("uploaded_by") or "")].append(r)
    segments = []
    source_baselines = {}
    for stream in streams.values():
        stream_home = home if manual_home else (infer_home(stream) or home)
        home_here = stream_home
        days_by_place = defaultdict(set)
        daily_counts = Counter(r["_dt"].date() for r in stream)
        source_baselines[str(stream[0].get("uploaded_by") or "")] = median(daily_counts.values())
        for r in stream:
            if r["_loc"]["name"]:
                days_by_place[r["_loc"]["name"]].add(r["_dt"].date())
        routine = {name for name, days in days_by_place.items() if len(days) >= 5 and (max(days)-min(days)).days >= 45}
        for r in stream:
            loc = r["_loc"]
            known = bool(loc["name"] or (loc["lat"] is not None and loc["lon"] is not None))
            r["_away"] = known and (not home_here or not nearby(loc, home_here))
            r["_home"] = known and bool(home_here and nearby(loc, home_here))
            r["_routine"] = loc["name"] in routine
        # Bracket unknown GPS with known same-camera evidence within six hours.
        by_source = defaultdict(list)
        for r in stream:
            by_source[_source(r)].append(r)
        for source, sequence in by_source.items():
            if not any(source):
                continue
            known_indices = [i for i, r in enumerate(sequence) if r["_away"] or r["_home"]]
            for left, right in zip(known_indices, known_indices[1:]):
                a, b = sequence[left], sequence[right]
                compatible = nearby(a["_loc"], b["_loc"], 100) or bool(a["_loc"]["country"] and a["_loc"]["country"] == b["_loc"]["country"])
                if a["_away"] and b["_away"] and compatible and b["_dt"]-a["_dt"] <= timedelta(hours=6):
                    for r in sequence[left+1:right]:
                        r["_away"] = True
                        r["_inferred"] = True
                        r["_context_loc"] = a["_loc"]
        # Unknown photos form separate time-based candidates; they cannot break a known trip.
        for lane in ([r for r in stream if r["_away"] or r["_home"]],
                     [r for r in stream if not r["_away"] and not r["_home"]]):
            current = []
            for r in lane:
                split = False
                if current:
                    prev = current[-1]
                    hours = (r["_dt"]-prev["_dt"]).total_seconds()/3600
                    both_away = r["_away"] and prev["_away"]
                    loc, prev_loc = r.get("_context_loc", r["_loc"]), prev.get("_context_loc", prev["_loc"])
                    same_country = bool(loc["country"] and loc["country"] == prev_loc["country"])
                    km = distance(loc, prev_loc)
                    continuity = bool(home_here or same_country or nearby(loc, prev_loc, 100) or (km is not None and km <= 1200))
                    home_cc = (home_here or {}).get('country')
                    foreign = bool(home_cc and loc['country'] and prev_loc['country']
                                   and loc['country'] != home_cc and prev_loc['country'] != home_cc)
                    unknown_home_continuity = not home_cc and (km is None or km <= 100)
                    allowed_gap = 96 if both_away and continuity and (foreign or unknown_home_continuity) else min(gap_hours, 30)
                    # Without home/country/coordinate evidence, a different place is a separate event.
                    place_break = both_away and not continuity and loc["name"] != prev_loc["name"]
                    split = hours > allowed_gap or r["_home"] != prev["_home"] or place_break
                    # Unlocated photos from a different folder on a different day
                    # are not evidence of a continuous trip. Otherwise one stray
                    # photo prevents the next day's event from joining its GPS lane.
                    if not (r['_away'] or r['_home'] or prev['_away'] or prev['_home']):
                        folder, previous_folder = folder_key(r.get('rel_path')), folder_key(prev.get('rel_path'))
                        if folder and previous_folder and folder != previous_folder and r['_dt'].date() != prev['_dt'].date():
                            split = True
                    if not foreign and km is not None and km > 80 and (hours > 6 or r['_dt'].date() != prev['_dt'].date()):
                        split = True
                    if r["_home"] and r["_dt"].date() != prev["_dt"].date():
                        split = True
                if split:
                    segments.append((current, home_here))
                    current = []
                current.append(r)
            if current:
                segments.append((current, home_here))
    segments = combine_day_segments(segments)
    stats["segments"] = len(segments)
    candidates = []
    for segment, segment_home in segments:
        if len(segment) < min_photos:
            stats["rejected_too_few"] += 1
            continue
        start, end = segment[0]["_dt"], segment[-1]["_dt"]
        single_day = start.date() == end.date()
        # Short visits are meaningful; day events need at least half an hour of evidence.
        if (end-start).total_seconds()/3600 < (min(min_hours, .5) if single_day else min_hours):
            stats["rejected_too_short"] += 1
            continue
        at_home = all(r["_home"] for r in segment)
        occasion = occasion_for_dates([r['_dt'].date() for r in segment if r.get('captured_at')],
                                      [r['_loc']['country'] for r in segment if r['_loc']['country']])
        if sum(bool(r.get('captured_at')) for r in segment) < len(segment)*.6:
            occasion = None
        familiar = single_day and all(r["_routine"] for r in segment)
        baseline = source_baselines[str(segment[0].get("uploaded_by") or "")]
        if not (occasion and at_home) and (at_home or familiar) and len(segment) < max(min_photos, baseline * 2):
            stats["rejected_home_only"] += 1
            continue
        places = list(dict.fromkeys(r["_loc"]["name"] for r in segment if r["_loc"]["name"]))
        countries = list(dict.fromkeys(r["_loc"]["country"] for r in segment if r["_loc"]["country"]))
        country_names = [DA_COUNTRIES.get(c) or pycountry.countries.get(alpha_2=c).name for c in countries]
        primary = " og ".join(country_names) if not single_day and countries else (places[0] if places else None)
        kind = "event" if single_day else "trip"
        title = (f"En dag i {primary}" if single_day else f"Tur til {primary}") if primary else ("Dagens oplevelser" if single_day else "Oplevelser")
        title_source = 'trip' if not single_day and primary else 'place' if primary else 'generic'
        abroad = bool(segment_home and segment_home.get('country') and countries
                      and all(c != segment_home['country'] for c in countries))
        if abroad:
            title_source = 'journey'
            title = f"Rejse til {' og '.join(country_names)}"
        # Existing descriptions can suggest an activity, only with repeated explicit evidence.
        themes = {"zoo": ("zoo", "zoologisk"), "stranden": ("strand", "beach"), "skoven": ("skov", "forest")}
        if single_day and not abroad:
            for label, words in themes.items():
                matches = sum(any(re.search(r"\b" + re.escape(w) + r"\b", str(r.get("ai_desc_caption") or "").casefold() + " " + str(r.get("ai_desc_tags") or "").casefold()) for w in words) for r in segment)
                if matches >= max(3, len(segment)*.4):
                    title_source = 'activity'
                    title = f"En dag i {label}" if label == "zoo" else f"En dag ved {label}" if label == "stranden" else "En dag i skoven"
                    break
        title += f" · {start.strftime('%d.%m.%Y')}"
        if occasion:
            title = title_for(occasion)
            title_source = 'occasion'
        located = sum(bool(r["_loc"]["name"] or r["_loc"]["lat"] is not None) for r in segment)
        reasons = [f"{len(segment)} billeder fra {start.date().isoformat()} til {end.date().isoformat()}."]
        if occasion:
            reasons.append(f"Billeddatoerne falder på {occasion['name']}. Forslaget bygger på kalenderen; billederne behøver ikke vise en fejring.")
        if primary:
            reasons.append(f"Sammenhængende billeder fra {primary}.")
        if segment_home and not at_home and located:
            reasons.append("Billeder uden for dit normale område.")
        if at_home:
            reasons.append("Mærkedag i dit hjemområde." if occasion else "Flere billeder end normalt i dit hjemområde.")
        if not located:
            reasons.append("Grupperet efter tid; stedet er ukendt.")
        uncertain_dates = sum(not r.get("captured_at") for r in segment)
        if uncertain_dates:
            reasons.append(f"{uncertain_dates} billeder bruger fildato, som kan være importdato.")
        inferred = sum(bool(r.get("_inferred")) for r in segment)
        if inferred:
            reasons.append(f"{inferred} billeder uden GPS er knyttet til turen via samme kilde og nærliggende billeder.")
        day_inferred = sum(bool(r.get('_day_inferred')) for r in segment)
        if day_inferred:
            reasons.append(f"{day_inferred} billeder uden sted er samlet med dagens eneste tidsmæssigt sammenfaldende sted. Kontrollér, at de hører til samme oplevelse.")
        chapters = []
        for r in segment:
            place = r["_loc"]["name"]
            if not place:
                continue
            date = r["_dt"].date().isoformat()
            if chapters and chapters[-1]["place"] == place:
                chapters[-1]["end_date"] = date
                chapters[-1]["photo_count"] += 1
            else:
                chapters.append(dict(place=place, start_date=date, end_date=date, photo_count=1))
        candidates.append(dict(kind=kind, title=title, start_date=start.date().isoformat(), end_date=end.date().isoformat(),
                               primary_place=primary, photo_ids=[r["id"] for r in segment],
                               cover_photo_id=next((r["id"] for r in segment if r.get("favorite")), segment[len(segment)//2]["id"]),
                               evidence=dict(version=2, title_source=title_source, reasons=reasons, places=places, countries=countries, chapters=chapters,
                                             confidence="high" if located/len(segment) >= .7 and not uncertain_dates and not day_inferred else "medium" if located else "low",
                                             date_basis="Billeddatoer; afrejse og hjemkomst kan ligge uden for intervallet.",
                                             home=segment_home, inferred_photo_count=inferred, occasion=occasion)))
    return candidates, stats, home
