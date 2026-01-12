
import sqlite3
import json
import os

DB_PATH = os.path.join("data", "app.db")

def inspect_db():
    if not os.path.exists(DB_PATH):
        print(f"DB not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    print("--- SMTP Config ---")
    c.execute("SELECT value FROM system_settings WHERE key='smtp_config'")
    row = c.fetchone()
    if row:
        print(row['value'])
    else:
        print("No smtp_config found")

    print("\n--- Recent Notification Logs ---")
    try:
        c.execute("SELECT * FROM notification_logs ORDER BY id DESC LIMIT 5")
        rows = c.fetchall()
        for r in rows:
            print(dict(r))
    except Exception as e:
        print(f"Error reading logs: {e}")

    print("\n--- Users ---")
    c.execute("SELECT id, name, email FROM users")
    rows = c.fetchall()
    for r in rows:
        print(dict(r))

    conn.close()

if __name__ == "__main__":
    import sys
    # Redirect stdout to a file with utf-8 encoding
    with open("db_output.txt", "w", encoding="utf-8") as f:
        sys.stdout = f
        inspect_db()
