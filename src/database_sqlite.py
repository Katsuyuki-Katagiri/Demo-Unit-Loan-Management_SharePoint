import os
import streamlit as st

# Supabaseが設定されている場合はSupabase版を使用
_use_supabase = False
try:
    supabase_url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    supabase_key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
    if supabase_url and supabase_key:
        _use_supabase = True
except Exception:
    pass

if _use_supabase:
    # Supabase版の全関数をインポート
    from src.database_supabase import *
else:
    # SQLite版を使用
    import sqlite3
    import time
    import threading
    from typing import Optional, List, Tuple, Dict, Any
    import bcrypt

    # 環境変数からパスを取得（SharePoint同期フォルダ対応）
    # 環境変数が未設定の場合はデフォルトのローカルパスを使用
    DB_PATH = os.environ.get("DEMO_LOAN_DB_PATH", os.path.join("data", "app.db"))
    UPLOAD_DIR = os.environ.get("DEMO_LOAN_UPLOAD_DIR", os.path.join("data", "uploads"))
    
    # データベースロック用（ファイルベースの排他制御）
    _db_lock = threading.Lock()
    
    def get_db_connection(timeout: float = 30.0):
        """
        データベース接続を取得（WALモード対応）
        
        Args:
            timeout: タイムアウト秒数
        
        Returns:
            sqlite3.Connection
        """
        conn = sqlite3.connect(DB_PATH, timeout=timeout)
        # WALモードを有効化（同時読み書き対応）
        conn.execute("PRAGMA journal_mode=WAL")
        # 忙しい時のリトライ待機を設定
        conn.execute("PRAGMA busy_timeout=30000")
        return conn
    
    def execute_with_retry(func, max_retries: int = 5, base_delay: float = 0.5):
        """
        データベース操作をリトライ付きで実行
        
        Args:
            func: 実行する関数（引数なし）
            max_retries: 最大リトライ回数
            base_delay: 基本待機時間（秒）
        
        Returns:
            関数の戻り値
        """
        last_error = None
        for attempt in range(max_retries):
            try:
                return func()
            except sqlite3.OperationalError as e:
                last_error = e
                if "database is locked" in str(e) or "database is busy" in str(e):
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # 指数バックオフ
                        print(f"データベースがロック中。{delay:.1f}秒後にリトライ... (試行 {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                    else:
                        raise
                else:
                    raise
        raise last_error


def init_db():
    """Initialize the database with all tables for Phase 1."""
    # データベースファイルの親ディレクトリを作成（SharePoint同期フォルダ対応）
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    conn = get_db_connection()
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
    
    # Departments (部署)
    c.execute('''
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    ''')
    
    # Login History (ログイン履歴)
    c.execute('''
        CREATE TABLE IF NOT EXISTS login_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            email TEXT NOT NULL,
            user_name TEXT,
            login_at TEXT DEFAULT CURRENT_TIMESTAMP,
            ip_address TEXT,
            user_agent TEXT,
            success INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    
    # Run migrations
    migrate_user_department()
    migrate_category_managing_department()
    migrate_category_description()
    migrate_category_sort_order()
    
    migrate_dates()

# --- Login History ---

def record_login_history(user_id: int, email: str, user_name: str, ip_address: str = None, user_agent: str = None, success: bool = True):
    """ログイン履歴を記録"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO login_history (user_id, email, user_name, ip_address, user_agent, success)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, email, user_name, ip_address, user_agent, 1 if success else 0))
        conn.commit()
        return True
    except Exception as e:
        print(f"Login history record error: {e}")
        return False
    finally:
        conn.close()

def get_login_history(user_id: int = None, limit: int = 100):
    """ログイン履歴を取得"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if user_id:
        c.execute('''
            SELECT * FROM login_history WHERE user_id = ?
            ORDER BY login_at DESC LIMIT ?
        ''', (user_id, limit))
    else:
        c.execute('''
            SELECT * FROM login_history
            ORDER BY login_at DESC LIMIT ?
        ''', (limit,))
    
    results = [dict(row) for row in c.fetchall()]
    conn.close()
    return results

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

def create_user(email: str, name: str, password_str: str, role: str = 'user') -> bool:
    """Create a new user."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    password_bytes = password_str.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    try:
        c.execute("INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, ?)", (email, hashed, name, role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def delete_user(user_id: int) -> tuple[bool, str]:
    """Delete a user. Prevent deleting the last admin."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Check if user exists
    c.execute("SELECT role FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    if not user:
        conn.close()
        return False, "ユーザーが見つかりません。"
        
    # If deleting an admin, check if it's the last one
    if user[0] == 'admin':
        c.execute("SELECT count(*) FROM users WHERE role = 'admin'")
        admin_count = c.fetchone()[0]
        if admin_count <= 1:
            conn.close()
            return False, "最後の管理者は削除できません。"
            
    try:
        # Also remove from notification groups
        c.execute("DELETE FROM notification_groups WHERE user_id = ?", (user_id,))
        
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return True, "ユーザーを削除しました。"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def check_email_exists(email: str) -> bool:
    """Check if an email is already registered."""
    return get_user_by_email(email) is not None

def update_user_password(user_id: int, new_password: str) -> tuple:
    """ユーザーのパスワードを更新"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # ユーザー確認
    c.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not c.fetchone():
        conn.close()
        return False, "ユーザーが見つかりません。"
    
    try:
        password_bytes = new_password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        
        c.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed, user_id))
        conn.commit()
        return True, "パスワードを更新しました。"
    except Exception as e:
        return False, f"パスワード更新エラー: {e}"
    finally:
        conn.close()

def update_user_role(user_id: int, new_role: str) -> tuple:
    """ユーザーの権限を更新"""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
        conn.commit()
        return True, "権限を更新しました"
    except Exception as e:
        return False, f"権限更新エラー: {e}"
    finally:
        conn.close()


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

@st.cache_data(ttl=60)
def get_all_categories():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    # Check if sort_order exists, otherwise basic select
    # Or just assume migration ran.
    try:
        c.execute("SELECT * FROM categories ORDER BY sort_order ASC, id ASC")
    except:
        c.execute("SELECT * FROM categories")
        
    res = [dict(row) for row in c.fetchall()]
    conn.close()
    return res

def migrate_category_visibility():
    """Migrate categories table to include is_visible column."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # Check if column exists
        c.execute("PRAGMA table_info(categories)")
        columns = [r[1] for r in c.fetchall()]
        if 'is_visible' not in columns:
            print("Migrating categories: adding is_visible column...")
            c.execute("ALTER TABLE categories ADD COLUMN is_visible INTEGER DEFAULT 1")
            conn.commit()
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()

def migrate_user_department():
    """Migrate users table to include department_id column."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("PRAGMA table_info(users)")
        columns = [r[1] for r in c.fetchall()]
        if 'department_id' not in columns:
            print("Migrating users: adding department_id column...")
            c.execute("ALTER TABLE users ADD COLUMN department_id INTEGER REFERENCES departments(id)")
            conn.commit()
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()

def migrate_category_managing_department():
    """Migrate categories table to include managing_department_id column."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("PRAGMA table_info(categories)")
        columns = [r[1] for r in c.fetchall()]
        if 'managing_department_id' not in columns:
            print("Migrating categories: adding managing_department_id column...")
            c.execute("ALTER TABLE categories ADD COLUMN managing_department_id INTEGER REFERENCES departments(id)")
            conn.commit()
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()

def migrate_category_description():
    """Migrate categories table to include description column."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("PRAGMA table_info(categories)")
        columns = [r[1] for r in c.fetchall()]
        if 'description' not in columns:
            print("Migrating categories: adding description column...")
            c.execute("ALTER TABLE categories ADD COLUMN description TEXT")
            conn.commit()
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()

def migrate_category_sort_order():
    """Migrate categories table to include sort_order column."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("PRAGMA table_info(categories)")
        columns = [r[1] for r in c.fetchall()]
        if 'sort_order' not in columns:
            print("Migrating categories: adding sort_order column...")
            c.execute("ALTER TABLE categories ADD COLUMN sort_order INTEGER DEFAULT 0")
            conn.commit()
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()


def update_category_visibility(category_id: int, is_visible: bool):
    """Update visibility status of a category."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        val = 1 if is_visible else 0
        c.execute("UPDATE categories SET is_visible = ? WHERE id = ?", (val, category_id))
        conn.commit()
        return True
    except Exception as e:
        print(e)
        return False
    finally:
        conn.close()



def move_category_order(category_id: int, direction: str):
    """
    Move a category up or down in the sort order.
    direction: 'up' or 'down'
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    try:
        # 1. Get all categories sorted by current sort_order, then ID
        c.execute("SELECT id, sort_order FROM categories ORDER BY sort_order ASC, id ASC")
        categories = [dict(r) for r in c.fetchall()]
        
        # 2. Find index of target
        idx = -1
        for i, cat in enumerate(categories):
            if cat['id'] == category_id:
                idx = i
                break
        
        if idx == -1:
            return False, "Category not found"
        
        # 3. Determine swap target
        swap_idx = -1
        if direction == 'up':
            if idx > 0:
                swap_idx = idx - 1
        elif direction == 'down':
            if idx < len(categories) - 1:
                swap_idx = idx + 1
        
        if swap_idx != -1:
            # Swap in the list
            categories[idx], categories[swap_idx] = categories[swap_idx], categories[idx]
            
            # 4. Re-assign sort orders for ALL to normalize (spaced by 10)
            for i, cat in enumerate(categories):
                new_order = (i + 1) * 10
                c.execute("UPDATE categories SET sort_order = ? WHERE id = ?", (new_order, cat['id']))
            
            conn.commit()
            return True, "順序を更新しました"
        else:
            return False, "これ以上移動できません"

    except Exception as e:
        print(e)
        return False, str(e)
    finally:
        conn.close()

def create_category(name: str):
    """Create a new category."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO categories (name, is_visible) VALUES (?, 1)", (name,))
        conn.commit()
        return True, "カテゴリを作成しました"
    except sqlite3.IntegrityError:
        return False, "カテゴリ作成エラー (重複など)"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def update_category_basic_info(category_id: int, new_name: str, description: str, sort_order: int = 0):
    """Update the name, description and sort_order of a category."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("UPDATE categories SET name = ?, description = ?, sort_order = ? WHERE id = ?", (new_name, description, sort_order, category_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating category: {e}")
        return False
    finally:
        conn.close()

def update_category_name(category_id: int, new_name: str):
    """Update the name of a category. (Legacy wrapper)"""
    # Fetch description to keep it
    cat = get_category_by_id(category_id)
    desc = cat['description'] if cat and 'description' in cat.keys() else ""
    order = cat['sort_order'] if cat and 'sort_order' in cat.keys() else 0
    return update_category_basic_info(category_id, new_name, desc, order)

def get_category_by_id(category_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
    res = c.fetchone()
    conn.close()
    return res

def delete_category(category_id: int):
    """Delete a category if it has no associated device types."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # Check for dependencies
        c.execute("SELECT count(*) FROM device_types WHERE category_id = ?", (category_id,))
        count = c.fetchone()[0]
        if count > 0:
            return False, f"このカテゴリには {count} 件の機種が登録されているため削除できません。"
        
        c.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        conn.commit()
        return True, "カテゴリを削除しました"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

# -- Device Types --
def create_device_type(category_id: int, name: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO device_types (category_id, name) VALUES (?, ?)", (category_id, name))
    conn.commit()
    return c.lastrowid

@st.cache_data(ttl=60)
def get_device_types(category_id: int = None):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if category_id:
        c.execute("SELECT * FROM device_types WHERE category_id = ?", (category_id,))
    else:
        c.execute("SELECT * FROM device_types")
    res = [dict(row) for row in c.fetchall()]
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

@st.cache_data(ttl=60)
def get_all_items():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM items")
    res = [dict(row) for row in c.fetchall()]
    conn.close()
    return res

def get_item_by_exact_name(name: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM items WHERE name = ?", (name,))
    res = c.fetchone()
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

def delete_template_line(device_type_id: int, item_id: int):
    """Delete a template line item."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM template_lines WHERE device_type_id=? AND item_id=?", (device_type_id, item_id))
    conn.commit()
    conn.close()

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

def get_all_device_units():
    """全個体を一括取得（バッチクエリ用）"""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM device_units")
    res = [dict(row) for row in c.fetchall()]
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

def create_issue(device_unit_id: int, check_session_id: int, summary: str, created_by: str) -> int:
    """課題を作成し、作成された課題IDを返す。"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO issues (device_unit_id, check_session_id, status, summary, created_by)
        VALUES (?, ?, 'open', ?, ?)
    """, (device_unit_id, check_session_id, summary, created_by))
    issue_id = c.lastrowid
    conn.commit()
    conn.close()
    return issue_id

# -- Phase 2 Operations --

def migrate_loans_assetment_check():
    """Migrate loans table to include assetment_checked column."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("PRAGMA table_info(loans)")
        columns = [r[1] for r in c.fetchall()]
        if 'assetment_checked' not in columns:
            print("Migrating loans: adding assetment_checked column...")
            c.execute("ALTER TABLE loans ADD COLUMN assetment_checked INTEGER DEFAULT 0")
            conn.commit()
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()


def migrate_loans_notes():
    """Migrate loans table to include notes column."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("PRAGMA table_info(loans)")
        columns = [r[1] for r in c.fetchall()]
        if 'notes' not in columns:
            print("Migrating loans: adding notes column...")
            c.execute("ALTER TABLE loans ADD COLUMN notes TEXT")
            conn.commit()
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()

def create_loan(
    device_unit_id: int, 
    checkout_date: str, 
    destination: str, 
    purpose: str, 
    checker_user_id: Optional[int] = None,
    assetment_checked: bool = False,
    notes: str = None
) -> int:
    # マイグレーションはapp.py起動時に実行されるため、ここでは不要
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO loans (device_unit_id, checkout_date, destination, purpose, checker_user_id, status, assetment_checked, notes)
        VALUES (?, ?, ?, ?, ?, 'open', ?, ?)
    """, (device_unit_id, checkout_date, destination, purpose, checker_user_id, 1 if assetment_checked else 0, notes))
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

def migrate_returns_assetment_check():
    """Migrate returns table to include assetment_returned column."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("PRAGMA table_info(returns)")
        columns = [r[1] for r in c.fetchall()]
        if 'assetment_returned' not in columns:
            print("Migrating returns: adding assetment_returned column...")
            c.execute("ALTER TABLE returns ADD COLUMN assetment_returned INTEGER DEFAULT 0")
            conn.commit()
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()

def migrate_returns_notes():
    """Migrate returns table to include notes column."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("PRAGMA table_info(returns)")
        columns = [r[1] for r in c.fetchall()]
        if 'notes' not in columns:
            print("Migrating returns: adding notes column...")
            c.execute("ALTER TABLE returns ADD COLUMN notes TEXT")
            conn.commit()
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()

def migrate_returns_confirmation_check():
    """Migrate returns table to include confirmation_checked column."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("PRAGMA table_info(returns)")
        columns = [r[1] for r in c.fetchall()]
        if 'confirmation_checked' not in columns:
            print("Migrating returns: adding confirmation_checked column...")
            c.execute("ALTER TABLE returns ADD COLUMN confirmation_checked INTEGER DEFAULT 0")
            conn.commit()
    except Exception as e:
        print(f"Migration error: {e}")
    finally:
        conn.close()

def create_return(
    loan_id: int,
    return_date: str,
    checker_user_id: Optional[int] = None,
    assetment_returned: bool = False,
    notes: str = None,
    confirmation_checked: bool = False
) -> int:
    # マイグレーションはapp.py起動時に実行されるため、ここでは不要
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. Create Return Record
    c.execute("""
        INSERT INTO returns (loan_id, return_date, checker_user_id, assetment_returned, notes, confirmation_checked)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (loan_id, return_date, checker_user_id, 1 if assetment_returned else 0, notes, 1 if confirmation_checked else 0))
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

def create_check_line(check_session_id: int, item_id: int, required_qty: int, result: str, ng_reason: str = None, found_qty: int = None, comment: str = None):
    """チェック明細を作成"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO check_lines (check_session_id, item_id, required_qty, result, ng_reason, found_qty, comment)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (check_session_id, item_id, required_qty, result, ng_reason, found_qty, comment))
    conn.commit()
    conn.close()

def get_check_session_by_loan_id(loan_id: int, session_type: str = 'checkout'):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM check_sessions WHERE loan_id = ? AND session_type = ? LIMIT 1", (loan_id, session_type))
    res = c.fetchone()
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

# --- Supabase Storage Dummies ---

def upload_photo_to_storage(file_bytes: bytes, filename: str) -> str:
    # SQLite版ではローカル保存されるため、この関数は使用されないか、
    # 必要ならローカル保存ロジックを入れるべきだが、
    # 現状の実装ロジックでは呼び出し側で分岐等している前提とするか、
    # ここでは空を返す
    return ""

def delete_photo_from_storage(filename: str) -> bool:
    return False

def get_photo_public_url(filename: str) -> str:
    return ""

def upload_session_photo(session_id: str, file_bytes: bytes, index: int = 0) -> str:
    return ""

def get_session_photos(session_id: str) -> list:
    return []

def get_loan_history(device_unit_id: int, limit: int = None, offset: int = 0, include_canceled: bool = True):
    # Ensure schema is up to date (needed for new Assetment columns if not yet run)
    migrate_returns_assetment_check()
    migrate_returns_confirmation_check()
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Left join to get return info if available (get the latest valid return)
    query = """
        SELECT l.*, r.assetment_returned, r.confirmation_checked
        FROM loans l
        LEFT JOIN returns r ON l.id = r.loan_id AND (r.canceled = 0 OR r.canceled IS NULL)
        WHERE l.device_unit_id = ?
    """
    params = [device_unit_id]
    
    if not include_canceled:
        query += " AND (l.canceled = 0 OR l.canceled IS NULL)"
        
    query += " ORDER BY l.id DESC"
    
    if limit is not None:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
    c.execute(query, params)
    res = c.fetchall()
    conn.close()
    return res

# -- Phase 5 Operations --

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, name, email, role FROM users ORDER BY name")
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

def migrate_notifications_table():
    """Ensure notification_logs table exists."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS notification_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            related_id INTEGER,
            recipient TEXT NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def log_notification(event_type: str, related_id: int, recipient: str, status: str, error_message: str = None):
    # Ensure table exists
    migrate_notifications_table()
    
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

def migrate_system_settings_table():
    """Ensure system_settings table exists."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_system_setting(key: str, value: str):
    migrate_system_settings_table()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_system_setting(key: str):
    migrate_system_settings_table()
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

def reset_database_keep_admin():
    """
    DANGER: Resets the database, keeping ONLY the admin@example.com user.
    Deletes all logic data, transaction data, and other users.
    Re-seeds categories.
    Clears uploads directory.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        # 1. Delete Transaction Data (Child tables first)
        c.execute("DELETE FROM check_lines")
        c.execute("DELETE FROM issues")
        c.execute("DELETE FROM returns")
        c.execute("DELETE FROM check_sessions")
        c.execute("DELETE FROM loans")
        c.execute("DELETE FROM notification_logs")
        
        # 2. Delete Logic/Master Data
        c.execute("DELETE FROM unit_overrides")
        c.execute("DELETE FROM template_lines")
        c.execute("DELETE FROM device_units")
        c.execute("DELETE FROM items")
        c.execute("DELETE FROM device_types")
        c.execute("DELETE FROM notification_groups")
        
        # 3. Delete Categories (Will be re-seeded)
        c.execute("DELETE FROM categories")
        
        # 4. Delete Users except admin@example.com
        # Note: If admin@example.com doesn't exist, this leaves table empty (which triggers setup view)
        c.execute("DELETE FROM users WHERE email != 'admin@example.com'")
        
        # 5. Clear Uploads
        if os.path.exists(UPLOAD_DIR):
            for filename in os.listdir(UPLOAD_DIR):
                file_path = os.path.join(UPLOAD_DIR, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        import shutil
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f'Failed to delete {file_path}. Reason: {e}')
                    
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()
        
    # Re-seed static data
    seed_categories()
    
    return True


# --- Department Management ---

def create_department(name: str):
    """Create a new department."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO departments (name) VALUES (?)", (name,))
        conn.commit()
        return True, "部署を作成しました"
    except sqlite3.IntegrityError:
        return False, "同じ名前の部署が既に存在します"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def get_all_departments():
    """Get all departments."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM departments ORDER BY name")
    res = [dict(row) for row in c.fetchall()]
    conn.close()
    return res

def get_department_by_id(department_id: int):
    """Get a department by ID."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM departments WHERE id = ?", (department_id,))
    res = c.fetchone()
    conn.close()
    return dict(res) if res else None

def update_department(department_id: int, name: str):
    """Update department name."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("UPDATE departments SET name = ? WHERE id = ?", (name, department_id))
        conn.commit()
        return True, "部署名を更新しました"
    except sqlite3.IntegrityError:
        return False, "同じ名前の部署が既に存在します"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def delete_department(department_id: int):
    """Delete a department if no users belong to it."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # Check if any users belong to this department
        c.execute("SELECT count(*) FROM users WHERE department_id = ?", (department_id,))
        user_count = c.fetchone()[0]
        if user_count > 0:
            return False, f"この部署には {user_count} 名のユーザーが所属しているため削除できません"
        
        # Check if any categories use this as managing department
        c.execute("SELECT count(*) FROM categories WHERE managing_department_id = ?", (department_id,))
        cat_count = c.fetchone()[0]
        if cat_count > 0:
            return False, f"この部署は {cat_count} 件のカテゴリの管理部署に設定されているため削除できません"
        
        c.execute("DELETE FROM departments WHERE id = ?", (department_id,))
        conn.commit()
        return True, "部署を削除しました"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def update_user_department(user_id: int, department_id: Optional[int]):
    """Update user's department."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("UPDATE users SET department_id = ? WHERE id = ?", (department_id, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating user department: {e}")
        return False
    finally:
        conn.close()

def get_users_by_department(department_id: Optional[int]):
    """Get users by department. If department_id is None, get users without department."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    if department_id is None:
        c.execute("SELECT id, name, email, role, department_id FROM users WHERE department_id IS NULL ORDER BY name")
    else:
        c.execute("SELECT id, name, email, role, department_id FROM users WHERE department_id = ? ORDER BY name", (department_id,))
    res = [dict(row) for row in c.fetchall()]
    conn.close()
    return res

def update_category_managing_department(category_id: int, department_id: Optional[int]):
    """Update the managing department of a category."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("UPDATE categories SET managing_department_id = ? WHERE id = ?", (department_id, category_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating category managing department: {e}")
        return False
    finally:
        conn.close()

def get_category_managing_department(category_id: int):
    """Get the managing department of a category."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT d.* FROM departments d
        JOIN categories c ON c.managing_department_id = d.id
        WHERE c.id = ?
    """, (category_id,))
    res = c.fetchone()
    conn.close()
    return dict(res) if res else None

# --- logic.py用の抽象化関数 ---

def get_return_by_id(return_id: int):
    """返却IDで返却レコードを取得"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM returns WHERE id = ?", (return_id,))
    res = c.fetchone()
    conn.close()
    return dict(res) if res else None

def reopen_loan(loan_id: int):
    """貸出を再オープン（返却キャンセル時）"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE loans SET status = 'open' WHERE id = ?", (loan_id,))
    conn.commit()
    conn.close()

def get_return_check_sessions(loan_id: int):
    """返却に関連するチェックセッションを取得"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT id FROM check_sessions 
        WHERE loan_id = ? AND session_type = 'return' AND (canceled = 0 OR canceled IS NULL)
    """, (loan_id,))
    res = [row['id'] for row in c.fetchall()]
    conn.close()
    return res

def get_issues_by_session_id(session_id: int):
    """セッションIDに関連するオープンなIssueを取得"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT id FROM issues 
        WHERE check_session_id = ? AND (canceled = 0 OR canceled IS NULL)
    """, (session_id,))
    res = [row['id'] for row in c.fetchall()]
    conn.close()
    return res

def get_loan_periods_for_unit(device_unit_id: int):
    """稼働率計算用：個体の貸出期間一覧を取得"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT l.checkout_date, r.return_date, l.status, l.canceled 
        FROM loans l
        LEFT JOIN returns r ON l.id = r.loan_id AND (r.canceled = 0 OR r.canceled IS NULL)
        WHERE l.device_unit_id = ? AND (l.canceled = 0 OR l.canceled IS NULL)
    """, (device_unit_id,))
    res = [dict(row) for row in c.fetchall()]
    conn.close()
    return res

# --- Batch取得関数（N+1問題対策） ---

def get_device_units_for_types(type_ids: list):
    """
    複数の機種の個体を一括取得
    
    Returns:
        {type_id: [unit1, unit2, ...], ...} のディクショナリ
    """
    if not type_ids:
        return {}
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    placeholders = ','.join(['?']*len(type_ids))
    c.execute(f"SELECT * FROM device_units WHERE device_type_id IN ({placeholders})", type_ids)
    
    # 機種IDでグループ化
    units_by_type = {}
    for row in c.fetchall():
        unit = dict(row)
        type_id = unit['device_type_id']
        if type_id not in units_by_type:
            units_by_type[type_id] = []
        units_by_type[type_id].append(unit)
    
    conn.close()
    return units_by_type

def get_users_batch(user_ids: list):
    """
    複数のユーザーを一括取得
    
    Returns:
        {user_id: user_dict, ...} のディクショナリ
    """
    if not user_ids:
        return {}
    # 重複を除去
    unique_ids = list(set(user_ids))
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    placeholders = ','.join(['?']*len(unique_ids))
    c.execute(f"SELECT * FROM users WHERE id IN ({placeholders})", unique_ids)
    
    result = {row['id']: dict(row) for row in c.fetchall()}
    conn.close()
    return result

def get_active_loans_batch(unit_ids: list):
    """
    複数個体のアクティブな貸出を一括取得
    
    Returns:
        {unit_id: loan_dict, ...} のディクショナリ（貸出中の個体のみ）
    """
    if not unit_ids:
        return {}
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    placeholders = ','.join(['?']*len(unit_ids))
    c.execute(f"""
        SELECT * FROM loans 
        WHERE device_unit_id IN ({placeholders}) 
        AND status = 'open' 
        AND (canceled = 0 OR canceled IS NULL)
    """, unit_ids)
    
    result = {row['device_unit_id']: dict(row) for row in c.fetchall()}
    conn.close()
    return result

def get_check_sessions_batch(loan_ids: list):
    """
    複数貸出のチェックセッションを一括取得
    
    Returns:
        {loan_id: [session1, session2, ...], ...}
    """
    if not loan_ids:
        return {}
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    placeholders = ','.join(['?']*len(loan_ids))
    c.execute(f"""
        SELECT * FROM check_sessions 
        WHERE loan_id IN ({placeholders}) 
        AND (canceled = 0 OR canceled IS NULL)
        ORDER BY id
    """, loan_ids)
    
    sessions_by_loan = {}
    for row in c.fetchall():
        sess = dict(row)
        loan_id = sess['loan_id']
        if loan_id not in sessions_by_loan:
            sessions_by_loan[loan_id] = []
        sessions_by_loan[loan_id].append(sess)
    
    conn.close()
    return sessions_by_loan

def get_check_lines_batch(session_ids: list):
    """
    複数セッションのチェック明細を一括取得
    
    Returns:
        {session_id: [line1, line2, ...], ...}
    """
    if not session_ids:
        return {}
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    placeholders = ','.join(['?']*len(session_ids))
    # JOINでアイテム名・写真パスも取得
    c.execute(f"""
        SELECT cl.*, i.name as item_name, i.photo_path
        FROM check_lines cl
        LEFT JOIN items i ON cl.item_id = i.id
        WHERE cl.check_session_id IN ({placeholders})
    """, session_ids)
    
    lines_by_session = {}
    for row in c.fetchall():
        line = dict(row)
        session_id = line['check_session_id']
        if session_id not in lines_by_session:
            lines_by_session[session_id] = []
        lines_by_session[session_id].append(line)
    
    conn.close()
    return lines_by_session
