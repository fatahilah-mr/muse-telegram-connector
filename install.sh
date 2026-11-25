#!/bin/bash
# Installer kit bot Telegram Muse AI (sistem @muse01fthbot, versi vault v2).
#
# Pakai:
#   bash install.sh <target_dir> <bot_username_tanpa_@> <credential_slug> <allowed_ids_koma>
#
# Contoh:
#   bash install.sh ~/workspace/muse-tele muse02fthbot custom.telegram-bot-live-2 123456789,987654321
#
# Yang dilakukan script ini (hanya file, tanpa sentuh akun):
#   - salin script + process-one.md ke target_dir
#   - ganti username bot di docstring + process-one.md
#   - tulis config.json (nama kredensial vault) + state.json (allowlist, offset 0)
#   - buat direktori kerja (processing, history, downloads)
#   - cek semua .py bisa di-compile
#   - cek surrogate vault bisa diambil (kredensial harus sudah terdaftar
#     + terisi — lihat SETUP.md langkah 2)
#
# Yang TIDAK dilakukan script ini (harus lewat Muse + user, lihat SETUP.md):
#   - daftarin token bot ke Secure Vault (credentials.request_api_access)
#   - bikin cron dispatcher 1 menit (cron.add, body dari cron-body.md)
#   - bikin cron health 1 jam (cron.add)
#   - daftarin command ke BotFather (/start, /help, /id, /allow, /unallow, /status)
#
# KEAMANAN: kalau target_dir sudah berisi file .py, script BERHENTI — tidak
# menimpa instalasi yang sudah ada. Hapus manual atau pakai target lain.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-}"
BOT_USER="${2:-}"
CRED="${3:-}"
ALLOWED="${4:-}"

if [ -z "$TARGET" ] || [ -z "$BOT_USER" ] || [ -z "$CRED" ] || [ -z "$ALLOWED" ]; then
  echo "Pakai: bash install.sh <target_dir> <bot_username_tanpa_@> <credential_slug> <allowed_ids_koma>"
  exit 2
fi

mkdir -p "$TARGET"
if ls "$TARGET"/*.py >/dev/null 2>&1; then
  echo "BERHENTI: $TARGET sudah berisi file .py — tidak menimpa instalasi lama."
  exit 1
fi

cp "$KIT_DIR/scripts/"*.py "$KIT_DIR/scripts/process-one.md" "$TARGET/"
mkdir -p "$TARGET/processing" "$TARGET/history" "$TARGET/downloads"

# Username bot di docstring + process-one.md (kosmetik, tidak pengaruhi fungsi).
grep -rl "@muse01fthbot" "$TARGET" | xargs sed -i "s/@muse01fthbot/@${BOT_USER}/g"
# Nama kredensial vault di process-one.md.
sed -i "s/custom\.telegram-bot-live/${CRED}/g" "$TARGET/process-one.md"

# config.json — nama kredensial vault yang dibaca vault_token.py.
printf '{\n  "credential": "%s"\n}\n' "$CRED" > "$TARGET/config.json"

# state.json — allowlist + offset awal (jangan timpa kalau sudah ada).
if [ ! -f "$TARGET/state.json" ]; then
  IDS="$(echo "$ALLOWED" | sed 's/ *, */,/g')"
  printf '{"allowed": [%s], "offset": 0}\n' "$IDS" > "$TARGET/state.json"
fi

python3 -m py_compile "$TARGET"/*.py

# Cek surrogate vault (gagal keras kalau kredensial belum terdaftar/terisi).
cd "$TARGET"
if ! python3 -c "from vault_token import get_token; t = get_token(); assert t.startswith('hsurr:'), 'surrogate tidak valid'" 2>/dev/null; then
  echo "GAGAL: surrogate vault untuk '$CRED' tidak bisa diambil."
  echo "Pastikan langkah 2 SETUP.md sudah selesai (token sudah dipaste di secure entry)."
  exit 1
fi
echo "OK: terinstal di $TARGET (vault OK)"
echo "Lanjut ke SETUP.md langkah 5 (cron dispatcher + health)."
