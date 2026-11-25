#!/usr/bin/env python3
"""Marker pesan yang sedang diproses — dipakai subagent (process-one.md)
dan watchdog. Nama file SELALU memuat chat_id + message_id, karena
message_id Telegram cuma unik di dalam satu chat (DM A dan DM B bisa
punya message_id yang sama — versi lama yang cuma pakai message_id
bisa ketimpa antar chat).
Pakai:
  python3 mark.py create <chat_id> <message_id> [--thread <id>]
  python3 mark.py delete <chat_id> <message_id>
  python3 mark.py fail <chat_id> <message_id> <alasan-gagal>
  python3 mark.py list
Marker: processing/<chat_id>_<message_id>.json
Gagal:  processing/<chat_id>_<message_id>.failed.json (ganti marker biasa)
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROC_DIR = os.path.join(HERE, 'processing')


def _path(chat_id, message_id, suffix='.json'):
    return os.path.join(PROC_DIR, '%s_%s%s' % (chat_id, message_id, suffix))


def _atomic_write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp.%d' % os.getpid()
    with open(tmp, 'w') as f:
        json.dump(data, f)
    os.replace(tmp, path)


def create(chat_id, message_id, thread_id=None):
    _atomic_write(_path(chat_id, message_id), {
        'chat_id': int(chat_id),
        'thread_id': thread_id,
        'message_id': int(message_id),
        'started_at': int(time.time()),
    })
    print('OK')


def delete(chat_id, message_id):
    for suffix in ('.json', '.json.hinted', '.json.hinted2',
                   '.json.escalated',
                   '.failed.json', '.failed.json.notified'):
        try:
            os.remove(_path(chat_id, message_id, suffix))
        except FileNotFoundError:
            pass
    print('OK')


def fail(chat_id, message_id, error, thread_id=None):
    # Marker biasa diganti marker gagal — watchdog yang akan memberi
    # kabar satu kali ke user (lihat stuck_watchdog.py).
    try:
        os.remove(_path(chat_id, message_id))
    except FileNotFoundError:
        pass
    _atomic_write(_path(chat_id, message_id, '.failed.json'), {
        'chat_id': int(chat_id),
        'thread_id': thread_id,
        'message_id': int(message_id),
        'error': str(error)[:500],
        'failed_at': int(time.time()),
    })
    print('OK')


def list_markers():
    out = []
    if os.path.isdir(PROC_DIR):
        for name in sorted(os.listdir(PROC_DIR)):
            if name.endswith('.json') and not name.endswith('.failed.json'):
                try:
                    with open(os.path.join(PROC_DIR, name)) as f:
                        out.append(json.load(f))
                except Exception:
                    continue
    print(json.dumps(out, ensure_ascii=False))


def main():
    args = sys.argv[1:]
    if not args:
        print('Pakai: mark.py create|delete|fail|list ...', file=sys.stderr)
        raise SystemExit(2)
    if args[0] == 'create' and len(args) >= 3:
        thread = None
        if '--thread' in args:
            thread = int(args[args.index('--thread') + 1])
        create(args[1], args[2], thread)
    elif args[0] == 'delete' and len(args) >= 3:
        delete(args[1], args[2])
    elif args[0] == 'fail' and len(args) >= 4:
        thread = None
        if '--thread' in args:
            thread = int(args[args.index('--thread') + 1])
        fail(args[1], args[2], ' '.join(args[3:]), thread)
    elif args[0] == 'list':
        list_markers()
    else:
        print('Pakai: mark.py create|delete|fail|list ...', file=sys.stderr)
        raise SystemExit(2)


if __name__ == '__main__':
    main()
