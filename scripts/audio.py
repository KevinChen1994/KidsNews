#!/usr/bin/env python3
"""Project-local audio generation; Python standard library, no key in CLI/logs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]


def load_env():
    # Deliberately do not execute or interpolate .env as shell code.
    for line in (ROOT / '.env').read_text().splitlines() if (ROOT / '.env').exists() else []:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.removeprefix('export ').partition('=')
        if sep:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            else:
                value = value.split(' #', 1)[0].rstrip()
            os.environ.setdefault(key.strip(), value)


def env(*keys):
    return next((os.environ[k] for k in keys if os.environ.get(k)), '')


def save(path, data):
    tmp = path.with_suffix(path.suffix + '.part')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)


def request(url, headers=None, body=None, timeout=60):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers=headers or {})
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        # Some services echo input in errors. Redact configured secrets before reporting.
        message = exc.read(8192).decode(errors='replace')
        for key, value in os.environ.items():
            if value and any(t in key.lower() for t in ('key', 'token', 'secret', 'app_id')):
                message = message.replace(value, '[REDACTED]')
        raise RuntimeError(f'HTTP {exc.code}: {message}') from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f'Network request failed: {exc.reason}') from None


def post_json(url, headers, body):
    with request(url, headers, body) as response:
        data = json.load(response)
    if data.get('code') != 20000000:
        raise RuntimeError(f"Volcengine code={data.get('code')}: {data.get('message', '')}")
    return data


def download(response, out):
    tmp = out.with_suffix(out.suffix + '.part')
    try:
        with tmp.open('wb') as target:
            while chunk := response.read(65536):
                target.write(chunk)
        if tmp.stat().st_size < 100:
            raise RuntimeError('Empty or invalid audio response')
        tmp.replace(out)
    finally:
        tmp.unlink(missing_ok=True)


def volc_headers():
    h = {'Content-Type': 'application/json', 'X-Api-Resource-Id': 'seed-tts-2.0',
         'X-Api-Request-Id': str(uuid.uuid4())}
    if env('VOLCENGINE_API_KEY', 'volcengine_api_key'):
        h['X-Api-Key'] = env('VOLCENGINE_API_KEY', 'volcengine_api_key')
    else:
        h['X-Api-App-Id'] = env('VOLCENGINE_APP_ID', 'volcengine_app_id')
        h['X-Api-Access-Key'] = env('VOLCENGINE_ACCESS_TOKEN', 'VOLCENGINE_ACCECC_TOKEN',
                                    'volcengine_access_token', 'volcengine_accecc_token')
        if not h['X-Api-App-Id'] or not h['X-Api-Access-Key']:
            raise RuntimeError('Missing Volcengine API key or app ID + access token')
    return h


def generate(args):
    out = Path(args.output).resolve()
    if out.suffix != '.mp3':
        raise RuntimeError('Output must have .mp3 extension')
    if args.kind == 'tts':
        text = Path(args.text_file).read_text().strip()
        if '{{' in text or '}}' in text:
            raise RuntimeError('Render script placeholders with scripts/prepare_script.py before TTS')
        if not 1 <= len(text) <= 100000:
            raise RuntimeError('TTS text must contain 1–100000 characters')
        if not args.speaker:
            from select_voice import select_voice
            if args.dry_run:
                raise RuntimeError('For a side-effect-free TTS dry-run, supply --speaker explicitly; daily selection is persisted only for real runs')
            args.speaker = select_voice(args.episode_date)['speaker']
        body = {'user': {'uid': 'kids-news'}, 'req_params': {'text': text, 'speaker': args.speaker,
                'audio_params': {'format': 'mp3', 'sample_rate': 24000,
                                 'speech_rate': args.speech_rate, 'enable_timestamp': True}}}
        headers = volc_headers()
    else:
        if not 3 <= args.seconds <= 600:
            raise RuntimeError('Music duration must be 3–600 seconds')
        if not 1 <= len(args.prompt) <= 4100:
            raise RuntimeError('Music prompt must contain 1–4100 characters')
        body = {'prompt': args.prompt, 'music_length_ms': round(args.seconds * 1000),
                'model_id': args.model, 'force_instrumental': True}
        key = env('ELEVENLABS_API_KEY')
        if not key:
            raise RuntimeError('Missing ELEVENLABS_API_KEY')
        headers = {'Content-Type': 'application/json', 'xi-api-key': key}
    fingerprint = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    if args.dry_run:
        print(json.dumps({'provider': args.kind, 'request': body, 'output': str(out)}, ensure_ascii=False, indent=2))
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    state_path = out.with_suffix('.json')
    lock = out.with_suffix('.lock')
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise RuntimeError(f'Output locked: {lock}; check the running process before removing lock') from None
    os.close(fd)
    try:
        state = json.loads(state_path.read_text()) if state_path.exists() else {}
        if state and state.get('fingerprint') != fingerprint:
            raise RuntimeError('Output belongs to a different request; choose a new output filename')
        if out.exists():
            if (state.get('status') != 'complete' or out.stat().st_size < 100
                    or state.get('sha256') != hashlib.sha256(out.read_bytes()).hexdigest()):
                raise RuntimeError('Existing output is unverified; choose another output or inspect it')
            print(f'Cached: {out}')
            return
        policy_path = ROOT / 'config/music-library.json'
        if args.kind == 'music' and policy_path.exists():
            policy = json.loads(policy_path.read_text())
            if policy.get('generation_mode') == 'reuse-only':
                raise RuntimeError('Music library is reuse-only. New generation requires explicit user authorization and a policy update.')
            if policy.get('generation_mode') == 'authorized-batch':
                manifest = json.loads((ROOT / policy['authorized_manifest']).read_text())
                permitted = any((ROOT / t['output']).resolve() == out
                                and t['prompt'] == body['prompt']
                                and round(t['seconds'] * 1000) == body['music_length_ms']
                                and t['model'] == body['model_id'] for t in manifest['tracks'])
                if not permitted:
                    raise RuntimeError('Music request is outside the explicitly authorized batch')
        if args.kind == 'music' and state:
            raise RuntimeError('Previous music request may have been charged. Inspect its state; no automatic resubmission. Use a new output only for an intentional new request.')
        if args.kind == 'tts':
            if state.get('status') == 'failed':
                raise RuntimeError('Previous TTS task failed; inspect its sidecar before creating a new request')
            if not state:
                state = {'provider': 'volcengine', 'fingerprint': fingerprint, 'request': body,
                         'task_id': str(uuid.uuid4()), 'status': 'submitting'}
                save(state_path, state)  # Persist ID before any billable submission.
                body_submit = dict(body, unique_id=state['task_id'])
                result = post_json('https://openspeech.bytedance.com/api/v3/tts/submit', headers, body_submit)
                state['task_id'] = result['data']['task_id']
                state['status'] = 'running'
                save(state_path, state)
            print(f"TTS task: {state['task_id']}", flush=True)
            deadline = time.monotonic() + args.wait_seconds
            while True:
                result = post_json('https://openspeech.bytedance.com/api/v3/tts/query', volc_headers(),
                                   {'task_id': state['task_id']})
                data = result['data']
                if data['task_status'] == 2:
                    # Signed download URLs stay out of saved metadata and logs.
                    with request(data['audio_url']) as response:
                        download(response, out)
                    state['result'] = {k: v for k, v in data.items() if k not in ('audio_url', 'url_expire_time')}
                    break
                if data['task_status'] == 3:
                    state['status'] = 'failed'
                    save(state_path, state)
                    raise RuntimeError('TTS task failed')
                if time.monotonic() >= deadline:
                    raise RuntimeError('TTS wait timed out; rerun the SAME command to resume querying without resubmitting')
                time.sleep(5)
        else:
            state = {'provider': 'elevenlabs', 'fingerprint': fingerprint, 'request': body, 'status': 'requesting'}
            save(state_path, state)
            with request('https://api.elevenlabs.io/v1/music?output_format=mp3_44100_128', headers, body, timeout=240) as response:
                if not response.headers.get('Content-Type', '').startswith(('audio/', 'application/octet-stream')):
                    raise RuntimeError('Music API returned non-audio content')
                state['song_id'] = response.headers.get('song-id')
                download(response, out)
        state.update(status='complete', bytes=out.stat().st_size,
                     sha256=hashlib.sha256(out.read_bytes()).hexdigest())
        save(state_path, state)
        print(f'Saved: {out}', flush=True)
    finally:
        lock.unlink(missing_ok=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='kind', required=True)
    tts = sub.add_parser('tts')
    tts.add_argument('--text-file', required=True)
    tts.add_argument('--speaker', help='Explicit audition voice; otherwise select and persist daily Vivi/Yunzhou')
    tts.add_argument('--episode-date', help='Episode date YYYY-MM-DD, defaults to Shanghai today')
    tts.add_argument('--speech-rate', type=int, choices=range(-50, 101), default=-8, metavar='[-50,100]')
    tts.add_argument('--wait-seconds', type=int, default=180)
    music = sub.add_parser('music')
    music.add_argument('--prompt', required=True)
    music.add_argument('--seconds', type=float, default=20)
    music.add_argument('--model', choices=['music_v1', 'music_v2', 'music_v2_5'], default='music_v2_5')
    for parser in (tts, music):
        parser.add_argument('--output', required=True)
        parser.add_argument('--dry-run', action='store_true')
    args = p.parse_args()
    load_env()
    try:
        generate(args)
    except (RuntimeError, OSError, ValueError, KeyError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
