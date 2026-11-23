#!/usr/bin/env python3
"""Typing keeper buat bot @muse01fthbot — adaptasi dari typing_keeper.py
repo twiceyuan/muse-telegram-connector (dibaca 22 Nov 2026, source:189).

Masalah: status "mengetik..." Telegram cuma bertahan ~5 detik, padahal
subagent bisa kerja semenit lebih (apalagi pas generate gambar). Selama ini
process-one.md cuma nyuruh subagent kirim ulang typing secara manual —
gampang kelupaan di tengah kerja.

Cara pakai (dari subagent, langkah awal proses-one.md):
  nohup python3 ~/workspace/muse-tele/typing_keeper.py <chat_id> \\
      --done-file /tmp/muse-tele-typing-<message_id>.done \\
      [--thread <thread_id>] [--max-seconds 600] \\
      >> ~/workspace/muse-tele/typing_keeper.log 2>&1 &
  ... kerja seperti biasa ...
  touch /tmp/muse-tele-typing-<message_id>.done   # di akhir, sebelum selesai

Keeper kirim ulang typing tiap 4 detik lewat action.py (token tetap dibaca
action.py dari Secure Vault — script ini TIDAK pernah pegang token).
Berhenti sendiri kalau: file done muncul, sudah --max-seconds (default
600 dtk = 10 menit, sama kayak repo aslinya), atau chat action gagal
3x berturut-turut.
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ACTION = os.path.join(HERE, 'action.py')
INTERVAL = 4          # detik antar typing (repo asli: 4 dtk)
MAX_SECONDS = 600     # berhenti sendiri setelah 10 menit
MAX_FAILS = 3


def typing_once(chat_id, thread_id):
    cmd = [sys.executable, ACTION, 'typing', str(chat_id)]
    if thread_id:
        cmd += ['--thread', str(thread_id)]
    try:
        # action.py sendiri retry 3x @ 30 dtk (worst case ~102 dtk),
        # jadi timeout di sini harus lebih longgar dari itu.
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return r.returncode == 0 and '"ok": true' in r.stdout
    except Exception:
        return False


def already_running(done_file):
    # Satu pesan = satu keeper. Subagent kadang menjalankan langkah awal
    # berulang kali (22 Nov 2026: keeper dinyalakan 3x untuk 1 pesan);
    # duplikat langsung keluar, typing ganda tidak ada gunanya.
    pidfile = '/tmp/tg-keeper-%s.pid' % os.path.basename(
        done_file).replace('.done', '')
    try:
        with open(pidfile, 'r', encoding='utf-8') as fh:
            pid = int(fh.read().strip())
        os.kill(pid, 0)
        return True
    except Exception:
        pass
    try:
        with open(pidfile, 'w', encoding='utf-8') as fh:
            fh.write(str(os.getpid()))
    except Exception:
        pass
    return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument('chat_id', type=int)
    p.add_argument('--thread', type=int, default=None)
    p.add_argument('--done-file', required=True)
    p.add_argument('--max-seconds', type=int, default=MAX_SECONDS)
    args = p.parse_args()

    if already_running(args.done_file):
        print('typing keeper sudah jalan, skip', flush=True)
        return

    start = time.time()
    fails = 0
    sent = 0
    while True:
        if os.path.exists(args.done_file):
            break
        if time.time() - start >= args.max_seconds:
            break
        if typing_once(args.chat_id, args.thread):
            sent += 1
            fails = 0
        else:
            fails += 1
            if fails >= MAX_FAILS:
                break
        # Tunggu interval, tapi bangun lebih cepat kalau file done muncul.
        for _ in range(INTERVAL * 10):
            if os.path.exists(args.done_file):
                break
            time.sleep(0.1)
    try:
        os.remove(args.done_file)
    except FileNotFoundError:
        pass
    try:
        os.remove('/tmp/tg-keeper-%s.pid' % os.path.basename(
            args.done_file).replace('.done', ''))
    except FileNotFoundError:
        pass
    print(f'typing keeper berhenti: {sent}x typing terkirim, '
          f'{time.time() - start:.0f} detik', flush=True)


if __name__ == '__main__':
    main()
