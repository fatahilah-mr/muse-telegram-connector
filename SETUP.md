# SETUP — Pasang Bot Telegram Muse AI di Akun Baru

Sistem ini: bot Telegram jadi "tangan" akun Muse — polling `getUpdates`
tiap 1 menit, tiap pesan dilempar ke satu agent (paralel), jawaban
dikirim balik lewat bot. Token bot TIDAK ada di file, melainkan di
Secure Vault (surrogate `hsurr:` ditukar jadi token asli saat request
keluar).

Versi 2 (25 Nov 2026): dispatcher mekanis (`dispatch.py`), gerbang
allowlist + rate limit (`gate.py`), memori percakapan, media bisa
diunduh, pesan panjang auto-split, watchdog bereskalasi, cron health.

## Prasyarat

- Akun Muse baru (workspace sendiri, VM sendiri).
- Folder kit ini sudah disalin ke `~/workspace/muse-telegram-kit/`.
- Akun Telegram yang bisa bikin bot (BotFather), atau user yang bikinkan.

## Langkah 1 — Bikin bot Telegram baru

1. Di Telegram, buka **@BotFather** → `/newbot` → ikuti prompt (nama +
   username, username harus unik dan berakhiran `bot`).
2. Simpan **token** dan **username** bot. JANGAN kirim token di chat biasa.
3. (Opsional, dicatat buat nanti) kirim `/start` ke bot baru, lalu
   `/id` — tidak ada; ID Telegram kamu didapat dari **@userinfobot**
   (buka, kirim apa saja, catat angkanya). Itu yang masuk allowlist.

## Langkah 2 — Daftarin token ke Secure Vault

Dari akun Muse yang baru, panggil `credentials.request_api_access`:

- `provider`: slug unik per bot, huruf kecil, contoh
  `telegram-bot-live-2` (JANGAN pakai slug bot lain — satu slug = satu token)
- `api_hosts`: `["api.telegram.org"]`
- `auth_scheme`: `api_key`
- `placement`: `url_path_segment:/bot{}`

Muse akan memberi link secure entry — user paste **token bot BARU**
di sana. Muse tidak pernah melihat nilainya.

(Opsional tapi dianjurkan) setelah itu jalankan:
`/opt/muse/skills/custom-connector-setup/bin/scaffold-connector-docs --provider <slug>`
untuk membuat doc konektor `custom.<slug>`.

## Langkah 3 — Instalasi file

```bash
bash ~/workspace/muse-telegram-kit/install.sh \
  ~/workspace/muse-tele <username-bot-tanpa-@> <credential-slug> <id-telegram-kamu>
```

Contoh:

```bash
bash ~/workspace/muse-telegram-kit/install.sh \
  ~/workspace/muse-tele muse02fthbot custom.telegram-bot-live-2 123456789
```

Untuk beberapa owner, pisahkan ID dengan koma tanpa spasi:
`123456789,987654321`.

Installer menyalin script, mengganti username bot di docstring dan
`process-one.md`, menulis `config.json` (nama kredensial vault) dan
`state.json` (`{"allowed": [...], "offset": 0}`), membuat direktori
`processing/`, `history/`, `downloads/`, lalu cek compile + cek
surrogate vault. Kalau target sudah berisi `.py`, installer BERHENTI
(tidak menimpa).

## Langkah 4 — Verifikasi surrogate (sebelum cron jalan)

```bash
cd ~/workspace/muse-tele
python3 -c "from vault_token import get_token; t = get_token(); print('OK prefix=' + t.split(':')[0])"
python3 poll.py
```

Harus keluar `OK prefix=hsurr` lalu objek `{"updates": [], ...}`.
Kalau gagal, cek: kredensial sudah terisi (langkah 2) dan nama di
`config.json` sama dengan slug yang didaftarkan.

## Langkah 5 — Cron dispatcher 1 menit + cron health 1 jam

Buat cron dispatcher (`cron.add`):

- `id`: `muse-tele-poll-1m`
- `mode`: `task`, `enabled`: true
- `schedule`: `kind: interval`, `every: 1m`, timezone akun
  (`Asia/Jakarta` kalau user di WIB)
- `timeout_secs`: 300
- `body`: isi `~/workspace/muse-telegram-kit/cron-body.md`, dengan
  `<BOT_USERNAME>` diganti username bot baru dan `<CREDENTIAL>`
  diganti slug kredensial dari langkah 2.

Buat cron health (`cron.add`):

- `id`: `muse-tele-health-1h`
- `mode`: `task`, `enabled`: true
- `schedule`: `kind: interval`, `every: 1h`, timezone akun
- `timeout_secs`: 300
- `body`: "Jalankan `python3 ~/workspace/muse-tele/health.py`. Kalau
  output `status` = `alert`, laporkan masalahnya ke chat ini. Kalau
  `ok`, diam."

