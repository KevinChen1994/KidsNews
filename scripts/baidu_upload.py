#!/usr/bin/env python3
"""Upload through the account owner's OAuth app, without overwriting cloud files."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from audio import ROOT, env, load_env, save
from baidu_auth import oauth, update_env
from prepare_script import load_profile

BLOCK_SIZE = 4 * 1024 * 1024


class APIError(RuntimeError):
    def __init__(self, operation, code):
        self.operation, self.code = operation, code
        super().__init__(f'Baidu {operation} failed, code={code}; no automatic retry')


def access_token():
    token = env('BAIDU_NETDISK_ACCESS_TOKEN')
    if not token:
        raise RuntimeError('Account authorization is missing; run baidu_auth.py first')
    expiry = float(env('BAIDU_NETDISK_TOKEN_EXPIRES_AT') or 0)
    if expiry and expiry <= time.time() + 60:
        refresh = env('BAIDU_NETDISK_REFRESH_TOKEN')
        if not refresh:
            raise RuntimeError('Token expired and refresh token is missing')
        response = oauth('/oauth/2.0/token', {
            'grant_type': 'refresh_token', 'refresh_token': refresh,
            'client_id': env('BAIDU_NETDISK_APPKEY', 'BAIDU_NETDISK_AppKey'),
            'client_secret': env('BAIDU_NETDISK_SECRETKEY', 'BAIDU_NETDISK_SecretKey')})
        if response.get('error'):
            raise APIError('refresh', response['error'])
        token = response['access_token']
        update_env({'BAIDU_NETDISK_ACCESS_TOKEN': token,
                    'BAIDU_NETDISK_REFRESH_TOKEN': response.get('refresh_token', refresh),
                    'BAIDU_NETDISK_TOKEN_EXPIRES_AT': str(time.time()+response['expires_in'])})
    return token


class Client:
    def __init__(self, token):
        self.token = token

    def request(self, method, params=None, form=None, chunk=None):
        query = dict(params or {}, method=method, access_token=self.token)
        base = ('https://d.pcs.baidu.com/rest/2.0/pcs/superfile2' if chunk is not None
                else 'https://pan.baidu.com/rest/2.0/xpan/file')
        headers = {'User-Agent': 'KidsNews/1.0'}
        body = None
        if form is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
            body = urllib.parse.urlencode(form).encode()
        if chunk is not None:
            boundary = 'KidsNews' + uuid.uuid4().hex
            headers['Content-Type'] = 'multipart/form-data; boundary='+boundary
            body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                    'filename="part"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()
            body += chunk + f'\r\n--{boundary}--\r\n'.encode()
        request = urllib.request.Request(base+'?'+urllib.parse.urlencode(query),
                                         data=body, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                data = json.load(response)
        except urllib.error.HTTPError as error:
            raise APIError(method, f'http_{error.code}') from None
        except (urllib.error.URLError, TimeoutError):
            raise APIError(method, 'network-uncertain') from None
        code = data.get('errno', data.get('error_code', 0))
        if code:
            raise APIError(method, code)
        return data

    def find_file(self, directory, name):
        start = 0
        while True:
            items = self.request('list', {'dir': directory, 'start': start, 'limit': 1000}).get('list', [])
            for item in items:
                if item['server_filename'] == name:
                    return item
            if len(items) < 1000:
                return None
            start += len(items)


def validate_target(directory, name):
    path = PurePosixPath(directory)
    if not path.is_absolute() or '..' in path.parts or str(path) == '/':
        raise ValueError('Use an explicit absolute cloud directory, without parent traversal')
    if not name or PurePosixPath(name).name != name or name in ('.', '..') or '\\' in name:
        raise ValueError('Remote filename must not contain a directory')
    return str(path / name)


def upload(client, source, directory, name, create_directory=False):
    remote = validate_target(directory, name)
    file_bytes = source.read_bytes()
    if not file_bytes:
        raise ValueError('Empty files are not uploaded')
    sha256 = hashlib.sha256(file_bytes).hexdigest()
    md5 = hashlib.md5(file_bytes).hexdigest()
    cache = ROOT / 'state/uploads' / (hashlib.sha256(remote.encode()).hexdigest()+'.json')
    cache.parent.mkdir(parents=True, exist_ok=True)
    state = json.loads(cache.read_text()) if cache.exists() else {}
    if state and state.get('sha256') != sha256:
        raise RuntimeError('Cloud path belongs to a different local request; choose another filename')
    try:
        existing = client.find_file(directory, name)
    except APIError as error:
        if not create_directory or error.code not in (-9, 31066):
            raise
        client.request('create', form={'path': directory, 'isdir': 1, 'rtype': 0})
        existing = None
    if existing:
        same_content = (existing.get('size') == len(file_bytes) and
                        existing.get('md5') == (state.get('cloud_md5') or md5))
        if not same_content or existing.get('isdir'):
            raise RuntimeError('A cloud file already exists; cannot confirm matching content, so no overwrite')
        state.update(status='complete', path=remote, sha256=sha256, bytes=len(file_bytes),
                     fs_id=existing['fs_id'], cloud_md5=existing.get('md5'), verified_at=time.time())
        save(cache, state)
        return dict(state, cached=True)

    chunks = [file_bytes[i:i+BLOCK_SIZE] for i in range(0, len(file_bytes), BLOCK_SIZE)]
    block_md5 = [hashlib.md5(chunk).hexdigest() for chunk in chunks]
    state.update(path=remote, sha256=sha256, bytes=len(file_bytes))
    try:
        if not state.get('upload_id'):
            state.update(status='precreating')
            save(cache, state)
            result = client.request('precreate', form={
                'path': remote, 'size': len(file_bytes), 'isdir': 0, 'autoinit': 1,
                'rtype': 0, 'block_list': json.dumps(block_md5)})
            if result.get('return_type') == 2:
                existing = client.find_file(directory, name)
                if not existing or existing.get('size') != len(file_bytes) or existing.get('md5') != md5:
                    raise RuntimeError('Instant upload requires verification; no further write attempted')
                state.update(status='complete', fs_id=existing['fs_id'],
                             cloud_md5=existing['md5'], verified_at=time.time())
                save(cache, state)
                return state
            state.update(upload_id=result['uploadid'],
                         missing_parts=result.get('block_list', list(range(len(chunks)))),
                         uploaded_parts={}, status='uploading')
            save(cache, state)
        for index in state['missing_parts']:
            if str(index) in state['uploaded_parts']:
                continue
            result = client.request('upload', {'type': 'tmpfile', 'path': remote,
                                    'uploadid': state['upload_id'], 'partseq': index}, chunk=chunks[index])
            if result.get('md5') != block_md5[index]:
                raise RuntimeError('Uploaded part checksum mismatch')
            state['uploaded_parts'][str(index)] = result['md5']
            save(cache, state)
        state['status'] = 'creating'
        save(cache, state)
        result = client.request('create', form={'path': remote, 'size': len(file_bytes),
                                'isdir': 0, 'rtype': 0, 'uploadid': state['upload_id'],
                                'block_list': json.dumps(block_md5)})
        state.update(status='verifying', fs_id=result['fs_id'], cloud_md5=result.get('md5'))
        save(cache, state)
        existing = client.find_file(directory, name)
        if not existing or existing['fs_id'] != state['fs_id'] or existing.get('size') != len(file_bytes):
            raise RuntimeError('File created but list verification is pending; reuse this request to inspect')
        if existing.get('md5') != state.get('cloud_md5'):
            raise RuntimeError('Created file metadata and listing checksum differ')
        state.update(status='complete', verified_at=time.time())
        save(cache, state)
        return state
    except (APIError, RuntimeError, KeyError):
        save(cache, state)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', required=True)
    parser.add_argument('--remote-dir', help='Defaults to delivery.baidu_remote_dir in config/local.json')
    parser.add_argument('--remote-name')
    parser.add_argument('--create-dir', action='store_true', help='Create the specified directory if missing')
    args = parser.parse_args()
    load_env()
    directory = args.remote_dir or load_profile()['delivery'].get('baidu_remote_dir')
    if not directory:
        parser.error('Configure delivery.baidu_remote_dir or pass --remote-dir')
    source = Path(args.file)
    try:
        result = upload(Client(access_token()), source, directory,
                        args.remote_name or source.name, args.create_dir)
        print(json.dumps(result, ensure_ascii=False))
    except (APIError, RuntimeError, ValueError, OSError, KeyError) as error:
        # Exception messages from urllib never reach this output, so tokens stay private.
        parser.exit(1, f'Upload stopped: {error if isinstance(error, (APIError, RuntimeError, ValueError)) else "local file or response error"}\n')


if __name__ == '__main__':
    main()
