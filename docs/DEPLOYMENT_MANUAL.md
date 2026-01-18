# デモ機管理アプリ　クラウド運用マニュアル

## 概要

このマニュアルでは、デモ機管理アプリをStreamlit Cloudにデプロイし、Supabaseを活用してデータを永続化する方法を説明します。

---

## 1. 現在の構成

| 項目 | サービス | 状態 |
|---|---|---|
| アプリホスティング | Streamlit Community Cloud | ✅ 完了 |
| コード管理 | GitHub (Public) | ✅ 完了 |
| データベース | SQLite (メモリ) | ⚠️ 再起動でリセット |
| 画像ストレージ | ローカル | ⚠️ 再起動でリセット |

**アプリURL**: https://demo-unit-loan-management-ityndraxwiq2jviprv6ibh.streamlit.app/

---

## 2. アカウント情報

### GitHub
- **リポジトリ**: https://github.com/Katsuyuki-Katagiri/Demo-Unit-Loan-Management
- **ブランチ**: main
- **公開設定**: Public

### Supabase（将来のデータ永続化用）
- **Project URL**: `https://bccygvkzvwgkzasbyfqh.supabase.co`
- **Storageバケット**: `uploads`
- **Region**: Northeast Asia (Tokyo)

> ⚠️ **機密情報**（service_role キー、DBパスワード）は別途安全に保管してください。

---

## 3. デプロイ手順（再デプロイ時）

### 3.1 コード変更後の更新

1. ローカルでコードを変更
2. 以下のコマンドでGitHubにプッシュ:
```bash
cd "c:\Users\k.katagiri\OneDrive - 泉工医科工業　株式会社　\ドキュメント 1\Antigravity\Demo-Unit-Loan-Management"
git add .
git commit -m "変更内容の説明"
git push origin main
```
3. Streamlit Cloudが自動的に再デプロイ（数分待つ）

### 3.2 手動再デプロイ

1. https://share.streamlit.io にアクセス
2. アプリを選択
3. 右上の「⋮」メニュー → 「Reboot app」

---

## 4. 運用上の注意点

### 4.1 データのリセット

現在、以下のタイミングでデータがリセットされます:
- アプリの再デプロイ時
- アプリのリブート時
- 長時間アクセスがなくスリープ後に再起動した時

### 4.2 スリープについて

- 約15分間アクセスがないとアプリがスリープ
- 次回アクセス時に自動で起動（10〜30秒かかる場合あり）

---

## 5. Supabase移行ガイド（データ永続化）

### 5.1 移行のメリット

- データが永続化され、再起動後も保持
- 画像もクラウドストレージに保存
- 複数ユーザーの同時アクセスに対応

### 5.2 移行手順（概要）

1. **Supabaseダッシュボード**でデータベーステーブル作成
   - SQL Editorで `supabase_schema.sql` を実行
2. **コード変更**
   - `database.py` をPostgreSQL対応に変更
   - 画像アップロード処理をSupabase Storage対応に変更
3. **Streamlit Secrets設定**
   - Streamlit Cloud の「Settings」→「Secrets」に接続情報を設定
4. **再デプロイ**

### 5.3 Streamlit Secrets設定例

```toml
[supabase]
url = "https://bccygvkzvwgkzasbyfqh.supabase.co"
key = "eyJhbGciOiJIUzI1NiIs..."  # service_role キー
db_url = "postgresql://postgres:PASSWORD@db.bccygvkzvwgkzasbyfqh.supabase.co:5432/postgres"
```

---

## 6. トラブルシューティング

### 6.1 アプリが表示されない

1. https://share.streamlit.io でアプリの状態を確認
2. 「Logs」でエラーを確認
3. 必要に応じて「Reboot app」

### 6.2 デプロイに失敗する

1. GitHubリポジトリがPublicか確認
2. `requirements.txt` に必要なライブラリが記載されているか確認
3. `app.py` が正しいパスにあるか確認

### 6.3 ログインできない

- 初回起動時はデフォルトアカウントで作成されます
- 再起動後はデータがリセットされるため、再度アカウント登録が必要

---

## 7. 関連リンク

- **Streamlit Cloud**: https://share.streamlit.io
- **GitHub リポジトリ**: https://github.com/Katsuyuki-Katagiri/Demo-Unit-Loan-Management
- **Supabase**: https://supabase.com
- **アプリURL**: https://demo-unit-loan-management-ityndraxwiq2jviprv6ibh.streamlit.app/

---

## 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-01-18 | 初版作成、Streamlit Cloudデプロイ完了 |
