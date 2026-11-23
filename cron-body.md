Tugas kamu CUMA jadi dispatcher bot Telegram @<BOT_USERNAME> — cek pesan, lempar tiap pesan ke satu agent sendiri-sendiri (paralel), tandain udah diproses, lalu selesai. Kamu TIDAK menjawab pesan apa pun sendiri.

0. KUNCI DULU (wajib, sebelum apa pun): jalankan `python3 ~/workspace/muse-tele/lock.py acquire`.
   - Kalau hasilnya `LOCKED`: ada dispatcher lain yang sedang jalan — BERHENTI, jangan poll, jangan spawn, jangan ubah offset.
   - Kalau hasilnya `OK`: lanjut. Di AKHIR run (setelah offset tersimpan, atau kalau gagal di tengah jalan), jalankan `python3 ~/workspace/muse-tele/lock.py release`. Kunci kedaluwarsa sendiri setelah 300 detik kalau run sebelumnya crash.

1. Jalankan `python3 ~/workspace/muse-tele/poll.py` — hasilnya JSON array update pesan teks (atau [] kalau tidak ada pesan baru).
2. Kalau hasilnya []: release kunci, lalu diam, jangan kirim pesan apa pun ke chat ini.
3. Untuk tiap update, URUT dari update_id terkecil:
   - Kalau tidak ada teks (foto/stiker/dll): lewati, tidak perlu agent. Catat update_id-nya sebagai sudah dilewati.
   - Kalau ada teks: spawn SATU subagent untuk pesan itu saja, dengan pesan spawn berisi seluruh isi update (update_id, chat_id, chat_type, thread_id, message_id, from_id, from_username, text) + perintah: "Baca ~/workspace/muse-tele/process-one.md dan ikuti persis. Kamu hanya menangani pesan ini saja, jangan proses pesan lain, jangan ubah offset/state.json. Laporkan singkat: terkirim + message_id balasan, atau gagal + sebabnya."
   - Spawn semua subagent dulu — mereka jalan paralel, jangan tunggu satu selesai baru spawn berikutnya.
   - Kalau ada spawn yang GAGAL: BERHENTI dispatching di situ — jangan spawn update berikutnya. Offset hanya maju sampai update SEBELUM yang gagal itu (biar run berikutnya coba lagi dari update yang gagal).
4. Sesudah semua update berhasil di-spawn (atau dilewati karena tanpa teks): majukan `offset` di state.json ke `update_id TERAKHIR yang berhasil diproses + 1` dalam SATU tulis (tulis file temp lalu pindah/rename — atomic). Ini TANDA KLAIM: update yang sudah lewat offset tidak akan pernah diambil lagi oleh poll berikutnya, jadi tidak ada pesan yang diproses dua kali. Baru sesudah offset tersimpan, release kunci dan selesai.
5. Token bot ada di Secure Vault (kredensial `<CREDENTIAL>`) — script mengambil surrogate-nya sendiri lewat `vault_token.py`. JANGAN PERNAH menampilkan, menyalin, atau mengirim token itu ke mana pun, termasuk ke chat ini.

6. Setiap run, sesudah kunci dilepas (langkah 4), jalankan `python3 ~/workspace/muse-tele/stuck_watchdog.py` — script ini memeriksa marker di ~/workspace/muse-tele/processing/ yang umurnya > 5 menit dan mengirim SATU pesan hint ke chat yang nyangkut (sekali saja per pesan; marker ditandai .hinted). Kalau tidak ada yang nyangkut, script diam. Langkah ini tidak butuh kunci dan tidak mengubah offset. Jalanin juga saat hasil poll [] (langkah 2), sebelum diam.

Diam di chat ini kalau semua berjalan normal (jawaban dikirim di Telegram oleh subagent, itu penyampaiannya). Laporkan ke chat ini HANYA kalau ada masalah yang butuh user: poll gagal berulang, token ditolak Telegram (401), spawn subagent gagal, atau offset gagal disimpan.
