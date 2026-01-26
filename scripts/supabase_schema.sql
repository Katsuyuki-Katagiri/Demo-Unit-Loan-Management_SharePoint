-- Supabase テーブル作成スクリプト
-- このスクリプトをSupabaseダッシュボードの「SQL Editor」で実行してください

-- 1. Departments テーブル（先に作成：外部キー参照用）
CREATE TABLE IF NOT EXISTS departments (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

-- 2. Users テーブル
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    department_id INTEGER REFERENCES departments(id)
);

-- 3. Categories テーブル
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    sort_order INTEGER DEFAULT 0,
    managing_department_id INTEGER REFERENCES departments(id)
);

-- 4. Device Types テーブル
CREATE TABLE IF NOT EXISTS device_types (
    id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    name TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0
);

-- 5. Items テーブル
CREATE TABLE IF NOT EXISTS items (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    tips TEXT,
    photo_path TEXT
);

-- 6. Template Lines テーブル
CREATE TABLE IF NOT EXISTS template_lines (
    id SERIAL PRIMARY KEY,
    device_type_id INTEGER NOT NULL REFERENCES device_types(id),
    item_id INTEGER NOT NULL REFERENCES items(id),
    required_qty INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0
);

-- 7. Device Units テーブル
CREATE TABLE IF NOT EXISTS device_units (
    id SERIAL PRIMARY KEY,
    device_type_id INTEGER NOT NULL REFERENCES device_types(id),
    lot_number TEXT NOT NULL,
    mfg_date TEXT,
    location TEXT,
    note TEXT,
    status TEXT DEFAULT 'in_stock',
    last_check_date TEXT,
    next_check_date TEXT,
    missing_items TEXT,
    UNIQUE(device_type_id, lot_number)
);

-- 8. Unit Overrides テーブル
CREATE TABLE IF NOT EXISTS unit_overrides (
    id SERIAL PRIMARY KEY,
    device_unit_id INTEGER NOT NULL REFERENCES device_units(id),
    item_id INTEGER NOT NULL REFERENCES items(id),
    action TEXT NOT NULL,
    qty INTEGER
);

-- 9. Loans テーブル
CREATE TABLE IF NOT EXISTS loans (
    id SERIAL PRIMARY KEY,
    device_unit_id INTEGER NOT NULL REFERENCES device_units(id),
    checkout_date TEXT NOT NULL,
    destination TEXT NOT NULL,
    purpose TEXT NOT NULL,
    checker_user_id INTEGER,
    status TEXT DEFAULT 'open',
    notes TEXT,
    assetment_checked BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    canceled INTEGER DEFAULT 0,
    canceled_at TIMESTAMP,
    canceled_by TEXT,
    cancel_reason TEXT
);

-- 10. Check Sessions テーブル
CREATE TABLE IF NOT EXISTS check_sessions (
    id SERIAL PRIMARY KEY,
    session_type TEXT NOT NULL,
    loan_id INTEGER REFERENCES loans(id),
    device_unit_id INTEGER NOT NULL REFERENCES device_units(id),
    performed_by TEXT,
    performed_at TIMESTAMP DEFAULT NOW(),
    device_photo_dir TEXT,
    canceled INTEGER DEFAULT 0,
    canceled_at TIMESTAMP,
    canceled_by TEXT,
    cancel_reason TEXT
);

-- 11. Check Lines テーブル
CREATE TABLE IF NOT EXISTS check_lines (
    id SERIAL PRIMARY KEY,
    check_session_id INTEGER NOT NULL REFERENCES check_sessions(id),
    item_id INTEGER NOT NULL REFERENCES items(id),
    required_qty INTEGER NOT NULL,
    result TEXT NOT NULL,
    ng_reason TEXT,
    found_qty INTEGER,
    comment TEXT
);

