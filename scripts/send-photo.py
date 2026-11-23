#!/usr/bin/env python3
"""Kirim foto ke chat via bot @muse01fthbot (Bot API sendPhoto).
Pakai: python3 send-photo.py <chat_id> <file_path> [--thread <id>] [--reply-to <msg_id>] [--caption <teks>]
Token dari Secure Vault (vault_token.py). SENGAJA tanpa retry.
"""
import json
import mimetypes
import os
import sys
import time
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))

from vault_token import get_token
# Token dari Secure Vault (surrogate hsurr:...); runtime menukar jadi
# token asli saat request keluar. JANGAN print TOKEN.
TOKEN = get_token()

args = sys.argv[1:]
if len(args) < 2:
    print(json.dumps({'ok': False, 'error': 'pakai: send-photo.py <chat_id> <file_path> [--thread <id>] [--reply-to <msg_id>] [--caption <teks>]'}))
    sys.exit(1)
chat_id = args[0]
file_path = args[1]
thread = reply_to = caption = None
i = 2
while i < len(args):
    if args[i] == '--thread' and i + 1 < len(args):
        thread = args[i + 1]; i += 2
    elif args[i] == '--reply-to' and i + 1 < len(args):
        reply_to = args[i + 1]; i += 2
    elif args[i] == '--caption' and i + 1 < len(args):
        caption = args[i + 1]; i += 2
    else:
        i += 1

boundary = '----muse-tele-' + uuid.uuid4().hex

def part(name, value, filename=None, ctype=None):
    h = '--' + boundary + '\r\nContent-Disposition: form-data; name="' + name + '"'
    if filename:
        h += '; filename="' + filename + '"'
    h += '\r\n'
    if ctype:
        h += 'Content-Type: ' + ctype + '\r\n'
    h += '\r\n'
    return h.encode() + (value if isinstance(value, bytes) else value.encode()) + b'\r\n'

body = b''
body += part('chat_id', chat_id)
if thread:
    body += part('message_thread_id', thread)
if reply_to:
    body += part('reply_to_message_id', reply_to)
if caption:
    body += part('caption', caption)
with open(file_path, 'rb') as f:
    data = f.read()
ctype = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
body += part('photo', data, filename=os.path.basename(file_path), ctype=ctype)
body += ('--' + boundary + '--\r\n').encode()

url = 'https://api.telegram.org/bot' + TOKEN + '/sendPhoto'
# SENGAJA tanpa retry (pelajaran 22 Nov 2026): sendPhoto tidak
# idempotent. Percobaan pertama yang sampai ke Telegram tapi responsnya
# hilang (egress putus) + percobaan kedua = foto terkirim DUA KALI.
# Satu percobaan dengan timeout longgar; kalau gagal, caller yang
# memutuskan (jangan kirim ulang membabi buta — lihat process-one.md).
try:
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'multipart/form-data; boundary=' + boundary})
    with urllib.request.urlopen(req, timeout=90) as resp:
        res = json.load(resp)
    if res.get('ok'):
        print(json.dumps({'ok': True, 'message_id': res['result']['message_id']}))
        sys.exit(0)
    print(json.dumps({'ok': False, 'error': str(res)}))
    sys.exit(1)
except Exception as e:
    print(json.dumps({'ok': False, 'error': str(e)}))
    sys.exit(1)
