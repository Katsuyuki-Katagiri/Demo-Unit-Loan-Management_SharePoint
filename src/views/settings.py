
import streamlit as st
import json
from src.database import (
    get_all_categories, get_all_users, get_notification_members,
    add_notification_member, remove_notification_member,
    save_system_setting, get_system_setting,
    get_notification_logs
)

def render_settings_view():
    st.title("⚙️ 設定 (Settings)")
    
    st.info("通知グループとSMTP設定を管理します。")
    
    tab1, tab2, tab3 = st.tabs(["📧 SMTP設定", "👥 通知グループ", "📜 通知ログ"])
    
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
                
    # --- Notification Groups ---
    with tab2:
        st.header("通知グループ (Notification Groups)")
        st.caption("カテゴリごとの異常発生時の通知先を設定します。")
        
        categories = get_all_categories()
        cat_map = {c['name']: c['id'] for c in categories}
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

    # --- Logs ---
    with tab3:
        st.header("通知ログ (Logs)")
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
