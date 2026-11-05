#!/usr/bin/env python3
"""Execute a reviewed one-time music manifest, two in-flight calls, no retries."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from queue import Queue, Empty
import subprocess
import sys
from threading import Event, Lock

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    queue = Queue()
    seen = set()
    for item in manifest['tracks']:
        output = (ROOT / item['output']).resolve()
        if output.parent != ROOT / 'assets/music' or output.suffix != '.mp3' or output in seen:
            parser.error('Manifest requires distinct MP3 outputs directly under assets/music')
        if not 3 <= item['seconds'] <= 600:
            parser.error('Duration outside supported range')
        seen.add(output)
        queue.put(item)
    if args.dry_run:
        print(f"Validated {queue.qsize()} tracks; {sum(t['seconds'] for t in manifest['tracks'])} requested seconds; no requests sent")
        return
    stopped = Event()
    lock = Lock()
    results = []
    report = args.manifest.with_suffix('.results.json')

    def worker():
        while not stopped.is_set():
            try:
                item = queue.get_nowait()
            except Empty:
                return
            # Check again immediately before starting the next paid request.
            if stopped.is_set():
                return
            cmd = [sys.executable, str(ROOT / 'scripts/audio.py'), 'music', '--prompt', item['prompt'],
                   '--seconds', str(item['seconds']), '--model', item['model'], '--output', item['output']]
            result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            if result.returncode:
                stopped.set()
            with lock:
                record = {'id': item['id'], 'exit_code': result.returncode,
                          'stdout': result.stdout.strip(), 'stderr': result.stderr.strip()}
                results.append(record)
                report.write_text(json.dumps({'results': results, 'stopped_on_error': stopped.is_set()}, ensure_ascii=False, indent=2)+'\n')
                print(f"{len(results)}/{len(manifest['tracks'])} {item['id']}: " + ('complete' if result.returncode == 0 else record['stderr']), flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: worker(), range(2)))
    if stopped.is_set():
        print('Stopped. No automatic retries; inspect sidecars and result report.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
