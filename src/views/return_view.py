import streamlit as st
import datetime
import os
from src.database import (
    get_device_unit_by_id, get_device_type_by_id, UPLOAD_DIR, get_active_loan, get_loan_by_id,
    get_user_by_id, get_check_session_by_loan_id
)
from src.logic import get_synthesized_checklist, process_return, compress_image

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
    
    from src.ui import render_header
    render_header("機材返却登録", "assignment_return")
    st.markdown(f"**{type_info['name']}** (Lot: {unit['lot_number']})")
    
    # Back Button
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
    st.info("ファイル選択、またはカメラで撮影してください")

    # Custom CSS for Uploader Localization
    st.markdown("""
    <style>
        /* Localization of Dropzone text */
        [data-testid="stFileUploaderDropzoneInstructions"] > div > span,
        [data-testid="stFileUploaderDropzoneInstructions"] > div > small {
            display: none;
        }
        [data-testid="stFileUploaderDropzoneInstructions"] > div::after {
            content: "ここにファイルをドラッグ＆ドロップ";
            display: block;
            margin-bottom: 4px;
            font-size: 14px;
        }
        [data-testid="stFileUploaderDropzoneInstructions"] > div::before {
            content: "制限: 5MB/ファイル • PNG, JPG, JPEG";
            font-size: 12px;
            color: rgba(49, 51, 63, 0.6);
            display: block;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # File Uploader (standard with Japanese localization via CSS)
    uploaded_files = st.file_uploader("写真アップロード", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'], key="return_uploader")
    st.caption("📷 スマホの場合: 「Browse files」→「写真を撮る」または「カメラ」で背面カメラから撮影できます")
    
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


    
    
     # General Check Item
    st.write("")
    is_clean_checked = st.checkbox("汚れはありませんか（血液等の汚れはきちんと清掃して下さい）", key="check_clean_ret")
    
    st.write("")
    assetment_returned = st.checkbox("AssetmentNeoの返却処理を忘れずに行って下さい", key="check_assetment_ret")
    if not assetment_returned:
        st.info("💡 返却登録が済んでいない場合は [https://saas.assetment.net/AS3230-PA0200320/](https://saas.assetment.net/AS3230-PA0200320/) から返却登録を行ってから返却を確定してください")

    st.write("")
    confirmation_checked = st.checkbox("医療機器の貸出しに関する確認書をアップロードお願いします", key="check_confirmation_ret")
    if not confirmation_checked:
        st.info("💡 確認書をアップロードしていない場合は [こちら](https://forms.office.com/pages/responsepage.aspx?id=wfeBD9KOc0CWX5TRWC9tQ5z80pIW4x5CmSR6SYfwmBJUQlBFQ0dNRzRXUU5ZQ1BBMVZKVjJMOTgxVyQlQCN0PWcu&route=shorturl) からアップロードをお願いします")

    st.divider()
    st.markdown("### 備考（任意）")
    remarks = st.text_area("自由に記載できます", placeholder="例：付属品の欠品あり、異音ありなど", key="return_remarks")

    st.divider()
    
    # Error Display
    errors = []
    if not is_clean_checked:
        errors.append("「汚れはありませんか」のチェックを確認してください")
    if not assetment_returned:
        errors.append("AssetmentNeoの返却処理確認を行ってください")
    if not confirmation_checked:
        errors.append("医療機器の貸出しに関する確認書のアップロード確認を行ってください")

    if not uploaded_files:
        errors.append("写真を最低1枚保存してください")
        
    if errors:
        for e in errors:
            st.error(e)
        st.button("返却を確定する", type="primary", disabled=True, key="btn_ret_disabled")
    else:
        if st.button("返却を確定する", type="primary", key="btn_ret_submit"):
            # Process Submission
            
            # Check file sizes
            if uploaded_files:
                for uf in uploaded_files:
                    if uf.size > 5 * 1024 * 1024:
                        st.error(f"ファイルサイズが大きすぎます: {uf.name} (上限5MB)")
                        st.stop()
            
            

            # 1. Save Photos
            timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            session_dir_name = f"return_{unit_id}_{timestamp_str}"
            abs_session_dir = os.path.join(UPLOAD_DIR, session_dir_name)
            os.makedirs(abs_session_dir, exist_ok=True)
            
            if uploaded_files:
                for uf in uploaded_files:
                    compressed = compress_image(uf)
                    if compressed:
                        base_name, _ = os.path.splitext(uf.name)
                        save_name = f"{base_name}.webp"
                        with open(os.path.join(abs_session_dir, save_name), "wb") as f:
                            f.write(compressed.getbuffer())
                    else:
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
            
            # Add Cleaning Check (System Item)
            from src.database import get_item_by_exact_name, create_item
            clean_item_name = "汚れチェック"
            clean_item = get_item_by_exact_name(clean_item_name)
            if not clean_item:
                # Create if not exists
                clean_id = create_item(clean_item_name, "システム自動生成: 返却時の汚れ確認", "")
            else:
                clean_id = clean_item['id']
            
            check_results_list.append({
                'item_id': clean_id,
                'name': clean_item_name,
                'required_qty': 1,
                'result': 'OK', # Always OK because it is mandatory to match validation
                'ng_reason': None,
                'found_qty': None,
                'comment': "汚れなし確認済み"
            })

            # 3. Call Logic
            try:
                user_name = st.session_state.get('user_name', 'Unknown')
                
                result_status = process_return(
                    device_unit_id=unit_id,
                    return_date=return_date.isoformat(),
                    check_results=check_results_list,
                    photo_dir=session_dir_name, 
                    user_name=user_name,
                    user_id=st.session_state.get('user_id'),
                    assetment_returned=assetment_returned,
                    notes=remarks,
                    confirmation_checked=confirmation_checked
                )
                
                if result_status == 'in_stock':
                    st.markdown("""
                    <style>
                        @keyframes fadeInScale {
                            0% { opacity: 0; transform: scale(0.8); }
                            100% { opacity: 1; transform: scale(1); }
                        }
                        @keyframes checkPulse {
                            0%, 100% { transform: scale(1); }
                            50% { transform: scale(1.1); }
                        }
                        .completion-card {
                            animation: fadeInScale 0.5s ease-out forwards;
                        }
                        .completion-icon {
                            animation: checkPulse 1s ease-in-out 2;
                        }
                    </style>
                    <div class="completion-card" style="
                        background: linear-gradient(135deg, #10B981 0%, #059669 100%);
                        color: white;
                        padding: 40px 30px;
                        border-radius: 16px;
                        text-align: center;
                        margin: 30px 0;
                        box-shadow: 0 15px 35px rgba(16, 185, 129, 0.35);
                    ">
                        <div class="completion-icon" style="font-size: 56px; margin-bottom: 15px;">✓</div>
                        <div style="font-size: 26px; font-weight: 700; margin-bottom: 12px; letter-spacing: 1px;">返却登録完了</div>
                        <div style="font-size: 14px; opacity: 0.85; font-weight: 300;">ステータス: 在庫あり</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <style>
                        @keyframes fadeInScale {
                            0% { opacity: 0; transform: scale(0.8); }
                            100% { opacity: 1; transform: scale(1); }
                        }
                        .completion-card-warn {
                            animation: fadeInScale 0.5s ease-out forwards;
                        }
                    </style>
                    <div class="completion-card-warn" style="
                        background: linear-gradient(135deg, #F59E0B 0%, #D97706 100%);
                        color: white;
                        padding: 40px 30px;
                        border-radius: 16px;
                        text-align: center;
                        margin: 30px 0;
                        box-shadow: 0 15px 35px rgba(245, 158, 11, 0.35);
                    ">
                        <div style="font-size: 56px; margin-bottom: 15px;">!</div>
                        <div style="font-size: 26px; font-weight: 700; margin-bottom: 12px; letter-spacing: 1px;">登録完了</div>
                        <div style="font-size: 14px; opacity: 0.85; font-weight: 300;">NG箇所または未解決のIssueがあるため、<br>ステータスは「要対応」です</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Brief pause to show completion
                import time
                time.sleep(2)
                
                # Clear state
                st.session_state['return_mode'] = False
                del st.session_state['return_checklist_data']
                st.rerun()
                
            except ValueError as e:
                st.error(str(e))
