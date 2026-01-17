import streamlit as st
import datetime
import os
from src.database import (
    get_device_unit_by_id, get_device_type_by_id, UPLOAD_DIR
)
from src.logic import get_synthesized_checklist, process_loan, get_image_base64, compress_image

# ... (lines 9-217) ...


def render_loan_view(unit_id: int):
    # Retrieve Unit & Type Info
    unit = get_device_unit_by_id(unit_id)
    if not unit:
        st.error("Unit not found")
        if st.button("Back"):
            st.session_state['loan_mode'] = False
            st.rerun()
        return

    type_info = get_device_type_by_id(unit['device_type_id'])
    
    from src.ui import render_header
    render_header("機材貸出登録", "shopping_cart_checkout")
    st.markdown(f"**{type_info['name']}** (Lot: {unit['lot_number']})")
    
    # Back Button
    if st.button("← キャンセルして戻る"):
        st.session_state['loan_mode'] = False
        st.rerun()

    st.divider()

    # --- input Fields ---
    col1, col2 = st.columns(2)
    with col1:
        checkout_date = st.date_input("持出日", value=datetime.date.today())
        destination = st.text_input("貸出先 (必須)", placeholder="例: 〇〇病院 手術室")
    
    with col2:
        purpose_options = [
            "臨床使用（点検代替含む）",
            "デモ（非臨床・説明用）",
            "事故・故障対応",
            "レンタル",
            "学会展示",
            "定期点検・修理（TM部用）"
        ]
        purpose = st.selectbox("貸出目的", purpose_options)
        
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

    # Camera Toggle Logic
    if 'show_camera_loan' not in st.session_state:
        st.session_state['show_camera_loan'] = False

    # File Uploader (standard with Japanese localization via CSS)
    uploaded_files = st.file_uploader("写真アップロード", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
    
    # Camera Toggle Button - positioned on the right below the uploader
    col_spacer, col_cam_btn = st.columns([0.75, 0.25])
    with col_cam_btn:
        if st.button("📷 カメラ起動" if not st.session_state['show_camera_loan'] else "❌ 閉じる", key="cam_toggle_loan", use_container_width=True):
            st.session_state['show_camera_loan'] = not st.session_state['show_camera_loan']
            st.rerun()

    camera_image = None
    if st.session_state['show_camera_loan']:
        st.caption("撮影ボタンを押して写真を記録してください")
        camera_image = st.camera_input("カメラ", label_visibility="collapsed")
    
    st.subheader("構成品チェック")
    
    # helper for session state initialization
    if 'checklist_data' not in st.session_state or st.session_state.get('current_loan_unit_id') != unit_id:
        # Initialize
        checklist_items = get_synthesized_checklist(unit['device_type_id'], unit['id'])
        st.session_state['checklist_data'] = {}
        st.session_state['checklist_items_source'] = checklist_items # Keep reference order
        st.session_state['current_loan_unit_id'] = unit_id
        
        for item in checklist_items:
            st.session_state['checklist_data'][item['item_id']] = {
                'result': 'OK',
                'ng_reason': '紛失', # default
                'found_qty': 0,
                'comment': ''
            }
            
    # Render Checklist
    checklist_items = st.session_state['checklist_items_source']
    
    for item in checklist_items:
        item_id = item['item_id']
        data = st.session_state['checklist_data'][item_id]
        
        with st.container(border=True):
            r1, r2 = st.columns([3, 2])
            with r1:
                name_disp = item['name']
                if item['is_override']:
                    name_disp += " (個体差分)"
                st.markdown(f"**{name_disp}**")
                st.caption(f"必要数: {item['required_qty']}")
                
                # Show image if exists
                # Show image if exists
                if item['photo_path']:
                    full_path = os.path.join(UPLOAD_DIR, item['photo_path'])
                    if os.path.exists(full_path):
                        # Use same logic as Home View
                        b64 = get_image_base64(full_path)
                        if b64:
                            st.markdown(f'<img src="data:image/png;base64,{b64}" style="width: 120px; height: 120px; object-fit: contain; border: 1px solid #ddd; border-radius: 4px;">', unsafe_allow_html=True)
                        else:
                            st.caption("Load Error")
                    else:
                        # Placeholder
                        st.markdown('<div style="width: 120px; height: 120px; background-color: #f0f0f0; border-radius: 4px; display: flex; align-items: center; justify-content: center; color: #888;">No Image</div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div style="width: 120px; height: 120px; background-color: #f0f0f0; border-radius: 4px; display: flex; align-items: center; justify-content: center; color: #888;">No Image</div>', unsafe_allow_html=True)

            with r2:
                # Result Toggle
                # We use radio with horizontal=True
                res = st.radio(
                    f"Result_{item_id}", 
                    ['OK', 'NG'], 
                    index=0 if data['result'] == 'OK' else 1,
                    key=f"res_{item_id}",
                    horizontal=True,
                    label_visibility="collapsed"
                )
                
                # Update state immediately (this reruns script, so we need consistent state)
                st.session_state['checklist_data'][item_id]['result'] = res
                
                if res == 'NG':
                    st.error("NG詳細を入力してください")
                    reason = st.selectbox(
                        "理由", 
                        ['紛失', '破損', '数量不足'], 
                        key=f"reason_{item_id}",
                        index=['紛失', '破損', '数量不足'].index(data['ng_reason'])
                    )
                    st.session_state['checklist_data'][item_id]['ng_reason'] = reason
                    
                    if reason == '数量不足':
                        fq = st.number_input("確認数量", min_value=0, value=data['found_qty'], key=f"fq_{item_id}")
                        st.session_state['checklist_data'][item_id]['found_qty'] = fq
                        
                    comm = st.text_input("コメント", value=data['comment'], key=f"comm_{item_id}")
                    st.session_state['checklist_data'][item_id]['comment'] = comm



    st.divider()
    st.markdown("### 外部システム登録確認")
    assetment_checked = st.checkbox("AssetmentNeoの貸出登録は済んでいますか？")
    if not assetment_checked:
        st.info("💡 貸出登録が済んでいない場合は [https://saas.assetment.net/AS3230-PA0200320/](https://saas.assetment.net/AS3230-PA0200320/) から貸出登録を行ってから持出お願いします")

    st.divider()
    st.markdown("### 備考（任意）")
    remarks = st.text_area("自由に記載できます", placeholder="例：〇〇先生使用分、返却予定日など", key="loan_remarks")

    
    # Error Display
    errors = []
    if not destination:
        errors.append("貸出先を入力してください")
    if not uploaded_files and not camera_image:
        errors.append("写真を最低1枚保存してください（アップロード または カメラ撮影）")
    if not assetment_checked:
        errors.append("AssetmentNeoの登録確認を行ってください")
        
    if errors:
        for e in errors:
            st.error(e)
        st.button("登録 (入力不備があります)", disabled=True)
    else:
        if st.button("貸出を確定する", type="primary"):
            # Process Submission
            
            # 1. Save Photos
            # Create a specific directory for this session photos?
            # Or just unique filenames in uploads?
            # Phase 2 requirement: keep it simple in uploads or struct?
            # User requirement: "device_photo_dir（このチェックの写真保存先）"
            # Let's make a new subdirectory YYYYMMDD_Loan_UnitID
            timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            session_dir_name = f"loan_{unit_id}_{timestamp_str}"
            abs_session_dir = os.path.join(UPLOAD_DIR, session_dir_name)
            os.makedirs(abs_session_dir, exist_ok=True)
            
            if uploaded_files:
                for i, uf in enumerate(uploaded_files):
                    compressed = compress_image(uf)
                    if compressed:
                        # Force .webp extension
                        base_name = f"photo_upload_{i}"
                        save_name = f"{base_name}.webp"
                        with open(os.path.join(abs_session_dir, save_name), "wb") as f:
                            f.write(compressed.getvalue())
                    else:
                        # Fallback (shouldn't happen often)
                        with open(os.path.join(abs_session_dir, uf.name), "wb") as f:
                            f.write(uf.getvalue())
            
            if camera_image:
                # Compress camera image too
                compressed_cam = compress_image(camera_image)
                cam_filename = f"camera_{datetime.datetime.now().strftime('%H%M%S')}.webp"
                
                with open(os.path.join(abs_session_dir, cam_filename), "wb") as f:
                    if compressed_cam:
                        f.write(compressed_cam.getvalue())
                    else:
                        f.write(camera_image.getvalue())
                    
            # 2. Build Check Results List
            check_results_list = []
            for item in checklist_items:
                iid = item['item_id']
                d = st.session_state['checklist_data'][iid]
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
                # We don't have user_id easily unless we store it. 
                # auth.py stores 'user_email'? get_user_by_email -> id
                # For now pass None for checker_user_id or fetch it.
                # Let's assume we can proceed with user_name for 'performed_by'.
                
                result_status = process_loan(
                    device_unit_id=unit_id,
                    checkout_date=checkout_date.isoformat(),
                    destination=destination,
                    purpose=purpose,
                    check_results=check_results_list,
                    photo_dir=session_dir_name, # Relative path
                    user_name=user_name,
                    user_id=st.session_state.get('user_id'),
                    assetment_checked=assetment_checked,
                    notes=remarks
                )
                
                if result_status == 'loaned':
                    st.success("貸出登録完了！ (ステータス: 貸出中)")
                else:
                    st.warning("登録完了！ (NG箇所があるため、ステータスは「要対応」になりました)")
                
                # Clear state
                st.session_state['loan_mode'] = False
                st.session_state['selected_unit_id'] = None # Go back to list? Or stay?
                # Let's go back to Unit Detail (which will now show new status)
                st.session_state['selected_unit_id'] = unit_id 
                # But we should clear 'checklist_data'
                del st.session_state['checklist_data']
                st.rerun()
                
            except ValueError as e:
                st.error(str(e))
