import socket
import threading
import sqlite3
from flask import Flask, render_template, request, redirect, url_for
from tcp_email_notif import kirim_email_notifikasi

app = Flask(__name__)

DB_NAME = 'washqueue.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS antrian (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nomor INTEGER,
            nama TEXT,
            jenis TEXT,
            email TEXT,
            no_hp TEXT,
            status TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nomor INTEGER,
            email TEXT,
            status TEXT,
            waktu TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()

init_db()

def get_antrian():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT nomor, nama, jenis, email, no_hp, status FROM antrian")
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "nomor": r[0],
            "nama": r[1],
            "jenis": r[2],
            "email": r[3],
            "no_hp": r[4],
            "status": r[5]
        }
        for r in rows
    ]


def get_next_nomor():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT MAX(nomor) FROM antrian")
    result = cursor.fetchone()[0]

    conn.close()
    return 1 if result is None else result + 1


UDP_IP = '255.255.255.255'
UDP_PORT = 5005

def broadcast_udp(pesan):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(pesan.encode(), (UDP_IP, UDP_PORT))
    sock.close()
    print(f"[UDP] {pesan}")


def save_email_log(nomor, email, status):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO email_log (nomor, email, status)
        VALUES (?, ?, ?)
    """, (nomor, email, status))

    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html', antrian=get_antrian())


@app.route('/daftar', methods=['GET', 'POST'])
def daftar():
    if request.method == 'POST':
        nama  = request.form['nama']
        jenis = request.form['jenis']
        email = request.form['email']
        no_hp = request.form['no_hp']

        nomor = get_next_nomor()

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO antrian (nomor, nama, jenis, email, no_hp, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (nomor, nama, jenis, email, no_hp, 'Menunggu'))

        conn.commit()
        conn.close()

        return redirect(url_for('index'))

    return render_template('daftar.html')

@app.route('/admin')
def admin():
    return render_template('admin.html', antrian=get_antrian())

@app.route('/panggil/<int:nomor>')
def panggil(nomor):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT nama, email FROM antrian WHERE nomor = ?", (nomor,))
    data = cursor.fetchone()

    if data:
        nama, email = data

        cursor.execute("""
            UPDATE antrian SET status = 'Dipanggil'
            WHERE nomor = ?
        """, (nomor,))
        conn.commit()

        pesan = f"[ANTRIAN] Nomor {nomor} - {nama} dipanggil!"
        threading.Thread(target=broadcast_udp, args=(pesan,)).start()

        threading.Thread(
            target=kirim_email_notifikasi,
            args=(email, nama, nomor)
        ).start()

        save_email_log(nomor, email, 'TERKIRIM')

    conn.close()
    return redirect(url_for('admin'))

@app.route('/selesai/<int:nomor>')
def selesai(nomor):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE antrian SET status = 'Selesai'
        WHERE nomor = ?
    """, (nomor,))

    conn.commit()
    conn.close()

    pesan = f"[ANTRIAN] Nomor {nomor} selesai. Terima kasih!"
    threading.Thread(target=broadcast_udp, args=(pesan,)).start()

    return redirect(url_for('admin'))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
    
    
    import os
print("DB YANG DIPAKAI FLASK:", os.path.abspath("washqueue.db"))
