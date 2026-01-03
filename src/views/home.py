import streamlit as st
import os
from src.database import (
    get_all_categories, get_device_types, get_device_units, 
    get_device_unit_by_id, get_device_type_by_id, UPLOAD_DIR
)
from src.logic import get_synthesized_checklist

def render_home_view():
    # Navigation State Management
    # Level 0: Categories (Default)
    # Level 1: Device Types (in session_state['selected_category_id'])
    # Level 2: Device Units (in session_state['selected_type_id'])
    # Level 3: Unit Detail (in session_state['selected_unit_id'])
    
    # Back button helpers
    if 'selected_unit_id' in st.session_state and st.session_state['selected_unit_id']:
        if st.button("← ロット一覧に戻る"):
            st.session_state['selected_unit_id'] = None
            st.rerun()
            
    elif 'selected_type_id' in st.session_state and st.session_state['selected_type_id']:
        if st.button("← 機種一覧に戻る"):
            st.session_state['selected_type_id'] = None
            st.rerun()
            
    elif 'selected_category_id' in st.session_state and st.session_state['selected_category_id']:
        if st.button("← 大分類に戻る"):
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
            st.info(f"保管場所: {unit['location']} | Status: {unit['status']}")
            
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
            with st.expander("貸出履歴 / 取消 (History)"):
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
            from src.database import get_active_loan
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
            for item in checklist:
                with st.container(border=True):
                   c1, c2 = st.columns([1, 4])
                   with c1:
                       if item['photo_path']:
                           full_path = os.path.join(UPLOAD_DIR, item['photo_path'])
                           if os.path.exists(full_path):
                               st.image(full_path, use_container_width=True)
                           else:
                               st.caption("No Image")
                       else:
                           st.caption("No Image")
                    
                   with c2:
                       name_display = item['name']
                       if item['is_override']:
                           name_display += " (個体差分)"
                       st.markdown(f"#### {name_display}")
                       st.write(f"必要数: **{item['required_qty']}**")

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
                if st.button(t['name'], key=f"type_{t['id']}", use_container_width=True):
                    st.session_state['selected_type_id'] = t['id']
                    st.rerun()

    # --- Level 0: Categories (Home) ---
    else:
        st.markdown("### クラス選択")
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
