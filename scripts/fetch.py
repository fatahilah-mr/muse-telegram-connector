#!/usr/bin/env python3
"""Unduh file media yang dikirim ke bot (getFile + download).
Dipakai process-one.md supaya subagent bisa MELIHAT foto, MEMBACA
dokumen, dan MENTRANSKRIP voice note — bukan cuma baca caption.
URL unduh: https://api.telegram.org/file/bot<token>/<file_path> — SATU
segmen /file/ saja (pelajaran 20 Nov 2026: /file/ kedua = 404 permanen).
Batas unduh 20 MB (limit Bot API). File disimpan di downloads/ dengan
nama aman; file unduhan lebih dari 24 jam dibersihkan otomatis tiap run.
Pakai: python3 fetch.py <file_id> [--filename <nama>]
Output: JSON {"ok": true, "path": ..., "size": ...} atau error.
"""
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DL_DIR = os.path.join(HERE, 'downloads')
MAX_DOWNLOAD = 20 * 1024 * 1024  # 20 MB — limit unduh Bot API

from vault_token import get_token
# Token dari Secure Vault (surrogate hsurr:...); runtime menukar jadi
# token asli saat request keluar. JANGAN print TOKEN.
TOKEN = get_token()


def _safe_name(name):
    name = re.sub(r'[^A-Za-z0-9._-]+', '_', name or '')
    return name[:80] or 'file'


def _cleanup_old():
    try:
        now = time.time()
        for name in os.listdir(DL_DIR):
            path = os.path.join(DL_DIR, name)
            try:
                if os.path.isfile(path) and now - os.path.getmtime(path) > 86400:
                    os.remove(path)
            except Exception:
                pass
    except Exception:
        pass


def _api(method, payload=None):
    last_err = None
    for attempt in range(3):  # getFile/download boleh retry (read-only)
        try:
            req = urllib.request.Request(
                f'https://api.telegram.org/bot{TOKEN}/{method}',
                data=json.dumps(payload).encode() if payload else None,
                method='POST' if payload else 'GET')
            if payload:
                req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    return {'ok': False, 'error': str(last_err)}


def main():
    args = sys.argv[1:]
    if len(args) < 1:
        print('Pakai: fetch.py <file_id> [--filename <nama>]', file=sys.stderr)
        raise SystemExit(2)
    file_id = args[0]
    filename = None
    if '--filename' in args:
        filename = args[args.index('--filename') + 1]

    os.makedirs(DL_DIR, exist_ok=True)
    _cleanup_old()

    res = _api('getFile', {'file_id': file_id})
    if not res.get('ok'):
        print(json.dumps({'ok': False, 'error': str(res)}))
        raise SystemExit(1)
    info = res['result']
    file_path = info.get('file_path')
    file_size = info.get('file_size') or 0
    if not file_path:
        print(json.dumps({'ok': False, 'error': 'getFile tidak mengembalikan file_path'}))
        raise SystemExit(1)
    if file_size > MAX_DOWNLOAD:
        print(json.dumps({'ok': False,
                          'error': 'file kebesaran buat diunduh (> 20 MB)'}))
        raise SystemExit(1)

    ext = os.path.splitext(file_path)[1]
    base = _safe_name(filename) if filename else os.path.basename(file_path)
    if ext and not base.endswith(ext):
        base += ext
    local = os.path.join(DL_DIR, '%s_%s' % (_safe_name(file_id)[:16], base))
    url = 'https://api.telegram.org/file/bot%s/%s' % (TOKEN, file_path)
    try:
        req = urllib.request.Request(url)
        size = 0
        with urllib.request.urlopen(req, timeout=120) as resp, open(local, 'wb') as f:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_DOWNLOAD:
                    raise RuntimeError('file kebesaran saat diunduh (> 20 MB)')
                f.write(chunk)
    except Exception as e:
        try:
            os.remove(local)
        except Exception:
            pass
        print(json.dumps({'ok': False, 'error': str(e)}))
        raise SystemExit(1)
    print(json.dumps({'ok': True, 'path': local, 'size': size},
                     ensure_ascii=False))


if __name__ == '__main__':
    main()
