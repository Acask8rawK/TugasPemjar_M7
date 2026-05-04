import sqlite3

conn = sqlite3.connect("washqueue.db")
cursor = conn.cursor()

print("=== ANTRIAN ===")
cursor.execute("SELECT * FROM antrian")
for row in cursor.fetchall():
    print(row)

print("\n=== EMAIL LOG ===")
cursor.execute("SELECT * FROM email_log")
for row in cursor.fetchall():
    print(row)

conn.close()