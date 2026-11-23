#!/usr/bin/env python3
"""Kirim pesan via bot @muse01fthbot. Teks dibaca dari stdin (biar newline aman).
Pakai: printf '%s' 'teks balasan' | python3 send.py <chat_id> [--thread <id>] [--reply-to <msg_id>]
Output: JSON hasil sendMessage (ok + message_id).
"""
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
from vault_token import get_token
# Token dari Secure Vault (surrogate hsurr:...); runtime menukar jadi
# token asli saat request keluar. JANGAN print TOKEN.
TOKEN = get_token()

def post(payload):
    # SENGAJA tanpa retry (pelajaran 22 Nov 2026): sendMessage tidak
    # idempotent. Kalau percobaan pertama sampai ke Telegram tapi
    # responsnya hilang di jalan (egress putus), percobaan kedua akan
    # mengirim PESAN YANG SAMA untuk kedua kalinya — user lihat dobel.
    # Satu percobaan dengan timeout longgar; kalau gagal, caller yang
    # memutuskan (jangan kirim ulang membabi buta — lihat process-one.md).
    try:
        req = urllib.request.Request(
            f'https://api.telegram.org/bot{TOKEN}/sendMessage',
            data=json.dumps(payload).encode(), method='POST')
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except Exception as e:
        return {'ok': False, 'error': str(e)}

args = sys.argv[1:]
if not args:
    print('Pakai: send.py <chat_id> [--thread <id>] [--reply-to <msg_id>]', file=sys.stderr)
    raise SystemExit(2)
chat_id = args[0]
thread_id = None
reply_to = None
i = 1
while i < len(args):
    if args[i] == '--thread' and i + 1 < len(args):
        thread_id = int(args[i + 1]); i += 2
    elif args[i] == '--reply-to' and i + 1 < len(args):
        reply_to = int(args[i + 1]); i += 2
    else:
        i += 1
text = sys.stdin.read()
if not text.strip():
    print(json.dumps({'ok': False, 'error': 'teks kosong'}))
    raise SystemExit(1)
payload = {'chat_id': int(chat_id), 'text': text}
if thread_id:
    payload['message_thread_id'] = thread_id
if reply_to:
    payload['reply_parameters'] = {'message_id': reply_to}
print(json.dumps(post(payload), ensure_ascii=False))
