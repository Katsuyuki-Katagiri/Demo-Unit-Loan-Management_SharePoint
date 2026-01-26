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
    user_role = st.session_state.get('user_role')
    
    # Conditional Tabs
    if user_role == 'admin':
        main_tab1, main_tab2, main_tab3 = st.tabs([
            "機種管理", 
            "構成品マスタ",
            "カテゴリ設定"
        ])
    else:
        main_tab1, main_tab2 = st.tabs([
            "機種管理", 
            "構成品マスタ"
        ])
        main_tab3 = None
    
    # --- Tab 3: Category Visibility (Admin Only) ---
    if user_role == 'admin' and main_tab3:
        with main_tab3:
            from src.views.master_category import render_category_settings_tab
            render_category_settings_tab()
    
    # --- Tab 1: Device Management Hub ---
    
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
                            new_type_id = create_device_type(cat_options[selected_cat], type_name)
                            st.session_state['master_selected_type_id'] = new_type_id
                            # Widgetの選択状態も更新（これがないと古いラベルのままになるか、リセットされない）
                            # 次のリロード時にIDからラベルを逆引きしてセットされるが、念のためクリアしておくことで自動設定を促す
                            # または、ここでラベルを計算できればベストだが、rerunしたほうが安全
                            if 'master_device_selector' in st.session_state:
                                del st.session_state['master_device_selector']
                                
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
            
            # ロット情報がある場合はロット番号を表示、ない場合はIDを表示
            # パフォーマンス改善: 一括取得でN+1問題を回避
            from src.database import get_device_units_for_types
            type_ids = [t['id'] for t in types]
            units_by_type = get_device_units_for_types(type_ids) if type_ids else {}
            
            type_opts = {}
            # ID -> Label Map for reverse lookup
            id_to_label = {}
            
            for t in types:
                units = units_by_type.get(t['id'], [])
                if units and units[0].get('lot_number'):
                    label = f"{t['name']} (Lot:{units[0]['lot_number']})"
                else:
                    label = f"{t['name']} (ID:{t['id']})"
                type_opts[label] = t['id']
                id_to_label[t['id']] = label
            
            # Determine initial selection based on ID
            # Use 'master_device_selector' key for widget state persistence
            widget_key = "master_device_selector"
            
            # 1. 保存されたIDからラベルを特定
            target_label = None
            if 'master_selected_type_id' in st.session_state:
                saved_id = st.session_state['master_selected_type_id']
                if saved_id in id_to_label:
                    target_label = id_to_label[saved_id]
            
            # 2. ラベルが見つからない（初期状態 or 削除済み）場合は先頭を選択
            if target_label is None and type_opts:
                target_label = list(type_opts.keys())[0]
                
            # 3. Widgetのセッションステートを更新（条件付き）
            # 常に上書きするとユーザーの変更を打ち消してしまうため、
            # 未設定の場合や、現在の選択肢に含まれていない場合のみ更新する
            should_update_widget = False
            if widget_key not in st.session_state:
                should_update_widget = True
            elif st.session_state[widget_key] not in type_opts:
                should_update_widget = True
            
            if should_update_widget and target_label:
                st.session_state[widget_key] = target_label

            # Callback: ラベル変更時にIDを保存
            def on_device_select():
                selected_label = st.session_state[widget_key]
                if selected_label in type_opts:
                    st.session_state['master_selected_type_id'] = type_opts[selected_label]

            # 4. Render Radio Button (index引数は使用しない)
            selected_type_key = st.radio(
                "編集する機種を選んでください", 
                options=list(type_opts.keys()),
                key=widget_key,
                on_change=on_device_select
            )
            
            # 初回レンダリング時などのためにIDも同期しておく
            if selected_type_key and 'master_selected_type_id' not in st.session_state:
                 st.session_state['master_selected_type_id'] = type_opts[selected_type_key]

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
                
                # --- Edit Device Info ---
                with st.expander("✏️ 機種情報（名称・補足）を編集"):
                    with st.form("edit_type_info_form"):
                        from src.database import update_device_type_basic_info
                        
                        new_type_name = st.text_input("機種名", value=current_type_name)
                        
                        # current_type keys check to avoid KeyError if description missing
                        current_desc = current_type.get('description', '') if current_type else ""
                        new_desc = st.text_area("補足説明", value=current_desc, help="機種に関する補足情報を入力できます")

                        if st.form_submit_button("変更を保存"):
                            if new_type_name:
                                if update_device_type_basic_info(selected_type_id, new_type_name, new_desc):
                                    st.cache_data.clear()
                                    st.success("機種情報を更新しました")
                                    st.rerun()
                                else:
                                    st.error("更新エラー: 必要であればデータベースにdescriptionカラムを追加してください。")
                            else:
                                st.error("機種名は必須です")
                            
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
                                    
                                    # Update basic info
                                    from src.database import update_device_unit
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
                st.caption("この機種の標準的な付属品（チェックリスト）を定義します。チェックを外すと不足品として登録されます。")
                
                # Current Template
                current_lines = get_template_lines(selected_type_id)
                if current_lines:
                    from src.database import delete_template_line, update_device_unit_missing_items
                    
                    # 現在の不足品を取得（ロットが存在する場合）
                    current_missing_ids = set()
                    if units:
                        unit = units[0]  # 1機種1ロット制限
                        cur_str = unit.get('missing_items')
                        if cur_str:
                            m_ids = [m.strip() for m in str(cur_str).split(',') if m.strip()]
                            current_missing_ids = {int(m) for m in m_ids if m.isdigit()}
                    
                    st.markdown("**現在の構成:**")
                    st.caption("🔴 ON = 揃っている | ⚪ OFF = 不足品")
                    
                    # 不足品を追跡するためのリスト (計算用)
                    missing_items_selected = []
                    
                    # --- Auto-save callback logic ---
                    def on_toggle_change(unit_id, item_id, key):
                        # Get new state from session state
                        new_state = st.session_state[key]
                        # True = Available (Not Missing), False = Missing
                        
                        # Current missing items (reload from DB to be safe)
                        from src.database import get_device_unit_by_id, update_device_unit_missing_items
                        u = get_device_unit_by_id(unit_id)
                        current_missing = set()
                        if u and u.get('missing_items'):
                            m_ids = [m.strip() for m in str(u['missing_items']).split(',') if m.strip()]
                            current_missing = {int(m) for m in m_ids if m.isdigit()}
                        
                        if new_state:
                            # Available -> Remove from missing if present
                            if item_id in current_missing:
                                current_missing.remove(item_id)
                        else:
                            # Missing -> Add to missing
                            current_missing.add(item_id)
                            
                        # Save back to DB
                        update_device_unit_missing_items(unit_id, list(current_missing))
                        # Toast notification
                        action = "揃っている" if new_state else "不足"
                        st.toast(f"状態を保存しました: {action}")
                    
                    for idx, line in enumerate(current_lines, 1):
                        item_id = line['item_id']
                        item_name = line['item_name']
                        required_qty = line['required_qty']
                        is_missing = item_id in current_missing_ids
                        
                        if is_missing:
                            missing_items_selected.append(item_id)
                        
                        # 各構成品の行
                        col_toggle, col_name, col_del = st.columns([1, 7, 1])
                        
                        with col_toggle:
                            # トグルスイッチ: ON = 揃っている、OFF = 不足
                            toggle_key = f"avail_toggle_{selected_type_id}_{item_id}"
                            
                            # Auto-save enabled toggle
                            # Note: unit is available here (units[0])
                            u_id = units[0]['id'] if units else 0
                            
                            is_available = st.toggle(
                                "在庫",
                                value=not is_missing,  # 不足品以外はON
                                key=toggle_key,
                                label_visibility="collapsed",
                                on_change=on_toggle_change,
                                args=(u_id, item_id, toggle_key),
                                disabled=not units # Disable if no unit registered
                            )
                        
                        with col_name:
                            if is_available:
                                st.text(f"{idx}. {item_name} (必要数: {required_qty})")
                            else:
                                st.markdown(f"**{idx}. {item_name}** (必要数: {required_qty}) ⚠️ **不足**")
                        
                        with col_del:
                            if st.button("🗑️", key=f"del_line_{line['id']}", help="この構成品を削除"):
                                delete_template_line(selected_type_id, item_id)
                                st.cache_data.clear()
                                st.rerun()
                    
                    # 不足品の件数表示 (ボタンは削除)
                    st.divider()
                    missing_count = len(missing_items_selected)
                    
                    if missing_count > 0:
                        st.warning(f"⚠️ 現在の不足品: **{missing_count}件** (自動保存されます)")
                    else:
                        st.success("✅ 全ての構成品が揃っています")
                    
                else:
                    st.info("構成品が登録されていません。")
                
                with st.expander("構成品を追加/編集"):
                    st.caption("※希望する構成品がない場合は「構成品マスタ」タブから構成品を追加してください")
                    
                    # 検索フィルター
                    # Enterキーでの反応を確実にするため、コールバックを設定（空でも動作するが、rerunを明示しても良い）
                    def on_search_submit():
                        pass
                        
                    filter_keyword = st.text_input(
                        "🔍 構成品を検索・絞り込み", 
                        key="search_tpl_item",
                        on_change=on_search_submit
                    )
                    
                    all_items = get_all_items()
                    # "汚れチェック"を除外 + 検索キーワードでフィルタリング
                    all_items = [
                        i for i in all_items 
                        if i.get('name') != '汚れチェック' 
                        and (filter_keyword.lower() in i.get('name', '').lower() if filter_keyword else True)
                    ]
                    
                    if not all_items:
                        st.info("該当する構成品がありません")
                    else:
                        # 既存の構成品IDを取得（登録済みかどうかの判定用）
                        existing_item_ids = {line['item_id'] for line in current_lines}
                        
                        # セッションステートで選択状態と数量を管理
                        if 'bulk_add_selections' not in st.session_state:
                            st.session_state.bulk_add_selections = {}
                        
                        st.markdown("**構成品を選択（複数選択可）**")
                        st.caption("チェックを入れて数量を設定し、「一括登録」ボタンで登録します")
                        
                        # 選択用のコンテナ
                        selection_container = st.container()
                        with selection_container:
                            for item in all_items:
                                item_id = item['id']
                                item_name = item['name']
                                is_registered = item_id in existing_item_ids
                                
                                # 各構成品の行
                                col_check, col_name, col_qty = st.columns([1, 4, 2])
                                
                                with col_check:
                                    # チェックボックス
                                    checked = st.checkbox(
                                        "選択",
                                        key=f"bulk_check_{selected_type_id}_{item_id}",
                                        label_visibility="collapsed"
                                    )
                                
                                with col_name:
                                    # 構成品名（登録済みの場合はマーク付き）
                                    if is_registered:
                                        st.markdown(f"✅ **{item_name}** (登録済み)")
                                    else:
                                        st.markdown(f"⬜ {item_name}")
                                
                                with col_qty:
                                    # 数量入力（チェックされている場合のみ有効）
                                    qty = st.number_input(
                                        "数量",
                                        min_value=1,
                                        value=1,
                                        key=f"bulk_qty_{selected_type_id}_{item_id}",
                                        label_visibility="collapsed",
                                        disabled=not checked
                                    )
                                
                                # 選択状態を保存
                                if checked:
                                    st.session_state.bulk_add_selections[item_id] = {
                                        'name': item_name,
                                        'qty': qty
                                    }
                                elif item_id in st.session_state.bulk_add_selections:
                                    del st.session_state.bulk_add_selections[item_id]
                        
                        # 選択件数の表示と一括登録ボタン
                        selected_count = sum(
                            1 for item in all_items 
                            if st.session_state.get(f"bulk_check_{selected_type_id}_{item['id']}", False)
                        )
                        
                        st.divider()
                        col_info, col_btn = st.columns([2, 1])
                        with col_info:
                            st.info(f"選択中: **{selected_count}件**")
                        
                        with col_btn:
                            if st.button("一括登録", type="primary", disabled=selected_count == 0):
                                # 選択された構成品を一括登録
                                registered_count = 0
                                for item in all_items:
                                    item_id = item['id']
                                    if st.session_state.get(f"bulk_check_{selected_type_id}_{item_id}", False):
                                        qty = st.session_state.get(f"bulk_qty_{selected_type_id}_{item_id}", 1)
                                        add_template_line(selected_type_id, item_id, qty)
                                        registered_count += 1
                                
                                # 選択状態をクリア
                                st.session_state.bulk_add_selections = {}
                                st.cache_data.clear()
                                st.success(f"{registered_count}件の構成品を登録しました")
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
            # 検索ボックスの追加
            search_query = st.text_input("🔍 構成品を検索", key="search_item_master")

            # Reduce spacing between items
            st.markdown("""
                <style>
                [data-testid="stExpander"] {
                    margin-bottom: -1rem; 
                }
                </style>
            """, unsafe_allow_html=True)
            items = get_all_items()
            # "汚れチェック"はマスタ画面から非表示（返却時チェックには使用するためDBには残す）
            # 検索キーワードでフィルタリング
            items = [
                i for i in items 
                if i.get('name') != '汚れチェック'
                and (search_query in i.get('name', '') if search_query else True)
            ]
            
            if not items:
                st.info("該当する構成品はありません")
            
            for i in items:
                # Defensive coding: missing keys protection
                item_id = i.get('id')
                if not item_id:
                    continue

                item_name = i.get('name', '（名称不明）')
                item_tips = i.get('tips', '')

                with st.expander(f"{item_name}"):
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
                    c_txt.write(item_tips)
                    
                    st.divider()
                    st.caption("編集 / 削除")
                    with st.form(f"edit_item_{item_id}"):
                        new_name = st.text_input("構成品名", value=item_name)
                        new_tips = st.text_area("Tips", value=item_tips)
                        new_file = st.file_uploader("写真更新", key=f"file_{item_id}")
                        
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
