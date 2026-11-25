#!/usr/bin/env python3
"""Smoke test kit bot Telegram Muse AI — stdlib saja, TANPA jaringan
dan TANPA vault (semua yang butuh Telegram/vault diganti stub).
Jalankan dari folder kit:  python3 tests/test_kit.py
Yang dites:
  - lock.py: acquire / LOCKED / release bertanda token / NOT-MINE
  - send.py: split_message (pendek, panjang, satu kata raksasa)
  - gate.py: allowlist, penolakan privat (cooldown), diam di grup,
    rate limit + pemberitahuan "sabar", riwayat ditempel,
    stiker lolos, entri ratelimit basi dibersihkan
  - history.py: append/get, batas 20 entri, potong teks,
    lock basi dihapus (append tidak lemot)
  - mark.py: create/delete/fail, delete juga hapus flag .escalated
  - dispatch.py: commit offset — semua ter-spawn, sebagian, kosong
    tapi max_update_id ada (offset tetap maju), kosong total (tetap)
  - allow.py: add/remove/list, tolak hapus ID terakhir
  - vault_token.py: config.json rusak = gagal keras; tanpa config =
    fallback ke default (tanpa memanggil vault)
poll.py / dispatch.py / fetch.py butuh jaringan + vault, jadi TIDAK
di-unit-test di sini — ditutup tes end-to-end live via bot.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(KIT, 'scripts')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_py(path, args=None, inp=None, cwd=None, timeout=60):
    return subprocess.run(
        [sys.executable, path] + (args or []), input=inp,
        capture_output=True, text=True, cwd=cwd, timeout=timeout)


class LockTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.lock = os.path.join(self.d, 'lock.py')
        shutil.copy(os.path.join(SCRIPTS, 'lock.py'), self.lock)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_acquire_release_token(self):
        r = run_py(self.lock, ['acquire'], cwd=self.d)
        self.assertTrue(r.stdout.startswith('OK '), r.stdout)
        token = r.stdout.strip().split(' ', 1)[1]
        r2 = run_py(self.lock, ['acquire'], cwd=self.d)
        self.assertEqual(r2.stdout.strip(), 'LOCKED')
        r3 = run_py(self.lock, ['release', 'token-salah'], cwd=self.d)
        self.assertEqual(r3.stdout.strip(), 'NOT-MINE')
        self.assertTrue(os.path.exists(os.path.join(self.d, 'run.lock')))
        r4 = run_py(self.lock, ['release'], cwd=self.d)
        self.assertEqual(r4.returncode, 2)  # tanpa token: tolak hapus
        self.assertTrue(os.path.exists(os.path.join(self.d, 'run.lock')))
        r5 = run_py(self.lock, ['release', token], cwd=self.d)
        self.assertEqual(r5.stdout.strip(), 'OK')
        self.assertFalse(os.path.exists(os.path.join(self.d, 'run.lock')))


class SendSplitTest(unittest.TestCase):
    def setUp(self):
        # Import send.py TANPA menjalankan main() — tapi import-nya
        # memanggil get_token() (vault). Ganti dulu dengan stub modul.
        self.stub_dir = tempfile.mkdtemp()
        with open(os.path.join(self.stub_dir, 'vault_token.py'), 'w') as f:
            f.write('def get_token():\n    return "hsurr:test"\n')
        sys.path.insert(0, SCRIPTS)
        sys.path.insert(0, self.stub_dir)  # stub vault_token harus menang
        import send as send_mod
        self.send = send_mod

    def tearDown(self):
        sys.path.remove(self.stub_dir)
        sys.path.remove(SCRIPTS)
        sys.modules.pop('send', None)
        sys.modules.pop('vault_token', None)
        shutil.rmtree(self.stub_dir, ignore_errors=True)

    def test_pendek_tidak_dipotong(self):
        self.assertEqual(self.send.split_message('halo'), ['halo'])

    def test_panjang_dipotong_dan_tidak_lebih_limit(self):
        text = ('Paragraf satu. ' * 200 + '\n\n' +
                'Paragraf dua. ' * 200 + '\n\n' +
                'Paragraf tiga. ' * 200)
        chunks = self.send.split_message(text)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c), 4000)
            self.assertTrue(c.strip())

    def test_satu_kata_raksasa_dipotong_keras(self):
        chunks = self.send.split_message('x' * 9000)
        self.assertEqual(len(chunks), 3)
        self.assertEqual([len(c) for c in chunks], [4000, 4000, 1000])


class GateTest(unittest.TestCase):
    STUB_SEND = (
        '#!/usr/bin/env python3\n'
        'import json, sys\n'
        'log = sys.argv[0].rsplit("/", 1)[0] + "/send-calls.log"\n'
        'text = sys.stdin.read()\n'
        'with open(log, "a") as f:\n'
        '    f.write(json.dumps({"args": sys.argv[1:], "text": text}) + "\\n")\n'
        'print(json.dumps({"ok": True, "message_id": 1}))\n')

    def setUp(self):
        self.d = tempfile.mkdtemp()
        for name in ('gate.py', 'history.py'):
            shutil.copy(os.path.join(SCRIPTS, name),
                        os.path.join(self.d, name))
        with open(os.path.join(self.d, 'send.py'), 'w') as f:
            f.write(self.STUB_SEND)
        with open(os.path.join(self.d, 'state.json'), 'w') as f:
            json.dump({'allowed': [111], 'offset': 0}, f)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _gate(self, updates):
        payload = json.dumps({'updates': updates, 'max_update_id': 99})
        r = run_py(os.path.join(self.d, 'gate.py'), inp=payload, cwd=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def _send_calls(self):
        path = os.path.join(self.d, 'send-calls.log')
        if not os.path.exists(path):
            return []
        with open(path) as f:
            return [json.loads(line) for line in f if line.strip()]

    def _upd(self, uid, from_id, chat_id=1, chat_type='private', text='hi',
             media=None):
        return {'update_id': uid, 'message_id': uid, 'chat_id': chat_id,
                'chat_type': chat_type, 'thread_id': None,
                'from_id': from_id, 'from_username': 'u',
                'from_name': 'U', 'text': text, 'media': media,
                'file_id': None, 'file_size': None, 'date': 0}

    def test_allowed_lolos_dan_dapat_history(self):
        out = self._gate([self._upd(1, 111)])
        self.assertEqual(len(out['updates']), 1)
        self.assertIn('history', out['updates'][0])
        self.assertEqual(out['max_update_id'], 99)

    def test_nonallowed_privat_ditolak_dan_dicatat(self):
        out = self._gate([self._upd(1, 999)])
        self.assertEqual(out['updates'], [])
        calls = self._send_calls()
        self.assertEqual(len(calls), 1)
        self.assertIn('privat', calls[0]['text'])
        with open(os.path.join(self.d, 'rejections.log')) as f:
            self.assertIn('999', f.read())

    def test_nonallowed_grup_didiamkan(self):
        out = self._gate([self._upd(1, 999, chat_id=-100, chat_type='group')])
        self.assertEqual(out['updates'], [])
        self.assertEqual(self._send_calls(), [])

    def test_rate_limit_10_per_5_menit(self):
        ups = [self._upd(i, 111) for i in range(1, 13)]
        out = self._gate(ups)
        self.assertEqual(len(out['updates']), 10)
        calls = self._send_calls()
        self.assertEqual(len(calls), 1)  # 1x pemberitahuan "sabar"
        self.assertIn('Sabar', calls[0]['text'])

    def test_media_tanpa_teks_yang_bisa_diproses_lolos(self):
        out = self._gate([self._upd(1, 111, text='', media='voice')])
        self.assertEqual(len(out['updates']), 1)
        # Stiker lolos sejak 25 Nov 2026: file .webp kiriman user diubah
        # Telegram jadi stiker (caption ikut hilang) — harus tetap dijawab.
        out2 = self._gate([self._upd(2, 111, text='', media='sticker')])
        self.assertEqual(len(out2['updates']), 1)
        out3 = self._gate([self._upd(3, 111, text='', media='animation')])
        self.assertEqual(out3['updates'], [])

    def test_entri_ratelimit_basi_dibersihkan(self):
        # Entri user kosong + catatan cooldown basi tidak boleh menumpuk
        # selamanya di ratelimit.json (ditemukan analisis ulang 25 Nov).
        import time as _time
        now = int(_time.time())
        with open(os.path.join(self.d, 'ratelimit.json'), 'w') as f:
            json.dump({'users': {'555': [now - 9999]},
                       'reject_at': {'555': now - 9999},
                       'slowdown_at': {'555': now - 9999}}, f)
        self._gate([self._upd(1, 111)])
        with open(os.path.join(self.d, 'ratelimit.json')) as f:
            rl = json.load(f)
        self.assertNotIn('555', rl['users'])
        self.assertNotIn('555', rl['reject_at'])
        self.assertNotIn('555', rl['slowdown_at'])
        self.assertIn('111', rl['users'])  # entri aktif tetap ada


class HistoryTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.hist = os.path.join(self.d, 'history.py')
        shutil.copy(os.path.join(SCRIPTS, 'history.py'), self.hist)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_append_get_dan_batas(self):
        for i in range(25):
            r = run_py(self.hist, ['append', '7', 'user'],
                       inp='pesan %d' % i, cwd=self.d)
            self.assertEqual(r.returncode, 0, r.stderr)
        r = run_py(self.hist, ['get', '7', '--limit', '20'], cwd=self.d)
        entries = json.loads(r.stdout)
        self.assertEqual(len(entries), 20)  # dipangkas ke 20 terakhir
        self.assertEqual(entries[0]['text'], 'pesan 5')
        self.assertEqual(entries[-1]['text'], 'pesan 24')


class MarkTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.mark = os.path.join(self.d, 'mark.py')
        shutil.copy(os.path.join(SCRIPTS, 'mark.py'), self.mark)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_create_delete_fail(self):
        r = run_py(self.mark, ['create', '7', '42'], cwd=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        path = os.path.join(self.d, 'processing', '7_42.json')
        self.assertTrue(os.path.exists(path))
        r = run_py(self.mark, ['fail', '7', '42', 'kirim gagal'],
                   cwd=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(path))
        self.assertTrue(os.path.exists(
            os.path.join(self.d, 'processing', '7_42.failed.json')))
        r = run_py(self.mark, ['delete', '7', '42'], cwd=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(
            os.path.join(self.d, 'processing', '7_42.failed.json')))

    def test_delete_juga_hapus_escalated(self):
        # Flag .escalated harus ikut terhapus saat marker dihapus
        # (ditemukan analisis ulang 25 Nov 2026).
        run_py(self.mark, ['create', '7', '42'], cwd=self.d)
        flag = os.path.join(self.d, 'processing', '7_42.json.escalated')
        with open(flag, 'w') as f:
            f.write('1')
        r = run_py(self.mark, ['delete', '7', '42'], cwd=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(os.path.exists(flag))
        self.assertFalse(os.path.exists(
            os.path.join(self.d, 'processing', '7_42.json')))


class DispatchOffsetTest(unittest.TestCase):
    """dispatch.py commit: offset harus maju juga saat tidak ada update
    yang perlu di-spawn tapi max_update_id ada (mis. update non-message
    saja) — kalau tidak, run berikutnya mem-poll ulang update yang sama
    terus (ditemukan analisis ulang 25 Nov 2026)."""

    def setUp(self):
        self.d = tempfile.mkdtemp()
        for name in ('dispatch.py', 'lock.py'):
            shutil.copy(os.path.join(SCRIPTS, name),
                        os.path.join(self.d, name))
        # Stub watchdog (no-op) + stub poll/gate (tidak dipakai commit).
        for name in ('stuck_watchdog.py',):
            with open(os.path.join(self.d, name), 'w') as f:
                f.write('import sys; sys.exit(0)\n')
        os.makedirs(os.path.join(self.d, 'processing'), exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _commit(self, plan, offset_awal=100):
        with open(os.path.join(self.d, 'plan.json'), 'w') as f:
            json.dump(plan, f)
        with open(os.path.join(self.d, 'state.json'), 'w') as f:
            json.dump({'allowed': [111], 'offset': offset_awal}, f)
        spawned = ','.join(str(u['update_id'])
                           for u in plan.get('updates', []))
        r = run_py(os.path.join(self.d, 'dispatch.py'),
                   ['commit', '--spawned', spawned], cwd=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(self.d, 'state.json')) as f:
            return json.load(f)['offset']

    def test_updates_kosong_tapi_max_uid_ada_offset_maju(self):
        plan = {'token': 't', 'updates': [], 'max_update_id': 105,
                'escalations': []}
        self.assertEqual(self._commit(plan), 106)

    def test_semua_ter_spawn_offset_ke_max_uid(self):
        plan = {'token': 't',
                'updates': [{'update_id': 101}, {'update_id': 102}],
                'max_update_id': 102, 'escalations': []}
        self.assertEqual(self._commit(plan), 103)

    def test_tidak_ada_update_sama_sekali_offset_tetap(self):
        plan = {'token': 't', 'updates': [], 'max_update_id': None,
                'escalations': []}
        self.assertEqual(self._commit(plan), 100)


class HistoryStaleLockTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.hist = os.path.join(self.d, 'history.py')
        shutil.copy(os.path.join(SCRIPTS, 'history.py'), self.hist)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_lock_basi_dihapus_append_tidak_lemot(self):
        # File .lock berumur > 30 detik (pemilik crash) harus dibuang
        # supaya append tidak menunggu 5 detik tiap kali (ditemukan
        # analisis ulang 25 Nov 2026).
        import time as _time
        hist_dir = os.path.join(self.d, 'history')
        os.makedirs(hist_dir, exist_ok=True)
        lock = os.path.join(hist_dir, '7.json.lock')
        with open(lock, 'w') as f:
            f.write('')
        old = _time.time() - 60
        os.utime(lock, (old, old))
        t0 = _time.time()
        r = run_py(self.hist, ['append', '7', 'user'],
                   inp='tes lock basi', cwd=self.d)
        dt = _time.time() - t0
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertLess(dt, 4.0, 'append menunggu lock basi terlalu lama')
        r = run_py(self.hist, ['get', '7'], cwd=self.d)
        self.assertEqual(json.loads(r.stdout)[0]['text'], 'tes lock basi')


class AllowTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.allow = os.path.join(self.d, 'allow.py')
        shutil.copy(os.path.join(SCRIPTS, 'allow.py'), self.allow)
        with open(os.path.join(self.d, 'state.json'), 'w') as f:
            json.dump({'allowed': [111], 'offset': 5}, f)

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_add_remove_dan_tolak_hapus_terakhir(self):
        r = run_py(self.allow, ['add', '222'], cwd=self.d)
        self.assertEqual(json.loads(r.stdout)['allowed'], [111, 222])
        with open(os.path.join(self.d, 'state.json')) as f:
            self.assertEqual(json.load(f)['offset'], 5)  # offset utuh
        r = run_py(self.allow, ['remove', '222'], cwd=self.d)
        self.assertEqual(r.returncode, 0)
        r = run_py(self.allow, ['remove', '111'], cwd=self.d)
        self.assertEqual(r.returncode, 1)  # ID terakhir tidak boleh hapus
        with open(os.path.join(self.d, 'state.json')) as f:
            self.assertEqual(json.load(f)['allowed'], [111])


class VaultConfigTest(unittest.TestCase):
    def test_config_rusak_gagal_keras(self):
        d = tempfile.mkdtemp()
        try:
            shutil.copy(os.path.join(SCRIPTS, 'vault_token.py'),
                        os.path.join(d, 'vault_token.py'))
            with open(os.path.join(d, 'config.json'), 'w') as f:
                f.write('{ini bukan json')
            # CREDENTIAL dibaca di level modul, jadi import-nya sendiri
            # sudah harus gagal keras.
            with self.assertRaises(RuntimeError):
                load_module('vt_bad', os.path.join(d, 'vault_token.py'))
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_tanpa_config_fallback_default(self):
        d = tempfile.mkdtemp()
        try:
            shutil.copy(os.path.join(SCRIPTS, 'vault_token.py'),
                        os.path.join(d, 'vault_token.py'))
            env = dict(os.environ)
            env.pop('MUSE_TELE_CREDENTIAL', None)
            code = ('import vault_token; '
                    'print(vault_token._credential_name())')
            r = subprocess.run([sys.executable, '-c', code], cwd=d,
                               capture_output=True, text=True, env=env,
                               timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout.strip(), 'custom.telegram-bot-live')
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