-- 12. Issues テーブル
CREATE TABLE IF NOT EXISTS issues (
    id SERIAL PRIMARY KEY,
    device_unit_id INTEGER NOT NULL REFERENCES device_units(id),
    check_session_id INTEGER REFERENCES check_sessions(id),
    status TEXT DEFAULT 'open',
    summary TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by TEXT,
    resolved_at TIMESTAMP,
    resolved_by TEXT,
    canceled INTEGER DEFAULT 0,
    canceled_at TIMESTAMP,
    canceled_by TEXT,
    cancel_reason TEXT
);

-- 13. Returns テーブル
CREATE TABLE IF NOT EXISTS returns (
    id SERIAL PRIMARY KEY,
    loan_id INTEGER NOT NULL REFERENCES loans(id),
    return_date TEXT NOT NULL,
    checker_user_id INTEGER,
    assetment_returned BOOLEAN DEFAULT false,
    notes TEXT,
    confirmation_checked BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    canceled INTEGER DEFAULT 0,
    canceled_at TIMESTAMP,
    canceled_by TEXT,
    cancel_reason TEXT
);

-- 14. Notification Groups テーブル
CREATE TABLE IF NOT EXISTS notification_groups (
    id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    UNIQUE(category_id, user_id)
);

-- 15. Notification Logs テーブル
CREATE TABLE IF NOT EXISTS notification_logs (
    id SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    related_id INTEGER,
    recipient TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 16. System Settings テーブル
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- 17. Login History テーブル（ログイン履歴）
CREATE TABLE IF NOT EXISTS login_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    email TEXT NOT NULL,
    user_name TEXT,
    login_at TIMESTAMP DEFAULT NOW(),
    ip_address TEXT,
    user_agent TEXT,
    success BOOLEAN DEFAULT true
);

-- Row Level Security (RLS) を無効化（シンプルな運用のため）
-- 本番環境ではセキュリティ要件に応じてRLSを有効化してください
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE device_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE items ENABLE ROW LEVEL SECURITY;
ALTER TABLE template_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE device_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE unit_overrides ENABLE ROW LEVEL SECURITY;
ALTER TABLE loans ENABLE ROW LEVEL SECURITY;
ALTER TABLE check_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE check_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE issues ENABLE ROW LEVEL SECURITY;
ALTER TABLE returns ENABLE ROW LEVEL SECURITY;
ALTER TABLE departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE login_history ENABLE ROW LEVEL SECURITY;

-- 全テーブルにアクセス許可ポリシーを追加
-- service_role キーを使用するため、全てのアクセスを許可
CREATE POLICY "Allow all for service role" ON users FOR ALL USING (true);
CREATE POLICY "Allow all for service role" ON categories FOR ALL USING (true);
CREATE POLICY "Allow all for service role" ON device_types FOR ALL USING (true);
CREATE POLICY "Allow all for service role" ON items FOR ALL USING (true);
CREATE POLICY "Allow all for service role" ON template_lines FOR ALL USING (true);
CREATE POLICY "Allow all for service role" ON device_units FOR ALL USING (true);
CREATE POLICY "Allow all for service role" ON unit_overrides FOR ALL USING (true);
CREATE POLICY "Allow all for service role" ON loans FOR ALL USING (true);
CREATE POLICY "Allow all for service role" ON check_sessions FOR ALL USING (true);
CREATE POLICY "Allow all for service role" ON check_lines FOR ALL USING (true);
CREATE POLICY "Allow all for service role" ON issues FOR ALL USING (true);
CREATE POLICY "Allow all for service role" ON returns FOR ALL USING (true);
CREATE POLICY "Allow all for service role" ON departments FOR ALL USING (true);
CREATE POLICY "Allow all for service role" ON notification_groups FOR ALL USING (true);
CREATE POLICY "Allow all for service role" ON notification_logs FOR ALL USING (true);
CREATE POLICY "Allow all for service role" ON system_settings FOR ALL USING (true);
CREATE POLICY "Allow all for service role" ON login_history FOR ALL USING (true);
