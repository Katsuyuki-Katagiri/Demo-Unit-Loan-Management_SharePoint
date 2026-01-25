import streamlit as st
import os
import shutil
import uuid
from datetime import datetime, date
from src.logic import compress_image
from src.database import (
    get_all_categories, create_device_type, get_device_types,
    create_item, get_all_items, add_template_line, get_template_lines,
    create_device_unit, get_device_units, add_unit_override, 
    get_unit_overrides, update_device_unit, UPLOAD_DIR,
    update_item, delete_item, update_device_type_name,
    delete_device_type, get_all_departments, update_category_managing_department,
    get_department_by_id, upload_photo_to_storage
)


def render_master_view():
    from src.ui import render_header
    render_header("マスタ管理", "settings")
    
    # Main Tabs
    main_tab1, main_tab2, main_tab3 = st.tabs([
        "機種管理", 
        "構成品マスタ",
        "カテゴリ設定"
    ])
    
    # --- Tab 3: Category Visibility ---
    with main_tab3:
        st.header("カテゴリ表示設定")
        st.caption("ホーム画面に表示する装置カテゴリのON/OFF、名称変更、管理部署設定、追加・削除が行えます。")
        
        from src.database import (
            update_category_visibility, create_category, 
            update_category_name, delete_category, update_category_basic_info,
            move_category_order
        )
        
        # Prepare department options for dropdown
        departments = get_all_departments()
        dept_options = {"（未設定）": None}
        dept_options.update({d['name']: d['id'] for d in departments})
        dept_map_by_id = {d['id']: d for d in departments}
        
        # --- Add New Category ---
        with st.expander("➕ 新しいカテゴリを追加", expanded=False):
            with st.form("add_cat_form"):
                new_cat_name = st.text_input("カテゴリ名")
                if st.form_submit_button("追加"):
                    if new_cat_name:
                        success, msg = create_category(new_cat_name)
                        if success:
                            st.cache_data.clear()
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.warning("カテゴリ名を入力してください")

        st.divider()

        cats = get_all_categories()
        # cats rows: id, name, is_visible, managing_department_id
        
        if cats:
            for cat in cats:
                # Default is_visible=1 if None
                is_vis = bool(cat['is_visible']) if 'is_visible' in cat.keys() and cat['is_visible'] is not None else True
                
                with st.container(border=True):
                    # Adjusted columns: Name(3), Up(0.5), Down(0.5), UpdateBtn(1), Visible(1), Delete(0.5)
                    # We need compact columns for arrows
                    row1_c1, row1_c2, row1_c3, row1_c4, row1_c5, row1_c6 = st.columns([3, 0.4, 0.4, 0.8, 1, 0.5])
                    
                    # 1. Edit Name
                    new_name_input = row1_c1.text_input("名称", value=cat['name'], key=f"cat_name_{cat['id']}", label_visibility="collapsed")
                    
                    # 2. Sort Buttons
                    if row1_c2.button("↑", key=f"mv_up_{cat['id']}", help="上に移動"):
                        success, msg = move_category_order(cat['id'], 'up')
                        if success:
                            st.cache_data.clear()
                            st.rerun()
                            
                    if row1_c3.button("↓", key=f"mv_down_{cat['id']}", help="下に移動"):
                        success, msg = move_category_order(cat['id'], 'down')
                        if success:
                            st.cache_data.clear()
                            st.rerun()

                    # Description (Full width below)
                    current_desc = cat['description'] if 'description' in cat.keys() and cat['description'] else ""
                    new_desc_input = st.text_area("補足説明", value=current_desc, key=f"cat_desc_{cat['id']}", height=68, placeholder="補足説明を入力...")

                    # 3. Update Button (Name & Description only now, sort is handled by buttons)
                    if row1_c4.button("更新", key=f"upd_cat_{cat['id']}", help="保存"):
                        if new_name_input:
                            # Pass 0 or current sort for sort_order arg? 
                            # Since we don't edit sort order here, we can just pass current or ignore if we update function to be optional
                            # Re-using update_category_basic_info requires 4 args. 
                            # Let's pass the current sort_order to avoid overwriting it accidentally, though move_category handles it mostly.
                            current_sort = cat['sort_order'] if 'sort_order' in cat.keys() else 0
                            if update_category_basic_info(cat['id'], new_name_input, new_desc_input, current_sort):
                                st.cache_data.clear()
                                st.success("更新しました")
                                st.rerun()
                            else:
                                st.error("更新失敗")
                        else:
                            st.warning("名称は必須です")
                    
                    # 4. Visibility (Toggle)
                    current_toggle = row1_c5.toggle("表示", value=is_vis, key=f"cat_vis_{cat['id']}")
                    if current_toggle != is_vis:
                         update_category_visibility(cat['id'], current_toggle)
                         st.cache_data.clear()
                         st.rerun()

                    # 5. Delete Button
                    if row1_c6.button("🗑️", key=f"del_cat_{cat['id']}", help="削除"):
                         success, msg = delete_category(cat['id'])
                         if success:
                             st.cache_data.clear()
                             st.success(msg)
                             st.rerun()
                         else:
                             st.error(msg)
                    
                    # 5. Managing Department Selection (row 2)
                    current_dept_id = cat.get('managing_department_id')
                    current_dept_name = "（未設定）"
                    if current_dept_id:
                        dept_info = dept_map_by_id.get(current_dept_id)
                        if dept_info:
                            current_dept_name = dept_info['name']
                    
                    dept_names = list(dept_options.keys())
                    current_idx = 0
                    for i, name in enumerate(dept_names):
                        if name == current_dept_name:
                            current_idx = i
                            break
                    
                    row2_c1, row2_c2 = st.columns([1, 3])
                    row2_c1.caption("管理部署:")
                    new_dept_name = row2_c2.selectbox(
                        "管理部署",
                        dept_names,
                        index=current_idx,
                        key=f"cat_dept_{cat['id']}",
                        label_visibility="collapsed"
                    )
                    new_dept_id = dept_options[new_dept_name]
                    if new_dept_id != current_dept_id:
                        update_category_managing_department(cat['id'], new_dept_id)
                        st.cache_data.clear()
                        st.rerun()
        else:
            st.info("カテゴリがありません")
    
    # --- Tab 1: Device Management Hub ---
    with main_tab1:
        # 1. Device Registration / Selection
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("機種登録・選択")
            # Register New
            with st.expander("➕ 新しい機種を登録"):
                with st.form("add_type_form"):
                    cats = get_all_categories()
                    cat_options = {c['name']: c['id'] for c in cats}
                    selected_cat = st.selectbox("カテゴリ", options=list(cat_options.keys()))
                    type_name = st.text_input("機種名")
                    if st.form_submit_button("登録"):
                        if type_name:
                            create_device_type(cat_options[selected_cat], type_name)
                            st.cache_data.clear()
                            st.success(f"登録しました: {type_name}")
                            st.rerun()

            # Select Existing
            st.markdown("### 機種を選択")
            filter_cat = st.selectbox("カテゴリフィルター", ["全て"] + list(cat_options.keys()))
            
            if filter_cat == "全て":
                types = get_device_types()
            else:
                types = get_device_types(cat_options[filter_cat])
            
            type_opts = {f"{t['name']} (ID:{t['id']})": t['id'] for t in types}
            selected_type_key = st.radio("編集する機種を選んでください", options=list(type_opts.keys()))

        with col2:
            if selected_type_key:
                selected_type_id = type_opts[selected_type_key]
                # Get current type info
                current_type = next((t for t in types if t['id'] == selected_type_id), None)
                current_type_name = current_type['name'] if current_type else ""
                
                # Header with delete button
                header_col, delete_col = st.columns([6, 1])
                with header_col:
                    st.subheader(f"編集: {current_type_name}")
                with delete_col:
                    # Initialize delete confirmation state
                    if 'confirm_delete_type' not in st.session_state:
                        st.session_state.confirm_delete_type = False
                    
                    if st.button("🗑️", key="delete_type_btn", help="この機種を削除"):
                        st.session_state.confirm_delete_type = True
                        st.rerun()
                
                # Show confirmation dialog
                if st.session_state.get('confirm_delete_type', False):
                    st.warning(f"⚠️ 「{current_type_name}」を削除しますか？紐付いている全ての実機、貸出履歴、点検記録が完全に削除されます。")
                    confirm_col1, confirm_col2, _ = st.columns([1, 1, 3])
                    with confirm_col1:
                        if st.button("はい、削除する", type="primary", key="confirm_yes"):
                            from src.database import delete_device_type
                            success, msg = delete_device_type(selected_type_id)
                            st.session_state.confirm_delete_type = False
                            if success:
                                st.cache_data.clear()
                                st.warning(msg)
                                st.rerun()
                            else:
                                st.error(msg)
                    with confirm_col2:
                        if st.button("キャンセル", key="confirm_no"):
                            st.session_state.confirm_delete_type = False
                            st.rerun()
                
                # --- Edit Device Name ---
                with st.expander("✏️ 機種名を編集"):
                    with st.form("edit_type_name_form"):
                        new_type_name = st.text_input("機種名", value=current_type_name)
                        if st.form_submit_button("変更"):
                            if new_type_name and new_type_name != current_type_name:
                                if update_device_type_name(selected_type_id, new_type_name):
                                    st.cache_data.clear()
                                    st.success("機種名を変更しました")
                                    st.rerun()
                                else:
                                    st.error("エラー: その機種名は既に使用されている可能性があります")
                            
                st.divider()
                
                # --- Section 1: Unit Info ---
                st.markdown("#### ① ロット情報")
                st.caption("この機種の実機（ロット）を管理します。※1機種につき1台のみ登録可能です")
                
                # List Units
                units = get_device_units(selected_type_id)
                
                if units:
                    # Check for duplicates
                    if len(units) > 1:
                        st.error(f"⚠️ エラー: 複数のロット({len(units)}台)が登録されています。不要なデータを削除してください。")
                        for u in units:
                            with st.container(border=True):
                                c1, c2, c3 = st.columns([2, 2, 1])
                                c1.write(f"Lot: **{u['lot_number']}** (ID: {u['id']})")
                                c2.caption(f"Status: {u['status']} | Loc: {u['location']}")
                                if c3.button("削除", key=f"del_unit_{u['id']}", type="primary"):
                                    from src.database import delete_device_unit
                                    delete_device_unit(u['id'])
                                    st.cache_data.clear()
                                    st.warning(f"ID: {u['id']} を削除しました")
                                    st.rerun()

                    else:
                        # EDIT MODE (Single Unit)
                        unit = units[0] 
                        
                        # Display current info
                        st.dataframe(
                            [{"ロット": u['lot_number'], "保管場所": u['location'], "製造年月日": u['mfg_date'], "点検実施日": u['last_check_date'], "次回点検予定日": u['next_check_date']} for u in units],
                            use_container_width=True
                        )

                        with st.expander("ロット情報を編集", expanded=False):
                            with st.form("edit_unit_form"):
                                c1, c2 = st.columns(2)
                                new_lot = c1.text_input("ロット番号", value=unit['lot_number'])
                                new_loc = c2.text_input("保管場所", value=unit['location'] if unit['location'] else "")
                                new_mfg = st.text_input("製造年月日", value=unit['mfg_date'] if unit['mfg_date'] else "")
                                
                                c3, c4 = st.columns(2)
                                # Helper for date input
                                def parse_date(d_str):
                                    if d_str:
                                        try:
                                            return datetime.strptime(d_str, '%Y-%m-%d').date()
                                        except:
                                            return None
                                    return None

                                last_check = c3.date_input("点検実施日", value=parse_date(unit['last_check_date']), format="YYYY/MM/DD")
                                next_check = c4.date_input("次回点検予定日", value=parse_date(unit['next_check_date']), format="YYYY/MM/DD")
                                
                                if st.form_submit_button("更新"):
                                    l_str = last_check.strftime('%Y-%m-%d') if last_check else ""
                                    n_str = next_check.strftime('%Y-%m-%d') if next_check else ""
                                    
                                    if new_lot:
                                        if update_device_unit(unit['id'], new_lot, new_mfg, new_loc, l_str, n_str):
                                            st.cache_data.clear()
                                            st.success("更新しました")
                                            st.rerun()
                                        else:
                                            st.error("更新失敗 (重複など)")
                else:
                    # CREATE MODE
                    st.info("まだ登録されていません。")
                    with st.expander("新規ロット登録", expanded=True):
                        with st.form("add_unit_quick"):
                            c1, c2 = st.columns(2)
                            lot_num = c1.text_input("ロット番号 (必須)")
                            loc = c2.text_input("保管場所")
                            mfg = st.text_input("製造年月日")
                            
                            c3, c4 = st.columns(2)
                            last_check = c3.date_input("点検実施日", value=None, format="YYYY/MM/DD")
                            next_check = c4.date_input("次回点検予定日", value=None, format="YYYY/MM/DD")

                            if st.form_submit_button("登録"):
                                l_str = last_check.strftime('%Y-%m-%d') if last_check else ""
                                n_str = next_check.strftime('%Y-%m-%d') if next_check else ""

                                if lot_num:
                                    if create_device_unit(selected_type_id, lot_num, mfg, loc, l_str, n_str):
                                        st.cache_data.clear()
                                        st.success(f"登録しました: {lot_num}")
                                        st.rerun()
                                    else:
                                        st.error("登録失敗 (重複など)")

                st.divider()

                # --- Section 2: Component List (formerly Template) ---
                st.markdown("#### ② 構成品一覧")
                st.caption("この機種の標準的な付属品（チェックリスト）を定義します。")
                
                # Current Template
                current_lines = get_template_lines(selected_type_id)
                if current_lines:
                    st.markdown("**現在の構成:**")
                    from src.database import delete_template_line
                    for line in current_lines:
                        c1, c2 = st.columns([8, 1])
                        c1.text(f"・ {line['item_name']} (必要数: {line['required_qty']})")
                        if c2.button("🗑️", key=f"del_line_{line['id']}", help="この構成品を削除"):
                             delete_template_line(selected_type_id, line['item_id'])
                             st.cache_data.clear()
                             st.rerun()
                else:
                    st.info("構成品が登録されていません。")
                
                with st.expander("構成品を追加/編集"):
                    st.caption("※希望する構成品がない場合は「構成品マスタ」タブから構成品を追加してください")
                    with st.form("add_tpl_line"):
                        all_items = get_all_items()
                        item_opts = {f"{i['name']}": i['id'] for i in all_items}
                        sel_item_key = st.selectbox("構成品を選択", options=list(item_opts.keys()))
                        req_qty = st.number_input("必要数量", min_value=1, value=1)
                        if st.form_submit_button("追加/更新"):
                            add_template_line(selected_type_id, item_opts[sel_item_key], req_qty)
                            st.cache_data.clear()
                            st.success("更新しました")
                            st.rerun()



    # --- Tab 2: Item Master ---
    with main_tab2:
        st.header("構成品マスタ登録")
        st.caption("ケーブルやマニュアルなど、構成品のパーツを登録します。")
        
        col_i1, col_i2 = st.columns([1, 2])
        with col_i1:
            with st.form("add_item_global", clear_on_submit=True):
                item_name = st.text_input("構成品名")
                item_tips = st.text_area("確認時のTips")
                uploaded_file = st.file_uploader("写真", type=['png', 'jpg', 'jpeg'])
                if st.form_submit_button("登録"):
                    if item_name:
                        photo_path = ""
                        if uploaded_file:
                            if uploaded_file.size > 5 * 1024 * 1024:
                                st.error("ファイルサイズが大きすぎます (上限5MB)")
                                return

                            # 構成品マスタ用：より強い圧縮（最大400x400, 品質40）
                            compressed = compress_image(uploaded_file, max_size=(400, 400), quality=40)
                            if compressed:
                                # ユニークなファイル名を生成
                                unique_name = f"item_{uuid.uuid4().hex[:8]}.webp"
                                # Supabase Storageにアップロード
                                photo_url = upload_photo_to_storage(compressed.getvalue(), unique_name)
                                if photo_url:
                                    photo_path = photo_url
                                else:
                                    st.warning("写真のアップロードに失敗しました")
                            else:
                                st.warning("写真の圧縮に失敗しました")
                        create_item(item_name, item_tips, photo_path)
                        st.cache_data.clear()
                        st.success(f"登録しました: {item_name}")
                        st.rerun()

        with col_i2:
            st.subheader("登録済み構成品一覧")
            # Reduce spacing between items
            st.markdown("""
                <style>
                [data-testid="stExpander"] {
                    margin-bottom: -1rem; 
                }
                </style>
            """, unsafe_allow_html=True)
            items = get_all_items()
            for i in items:
                with st.expander(f"{i['name']}"):
                    c_img, c_txt = st.columns([1, 2])
                    photo_path = i.get('photo_path')
                    if photo_path:
                        # URLの場合は直接表示、ローカルパスの場合は既存の処理
                        if photo_path.startswith('http'):
                            c_img.image(photo_path)
                        else:
                            fp = os.path.join(UPLOAD_DIR, photo_path)
                            if os.path.exists(fp):
                                c_img.image(fp)
                    c_txt.write(i['tips'])
                    
                    st.divider()
                    st.caption("編集 / 削除")
                    with st.form(f"edit_item_{i['id']}"):
                        new_name = st.text_input("構成品名", value=i['name'])
                        new_tips = st.text_area("Tips", value=i['tips'])
                        new_file = st.file_uploader("写真更新", key=f"file_{i['id']}")
                        
                        c_upd, c_del = st.columns(2)
                        
                        if c_upd.form_submit_button("更新"):
                            photo_path = ""
                            if new_file:
                                # 構成品マスタ用：より強い圧縮（最大400x400, 品質40）
                                compressed = compress_image(new_file, max_size=(400, 400), quality=40)
                                if compressed:
                                    # ユニークなファイル名を生成
                                    unique_name = f"item_{uuid.uuid4().hex[:8]}.webp"
                                    # Supabase Storageにアップロード
                                    photo_url = upload_photo_to_storage(compressed.getvalue(), unique_name)
                                    if photo_url:
                                        photo_path = photo_url
                                    else:
                                        st.warning("写真のアップロードに失敗しました")
                                else:
                                    st.warning("写真の圧縮に失敗しました")
                                
                            if update_item(i['id'], new_name, new_tips, photo_path):
                                st.cache_data.clear()
                                st.success("更新しました")
                                st.rerun()
                                
                        if c_del.form_submit_button("削除", type="primary"):
                            success, msg = delete_item(i['id'])
                            if success:
                                st.cache_data.clear()
                                st.warning(msg)
                                st.rerun()
                            else:
                                st.error(msg)
    
    # --- Tab 3: Data Management (Admin Only) ---
    current_user_email = st.session_state.get('user_email', '')
    current_user_role = st.session_state.get('user_role', '')
    
    st.divider()
    st.caption(f" Debug Info: 現在のログインユーザー = '{current_user_email}' (権限: '{current_user_role}')")
    
    # Add tab if admin role or admin@example.com (case-insensitive check)
    is_admin = (current_user_role.lower() == 'admin' if current_user_role else False) or current_user_email == 'admin@example.com'
    st.caption(f" Debug: is_admin = {is_admin}, role.lower() = '{current_user_role.lower() if current_user_role else ''}')")
    
    if is_admin:
        # Re-create tabs to include Data Management
        # Note: Streamlit tabs must be defined at once.
        # Since we defined tabs at the top, we can't easily add one here without restructuring.
        # So we will append it below for now, but with clear visibility.
        
        st.markdown("## 🛠️ データ管理エリア")
        
        with st.expander("データベース初期化 (Admin Only)", expanded=True):
            st.error("⚠️ 危険エリア: ここでの操作は取り消せません")
            st.write(f"認証済み管理者: {current_user_email}")
            
            st.subheader("データベース初期化")
            st.markdown("""
                以下のデータを**全て削除**し、システムを初期状態に戻します。
                - 全ての機材・構成品登録
                - 全ての貸出・返却・点検記録
                - admin権限以外の全ユーザー
                - アップロードされた全画像ファイル
                
                ※カテゴリー情報は初期値にリセットされます。
                ※**admin権限ユーザーは削除されません。**
            """)
            
            confirm_reset = st.checkbox("上記を確認し、本当にデータを削除することに同意します (I agree to wipe all data)")
            
            if st.button("システムを完全初期化する", type="primary", disabled=not confirm_reset):
                from src.database import reset_database_keep_admin
                with st.spinner("初期化中..."):
                    if reset_database_keep_admin():
                        st.success("初期化が完了しました。")
                        st.balloons()
                        st.session_state['db_initialized'] = False
                        st.rerun()
                    else:
                        st.error("初期化に失敗しました。")
    else:
        st.warning("⚠️ データ初期化機能は管理者権限（admin）を持つユーザーのみ表示されます。")
