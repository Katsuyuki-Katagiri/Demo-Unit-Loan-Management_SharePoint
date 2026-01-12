
import sqlite3
import os
import datetime

DB_PATH = os.path.join("data", "demo_loan.db") # Correct DB Name from list_dir found 'demo_loan.db', logic.py imports DB_PATH from database.py. logic.py line 2 says from src.database import ..., DB_PATH.
# Wait, list_dir showed 'demo_loan.db'. Let's check src/database.py to be sure about DB_PATH.
from src.database import DB_PATH

def check_logs():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}!")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    print("--- Notification Logs (Last 10) ---")
    try:
        c.execute("SELECT * FROM notification_logs ORDER BY created_at DESC LIMIT 10")
        logs = c.fetchall()
        for l in logs:
            print(f"ID: {l['id']}, Type: {l['event_type']}, Recipient: {l['recipient']}, Status: {l['status']}, Error: {l['error_message']}, Time: {l['created_at']}")
    except Exception as e:
        print(f"Error querying logs: {e}")
        
    print("\n--- System Settings (SMTP) ---")
    try:
        c.execute("SELECT * FROM system_settings WHERE key = 'smtp_config'")
        setting = c.fetchone()
        if setting:
            print(f"SMTP Config: {setting['value']}")
        else:
            print("No SMTP Config found in system_settings.")
    except Exception as e:
        print(f"Error querying settings: {e}")

    conn.close()

if __name__ == "__main__":
    check_logs()
