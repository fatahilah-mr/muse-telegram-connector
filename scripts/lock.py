#!/usr/bin/env python3
"""Kunci antar-run cron bot — cegah dua run jalan bareng dan
jawab pesan yang sama dua kali (pernah kejadian: /help kejawab 2x).

Acquire ATOMIK: file kunci dibuat dengan O_CREAT|O_EXCL, jadi dua run yang
start di detik yang sama tidak bisa sama-sama lolos — versi lama cek-dulu
(os.path.exists) baru bikin file, ada celah race di antaranya.

Release BERTANDA (token): acquire mencetak token acak sekali pakai;
release HANYA menghapus kunci kalau tokennya cocok. Jadi run yang
lock-nya sudah kedaluwarsa dan diganti run lain tidak bisa menghapus
kunci milik run lain itu.
Pakai: python3 lock.py acquire  -> cetak "OK <token>" atau "LOCKED"
       python3 lock.py release <token>  -> cetak OK / NOT-MINE
Kunci kedaluwarsa sendiri setelah 300 detik (kalau run sebelumnya crash
dan tidak sempat release).
"""
import os
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
LOCK = os.path.join(HERE, 'run.lock')
MAX_AGE = 300

if len(sys.argv) < 2:
    print('Pakai: lock.py acquire | release <token>', file=sys.stderr)
    raise SystemExit(2)

if sys.argv[1] == 'acquire':
    for _ in range(2):
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            token = uuid.uuid4().hex
            with os.fdopen(fd, 'w') as f:
                f.write('%s:%d' % (token, int(time.time())))
            print('OK %s' % token)
            raise SystemExit(0)
        except FileExistsError:
            try:
                age = time.time() - os.path.getmtime(LOCK)
            except FileNotFoundError:
                # Kunci dihapus run lain di antara cek dan baca — coba
                # acquire lagi (ditemukan analisis ulang 25 Nov 2026).
                continue
            if age < MAX_AGE:
                print('LOCKED')
                raise SystemExit(0)
            # Kunci kedaluwarsa: hapus lalu coba lagi sekali.
            # Kalau run lain menghapus/membuat duluan, O_EXCL di
            # percobaan berikut yang menentukan pemenang.
            try:
                os.remove(LOCK)
            except FileNotFoundError:
                pass
    print('LOCKED')
    raise SystemExit(0)
elif sys.argv[1] == 'release':
    if len(sys.argv) < 3 or not sys.argv[2]:
        # Tanpa token, JANGAN hapus apa pun — bisa jadi kunci milik run lain.
        print('release butuh token dari acquire', file=sys.stderr)
        raise SystemExit(2)
    token = sys.argv[2]
    try:
        with open(LOCK) as f:
            stored = f.read().strip().split(':')[0]
    except FileNotFoundError:
        print('OK')  # sudah tidak ada
        raise SystemExit(0)
    except Exception:
        print('OK')
        raise SystemExit(0)
    if stored != token:
        print('NOT-MINE')  # kunci milik run lain — jangan dihapus
        raise SystemExit(0)
    try:
        os.remove(LOCK)
    except FileNotFoundError:
        pass
    print('OK')
else:
    print('Pakai: lock.py acquire | release <token>', file=sys.stderr)
    raise SystemExit(2)
