#!/usr/bin/env python3
"""Stuck watchdog buat bot — adaptasi dari stuck_watchdog.py
repo twiceyuan/muse-telegram-connector (dibaca 22 Nov 2026, source:189).

Masalah: kalau subagent nyangkut (crash, approval nyangkut, generate gagal
diam-diam), user di Telegram cuma lihat typing hilang tanpa balasan — tidak
ada yang ngabarin.

Cara kerja:
- Subagent, di awal proses, bikin marker JSON via mark.py di
  processing/<chat_id>_<message_id>.json. Di akhir proses, subagent
  HAPUS marker itu (mark.py delete). Kalau gagal kirim balasan, subagent
  menulis marker gagal (.failed.json) lewat mark.py fail.
- Script ini dipanggil dispatch.py tiap menit:
  - Marker proses umur > 5 menit dan belum di-hint: kirim hint 1x,
    tandai .hinted. Umur > 30 menit: hint ke-2 (.hinted2).
    Umur > 60 menit: tulis .escalated — dispatch.py menyertakannya
    di rencana supaya agent melapor ke chat Muse.
  - Marker gagal (.failed.json): kirim SATU pemberitahuan ke user
    ("balasan gagal kekirim, coba kirim ulang"), tandai .notified.
  - Bersih-bersih: marker proses > 24 jam dihapus; marker gagal
    > 7 hari dihapus; file penanda yatim (tanpa marker induk) dihapus.
Teks hint sengaja Bahasa Indonesia (repo aslinya masih Mandarin).
Pakai: python3 stuck_watchdog.py [--dry-run] [--list]
"""
import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROC_DIR = os.path.join(HERE, 'processing')
SEND = os.path.join(HERE, 'send.py')
RUNS_LOG = os.path.join(HERE, 'runs.log')
STUCK_AFTER = 300    # detik — hint pertama setelah 5 menit
HINT2_AFTER = 1800   # detik — hint kedua setelah 30 menit
ESCALATE_AFTER = 3600  # detik — eskalasi setelah 60 menit
MARKER_MAX_AGE = 86400     # detik — marker proses dibersihkan setelah 24 jam
FAILED_MAX_AGE = 7 * 86400  # detik — marker gagal dibersihkan setelah 7 hari

HINT1 = ('Lagi diproses bro, agak lama dikit — mungkin lagi generate '
         'atau ada yang nyangkut. Tunggu sebentar ya.')
HINT2 = ('Masih diproses bro, udah lebih dari 30 menit. Kalau kelamaan, '
         'coba kirim ulang pesannya ya.')


def _log(obj):
    try:
        with open(RUNS_LOG, 'a') as f:
            f.write(json.dumps(obj, ensure_ascii=False) + '\n')
    except Exception:
        pass


def _load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def _short_reason(error):
    e = (error or '').lower()
    if 'too long' in e or 'message text is too long' in e:
        return 'pesan kepanjangan'
    if 'bot was blocked' in e or 'forbidden' in e:
        return 'bot diblokir'
    if 'chat not found' in e:
        return 'chat tidak ditemukan'
    if 'timeout' in e or 'timed out' in e or 'remote end closed' in e:
        return 'gangguan jaringan'
    return 'gangguan teknis'


def _send(chat_id, thread_id, message_id, text):
    cmd = [sys.executable, SEND, str(chat_id)]
    if thread_id:
        cmd += ['--thread', str(thread_id)]
    if message_id:
        cmd += ['--reply-to', str(message_id)]
    try:
        # send.py sendiri SATU percobaan @ 60 dtk, jadi timeout di sini
        # harus lebih longgar.
        r = subprocess.run(cmd, input=text, capture_output=True,
                           text=True, timeout=90)
        return r.returncode == 0 and '"ok": true' in r.stdout
    except Exception:
        return False


def _markers():
    if not os.path.isdir(PROC_DIR):
        return [], []
    proc, failed = [], []
    for name in sorted(os.listdir(PROC_DIR)):
        path = os.path.join(PROC_DIR, name)
        if name.endswith('.failed.json'):
            m = _load(path)
            if m:
                failed.append((path, m))
        elif name.endswith('.json') and not name.endswith('.tmp'):
            m = _load(path)
            if m:
                proc.append((path, m))
    return proc, failed


