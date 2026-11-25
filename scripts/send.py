#!/usr/bin/env python3
"""Kirim pesan via bot. Teks dibaca dari stdin (biar newline aman).
Otomatis MEMOTONG pesan panjang jadi beberapa potong (limit Telegram
4096 karakter; dipakai 4000 biar aman), dipotong di batas paragraf /
baris / kalimat kalau bisa, kalau tidak baru potong keras. Potongan
pertama me-reply pesan asal (kalau --reply-to dipakai), potongan
berikutnya nyambung biasa.
Pakai: printf '%s' 'teks balasan' | python3 send.py <chat_id> [--thread <id>] [--reply-to <msg_id>]
Output: JSON hasil kirim (ok + message_id pesan terakhir + jumlah potong).
"""
import json
import sys
import urllib.request

from vault_token import get_token
# Token dari Secure Vault (surrogate hsurr:...); runtime menukar jadi
# token asli saat request keluar. JANGAN print TOKEN.
TOKEN = get_token()

LIMIT = 4000  # di bawah limit Telegram 4096


def _split_once(s, limit):
    """Potong s jadi (kepala, sisa); kepala <= limit, putus di batas
    terdekat: paragraf, baris, akhir kalimat, spasi — kalau tidak ada,
    potong keras di limit."""
    for sep, cut_after in (("\n\n", None), ("\n", None), (". ", 1), (" ", None)):
        idx = s.rfind(sep, 0, limit)
        if idx > 0:
            if sep == ". ":
                # pertahankan titik di kepala, buang spasinya
                return s[:idx + 1], s[idx + 2:].lstrip()
            return s[:idx].rstrip(), s[idx + len(sep):].lstrip()
    return s[:limit], s[limit:]


def split_message(text, limit=LIMIT):
    """Pecah teks panjang jadi list potongan, masing-masing <= limit."""
    if len(text) <= limit:
        return [text]
    chunks = []
    rest = text
    while len(rest) > limit:
        head, rest = _split_once(rest, limit)
        if not head:
            head, rest = rest[:limit], rest[limit:]
        chunks.append(head)
    if rest:
        chunks.append(rest)
    return chunks


def post(payload):
    # SENGAJA tanpa retry (pelajaran 22 Nov 2026): sendMessage tidak
    # idempotent. Kalau percobaan pertama sampai ke Telegram tapi
    # responsnya hilang di jalan (egress putus), percobaan kedua akan
    # mengirim PESAN YANG SAMA untuk kedua kalinya — user lihat dobel.
    # Satu percobaan dengan timeout longgar; kalau gagal, caller yang
    # memutuskan (jangan kirim ulang membabi buta — lihat process-one.md).
    # Catatan: memotong pesan (split_message) BUKAN retry — tiap potong
    # dikirim tepat satu kali.
    try:
        req = urllib.request.Request(
            f'https://api.telegram.org/bot{TOKEN}/sendMessage',
            data=json.dumps(payload).encode(), method='POST')
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except Exception as e:
        return {'ok': False, 'error': str(e)}


def main():
    args = sys.argv[1:]
    if not args:
        print('Pakai: send.py <chat_id> [--thread <id>] [--reply-to <msg_id>]',
              file=sys.stderr)
        raise SystemExit(2)
    chat_id = args[0]
    thread_id = None
    reply_to = None
    i = 1
    while i < len(args):
        if args[i] == '--thread' and i + 1 < len(args):
            thread_id = int(args[i + 1]); i += 2
        elif args[i] == '--reply-to' and i + 1 < len(args):
            reply_to = int(args[i + 1]); i += 2
        else:
            i += 1
    text = sys.stdin.read()
    if not text.strip():
        print(json.dumps({'ok': False, 'error': 'teks kosong'}))
        raise SystemExit(1)
    chunks = split_message(text)
    last_id = None
    for n, chunk in enumerate(chunks):
        payload = {'chat_id': int(chat_id), 'text': chunk}
        if thread_id:
            payload['message_thread_id'] = thread_id
        if reply_to and n == 0:
            payload['reply_parameters'] = {'message_id': reply_to}
        res = post(payload)
        if not res.get('ok'):
            print(json.dumps({'ok': False, 'error': str(res),
                              'sent_chunks': n,
                              'total_chunks': len(chunks)},
                             ensure_ascii=False))
            raise SystemExit(1)
        last_id = res['result']['message_id']
    print(json.dumps({'ok': True, 'message_id': last_id,
                      'chunks': len(chunks)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
