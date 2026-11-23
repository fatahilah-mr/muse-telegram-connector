#!/usr/bin/env python3
"""Aksi status bot @muse01fthbot saat memproses pesan:
- typing: nyalakan status "mengetik..." di chat (berlaku ~5 detik, kirim ulang
  kalau proses jawabnya lebih lama).
- react: kasih reaction emoji ke satu pesan (dipakai di grup, biar pengirim
  tahu pesannya sudah dilihat/diproses).
Pakai: python3 action.py typing <chat_id> [--thread <id>]
       python3 action.py react <chat_id> <message_id> <emoji>
Output: JSON hasil Bot API.
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

def call(method, payload):
    last_err = None
    for attempt in range(3):  # egress kadang putus — coba lagi
        try:
            req = urllib.request.Request(
                f'https://api.telegram.org/bot{TOKEN}/{method}',
                data=json.dumps(payload).encode(), method='POST')
            req.add_header('Content-Type', 'application/json')
            with urllib.request.urlopen(req, timeout=30) as resp:
                print(json.dumps(json.load(resp), ensure_ascii=False))
                return
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    print(json.dumps({'ok': False, 'error': str(last_err)}))

args = sys.argv[1:]
if not args:
    print('Pakai: action.py typing <chat_id> | react <chat_id> <message_id> <emoji>', file=sys.stderr)
    raise SystemExit(2)
if args[0] == 'typing':
    chat_id = int(args[1])
    payload = {'chat_id': chat_id, 'action': 'typing'}
    if '--thread' in args:
        payload['message_thread_id'] = int(args[args.index('--thread') + 1])
    call('sendChatAction', payload)
elif args[0] == 'react':
    chat_id, message_id, emoji = int(args[1]), int(args[2]), args[3]
    call('setMessageReaction', {
        'chat_id': chat_id,
        'message_id': message_id,
        'reaction': [{'type': 'emoji', 'emoji': emoji}],
    })
else:
    print('aksi tidak dikenal: typing | react', file=sys.stderr)
    raise SystemExit(2)
