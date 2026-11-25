#!/usr/bin/env python3
"""Ambil update baru dari bot via getUpdates (polling, tanpa webhook).
Baca offset dari state.json, TIDAK memajukan offset (pemanggil yang memajukan
setelah pesan selesai ditangani — supaya tidak ada pesan yang hilang).
Output: SATU objek JSON {"updates": [...], "max_update_id": N|null}.
  - "updates": hanya update yang punya 'message' (teks/media). Tiap update
    membawa file_id + file_size kalau pesannya bawa media (buat fetch.py).
  - "max_update_id": update_id TERBESAR yang terlihat di hasil getUpdates,
    termasuk update non-message (edit, dsb.) — supaya dispatcher bisa
    mengklaim/melewatinya dan offset tidak macet di update non-teks.
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
try:
    with open(os.path.join(HERE, 'state.json')) as f:
        STATE = json.load(f)
except Exception as e:
    print(json.dumps({'error': 'state.json tidak bisa dibaca: %s' % e}))
    raise SystemExit(1)

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

MEDIA_KEYS = ('photo', 'video', 'document', 'sticker', 'voice',
              'video_note', 'audio', 'animation', 'contact',
              'location', 'poll')

out = []
max_update_id = None
for u in data.get('result', []):
    uid = u.get('update_id')
    if isinstance(uid, int):
        max_update_id = uid if max_update_id is None else max(max_update_id, uid)
    msg = u.get('message')
    if not msg:
        continue
    text = msg.get('text') or msg.get('caption') or ''
    media = None
    file_id = None
    file_size = None
    for key in MEDIA_KEYS:
        if key in msg:
            media = key
            val = msg[key]
            if key == 'photo' and isinstance(val, list) and val:
                # photo adalah array ukuran; ambil yang terbesar (terakhir).
                biggest = val[-1]
                file_id = biggest.get('file_id')
                file_size = biggest.get('file_size')
            elif isinstance(val, dict):
                file_id = val.get('file_id')
                file_size = val.get('file_size')
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
        'file_id': file_id,
        'file_size': file_size,
        'date': msg.get('date'),
    })
print(json.dumps({'updates': out, 'max_update_id': max_update_id},
                 ensure_ascii=False))
