# WashQueue v2 - Sistem Antrian Cuci Motor dan Mobil

WashQueue adalah aplikasi antrian cuci kendaraan berbasis web untuk pelanggan dan admin. Aplikasi ini dibuat untuk tugas Pemrograman Jaringan dengan fokus pada penerapan komunikasi berbasis TCP dan UDP dalam satu sistem nyata.

Pada versi 2, sistem tidak hanya menyimpan data di memori, tetapi sudah menggunakan database SQLite sehingga data antrian dan log email tetap tersimpan selama file database tidak dihapus.

## Anggota Kelompok

| No | Nama | NPM |
|---:|------|-----|
| 1 | Pasya Shafaa Aaqila | 51422281 |
| 2 | Dio Adeliya Putra | 50422434 |
| 3 | Muhammad Ghifani Ikhsan | 51422061 |
| 4 | Eva Meivina Dwiana | 50422472 |

Catatan: NPM pada tabel di atas adalah Nomor Pokok Mahasiswa. Proyek ini bukan aplikasi Node.js dan tidak menggunakan package manager `npm`.

## Ringkasan Aplikasi

Aplikasi ini digunakan untuk:

1. Mendaftarkan pelanggan ke antrian cuci motor atau mobil.
2. Menampilkan daftar antrian dan status setiap pelanggan.
3. Memberikan dashboard admin untuk memanggil pelanggan dan menandai antrian selesai.
4. Mengirim notifikasi email kepada pelanggan saat nomor antrian dipanggil.
5. Mengirim broadcast UDP ke listener lokal/LAN saat ada perubahan status antrian.
6. Menyimpan data antrian dan log email ke database SQLite.

## Tech Stack

| Bagian | Teknologi | Fungsi |
|--------|-----------|--------|
| Bahasa utama | Python | Bahasa pemrograman backend dan networking. |
| Web framework | Flask | Menjalankan server web, routing halaman, dan menerima input form pelanggan. |
| Template frontend | HTML, CSS, Jinja2 | Membuat tampilan halaman antrian, form daftar, admin, dan database viewer. |
| Database | SQLite3 | Menyimpan data antrian dan log email di `washqueue.db`. |
| Protokol web | HTTP di atas TCP | Komunikasi browser dengan server Flask pada port 5000. |
| Email | SMTP di atas TCP | Mengirim email notifikasi melalui Gmail SMTP pada port 587 dengan TLS. |
| UDP broadcast | Python `socket` UDP | Mengirim pesan status antrian ke listener pada port 5005. |
| Concurrency | Python `threading` | Menjalankan proses email dan UDP di background agar web tidak menunggu proses jaringan selesai. |
| Environment variable | `python-dotenv` | Membaca konfigurasi email dari file `.env`. |

## Struktur File Utama

```text
antrianCuci_kel1_v2/
├── app.py                # Aplikasi Flask, route web, database, dan pemanggilan UDP/email
├── tcp_email_notif.py    # Modul pengiriman email menggunakan SMTP/TCP
├── udp_listener.py       # Listener untuk menerima broadcast UDP port 5005
├── cek_db.py             # Script sederhana untuk melihat isi tabel database di terminal
├── washqueue.db          # Database SQLite lokal
└── templates/
    ├── index.html        # Halaman daftar antrian publik
    ├── daftar.html       # Form pendaftaran pelanggan
    ├── admin.html        # Dashboard admin
    └── db_view.html      # Tampilan isi database melalui browser
```

## Cara Menjalankan Aplikasi

### 1. Siapkan dependency Python

Jika belum ada Flask dan python-dotenv, install terlebih dahulu:

```bash
pip install flask python-dotenv
```

Modul `sqlite3`, `socket`, `threading`, `smtplib`, dan `email` sudah termasuk dalam standard library Python.

### 2. Siapkan konfigurasi email

Buat file `.env` di root project dengan format berikut:

