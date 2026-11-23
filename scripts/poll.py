#!/usr/bin/env python3
"""Ambil update baru dari bot @muse01fthbot via getUpdates (polling, tanpa webhook).
Baca offset dari state.json, TIDAK memajukan offset (pemanggil yang memajukan
setelah pesan selesai ditangani — supaya tidak ada pesan yang hilang).
Output: JSON array update pesan teks.
Pakai: python3 poll.py
"""
import json
import os
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

from vault_token import get_token
# Token dari Secure Vault (surrogate hsurr:...); runtime menukar jadi
# token asli saat request keluar. JANGAN print TOKEN.
TOKEN = get_token()
with open(os.path.join(HERE, 'state.json')) as f:
    STATE = json.load(f)

offset = STATE.get('offset', 0)
url = f'https://api.telegram.org/bot{TOKEN}/getUpdates?offset={offset}&timeout=0&limit=100'
data = None
last_err = None
for attempt in range(3):  # egress kadang putus (RemoteDisconnected) — coba lagi
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.load(resp)
        break
    except Exception as e:
        last_err = e
        time.sleep(2 * (attempt + 1))
if data is None:
    print(json.dumps({'error': str(last_err)}))
    raise SystemExit(1)
if not data.get('ok'):
    print(json.dumps({'error': data}))
    raise SystemExit(1)

out = []
for u in data.get('result', []):
    msg = u.get('message')
    if not msg:
        continue
    text = msg.get('text') or msg.get('caption') or ''
    media = None
    for key in ('photo', 'video', 'document', 'sticker', 'voice',
                'video_note', 'audio', 'animation', 'contact',
                'location', 'poll'):
        if key in msg:
            media = key
            break
    out.append({
        'update_id': u['update_id'],
        'message_id': msg['message_id'],
        'chat_id': msg['chat']['id'],
        'chat_type': msg['chat'].get('type'),
        'chat_title': msg['chat'].get('title'),
        'thread_id': msg.get('message_thread_id'),
        'from_id': (msg.get('from') or {}).get('id'),
        'from_username': (msg.get('from') or {}).get('username'),
        'from_name': ((msg.get('from') or {}).get('first_name') or ''),
        'text': text,
        'media': media,
        'date': msg.get('date'),
    })
print(json.dumps(out, ensure_ascii=False))
