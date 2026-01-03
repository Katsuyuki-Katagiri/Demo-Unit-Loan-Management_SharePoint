import sqlite3
import os

DB_PATH = os.path.join("data", "app.db")
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

try:
    c.execute("DELETE FROM categories WHERE name='Cat A'")
    c.execute("DELETE FROM device_types WHERE name='Type A'")
    conn.commit()
    print("Successfully deleted Cat A and Type A")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
