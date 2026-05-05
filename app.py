import os
import secrets
import socket
import sqlite3
import threading
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from tcp_email_notif import kirim_email_notifikasi

load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

DB_NAME = "washqueue.db"
UDP_IP = "255.255.255.255"
UDP_PORT = 5005


def configure_secret_key():
    secret_key = os.getenv("FLASK_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("FLASK_SECRET_KEY wajib diatur untuk menjalankan aplikasi.")
    app.secret_key = secret_key


def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS antrian (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nomor INTEGER,
            nama TEXT,
            jenis TEXT,
            email TEXT,
            no_hp TEXT,
            status TEXT
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nomor INTEGER,
            email TEXT,
            status TEXT,
            waktu TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def get_admin_by_username(username):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash FROM admin_users WHERE username = ?",
            (username,),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def get_admin_by_id(admin_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username, password_hash FROM admin_users WHERE id = ?",
            (admin_id,),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def create_admin_user(username, password):
    username = username.strip()
    if not username or not password:
        raise ValueError("Username dan password wajib diisi.")

    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM admin_users WHERE username = ?", (username,))
        if cursor.fetchone():
            raise ValueError("Username sudah digunakan.")

        cursor.execute(
            "INSERT INTO admin_users (username, password_hash) VALUES (?, ?)",
            (username, generate_password_hash(password)),
        )
        conn.commit()
    finally:
        conn.close()

    return get_admin_by_username(username)


def csrf_token():
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def validate_csrf_token(token):
    stored_token = session.get("_csrf_token")
    if not token or not stored_token or not secrets.compare_digest(token, stored_token):
        abort(400)


app.jinja_env.globals["csrf_token"] = csrf_token


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        admin_id = session.get("admin_id")
        if admin_id is None:
            return redirect(url_for("admin_login"))

        admin = get_admin_by_id(admin_id)
        if admin is None:
            session.clear()
            return redirect(url_for("admin_login"))

        session["admin_id"] = admin["id"]
        session["admin_username"] = admin["username"]
        return view(*args, **kwargs)

    return wrapped


def get_antrian():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT nomor, nama, jenis, email, no_hp, status FROM antrian")
    rows = cursor.fetchall()
    conn.close()
    return [
        {"nomor": r[0], "nama": r[1], "jenis": r[2], "email": r[3], "no_hp": r[4], "status": r[5]}
        for r in rows
    ]


def get_next_nomor():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(nomor) FROM antrian")
    result = cursor.fetchone()[0]
    conn.close()
    return 1 if result is None else result + 1


def broadcast_udp(pesan):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.sendto(pesan.encode(), (UDP_IP, UDP_PORT))
    sock.close()
    print(f"[UDP] {pesan}")


def save_email_log(nomor, email, status):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO email_log (nomor, email, status) VALUES (?, ?, ?)",
        (nomor, email, status),
    )
    conn.commit()
    conn.close()


# ─── ROUTE PUBLIK ────────────────────────────────────────────────


@app.route("/")
def index():
    return render_template("index.html", antrian=get_antrian())


@app.route("/daftar", methods=["GET", "POST"])
def daftar():
    if request.method == "POST":
        nama = request.form["nama"]
        jenis = request.form["jenis"]
        email = request.form["email"]
        no_hp = request.form["no_hp"]
        nomor = get_next_nomor()

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO antrian (nomor, nama, jenis, email, no_hp, status) VALUES (?, ?, ?, ?, ?, ?)",
            (nomor, nama, jenis, email, no_hp, "Menunggu"),
        )
        conn.commit()
        conn.close()
        return redirect(url_for("index"))

    return render_template("daftar.html")


# ─── ROUTE ADMIN ─────────────────────────────────────────────────


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            error = "Username dan password wajib diisi."
        else:
            admin = get_admin_by_username(username)
            if admin and check_password_hash(admin["password_hash"], password):
                session["admin_id"] = admin["id"]
                session["admin_username"] = admin["username"]
                return redirect(url_for("admin"))
            error = "Username atau password salah."

    return render_template("login.html", error=error)


@app.route("/admin/logout", methods=["POST"])
@admin_required
def admin_logout():
    validate_csrf_token(request.form.get("_csrf_token"))
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin():
    return render_template(
        "admin.html",
        antrian=get_antrian(),
        admin_username=session.get("admin_username"),
    )


@app.route("/admin/panggil/<int:nomor>", methods=["POST"])
@admin_required
def panggil(nomor):
    validate_csrf_token(request.form.get("_csrf_token"))
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT nama, email, status FROM antrian WHERE nomor = ?", (nomor,))
        data = cursor.fetchone()

        if data and data["status"] == "Menunggu":
            cursor.execute("UPDATE antrian SET status = 'Dipanggil' WHERE nomor = ?", (nomor,))
            conn.commit()

            pesan = f"[ANTRIAN] Nomor {nomor} - {data['nama']} dipanggil!"
            threading.Thread(target=broadcast_udp, args=(pesan,)).start()
            threading.Thread(target=kirim_email_notifikasi, args=(data["email"], data["nama"], nomor)).start()
            save_email_log(nomor, data["email"], "TERKIRIM")
    finally:
        conn.close()

    return redirect(url_for("admin"))


@app.route("/admin/selesai/<int:nomor>", methods=["POST"])
@admin_required
def selesai(nomor):
    validate_csrf_token(request.form.get("_csrf_token"))
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM antrian WHERE nomor = ?", (nomor,))
        data = cursor.fetchone()

        if data and data["status"] == "Dipanggil":
            cursor.execute("UPDATE antrian SET status = 'Selesai' WHERE nomor = ?", (nomor,))
            conn.commit()

            pesan = f"[ANTRIAN] Nomor {nomor} selesai. Terima kasih!"
            threading.Thread(target=broadcast_udp, args=(pesan,)).start()
    finally:
        conn.close()

    return redirect(url_for("admin"))


@app.route("/admin/db-view")
@admin_required
def db_view():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM antrian")
    antrian_rows = cursor.fetchall()
    cursor.execute("SELECT * FROM email_log")
    email_rows = cursor.fetchall()
    conn.close()
    return render_template("db_view.html", antrian_rows=antrian_rows, email_rows=email_rows)


def main():
    configure_secret_key()
    init_db()
    print("DB YANG DIPAKAI FLASK:", os.path.abspath(DB_NAME))
    print("Admin panel: http://127.0.0.1:5000/admin")
    app.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == "__main__":
    main()
