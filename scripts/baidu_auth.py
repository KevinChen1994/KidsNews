#!/usr/bin/env python3
"""Authorize the project's own Baidu application; credentials stay in root .env."""
import argparse
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from audio import ROOT, env, load_env


def update_env(values):
    path = ROOT / '.env'
    lines = path.read_text().splitlines() if path.exists() else []
    remaining = dict(values)
    output = []
    for line in lines:
        match = re.match(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=', line)
        key = match.group(1) if match else None
        if key in values:
            if key in remaining:
                output.append(f'{key}="{remaining.pop(key)}"')
        else:
            output.append(line)
    output.extend(f'{key}="{value}"' for key, value in remaining.items())
    if any(any(c in str(value) for c in ['\n', '\r', '"']) for value in values.values()):
        raise RuntimeError('Unexpected characters in OAuth response')
    temp = path.with_suffix('.part')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as handle:
            handle.write('\n'.join(output)+'\n')
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def oauth(path, params):
    url = 'https://openapi.baidu.com' + path + '?' + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={'User-Agent': 'KidsNews/1.0'})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        try:
            result = json.loads(error.read(8192))
            return {'error': result.get('error', f'http_{error.code}')}
        except (ValueError, UnicodeError):
            return {'error': f'http_{error.code}'}
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError('Baidu OAuth network request failed; credentials were not logged') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['start', 'poll', 'status'])
    args = parser.parse_args()
    load_env()
    app_key = env('BAIDU_NETDISK_APPKEY', 'BAIDU_NETDISK_AppKey')
    secret_key = env('BAIDU_NETDISK_SECRETKEY', 'BAIDU_NETDISK_SecretKey')
    if args.command == 'status':
        print(json.dumps({'app_key_configured': bool(app_key),
                          'secret_key_configured': bool(secret_key),
                          'access_token_configured': bool(env('BAIDU_NETDISK_ACCESS_TOKEN')),
                          'refresh_token_configured': bool(env('BAIDU_NETDISK_REFRESH_TOKEN'))}))
        return
    if not app_key or not secret_key:
        parser.error('Configure AppKey and SecretKey in root .env first')
    if args.command == 'start':
        if env('BAIDU_NETDISK_ACCESS_TOKEN'):
            print(json.dumps({'status': 'token-already-configured', 'new_authorization_started': False}))
            return
        deadline = float(env('BAIDU_NETDISK_DEVICE_EXPIRES_AT') or 0)
        if deadline > time.time() and env('BAIDU_NETDISK_DEVICE_CODE'):
            print(json.dumps({'status': 'authorization-pending',
                              'verification_url': env('BAIDU_NETDISK_VERIFICATION_URL'),
                              'user_code': env('BAIDU_NETDISK_USER_CODE'),
                              'expires_in': int(deadline-time.time())}))
            return
        result = oauth('/oauth/2.0/device/code', {'response_type': 'device_code',
                       'client_id': app_key, 'scope': 'basic,netdisk'})
        if result.get('error'):
            print(json.dumps(result))
            raise SystemExit(1)
        url = result['verification_url']
        parsed = urllib.parse.urlsplit(url)
        if parsed.hostname not in ('openapi.baidu.com', 'passport.baidu.com'):
            raise RuntimeError('Unexpected OAuth verification destination')
        url = urllib.parse.urlunsplit(('https', parsed.netloc, parsed.path, parsed.query, ''))
        update_env({'BAIDU_NETDISK_DEVICE_CODE': result['device_code'],
                    'BAIDU_NETDISK_DEVICE_EXPIRES_AT': str(time.time()+result['expires_in']),
                    'BAIDU_NETDISK_USER_CODE': result['user_code'],
                    'BAIDU_NETDISK_VERIFICATION_URL': url})
        print(json.dumps({'status': 'authorization-required', 'verification_url': url,
                          'user_code': result['user_code'], 'expires_in': result['expires_in']}))
    else:
        code = env('BAIDU_NETDISK_DEVICE_CODE')
        if not code:
            parser.error('Run start first')
        result = oauth('/oauth/2.0/token', {'grant_type': 'device_token', 'code': code,
                       'client_id': app_key, 'client_secret': secret_key})
        if result.get('error'):
            print(json.dumps({'status': result['error']}))
            raise SystemExit(2 if result['error'] == 'authorization_pending' else 1)
        update_env({'BAIDU_NETDISK_ACCESS_TOKEN': result['access_token'],
                    'BAIDU_NETDISK_REFRESH_TOKEN': result.get('refresh_token', ''),
                    'BAIDU_NETDISK_TOKEN_EXPIRES_AT': str(time.time()+result['expires_in']),
                    'BAIDU_NETDISK_DEVICE_CODE': '', 'BAIDU_NETDISK_DEVICE_EXPIRES_AT': '0'})
        print(json.dumps({'status': 'authorized', 'scope': result.get('scope'),
                          'credentials_saved_to': '.env', 'expires_in': result['expires_in']}))


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, KeyError, ValueError) as error:
        print('OAuth failed safely; check configuration or response format.')
        raise SystemExit(1) from None
