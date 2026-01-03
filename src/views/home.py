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
        unit = get_device_unit_by_id(unit_id)
        type_info = get_device_type_by_id(unit['device_type_id'])
        
        st.title(f"{type_info['name']} (Lot: {unit['lot_number']})")
        st.info(f"保管場所: {unit['location']} | Status: {unit['status']}")
        
        st.subheader("構成品チェックリスト")
        checklist = get_synthesized_checklist(unit['device_type_id'], unit['id'])
        
        if not checklist:
            st.warning("構成品が定義されていません")
        else:
            for item in checklist:
                with st.container(border=True):
                   c1, c2 = st.columns([1, 4])
                   with c1:
                       if item['photo_path']:
                           # TODO: logic.py needs to fetch photo_path for overrides too if possible.
                           # Currently basic items have it.
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