def _flag(path, suffix):
    return os.path.exists(path + suffix)


def _touch(path, suffix, now):
    try:
        with open(path + suffix, 'w') as f:
            f.write(str(now))
    except Exception:
        pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--list', action='store_true')
    args = p.parse_args()

    now = int(time.time())
    proc, failed = _markers()
    if args.list:
        if not proc and not failed:
            print('tidak ada pesan yang sedang diproses / gagal')
            return
        for path, m in proc:
            age = now - int(m.get('started_at', now))
            print(f"{m.get('message_id')} chat={m.get('chat_id')} "
                  f"umur={age}d hinted={_flag(path, '.hinted')} "
                  f"hinted2={_flag(path, '.hinted2')} "
                  f"escalated={_flag(path, '.escalated')}")
        for path, m in failed:
            age = now - int(m.get('failed_at', now))
            print(f"GAGAL {m.get('message_id')} chat={m.get('chat_id')} "
                  f"umur={age}d notified={_flag(path, '.notified')} "
                  f"alasan={_short_reason(m.get('error', ''))}")
        return

    for path, m in proc:
        age = now - int(m.get('started_at', now))
        chat_id = m.get('chat_id')
        if not chat_id:
            continue
        if age >= MARKER_MAX_AGE:
            # Sudah dieskalasi (atau tidak ada yang peduli) — bersihkan.
            for suffix in ('', '.hinted', '.hinted2', '.escalated'):
                try:
                    os.remove(path + suffix)
                except FileNotFoundError:
                    pass
            _log({'ts': now, 'event': 'marker_dibersihkan',
                  'message_id': m.get('message_id')})
            continue
        if age >= ESCALATE_AFTER and not _flag(path, '.escalated'):
            _touch(path, '.escalated', now)
            _log({'ts': now, 'event': 'escalated',
                  'message_id': m.get('message_id'), 'chat_id': chat_id})
            continue
        if age >= HINT2_AFTER and _flag(path, '.hinted') \
                and not _flag(path, '.hinted2'):
            if args.dry_run:
                print(f'[dry-run] hint ke-2 ke chat {chat_id}')
                continue
            if _send(chat_id, m.get('thread_id'), m.get('message_id'), HINT2):
                _touch(path, '.hinted2', now)
            continue
        if age >= STUCK_AFTER and not _flag(path, '.hinted'):
            if args.dry_run:
                print(f'[dry-run] hint ke-1 ke chat {chat_id}')
                continue
            if _send(chat_id, m.get('thread_id'), m.get('message_id'), HINT1):
                _touch(path, '.hinted', now)

    for path, m in failed:
        age = now - int(m.get('failed_at', now))
        if age >= FAILED_MAX_AGE:
            for suffix in ('', '.notified'):
                try:
                    os.remove(path + suffix)
                except FileNotFoundError:
                    pass
            continue
        if _flag(path, '.notified'):
            continue
        chat_id = m.get('chat_id')
        if not chat_id:
            continue
        text = ('Maaf bro, balasan gw buat pesan tadi gagal kekirim '
                '(%s). Coba kirim ulang pesannya ya.'
                % _short_reason(m.get('error', '')))
        if args.dry_run:
            print(f'[dry-run] kabar gagal ke chat {chat_id}')
            continue
        _send(chat_id, m.get('thread_id'), m.get('message_id'), text)
        # Tandai apa pun hasilnya — jangan spam tiap menit.
        _touch(path, '.notified', now)
        _log({'ts': now, 'event': 'failed_diberitahu',
              'message_id': m.get('message_id'), 'chat_id': chat_id})

    # Bersihkan file penanda yatim (marker induknya sudah tidak ada).
    if os.path.isdir(PROC_DIR):
        for name in os.listdir(PROC_DIR):
            if name.endswith(('.hinted', '.hinted2', '.notified',
                              '.escalated')):
                base = name.rsplit('.', 1)[0]
                if not os.path.exists(os.path.join(PROC_DIR, base)):
                    try:
                        os.remove(os.path.join(PROC_DIR, name))
                    except Exception:
                        pass


if __name__ == '__main__':
    main()
