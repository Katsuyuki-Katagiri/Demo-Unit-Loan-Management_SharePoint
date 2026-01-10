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
            last_check_date TEXT,
            next_check_date TEXT,
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
            checker_user_id INTEGER,
            status TEXT DEFAULT 'open',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            canceled INTEGER DEFAULT 0,
            canceled_at TEXT,
            canceled_by TEXT,
            cancel_reason TEXT,
            FOREIGN KEY (device_unit_id) REFERENCES device_units (id)
        )
    ''')

    # Check Sessions (チェック単位)
    c.execute('''
        CREATE TABLE IF NOT EXISTS check_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_type TEXT NOT NULL,
            loan_id INTEGER,
            device_unit_id INTEGER NOT NULL,
            performed_by TEXT,
            performed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            device_photo_dir TEXT,
            canceled INTEGER DEFAULT 0,
            canceled_at TEXT,
            canceled_by TEXT,
            cancel_reason TEXT,
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
            status TEXT DEFAULT 'open',
            summary TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            resolved_at TEXT,
            resolved_by TEXT,
            canceled INTEGER DEFAULT 0,
            canceled_at TEXT,
            canceled_by TEXT,
            cancel_reason TEXT,
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
            canceled INTEGER DEFAULT 0,
            canceled_at TEXT,
            canceled_by TEXT,
            cancel_reason TEXT,
            FOREIGN KEY (loan_id) REFERENCES loans (id)
        )
    ''')
    
    # Phase 5 Tables
    # Notification Groups (Category <-> Users)
    c.execute('''
        CREATE TABLE IF NOT EXISTS notification_groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (category_id) REFERENCES categories (id),
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(category_id, user_id)
        )
    ''')

    # Notification Logs
    c.execute('''
        CREATE TABLE IF NOT EXISTS notification_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL, -- 'issue_created' etc.
            related_id INTEGER, -- e.g. issue_id
            recipient TEXT NOT NULL, -- Email or User Name
            status TEXT NOT NULL, -- 'sent', 'failed', 'logged_only'
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # System Settings (Key-Value)
    c.execute('''
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    conn.commit()
    conn.close()
    
    migrate_dates()

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

def update_item(item_id: int, name: str, tips: str, photo_path: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        if photo_path:
            c.execute("UPDATE items SET name=?, tips=?, photo_path=? WHERE id=?", (name, tips, photo_path, item_id))
        else:
            c.execute("UPDATE items SET name=?, tips=? WHERE id=?", (name, tips, item_id))
        conn.commit()
        return True
    except Exception as e:
        print(e)
        return False
    finally:
        conn.close()

def delete_item(item_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # 1. Check if used in check_lines (History)
        c.execute("SELECT count(*) FROM check_lines WHERE item_id = ?", (item_id,))
        if c.fetchone()[0] > 0:
            return False, "使用履歴があるため削除できません。"

        # 2. Safe to delete -> Remove from templates and overrides first
        c.execute("DELETE FROM template_lines WHERE item_id = ?", (item_id,))
        c.execute("DELETE FROM unit_overrides WHERE item_id = ?", (item_id,))
        c.execute("DELETE FROM items WHERE id = ?", (item_id,))
        
        conn.commit()
        return True, "削除しました。"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

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
def create_device_unit(device_type_id: int, lot_number: str, mfg_date: str = "", location: str = "", last_check_date: str = "", next_check_date: str = ""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO device_units (device_type_id, lot_number, mfg_date, location, last_check_date, next_check_date) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (device_type_id, lot_number, mfg_date, location, last_check_date, next_check_date))
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

def update_device_unit(unit_id: int, lot_number: str, mfg_date: str, location: str, last_check_date: str, next_check_date: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE device_units 
            SET lot_number = ?, mfg_date = ?, location = ?, last_check_date = ?, next_check_date = ?
            WHERE id = ?
        """, (lot_number, mfg_date, location, last_check_date, next_check_date, unit_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def update_device_type_name(type_id: int, new_name: str) -> bool:
    """Update the name of a device type."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("UPDATE device_types SET name = ? WHERE id = ?", (new_name, type_id))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def delete_device_unit(unit_id: int):
    """Delete a unit and all its related history (Cascade)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # Delete related tables
        # 1. Get loan IDs
        c.execute("SELECT id FROM loans WHERE device_unit_id = ?", (unit_id,))
        loan_ids = [r[0] for r in c.fetchall()]
        
        # 2. Get check_session IDs
        c.execute("SELECT id FROM check_sessions WHERE device_unit_id = ?", (unit_id,))
        session_ids = [r[0] for r in c.fetchall()]
        
        if session_ids:
            placeholders = ','.join(['?']*len(session_ids))
            c.execute(f"DELETE FROM check_lines WHERE check_session_id IN ({placeholders})", session_ids)
            c.execute(f"DELETE FROM issues WHERE check_session_id IN ({placeholders})", session_ids)
            
        c.execute("DELETE FROM issues WHERE device_unit_id = ?", (unit_id,))
        c.execute("DELETE FROM check_sessions WHERE device_unit_id = ?", (unit_id,))
        
        if loan_ids:
            placeholders = ','.join(['?']*len(loan_ids))
            c.execute(f"DELETE FROM returns WHERE loan_id IN ({placeholders})", loan_ids)
            
        c.execute("DELETE FROM loans WHERE device_unit_id = ?", (unit_id,))
        c.execute("DELETE FROM unit_overrides WHERE device_unit_id = ?", (unit_id,))
        c.execute("DELETE FROM device_units WHERE id = ?", (unit_id,))
        
        conn.commit()
        return True
    except Exception as e:
        print(e)
        return False
    finally:
        conn.close()

def delete_device_type(type_id: int):
    """Delete a device type and ALL related data (Cascade)."""
    # 1. Get all units
    units = get_device_units(type_id)
    
    # 2. Delete each unit (using existing logic)
    for u in units:
        if not delete_device_unit(u['id']):
            return False, f"Unit ID {u['id']} delete failed"

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # 3. Delete Template Lines
        c.execute("DELETE FROM template_lines WHERE device_type_id = ?", (type_id,))
        
        # 4. Delete Device Type
        c.execute("DELETE FROM device_types WHERE id = ?", (type_id,))
        
        conn.commit()
        return True, "機種を削除しました"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

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
    c.execute("SELECT * FROM issues WHERE device_unit_id = ? AND status = 'open' AND (canceled = 0 OR canceled IS NULL)", (device_unit_id,))
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
        WHERE device_unit_id = ? AND status = 'open' AND (canceled = 0 OR canceled IS NULL)
        ORDER BY id DESC LIMIT 1
    """, (device_unit_id,))
    res = c.fetchone()
    conn.close()
    return res

def get_check_session_by_loan_id(loan_id: int, session_type: str = 'checkout'):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM check_sessions WHERE loan_id = ? AND session_type = ? LIMIT 1", (loan_id, session_type))
    res = c.fetchone()
    conn.close()
    return res

def get_all_check_sessions_for_loan(loan_id: int):
    """Get ALL check sessions related to a loan (checkout, return, etc.)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT * FROM check_sessions 
        WHERE loan_id = ? 
        ORDER BY id ASC
    """, (loan_id,))
    res = c.fetchall()
    conn.close()
    return res

def get_check_session_lines(check_session_id: int):
    """Get check lines with item details for a session."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT cl.*, i.name as item_name, i.photo_path
        FROM check_lines cl
        JOIN items i ON cl.item_id = i.id
        WHERE cl.check_session_id = ?
        ORDER BY cl.id ASC
    """, (check_session_id,))
    res = c.fetchall()
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


# -- Phase 4 Operations --

def resolve_issue(issue_id: int, user_name: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE issues 
        SET status = 'closed', resolved_at = CURRENT_TIMESTAMP, resolved_by = ?
        WHERE id = ?
    """, (user_name, issue_id))
    conn.commit()
    conn.close()

def cancel_record(table: str, record_id: int, user_name: str, reason: str):
    """
    Generic cancellation. 
    Tables must have: canceled, canceled_at, canceled_by, cancel_reason
    """
    valid_tables = ['loans', 'returns', 'check_sessions', 'issues']
    if table not in valid_tables:
        raise ValueError(f"Invalid table for cancellation: {table}")
        
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    query = f"""
        UPDATE {table}
        SET canceled = 1, canceled_at = CURRENT_TIMESTAMP, 
            canceled_by = ?, cancel_reason = ?
        WHERE id = ?
    """
    c.execute(query, (user_name, reason, record_id))
    conn.commit()
    conn.close()

def get_related_records(loan_id: int = None, return_id: int = None):
    """
    Find related records for cascading cancellation.
    Returns dict of lists: {'returns': [], 'check_sessions': [], 'issues': []}
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    res = {'returns': [], 'check_sessions': [], 'issues': []}
    
    if loan_id:
        # Find Returns linked to this loan
        c.execute("SELECT id FROM returns WHERE loan_id = ? AND (canceled = 0 OR canceled IS NULL)", (loan_id,))
        res['returns'] = [r['id'] for r in c.fetchall()]
        
        # Find CheckSessions linked to this loan (checkout)
        c.execute("SELECT id FROM check_sessions WHERE loan_id = ? AND (canceled = 0 OR canceled IS NULL)", (loan_id,))
        res['check_sessions'] = [r['id'] for r in c.fetchall()]
        
    # Issues are linked to CheckSessions
    if res['check_sessions']:
        placeholders = ','.join(['?']*len(res['check_sessions']))
        c.execute(f"SELECT id FROM issues WHERE check_session_id IN ({placeholders}) AND status = 'open'", tuple(res['check_sessions']))
        res['issues'] = [r['id'] for r in c.fetchall()]
        
    conn.close()
    return res

def migrate_phase4():
    """Add new columns for Phase 4 if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    tables = ['loans', 'check_sessions', 'issues', 'returns']
    columns = [
        ('canceled', 'INTEGER DEFAULT 0'),
        ('canceled_at', 'TEXT'),
        ('canceled_by', 'TEXT'),
        ('cancel_reason', 'TEXT')
    ]
    
    for tbl in tables:
        # Check columns
        c.execute(f"PRAGMA table_info({tbl})")
        existing_cols = [row[1] for row in c.fetchall()]
        
        for col_name, col_def in columns:
            if col_name not in existing_cols:
                try:
                    print(f"Migrating {tbl}: Adding {col_name}")
                    c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col_name} {col_def}")
                except Exception as e:
                    print(f"Error altering {tbl}: {e}")
                    
    conn.commit()
    conn.close()

def get_loan_history(device_unit_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT * FROM loans 
        WHERE device_unit_id = ?
        ORDER BY id DESC
    """, (device_unit_id,))
    res = c.fetchall()
    conn.close()
    return res

# -- Phase 5 Operations --

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, name, email FROM users ORDER BY name")
    res = c.fetchall()
    conn.close()
    return res

def get_user_by_id(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, name, email FROM users WHERE id = ?", (user_id,))
    res = c.fetchone()
    conn.close()
    return res

def add_notification_member(category_id: int, user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO notification_groups (category_id, user_id) VALUES (?, ?)", (category_id, user_id))
        conn.commit()
    except sqlite3.IntegrityError:
        pass # Already exists
    conn.close()

def remove_notification_member(category_id: int, user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM notification_groups WHERE category_id = ? AND user_id = ?", (category_id, user_id))
    conn.commit()
    conn.close()

def get_notification_members(category_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT u.id, u.name, u.email 
        FROM notification_groups ng
        JOIN users u ON ng.user_id = u.id
        WHERE ng.category_id = ?
    """, (category_id,))
    res = c.fetchall()
    conn.close()
    return res

def log_notification(event_type: str, related_id: int, recipient: str, status: str, error_message: str = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO notification_logs (event_type, related_id, recipient, status, error_message)
        VALUES (?, ?, ?, ?, ?)
    """, (event_type, related_id, recipient, status, error_message))
    conn.commit()
    conn.close()

def get_notification_logs(limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM notification_logs ORDER BY id DESC LIMIT ?", (limit,))
    res = c.fetchall()
    conn.close()
    return res

def save_system_setting(key: str, value: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_system_setting(key: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM system_settings WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def migrate_phase5():
    """Create Phase 5 tables if they don't exist."""
    print("Migrating Phase 5...")
    init_db() # init_db now includes Phase 5 tables, so running it checks and creates them safely
    migrate_dates() # Ensure dates are added
    print("Phase 5 Migration Complete (via init_db check).")

def migrate_dates():
    """Add date columns to device_units if missing."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA table_info(device_units)")
    cols = [r[1] for r in c.fetchall()]
    
    if 'last_check_date' not in cols:
        try:
            c.execute("ALTER TABLE device_units ADD COLUMN last_check_date TEXT")
            print("Added last_check_date")
        except: pass
        
    if 'next_check_date' not in cols:
        try:
            c.execute("ALTER TABLE device_units ADD COLUMN next_check_date TEXT")
            print("Added next_check_date")
        except: pass
    
    conn.commit()
    conn.close()

def get_unit_status_counts(category_id: int = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if category_id:
        c.execute("""
            SELECT u.status, COUNT(*) 
            FROM device_units u
            JOIN device_types t ON u.device_type_id = t.id
            WHERE t.category_id = ?
            GROUP BY u.status
        """, (category_id,))
    else:
        c.execute("SELECT status, COUNT(*) FROM device_units GROUP BY status")
        
    rows = c.fetchall()
    conn.close()
    return dict(rows)



