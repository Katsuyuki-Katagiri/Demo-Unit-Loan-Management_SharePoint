
import streamlit as st
import json
from src.database import (
    get_all_categories, get_all_users, get_notification_members,
    add_notification_member, remove_notification_member,
    save_system_setting, get_system_setting,
    get_notification_logs, create_user, delete_user, check_email_exists
)

def render_settings_view():
    from src.ui import render_header
    render_header("設定", "settings")
    
    st.info("通知グループとSMTP設定、およびユーザーを管理します。")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📧 SMTP設定", "👤 ユーザー管理", "👥 通知グループ", "📜 通知ログ"])
    
    # --- SMTP Configuration ---
    with tab1:
        st.header("SMTP Configuration")
        st.caption("メール通知を使用する場合に設定してください。")
        
        current_config_json = get_system_setting('smtp_config')
        default_config = {
            "enabled": False, "host": "smtp.gmail.com", "port": 587, 
            "user": "", "password": "", "from_addr": ""
        }
        
        if current_config_json:
            try:
                loaded = json.loads(current_config_json)
                default_config.update(loaded)
            except:
                pass

        with st.form("smtp_form"):
            enabled = st.checkbox("メール通知を有効にする", value=default_config['enabled'])
            c1, c2 = st.columns(2)
            host = c1.text_input("SMTP Host", value=default_config['host'])
            port = c2.number_input("SMTP Port", value=int(default_config['port']))
            user = c1.text_input("SMTP User", value=default_config['user'])
            password = c2.text_input("SMTP Password", value=default_config['password'], type="password")
            from_addr = st.text_input("From Address", value=default_config['from_addr'])
            
            if st.form_submit_button("保存"):
                new_config = {
                    "enabled": enabled, "host": host, "port": port,
                    "user": user, "password": password, "from_addr": from_addr
                }
                save_system_setting('smtp_config', json.dumps(new_config))
                st.success("SMTP設定を保存しました。")

        st.divider()
        st.subheader("接続テスト")
        test_email = st.text_input("テスト送信先メールアドレス", placeholder="your_email@example.com")
        if st.button("テストメール送信"):
            if not test_email:
                st.error("テスト送信先を入力してください。")
            else:
                # Use current saved settings (or should we use form values? Form values are gone after submit)
                # We use saved settings for simplicity, forcing user to save first.
                # Actually, capturing form state is hard without saving.
                # Let's verify saved settings.
                
                saved_config_json = get_system_setting('smtp_config')
                if not saved_config_json:
                     st.error("設定が保存されていません。先に保存してください。")
                else:
                    conf = json.loads(saved_config_json)
                    if not conf.get('enabled'):
                        st.warning("設定では「メール通知を有効にする」がOFFになっていますが、テスト送信を試みます。")
                        
                    import smtplib
                    from email.mime.text import MIMEText
                    
                    try:
                        msg = MIMEText("This is a test email from Demo Unit Loan Management System.")
                        msg['Subject'] = "[Test] SMTP Connection Verification"
                        msg['From'] = conf.get('from_addr', 'noreply@example.com')
                        msg['To'] = test_email
                        
                        with smtplib.SMTP(conf.get('host', 'localhost'), int(conf.get('port', 25))) as server:
                             if int(conf.get('port', 25)) == 587:
                                 server.starttls()
                             if conf.get('user') and conf.get('password'):
                                 server.login(conf.get('user'), conf.get('password'))
                             server.send_message(msg)
                        
                        st.success(f"送信成功！ ({test_email})")
                    except Exception as e:
                        st.error(f"送信失敗:\n{e}")
                
    # --- User Management ---
    with tab2:
        st.header("ユーザー管理")
        st.caption("システムにログインできるユーザーを追加・削除します。")

        # 1. Add User
        with st.expander("➕ 新規ユーザー登録", expanded=False):
            with st.form("create_user_form"):
                new_email = st.text_input("メールアドレス (ID)")
                new_name = st.text_input("氏名")
                new_pass = st.text_input("パスワード", type="password")
                new_pass_confirm = st.text_input("パスワード (確認)", type="password")
                new_role = st.selectbox("権限", ["user", "admin", "related"], index=0, help="admin: 全権限, user: 一般, related: 関連業者")
                
                if st.form_submit_button("ユーザーを作成"):
                    if not new_email or not new_name or not new_pass:
                        st.error("全ての項目を入力してください。")
                    elif new_pass != new_pass_confirm:
                        st.error("パスワードが一致しません。")
                    elif check_email_exists(new_email):
                        st.error("このメールアドレスは既に使用されています。")
                    else:
                        if create_user(new_email, new_name, new_pass, new_role):
                            st.success(f"ユーザーを作成しました: {new_name}")
                            st.rerun()
                        else:
                            st.error("作成に失敗しました。")

        st.divider()

        # 2. List Users
        st.subheader("登録済みユーザー一覧")
        
        users = get_all_users()
        if users:
            for u in users:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 1])
                    role_badge = "👑 Admin" if u['role'] == 'admin' else "👤 User" if u['role'] == 'user' else "🏢 Related"
                    c1.markdown(f"**{u['name']}** ({u['email']})")
                    c2.caption(role_badge)
                    
                    # Prevent deleting self or last admin handled in DB, but good to act here too
                    if c3.button("削除", key=f"del_user_{u['id']}", type="secondary"):
                        success, msg = delete_user(u['id'])
                        if success:
                            st.warning(msg)
                            st.rerun()
                        else:
                            st.error(msg)
        else:
            st.info("ユーザーがいません。")

    # --- Notification Groups ---
    with tab3:
        st.header("通知グループ")
        st.caption("カテゴリごとの異常発生時の通知先を設定します。")
        
        categories = get_all_categories()
        cat_map = {c['name']: c['id'] for c in categories}
        if cat_map:
            selected_cat_name = st.selectbox("カテゴリ選択", list(cat_map.keys()))
            
            if selected_cat_name:
                cat_id = cat_map[selected_cat_name]
                members = get_notification_members(cat_id)
                
                # Show current members
                st.subheader(f"Current Members for {selected_cat_name}")
                if members:
                    for m in members:
                        c1, c2 = st.columns([4, 1])
                        c1.write(f"👤 {m['name']} ({m['email']})")
                        if c2.button("削除", key=f"del_{m['id']}"):
                            remove_notification_member(cat_id, m['id'])
                            st.rerun()
                else:
                    st.write("メンバーがいません。")
                
                st.divider()
                
                # Add Member
                st.subheader("メンバー追加")
                all_users = get_all_users()
                # Filter out existing members
                member_ids = [m['id'] for m in members]
                available_users = [u for u in all_users if u['id'] not in member_ids]
                
                if available_users:
                    u_map = {f"{u['name']} ({u['email']})": u['id'] for u in available_users}
                    selected_user_label = st.selectbox("ユーザー選択", list(u_map.keys()))
                    if st.button("追加"):
                        add_notification_member(cat_id, u_map[selected_user_label])
                        st.success("メンバーを追加しました。")
                        st.rerun()
                else:
                    st.info("追加可能なユーザーがいません（全員追加済みか、ユーザーマスタが空です）。")
        else:
            st.warning("カテゴリが登録されていません。マスタ管理で登録してください。")

    # --- Logs ---
    with tab4:
        st.header("通知ログ")
        if st.button("更新"):
            st.rerun()
            
        logs = get_notification_logs(limit=50)
        if logs:
            for l in logs:
                status_color = "green" if l['status'] == 'sent' else "red" if l['status'] == 'failed' else "grey"
                st.markdown(f"**[{l['created_at']}]** :{status_color}[{l['status']}] {l['event_type']} -> {l['recipient']}")
                if l['error_message']:
                    st.error(f"Error: {l['error_message']}")
                st.divider()
        else:
            st.write("ログはありません。")
