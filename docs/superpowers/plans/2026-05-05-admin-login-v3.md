# Admin Login v3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the secret admin URL with real authenticated admin access backed by SQLite sessions and password hashes.

**Architecture:** Keep the existing Flask app as the web entry point, add an `admin_users` table in SQLite, store login state in Flask session, and protect every admin-only route with a decorator. Admin accounts are created manually through a small terminal script, while the public queue pages, UDP broadcast, and SMTP email flow stay intact.

**Tech Stack:** Python, Flask, SQLite3, Jinja2 templates, Werkzeug security helpers, python-dotenv, standard library (`getpass`, `tempfile`, `unittest`, `sqlite3`, `functools`, `os`).

---

### Task 1: Add admin authentication and route protection

**Files:**
- Modify: `app.py:1-230`
- Create: `tests/test_admin_auth.py`

- [ ] **Step 1: Write the failing test**

```python
import os
import sqlite3
import tempfile
import unittest
from werkzeug.security import generate_password_hash

import app as washqueue


class AdminAuthTests(unittest.TestCase):
    def setUp(self):
        self.fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.fd)
        washqueue.DB_NAME = self.db_path
        washqueue.app.config["TESTING"] = True
        washqueue.app.secret_key = "test-secret"
        washqueue.init_db()
        self.client = washqueue.app.test_client()
        self._seed_admin()
        self._seed_queue()

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def _seed_admin(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO admin_users (username, password_hash) VALUES (?, ?)",
            ("admin", generate_password_hash("admin123")),
        )
        conn.commit()
        conn.close()

    def _seed_queue(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO antrian (nomor, nama, jenis, email, no_hp, status) VALUES (?, ?, ?, ?, ?, ?)",
            (1, "Budi", "Motor", "budi@example.com", "08123456789", "Menunggu"),
        )
        conn.commit()
        conn.close()

    def test_admin_redirects_to_login_when_not_authenticated(self):
        response = self.client.get("/admin", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.headers["Location"])

    def test_login_rejects_wrong_password(self):
        response = self.client.post(
            "/admin/login",
            data={"username": "admin", "password": "salah"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Username atau password salah", response.data)

    def test_login_sets_session_and_unlocks_dashboard(self):
        with self.client as client:
            response = client.post(
                "/admin/login",
                data={"username": "admin", "password": "admin123"},
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 302)
            self.assertIn("/admin", response.headers["Location"])
            with client.session_transaction() as sess:
                self.assertEqual(sess["admin_username"], "admin")
            dashboard = client.get("/admin")
            self.assertEqual(dashboard.status_code, 200)
            self.assertIn(b"Dashboard Admin", dashboard.data)

    def test_admin_actions_require_login(self):
        response = self.client.get("/admin/panggil/1", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.headers["Location"])

    def test_logout_clears_session(self):
        with self.client as client:
            client.post(
                "/admin/login",
                data={"username": "admin", "password": "admin123"},
            )
            response = client.get("/admin/logout", follow_redirects=False)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/admin/login", response.headers["Location"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m unittest discover -s tests -p "test_admin_auth.py" -v
```

Expected: FAIL because `/admin/login`, `/admin/logout`, and the auth decorator do not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Add these imports near the top of `app.py`:

```python
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash, generate_password_hash
```

Set the Flask secret key from `.env`:

```python
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "washqueue-dev-secret")
```

Add a shared database connection helper and the admin lookup helper:

```python
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def get_admin_by_username(username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, password_hash FROM admin_users WHERE username = ?",
        (username,),
    )
    admin = cursor.fetchone()
    conn.close()
    return admin
```

Extend `init_db()` so it creates the admin table too:

```python
cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')
```

Add the session guard decorator:

```python
def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped
```

Add login and logout routes:

