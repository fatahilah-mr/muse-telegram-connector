# Kit Bot Telegram Muse AI

Paket pasang-ulang sistem yang menghubungkan akun Muse ke Telegram
(bot @muse01fthbot di akun ini) — polling tiap 1 menit, jawab pesan
paralel, bisa kirim teks/foto/video, token di Secure Vault.

Snapshot sistem live per **24 Nov 2026** (versi vault, sudah teruji:
pesan + foto + video + 55 run dispatcher berturut-turut tanpa gagal).

## Isi paket

- `scripts/` — 9 script Python + `process-one.md` (instruksi per-pesan)
- `install.sh` — salin script, tulis `config.json` + `state.json`, cek compile
- `config.example.json` — contoh `config.json` (nama kredensial vault)
- `cron-body.md` — template body cron dispatcher 1 menit
- `SETUP.md` — panduan lengkap buat akun Muse baru

## Cara pakai singkat

1. Salin folder ini ke workspace akun Muse yang baru.
2. Bikin bot baru via BotFather, daftarin tokennya ke Secure Vault
   (lihat `SETUP.md` langkah 2–3).
3. `bash install.sh ~/workspace/muse-tele <username-bot> <credential-slug> <id-telegram-kamu>`
4. Bikin cron dispatcher dari `cron-body.md`, daftarin command ke BotFather.
5. Verifikasi (langkah 6 di `SETUP.md`).

## Yang tidak otomatis

BotFather, isi token vault, dan pembuatan cron tetap butuh Muse + user
di akun baru — tidak bisa murni dari script. Detailnya di `SETUP.md`.
