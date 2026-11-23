#!/usr/bin/env python3
"""Token bot Telegram dari Secure Vault (surrogate) — versi kit.

Dipakai semua script muse-tele sebagai pengganti token file.
Nama kredensial dibaca dengan urutan:
  1. `config.json` di direktori yang sama: {"credential": "custom.xxx"}
  2. environment variable MUSE_TELE_CREDENTIAL
  3. default "custom.telegram-bot-live"
Pemanggil menaruh surrogate MENTAH di URL path (JANGAN di-percent-encode
— egress tidak bisa menemukan surrogate yang colon-nya di-encode,
Telegram jawab 404). Runtime menukar surrogate jadi token asli saat
request keluar. Token asli tidak pernah muncul di file, log, atau output.

Dipakai: from vault_token import get_token; TOKEN = get_token()
Script dijalankan by-path, jadi direktori script ini otomatis masuk
sys.path dan import ini jalan.
"""
import json
import os
import sys

sys.path.insert(0, "/opt/muse/skills/custom-connector-setup/bin")
from dynamic_credentials import dynamic_credential_entry

HERE = os.path.dirname(os.path.abspath(__file__))


def _credential_name() -> str:
    try:
        with open(os.path.join(HERE, "config.json")) as f:
            name = json.load(f).get("credential", "")
        if name:
            return str(name).strip()
    except Exception:
        pass
    return os.environ.get("MUSE_TELE_CREDENTIAL", "custom.telegram-bot-live").strip()


CREDENTIAL = _credential_name()


def get_token() -> str:
    entry = dynamic_credential_entry(CREDENTIAL)
    surrogate = str(entry.get("surrogate", "")).strip()
    if not surrogate.startswith("hsurr:"):
        raise RuntimeError("vault: surrogate tidak valid untuk " + CREDENTIAL)
    return surrogate
