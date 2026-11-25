#!/usr/bin/env python3
"""Kirim video ke chat via bot (Bot API sendVideo).
Pakai: python3 send-video.py <chat_id> <file_path> [--thread <id>] [--reply-to <msg_id>] [--caption <teks>] [--duration <detik>]
Token dari Secure Vault (vault_token.py).
SENGAJA tanpa retry (pelajaran 22 Nov 2026): sendVideo tidak
idempotent. Percobaan pertama yang sampai ke Telegram tapi responsnya
hilang (egress putus) + percobaan kedua = video terkirim DUA KALI.
Satu percobaan dengan timeout longgar; kalau gagal, caller yang
memutuskan (jangan kirim ulang membabi buta — lihat process-one.md).
Batas ukuran file 50 MB (limit Bot API) — dicek SEBELUM dibaca ke RAM.
"""
import json
import mimetypes
import os
import subprocess
import sys
import urllib.request
import uuid

from vault_token import get_token
# Token dari Secure Vault (surrogate hsurr:...); runtime menukar jadi
# token asli saat request keluar. JANGAN print TOKEN.
TOKEN = get_token()

MAX_FILE = 50 * 1024 * 1024  # 50 MB — limit Bot API buat kirim file


def part(boundary, name, value, filename=None, ctype=None):
    h = '--' + boundary + '\r\nContent-Disposition: form-data; name="' + name + '"'
    if filename:
        h += '; filename="' + filename + '"'
    h += '\r\n'
    if ctype:
        h += 'Content-Type: ' + ctype + '\r\n'
    h += '\r\n'
    return h.encode() + (value if isinstance(value, bytes) else value.encode()) + b'\r\n'


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        print(json.dumps({'ok': False, 'error': 'pakai: send-video.py <chat_id> <file_path> [--thread <id>] [--reply-to <msg_id>] [--caption <teks>] [--duration <detik>]'}))
        sys.exit(1)
    chat_id = args[0]
    file_path = args[1]
    thread = reply_to = caption = duration = None
    i = 2
    while i < len(args):
        if args[i] == '--thread' and i + 1 < len(args):
            thread = args[i + 1]; i += 2
        elif args[i] == '--reply-to' and i + 1 < len(args):
            reply_to = args[i + 1]; i += 2
        elif args[i] == '--caption' and i + 1 < len(args):
            caption = args[i + 1]; i += 2
        elif args[i] == '--duration' and i + 1 < len(args):
            duration = args[i + 1]; i += 2
        else:
            i += 1

    if not os.path.isfile(file_path):
        print(json.dumps({'ok': False, 'error': 'file tidak ada: %s' % file_path}))
        sys.exit(1)
    if os.path.getsize(file_path) > MAX_FILE:
        print(json.dumps({'ok': False,
                          'error': 'file kebesaran (> 50 MB, limit Bot API)'}))
        sys.exit(1)

    # Durasi & dimensi dari ffprobe kalau tidak dikasih manual.
    width = height = None
    if duration is None:
        try:
            out = subprocess.run(
                ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                 '-show_entries', 'stream=width,height,duration',
                 '-of', 'json', file_path],
                capture_output=True, text=True, timeout=30)
            stream = json.loads(out.stdout)['streams'][0]
            duration = str(int(round(float(stream['duration']))))
            width, height = str(stream['width']), str(stream['height'])
        except Exception:
            width = height = None

    boundary = '----muse-tele-' + uuid.uuid4().hex
    body = b''
    body += part(boundary, 'chat_id', chat_id)
    body += part(boundary, 'supports_streaming', 'true')
    if thread:
        body += part(boundary, 'message_thread_id', thread)
    if reply_to:
        body += part(boundary, 'reply_parameters',
                     json.dumps({'message_id': int(reply_to)}))
    if duration:
        body += part(boundary, 'duration', duration)
    if width:
        body += part(boundary, 'width', width)
        body += part(boundary, 'height', height)
    if caption:
        body += part(boundary, 'caption', caption)
    with open(file_path, 'rb') as f:
        data = f.read()
    ctype = mimetypes.guess_type(file_path)[0] or 'video/mp4'
    body += part(boundary, 'video', data, filename=os.path.basename(file_path),
                 ctype=ctype)
    body += ('--' + boundary + '--\r\n').encode()

    url = 'https://api.telegram.org/bot' + TOKEN + '/sendVideo'
    try:
        req = urllib.request.Request(url, data=body, headers={'Content-Type': 'multipart/form-data; boundary=' + boundary})
        with urllib.request.urlopen(req, timeout=180) as resp:
            res = json.load(resp)
        if res.get('ok'):
            print(json.dumps({'ok': True, 'message_id': res['result']['message_id']}))
            sys.exit(0)
        print(json.dumps({'ok': False, 'error': str(res)}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({'ok': False, 'error': str(e)}))
        sys.exit(1)


if __name__ == '__main__':
    main()