```env
EMAIL_PENGIRIM=email_pengirim@gmail.com
EMAIL_PASSWORD=app_password_gmail
```

Gunakan Gmail App Password, bukan password utama akun Google.

### 3. Jalankan server Flask

```bash
python app.py
```

Server berjalan pada:

```text
http://127.0.0.1:5000
```

Di terminal, aplikasi juga menampilkan URL panel admin berdasarkan nilai `SECRET` di `app.py`.

### 4. Jalankan UDP listener

Buka terminal kedua, lalu jalankan:

```bash
python udp_listener.py
```

Listener akan menunggu broadcast UDP pada port 5005. Untuk pengujian LAN, jalankan listener pada komputer yang berada di jaringan lokal yang sama dan pastikan firewall mengizinkan UDP port 5005.

### 5. Melihat isi database dari terminal

```bash
python cek_db.py
```

Script ini menampilkan isi tabel `antrian` dan `email_log` dari `washqueue.db`.

## Fitur Aplikasi

### 1. Halaman antrian publik

Route: `/`

Halaman ini menampilkan:

- total antrian,
- jumlah status `Menunggu`,
- jumlah status `Dipanggil`,
- jumlah status `Selesai`,
- daftar pelanggan yang sudah mendaftar.

Data ditampilkan dari database SQLite melalui fungsi `get_antrian()` di `app.py`.

### 2. Form pendaftaran antrian

Route: `/daftar`

Pelanggan mengisi:

- jenis kendaraan: motor atau mobil,
- nama pemilik,
- nomor HP,
- alamat email.

Saat form dikirim, aplikasi:

1. mengambil nomor antrian berikutnya dari database,
2. menyimpan data pelanggan ke tabel `antrian`,
3. memberi status awal `Menunggu`,
4. mengarahkan pelanggan kembali ke halaman antrian.

### 3. Dashboard admin dengan secret route

Route admin menggunakan nilai `SECRET` pada `app.py`, bukan `/admin` biasa.

Dashboard admin menampilkan antrian berdasarkan status:

- `Menunggu`: bisa dipanggil,
- `Dipanggil`: bisa ditandai selesai,
- `Selesai`: ditampilkan sebagai data yang sudah selesai.

Secret route dipakai agar link admin tidak langsung terlihat dari navigasi publik. Namun, ini belum setara dengan sistem login karena siapa pun yang mengetahui URL tetap bisa membuka dashboard.

### 4. Memanggil nomor antrian

Route: `/<SECRET>/panggil/<nomor>`

Saat admin menekan tombol panggil, aplikasi melakukan beberapa proses:

1. mencari data pelanggan berdasarkan nomor antrian,
2. mengubah status menjadi `Dipanggil`,
3. mengirim pesan broadcast UDP,
4. mengirim email notifikasi melalui SMTP/TCP,
5. mencatat log email ke tabel `email_log`.

Pengiriman UDP dan email dijalankan menggunakan `threading.Thread` agar response halaman admin tidak tertahan oleh proses jaringan.

### 5. Menandai antrian selesai

Route: `/<SECRET>/selesai/<nomor>`

Saat admin menandai antrian selesai, aplikasi:

1. mengubah status menjadi `Selesai`,
2. mengirim broadcast UDP bahwa nomor tersebut selesai,
3. mengarahkan admin kembali ke dashboard.

Pada proses selesai, aplikasi mengirim UDP broadcast tetapi tidak mengirim email.

### 6. Database viewer

Route: `/<SECRET>/db-view`

Halaman ini menampilkan isi tabel:

- `antrian`,
- `email_log`.

Fitur ini membantu melihat data yang benar-benar tersimpan di SQLite tanpa membuka database secara manual.

## Database

Database yang digunakan adalah SQLite dengan file:

```text
washqueue.db
```

Saat `app.py` dijalankan, fungsi `init_db()` otomatis membuat tabel jika belum ada.

