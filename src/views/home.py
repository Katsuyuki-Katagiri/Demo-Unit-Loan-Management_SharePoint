import streamlit as st
import os
from src.database import (
    get_all_categories, get_device_types, get_device_units, 
    get_device_unit_by_id, get_device_type_by_id, UPLOAD_DIR,
    get_active_loan, get_user_by_id, get_check_session_by_loan_id,
    get_category_by_id, get_session_photos,
    get_device_units_for_types, get_users_batch, get_active_loans_batch
)

from src.logic import get_synthesized_checklist, get_image_base64

def render_home_view():
    # Navigation State Management
    # Level 0: Categories (Default)
    # Level 1: Device Types (in session_state['selected_category_id'])
    # Level 2: Device Units (in session_state['selected_type_id'])
    # Level 3: Unit Detail (in session_state['selected_unit_id'])
    
    # Back button helpers
    # Back button helpers
    if 'selected_unit_id' in st.session_state and st.session_state['selected_unit_id']:
        c_b1, c_b2 = st.columns([2, 8])
        with c_b1:
            if st.button("← 機種一覧に戻る"): 
                st.session_state['selected_unit_id'] = None
                st.session_state['selected_type_id'] = None # Also clear type to go back to list
                st.session_state['loan_mode'] = False
                st.session_state['return_mode'] = False
                if 'checklist_data' in st.session_state: del st.session_state['checklist_data']
                if 'return_checklist_data' in st.session_state: del st.session_state['return_checklist_data']
                st.rerun()
        with c_b2:
            if st.button("🏠 ホームに戻る", key="home_btn_3"):
                st.session_state['selected_unit_id'] = None
                st.session_state['selected_type_id'] = None
                st.session_state['selected_category_id'] = None
                st.session_state['loan_mode'] = False
                st.session_state['return_mode'] = False
                if 'checklist_data' in st.session_state: del st.session_state['checklist_data']
                if 'return_checklist_data' in st.session_state: del st.session_state['return_checklist_data']
                st.rerun()
            
    elif 'selected_type_id' in st.session_state and st.session_state['selected_type_id']:
        c_b1, c_b2 = st.columns([2, 8])
        with c_b1:
            if st.button("← 機種一覧に戻る"):
                st.session_state['selected_type_id'] = None
                st.rerun()
        with c_b2:
            if st.button("🏠 ホームに戻る", key="home_btn_2"):
                st.session_state['selected_type_id'] = None
                st.session_state['selected_category_id'] = None
                st.rerun()
            
    elif 'selected_category_id' in st.session_state and st.session_state['selected_category_id']:
        if st.button("← ホームに戻る"):
            st.session_state['selected_category_id'] = None
            st.rerun()

    # --- Level 3: Unit Detail (Checklist) ---
    if st.session_state.get('selected_unit_id'):
        unit_id = st.session_state['selected_unit_id']

        # Reset history limit if unit changed
        if 'last_viewed_unit_id' not in st.session_state or st.session_state['last_viewed_unit_id'] != unit_id:
            st.session_state['history_limit'] = 5
            st.session_state['last_viewed_unit_id'] = unit_id
        
        # Check if in Loan Mode
        if st.session_state.get('loan_mode'):
            from src.views.loan import render_loan_view
            render_loan_view(unit_id)
            return

        if st.session_state.get('return_mode'):
            from src.views.return_view import render_return_view
            render_return_view(unit_id)
            return

        unit = get_device_unit_by_id(unit_id)
        type_info = get_device_type_by_id(unit['device_type_id'])
        
        c1, c2 = st.columns([3, 1])
        with c1:
            st.title(f"{type_info['name']} (Lot: {unit['lot_number']})")
            # Determine display info
            location_disp = f"保管場所: {unit['location']}"
            loaner_disp = ""
            
            if unit['status'] == 'loaned':
                active_loan = get_active_loan(unit_id)
                if active_loan:
                    location_disp = f"保管場所: {active_loan['destination']} (貸出先)"
                    # Get Loaner Name
                    l_Name = "Unknown"
                    if active_loan['checker_user_id']:
                        u_obj = get_user_by_id(active_loan['checker_user_id'])
                        if u_obj: l_Name = u_obj['name']
                    else:
                        # Fallback
                        sess = get_check_session_by_loan_id(active_loan['id'])
                        if sess: l_Name = sess['performed_by']
                    
                    loaner_disp = f" | 持出者: {l_Name}"

            # Status Mapping
            status_map = {
                'in_stock': '在庫あり',
                'loaned': '貸出中',
                'needs_attention': '要対応'
            }
            status_jp = status_map.get(unit['status'], unit['status'])
            st.info(f"{location_disp}{loaner_disp} | ステータス: {status_jp}")
            
            # --- Issues Section ---
            from src.database import get_open_issues
            from src.logic import perform_issue_resolution, perform_cancellation
            
            issues = get_open_issues(unit_id)
            if issues:
                st.error(f"⚠️ 要対応 (Issues): {len(issues)}件")
                for i in issues:
                    with st.container(border=True):
                        st.write(f"**{i['summary']}**")
                        st.caption(f"Created: {i['created_at']} by {i['created_by']}")
                        # Resolve Button (Mock Admin check: anyone can for demo)
                        if st.button("解決済みにする (Resolve)", key=f"resolve_{i['id']}"):
                            perform_issue_resolution(unit_id, i['id'], st.session_state.get('user_name', 'Admin'))
                            st.success("Issue Resolved!")
                            st.rerun()
            
            # --- History Section ---
            with st.expander("貸出返却履歴"):
                from src.database import get_loan_history
                
                # Pagination State
                if 'history_limit' not in st.session_state:
                    st.session_state['history_limit'] = 5
                
                # Fetch limit + 1 to check if there are more records
                fetch_limit = st.session_state['history_limit'] + 1
                history_batch = get_loan_history(unit_id, limit=fetch_limit, include_canceled=False)
                
                has_more = len(history_batch) > st.session_state['history_limit']
                displayed_history = history_batch[:st.session_state['history_limit']]
                
                if not displayed_history:
                    st.write("履歴なし")
                else:
                    for l_row in displayed_history:
                        l = dict(l_row)
                        status_icon = "🟢" if l['status'] == 'open' else "⚫"
                        
                        # Determine Carrier Name
                        carrier_name = "Unknown"
                        if l['checker_user_id']:
                            u_obj = get_user_by_id(l['checker_user_id'])
                            if u_obj: carrier_name = u_obj['name']
                        else:
                            # Fallback to check session
                            sess = get_check_session_by_loan_id(l['id'])
                            if sess: carrier_name = sess['performed_by']

                        st.markdown(f"**{l['checkout_date']}** - {l['destination']} ({l['purpose']})")
                        if l['status'] == 'open':
                            assetment_label = "Assetment: 済" if 'assetment_checked' in l.keys() and l['assetment_checked'] else "Assetment: 未"
                        else: # Closed (Returned)
                            labels = []
                            if l.get('assetment_checked'): labels.append("貸出Assetment: 済")
                            if l.get('assetment_returned'): labels.append("返却Assetment: 済")
                            if l.get('confirmation_checked'): labels.append("確認書: 済")
                            assetment_label = " | ".join(labels) if labels else "Assetment: 未"
                        
                        status_disp = "貸出中" if l['status'] == 'open' else "返却済"
                        st.caption(f"ステータス: {status_disp} | 持出者: {carrier_name} | {status_icon} | {assetment_label}")
                        
                        if 'notes' in l.keys() and l['notes']:
                            st.info(f"備考: {l['notes']}")
                        
                        # Cancel Button (Only if not already canceled)
                        if not l['canceled']:
                            if st.button(f"取消 (Cancel Loan #{l['id']})", key=f"cancel_loan_{l['id']}"):
                                perform_cancellation('loan', l['id'], st.session_state.get('user_name', 'Admin'), "Admin Cancel", unit_id)
                                st.warning("Loan Canceled")
                                st.rerun()
                        
                        # --- Check Details ---
                        from src.database import get_all_check_sessions_for_loan, get_check_session_lines
                        sessions = get_all_check_sessions_for_loan(l['id'])
                        if sessions:
                            for sess in sessions:
                                s_type_label = "貸出時チェック" if sess['session_type'] == 'checkout' else "返却時チェック"
                                with st.expander(f"📋 {s_type_label} 詳細 ({sess['performed_at']})"):
                                    # Special display for Assetment check in Checkout
                                    if sess['session_type'] == 'checkout':
                                        # sqlite3.Row does not support .get(), so convert to dict or check keys
                                        is_checked = l['assetment_checked'] if 'assetment_checked' in l.keys() else 0
                                        if is_checked:
                                            st.success("✅ AssetmentNeo 登録確認済み")
                                        else:
                                            st.warning("⚠️ AssetmentNeo 登録未確認")
                                        st.divider()
                                    elif sess['session_type'] == 'return':
                                        # Assetment check for Return
                                        is_returned = l['assetment_returned'] if 'assetment_returned' in l.keys() else 0
                                        if is_returned:
                                            st.success("✅ AssetmentNeo 返却処理確認済み")
                                        else:
                                            st.warning("⚠️ AssetmentNeo 返却処理未確認")
                                        st.divider()
                                    # Show Photos
                                    photo_displayed = False
                                    if sess['device_photo_dir']:
                                        # 1. Try Supabase Storage
                                        storage_photos = get_session_photos(sess['device_photo_dir'])
                                        if storage_photos:
                                            st.caption("記録写真 (Storage)")
                                            for i in range(0, len(storage_photos), 4):
                                                cols = st.columns(4)
                                                for j in range(4):
                                                    if i + j < len(storage_photos):
                                                        cols[j].image(storage_photos[i+j], use_container_width=True)
                                            st.divider()
                                            photo_displayed = True
                                        
                                        # 2. Fallback to Local Storage (if no storage photos or for historical data)
                                        if not photo_displayed:
                                            photo_dir_path = os.path.join(UPLOAD_DIR, sess['device_photo_dir'])
                                            if os.path.exists(photo_dir_path):
                                                photos = [f for f in os.listdir(photo_dir_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
                                                if photos:
                                                    st.caption("記録写真 (Local)")
                                                    for i in range(0, len(photos), 4):
                                                        cols = st.columns(4)
                                                        for j in range(4):
                                                            if i + j < len(photos):
                                                                cols[j].image(os.path.join(photo_dir_path, photos[i+j]), use_container_width=True)
                                                    st.divider()

                                    lines = get_check_session_lines(sess['id'])
                                    if not lines:
                                        st.caption("詳細データなし")
                                    else:
                                        # Table-like display
                                        for line in lines:
                                            # Icon based on result
                                            r_icon = "✅" if line['result'] == 'OK' else "⚠️"
                                            if line['result'] == 'NG': r_icon = "❌"
                                            
                                            st.write(f"{r_icon} **{line['item_name']}**")
                                            if line['result'] != 'OK':
                                                st.caption(f"理由: {line['ng_reason']} | 数量: {line['found_qty']}")
                                            if line['comment']:
                                                st.caption(f"コメント: {line['comment']}")
                        
                        # Stronger Divider
                        st.markdown("<hr style='border: none; border-top: 3px solid #666; margin: 30px 0;'>", unsafe_allow_html=True)
                    
                    if has_more:
                        if st.button("もっと見る (更に5件表示)", key="show_more_history"):
                            st.session_state['history_limit'] += 5
                            st.rerun()

        with c2:
            st.write("") # spacer
            st.write("")
            # Check conditions for Loan/Return
            
            # Custom CSS for tall buttons (Primary Only) - Scoped to this view effectively by context
            active_loan = get_active_loan(unit_id)
            
            # Re-check issues (might be resolved just now)
            can_loan = (unit['status'] == 'in_stock') and (not issues)
            can_return = (unit['status'] == 'loaned') or (active_loan)
            
            # Custom CSS for tall buttons (Primary Only) - Scoped to this view effectively by context
            # Base style for size
            base_style = """
                <style>
                div.stButton > button[kind="primary"] {
                    height: 100px !important;
                    font-size: 1.5em !important;
                    font-weight: bold !important;
                    color: white !important;
                }
                </style>
            """
            st.markdown(base_style, unsafe_allow_html=True)
            
            # active_loan, can_loan, can_returnは上で既に計算済みのため再計算不要
            
            if can_loan:
                # Inject Blue Color
                st.markdown("""
                    <style>
                    div.stButton > button[kind="primary"] {
                        background-color: #2196F3 !important;
                        border-color: #2196F3 !important;
                    }
                    div.stButton > button[kind="primary"]:hover {
                        background-color: #1976D2 !important;
                        border-color: #1976D2 !important;
                    }
                    </style>
                """, unsafe_allow_html=True)
                
                if st.button("📦 貸出登録 (Checkout)", type="primary", use_container_width=True):
                    st.session_state['loan_mode'] = True
                    st.rerun()
                st.markdown("<div style='text-align: center; color: gray; font-size: 0.8em; margin-top: -10px; margin-bottom: 20px;'>貸出登録は、上記ボタンから行ってください</div>", unsafe_allow_html=True)
            
            elif can_return:
                 # Inject Red Color
                 st.markdown("""
                    <style>
                    div.stButton > button[kind="primary"] {
                        background-color: #F44336 !important;
                        border-color: #F44336 !important;
                    }
                    div.stButton > button[kind="primary"]:hover {
                        background-color: #D32F2F !important;
                        border-color: #D32F2F !important;
                    }
                    </style>
                 """, unsafe_allow_html=True)
                 
                 if st.button("↩️ 返却登録 (Return)", type="primary", use_container_width=True):
                    st.session_state['return_mode'] = True
                    st.rerun()
                 st.markdown("<div style='text-align: center; color: gray; font-size: 0.8em; margin-top: -10px; margin-bottom: 20px;'>返却登録は、上記ボタンから行ってください</div>", unsafe_allow_html=True)
            elif unit['status'] != 'in_stock' and not active_loan:
                 st.button(f"状態: {unit['status']}", disabled=True)
            elif issues:
                st.button("貸出不可 (要対応あり)", disabled=True)

        st.subheader("構成品チェックリスト (参照)")
        checklist = get_synthesized_checklist(unit['device_type_id'], unit['id'])
        
        if not checklist:
            st.warning("構成品が定義されていません")
        else:
            html_content = ""
            for item in checklist:
                img_tag = ""
                if item['photo_path']:
                    # URLの場合は直接使用、ローカルパスの場合は既存処理
                    if item['photo_path'].startswith('http'):
                        img_tag = f'<img src="{item["photo_path"]}" style="max-width: 100%; max-height: 100%; object-fit: contain;">'
                    else:
                        full_path = os.path.join(UPLOAD_DIR, item['photo_path'])
                        if os.path.exists(full_path):
                            b64_str = get_image_base64(full_path)
                            if b64_str:
                                img_tag = f'<img src="data:image/png;base64,{b64_str}" style="max-width: 100%; max-height: 100%; object-fit: contain;">'
                            else:
                                img_tag = '<div style="color: #888; font-size: 0.8em;">Image Error</div>'
                        else:
                            img_tag = '<div style="color: #888; font-size: 0.8em;">No Image</div>'
                else:
                    img_tag = '<div style="color: #888; font-size: 0.8em;">No Image</div>'

                name_display = item['name']
                if item['is_override']:
                    name_display += " <span style='color: orange; font-size: 0.8em;'>(個体差分)</span>"
                
                # Card HTML
                html_content += f"""
                <div style="
                    display: flex; 
                    flex-direction: row; 
                    align-items: center; 
                    border: 1px solid rgba(128, 128, 128, 0.2); 
                    border-radius: 8px; 
                    padding: 10px; 
                    margin-bottom: 10px; 
                    height: 120px; 
                    background-color: transparent;
                ">
                    <div style="
                        width: 120px; 
                        height: 100px; 
                        flex-shrink: 0; 
                        display: flex; 
                        align-items: center; 
                        justify-content: center;
                        margin-right: 15px;
                        background-color: rgba(128, 128, 128, 0.05);
                        border-radius: 4px;
                    ">
                        {img_tag}
                    </div>
                    <div style="flex-grow: 1; overflow: hidden;">
                        <div style="font-weight: bold; font-size: 1.1em; margin-bottom: 5px;">{name_display}</div>
                        <div style="font-size: 0.9em;">必要数: <strong>{item['required_qty']}</strong></div>
                    </div>
                </div>
                """
            
            st.markdown(html_content, unsafe_allow_html=True)

    # --- Level 2: Device Units List ---
    elif st.session_state.get('selected_type_id'):
        type_id = st.session_state['selected_type_id']
        type_info = get_device_type_by_id(type_id)
        st.header(f"{type_info['name']} - ロット一覧")
        
        units = get_device_units(type_id)
        
        if not units:
            st.info("登録されている機器(ロット)はありません")
        else:
            for u in units:
                # Card style
                with st.container(border=True):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**Lot: {u['lot_number']}**")
                        st.caption(f"保管場所: {u['location']}")
                    with col2:
                        if st.button("選択", key=f"sel_unit_{u['id']}"):
                            st.session_state['selected_unit_id'] = u['id']
                            st.rerun()

    # --- Level 1: Device Types List ---
    elif st.session_state.get('selected_category_id'):
        cat_id = st.session_state['selected_category_id']
        category = get_category_by_id(cat_id)
        
        if category:
            st.title(category['name'])
            if 'description' in category.keys() and category['description']:
                st.caption(category['description'])
        
        # --- Dashboard Summary (Category Specific) ---
        from src.database import get_unit_status_counts
        status_counts = get_unit_status_counts(cat_id)
        
        total = sum(status_counts.values())
        in_stock = status_counts.get('in_stock', 0)
        loaned = status_counts.get('loaned', 0)
        needs_attention = status_counts.get('needs_attention', 0)
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("総台数", total)
        m2.metric("在庫あり", in_stock)
        m3.metric("貸出中", loaned)
        m4.metric("⚠️ 要対応", needs_attention, delta_color="inverse")
        
        if needs_attention > 0:
            st.toast(f"このカテゴリーに要対応の機材が {needs_attention} 台あります！", icon="⚠️")
            
        st.divider()
        # Need category name? logic to fetch...
        # For now just show types
        st.header("機種一覧")
        
        types = get_device_types(cat_id)
        if not types:
            st.info("この分類に登録されている機種はありません")
        else:
            # バッチクエリで事前にデータを取得（パフォーマンス最適化）
            type_ids = [t['id'] for t in types]
            units_by_type = get_device_units_for_types(type_ids)
            
            # 貸出中の個体IDを収集してアクティブ貸出を一括取得
            all_unit_ids = []
            for t_id, units in units_by_type.items():
                all_unit_ids.extend([u['id'] for u in units])
            active_loans = get_active_loans_batch(all_unit_ids) if all_unit_ids else {}
            
            # 貸出のchecker_user_idを収集してユーザー情報を一括取得
            user_ids = [loan['checker_user_id'] for loan in active_loans.values() if loan.get('checker_user_id')]
            users_map = get_users_batch(user_ids) if user_ids else {}
            
            for t in types:
                # Determine Label with Status
                units = units_by_type.get(t['id'], [])
                
                with st.container(border=True):
                    if units:
                        unit = units[0]
                        status = unit['status']
                        
                        # Line 1: Status badge
                        if status == 'in_stock':
                            st.markdown("**✅ 在庫あり**")
                        elif status == 'loaned':
                            st.markdown("**🔴 貸出中**")
                        elif status == 'needs_attention':
                            st.markdown("**⚠️ 要対応**")
                        
                        # Line 2: Device + Lot
                        st.markdown(f"**{t['name']}** (Lot: {unit['lot_number']})")
                        
                        # Line 3: Loan info (if loaned)
                        if status == 'loaned':
                            loan_info = active_loans.get(unit['id'])
                            if loan_info:
                                carrier_name = "Unknown"
                                if loan_info['checker_user_id']:
                                    u_obj = users_map.get(loan_info['checker_user_id'])
                                    if u_obj: carrier_name = u_obj['name']
                                else:
                                    sess = get_check_session_by_loan_id(loan_info['id'])
                                    if sess: carrier_name = sess['performed_by']
                                
                                st.caption(f"📍 {loan_info['destination']} / 持出者: {carrier_name} / {loan_info['checkout_date']}")
                                if 'notes' in loan_info.keys() and loan_info['notes']:
                                    st.caption(f"備考: {loan_info['notes']}")
                        
                        # Line 4: Maintenance dates
                        if unit['last_check_date'] or unit['next_check_date']:
                            parts = []
                            if unit['last_check_date']:
                                parts.append(f"点検: {unit['last_check_date']}")
                            if unit['next_check_date']:
                                parts.append(f"次回: {unit['next_check_date']}")
                            st.caption(" | ".join(parts))
                        
                        # Select button
                        if st.button("選択 →", key=f"type_{t['id']}", use_container_width=True):
                            st.session_state['selected_type_id'] = t['id']
                            st.session_state['selected_unit_id'] = unit['id']
                            st.rerun()
                    else:
                        st.markdown(f"**{t['name']}**")
                        if st.button("選択 →", key=f"type_{t['id']}", use_container_width=True):
                            st.session_state['selected_type_id'] = t['id']
                            st.rerun()

    # --- Level 0: Categories (Home) ---
    else:
        from src.ui import render_header
        render_header("デモ機管理アプリ", "home")
        
        # Dashboard summary moved to category view (Level 1)
        st.write("")
        
        st.markdown("### 装置選択")
        categories = get_all_categories()
        
        # Filter visible only
        visible_cats = [c for c in categories if (c['is_visible'] if 'is_visible' in c.keys() else 1) == 1]
        
        # Grid layout
        cols = st.columns(3)
        
        # CSS for Button-as-Card
        st.markdown("""
        <style>
        /* Target ONLY buttons in Main area (exclude sidebar) and exclude Primary buttons */
        section[data-testid="stMain"] div.stButton > button:not([kind="primary"]) {
            width: 100%;
            height: auto;
            min-height: 80px;
            white-space: pre-wrap !important;
            text-align: center;
            border: 1px solid rgba(49, 51, 63, 0.2);
            background-color: white;
            color: #666; /* Base color (Description) */
            padding: 8px 4px;
            line-height: 1.25;
            transition: all 0.2s;
        }
        section[data-testid="stMain"] div.stButton > button:not([kind="primary"]):hover {
            border-color: #ff4b4b;
            background-color: white;
            transform: translateY(-2px);
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        section[data-testid="stMain"] div.stButton > button:not([kind="primary"]):focus {
            box-shadow: none;
            outline: none;
        }
        
        /* Typography: Title vs Description */
        section[data-testid="stMain"] div.stButton > button:not([kind="primary"]) p {
            font-size: 0.8rem !important; /* Description Size */
            margin: 0px !important;
        }
        section[data-testid="stMain"] div.stButton > button:not([kind="primary"]) p::first-line {
            font-size: 1.15rem !important; /* Title Size */
            font-weight: bold;
            color: #31333F;
            line-height: 1.6;
        }

        /* Dark mode adjustments */
        @media (prefers-color-scheme: dark) {
            section[data-testid="stMain"] div.stButton > button:not([kind="primary"]) {
                background-color: #262730;
                color: #AAAAAA;
                border: 1px solid rgba(250, 250, 250, 0.2);
            }
            section[data-testid="stMain"] div.stButton > button:not([kind="primary"]):hover {
                border-color: #ff4b4b;
                color: #ff4b4b;
                background-color: #262730;
            }
            section[data-testid="stMain"] div.stButton > button:not([kind="primary"]) p::first-line {
                color: #FAFAFA;
            }
        }
        </style>
        """, unsafe_allow_html=True)

        for i, cat in enumerate(visible_cats):
            col = cols[i % 3]
            with col:
                desc_text = cat['description'] if 'description' in cat.keys() and cat['description'] else " "
                
                # Label: Name (Line 1) + Description (Line 2)
                # No markdown stars, relying on CSS ::first-line
                label = f"{cat['name']}\n{desc_text}"
                
                if st.button(label, key=f"cat_btn_{cat['id']}", use_container_width=True):
                    st.session_state['selected_category_id'] = cat['id']
                    st.rerun()
