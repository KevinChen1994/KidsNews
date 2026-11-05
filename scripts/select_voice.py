#!/usr/bin/env python3
"""Select one approved voice per Shanghai calendar day, persist it for retries."""
import argparse
from datetime import date, datetime
import json
import os
from pathlib import Path
import secrets
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def select_voice(episode_date=None, root=ROOT):
    day = episode_date or datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    if date.fromisoformat(day).isoformat() != day:
        raise ValueError('Episode date must be YYYY-MM-DD')
    config = json.loads((root / 'config/voice-options.json').read_text())
    policy = config['daily_selection']
    voices = [v for v in config['voices'] if v['speaker'] in policy['speakers']]
    if len(voices) != len(policy['speakers']) or not voices:
        raise ValueError('Daily voice pool does not match configured voices')
    folder = root / 'state/voices'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f'{day}.json'
    lock = folder / f'{day}.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise RuntimeError('Daily voice selection is locked; check concurrent process and retry') from None
    os.close(fd)
    try:
        if target.exists():
            record = json.loads(target.read_text())
            if record['speaker'] not in policy['speakers'] or record['episode_date'] != day:
                raise ValueError('Saved daily voice conflicts with current policy; inspect before continuing')
            return record
        voice = secrets.choice(voices)
        record = {'episode_date': day, 'timezone': 'Asia/Shanghai', 'name': voice['name'],
                  'speaker': voice['speaker'], 'selection': 'uniform-random-persisted',
                  'created_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()}
        tmp = target.with_suffix('.json.part')
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n')
        tmp.replace(target)
        return record
    finally:
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--episode-date', help='YYYY-MM-DD, defaults to today in Asia/Shanghai')
    args = parser.parse_args()
    print(json.dumps(select_voice(args.episode_date), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
