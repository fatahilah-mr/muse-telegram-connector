#!/usr/bin/env python3
"""Kunci antar-run cron bot @muse01fthbot — cegah dua run jalan bareng dan
jawab pesan yang sama dua kali (pernah kejadian: /help kejawab 2x).

Acquire ATOMIK: file kunci dibuat dengan O_CREAT|O_EXCL, jadi dua run yang
start di detik yang sama tidak bisa sama-sama lolos — versi lama cek-dulu
(os.path.exists) baru bikin file, ada celah race di antaranya.
Pakai: python3 lock.py acquire  -> cetak LOCKED (ada run lain) atau OK
       python3 lock.py release  -> hapus kunci
Kunci kedaluwarsa sendiri setelah 300 detik (kalau run sebelumnya crash
dan tidak sempat release).
"""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOCK = os.path.join(HERE, 'run.lock')
MAX_AGE = 300

if sys.argv[1] == 'acquire':
    for _ in range(2):
        try:
            fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, 'w') as f:
                f.write(str(int(time.time())))
            print('OK')
            raise SystemExit(0)
        except FileExistsError:
            age = time.time() - os.path.getmtime(LOCK)
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
    try:
        os.remove(LOCK)
    except FileNotFoundError:
        pass
    print('OK')
else:
    print('Pakai: lock.py acquire | release', file=sys.stderr)
    raise SystemExit(2)
