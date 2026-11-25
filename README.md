# Kit Bot Telegram Muse AI

Paket pasang-ulang sistem yang menghubungkan akun Muse ke Telegram
(bot @muse01fthbot di akun ini) — polling tiap 1 menit, jawab pesan
paralel, bisa kirim teks/foto/video, token di Secure Vault.

Versi 2 (25 Nov 2026) — perbaikan dari analisis celah
(`analisis-muse-telegram-connector.md`): gerbang allowlist + rate limit,
dispatcher mekanis (`dispatch.py`), memori percakapan, media bisa
diunduh/dilihat/ditranskrip, pesan panjang auto-split, penanganan
gagal kirim + eskalasi watchdog, cron health. Snapshot sistem live per
24 Nov 2026 (versi vault, sudah teruji: pesan + foto + video + 55 run
dispatcher berturut-turut tanpa gagal) + perbaikan v2.

## Isi paket

- `scripts/` — script Python + `process-one.md` (instruksi per-pesan):
  `poll.py`, `gate.py`, `dispatch.py`, `send.py`, `send-photo.py`,
  `send-video.py`, `action.py`, `lock.py`, `vault_token.py`,
  `typing_keeper.py`, `stuck_watchdog.py`, `health.py`, `mark.py`,
  `history.py`, `fetch.py`, `allow.py`, `process-one.md`
- `tests/test_kit.py` — smoke test (stdlib saja, tanpa jaringan)
- `install.sh` — salin script, tulis `config.json` + `state.json`,
  buat direktori kerja, cek compile + cek surrogate vault
- `config.example.json` — contoh `config.json` (nama kredensial vault)
- `cron-body.md` — template body cron dispatcher 1 menit (aliran dispatch.py)
- `SETUP.md` — panduan lengkap buat akun Muse baru
- `LICENSE` (MIT), `.gitignore`

## Cara pakai singkat

1. Salin folder ini ke workspace akun Muse yang baru.
2. Bikin bot baru via BotFather, daftarin tokennya ke Secure Vault
   (lihat `SETUP.md` langkah 2–3).
3. `bash install.sh ~/workspace/muse-tele <username-bot> <credential-slug> <id-telegram-kamu>`
4. Bikin cron dispatcher dari `cron-body.md` + cron health 1 jam,
   daftarin command ke BotFather.
5. Verifikasi (langkah 7 di `SETUP.md`).

## Yang tidak otomatis

BotFather, isi token vault, dan pembuatan cron tetap butuh Muse + user
di akun baru — tidak bisa murni dari script. Detailnya di `SETUP.md`.
