try:
    import bcrypt
    print("bcrypt: OK")
except ImportError as e:
    print(f"bcrypt: Missing ({e})")

try:
    import streamlit
    print("streamlit: OK")
except ImportError as e:
    print(f"streamlit: Missing ({e})")

import sqlite3
print("sqlite3: OK")
