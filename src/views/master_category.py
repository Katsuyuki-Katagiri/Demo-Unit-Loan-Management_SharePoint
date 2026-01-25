import streamlit as st
from src.database import (
    get_all_categories, update_category_visibility, create_category, 
    update_category_name, delete_category, update_category_basic_info,
    move_category_order, get_all_departments, update_category_managing_department
)

def render_category_settings_tab():
    st.header("カテゴリ表示設定")
    st.caption("ホーム画面に表示する装置カテゴリのON/OFF、名称変更、管理部署設定、追加・削除が行えます。")
    
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
    
    if cats:
        for cat in cats:
            # Default is_visible=1 if None
            is_vis = bool(cat['is_visible']) if 'is_visible' in cat.keys() and cat['is_visible'] is not None else True
            
            with st.container(border=True):
                # Adjusted columns: Name(3), Up(0.5), Down(0.5), UpdateBtn(1), Visible(1), Delete(0.5)
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

                # Description
                current_desc = cat.get('description', "") or ""
                new_desc_input = st.text_area("補足説明", value=current_desc, key=f"cat_desc_{cat['id']}", height=68, placeholder="補足説明を入力...")

                # 3. Update Button
                if row1_c4.button("更新", key=f"upd_cat_{cat['id']}", help="保存"):
                    if new_name_input:
                        current_sort = cat.get('sort_order', 0)
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
                
                # 6. Managing Department
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
