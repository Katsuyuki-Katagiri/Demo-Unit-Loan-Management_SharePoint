import sqlite3
import os
from typing import Optional, List, Tuple, Dict, Any
import bcrypt

DB_PATH = os.path.join("data", "app.db")
UPLOAD_DIR = os.path.join("data", "uploads")

def init_db():
    """Initialize the database with all tables for Phase 1."""
    os.makedirs("data", exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Phase 0 Tables
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash BLOB NOT NULL,
            name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    
    # Phase 1 Tables
    # Device Types (機種)
    c.execute('''
        CREATE TABLE IF NOT EXISTS device_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
    ''')

    # Items (構成品)
    c.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            tips TEXT,
            photo_path TEXT
        )
    ''')

    # Template Lines (機種ごとの必要構成品)
    c.execute('''
        CREATE TABLE IF NOT EXISTS template_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_type_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            required_qty INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER DEFAULT 0,
            FOREIGN KEY (device_type_id) REFERENCES device_types (id),
            FOREIGN KEY (item_id) REFERENCES items (id)
        )
    ''')

    # Device Units (個体/ロット)
    c.execute('''
        CREATE TABLE IF NOT EXISTS device_units (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_type_id INTEGER NOT NULL,
            lot_number TEXT NOT NULL,
            mfg_date TEXT,
            location TEXT,
            note TEXT,
            status TEXT DEFAULT 'in_stock',
            FOREIGN KEY (device_type_id) REFERENCES device_types (id),
            UNIQUE(device_type_id, lot_number)
        )
    ''')

    # Unit Overrides (個体差分)
    c.execute('''
        CREATE TABLE IF NOT EXISTS unit_overrides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_unit_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            action TEXT NOT NULL, -- 'add', 'remove', 'qty'
            qty INTEGER, -- Used for 'add' or 'qty' action
            FOREIGN KEY (device_unit_id) REFERENCES device_units (id),
            FOREIGN KEY (item_id) REFERENCES items (id)
        )
    ''')
    
    

    # Phase 2 Tables
    # Loans (貸出)
    c.execute('''
        CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_unit_id INTEGER NOT NULL,
            checkout_date TEXT NOT NULL,
            destination TEXT NOT NULL,
            purpose TEXT NOT NULL,
            checker_user_id INTEGER, -- Optional: ID of user who performed checkout
            status TEXT DEFAULT 'open', -- open, closed
            canceled INTEGER DEFAULT 0, -- 0: false, 1: true
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (device_unit_id) REFERENCES device_units (id)
        )
    ''')

    # Check Sessions (チェック単位)
    c.execute('''
        CREATE TABLE IF NOT EXISTS check_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_type TEXT NOT NULL, -- 'checkout', 'return'
            loan_id INTEGER,
            device_unit_id INTEGER NOT NULL,
            performed_by TEXT, -- User name or ID
            performed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            device_photo_dir TEXT, -- Path to directory containing session photos
            canceled INTEGER DEFAULT 0,
            FOREIGN KEY (loan_id) REFERENCES loans (id),
            FOREIGN KEY (device_unit_id) REFERENCES device_units (id)
        )
    ''')

    # Check Lines (構成品ごとの結果)
    c.execute('''
        CREATE TABLE IF NOT EXISTS check_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            check_session_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            required_qty INTEGER NOT NULL,
            result TEXT NOT NULL, -- 'OK', 'NG'
            ng_reason TEXT, -- 'lost', 'damaged', 'missing_qty'
            found_qty INTEGER, -- If missing_qty, how many found?
            comment TEXT,
            FOREIGN KEY (check_session_id) REFERENCES check_sessions (id),
            FOREIGN KEY (item_id) REFERENCES items (id)
        )
    ''')

    # Issues (要対応)
    c.execute('''
        CREATE TABLE IF NOT EXISTS issues (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_unit_id INTEGER NOT NULL,
            check_session_id INTEGER,
            status TEXT DEFAULT 'open', -- open, closed
            summary TEXT, -- e.g. "Missing power cord"
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            resolved_at TEXT,
            resolved_by TEXT,
            FOREIGN KEY (device_unit_id) REFERENCES device_units (id),
            FOREIGN KEY (check_session_id) REFERENCES check_sessions (id)
        )
    ''')

    # Phase 3 Tables
    # Returns (返却)
    c.execute('''
        CREATE TABLE IF NOT EXISTS returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id INTEGER NOT NULL,
            return_date TEXT NOT NULL,
            checker_user_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (loan_id) REFERENCES loans (id)
        )
    ''')
    
    conn.commit()
    conn.close()

# --- User & Auth ---

def create_initial_admin(email: str, name: str, password_str: str) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT count(*) FROM users")
    if c.fetchone()[0] > 0:
        conn.close()
        return False
    password_bytes = password_str.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    try:
        c.execute("INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, ?)", (email, hashed, name, 'admin'))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_user_by_email(email: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = c.fetchone()
    conn.close()
    return user

def check_users_exist() -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT count(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count > 0

# --- Master Helper Functions ---

def seed_categories():
    categories = [
        "セルセーバー", "電気メス関連備品", "カウン太くん", "鋼製小物・サキュームカート",
        "IABP", "UNIMO", "冷温水槽", "その他人工心肺関連",
        "電気メス本体", "サキューム", "麻酔器", "カフ圧計"
    ]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for cat in categories:
        try:
            c.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat,))
        except Exception:
            pass
    conn.commit()
    conn.close()

def get_all_categories():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM categories")
    res = c.fetchall()
    conn.close()
    return res

# -- Device Types --
def create_device_type(category_id: int, name: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO device_types (category_id, name) VALUES (?, ?)", (category_id, name))
    conn.commit()
    return c.lastrowid

def get_device_types(category_id: int = None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if category_id:
        c.execute("SELECT * FROM device_types WHERE category_id = ?", (category_id,))
    else:
        c.execute("SELECT * FROM device_types")
    res = c.fetchall()
    conn.close()
    return res

def get_device_type_by_id(type_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM device_types WHERE id = ?", (type_id,))
    res = c.fetchone()
    conn.close()
    return res

# -- Items --
def create_item(name: str, tips: str = "", photo_path: str = ""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO items (name, tips, photo_path) VALUES (?, ?, ?)", (name, tips, photo_path))
    conn.commit()
    return c.lastrowid

def get_all_items():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM items")
    res = c.fetchall()
    conn.close()
    return res

# -- Templates --
def add_template_line(device_type_id: int, item_id: int, required_qty: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Check if exists
    c.execute("SELECT id FROM template_lines WHERE device_type_id=? AND item_id=?", (device_type_id, item_id))
    exists = c.fetchone()
    if exists:
        c.execute("UPDATE template_lines SET required_qty=? WHERE id=?", (required_qty, exists[0]))
    else:
        c.execute("INSERT INTO template_lines (device_type_id, item_id, required_qty) VALUES (?, ?, ?)", 
                  (device_type_id, item_id, required_qty))
    conn.commit()
    conn.close()

def get_template_lines(device_type_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT tl.*, i.name as item_name, i.photo_path 
        FROM template_lines tl
        JOIN items i ON tl.item_id = i.id
        WHERE tl.device_type_id = ?
        ORDER BY tl.sort_order
    """, (device_type_id,))
    res = c.fetchall()
    conn.close()
    return res

# -- Device Units --
def create_device_unit(device_type_id: int, lot_number: str, mfg_date: str = "", location: str = ""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO device_units (device_type_id, lot_number, mfg_date, location) 
            VALUES (?, ?, ?, ?)
        """, (device_type_id, lot_number, mfg_date, location))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_device_units(device_type_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM device_units WHERE device_type_id = ?", (device_type_id,))
    res = c.fetchall()
    conn.close()
    return res

def get_device_unit_by_id(unit_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM device_units WHERE id = ?", (unit_id,))
    res = c.fetchone()
    conn.close()
    return res

def update_unit_status(unit_id: int, status: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE device_units SET status = ? WHERE id = ?", (status, unit_id))
    conn.commit()
    conn.close()

# -- Unit Overrides --
def add_unit_override(device_unit_id: int, item_id: int, action: str, qty: int = 0):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Remove existing override for this item to avoid conflict logic complexity for now
    c.execute("DELETE FROM unit_overrides WHERE device_unit_id=? AND item_id=?", (device_unit_id, item_id))
    
    c.execute("""
        INSERT INTO unit_overrides (device_unit_id, item_id, action, qty)
        VALUES (?, ?, ?, ?)
    """, (device_unit_id, item_id, action, qty))
    conn.commit()
    conn.close()

def get_unit_overrides(device_unit_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT uo.*, i.name as item_name, i.photo_path
        FROM unit_overrides uo
        JOIN items i ON uo.item_id = i.id
        WHERE uo.device_unit_id = ?
    """, (device_unit_id,))
    res = c.fetchall()
    conn.close()
    return res

# -- Issues --
def get_open_issues(device_unit_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM issues WHERE device_unit_id = ? AND status = 'open'", (device_unit_id,))
    res = c.fetchall()
    conn.close()
    return res

def create_issue(device_unit_id: int, check_session_id: int, summary: str, created_by: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO issues (device_unit_id, check_session_id, status, summary, created_by)
        VALUES (?, ?, 'open', ?, ?)
    """, (device_unit_id, check_session_id, summary, created_by))
    conn.commit()
    conn.close()

# -- Phase 2 Operations --

def create_loan(
    device_unit_id: int, 
    checkout_date: str, 
    destination: str, 
    purpose: str, 
    checker_user_id: Optional[int] = None
) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO loans (device_unit_id, checkout_date, destination, purpose, checker_user_id, status)
        VALUES (?, ?, ?, ?, ?, 'open')
    """, (device_unit_id, checkout_date, destination, purpose, checker_user_id))
    loan_id = c.lastrowid
    conn.commit()
    conn.close()
    return loan_id

def create_check_session(
    session_type: str,
    device_unit_id: int,
    loan_id: Optional[int],
    performed_by: str,
    device_photo_dir: str
) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO check_sessions (session_type, device_unit_id, loan_id, performed_by, device_photo_dir)
        VALUES (?, ?, ?, ?, ?)
    """, (session_type, device_unit_id, loan_id, performed_by, device_photo_dir))
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id

def create_check_line(
    check_session_id: int,
    item_id: int,
    required_qty: int,
    result: str, # OK/NG
    ng_reason: str = None,
    found_qty: int = None,
    comment: str = None
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO check_lines (check_session_id, item_id, required_qty, result, ng_reason, found_qty, comment)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (check_session_id, item_id, required_qty, result, ng_reason, found_qty, comment))
    conn.commit()
    conn.close()

# -- Phase 3 Operations --

def create_return(
    loan_id: int,
    return_date: str,
    checker_user_id: Optional[int] = None
) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. Create Return Record
    c.execute("""
        INSERT INTO returns (loan_id, return_date, checker_user_id)
        VALUES (?, ?, ?)
    """, (loan_id, return_date, checker_user_id))
    return_id = c.lastrowid
    
    # 2. Close the Loan
    c.execute("UPDATE loans SET status = 'closed' WHERE id = ?", (loan_id,))
    
    conn.commit()
    conn.close()
    return return_id

def get_active_loan(device_unit_id: int):
    """Get the 'open' loan for a unit (if any)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT * FROM loans 
        WHERE device_unit_id = ? AND status = 'open'
        ORDER BY id DESC LIMIT 1
    """, (device_unit_id,))
    res = c.fetchone()
    conn.close()
    return res

def get_loan_by_id(loan_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM loans WHERE id = ?", (loan_id,))
    res = c.fetchone()
    conn.close()
    return res

