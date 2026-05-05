# Admin Login v3 Design

## Goal

Implement v3 admin authentication for WashQueue so only authenticated admins can access the admin dashboard and admin-only actions. The implementation must stay within the current project stack: Flask, SQLite, Jinja templates, and standard Python libraries plus existing Flask/Werkzeug dependencies.

## Current State

WashQueue v2 protects admin pages using a secret route stored in `SECRET` inside `app.py`. This hides admin links from public navigation, but it is not real authentication. Anyone who knows the secret URL can access the admin dashboard, call queue numbers, mark queues complete, and view database rows.

## Selected Approach

Use Flask sessions with admin accounts stored in SQLite.

- Admin accounts live in a new `admin_users` table.
- Passwords are stored using Werkzeug password hashes.
- Login state is stored in the Flask session.
- Admin-only routes are protected with an `admin_required` decorator.
- Admin accounts are created manually using a script, not through a public registration page.

This approach keeps the feature aligned with the existing SQLite-based v2 architecture while avoiding a larger admin management UI.

## Route Design

Public routes remain accessible without login:

- `/`
- `/daftar`

New authentication routes:

- `/admin/login` — shows and processes the admin login form.
- `/admin/logout` — clears the admin session and redirects to login.

Protected admin routes:

- `/admin`
- `/admin/panggil/<nomor>`
- `/admin/selesai/<nomor>`
- `/admin/db-view`

The old secret route should no longer be the main protection mechanism. Admin protection comes from login session checks.

## Database Design

Add a new table during `init_db()`:

```sql
CREATE TABLE IF NOT EXISTS admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

Existing tables remain unchanged:

- `antrian`
- `email_log`

## Admin Account Creation

Add `create_admin.py` as a manual terminal script.

Expected behavior:

1. Ask for username.
2. Ask for password without echoing it to the terminal.
3. Ask for password confirmation.
4. Hash the password using `generate_password_hash()`.
5. Insert the account into `admin_users`.
6. Reject duplicate usernames.
7. Print a clear success or error message.

This keeps account creation private to the person operating the project files.

## Session Behavior

After successful login, store these session values:

- `admin_id`
- `admin_username`

The `admin_required` decorator checks for `admin_id`. If missing, it redirects to `/admin/login`.

Logout clears the session and redirects to `/admin/login`.

## Template Changes

Add:

- `templates/login.html` for the admin login page.

Update:

- `templates/admin.html` to show the logged-in admin username and a logout button.

Keep:

- `templates/index.html` public.
- `templates/daftar.html` public.
- `templates/db_view.html` with the same table layout; only links pointing back to admin should use `/admin`.

## Configuration

Use Flask `app.secret_key` for session signing.

Preferred source:

- `FLASK_SECRET_KEY` from `.env`.

Local fallback:

- Use a hardcoded development fallback only when `FLASK_SECRET_KEY` is missing so the local demo still runs; README must instruct users to set `FLASK_SECRET_KEY` in `.env`.

## Error Handling

Login form should handle:

- empty username or password,
- username not found,
- wrong password.

For all login failures, show a simple error message and do not reveal whether the username or password was wrong.

`create_admin.py` should handle:

- duplicate username,
- password confirmation mismatch,
- empty username/password,
- database connection errors.

## Security Boundaries

Included in v3:

- SQLite-backed admin accounts,
- password hashing,
- login/logout session flow,
- route-level access control for admin pages,
- no plaintext admin password in source code.

Not included in v3:

- public admin registration,
- password reset,
- multiple roles,
- CSRF protection,
- HTTPS deployment configuration,
- rate limiting.

Those items can be later improvements, but they are outside the current task scope.

## Data Flow

### Admin Login

```text
Admin opens /admin
        |
        v
Not logged in
        |
        v
Redirect to /admin/login
        |
        v
Submit username and password
        |
        v
Lookup username in admin_users
        |
        v
Check password hash
        |
        +--> valid: set session and redirect to /admin
        |
        +--> invalid: stay on login page with error
```

### Protected Admin Action

```text
Admin requests /admin/panggil/<nomor>
        |
        v
admin_required checks session
        |
        +--> no session: redirect to /admin/login
        |
        +--> session exists: continue route
        |
        v
Update queue status, send UDP broadcast, send email thread, log email
```

## README Updates

README should be updated for v3 with:

- `FLASK_SECRET_KEY` in `.env`,
- how to run `create_admin.py`,
- how to login at `/admin/login`,
- that admin dashboard is protected by authentication instead of secret URL,
- updated v2 vs v3 comparison.

## Verification Plan

After implementation, verify with:

1. `python -m py_compile app.py create_admin.py tcp_email_notif.py udp_listener.py cek_db.py`
2. Create an admin using `create_admin.py`.
3. Start Flask with `python app.py`.
4. Confirm `/admin` redirects to `/admin/login` when not logged in.
5. Confirm wrong password shows an error.
6. Confirm correct login opens `/admin`.
7. Confirm `/admin/db-view`, `/admin/panggil/<nomor>`, and `/admin/selesai/<nomor>` require login.
8. Confirm logout clears access and redirects back to login.
9. Confirm public routes `/` and `/daftar` still work.

## Success Criteria

- Admin panel cannot be accessed without login.
- Admin actions cannot be executed without login.
- Admin credentials are stored in SQLite with password hashes.
- Admin creation works through a manual script.
- Public queue and registration features remain accessible.
- Existing UDP and SMTP behavior remains connected to admin queue actions.