```python
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            error = 'Username dan password wajib diisi.'
        else:
            admin = get_admin_by_username(username)
            if admin and check_password_hash(admin['password_hash'], password):
                session['admin_id'] = admin['id']
                session['admin_username'] = admin['username']
                return redirect(url_for('admin'))
            error = 'Username atau password salah.'
    return render_template('login.html', error=error)


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))
```

Replace the old secret-route admin handlers with canonical admin paths and protect them:

```python
@app.route('/admin')
@admin_required
def admin():
    return render_template('admin.html', antrian=get_antrian(), admin_username=session.get('admin_username'))


@app.route('/admin/panggil/<int:nomor>')
@admin_required
def panggil(nomor):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT nama, email FROM antrian WHERE nomor = ?", (nomor,))
    data = cursor.fetchone()

    if data:
        nama, email = data
        cursor.execute("UPDATE antrian SET status = 'Dipanggil' WHERE nomor = ?", (nomor,))
        conn.commit()

        pesan = f"[ANTRIAN] Nomor {nomor} - {nama} dipanggil!"
        threading.Thread(target=broadcast_udp, args=(pesan,)).start()
        threading.Thread(target=kirim_email_notifikasi, args=(email, nama, nomor)).start()
        save_email_log(nomor, email, 'TERKIRIM')

    conn.close()
    return redirect(url_for('admin'))


@app.route('/admin/selesai/<int:nomor>')
@admin_required
def selesai(nomor):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE antrian SET status = 'Selesai' WHERE nomor = ?", (nomor,))
    conn.commit()
    conn.close()

    pesan = f"[ANTRIAN] Nomor {nomor} selesai. Terima kasih!"
    threading.Thread(target=broadcast_udp, args=(pesan,)).start()
    return redirect(url_for('admin'))


@app.route('/admin/db-view')
@admin_required
def db_view():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM antrian")
    antrian_rows = cursor.fetchall()
    cursor.execute("SELECT * FROM email_log")
    email_rows = cursor.fetchall()
    conn.close()
    return render_template('db_view.html', antrian_rows=antrian_rows, email_rows=email_rows)
```

Remove the `SECRET` constant and every `/{SECRET}` route path usage from `app.py`. Replace matching template links so admin access uses login-protected `/admin` routes.

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
python -m unittest discover -s tests -p "test_admin_auth.py" -v
```

Expected: PASS for the redirect, login failure, login success, logout, and route protection cases.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_admin_auth.py
git commit -m "feat: add authenticated admin access"
```

---

### Task 2: Add manual admin creation script

**Files:**
- Modify: `app.py:1-260`
- Create: `create_admin.py`
- Modify: `tests/test_admin_auth.py:1-220`

- [ ] **Step 1: Write the failing test**

Add this test method to `tests/test_admin_auth.py`:

```python
    def test_create_admin_user_hashes_password_and_rejects_duplicate(self):
        washqueue.create_admin_user("root", "secret")
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT username, password_hash FROM admin_users WHERE username = ?",
            ("root",),
        ).fetchone()
        self.assertEqual(row[0], "root")
        self.assertNotEqual(row[1], "secret")
        conn.close()

        with self.assertRaises(ValueError):
            washqueue.create_admin_user("root", "another")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m unittest discover -s tests -p "test_admin_auth.py" -v
```

Expected: FAIL because `create_admin_user()` does not exist yet.

- [ ] **Step 3: Write the minimal implementation**

Add this helper to `app.py` near the other database helpers:

```python
def create_admin_user(username, password):
    username = username.strip()
    if not username or not password:
        raise ValueError('Username dan password wajib diisi.')

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM admin_users WHERE username = ?", (username,))
    if cursor.fetchone():
        conn.close()
        raise ValueError('Username sudah digunakan.')

    cursor.execute(
        "INSERT INTO admin_users (username, password_hash) VALUES (?, ?)",
        (username, generate_password_hash(password)),
    )
    conn.commit()
    conn.close()
```

Create `create_admin.py` with an interactive terminal flow:

