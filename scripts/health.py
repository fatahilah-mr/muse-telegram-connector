#!/usr/bin/env python3
"""Cek kesehatan bot — dipanggil cron tiap jam (muse-tele-health-1h).
Tidak mengirim apa pun sendiri; cuma mencetak JSON. Cron yang membaca
output ini dan melapor ke chat kalau status-nya "alert".
Yang dicek:
  - heartbeat.txt: terakhir kali poll/gate sukses. Alert kalau > 15 menit
    (dispatcher 1 menit seharusnya memperbaruinya tiap run).
  - state.json: bisa dibaca dan punya allowlist + offset.
  - run.lock: ada dan berumur > 300 detik (dispatcher macet / crash).
  - marker gagal / marker nyangkut: dilaporkan sebagai info (bukan alert).
Pakai: python3 health.py
Output: {"status": "ok"|"alert", "checks": {...}}
Selalu keluar 0 — yang memutuskan melapor adalah cron, bukan skrip ini.
"""
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HEARTBEAT = os.path.join(HERE, 'heartbeat.txt')
STATE = os.path.join(HERE, 'state.json')
LOCK = os.path.join(HERE, 'run.lock')
PROC_DIR = os.path.join(HERE, 'processing')

HEARTBEAT_MAX_AGE = 900  # detik — 15 menit


def main():
    now = int(time.time())
    checks = {}
    problems = []

    try:
        with open(HEARTBEAT) as f:
            last = int(f.read().strip())
        age = now - last
        checks['heartbeat_age_detik'] = age
        if age > HEARTBEAT_MAX_AGE:
            problems.append('tidak ada poll sukses selama %d detik' % age)
    except Exception:
        checks['heartbeat_age_detik'] = None
        problems.append('heartbeat.txt tidak ada / tidak bisa dibaca '
                        '(dispatcher belum pernah sukses?)')

    try:
        with open(STATE) as f:
            state = json.load(f)
        checks['offset'] = state.get('offset')
        checks['allowed_count'] = len(state.get('allowed', []))
        if not isinstance(state.get('allowed'), list) \
                or not state.get('allowed'):
            problems.append('allowlist kosong / tidak valid')
    except Exception as e:
        checks['offset'] = None
        problems.append('state.json tidak bisa dibaca (%s)' % e)

    try:
        lock_age = now - int(os.path.getmtime(LOCK))
        checks['lock_age_detik'] = lock_age
        if lock_age > 300:
            problems.append('run.lock berumur %d detik (dispatcher mungkin '
                            'macet)' % lock_age)
    except FileNotFoundError:
        checks['lock_age_detik'] = None
    except Exception:
        checks['lock_age_detik'] = None

    stuck = failed = 0
    try:
        for name in os.listdir(PROC_DIR):
            if name.endswith('.failed.json'):
                failed += 1
            elif name.endswith('.json'):
                stuck += 1
    except Exception:
        pass
    checks['marker_nyangkut'] = stuck
    checks['marker_gagal'] = failed

    status = 'alert' if problems else 'ok'
    print(json.dumps({'status': status, 'checks': checks,
                      'problems': problems}, ensure_ascii=False))


if __name__ == '__main__':
    main()