### Tabel `antrian`

| Kolom | Fungsi |
|-------|--------|
| `id` | Primary key otomatis. |
| `nomor` | Nomor antrian pelanggan. |
| `nama` | Nama pelanggan. |
| `jenis` | Jenis kendaraan, yaitu Motor atau Mobil. |
| `email` | Email pelanggan untuk notifikasi. |
| `no_hp` | Nomor HP pelanggan. |
| `status` | Status antrian: `Menunggu`, `Dipanggil`, atau `Selesai`. |

### Tabel `email_log`

| Kolom | Fungsi |
|-------|--------|
| `id` | Primary key otomatis. |
| `nomor` | Nomor antrian yang dipanggil. |
| `email` | Email tujuan. |
| `status` | Status log yang dicatat aplikasi. |
| `waktu` | Waktu log dibuat. |

Catatan akurasi: pada implementasi saat ini, log email dengan status `TERKIRIM` dicatat setelah thread email dimulai. Artinya, log tersebut menunjukkan bahwa proses pengiriman diminta oleh aplikasi, bukan bukti final bahwa email sudah masuk ke inbox pelanggan.

## Penggunaan Protokol TCP dan UDP

### 1. HTTP di atas TCP untuk aplikasi web

Browser berkomunikasi dengan Flask menggunakan HTTP. HTTP berjalan di atas TCP, sehingga proses membuka halaman, mengirim form, dan menekan tombol admin memakai koneksi yang andal dan berurutan.

Digunakan pada:

- `GET /` untuk melihat daftar antrian,
- `GET` dan `POST /daftar` untuk form pendaftaran,
- `GET /<SECRET>` untuk dashboard admin,
- `GET /<SECRET>/panggil/<nomor>` untuk memanggil pelanggan,
- `GET /<SECRET>/selesai/<nomor>` untuk menyelesaikan antrian,
- `GET /<SECRET>/db-view` untuk melihat database.

Kenapa memakai TCP:

- data form pelanggan tidak boleh hilang,
- response halaman harus diterima utuh,
- HTTP memang menggunakan TCP sebagai transport umum,
- cocok untuk komunikasi request-response antara browser dan server.

Bagaimana prosesnya:

1. Browser mengirim request HTTP ke server Flask pada port 5000.
2. Flask menerima request dan menjalankan route terkait.
3. Jika ada perubahan data, Flask menulis ke SQLite.
4. Flask mengirim response HTML kembali ke browser.

### 2. SMTP di atas TCP untuk email notifikasi

File `tcp_email_notif.py` menggunakan modul `smtplib` untuk membuat koneksi ke:

```text
smtp.gmail.com:587
```

Alur pengiriman email:

1. Aplikasi membuat koneksi TCP ke server SMTP Gmail.
2. Aplikasi menjalankan `ehlo()` untuk identifikasi klien.
3. Aplikasi menjalankan `starttls()` agar koneksi memakai TLS.
4. Aplikasi login dengan `EMAIL_PENGIRIM` dan `EMAIL_PASSWORD` dari `.env`.
5. Aplikasi mengirim email dengan `sendmail()`.
6. Koneksi ditutup dengan `quit()`.

Kenapa memakai TCP:

- SMTP memang berjalan di atas TCP,
- isi email harus dikirim berurutan dan utuh,
- proses login dan TLS membutuhkan koneksi yang stabil,
- jika koneksi gagal, program bisa menangkap error melalui exception.

Catatan penting: TCP membantu memastikan data terkirim utuh sampai endpoint koneksi SMTP, tetapi tidak menjamin email pasti dibaca atau pasti masuk inbox pelanggan. Setelah diterima server SMTP, email masih bisa diproses, ditunda, masuk spam, atau ditolak oleh sistem email tujuan.

### 3. UDP broadcast untuk status antrian real-time di LAN

UDP digunakan untuk mengirim pesan status antrian ke listener tanpa membuat koneksi terlebih dahulu.

