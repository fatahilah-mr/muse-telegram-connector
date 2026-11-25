#!/usr/bin/env python3
"""Kelola allowlist bot (state.json) dari Telegram (/allow, /unallow)
atau shell. Tulis atomic (temp + rename) supaya poll.py yang membaca
bersamaan tidak dapat file setengah tertulis.
Pakai:
  python3 allow.py add <user_id>
  python3 allow.py remove <user_id>
  python3 allow.py list
Aturan: ID terakhir tidak boleh dihapus (bot tidak boleh tanpa owner).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, 'state.json')


def _load():
    with open(STATE) as f:
        data = json.load(f)
    if not isinstance(data.get('allowed'), list):
        data['allowed'] = []
    return data


def _save(data):
    tmp = STATE + '.tmp.%d' % os.getpid()
    with open(tmp, 'w') as f:
        json.dump(data, f)
    os.replace(tmp, STATE)


def main():
    args = sys.argv[1:]
    if len(args) < 1 or args[0] not in ('add', 'remove', 'list'):
        print('Pakai: allow.py add|remove <user_id> | list', file=sys.stderr)
        raise SystemExit(2)
    if args[0] == 'list':
        print(json.dumps({'allowed': _load().get('allowed', [])}))
        return
    if len(args) < 2:
        print('Pakai: allow.py add|remove <user_id>', file=sys.stderr)
        raise SystemExit(2)
    try:
        uid = int(args[1])
    except ValueError:
        print(json.dumps({'ok': False, 'error': 'user_id harus angka'}))
        raise SystemExit(1)
    data = _load()
    allowed = data.get('allowed', [])
    if args[0] == 'add':
        if uid not in allowed:
            allowed.append(uid)
            data['allowed'] = allowed
            _save(data)
        print(json.dumps({'ok': True, 'allowed': allowed}))
    else:
        if uid not in allowed:
            print(json.dumps({'ok': False, 'error': 'ID tidak ada di allowlist'}))
            raise SystemExit(1)
        if len(allowed) <= 1:
            print(json.dumps({'ok': False,
                              'error': 'tidak bisa hapus ID terakhir'}))
            raise SystemExit(1)
        allowed.remove(uid)
        data['allowed'] = allowed
        _save(data)
        print(json.dumps({'ok': True, 'allowed': allowed}))


if __name__ == '__main__':
    main()
