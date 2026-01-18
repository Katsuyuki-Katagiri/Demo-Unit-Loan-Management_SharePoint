# Supabase Database Layer
# このファイルはSupabaseをデータベースとして使用するための関数を提供します

import os
from typing import Optional, List, Dict, Any
import bcrypt
import streamlit as st
from supabase import create_client, Client

# Supabase接続
def get_supabase_client() -> Client:
    """Supabaseクライアントを取得"""
    url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        raise ValueError("SUPABASE_URL と SUPABASE_KEY が設定されていません")
    
    return create_client(url, key)

# グローバルクライアント（キャッシュ）
_supabase: Optional[Client] = None

def get_client() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = get_supabase_client()
    return _supabase

# アップロードディレクトリ（写真用）
UPLOAD_DIR = os.path.join("data", "uploads")
# SQLite互換性のためのダミーパス（Supabase使用時は実際には使用されない）
DB_PATH = os.path.join("data", "app.db")


def init_db():
    """データベース初期化（Supabaseでは主にディレクトリ作成のみ）"""
    os.makedirs("data", exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- User & Auth ---

def create_initial_admin(email: str, name: str, password_str: str) -> bool:
    """初期管理者を作成"""
    client = get_client()
    
    # ユーザーが存在するか確認
    result = client.table("users").select("id").execute()
    if len(result.data) > 0:
        return False
    
    password_bytes = password_str.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
    
    try:
        client.table("users").insert({
            "email": email,
            "password_hash": hashed,
            "name": name,
            "role": "admin"
        }).execute()
        return True
    except Exception as e:
        print(f"Error creating admin: {e}")
        return False

def get_user_by_email(email: str):
    """メールアドレスでユーザーを取得"""
    client = get_client()
    result = client.table("users").select("*").eq("email", email).execute()
    if result.data:
        return result.data[0]
    return None

def get_user_by_id(user_id: int):
    """IDでユーザーを取得"""
    client = get_client()
    result = client.table("users").select("*").eq("id", user_id).execute()
    if result.data:
        return result.data[0]
    return None

def check_users_exist() -> bool:
    """ユーザーが存在するか確認"""
    client = get_client()
    result = client.table("users").select("id").limit(1).execute()
    return len(result.data) > 0

def create_user(email: str, name: str, password_str: str, role: str = 'user') -> bool:
    """新規ユーザーを作成"""
    client = get_client()
    
    password_bytes = password_str.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
    
    try:
        client.table("users").insert({
            "email": email,
            "password_hash": hashed,
            "name": name,
            "role": role
        }).execute()
        return True
    except Exception as e:
        print(f"Error creating user: {e}")
        return False

def delete_user(user_id: int) -> tuple:
    """ユーザーを削除"""
    client = get_client()
    
    # ユーザー確認
    result = client.table("users").select("role").eq("id", user_id).execute()
    if not result.data:
        return False, "ユーザーが見つかりません。"
    
    # 最後の管理者か確認
    if result.data[0]["role"] == "admin":
        admin_result = client.table("users").select("id").eq("role", "admin").execute()
        if len(admin_result.data) <= 1:
            return False, "最後の管理者は削除できません。"
    
    try:
        # 通知グループからも削除
        client.table("notification_groups").delete().eq("user_id", user_id).execute()
        client.table("users").delete().eq("id", user_id).execute()
        return True, "ユーザーを削除しました。"
    except Exception as e:
        return False, str(e)

def get_all_users():
    """全ユーザーを取得"""
    client = get_client()
    result = client.table("users").select("*").execute()
    return result.data

def check_email_exists(email: str) -> bool:
    """メールアドレスが登録済みか確認"""
    return get_user_by_email(email) is not None

# --- Categories ---

def seed_categories():
    """初期カテゴリを登録"""
    categories = [
        "セルセーバー", "電気メス関連備品", "カウン太くん", "鋼製小物・サキュームカート",
        "IABP", "UNIMO", "冷温水槽", "その他人工心肺関連",
        "電気メス本体", "サキューム", "麻酔器", "カフ圧計"
    ]
    client = get_client()
    for cat in categories:
        try:
            # 既存をチェックして無ければ追加
            existing = client.table("categories").select("id").eq("name", cat).execute()
            if not existing.data:
                client.table("categories").insert({"name": cat}).execute()
        except Exception:
            pass

@st.cache_data(ttl=60)
def get_all_categories():
    """全カテゴリを取得"""
    client = get_client()
    result = client.table("categories").select("*").order("sort_order").order("id").execute()
    return result.data

def get_category_by_id(category_id: int):
    """IDでカテゴリを取得"""
    client = get_client()
    result = client.table("categories").select("*").eq("id", category_id).execute()
    if result.data:
        return result.data[0]
    return None

def create_category(name: str):
    """カテゴリを作成"""
    client = get_client()
    try:
        client.table("categories").insert({"name": name}).execute()
        return True, "カテゴリを作成しました"
    except Exception as e:
        return False, f"カテゴリ作成エラー: {e}"

def update_category_basic_info(category_id: int, new_name: str, description: str, sort_order: int = 0):
    """カテゴリの基本情報を更新"""
    client = get_client()
    try:
        client.table("categories").update({
            "name": new_name,
            "description": description,
            "sort_order": sort_order
        }).eq("id", category_id).execute()
        return True
    except Exception as e:
        print(f"Error updating category: {e}")
        return False

def update_category_name(category_id: int, new_name: str):
    """カテゴリ名を更新（レガシーラッパー）"""
    cat = get_category_by_id(category_id)
    desc = cat.get("description", "") if cat else ""
    order = cat.get("sort_order", 0) if cat else 0
    return update_category_basic_info(category_id, new_name, desc, order)

def delete_category(category_id: int):
    """カテゴリを削除"""
    client = get_client()
    
    # 依存関係チェック
    types = client.table("device_types").select("id").eq("category_id", category_id).execute()
    if types.data:
        return False, f"このカテゴリには {len(types.data)} 件の機種が登録されているため削除できません。"
    
    try:
        client.table("categories").delete().eq("id", category_id).execute()
        return True, "カテゴリを削除しました"
    except Exception as e:
        return False, str(e)

# --- Device Types ---

def create_device_type(category_id: int, name: str):
    """機種を作成"""
    client = get_client()
    result = client.table("device_types").insert({
        "category_id": category_id,
        "name": name
    }).execute()
    if result.data:
        return result.data[0]["id"]
    return None

@st.cache_data(ttl=60)
def get_device_types(category_id: int = None):
    """機種一覧を取得"""
    client = get_client()
    query = client.table("device_types").select("*")
    if category_id:
        query = query.eq("category_id", category_id)
    result = query.execute()
    return result.data

def get_device_type_by_id(type_id: int):
    """IDで機種を取得"""
    client = get_client()
    result = client.table("device_types").select("*").eq("id", type_id).execute()
    if result.data:
        return result.data[0]
    return None

def update_device_type_name(type_id: int, new_name: str) -> bool:
    """機種名を更新"""
    client = get_client()
    try:
        client.table("device_types").update({"name": new_name}).eq("id", type_id).execute()
        return True
    except Exception:
        return False

# --- Items ---

def create_item(name: str, tips: str = "", photo_path: str = ""):
    """構成品を作成"""
    client = get_client()
    result = client.table("items").insert({
        "name": name,
        "tips": tips,
        "photo_path": photo_path
    }).execute()
    if result.data:
        return result.data[0]["id"]
    return None

@st.cache_data(ttl=60)
def get_all_items():
    """全構成品を取得"""
    client = get_client()
    result = client.table("items").select("*").execute()
    return result.data

def get_item_by_exact_name(name: str):
    """名前で構成品を取得"""
    client = get_client()
    result = client.table("items").select("*").eq("name", name).execute()
    if result.data:
        return result.data[0]
    return None

def update_item(item_id: int, name: str, tips: str, photo_path: str):
    """構成品を更新"""
    client = get_client()
    try:
        data = {"name": name, "tips": tips}
        if photo_path:
            data["photo_path"] = photo_path
        client.table("items").update(data).eq("id", item_id).execute()
        return True
    except Exception as e:
        print(e)
        return False

def delete_item(item_id: int):
    """構成品を削除"""
    client = get_client()
    
    # 使用履歴チェック
    check_lines = client.table("check_lines").select("id").eq("item_id", item_id).limit(1).execute()
    if check_lines.data:
        return False, "使用履歴があるため削除できません。"
    
    try:
        client.table("template_lines").delete().eq("item_id", item_id).execute()
        client.table("unit_overrides").delete().eq("item_id", item_id).execute()
        client.table("items").delete().eq("id", item_id).execute()
        return True, "削除しました。"
    except Exception as e:
        return False, str(e)

# --- Template Lines ---

def add_template_line(device_type_id: int, item_id: int, required_qty: int):
    """テンプレート行を追加または更新"""
    client = get_client()
    
    # 既存チェック
    existing = client.table("template_lines").select("id").eq("device_type_id", device_type_id).eq("item_id", item_id).execute()
    
    if existing.data:
        client.table("template_lines").update({"required_qty": required_qty}).eq("id", existing.data[0]["id"]).execute()
    else:
        client.table("template_lines").insert({
            "device_type_id": device_type_id,
            "item_id": item_id,
            "required_qty": required_qty
        }).execute()

def get_template_lines(device_type_id: int):
    """テンプレート行を取得"""
    client = get_client()
    result = client.table("template_lines").select("*, items(name, photo_path)").eq("device_type_id", device_type_id).order("sort_order").execute()
    
    # データ整形
    lines = []
    for row in result.data:
        item = row.get("items", {})
        lines.append({
            "id": row["id"],
            "device_type_id": row["device_type_id"],
            "item_id": row["item_id"],
            "required_qty": row["required_qty"],
            "sort_order": row.get("sort_order", 0),
            "item_name": item.get("name", ""),
            "photo_path": item.get("photo_path", "")
        })
    return lines

def delete_template_line(device_type_id: int, item_id: int):
    """テンプレート行を削除"""
    client = get_client()
    client.table("template_lines").delete().eq("device_type_id", device_type_id).eq("item_id", item_id).execute()

# --- Device Units ---

def create_device_unit(device_type_id: int, lot_number: str, mfg_date: str = "", location: str = "", last_check_date: str = "", next_check_date: str = ""):
    """個体を作成"""
    client = get_client()
    try:
        client.table("device_units").insert({
            "device_type_id": device_type_id,
            "lot_number": lot_number,
            "mfg_date": mfg_date,
            "location": location,
            "last_check_date": last_check_date,
            "next_check_date": next_check_date
        }).execute()
        return True
    except Exception:
        return False

def get_device_units(device_type_id: int):
    """機種の個体一覧を取得"""
    client = get_client()
    result = client.table("device_units").select("*").eq("device_type_id", device_type_id).execute()
    return result.data

def get_device_unit_by_id(unit_id: int):
    """IDで個体を取得"""
    client = get_client()
    result = client.table("device_units").select("*").eq("id", unit_id).execute()
    if result.data:
        return result.data[0]
    return None

def update_device_unit(unit_id: int, lot_number: str, mfg_date: str, location: str, last_check_date: str, next_check_date: str):
    """個体を更新"""
    client = get_client()
    try:
        client.table("device_units").update({
            "lot_number": lot_number,
            "mfg_date": mfg_date,
            "location": location,
            "last_check_date": last_check_date,
            "next_check_date": next_check_date
        }).eq("id", unit_id).execute()
        return True
    except Exception:
        return False

def update_device_unit_status(unit_id: int, status: str):
    """個体のステータスを更新"""
    client = get_client()
    client.table("device_units").update({"status": status}).eq("id", unit_id).execute()

def delete_device_unit(unit_id: int):
    """個体を削除（カスケード）"""
    client = get_client()
    try:
        # 関連データを削除
        loans = client.table("loans").select("id").eq("device_unit_id", unit_id).execute()
        for loan in loans.data:
            client.table("returns").delete().eq("loan_id", loan["id"]).execute()
        
        sessions = client.table("check_sessions").select("id").eq("device_unit_id", unit_id).execute()
        for s in sessions.data:
            client.table("check_lines").delete().eq("check_session_id", s["id"]).execute()
        
        client.table("issues").delete().eq("device_unit_id", unit_id).execute()
        client.table("check_sessions").delete().eq("device_unit_id", unit_id).execute()
        client.table("loans").delete().eq("device_unit_id", unit_id).execute()
        client.table("unit_overrides").delete().eq("device_unit_id", unit_id).execute()
        client.table("device_units").delete().eq("id", unit_id).execute()
        
        return True, "削除しました"
    except Exception as e:
        return False, str(e)

# --- Loans ---

def create_loan(device_unit_id: int, checkout_date: str, destination: str, purpose: str, checker_user_id: int = None, notes: str = ""):
    """貸出を作成"""
    client = get_client()
    result = client.table("loans").insert({
        "device_unit_id": device_unit_id,
        "checkout_date": checkout_date,
        "destination": destination,
        "purpose": purpose,
        "checker_user_id": checker_user_id,
        "notes": notes,
        "status": "open"
    }).execute()
    if result.data:
        return result.data[0]["id"]
    return None

def get_active_loan(device_unit_id: int):
    """アクティブな貸出を取得"""
    client = get_client()
    result = client.table("loans").select("*").eq("device_unit_id", device_unit_id).eq("status", "open").eq("canceled", 0).execute()
    if result.data:
        return result.data[0]
    return None

def close_loan(loan_id: int):
    """貸出をクローズ"""
    client = get_client()
    client.table("loans").update({"status": "closed"}).eq("id", loan_id).execute()

def get_loan_by_id(loan_id: int):
    """IDで貸出を取得"""
    client = get_client()
    result = client.table("loans").select("*").eq("id", loan_id).execute()
    if result.data:
        return result.data[0]
    return None

# --- Check Sessions ---

def create_check_session(session_type: str, device_unit_id: int, loan_id: int = None, performed_by: str = "", device_photo_dir: str = ""):
    """チェックセッションを作成"""
    client = get_client()
    result = client.table("check_sessions").insert({
        "session_type": session_type,
        "device_unit_id": device_unit_id,
        "loan_id": loan_id,
        "performed_by": performed_by,
        "device_photo_dir": device_photo_dir
    }).execute()
    if result.data:
        return result.data[0]["id"]
    return None

def get_check_session_by_loan_id(loan_id: int):
    """貸出IDでチェックセッションを取得"""
    client = get_client()
    result = client.table("check_sessions").select("*").eq("loan_id", loan_id).eq("session_type", "loan").eq("canceled", 0).execute()
    if result.data:
        return result.data[0]
    return None

def get_check_sessions_for_unit(device_unit_id: int, limit: int = 10):
    """個体のチェックセッション履歴を取得"""
    client = get_client()
    result = client.table("check_sessions").select("*").eq("device_unit_id", device_unit_id).eq("canceled", 0).order("performed_at", desc=True).limit(limit).execute()
    return result.data

# --- Check Lines ---

def create_check_line(check_session_id: int, item_id: int, required_qty: int, result_val: str, ng_reason: str = None, found_qty: int = None, comment: str = None):
    """チェック行を作成"""
    client = get_client()
    client.table("check_lines").insert({
        "check_session_id": check_session_id,
        "item_id": item_id,
        "required_qty": required_qty,
        "result": result_val,
        "ng_reason": ng_reason,
        "found_qty": found_qty,
        "comment": comment
    }).execute()

def get_check_lines_for_session(session_id: int):
    """セッションのチェック行を取得"""
    client = get_client()
    result = client.table("check_lines").select("*, items(name)").eq("check_session_id", session_id).execute()
    
    lines = []
    for row in result.data:
        item = row.get("items", {})
        lines.append({
            **row,
            "item_name": item.get("name", "")
        })
    return lines

# --- Issues ---

def create_issue(device_unit_id: int, check_session_id: int = None, summary: str = "", created_by: str = ""):
    """問題を作成"""
    client = get_client()
    result = client.table("issues").insert({
        "device_unit_id": device_unit_id,
        "check_session_id": check_session_id,
        "summary": summary,
        "created_by": created_by,
        "status": "open"
    }).execute()
    if result.data:
        return result.data[0]["id"]
    return None

def get_open_issues_for_unit(device_unit_id: int):
    """個体のオープンな問題を取得"""
    client = get_client()
    result = client.table("issues").select("*").eq("device_unit_id", device_unit_id).eq("status", "open").eq("canceled", 0).execute()
    return result.data

def resolve_issue(issue_id: int, resolved_by: str = ""):
    """問題を解決"""
    client = get_client()
    import datetime
    client.table("issues").update({
        "status": "resolved",
        "resolved_at": datetime.datetime.now().isoformat(),
        "resolved_by": resolved_by
    }).eq("id", issue_id).execute()

# --- Returns ---

def create_return(loan_id: int, return_date: str, checker_user_id: int = None):
    """返却を作成"""
    client = get_client()
    result = client.table("returns").insert({
        "loan_id": loan_id,
        "return_date": return_date,
        "checker_user_id": checker_user_id
    }).execute()
    if result.data:
        return result.data[0]["id"]
    return None

# --- Unit Overrides ---

def add_unit_override(device_unit_id: int, item_id: int, action: str, qty: int = None):
    """個体差分を追加"""
    client = get_client()
    client.table("unit_overrides").insert({
        "device_unit_id": device_unit_id,
        "item_id": item_id,
        "action": action,
        "qty": qty
    }).execute()

def get_unit_overrides(device_unit_id: int):
    """個体差分を取得"""
    client = get_client()
    result = client.table("unit_overrides").select("*").eq("device_unit_id", device_unit_id).execute()
    return result.data

def delete_unit_override(override_id: int):
    """個体差分を削除"""
    client = get_client()
    client.table("unit_overrides").delete().eq("id", override_id).execute()

# --- System Settings ---

def get_system_setting(key: str) -> Optional[str]:
    """システム設定を取得"""
    client = get_client()
    result = client.table("system_settings").select("value").eq("key", key).execute()
    if result.data:
        return result.data[0]["value"]
    return None

def set_system_setting(key: str, value: str):
    """システム設定を保存"""
    client = get_client()
    
    existing = client.table("system_settings").select("key").eq("key", key).execute()
    if existing.data:
        client.table("system_settings").update({"value": value}).eq("key", key).execute()
    else:
        client.table("system_settings").insert({"key": key, "value": value}).execute()

# --- Notification Groups ---

def get_notification_group_users(category_id: int):
    """カテゴリの通知グループユーザーを取得"""
    client = get_client()
    result = client.table("notification_groups").select("user_id, users(id, name, email)").eq("category_id", category_id).execute()
    
    users = []
    for row in result.data:
        user = row.get("users", {})
        if user:
            users.append(user)
    return users

def add_user_to_notification_group(category_id: int, user_id: int):
    """ユーザーを通知グループに追加"""
    client = get_client()
    try:
        client.table("notification_groups").insert({
            "category_id": category_id,
            "user_id": user_id
        }).execute()
        return True
    except Exception:
        return False

def remove_user_from_notification_group(category_id: int, user_id: int):
    """ユーザーを通知グループから削除"""
    client = get_client()
    client.table("notification_groups").delete().eq("category_id", category_id).eq("user_id", user_id).execute()

# --- Notification Logs ---

def log_notification(event_type: str, related_id: int, recipient: str, status: str, error_message: str = None):
    """通知ログを記録"""
    client = get_client()
    client.table("notification_logs").insert({
        "event_type": event_type,
        "related_id": related_id,
        "recipient": recipient,
        "status": status,
        "error_message": error_message
    }).execute()

# --- Departments ---

def get_all_departments():
    """全部署を取得"""
    client = get_client()
    result = client.table("departments").select("*").execute()
    return result.data

def create_department(name: str):
    """部署を作成"""
    client = get_client()
    try:
        client.table("departments").insert({"name": name}).execute()
        return True
    except Exception:
        return False

# --- Synthesized Checklist (Logic) ---

def get_synthesized_checklist(device_type_id: int, device_unit_id: int):
    """テンプレートと個体差分を合成したチェックリストを取得"""
    template_lines = get_template_lines(device_type_id)
    overrides = get_unit_overrides(device_unit_id)
    
    checklist = []
    for line in template_lines:
        item_id = line["item_id"]
        required_qty = line["required_qty"]
        
        # 差分を適用
        for ov in overrides:
            if ov["item_id"] == item_id:
                if ov["action"] == "remove":
                    required_qty = 0
                elif ov["action"] == "qty" and ov["qty"] is not None:
                    required_qty = ov["qty"]
        
        if required_qty > 0:
            checklist.append({
                "item_id": item_id,
                "name": line.get("item_name", ""),
                "required_qty": required_qty,
                "photo_path": line.get("photo_path", "")
            })
    
    # 追加アイテム
    for ov in overrides:
        if ov["action"] == "add":
            # テンプレートに無いアイテム
            if not any(c["item_id"] == ov["item_id"] for c in checklist):
                # アイテム情報を取得
                client = get_client()
                item_result = client.table("items").select("*").eq("id", ov["item_id"]).execute()
                if item_result.data:
                    item = item_result.data[0]
                    checklist.append({
                        "item_id": ov["item_id"],
                        "name": item.get("name", ""),
                        "required_qty": ov["qty"] or 1,
                        "photo_path": item.get("photo_path", "")
                    })
    
    return checklist

# --- Statistics ---

def get_status_counts_for_category(category_id: int) -> Dict[str, int]:
    """カテゴリのステータス別個体数を取得"""
    client = get_client()
    
    # カテゴリの機種を取得
    types = client.table("device_types").select("id").eq("category_id", category_id).execute()
    type_ids = [t["id"] for t in types.data]
    
    if not type_ids:
        return {"in_stock": 0, "loaned": 0, "needs_attention": 0}
    
    # 各機種の個体を取得
    units = client.table("device_units").select("status").in_("device_type_id", type_ids).execute()
    
    counts = {"in_stock": 0, "loaned": 0, "needs_attention": 0}
    for unit in units.data:
        status = unit.get("status", "in_stock")
        if status in counts:
            counts[status] += 1
    
    return counts

# --- Migration compatibility functions ---
# これらの関数はSQLite版との互換性のために空の実装を提供

def migrate_user_department():
    pass

def migrate_category_managing_department():
    pass

def migrate_category_description():
    pass

def migrate_category_sort_order():
    pass

def migrate_dates():
    pass

def migrate_category_visibility():
    pass

def update_category_visibility(category_id: int, is_visible: bool):
    """カテゴリの可視性を更新（互換性のため）"""
    # Supabaseではis_visible列を使用しない場合、この関数は不要
    pass

def move_category_order(category_id: int, direction: str):
    """カテゴリの順序を変更"""
    client = get_client()
    
    categories = client.table("categories").select("id, sort_order").order("sort_order").order("id").execute()
    cat_list = categories.data
    
    idx = -1
    for i, cat in enumerate(cat_list):
        if cat["id"] == category_id:
            idx = i
            break
    
    if idx == -1:
        return False, "Category not found"
    
    swap_idx = -1
    if direction == "up" and idx > 0:
        swap_idx = idx - 1
    elif direction == "down" and idx < len(cat_list) - 1:
        swap_idx = idx + 1
    
    if swap_idx != -1:
        cat_list[idx], cat_list[swap_idx] = cat_list[swap_idx], cat_list[idx]
        
        for i, cat in enumerate(cat_list):
            new_order = (i + 1) * 10
            client.table("categories").update({"sort_order": new_order}).eq("id", cat["id"]).execute()
        
        return True, "順序を更新しました"
    
    return False, "これ以上移動できません"

# --- SQLite互換性のためのエイリアス・追加関数 ---

def update_unit_status(unit_id: int, status: str):
    """個体のステータスを更新（SQLite互換エイリアス）"""
    return update_device_unit_status(unit_id, status)

def get_open_issues(device_unit_id: int):
    """オープンな問題を取得（SQLite互換エイリアス）"""
    return get_open_issues_for_unit(device_unit_id)

def cancel_record(table: str, record_id: int, user_name: str, reason: str):
    """レコードをキャンセル"""
    client = get_client()
    import datetime
    
    valid_tables = ['loans', 'returns', 'check_sessions', 'issues']
    if table not in valid_tables:
        raise ValueError(f"Invalid table for cancellation: {table}")
    
    client.table(table).update({
        "canceled": 1,
        "canceled_at": datetime.datetime.now().isoformat(),
        "canceled_by": user_name,
        "cancel_reason": reason
    }).eq("id", record_id).execute()

def get_related_records(loan_id: int = None, return_id: int = None):
    """関連レコードを取得（キャンセル用）"""
    client = get_client()
    
    res = {'returns': [], 'check_sessions': [], 'issues': []}
    
    if loan_id:
        # 関連する返却を取得
        returns = client.table("returns").select("id").eq("loan_id", loan_id).eq("canceled", 0).execute()
        res['returns'] = [r['id'] for r in returns.data]
        
        # 関連するチェックセッションを取得
        sessions = client.table("check_sessions").select("id").eq("loan_id", loan_id).eq("canceled", 0).execute()
        res['check_sessions'] = [s['id'] for s in sessions.data]
    
    # 関連する問題を取得
    if res['check_sessions']:
        for session_id in res['check_sessions']:
            issues = client.table("issues").select("id").eq("check_session_id", session_id).eq("status", "open").execute()
            res['issues'].extend([i['id'] for i in issues.data])
    
    return res

def get_loan_history(device_unit_id: int, limit: int = None, offset: int = 0, include_canceled: bool = True):
    """貸出履歴を取得"""
    client = get_client()
    
    query = client.table("loans").select("*").eq("device_unit_id", device_unit_id)
    
    if not include_canceled:
        query = query.eq("canceled", 0)
    
    query = query.order("id", desc=True)
    
    if limit:
        query = query.limit(limit).offset(offset)
    
    result = query.execute()
    return result.data

def get_check_session_lines(check_session_id: int):
    """チェックセッションの行を取得"""
    client = get_client()
    result = client.table("check_lines").select("*, items(name, photo_path)").eq("check_session_id", check_session_id).execute()
    
    lines = []
    for row in result.data:
        item = row.get("items", {})
        lines.append({
            **row,
            "item_name": item.get("name", ""),
            "photo_path": item.get("photo_path", "")
        })
    return lines

def get_all_check_sessions_for_loan(loan_id: int):
    """ローンに関連する全チェックセッションを取得"""
    client = get_client()
    result = client.table("check_sessions").select("*").eq("loan_id", loan_id).order("id").execute()
    return result.data

def delete_unit_override(override_id: int):
    """個体差分を削除"""
    client = get_client()
    client.table("unit_overrides").delete().eq("id", override_id).execute()

def delete_device_type(type_id: int):
    """機種を削除（カスケード）"""
    client = get_client()
    
    # 関連する個体を取得
    units = get_device_units(type_id)
    
    # 各個体を削除
    for unit in units:
        result = delete_device_unit(unit['id'])
        if not result[0]:
            return False, f"個体ID {unit['id']} の削除に失敗しました"
    
    try:
        # テンプレート行を削除
        client.table("template_lines").delete().eq("device_type_id", type_id).execute()
        # 機種を削除
        client.table("device_types").delete().eq("id", type_id).execute()
        return True, "機種を削除しました"
    except Exception as e:
        return False, str(e)