Pada `app.py`, server mengirim pesan ke:

```text
255.255.255.255:5005
```

Pada `udp_listener.py`, listener menerima pesan dari:

```text
0.0.0.0:5005
```

Alur UDP broadcast:

1. Admin menekan tombol `Panggil` atau `Tandai Selesai`.
2. Flask membuat pesan status antrian.
3. Fungsi `broadcast_udp()` membuat socket UDP.
4. Socket mengaktifkan opsi broadcast dengan `SO_BROADCAST`.
5. Pesan dikirim ke alamat broadcast `255.255.255.255` pada port 5005.
6. Program `udp_listener.py` yang berjalan di LAN menerima pesan dengan `recvfrom()` dan menampilkannya di terminal.

Kenapa memakai UDP:

- tidak perlu handshake seperti TCP,
- lebih ringan untuk pesan pendek,
- cocok untuk broadcast ke banyak penerima di jaringan lokal,
- server tidak perlu menyimpan daftar client yang sedang aktif,
- cocok untuk display antrian atau monitor lokal.

Keterbatasan UDP:

- tidak ada jaminan pesan sampai,
- tidak ada retry otomatis,
- urutan pesan tidak dijamin,
- firewall atau konfigurasi jaringan bisa memblokir broadcast.

Karena itu, UDP di aplikasi ini dipakai sebagai notifikasi cepat, bukan sebagai sumber data utama. Data utama tetap disimpan di SQLite dan ditampilkan melalui halaman web.

## Perbedaan Implementasi v1 dan v2

Folder pembanding v1: `C:\Users\acask8rawk\Documents\tugas s8\pemjar\m7\antrianCUci_kel1_v1`

| Aspek | Versi 1 | Versi 2 |
|------|---------|---------|
| Penyimpanan data | Menggunakan list Python `antrian` di memori. | Menggunakan SQLite `washqueue.db`. |
| Ketahanan data | Data hilang saat server restart. | Data tetap tersimpan selama database tidak dihapus. |
| Nomor antrian | Menggunakan variabel global `nomor_counter`. | Mengambil nomor berikutnya dari `MAX(nomor)` di database. |
| Route admin | Menggunakan `/admin`. | Menggunakan secret route berdasarkan `SECRET` di `app.py`. |
| Route panggil | `/panggil/<nomor>`. | `/<SECRET>/panggil/<nomor>`. |
| Route selesai | `/selesai/<nomor>`. | `/<SECRET>/selesai/<nomor>`. |
| Database viewer | Belum ada. | Ada route `/<SECRET>/db-view`. |
| Log email | Belum ada tabel log. | Ada tabel `email_log`. |
| Konfigurasi email | Membaca environment variable langsung dengan `os.getenv()`. | Menggunakan `load_dotenv()` agar `.env` dibaca otomatis. |
| UDP broadcast | Sudah ada untuk panggil dan selesai. | Tetap ada, dengan data yang terintegrasi ke database. |
| SMTP/TCP email | Sudah ada untuk notifikasi panggil. | Tetap ada dan dipanggil dari flow berbasis database. |
| Threading | Sudah digunakan untuk UDP dan email. | Tetap digunakan agar proses jaringan berjalan di background. |
| Tampilan | Berdasarkan file v1 yang tersedia, fokus utama ada pada logic Flask dan route sederhana. | Template v2 lebih lengkap: halaman publik, form daftar, dashboard admin, dan database viewer. |

Inti pengembangan v2 adalah perubahan dari sistem antrian sementara berbasis memori menjadi sistem yang lebih persisten dan mudah dipantau melalui SQLite, secret admin route, database viewer, dan email log.

## Alur Kerja Sistem

### Alur pelanggan mendaftar

