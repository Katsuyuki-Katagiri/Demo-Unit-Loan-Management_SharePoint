# Supabase Database Layer
# このファイルはSupabaseをデータベースとして使用するための関数を提供します

import os
from typing import Optional, List, Dict, Any
import bcrypt
import streamlit as st
import time
import httpx
from supabase import create_client, Client

# Supabase接続
@st.cache_resource
def get_supabase_client() -> Client:
    """Supabaseクライアントを取得（キャッシュされる）"""
    url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        raise ValueError("SUPABASE_URL と SUPABASE_KEY が設定されていません")
    
    return create_client(url, key)

def get_client() -> Client:
    """Supabaseクライアントを取得（st.cache_resourceでキャッシュ）"""
    return get_supabase_client()

def retry_supabase_query(max_retries=3, delay=1, exceptions=(httpx.ReadError, httpx.ConnectError)):
    """Supabaseクエリのリトライデコレータ"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    if i == max_retries - 1:
                        raise
                    time.sleep(delay * (i + 1))
            return func(*args, **kwargs) # Should not be reached
        return wrapper
    return decorator

# アップロードディレクトリ（写真用）- ローカルフォールバック用
UPLOAD_DIR = os.path.join("data", "uploads")
# SQLite互換性のためのダミーパス（Supabase使用時は実際には使用されない）
DB_PATH = os.path.join("data", "app.db")
# Supabase Storage バケット名
STORAGE_BUCKET = "item-photos"


# --- Supabase Storage ---

def upload_photo_to_storage(file_bytes: bytes, filename: str) -> str:
    """
    Supabase Storageに写真をアップロードし、公開URLを返す
    
    Args:
        file_bytes: アップロードするファイルのバイトデータ
        filename: ファイル名（ユニークにすること推奨）
    
    Returns:
        公開URL（str）、失敗時は空文字列
    """
    client = get_client()
    try:
        # Storageにアップロード
        result = client.storage.from_(STORAGE_BUCKET).upload(
            path=filename,
            file=file_bytes,
            file_options={"content-type": "image/webp", "upsert": "true"}
        )
        
        # 公開URLを取得
        public_url = client.storage.from_(STORAGE_BUCKET).get_public_url(filename)
        return public_url
        
    except Exception as e:
        print(f"Storage upload error: {e}")
        return ""


def delete_photo_from_storage(filename: str) -> bool:
    """
    Supabase Storageから写真を削除
    
    Args:
        filename: 削除するファイル名
    
    Returns:
        成功時True、失敗時False
    """
    client = get_client()
    try:
        client.storage.from_(STORAGE_BUCKET).remove([filename])
        return True
    except Exception as e:
        print(f"Storage delete error: {e}")
        return False


def get_photo_public_url(filename: str) -> str:
    """
    ファイル名から公開URLを取得
    
    Args:
        filename: ファイル名
    
    Returns:
        公開URL（str）
    """
    if not filename:
        return ""
    
    # すでにURLの場合はそのまま返す
    if filename.startswith("http"):
        return filename
    
    client = get_client()
    try:
        return client.storage.from_(STORAGE_BUCKET).get_public_url(filename)
    except Exception as e:
        print(f"Get public URL error: {e}")
        return ""


# セッション写真用バケット（貸出・返却時の写真）
SESSION_PHOTOS_BUCKET = "session-photos"

# 写真保存上限数
SESSION_PHOTOS_LIMIT = 2000


def count_all_session_photos() -> int:
    """
    session-photosバケット内の全写真数をカウント
    
    Returns:
        写真の総数
    """
    client = get_client()
    try:
        # ルートフォルダ一覧を取得
        folders = client.storage.from_(SESSION_PHOTOS_BUCKET).list("")
        total_count = 0
        
        for folder in folders:
            folder_name = folder.get("name", "")
            if folder_name and folder.get("id") is None:  # フォルダの場合（idがない）
                # フォルダ内のファイル一覧を取得
                files = client.storage.from_(SESSION_PHOTOS_BUCKET).list(folder_name)
                for f in files:
                    if f.get("name") and f.get("id"):  # ファイルの場合（idがある）
                        total_count += 1
        
        return total_count
    except Exception as e:
        print(f"Count session photos error: {e}")
        return 0


def get_protected_session_folders() -> set:
    """
    削除対象から除外すべきセッションフォルダを取得
    （返却されていない貸出に関連するセッション）
    
    Returns:
        保護すべきフォルダ名のセット
    """
    client = get_client()
    protected = set()
    
    try:
        # ステータスが open（返却されていない）の貸出を取得
        open_loans = client.table("loans").select("id").eq("status", "open").eq("canceled", 0).execute()
        
        if not open_loans.data:
            return protected
        
        open_loan_ids = [loan["id"] for loan in open_loans.data]
        
        # オープン貸出に関連するチェックセッションの device_photo_dir を取得
        for loan_id in open_loan_ids:
            sessions = client.table("check_sessions").select("device_photo_dir").eq("loan_id", loan_id).execute()
            for session in sessions.data:
                photo_dir = session.get("device_photo_dir", "")
                if photo_dir:
                    protected.add(photo_dir)
        
        return protected
    except Exception as e:
        print(f"Get protected folders error: {e}")
        return protected


def get_oldest_session_folders(limit: int = 10) -> list:
    """
    最も古いセッションフォルダを取得（作成日時順）
    ※返却されていない貸出に関連するフォルダは除外
    
    Args:
        limit: 取得するフォルダ数
    
    Returns:
        古い順にソートされたフォルダ名のリスト
    """
    client = get_client()
    try:
        folders = client.storage.from_(SESSION_PHOTOS_BUCKET).list("")
        
        # 保護すべきフォルダを取得
        protected_folders = get_protected_session_folders()
        
        # フォルダ情報を収集（created_atでソート）
        folder_list = []
        for folder in folders:
            folder_name = folder.get("name", "")
            created_at = folder.get("created_at", "")
            if folder_name and folder.get("id") is None:  # フォルダの場合
                # 保護対象フォルダは除外
                if folder_name in protected_folders:
                    continue
                folder_list.append({
                    "name": folder_name,
                    "created_at": created_at
                })
        
        # 作成日時の古い順にソート
        folder_list.sort(key=lambda x: x.get("created_at", ""))
        
        # 指定数まで返す
        return [f["name"] for f in folder_list[:limit]]
    except Exception as e:
        print(f"Get oldest folders error: {e}")
        return []


def delete_session_folder(folder_name: str) -> tuple:
    """
    セッションフォルダとその中のファイルを全て削除
    
    Args:
        folder_name: 削除するフォルダ名
    
    Returns:
        (成功: True/False, 削除したファイル数)
    """
    client = get_client()
    try:
        # フォルダ内のファイル一覧を取得
        files = client.storage.from_(SESSION_PHOTOS_BUCKET).list(folder_name)
        
        if not files:
            return True, 0
        
        # ファイルパスのリストを作成
        file_paths = []
        for f in files:
            if f.get("name"):
                file_paths.append(f"{folder_name}/{f['name']}")
        
        if file_paths:
            # ファイルを削除
            client.storage.from_(SESSION_PHOTOS_BUCKET).remove(file_paths)
        
        return True, len(file_paths)
    except Exception as e:
        print(f"Delete session folder error: {e}")
        return False, 0


def cleanup_old_session_photos() -> tuple:
    """
    写真が上限を超えている場合、古いセッションフォルダを削除
    
    Returns:
        (削除したフォルダ数, 削除した写真数)
    """
    try:
        total_photos = count_all_session_photos()
        
        if total_photos <= SESSION_PHOTOS_LIMIT:
            return 0, 0
        
        # 削除が必要な写真数
        photos_to_delete = total_photos - SESSION_PHOTOS_LIMIT
        deleted_folders = 0
        deleted_photos = 0
        
        # 古いフォルダから順に削除
        while deleted_photos < photos_to_delete:
            oldest_folders = get_oldest_session_folders(5)
            
            if not oldest_folders:
                break
            
            for folder_name in oldest_folders:
                success, count = delete_session_folder(folder_name)
                if success:
                    deleted_folders += 1
                    deleted_photos += count
                    print(f"セッション写真クリーンアップ: {folder_name} を削除 ({count}枚)")
                
                if deleted_photos >= photos_to_delete:
                    break
        
        print(f"セッション写真クリーンアップ完了: {deleted_folders}フォルダ, {deleted_photos}枚を削除")
        return deleted_folders, deleted_photos
        
    except Exception as e:
        print(f"Cleanup old session photos error: {e}")
        return 0, 0


def upload_session_photo(session_id: str, file_bytes: bytes, index: int = 0) -> str:
    """
    貸出・返却時のセッション写真をSupabase Storageにアップロード
    
    アップロード後、写真総数が上限（2000枚）を超えていれば古いものから削除
    
    Args:
        session_id: セッションID（例: loan_123_20260119_120000）
        file_bytes: 画像のバイトデータ
        index: 写真の連番
    
    Returns:
        公開URL（str）、失敗時は空文字列
    """
    client = get_client()
    filename = f"{session_id}/photo_{index}.webp"
    
    try:
        result = client.storage.from_(SESSION_PHOTOS_BUCKET).upload(
            path=filename,
            file=file_bytes,
            file_options={"content-type": "image/webp", "upsert": "true"}
        )
        
        public_url = client.storage.from_(SESSION_PHOTOS_BUCKET).get_public_url(filename)
        
        # アップロード成功後、古い写真をクリーンアップ（バックグラウンドで実行）
        # index == 0の時のみクリーンアップを実行（セッションの最初の写真時のみ）
        if index == 0:
            import threading
            def _background_cleanup():
                try:
                    cleanup_old_session_photos()
                except Exception as cleanup_error:
                    # クリーンアップエラーはログのみ、アップロード成功は維持
                    print(f"Cleanup error (non-critical): {cleanup_error}")
            
            cleanup_thread = threading.Thread(target=_background_cleanup, daemon=True)
            cleanup_thread.start()
        
        return public_url
        
    except Exception as e:
        print(f"Session photo upload error: {e}")
        return ""


def get_session_photos(session_id: str) -> list:
    """
    セッションの写真URL一覧を取得
    
    Args:
        session_id: セッションID
    
    Returns:
        公開URLのリスト
    """
    client = get_client()
    try:
        # フォルダ内のファイル一覧を取得
        result = client.storage.from_(SESSION_PHOTOS_BUCKET).list(session_id)
        if result:
            urls = []
            for item in result:
                if item.get('name'):
                    url = client.storage.from_(SESSION_PHOTOS_BUCKET).get_public_url(f"{session_id}/{item['name']}")
                    urls.append(url)
            return urls
        return []
    except Exception as e:
        print(f"Get session photos error: {e}")
        return []


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

@retry_supabase_query()
def get_user_by_email(email: str):
    """メールアドレスでユーザーを取得"""
    client = get_client()
    result = client.table("users").select("*").eq("email", email).execute()
    if result.data:
        return result.data[0]
    return None

@retry_supabase_query()
def get_user_by_id(user_id: int):
    """IDでユーザーを取得"""
    client = get_client()
    result = client.table("users").select("*").eq("id", user_id).execute()
    if result.data:
        return result.data[0]
    return None

@retry_supabase_query()
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

def update_user_password(user_id: int, new_password: str) -> tuple:
    """ユーザーのパスワードを更新"""
    client = get_client()
    
    # ユーザー確認
    result = client.table("users").select("id").eq("id", user_id).execute()
    if not result.data:
        return False, "ユーザーが見つかりません。"
    
    try:
        password_bytes = new_password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt).decode('utf-8')
        
        client.table("users").update({
            "password_hash": hashed
        }).eq("id", user_id).execute()
        return True, "パスワードを更新しました。"
    except Exception as e:
        return False, f"パスワード更新エラー: {e}"

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

@retry_supabase_query()
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

# --- バッチクエリ関数（パフォーマンス最適化用） ---

@retry_supabase_query()
def get_all_device_units():
    """全個体を一括取得（バッチクエリ用）"""
    client = get_client()
    result = client.table("device_units").select("*").execute()
    return result.data

@retry_supabase_query()
def get_device_units_for_types(type_ids: list):
    """
    複数の機種の個体を一括取得
    
    Returns:
        {type_id: [unit1, unit2, ...], ...} のディクショナリ
    """
    if not type_ids:
        return {}
    client = get_client()
    result = client.table("device_units").select("*").in_("device_type_id", type_ids).execute()
    
    # 機種IDでグループ化
    units_by_type = {}
    for unit in result.data:
        type_id = unit['device_type_id']
        if type_id not in units_by_type:
            units_by_type[type_id] = []
        units_by_type[type_id].append(unit)
    return units_by_type

@retry_supabase_query()
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
    client = get_client()
    result = client.table("users").select("*").in_("id", unique_ids).execute()
    
    # IDでディクショナリ化
    return {u['id']: u for u in result.data}

@retry_supabase_query()
def get_active_loans_batch(unit_ids: list):
    """
    複数個体のアクティブな貸出を一括取得
    
    Returns:
        {unit_id: loan_dict, ...} のディクショナリ（貸出中の個体のみ）
    """
    if not unit_ids:
        return {}
    client = get_client()
    result = client.table("loans").select("*").in_("device_unit_id", unit_ids).eq("status", "open").eq("canceled", 0).execute()
    
    # 個体IDでディクショナリ化
    return {l['device_unit_id']: l for l in result.data}

@retry_supabase_query()
def get_all_loan_periods(unit_ids: list, start_date: str, end_date: str):
    """
    複数個体の貸出期間を一括取得（稼働率計算用）
    
    Returns:
        {unit_id: [(checkout_date, return_date), ...], ...} のディクショナリ
    """
    if not unit_ids:
        return {}
    client = get_client()
    
    # 期間と重なる可能性のある貸出を取得
    # checkout_date <= end_date かつ (return_date >= start_date または return_date IS NULL)
    result = client.table("loans").select(
        "device_unit_id, checkout_date, returns(return_date)"
    ).in_("device_unit_id", unit_ids).eq("canceled", 0).lte("checkout_date", end_date).execute()
    
    # 個体IDでグループ化
    periods_by_unit = {}
    for loan in result.data:
        unit_id = loan['device_unit_id']
        if unit_id not in periods_by_unit:
            periods_by_unit[unit_id] = []
        
        return_date = None
        if loan.get('returns') and isinstance(loan['returns'], list) and len(loan['returns']) > 0:
            return_date = loan['returns'][0].get('return_date')
        elif loan.get('returns') and isinstance(loan['returns'], dict):
            return_date = loan['returns'].get('return_date')
        
        periods_by_unit[unit_id].append({
            'checkout_date': loan['checkout_date'],
            'return_date': return_date
        })
    
    return periods_by_unit

@retry_supabase_query()
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
    try:
        client.table("device_units").update({"status": status}).eq("id", unit_id).execute()
        return True
    except Exception as e:
        print(f"Error updating unit status: {e}")
        return False

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

def create_loan(device_unit_id: int, checkout_date: str, destination: str, purpose: str, checker_user_id: int = None, notes: str = "", assetment_checked: bool = False):
    """貸出を作成"""
    client = get_client()
    result = client.table("loans").insert({
        "device_unit_id": device_unit_id,
        "checkout_date": checkout_date,
        "destination": destination,
        "purpose": purpose,
        "checker_user_id": checker_user_id,
        "notes": notes,
        "assetment_checked": assetment_checked,
        "status": "open"
    }).execute()
    if result.data:
        return result.data[0]["id"]
    return None

@retry_supabase_query()
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

def create_check_line(check_session_id: int, item_id: int, required_qty: int, result: str, ng_reason: str = None, found_qty: int = None, comment: str = None):
    """チェック明細を作成"""
    client = get_client()
    data = {
        "check_session_id": check_session_id,
        "item_id": item_id,
        "required_qty": required_qty,
        "result": result
    }
    if ng_reason:
        data["ng_reason"] = ng_reason
    if found_qty is not None:
        data["found_qty"] = found_qty
    if comment:
        data["comment"] = comment
        
    client.table("check_lines").insert(data).execute()

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

@retry_supabase_query()
def get_open_issues_for_unit(device_unit_id: int):
    """個体のオープンな問題を取得（リトライ付き）"""
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

def create_return(
    loan_id: int, 
    return_date: str, 
    checker_user_id: int = None, 
    assetment_returned: bool = False, 
    notes: str = None, 
    confirmation_checked: bool = False
):
    """返却を作成し、貸出をクローズ"""
    client = get_client()
    
    # 1. Create Return
    result = client.table("returns").insert({
        "loan_id": loan_id,
        "return_date": return_date,
        "checker_user_id": checker_user_id,
        "assetment_returned": assetment_returned,
        "notes": notes,
        "confirmation_checked": confirmation_checked
    }).execute()
    
    if result.data:
        # 2. Close Loan
        client.table("loans").update({"status": "closed"}).eq("id", loan_id).execute()
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

@retry_supabase_query()
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
        return True, "部署を作成しました"
    except Exception as e:
        return False, f"作成に失敗しました: {str(e)}"

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
    result = client.table("check_sessions").select("*").eq("loan_id", loan_id).eq("canceled", 0).order("id").execute()
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

@retry_supabase_query()
def get_notification_members(category_id: int):
    """カテゴリの通知メンバーを取得"""
    client = get_client()
    result = client.table("notification_groups").select("user_id, users(id, name, email)").eq("category_id", category_id).execute()
    
    members = []
    for row in result.data:
        user = row.get("users", {})
        if user:
            members.append(user)
    return members

def add_notification_member(category_id: int, user_id: int):
    """通知メンバーを追加"""
    client = get_client()
    try:
        client.table("notification_groups").insert({
            "category_id": category_id,
            "user_id": user_id
        }).execute()
        return True
    except Exception:
        return False

def remove_notification_member(category_id: int, user_id: int):
    """通知メンバーを削除"""
    client = get_client()
    client.table("notification_groups").delete().eq("category_id", category_id).eq("user_id", user_id).execute()

def get_category_managing_department(category_id: int):
    """カテゴリの管理部署を取得"""
    client = get_client()
    
    # カテゴリを取得
    cat_result = client.table("categories").select("managing_department_id").eq("id", category_id).execute()
    if not cat_result.data or not cat_result.data[0].get("managing_department_id"):
        return None
    
    dept_id = cat_result.data[0]["managing_department_id"]
    
    # 部署を取得
    dept_result = client.table("departments").select("*").eq("id", dept_id).execute()
    if dept_result.data:
        return dept_result.data[0]
    return None

def update_category_managing_department(category_id: int, department_id: int = None):
    """カテゴリの管理部署を更新"""
    client = get_client()
    try:
        client.table("categories").update({"managing_department_id": department_id}).eq("id", category_id).execute()
        return True
    except Exception:
        return False

def get_department_by_id(department_id: int):
    """部署をIDで取得"""
    client = get_client()
    result = client.table("departments").select("*").eq("id", department_id).execute()
    if result.data:
        return result.data[0]
    return None

def update_department(department_id: int, name: str):
    """部署を更新"""
    client = get_client()
    try:
        client.table("departments").update({"name": name}).eq("id", department_id).execute()
        return True
    except Exception:
        return False

def delete_department(department_id: int):
    """部署を削除"""
    client = get_client()
    
    # 使用中か確認
    users = client.table("users").select("id").eq("department_id", department_id).limit(1).execute()
    if users.data:
        return False, "この部署にはユーザーが所属しているため削除できません"
    
    try:
        client.table("departments").delete().eq("id", department_id).execute()
        return True, "部署を削除しました"
    except Exception as e:
        return False, str(e)

def update_user_department(user_id: int, department_id: int = None):
    """ユーザーの部署を更新"""
    client = get_client()
    client.table("users").update({"department_id": department_id}).eq("id", user_id).execute()

def get_users_by_department(department_id: int = None):
    """部署でユーザーを取得"""
    client = get_client()
    if department_id:
        result = client.table("users").select("*").eq("department_id", department_id).execute()
    else:
        result = client.table("users").select("*").is_("department_id", "null").execute()
    return result.data

def get_notification_logs(limit: int = 50):
    """通知ログを取得"""
    client = get_client()
    result = client.table("notification_logs").select("*").order("created_at", desc=True).limit(limit).execute()
    return result.data

def save_system_setting(key: str, value: str):
    """システム設定を保存（エイリアス）"""
    return set_system_setting(key, value)

def get_unit_status_counts(category_id: int = None):
    """ステータスごとの個体数を取得"""
    client = get_client()
    
    if category_id:
        # カテゴリの機種を取得
        types = client.table("device_types").select("id").eq("category_id", category_id).execute()
        type_ids = [t["id"] for t in types.data]
        
        if not type_ids:
            return {"in_stock": 0, "loaned": 0, "needs_attention": 0}
        
        # 各機種の個体を取得
        units = client.table("device_units").select("status").in_("device_type_id", type_ids).execute()
    else:
        units = client.table("device_units").select("status").execute()
    
    counts = {"in_stock": 0, "loaned": 0, "needs_attention": 0}
    for unit in units.data:
        status = unit.get("status", "in_stock")
        if status in counts:
            counts[status] += 1
    
    return counts

def reset_database_keep_admin():
    """データベースをリセット（管理者のみ保持）"""
    client = get_client()
    
    try:
        # ログインユーザー以外を削除
        users = client.table("users").select("id, email").execute()
        for user in users.data:
            if user["email"] != "admin@example.com":
                client.table("users").delete().eq("id", user["id"]).execute()
        
        # トランザクションデータを削除
        client.table("check_lines").delete().neq("id", 0).execute()
        client.table("check_sessions").delete().neq("id", 0).execute()
        client.table("issues").delete().neq("id", 0).execute()
        client.table("returns").delete().neq("id", 0).execute()
        client.table("loans").delete().neq("id", 0).execute()
        client.table("unit_overrides").delete().neq("id", 0).execute()
        client.table("device_units").delete().neq("id", 0).execute()
        client.table("template_lines").delete().neq("id", 0).execute()
        client.table("device_types").delete().neq("id", 0).execute()
        client.table("items").delete().neq("id", 0).execute()
        client.table("notification_groups").delete().neq("id", 0).execute()
        client.table("notification_logs").delete().neq("id", 0).execute()
        
        # カテゴリを再シード
        seed_categories()
        
        return True, "データベースをリセットしました"
    except Exception as e:
        return False, str(e)

# マイグレーション関数（Supabaseでは不要だが互換性のため定義）
def migrate_notifications_table():
    pass

def migrate_system_settings_table():
    pass

def migrate_phase5():
    pass

def migrate_loans_assetment_check():
    pass

def migrate_loans_notes():
    pass

def migrate_returns_assetment_check():
    pass

def migrate_returns_notes():
    pass

def migrate_returns_confirmation_check():
    pass

# --- Login History ---

def record_login_history(user_id: int, email: str, user_name: str, ip_address: str = None, user_agent: str = None, success: bool = True):
    """ログイン履歴を記録"""
    client = get_client()
    try:
        client.table("login_history").insert({
            "user_id": user_id,
            "email": email,
            "user_name": user_name,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "success": success
        }).execute()
        return True
    except Exception as e:
        print(f"Login history record error: {e}")
        return False

def get_login_history(user_id: int = None, limit: int = 100):
    """ログイン履歴を取得"""
    client = get_client()
    query = client.table("login_history").select("*")
    
    if user_id:
        query = query.eq("user_id", user_id)
    
    result = query.order("login_at", desc=True).limit(limit).execute()
    return result.data

# --- logic.py用の抽象化関数 ---

def get_return_by_id(return_id: int):
    """返却IDで返却レコードを取得"""
    client = get_client()
    result = client.table("returns").select("*").eq("id", return_id).execute()
    if result.data:
        return result.data[0]
    return None

def reopen_loan(loan_id: int):
    """貸出を再オープン（返却キャンセル時）"""
    client = get_client()
    client.table("loans").update({"status": "open"}).eq("id", loan_id).execute()

def get_return_check_sessions(loan_id: int):
    """返却に関連するチェックセッションを取得"""
    client = get_client()
    result = client.table("check_sessions").select("id").eq("loan_id", loan_id).eq("session_type", "return").eq("canceled", 0).execute()
    return [row['id'] for row in result.data]

def get_issues_by_session_id(session_id: int):
    """セッションIDに関連するオープンなIssueを取得"""
    client = get_client()
    result = client.table("issues").select("id").eq("check_session_id", session_id).eq("canceled", 0).execute()
    return [row['id'] for row in result.data]

def get_loan_periods_for_unit(device_unit_id: int):
    """稼働率計算用：個体の貸出期間一覧を取得"""
    client = get_client()
    
    # 貸出を取得
    loans_result = client.table("loans").select("id, checkout_date, status, canceled").eq("device_unit_id", device_unit_id).eq("canceled", 0).execute()
    
    results = []
    for loan in loans_result.data:
        # 対応する返却を取得
        return_result = client.table("returns").select("return_date").eq("loan_id", loan["id"]).eq("canceled", 0).execute()
        return_date = return_result.data[0]["return_date"] if return_result.data else None
        
        results.append({
            "checkout_date": loan["checkout_date"],
            "return_date": return_date,
            "status": loan["status"],
            "canceled": loan["canceled"]
        })
    
    return results
