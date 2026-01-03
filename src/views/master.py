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
    st.title("マスター管理")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "機種 (Device Types)", 
        "構成品 (Items)", 
        "テンプレート (Templates)", 
        "ロット/個体 (Units)", 
        "個体差分 (Overrides)"
    ])
    
    # --- Tab 1: Device Types ---
    with tab1:
        st.header("機種登録")
        
        # Form to add device type
        with st.form("add_type_form"):
            cats = get_all_categories()
            cat_options = {c['name']: c['id'] for c in cats}
            selected_cat = st.selectbox("大分類", options=list(cat_options.keys()))
            type_name = st.text_input("機種名")
            submitted = st.form_submit_button("登録")
            
            if submitted and type_name:
                create_device_type(cat_options[selected_cat], type_name)
                st.success(f"機種 '{type_name}' を登録しました")
        
        st.divider()
        st.subheader("機種一覧")
        # Filterable list
        filter_cat = st.selectbox("大分類で絞り込み", ["全て"] + list(cat_options.keys()))
        
        if filter_cat == "全て":
            types = get_device_types()
        else:
            types = get_device_types(cat_options[filter_cat])
            
        for t in types:
            st.text(f"ID: {t['id']} | {t['name']}")

    # --- Tab 2: Items ---
    with tab2:
        st.header("構成品登録")
        with st.form("add_item_form"):
            item_name = st.text_input("構成品名")
            item_tips = st.text_area("確認ポイント/Tips (任意)")
            uploaded_file = st.file_uploader("写真 (任意)", type=['png', 'jpg', 'jpeg'])
            
            submitted_item = st.form_submit_button("登録")
            
            if submitted_item and item_name:
                photo_path = ""
                if uploaded_file is not None:
                    # Save file
                    file_ext = os.path.splitext(uploaded_file.name)[1]
                    # Simple filename strategy: item_name_timestamp or just random to avoid conflict?
                    # For simplicity: item_name based, but handle duplicate later?
                    # Let's use name + simple hash or just original name if unique enough manually managed.
                    save_name = f"{uploaded_file.name}"
                    save_path = os.path.join(UPLOAD_DIR, save_name)
                    with open(save_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    photo_path = save_name
                
                create_item(item_name, item_tips, photo_path)
                st.success(f"構成品 '{item_name}' を登録しました")

        st.divider()
        st.subheader("構成品一覧")
        items = get_all_items()
        for i in items:
            col1, col2 = st.columns([1, 4])
            with col1:
                if i['photo_path']:
                    full_path = os.path.join(UPLOAD_DIR, i['photo_path'])
                    if os.path.exists(full_path):
                        st.image(full_path, use_container_width=True)
                    else:
                        st.write("No Image")
                else:
                    st.write("No Image")
            with col2:
                st.markdown(f"**{i['name']}**")
                st.write(i['tips'])

    # --- Tab 3: Templates ---
    with tab3:
        st.header("テンプレート編集")
        st.info("機種ごとの標準構成品（チェックリストのベース）を定義します")
        
        # Select Device Type
        all_types = get_device_types()
        type_opts = {f"{t['name']} (ID:{t['id']})": t['id'] for t in all_types}
        sel_type_key = st.selectbox("機種を選択", options=list(type_opts.keys()))
        
        if sel_type_key:
            sel_type_id = type_opts[sel_type_key]
            
            # Show existing
            st.subheader("現在の構成")
            current_lines = get_template_lines(sel_type_id)
            if current_lines:
                for line in current_lines:
                    st.write(f"- {line['item_name']} (必要数: {line['required_qty']})")
            else:
                st.write("まだ構成品が登録されていません")
            
            # Add Line Form
            st.subheader("構成品を追加/更新")
            with st.form("add_template_line"):
                all_items = get_all_items()
                item_opts = {f"{i['name']}": i['id'] for i in all_items}
                sel_item_key = st.selectbox("構成品", options=list(item_opts.keys()))
                req_qty = st.number_input("必要数量", min_value=1, value=1)
                
                sub_tpl = st.form_submit_button("追加/更新")
                if sub_tpl and sel_item_key:
                    add_template_line(sel_type_id, item_opts[sel_item_key], req_qty)
                    st.success("更新しました")
                    st.rerun()

    # --- Tab 4: Units ---
    with tab4:
        st.header("ロット/個体登録")
        # Select Device Type
        sel_type_key_unit = st.selectbox("機種を選択", options=list(type_opts.keys()), key="unit_type_sel")
        
        if sel_type_key_unit:
            sel_type_id_unit = type_opts[sel_type_key_unit]
            
            with st.form("add_unit_form"):
                lot_num = st.text_input("ロット番号/管理ID (必須)")
                mfg = st.text_input("製造年月日 (任意)")
                loc = st.text_input("保管場所 (任意)")
                
                sub_unit = st.form_submit_button("登録")
                if sub_unit and lot_num:
                    if create_device_unit(sel_type_id_unit, lot_num, mfg, loc):
                        st.success(f"ロット {lot_num} を登録しました")
                    else:
                        st.error("登録失敗 (ロット番号が重複している可能性があります)")
            
            st.subheader("登録済みロット一覧")
            units = get_device_units(sel_type_id_unit)
            for u in units:
                st.write(f"Lot: {u['lot_number']} | Status: {u['status']}")

    # --- Tab 5: Overrides ---
    with tab5:
        st.header("個体差分設定")
        st.info("特定のロットだけ構成品が異なる場合（欠品や備品追加）に設定します")
        
        # 1. Select Type
        sel_type_key_ov = st.selectbox("機種を選択", options=list(type_opts.keys()), key="ov_type_sel")
        
        if sel_type_key_ov:
            sel_type_id_ov = type_opts[sel_type_key_ov]
            
            # 2. Select Unit
            units_ov = get_device_units(sel_type_id_ov)
            if not units_ov:
                st.warning("この機種にはロットが登録されていません")
            else:
                unit_opts = {f"Lot: {u['lot_number']}": u['id'] for u in units_ov}
                sel_unit_key = st.selectbox("ロットを選択", options=list(unit_opts.keys()))
                
                if sel_unit_key:
                    sel_unit_id = unit_opts[sel_unit_key]
                    
                    st.subheader("設定済みの差分")
                    overrides = get_unit_overrides(sel_unit_id)
                    if overrides:
                        for ov in overrides:
                            st.write(f"- {ov['item_name']}: {ov['action']} (Qty: {ov['qty']})")
                    else:
                        st.write("差分はありません")
                        
                    st.divider()
                    st.subheader("差分を追加")
                    with st.form("add_override_form"):
                        all_items_ov = get_all_items()
                        item_opts_ov = {f"{i['name']}": i['id'] for i in all_items_ov}
                        sel_item_key_ov = st.selectbox("構成品", options=list(item_opts_ov.keys()), key="ov_item")
                        
                        action = st.radio("アクション", ["add", "remove", "qty"])
                        qty_ov = st.number_input("数量 (remove時は無視されます)", min_value=0, value=1)
                        
                        sub_ov = st.form_submit_button("設定")
                        if sub_ov and sel_item_key_ov:
                            add_unit_override(sel_unit_id, item_opts_ov[sel_item_key_ov], action, qty_ov)
                            st.success("差分を設定しました")
                            st.rerun()
