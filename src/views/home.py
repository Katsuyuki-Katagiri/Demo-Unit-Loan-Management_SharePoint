import streamlit as st
import os
from src.database import (
    get_all_categories, get_device_types, get_device_units, 
    get_device_unit_by_id, get_device_type_by_id, UPLOAD_DIR,
    get_active_loan, get_user_by_id, get_check_session_by_loan_id
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
                st.rerun()
        with c_b2:
            if st.button("🏠 ホームに戻る", key="home_btn_3"):
                st.session_state['selected_unit_id'] = None
                st.session_state['selected_type_id'] = None
                st.session_state['selected_category_id'] = None
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

            st.info(f"{location_disp}{loaner_disp} | Status: {unit['status']}")
            
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
            with st.expander("貸出履歴 / 取消"):
                from src.database import get_loan_history
                history = get_loan_history(unit_id)
                if not history:
                    st.write("履歴なし")
                else:
                    for l in history:
                        status_icon = "🟢" if l['status'] == 'open' else "⚫"
                        if l['canceled']:
                            status_icon = "❌ (Canceled)"
                            
                        st.markdown(f"**{l['checkout_date']}** - {l['destination']} ({l['purpose']})")
                        st.caption(f"Status: {l['status']} | {status_icon}")
                        
                        # Cancel Button (Only if not already canceled)
                        if not l['canceled']:
                            # If Open, allow cancellation
                            # If Closed (returned), usually allow cancelling the RETURN, not the LOAN directly?
                            # Requirement: "All cancellation OK"
                            # If status is closed, it means it was returned. Cancelling Loan would orphan the return?
                            # Logic perform_cancellation('loan') cascades to Returns too. So it's safe.
                            if st.button(f"取消 (Cancel Loan #{l['id']})", key=f"cancel_loan_{l['id']}"):
                                perform_cancellation('loan', l['id'], st.session_state.get('user_name', 'Admin'), "Admin Cancel", unit_id)
                                st.warning("Loan Canceled")
                                st.rerun()
                        st.divider()

        with c2:
            st.write("") # spacer
            st.write("")
            # Check conditions for Loan/Return

            # issues fetched above
            active_loan = get_active_loan(unit_id)
            
            # Re-check issues (might be resolved just now)
            # But 'issues' variable is from before resolution. Rerun handles display update.
            # Button logic:
            can_loan = (unit['status'] == 'in_stock') and (not issues)
            can_return = (unit['status'] == 'loaned') or (active_loan)
            
            if can_loan:
                if st.button("📦 貸出登録 (Checkout)", type="primary"):
                    st.session_state['loan_mode'] = True
                    st.rerun()
            elif can_return:
                 if st.button("↩️ 返却登録 (Return)", type="primary"):
                    st.session_state['return_mode'] = True
                    st.rerun()
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
        # Need category name? logic to fetch...
        # For now just show types
        st.header("機種一覧")
        
        types = get_device_types(cat_id)
        if not types:
            st.info("この分類に登録されている機種はありません")
        else:
            for t in types:
                # Determine Label with Status
                units = get_device_units(t['id'])
                label = t['name']
                if units:
                    status = units[0]['status']
                    if status == 'in_stock':
                        label += " 【✅ 在庫あり】"
                    elif status == 'loaned':
                        label += " 【🔴 貸出中】"
                        # Get active loan info
                        loan_info = get_active_loan(units[0]['id'])
                        if loan_info:
                            # Get Carrier Name
                            carrier_name = "Unknown"
                            if loan_info['checker_user_id']:
                                u_obj = get_user_by_id(loan_info['checker_user_id'])
                                if u_obj: carrier_name = u_obj['name']
                            else:
                                sess = get_check_session_by_loan_id(loan_info['id'])
                                if sess: carrier_name = sess['performed_by']

                            label += f" @ {loan_info['destination']} (持出者: {carrier_name} / {loan_info['checkout_date']})"
                    elif status == 'needs_attention':
                        label += " 【⚠️ 要対応】"
                
                if st.button(label, key=f"type_{t['id']}", use_container_width=True):
                    st.session_state['selected_type_id'] = t['id']
                    # Auto-select unit if exists (Skip Level 2)
                    if units:
                        st.session_state['selected_unit_id'] = units[0]['id']
                    st.rerun()

    # --- Level 0: Categories (Home) ---
    else:
        st.title("🏠 機材貸出ホーム")
        
        # --- Dashboard Summary ---
        from src.database import get_unit_status_counts
        status_counts = get_unit_status_counts()
        
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
            st.toast(f"要対応の機材が {needs_attention} 台あります！", icon="⚠️")
            
        st.divider()
        
        st.markdown("### 装置選択")
        categories = get_all_categories()
        
        # Grid layout
        cols = st.columns(3)
        for i, cat in enumerate(categories):
            col = cols[i % 3]
            with col:
                # Big Button Style
                if st.button(cat['name'], key=f"cat_{cat['id']}", use_container_width=True):
                    st.session_state['selected_category_id'] = cat['id']
                    st.rerun()
