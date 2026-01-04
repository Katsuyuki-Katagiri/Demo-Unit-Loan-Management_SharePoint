import streamlit as st
import datetime
import os
from src.database import (
    get_device_unit_by_id, get_device_type_by_id, UPLOAD_DIR, get_active_loan, get_loan_by_id,
    get_user_by_id, get_check_session_by_loan_id
)
from src.logic import get_synthesized_checklist, process_return

def render_return_view(unit_id: int):
    # Retrieve Unit & Type Info
    unit = get_device_unit_by_id(unit_id)
    if not unit:
        st.error("Unit not found")
        if st.button("back"):
            st.session_state['return_mode'] = False
            st.rerun()
        return

    # Check for active loan
    active_loan_info = get_active_loan(unit_id)
    if not active_loan_info:
        st.error("No active loan found for this unit.")
        if st.button("back"):
            st.session_state['return_mode'] = False
            st.rerun()
        return

    type_info = get_device_type_by_id(unit['device_type_id'])
    
    st.title("機材返却登録")
    st.markdown(f"**{type_info['name']}** (Lot: {unit['lot_number']})")
    
    # Back Button
    if st.button("← キャンセルして戻る"):
        st.session_state['return_mode'] = False
        st.rerun()

    st.divider()

    # --- Display Loan Info ---
    st.subheader("貸出情報")
    with st.container(border=True):
        # Get Carrier Name
        carrier_name = "Unknown"
        if active_loan_info['checker_user_id']:
            u_obj = get_user_by_id(active_loan_info['checker_user_id'])
            if u_obj: carrier_name = u_obj['name']
        else:
            sess = get_check_session_by_loan_id(active_loan_info['id'])
            if sess: carrier_name = sess['performed_by']

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.write(f"持出日: **{active_loan_info['checkout_date']}**")
        with c2:
            st.write(f"持出者: **{carrier_name}**")
        with c3:
            st.write(f"貸出先: **{active_loan_info['destination']}**")
        with c4:
            st.write(f"目的: **{active_loan_info['purpose']}**")

    # --- input Fields ---
    st.subheader("返却情報")
    return_date = st.date_input("返却日", value=datetime.date.today())
    
    st.subheader("写真記録 (必須)")
    uploaded_files = st.file_uploader("返却時の写真をアップロードしてください (最低1枚)", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'], key="return_uploader")
    
    st.subheader("構成品チェック")
    
    # helper for session state initialization (Reuse logic if possible, but separate key)
    if 'return_checklist_data' not in st.session_state or st.session_state.get('current_return_unit_id') != unit_id:
        # Initialize
        checklist_items = get_synthesized_checklist(unit['device_type_id'], unit['id'])
        st.session_state['return_checklist_data'] = {}
        st.session_state['return_checklist_items_source'] = checklist_items
        st.session_state['current_return_unit_id'] = unit_id
        
        for item in checklist_items:
            st.session_state['return_checklist_data'][item['item_id']] = {
                'result': 'OK',
                'ng_reason': '紛失',
                'found_qty': 0,
                'comment': ''
            }
            
    # Render Checklist
    checklist_items = st.session_state['return_checklist_items_source']
    
    for item in checklist_items:
        item_id = item['item_id']
        data = st.session_state['return_checklist_data'][item_id]
        
        with st.container(border=True):
            r1, r2 = st.columns([3, 2])
            with r1:
                name_disp = item['name']
                if item['is_override']:
                    name_disp += " (個体差分)"
                st.markdown(f"**{name_disp}**")
                st.caption(f"必要数: {item['required_qty']}")
                
                if item['photo_path']:
                    full_path = os.path.join(UPLOAD_DIR, item['photo_path'])
                    if os.path.exists(full_path):
                        st.image(full_path, width=100)

            with r2:
                # Result Toggle
                res = st.radio(
                    f"Result_{item_id}_ret", 
                    ['OK', 'NG'], 
                    index=0 if data['result'] == 'OK' else 1,
                    key=f"res_{item_id}_ret",
                    horizontal=True,
                    label_visibility="collapsed"
                )
                
                st.session_state['return_checklist_data'][item_id]['result'] = res
                
                if res == 'NG':
                    st.error("NG詳細を入力してください")
                    reason = st.selectbox(
                        "理由", 
                        ['紛失', '破損', '数量不足'], 
                        key=f"reason_{item_id}_ret",
                        index=['紛失', '破損', '数量不足'].index(data['ng_reason'])
                    )
                    st.session_state['return_checklist_data'][item_id]['ng_reason'] = reason
                    
                    if reason == '数量不足':
                        fq = st.number_input("確認数量", min_value=0, value=data['found_qty'], key=f"fq_{item_id}_ret")
                        st.session_state['return_checklist_data'][item_id]['found_qty'] = fq
                        
                    comm = st.text_input("コメント", value=data['comment'], key=f"comm_{item_id}_ret")
                    st.session_state['return_checklist_data'][item_id]['comment'] = comm


    st.divider()
    
    # Error Display
    errors = []
    if not uploaded_files:
        errors.append("写真を最低1枚アップロードしてください")
        
    if errors:
        for e in errors:
            st.error(e)
        st.button("登録 (入力不備があります)", disabled=True, key="btn_ret_disabled")
    else:
        if st.button("返却を確定する", type="primary", key="btn_ret_submit"):
            # Process Submission
            
            # 1. Save Photos
            timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            session_dir_name = f"return_{unit_id}_{timestamp_str}"
            abs_session_dir = os.path.join(UPLOAD_DIR, session_dir_name)
            os.makedirs(abs_session_dir, exist_ok=True)
            
            for uf in uploaded_files:
                with open(os.path.join(abs_session_dir, uf.name), "wb") as f:
                    f.write(uf.getbuffer())
                    
            # 2. Build Check Results List
            check_results_list = []
            for item in checklist_items:
                iid = item['item_id']
                d = st.session_state['return_checklist_data'][iid]
                check_results_list.append({
                    'item_id': iid,
                    'name': item['name'],
                    'required_qty': item['required_qty'],
                    'result': d['result'],
                    'ng_reason': d['ng_reason'] if d['result'] == 'NG' else None,
                    'found_qty': d['found_qty'] if d['result'] == 'NG' and d['ng_reason'] == '数量不足' else None,
                    'comment': d['comment'] if d['result'] == 'NG' else None
                })
                
            # 3. Call Logic
            try:
                user_name = st.session_state.get('user_name', 'Unknown')
                
                result_status = process_return(
                    device_unit_id=unit_id,
                    return_date=return_date.isoformat(),
                    check_results=check_results_list,
                    photo_dir=session_dir_name, 
                    user_name=user_name
                )
                
                if result_status == 'in_stock':
                    st.success("返却登録完了！ (ステータス: 在庫あり)")
                else:
                    st.warning("登録完了！ (NG箇所があるか未解決のIssueがあるため、ステータスは「要対応」になりました)")
                
                # Clear state
                st.session_state['return_mode'] = False
                del st.session_state['return_checklist_data']
                st.rerun()
                
            except ValueError as e:
                st.error(str(e))
