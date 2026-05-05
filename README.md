# Penjelasan Protokol di Project WashQueue

Dokumen ini merangkum kebingungan yang sempat muncul: fitur mana pakai TCP/UDP, letak kodenya, alur request, kenapa bisa jalan bersamaan, dan cek kecocokan isi PDF.

---

## 1) Fitur A/B dan protokol yang dipakai

| Fitur | Protokol aplikasi | Transport | Lokasi kode |
|---|---|---|---|
| Buka halaman web (`/`, `/daftar`, `/admin`) | HTTP/1.1 | TCP | `app.py:23-25`, `app.py:27-43`, `app.py:45-47`, `app.py:73-75` |
| Submit form antrian | HTTP `POST /daftar` | TCP | `app.py:27-43` |
| Klik tombol Dipanggil/Selesai | HTTP `GET /panggil/<nomor>` / `GET /selesai/<nomor>` | TCP | `app.py:49-71` |
| Broadcast status ke LAN | Pesan UDP | UDP | `app.py:15-21` + listener `udp_listener.py:7-13`, `udp_listener.py:21-24` |
| Kirim notifikasi email | SMTP (`EHLO`, `STARTTLS`, `LOGIN`, `SENDMAIL`) | TCP (+ TLS setelah STARTTLS) | `tcp_email_notif.py:11-39` |

Inti: **POST itu HTTP method**, bukan TCP. Kalimat yang tepat: **HTTP POST berjalan di atas TCP**.

---

## 2) Di mana 3-way handshake terjadi?

3-way handshake (SYN → SYN-ACK → ACK) terjadi di level **OS/network stack**, bukan di fungsi route Flask.

Terjadi saat:
1. Browser konek ke Flask server `host=0.0.0.0, port=5000` (`app.py:73-75`).
2. Kode Python tidak menulis paket SYN/ACK manual; OS yang menangani.
3. Setelah koneksi TCP jadi, baru HTTP request diproses (`GET`, `POST`, dll).

Handshake TCP juga terjadi saat app membuat koneksi ke SMTP server (`smtp.gmail.com:587`) di `tcp_email_notif.py:15`.

---

## 3) Alur fitur POST antrian

1. User buka `/daftar` (HTTP GET) → form tampil (`app.py:27-43`).
2. User klik tombol submit → browser kirim **HTTP POST /daftar**.
3. Server ambil data form: `nama`, `jenis`, `email`, `no_hp` (`app.py:31-34`).
4. Server simpan ke list `antrian` (in-memory) dan set status `Menunggu` (`app.py:37-41`).
5. Server balas redirect `302` ke halaman index (`app.py:42`).
6. Browser lanjut `GET /` (pola Post/Redirect/Get).

---

## 4) Alur fitur Dipanggil sampai email terkirim

1. Admin klik tombol **Dipanggil** → request `GET /panggil/<nomor>` (`app.py:49`).
2. Status item diubah jadi `Dipanggil` (`app.py:52-54`).
3. Server menembakkan 2 proses background:
   - Thread UDP broadcast (`app.py:55-56`) untuk notifikasi LAN.
   - Thread kirim email (`app.py:57-59`) ke fungsi SMTP.
4. Di SMTP function:
   - Konek TCP ke `smtp.gmail.com:587` (`tcp_email_notif.py:15`)
   - `EHLO` (`tcp_email_notif.py:16`)
   - `STARTTLS` (`tcp_email_notif.py:17`)
   - `LOGIN` (`tcp_email_notif.py:18`)
   - `sendmail` (`tcp_email_notif.py:37`)
   - `quit` (`tcp_email_notif.py:38`)

---

## 5) Kenapa fitur tertentu pakai TCP, dan yang lain pakai UDP?

### Kenapa web + form pakai TCP?
- HTTP butuh request/response yang rapi dan reliable.
- Data form tidak boleh hilang/acak urutan.
- Karena itu HTTP memakai TCP.

### Kenapa email (SMTP) pakai TCP?
- Pengiriman email butuh sesi/perintah berurutan (EHLO → AUTH → DATA).
- SMTP memang dirancang berjalan di atas TCP.
- `STARTTLS` menambah keamanan enkripsi.

### Kenapa broadcast pakai UDP?
- Butuh kirim cepat ke banyak device LAN sekaligus.
- Tidak perlu koneksi satu-per-satu ke tiap client.
- Trade-off: tidak ada jaminan paket pasti sampai.

---

## 6) Kenapa UDP dan SMTP/TCP bisa bekerja barengan?

Karena dipisah ke **dua thread** (`threading.Thread`) di `app.py:56` dan `app.py:58-59`.

Artinya:
- Thread 1: kirim UDP broadcast.
- Thread 2: kirim email SMTP/TCP.
- Main thread web tetap bisa cepat balas request admin (tidak menunggu email selesai dulu).

### Apa itu multithreading (versi sederhana)?
Multithreading adalah menjalankan beberapa pekerjaan secara **konkuren** dalam satu proses, supaya tugas I/O lambat (mis. SMTP) tidak memblokir tugas lain (respon web/admin).

---

## 7) Kenapa UDP broadcast kamu berhasil?

Syarat yang terlihat terpenuhi:
1. Pengirim kirim ke broadcast `255.255.255.255:5005` (`app.py:12-13`, `app.py:19`).
2. Listener bind ke port yang sama `5005` (`udp_listener.py:3`, `udp_listener.py:13`).
3. Opsi `SO_BROADCAST` aktif (`app.py:18`, `udp_listener.py:10`).
4. Device ada di LAN/broadcast domain yang sama dan firewall tidak memblokir port ini.

---

## 8) Cek PDF: sudah cocok atau belum?

File yang dicek: `T7_Pemjar_WashQueue_Kel1.pdf`

### Yang sudah cocok
- HTTP/TCP untuk web access: **cocok**.
- SMTP/TCP (+ TLS 587) untuk email notifikasi: **cocok**.
- UDP broadcast untuk notifikasi LAN: **cocok**.
- Penggunaan threading agar admin page tidak terasa lag saat kirim email: **cocok** dengan `threading.Thread` di `app.py`.

### Yang perlu direvisi
- Beberapa bagian PDF menyebut data pendaftaran masuk ke **database/SQLite**.
- Implementasi saat ini **belum database**; masih list in-memory: `antrian = []` di `app.py:9`.

Saran kalimat revisi:
> “Saat ini data antrian disimpan sementara di memori server (list Python), belum persisten ke database.”

---

## 9) Kesimpulan singkat

- **POST antrian** = HTTP method di atas TCP.
- **Notifikasi email** = SMTP di atas TCP, lalu diamankan TLS (STARTTLS).
- **Notifikasi layar LAN** = UDP broadcast.
- **Bisa jalan bareng** karena multithreading (dua thread background dijalankan saat tombol Dipanggil ditekan).