```text
Pelanggan buka /daftar
        |
        v
Mengisi jenis kendaraan, nama, no HP, email
        |
        v
Flask menerima POST /daftar melalui HTTP/TCP
        |
        v
Nomor antrian dihitung dari database
        |
        v
Data disimpan ke tabel antrian dengan status Menunggu
        |
        v
Pelanggan diarahkan ke halaman /
```

### Alur admin memanggil pelanggan

```text
Admin buka dashboard secret route
        |
        v
Admin klik Panggil
        |
        v
Flask update status menjadi Dipanggil
        |
        +--> Thread UDP broadcast ke port 5005
        |
        +--> Thread SMTP/TCP email ke pelanggan
        |
        v
Log email dicatat ke email_log
        |
        v
Admin kembali ke dashboard
```

### Alur admin menyelesaikan antrian

```text
Admin klik Tandai Selesai
        |
        v
Flask update status menjadi Selesai
        |
        v
Thread UDP broadcast mengirim pesan selesai
        |
        v
Admin kembali ke dashboard
```

## Catatan Akurasi terhadap PDF Presentasi

PDF `T7_Pemjar_WashQueue_Kel1.pdf` secara umum sudah sesuai dengan implementasi v2:

- anggota kelompok sesuai,
- aplikasi menggunakan Flask Python,
- database menggunakan SQLite `washqueue.db`,
- frontend menggunakan HTML/CSS template Flask,
- HTTP digunakan untuk browser dan server Flask,
- SMTP/TCP digunakan pada `tcp_email_notif.py`,
- UDP broadcast digunakan pada `udp_listener.py` port 5005,
- admin memakai secret route,
- proses UDP dan email pada aksi panggil dijalankan dengan `threading`.

Namun ada beberapa catatan agar penjelasan lebih tepat:

1. Klaim bahwa email “pasti diterima” perlu diperhalus. TCP menjamin koneksi lebih andal sampai server SMTP, tetapi tidak menjamin email pasti masuk inbox pelanggan.
2. Pengujian pada PDF yang menyebut email diterima pelanggan tidak bisa dibuktikan hanya dari source code. Itu perlu bukti runtime, misalnya screenshot email masuk atau log SMTP sukses.
3. Tabel `email_log` saat ini mencatat status `TERKIRIM` setelah thread email dimulai, bukan setelah fungsi email mengembalikan hasil sukses.
4. Pada bagian pengembangan lanjutan, “Dashboard khusus admin” sebenarnya sudah ada dalam bentuk secret route. Jika ingin dijadikan pengembangan berikutnya, istilah yang lebih tepat adalah “login admin” atau “autentikasi admin”.
5. Ada typo kecil pada PDF: “Tambahkah login user” sebaiknya menjadi “Tambahkan login user”.

## Keterbatasan dan Pengembangan Lanjutan

Beberapa hal yang masih bisa dikembangkan:

1. Menambahkan login admin agar secret route tidak menjadi satu-satunya perlindungan dashboard.
2. Memperbaiki status `email_log` agar benar-benar mencatat sukses atau gagal berdasarkan hasil pengiriman email.
3. Menambahkan validasi nomor HP dan email di sisi backend.
4. Menambahkan tombol hapus/reset antrian untuk operasional harian.
5. Menambahkan halaman riwayat pelanggan untuk pelanggan tetap atau loyalty point.
6. Menambahkan auto-refresh atau WebSocket/SSE pada halaman antrian publik agar status berubah tanpa reload manual.
7. Menambahkan test otomatis untuk route Flask, database, dan fungsi broadcast.

## Kesimpulan

WashQueue v2 menerapkan konsep Pemrograman Jaringan melalui kombinasi HTTP/TCP, SMTP/TCP, dan UDP broadcast. TCP dipakai untuk komunikasi yang membutuhkan keandalan, seperti web dan email. UDP dipakai untuk broadcast cepat di jaringan lokal. SQLite membuat data antrian lebih persisten dibanding versi 1 yang masih memakai list di memori.
