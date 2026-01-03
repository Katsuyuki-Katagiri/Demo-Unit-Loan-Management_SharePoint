import os
import sqlite3
import shutil
from src.database import init_db, create_initial_admin, seed_categories, DB_PATH
import time

def verify_phase0():
    print("Starting Verification for Phase 0...")
    
    # 1. Clean environment
    if os.path.exists("data"):
        shutil.rmtree("data")
    print("[x] Cleaned data directory")
    
    # 2. Initialize DB
    init_db()
    if os.path.exists(DB_PATH):
        print("[x] Database created")
    else:
        print("[!] Database creation FAILED")
        return

    # 3. Verify Users table empty
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT count(*) FROM users")
    if c.fetchone()[0] == 0:
        print("[x] Users table is initially empty")
    else:
        print("[!] Users table NOT empty")
    
    # 4. Create Admin
    print("Attempting to create admin...")
    success = create_initial_admin("admin@example.com", "Admin User", "password123")
    if success:
        print("[x] Admin creation successful")
    else:
        print("[!] Admin creation FAILED")
        
    c.execute("SELECT * FROM users WHERE email='admin@example.com'")
    user = c.fetchone() # (id, email, hash, name, role)
    if user and user[3] == "Admin User" and user[4] == "admin":
        print("[x] Admin user data verified")
    else:
        print("[!] Admin user data verification FAILED")

    # 5. Verify Categories Seed
    seed_categories()
    c.execute("SELECT count(*) FROM categories")
    count = c.fetchone()[0]
    if count == 12:
        print("[x] Categories seeded correctly (12 items)")
    else:
        print(f"[!] Categories count mismatch: {count}")
    
    conn.close()
    
    print("Verification Phase 0 Completed.")

if __name__ == "__main__":
    verify_phase0()