## Langkah 6 — Command BotFather + privacy

Di @BotFather → bot baru → `/setcommands`:

```
start - Mulai bot
help - Bantuan
id - Lihat ID Telegram kamu
allow - Tambah ID ke allowlist (owner saja)
unallow - Hapus ID dari allowlist (owner saja)
status - Cek kondisi bot
```

Privacy mode: biarkan **ON** kalau bot cuma dipakai di DM / dibalas
saat di-mention. Kalau mau bot baca semua pesan grup, matikan lewat
`/setprivacy` → Disable, ATAU jadikan bot admin grup.

## Langkah 7 — Verifikasi end-to-end

Dari akun Muse baru (ganti 123456789 dengan ID Telegram kamu):

```bash
cd ~/workspace/muse-tele
printf '%s' "tes halo" | python3 send.py 123456789
python3 action.py typing 123456789
python3 send-photo.py 123456789 <file-foto> --caption "tes foto"
python3 send-video.py 123456789 <file-video-10detik.mp4> --caption "tes video" --duration 10
python3 dispatch.py plan   # harus keluar {"status": "plan", ...}
```

Lalu kirim pesan ke bot dari Telegram — balasan harus datang dalam
~1 menit, dengan status mengetik terlihat saat diproses. Terakhir,
cek `cron.runs` untuk `muse-tele-poll-1m`: run-run pertama harus
`succeeded` tanpa error.

Jalankan juga smoke test kit (dari folder kit, tanpa jaringan):

```bash
python3 ~/workspace/muse-telegram-kit/tests/test_kit.py
```

## Yang tidak ikut pindah

- **Riwayat pesan / offset**: `state.json` mulai dari 0 di akun baru.
- **Goal dan dokumen konsep**: buat ulang kalau mau (opsional).
- **Bot lama**: tetap jalan di akun lama — kit ini instalasi baru,
  bukan migrasi. Satu bot Telegram = satu akun Muse.

## Gotcha (pelajaran yang sudah dibayar mahal)

- **Surrogate JANGAN di-percent-encode.** Colon di `hsurr:...` harus
  mentah di URL. Kalau di-encode, egress tidak menemukan surrogate dan
  Telegram jawab 404.
- **Kirim pesan/foto/video SATU percobaan, tanpa retry.** Respons
  hilang di jalan ≠ gagal kirim — retry bikin pesan dobel. (Memotong
  pesan panjang jadi beberapa potong BUKAN retry — tiap potong dikirim
  tepat satu kali.)
- **Lock dispatcher atomik** (`O_CREAT|O_EXCL`, kedaluwarsa 300 dtk)
  dan **release bertanda token**. Jangan ganti dengan cek-dulu-bikin-dulu
  — itu race dan bikin pesan kejawab 2x.
- **Offset dimajukan dispatch.py commit SETELAH spawn sukses**, tulis
  atomic (file temp lalu rename). Update yang sudah lewat offset tidak
  pernah diproses ulang — kalau spawn gagal, offset hanya maju sampai
  sebelum yang gagal.
- **ID pesan GramJS ≠ ID Bot API.** Jangan pakai ID GramJS sebagai
  `--reply-to` (Telegram jawab 400).
- **Privacy mode ON**: @mention di grup tidak sampai ke bot kecuali
  bot jadi admin atau privacy dimatikan.
- **Bot BISA melihat foto** yang dikirim ke dia (diunduh via `fetch.py`,
  lalu dibaca — sejak v2, 25 Nov 2026). Foto, dokumen teks/PDF, dan
  voice note juga bisa diproses. Stiker juga dibaca (file .webp yang
  dikirim sebagai dokumen diubah Telegram jadi stiker dan captionnya
  hilang di Bot API — bot tetap mendeskripsikan gambarnya).
- **Jangan simpan token di file.** Sistem ini tidak membaca
  `bot-token.txt` sama sekali. Kalau ada file itu di instalasi lama,
  itu cuma backup darurat.
- **Marker memakai chat_id + message_id.** `message_id` saja tidak
  cukup — dua chat bisa punya `message_id` yang sama.
- **Gate menyaring sebelum spawn.** Pesan dari luar allowlist dan
  pesan melebihi rate limit (10 pesan / 5 menit per user) tidak
  pernah jadi subagent.
- **Pesan gagal terkirim dicatat (.failed.json).** Watchdog memberi
  kabar satu kali ke user; jangan hapus marker gagal diam-diam.
- **Polling 1 menit = biaya turns.** Jangan turunkan interval tanpa
  alasan — dan kalau user sudah menetapkan 1 menit, jangan diubah.