```python
from getpass import getpass

from app import create_admin_user, init_db


def main():
    init_db()
    username = input('Username admin: ').strip()
    password = getpass('Password admin: ')
    confirm = getpass('Konfirmasi password: ')

    if password != confirm:
        print('Password tidak cocok.')
        return 1

    try:
        create_admin_user(username, password)
    except ValueError as exc:
        print(str(exc))
        return 1

    print(f"Akun admin '{username}' berhasil dibuat.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
python -m unittest discover -s tests -p "test_admin_auth.py" -v
```

Expected: PASS, and the admin row should be stored with a password hash.

- [ ] **Step 5: Commit**

```bash
git add app.py create_admin.py tests/test_admin_auth.py
git commit -m "feat: add manual admin account creation"
```

---

### Task 3: Replace secret admin UI with authenticated templates

**Files:**
- Create: `templates/login.html`
- Modify: `templates/admin.html:1-374`
- Modify: `templates/db_view.html:1-40`
- Modify: `tests/test_admin_auth.py:1-260`

- [ ] **Step 1: Write the failing test**

Add these UI assertions to `tests/test_admin_auth.py`:

```python
    def test_login_page_renders_form(self):
        response = self.client.get('/admin/login')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login Admin', response.data)
        self.assertIn(b'Username', response.data)
        self.assertIn(b'Password', response.data)

    def test_dashboard_shows_logout_and_admin_name(self):
        with self.client as client:
            client.post(
                '/admin/login',
                data={'username': 'admin', 'password': 'admin123'},
            )
            response = client.get('/admin')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Keluar', response.data)
            self.assertIn(b'admin', response.data)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python -m unittest discover -s tests -p "test_admin_auth.py" -v
```

Expected: FAIL because the login template and the authenticated admin labels are not in the UI yet.

- [ ] **Step 3: Write the minimal implementation**

