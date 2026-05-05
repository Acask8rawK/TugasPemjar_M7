from getpass import getpass

from app import create_admin_user, init_db


def main():
    init_db()
    username = input("Username admin: ").strip()
    password = getpass("Password admin: ")
    confirm = getpass("Konfirmasi password: ")

    if password != confirm:
        print("Password tidak cocok.")
        return 1

    try:
        create_admin_user(username, password)
    except ValueError as exc:
        print(str(exc))
        return 1

    print(f"Akun admin '{username}' berhasil dibuat.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
