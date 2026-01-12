import sqlite3
import os

DB_PATH = "data/app.db"
UPLOAD_DIR = "data/uploads"

def check_debug():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    print("--- Check Sessions ---")
    c.execute("SELECT id, session_type, device_photo_dir FROM check_sessions ORDER BY id DESC LIMIT 5")
    rows = c.fetchall()
    for r in rows:
        print(f"ID: {r['id']}, Type: {r['session_type']}, PhotoDir: '{r['device_photo_dir']}'")
        
        if r['device_photo_dir']:
            full_path = os.path.join(UPLOAD_DIR, r['device_photo_dir'])
            exists = os.path.exists(full_path)
            print(f"  -> Path: {full_path}, Exists: {exists}")
            if exists:
                files = os.listdir(full_path)
                print(f"  -> Files: {files}")
        else:
            print("  -> No Photo Dir Set")

    conn.close()

if __name__ == "__main__":
    check_debug()
