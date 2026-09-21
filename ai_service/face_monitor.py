"""Read-only terminal monitor: python face_monitor.py --slots 8."""
import argparse
import json
import shutil
import sys
import time
import unicodedata
from urllib.request import urlopen


def clean(value):
    return ''.join(c if not unicodedata.category(c).startswith('C') else ' ' for c in str(value))


def render(rows, slots, width):
    jobs = {int(row['instance']): row for row in rows}
    count = max(slots, max(jobs, default=0))
    lines = [f'FjordLens | {len(jobs)} aktive | Ctrl+C lukker visningen', '']
    for instance in range(1, count + 1):
        row = jobs.get(instance)
        if row is None:
            line = f'{instance:2} | Ledig'
        else:
            stage = {'inference': 'Analyserer', 'serialize': 'Klargør resultat',
                     'done': 'Færdig', 'error': 'Fejl'}.get(row['stage'], row['stage'])
            percent = '--' if row['percent'] is None else f"{row['percent']}%"
            line = f"{instance:2} | {stage:<16} | {percent:>4} | {row['elapsed_sec']:6.1f}s | {clean(row['file'])}"
        lines.append(line)
    return '\n'.join(clean(line)[:max(1, width - 1)] + '\x1b[K' for line in lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--slots', type=int, choices=range(1, 17), default=8)
    args = parser.parse_args()
    if not sys.stdout.isatty():
        parser.error('Brug en interaktiv terminal: docker exec -it fjordlens-ai python face_monitor.py')
    # Alternate screen keeps the shell clean and restores it on Ctrl+C.
    print('\x1b[?1049h\x1b[?25l', end='', flush=True)
    try:
        while True:
            try:
                with urlopen('http://127.0.0.1:8000/faces/status', timeout=2) as response:
                    status = json.load(response)
                    rows = status['instances']
                screen = render(rows, args.slots, shutil.get_terminal_size().columns)
                if status.get('waiting'):
                    screen += '\n' + clean(status['waiting'])
            except (OSError, ValueError, KeyError) as exc:
                screen = 'Afventer AI-tjenesten: ' + clean(exc)[:100]
            print('\x1b[H' + screen + '\x1b[J', end='', flush=True)
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        print('\x1b[?25h\x1b[?1049l', end='', flush=True)


if __name__ == '__main__':
    main()
