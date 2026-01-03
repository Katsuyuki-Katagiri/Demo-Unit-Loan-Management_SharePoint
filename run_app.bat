@echo off
chcp 65001
echo アプリケーションを起動しています...
".venv\Scripts\python.exe" -m streamlit run app.py
pause
