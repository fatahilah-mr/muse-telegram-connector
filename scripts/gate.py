#!/usr/bin/env python3
"""Gerbang dispatcher: saring update hasil poll.py SEBELUM di-spawn.
  - Allowlist: from_id yang tidak di-allowlist DITOLAK — di chat privat
    dibalas penolakan (maks 1x per 10 menit per pengirim, biar tidak
    di-spam), di grup didiamkan saja (penolakan publik cuma bocor +
    bikin ribut). Semua penolakan dicatat di rejections.log.
  - Rate limit: maks 10 pesan per user per 5 menit. Lebihnya di-drop;
    di chat privat dikirimi 1x pemberitahuan "sabar" per 5 menit.
  - Media tanpa teks: hanya photo/video/document/voice/audio/video_note
    yang diteruskan (ditangani cabang media di process-one.md);
    sticker/animation/contact/location/poll dilewati diam-diam.
  - Tiap update yang lolos ditempeli riwayat chat (history.py) sebagai
    konteks percakapan.
  - Tiap run yang sukses memperbarui heartbeat.txt (dipakai health.py).
Pakai: python3 poll.py | python3 gate.py
Output: objek poll yang sama, dengan "updates" sudah tersaring.
Keluar 1 kalau state.json tidak bisa dibaca (fail closed — kalau tidak
tahu siapa yang boleh, jangan spawn apa pun).
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SEND = os.path.join(HERE, 'send.py')
STATE = os.path.join(HERE, 'state.json')
RATELIMIT = os.path.join(HERE, 'ratelimit.json')
RUNS_LOG = os.path.join(HERE, 'runs.log')
REJECT_LOG = os.path.join(HERE, 'rejections.log')
HEARTBEAT = os.path.join(HERE, 'heartbeat.txt')

from history import get_history

RATE_WINDOW = 300    # detik — jendela rate limit
RATE_MAX = 10        # pesan per user per jendela
REJECT_COOLDOWN = 600   # detik — penolakan ke pengirim yang sama
SLOWDOWN_COOLDOWN = 300
SEND_TIMEOUT = 40
MAX_SENDS_PER_RUN = 5

SPAWNABLE_MEDIA = ('photo', 'video', 'document', 'voice', 'audio',
                    'video_note')
REJECT_TEXT = 'Maaf, bot ini privat — cuma buat owner-nya aja.'
SLOWDOWN_TEXT = 'Sabar bro, kebanyakan pesan — tunggu sebentar ya.'


def _load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def _atomic_write(path, data):
    tmp = path + '.tmp.%d' % os.getpid()
    with open(tmp, 'w') as f:
        json.dump(data, f)
    os.replace(tmp, path)


def _log(path, obj):
    try:
        with open(path, 'a') as f:
            f.write(json.dumps(obj, ensure_ascii=False) + '\n')
    except Exception:
        pass


def _rotate_runs_log():
    try:
        if os.path.getsize(RUNS_LOG) > 200 * 1024:
            with open(RUNS_LOG) as f:
                lines = f.readlines()
            with open(RUNS_LOG, 'w') as f:
                f.writelines(lines[-1000:])
    except Exception:
        pass


class Sender:
    """Kirim pesan singkat via send.py, dibatasi jumlahnya per run."""

    def __init__(self):
        self.sent = 0

    def send(self, chat_id, text, thread_id=None):
        if self.sent >= MAX_SENDS_PER_RUN:
            return False
        cmd = [sys.executable, SEND, str(chat_id)]
        if thread_id:
            cmd += ['--thread', str(thread_id)]
        try:
            r = subprocess.run(cmd, input=text, capture_output=True,
                               text=True, timeout=SEND_TIMEOUT)
            self.sent += 1
            return r.returncode == 0 and '"ok": true' in r.stdout
        except Exception:
            return False


def main():
    try:
        data = json.load(sys.stdin)
    except Exception as e:
        print('gate: input bukan JSON: %s' % e, file=sys.stderr)
        raise SystemExit(1)
    updates = data.get('updates')
    if not isinstance(updates, list):
        print('gate: input tidak punya "updates"', file=sys.stderr)
        raise SystemExit(1)

    try:
        with open(STATE) as f:
            state = json.load(f)
        allowed = state.get('allowed', [])
    except Exception as e:
        print('gate: state.json tidak bisa dibaca (%s) — fail closed'
              % e, file=sys.stderr)
        raise SystemExit(1)
    if not isinstance(allowed, list):
        allowed = []

    now = int(time.time())
    rl = _load_json(RATELIMIT, {})
    users = rl.get('users', {})
    reject_at = rl.get('reject_at', {})
    slowdown_at = rl.get('slowdown_at', {})
    for uid in list(users):
        users[uid] = [t for t in users[uid] if now - t < RATE_WINDOW]

    sender = Sender()
    kept = []
    n_rejected = 0
    n_limited = 0
    for u in updates:
        from_id = u.get('from_id')
        chat_id = u.get('chat_id')
        chat_type = u.get('chat_type')
        text = (u.get('text') or '').strip()
        media = u.get('media')

        if from_id not in allowed:
            n_rejected += 1
            _log(REJECT_LOG, {'ts': now, 'chat_id': chat_id,
                              'chat_type': chat_type, 'from_id': from_id,
                              'username': u.get('from_username'),
                              'message_id': u.get('message_id')})
            # Penolakan hanya di chat privat + cooldown, biar tidak spam.
            if chat_type == 'private':
                last = reject_at.get(str(from_id), 0)
                if now - last >= REJECT_COOLDOWN:
                    if sender.send(chat_id, REJECT_TEXT,
                                   u.get('thread_id')):
                        reject_at[str(from_id)] = now
            continue

        if not text and media not in SPAWNABLE_MEDIA:
            continue  # stiker/dll: lewati diam-diam (offset tetap maju)

        stamps = users.get(str(from_id), [])
        if len(stamps) >= RATE_MAX:
            n_limited += 1
            _log(RUNS_LOG, {'ts': now, 'event': 'rate_limited',
                            'from_id': from_id, 'chat_id': chat_id})
            if chat_type == 'private':
                last = slowdown_at.get(str(from_id), 0)
                if now - last >= SLOWDOWN_COOLDOWN:
                    if sender.send(chat_id, SLOWDOWN_TEXT,
                                   u.get('thread_id')):
                        slowdown_at[str(from_id)] = now
            continue
        stamps.append(now)
        users[str(from_id)] = stamps

        u['history'] = get_history(chat_id, limit=12)
        kept.append(u)

    _atomic_write(RATELIMIT, {'users': users, 'reject_at': reject_at,
                              'slowdown_at': slowdown_at})
    try:
        with open(HEARTBEAT, 'w') as f:
            f.write(str(now))
    except Exception:
        pass
    _log(RUNS_LOG, {'ts': now, 'event': 'gate', 'seen': len(updates),
                    'kept': len(kept), 'rejected': n_rejected,
                    'rate_limited': n_limited})
    _rotate_runs_log()
    data['updates'] = kept
    print(json.dumps(data, ensure_ascii=False))


if __name__ == '__main__':
    main()
