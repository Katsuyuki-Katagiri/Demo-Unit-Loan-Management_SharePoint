@echo off
chcp 65001
echo 依存ライブラリをインストールしています...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo インストールに失敗しました。
    pause
    exit /b %errorlevel%
)
echo インストール完了。
pause