Create `templates/login.html`:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Login Admin — WashQueue</title>
  <style>
    body { font-family: Arial, sans-serif; background: #0d1117; color: #e6edf3; margin: 0; }
    .wrap { max-width: 420px; margin: 5rem auto; padding: 2rem; background: #161b22; border: 1px solid #30363d; border-radius: 12px; }
    label { display: block; margin: 1rem 0 0.35rem; }
    input { width: 100%; padding: 0.75rem; border-radius: 8px; border: 1px solid #30363d; background: #21262d; color: #e6edf3; }
    button { width: 100%; margin-top: 1.2rem; padding: 0.8rem; border: 0; border-radius: 8px; background: #00d4aa; font-weight: 700; }
    .error { margin-top: 1rem; color: #f85149; }
  </style>
</head>
<body>
  <main class="wrap">
    <h1>Login Admin</h1>
    <p>Masuk untuk mengakses dashboard admin.</p>
    {% if error %}
    <p class="error">{{ error }}</p>
    {% endif %}
    <form method="POST" action="/admin/login">
      <label for="username">Username</label>
      <input id="username" name="username" type="text" autocomplete="username" required />
      <label for="password">Password</label>
      <input id="password" name="password" type="password" autocomplete="current-password" required />
      <button type="submit">Masuk</button>
    </form>
  </main>
</body>
</html>
```

Update `templates/admin.html` so the header shows the active admin and a logout button, and all action links use the canonical `/admin` route family:

```html
<div class="admin-header">
  <div>
    <h1>Dashboard Admin</h1>
    <p>Login sebagai {{ admin_username }} · TCP/HTTP + UDP Broadcast aktif</p>
  </div>
  <div class="card-actions">
    <a href="/admin/db-view" class="btn btn-db">🗄️ Lihat Database</a>
    <a href="/admin/logout" class="btn btn-done">Keluar</a>
  </div>
</div>
```

Replace queue-action links in the admin cards:

```html
<a href="/admin/panggil/{{ item.nomor }}" class="btn btn-call">📢 Panggil</a>
<a href="/admin/selesai/{{ item.nomor }}" class="btn btn-done">✅ Tandai Selesai</a>
```

Update `templates/db_view.html` so the top of the page provides a clean way back to the authenticated dashboard:

```html
<p style="margin-bottom: 1rem;">
  <a href="/admin">← Kembali ke dashboard</a> |
  <a href="/admin/logout">Logout</a>
</p>
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
python -m unittest discover -s tests -p "test_admin_auth.py" -v
```

Expected: PASS, and the HTML responses should contain the login form, admin name, and logout button.

- [ ] **Step 5: Commit**

```bash
git add templates/login.html templates/admin.html templates/db_view.html tests/test_admin_auth.py
git commit -m "feat: add admin login and authenticated dashboard ui"
```

---

### Task 4: Refresh README for v3 and validate setup flow

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the failing doc check**

Use a simple content check so the README change is treated like a real deliverable:

```bash
grep -q "FLASK_SECRET_KEY\|create_admin.py\|/admin/login\|admin_required" README.md
```

Expected before the update: exit code 1 because the README does not yet document the v3 login flow clearly enough.

- [ ] **Step 2: Run the check to verify it fails**

Run:

```bash
grep -q "FLASK_SECRET_KEY\|create_admin.py\|/admin/login\|admin_required" README.md
```

Expected: exit code 1 before the README update.

- [ ] **Step 3: Write the minimal implementation**

Update the README setup section so it includes this order:

```text
1. clone dari GitHub
2. buat virtual environment
3. install Flask dan python-dotenv
4. isi .env dengan EMAIL_PENGIRIM, EMAIL_PASSWORD, dan FLASK_SECRET_KEY
5. jalankan create_admin.py untuk membuat akun admin
6. jalankan app.py
7. login ke /admin/login
```

Add the `.env` example:

```env
EMAIL_PENGIRIM=email_pengirim@gmail.com
EMAIL_PASSWORD=app_password_gmail
FLASK_SECRET_KEY=isi_dengan_string_rahasia_panjang
```

Add a v2 vs v3 comparison table that states:

- v2: secret route admin
- v3: authenticated admin login with SQLite session
- v3: manual admin creation script
- v3: same UDP and SMTP behavior remains

- [ ] **Step 4: Run the check to verify it passes**

Run:

```bash
grep -n "FLASK_SECRET_KEY\|create_admin.py\|/admin/login\|admin_required" README.md
```

Expected: matches are present and the README clearly explains the v3 flow.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: update washqueue v3 admin login guide"
```

---

### Task 5: Final regression and smoke-test pass

**Files:**
- No code changes expected unless a test uncovers a real bug

- [ ] **Step 1: Run the full regression suite**

Run:

```bash
python -m unittest discover -s tests -p "test_admin_auth.py" -v
```

Expected: all admin-auth tests pass.

- [ ] **Step 2: Compile the Python files**

Run:

```bash
python -m py_compile app.py create_admin.py tcp_email_notif.py udp_listener.py cek_db.py
```

Expected: no syntax errors.

- [ ] **Step 3: Manual smoke test the login flow**

Run:

```bash
python create_admin.py
python app.py
```

Then verify in a browser:

- `/admin` redirects to `/admin/login` when logged out
- login succeeds with the created admin account
- `/admin/panggil/<nomor>` and `/admin/selesai/<nomor>` still trigger the existing queue flow after login
- logout returns you to the login page

- [ ] **Step 4: Check the working tree before staging**

Run:

```bash
git status --short
```

Expected: only the source files, templates, tests, and README are changed. Do **not** stage `washqueue.db` unless there is an intentional schema migration that must be committed.

- [ ] **Step 5: Commit only the intended source changes**

```bash
git add app.py create_admin.py templates/login.html templates/admin.html templates/db_view.html tests/test_admin_auth.py README.md
git commit -m "feat: ship authenticated admin login v3"
```
