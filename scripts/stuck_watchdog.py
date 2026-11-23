#!/usr/bin/env python3
"""Stuck watchdog buat bot @muse01fthbot — adaptasi dari stuck_watchdog.py
repo twiceyuan/muse-telegram-connector (dibaca 22 Nov 2026, source:189).

Masalah: kalau subagent nyangkut (crash, approval nyangkut, generate gagal
diam-diam), user di Telegram cuma lihat typing hilang tanpa balasan — tidak
ada yang ngabarin.

Cara kerja:
- Subagent, di awal proses, bikin marker JSON di ~/workspace/muse-tele/
  processing/<message_id>.json berisi chat_id, thread_id (kalau ada),
  message_id, started_at (epoch). Di akhir proses, subagent HAPUS marker itu.
- Script ini dipanggil dispatcher tiap menit (tanpa giliran agent tambahan —
  dispatcher cron 1 menit sudah jalan): marker yang umurnya > 5 menit
  (= 300 dtk, sama kayak repo aslinya) dan belum pernah di-hint, dikirimi
  SATU pesan hint via send.py, lalu marker ditandai .hinted biar tidak
  spam tiap menit.
- Marker yang sudah .hinted tidak dikirimi lagi. Marker tidak pernah dihapus
  otomatis — dispatcher/agent yang menangani bisa lihat daftar nyangkut
  lewat --list.

Pakai: python3 stuck_watchdog.py [--dry-run] [--list]
       --dry-run: cuma tampilkan apa yang akan dikirim, tanpa panggil API.
       --list: tampilkan semua marker yang lagi diproses + umurnya.
Teks hint sengaja Bahasa Indonesia (repo aslinya masih Mandarin).
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROC_DIR = os.path.join(HERE, 'processing')
SEND = os.path.join(HERE, 'send.py')
STUCK_AFTER = 300  # detik — pesan dianggap nyangkut setelah 5 menit

HINT = ('Lagi diproses bro, agak lama dikit — mungkin lagi generate '
        'atau ada yang nyangkut. Tunggu sebentar ya.')


def markers():
    if not os.path.isdir(PROC_DIR):
        return []
    out = []
    for name in sorted(os.listdir(PROC_DIR)):
        if not name.endswith('.json'):
            continue
        path = os.path.join(PROC_DIR, name)
        try:
            with open(path) as f:
                out.append((path, json.load(f)))
        except Exception:
            continue
    return out


def send_hint(chat_id, thread_id, message_id):
    import subprocess
    cmd = [sys.executable, SEND, str(chat_id)]
    if thread_id:
        cmd += ['--thread', str(thread_id)]
    if message_id:
        cmd += ['--reply-to', str(message_id)]
    try:
        # send.py sendiri retry 3x @ 30 dtk (worst case ~102 dtk),
        # jadi timeout di sini harus lebih longgar dari itu.
        r = subprocess.run(cmd, input=HINT, capture_output=True,
                           text=True, timeout=120)
        return r.returncode == 0 and '"ok": true' in r.stdout
    except Exception:
        return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--list', action='store_true')
    args = p.parse_args()

    now = int(time.time())
    found = markers()
    if args.list:
        if not found:
            print('tidak ada pesan yang sedang diproses')
            return
        for path, m in found:
            age = now - int(m.get('started_at', now))
            hinted = os.path.exists(path + '.hinted')
            print(f"{m.get('message_id')} chat={m.get('chat_id')} "
                  f"umur={age}d hinted={hinted}")
        return

    for path, m in found:
        age = now - int(m.get('started_at', now))
        if age < STUCK_AFTER:
            continue
        if os.path.exists(path + '.hinted'):
            continue  # sudah pernah di-hint, jangan spam
        chat_id = m.get('chat_id')
        if not chat_id:
            continue
        if args.dry_run:
            print(f'[dry-run] akan kirim hint ke chat {chat_id} '
                  f'(message {m.get("message_id")}, umur {age}d)')
            continue
        if send_hint(chat_id, m.get('thread_id'), m.get('message_id')):
            open(path + '.hinted', 'w').write(str(now))
            print(f'hint terkirim ke chat {chat_id} '
                  f'(message {m.get("message_id")}, umur {age}d)')
        else:
            print(f'GAGAL kirim hint ke chat {chat_id}', file=sys.stderr)


if __name__ == '__main__':
    main()
