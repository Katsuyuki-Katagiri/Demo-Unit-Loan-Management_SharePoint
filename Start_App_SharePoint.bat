@echo off
REM ====================================================
REM  デモ機管理アプリ起動スクリプト (SharePoint同期版)
REM ====================================================
REM 
REM  このスクリプトは SharePoint 同期フォルダにデータを保存する
REM  構成で使用します。
REM
REM  [使用方法]
REM  1. 下記のパスを実際の環境に合わせて修正してください
REM  2. このバッチファイルをダブルクリックして起動
REM
REM ====================================================

REM --- 環境変数設定 ---
REM SharePoint同期フォルダ内のデータベースパス
set DEMO_LOAN_DB_PATH=C:\Users\k.katagiri\OneDrive - 泉工医科工業　株式会社　\DemoLoandata\app.db

REM 写真保存フォルダのパス
set DEMO_LOAN_UPLOAD_DIR=C:\Users\k.katagiri\OneDrive - 泉工医科工業　株式会社　\DemoLoandata\uploads

REM --- アプリ起動 ---
echo ====================================================
echo   デモ機管理アプリを起動しています...
echo ====================================================
echo.
echo データベース: %DEMO_LOAN_DB_PATH%
echo 写真フォルダ: %DEMO_LOAN_UPLOAD_DIR%
echo.

REM データフォルダが存在しない場合は作成
if not exist "%DEMO_LOAN_UPLOAD_DIR%" mkdir "%DEMO_LOAN_UPLOAD_DIR%"

REM Streamlit起動
streamlit run app.py

pause
