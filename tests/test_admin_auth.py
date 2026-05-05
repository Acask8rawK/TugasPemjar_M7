import os
import re
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import check_password_hash, generate_password_hash

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

    def _login(self, client):
        return client.post(
            "/admin/login",
            data={"username": "admin", "password": "admin123"},
            follow_redirects=False,
        )

    def _csrf_token(self, client):
        response = client.get("/admin")
        self.assertEqual(response.status_code, 200)
        match = re.search(r'name="_csrf_token" value="([^"]+)"', response.get_data(as_text=True))
        if match is None:
            self.fail("CSRF token tidak ditemukan di dashboard admin")
        return match.group(1)

    def _queue_status(self, nomor=1):
        conn = sqlite3.connect(self.db_path)
        status = conn.execute("SELECT status FROM antrian WHERE nomor = ?", (nomor,)).fetchone()[0]
        conn.close()
        return status

    def _email_log_count(self):
        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM email_log").fetchone()[0]
        conn.close()
        return count

    def test_admin_redirects_to_login_when_not_authenticated(self):
        response = self.client.get("/admin", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.headers["Location"])

    def test_admin_actions_require_login(self):
        response = self.client.post("/admin/panggil/1", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.headers["Location"])

    def test_selesai_requires_login(self):
        response = self.client.post("/admin/selesai/1", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.headers["Location"])

    def test_db_view_requires_login(self):
        response = self.client.get("/admin/db-view", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login", response.headers["Location"])

    def test_login_rejects_wrong_password(self):
        response = self.client.post(
            "/admin/login",
            data={"username": "admin", "password": "salah"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Username atau password salah", response.data)

    def test_login_page_renders_form(self):
        response = self.client.get("/admin/login")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Login Admin", response.data)
        self.assertIn(b"Username", response.data)
        self.assertIn(b"Password", response.data)

    def test_dashboard_shows_logout_and_admin_name(self):
        with self.client as client:
            self._login(client)
            response = client.get("/admin")
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Keluar", response.data)
            self.assertIn(b"admin", response.data)

    def test_login_sets_session_and_unlocks_dashboard(self):
        with self.client as client:
            response = self._login(client)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/admin", response.headers["Location"])
            with client.session_transaction() as sess:
                self.assertEqual(sess["admin_username"], "admin")
            dashboard = client.get("/admin")
            self.assertEqual(dashboard.status_code, 200)
            self.assertIn(b"Dashboard Admin", dashboard.data)

    def test_invalid_admin_session_is_cleared(self):
        with self.client as client:
            with client.session_transaction() as sess:
                sess["admin_id"] = 999
                sess["admin_username"] = "ghost"
            response = client.get("/admin", follow_redirects=False)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/admin/login", response.headers["Location"])
            with client.session_transaction() as sess:
                self.assertNotIn("admin_id", sess)

    def test_create_admin_user_hashes_password_and_rejects_duplicates(self):
        created = washqueue.create_admin_user("  newadmin  ", "secret123")
        self.assertEqual(created["username"], "newadmin")
        self.assertNotEqual(created["password_hash"], "secret123")
        self.assertTrue(check_password_hash(created["password_hash"], "secret123"))

        with self.assertRaises(ValueError):
            washqueue.create_admin_user("newadmin", "another-secret")

    def test_admin_action_requires_csrf_token(self):
        with self.client as client:
            self._login(client)
            response = client.post("/admin/panggil/1", follow_redirects=False)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(self._queue_status(), "Menunggu")

    def test_admin_can_update_queue_with_post_and_csrf(self):
        with self.client as client:
            self._login(client)
            token = self._csrf_token(client)
            with patch.object(washqueue, "broadcast_udp"), patch.object(washqueue, "kirim_email_notifikasi"):
                panggil = client.post(
                    "/admin/panggil/1",
                    data={"_csrf_token": token},
                    follow_redirects=False,
                )
                self.assertEqual(panggil.status_code, 302)
                self.assertEqual(self._queue_status(), "Dipanggil")
                self.assertEqual(self._email_log_count(), 1)

                selesai = client.post(
                    "/admin/selesai/1",
                    data={"_csrf_token": token},
                    follow_redirects=False,
                )
                self.assertEqual(selesai.status_code, 302)
                self.assertEqual(self._queue_status(), "Selesai")

    def test_get_admin_actions_do_not_mutate_queue(self):
        with self.client as client:
            self._login(client)
            response = client.get("/admin/panggil/1", follow_redirects=False)
            self.assertEqual(response.status_code, 405)
            self.assertEqual(self._queue_status(), "Menunggu")

    def test_invalid_status_transition_does_not_change_queue_or_notify(self):
        with self.client as client:
            self._login(client)
            token = self._csrf_token(client)
            with patch.object(washqueue, "broadcast_udp") as broadcast, patch.object(
                washqueue, "kirim_email_notifikasi"
            ) as email:
                response = client.post(
                    "/admin/selesai/1",
                    data={"_csrf_token": token},
                    follow_redirects=False,
                )
            self.assertEqual(response.status_code, 302)
            self.assertEqual(self._queue_status(), "Menunggu")
            self.assertEqual(self._email_log_count(), 0)
            broadcast.assert_not_called()
            email.assert_not_called()

    def test_logout_clears_session(self):
        with self.client as client:
            self._login(client)
            token = self._csrf_token(client)
            response = client.post(
                "/admin/logout",
                data={"_csrf_token": token},
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 302)
            self.assertIn("/admin/login", response.headers["Location"])
            with client.session_transaction() as sess:
                self.assertNotIn("admin_id", sess)
