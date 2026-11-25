#!/usr/bin/env python3
"""Dispatcher mekanis bot — ganti langkah-langkah manual di cron-body.md
lama (lock, poll, tulis offset) yang rawan terlewat karena cuma prosa.
Agent (cron) hanya: jalankan plan, spawn subagent dari daftarnya,
lalu jalankan commit. Semua yang krusial (lock, offset, watchdog,
heartbeat) dikerjakan skrip ini.
Pakai:
  python3 dispatch.py plan
    -> kunci, poll, gate, tulis plan.json, cetak rencana (JSON).
       status "locked" = ada run lain, berhenti. "poll_failed"/"gate_failed"
       = masalah, laporkan kalau alert=true. "plan" = daftar update
       yang harus di-spawn + eskalasi watchdog yang harus dilaporkan.
  python3 dispatch.py commit --spawned <id1,id2,...>
    -> majukan offset (hanya melewati update yang berhasil di-spawn
       berurutan dari awal; kalau semua ter-spawn, klaim sampai
       max_update_id), jalankan watchdog, perbarui heartbeat, lepas kunci.
       --spawned boleh kosong (tidak ada yang berhasil di-spawn).
Rencana (plan.json) memuat token lock — JANGAN dicetak ke chat.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOCK = os.path.join(HERE, 'lock.py')
POLL = os.path.join(HERE, 'poll.py')
GATE = os.path.join(HERE, 'gate.py')
WATCHDOG = os.path.join(HERE, 'stuck_watchdog.py')
STATE = os.path.join(HERE, 'state.json')
PLAN = os.path.join(HERE, 'plan.json')
HEARTBEAT = os.path.join(HERE, 'heartbeat.txt')
POLL_FAIL = os.path.join(HERE, 'poll_failures.json')
PROC_DIR = os.path.join(HERE, 'processing')

ALERT_COOLDOWN = 3600  # detik — laporan gagal poll maks 1x/jam


def _run(cmd, inp=None, timeout=180):
    try:
        return subprocess.run(cmd, input=inp, capture_output=True,
                              text=True, timeout=timeout)
    except Exception as e:
        return None


def _atomic_write(path, data):
    tmp = path + '.tmp.%d' % os.getpid()
    with open(tmp, 'w') as f:
        json.dump(data, f)
    os.replace(tmp, path)


def _load_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def _heartbeat():
    try:
        with open(HEARTBEAT, 'w') as f:
            f.write(str(int(time.time())))
    except Exception:
        pass


def _watchdog():
    _run([sys.executable, WATCHDOG], timeout=240)


def _escalations():
    out = []
    if os.path.isdir(PROC_DIR):
        for name in sorted(os.listdir(PROC_DIR)):
            if name.endswith('.escalated'):
                data = _load_json(os.path.join(PROC_DIR, name), {})
                if data:
                    out.append(data)
    return out


def _clear_escalations():
    if os.path.isdir(PROC_DIR):
        for name in os.listdir(PROC_DIR):
            if name.endswith('.escalated'):
                try:
                    os.remove(os.path.join(PROC_DIR, name))
                except Exception:
                    pass


def cmd_plan():
    r = _run([sys.executable, LOCK, 'acquire'], timeout=30)
    if r is None or not r.stdout.strip().startswith('OK '):
        print(json.dumps({'status': 'locked'}))
        return 0
    token = r.stdout.strip().split(' ', 1)[1]

    def release():
        _run([sys.executable, LOCK, 'release', token], timeout=30)

    r = _run([sys.executable, POLL], timeout=120)
    if r is None or r.returncode != 0:
        err = (r.stdout.strip() if r else '') or 'poll.py tidak jalan'
        now = int(time.time())
        pf = _load_json(POLL_FAIL, {}) or {}
        count = int(pf.get('count', 0)) + 1
        first_at = pf.get('first_at', now)
        last_alert = pf.get('last_alert_at')
        alert = count == 1 or last_alert is None or \
            now - int(last_alert) >= ALERT_COOLDOWN
        if alert:
            pf['last_alert_at'] = now
        pf.update({'count': count, 'first_at': first_at})
        _atomic_write(POLL_FAIL, pf)
        release()
        _watchdog()
        print(json.dumps({'status': 'poll_failed', 'alert': alert,
                          'failures': count, 'error': err[:500]},
                         ensure_ascii=False))
        return 0

    try:
        os.remove(POLL_FAIL)
    except FileNotFoundError:
        pass

    r2 = _run([sys.executable, GATE], inp=r.stdout, timeout=240)
    if r2 is None or r2.returncode != 0:
        err = ((r2.stderr or r2.stdout) if r2 else '').strip() or \
            'gate.py tidak jalan'
        release()
        _watchdog()
        print(json.dumps({'status': 'gate_failed', 'alert': True,
                          'error': err[:500]}, ensure_ascii=False))
        return 0

    try:
        gated = json.loads(r2.stdout)
    except Exception as e:
        release()
        _watchdog()
        print(json.dumps({'status': 'gate_failed', 'alert': True,
                          'error': 'output gate.py bukan JSON: %s' % e},
                         ensure_ascii=False))
        return 0

    plan = {'token': token,
            'updates': gated.get('updates', []),
            'max_update_id': gated.get('max_update_id'),
            'escalations': _escalations(),
            'created_at': int(time.time())}
    _atomic_write(PLAN, plan)
    print(json.dumps({'status': 'plan', 'updates': plan['updates'],
                      'max_update_id': plan['max_update_id'],
                      'escalations': plan['escalations']},
                     ensure_ascii=False))
    return 0


def cmd_commit(spawned_csv):
    plan = _load_json(PLAN)
    if not plan:
        print(json.dumps({'status': 'commit_failed',
                          'error': 'plan.json tidak ada — jalankan plan dulu'}))
        return 1
    token = plan.get('token', '')
    updates = plan.get('updates', [])
    max_uid = plan.get('max_update_id')

    spawned = set()
    if spawned_csv:
        for part in spawned_csv.split(','):
            part = part.strip()
            if part:
                try:
                    spawned.add(int(part))
                except ValueError:
                    pass

    # Offset maju melewati update yang berhasil di-spawn BERURUTAN dari
    # awal; kalau semuanya ter-spawn, klaim sampai max_update_id.
    new_offset = None
    contiguous = []
    for u in updates:
        if u.get('update_id') in spawned:
            contiguous.append(u['update_id'])
        else:
            break
    if updates and len(contiguous) == len(updates) and max_uid is not None:
        new_offset = int(max_uid) + 1
    elif contiguous:
        new_offset = contiguous[-1] + 1

    def release():
        _run([sys.executable, LOCK, 'release', token], timeout=30)

    try:
        state = _load_json(STATE)
        if state is None:
            raise RuntimeError('state.json tidak bisa dibaca')
        if new_offset is not None:
            state['offset'] = new_offset
            _atomic_write(STATE, state)
    except Exception as e:
        release()
        print(json.dumps({'status': 'commit_failed', 'error': str(e)[:500]},
                         ensure_ascii=False))
        return 1

    _watchdog()
    _heartbeat()
    _clear_escalations()
    release()
    try:
        os.remove(PLAN)
    except FileNotFoundError:
        pass
    print(json.dumps({'status': 'committed', 'offset': new_offset,
                      'spawned': len(spawned)}, ensure_ascii=False))
    return 0


def main():
    args = sys.argv[1:]
    if not args or args[0] not in ('plan', 'commit'):
        print('Pakai: dispatch.py plan | commit --spawned <id1,id2,...>',
              file=sys.stderr)
        raise SystemExit(2)
    if args[0] == 'plan':
        raise SystemExit(cmd_plan())
    spawned = ''
    if '--spawned' in args:
        spawned = args[args.index('--spawned') + 1]
    raise SystemExit(cmd_commit(spawned))


if __name__ == '__main__':
    main()
