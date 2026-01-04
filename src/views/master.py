import streamlit as st
import os
import shutil
from src.database import (
    get_all_categories, create_device_type, get_device_types,
    create_item, get_all_items, add_template_line, get_template_lines,
    create_device_unit, get_device_units, add_unit_override, 
    get_unit_overrides, UPLOAD_DIR
)


def render_master_view():
    st.title("マスタ管理 (Master Management)")
    
    # Main Tabs
    main_tab1, main_tab2 = st.tabs([
        "機種管理 (Device Management)", 
        "構成品マスタ (Item Master)"
    ])
    
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
                    selected_cat = st.selectbox("大分類", options=list(cat_options.keys()))
                    type_name = st.text_input("機種名")
                    if st.form_submit_button("登録"):
                        if type_name:
                            create_device_type(cat_options[selected_cat], type_name)
                            st.success(f"登録しました: {type_name}")
                            st.rerun()

            # Select Existing
            st.markdown("### 機種を選択")
            filter_cat = st.selectbox("大分類フィルター", ["全て"] + list(cat_options.keys()))
            
            if filter_cat == "全て":
                types = get_device_types()
            else:
                types = get_device_types(cat_options[filter_cat])
            
            type_opts = {f"{t['name']} (ID:{t['id']})": t['id'] for t in types}
            selected_type_key = st.radio("編集する機種を選んでください", options=list(type_opts.keys()))

        with col2:
            if selected_type_key:
                selected_type_id = type_opts[selected_type_key]
                st.subheader(f"編集: {selected_type_key}")
                st.divider()
                
                # --- Section 1: Template ---
                st.markdown("#### ① 標準構成 (Template)")
                st.caption("この機種の標準的な付属品（チェックリスト）を定義します。")
                
                # Current Template
                current_lines = get_template_lines(selected_type_id)
                if current_lines:
                    st.markdown("**現在の構成:**")
                    for line in current_lines:
                        st.text(f"・ {line['item_name']} (必要数: {line['required_qty']})")
                else:
                    st.info("構成品が登録されていません。")
                
                with st.expander("構成品を追加/編集"):
                    with st.form("add_tpl_line"):
                        all_items = get_all_items()
                        item_opts = {f"{i['name']}": i['id'] for i in all_items}
                        sel_item_key = st.selectbox("構成品を選択", options=list(item_opts.keys()))
                        req_qty = st.number_input("必要数量", min_value=1, value=1)
                        if st.form_submit_button("追加/更新"):
                            add_template_line(selected_type_id, item_opts[sel_item_key], req_qty)
                            st.success("更新しました")
                            st.rerun()

                st.divider()

                # --- Section 2: Units ---
                st.markdown("#### ② ロット一覧 (Units)")
                st.caption("この機種の実機（ロット）を管理します。")
                
                # List Units
                units = get_device_units(selected_type_id)
                if units:
                    st.dataframe(
                        [{"ID": u['id'], "Lot": u['lot_number'], "Status": u['status'], "Location": u['location']} for u in units],
                        use_container_width=True
                    )
                else:
                    st.info("登録済みのロットはありません。")
                
                with st.expander("新規ロット登録"):
                    with st.form("add_unit_quick"):
                        c1, c2 = st.columns(2)
                        lot_num = c1.text_input("ロット番号 (必須)")
                        loc = c2.text_input("保管場所")
                        mfg = st.text_input("製造年月日")
                        if st.form_submit_button("登録"):
                            if lot_num:
                                if create_device_unit(selected_type_id, lot_num, mfg, loc):
                                    st.success(f"登録しました: {lot_num}")
                                    st.rerun()
                                else:
                                    st.error("登録失敗 (重複など)")



    # --- Tab 2: Item Master ---
    with main_tab2:
        st.header("構成品マスタ登録")
        st.caption("ケーブルやマニュアルなど、構成品のパーツを登録します。")
        
        col_i1, col_i2 = st.columns([1, 2])
        with col_i1:
            with st.form("add_item_global"):
                item_name = st.text_input("構成品名")
                item_tips = st.text_area("確認時のTips")
                uploaded_file = st.file_uploader("写真", type=['png', 'jpg', 'jpeg'])
                if st.form_submit_button("登録"):
                    if item_name:
                        photo_path = ""
                        if uploaded_file:
                            save_name = uploaded_file.name
                            save_path = os.path.join(UPLOAD_DIR, save_name)
                            with open(save_path, "wb") as f:
                                f.write(uploaded_file.getbuffer())
                            photo_path = save_name
                        create_item(item_name, item_tips, photo_path)
                        st.success(f"登録しました: {item_name}")
                        st.rerun()

        with col_i2:
            st.subheader("登録済み構成品一覧")
            items = get_all_items()
            for i in items:
                with st.expander(f"{i['name']}"):
                    c_img, c_txt = st.columns([1, 2])
                    if i['photo_path']:
                        fp = os.path.join(UPLOAD_DIR, i['photo_path'])
                        if os.path.exists(fp):
                            c_img.image(fp)
                    c_txt.write(i['tips'])
