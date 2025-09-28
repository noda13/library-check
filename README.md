# 図書館予約状況自動取得ツール

## 概要
札幌市図書館の予約状況を自動で取得し、HTMLで一覧表示するPythonスクリプトです。GitHub Actionsで日次実行し、最新の予約状況を `docs/index.html` に出力します。

## 機能
- Seleniumによる自動ログイン・予約情報取得
- 予約情報をテーブル形式でHTML出力
- 「ご用意できました」やタイトル重複はハイライト表示
- 複数ユーザー対応
- GitHub Actionsで毎日自動実行

## 使い方
### 1. 必要なファイル
- `library_checker.py` : メインスクリプト
- `config.ini` : 認証情報（ユーザー名・パスワード）
- `.github/workflows/daily-library-check.yml` : 日次実行用ワークフロー

### 2. Python環境
- Python 3.11 以上推奨
- venv（仮想環境）推奨

### 3. 依存パッケージ
- selenium
- webdriver-manager
- beautifulsoup4

### 4. 認証情報の管理
`config.ini` は以下の形式です。
```
[user_1]
username = あなたのID
password = あなたのパスワード

[user_2]
username = ...
password = ...
```

#### GitHub Actionsでの安全な管理方法
1. 各ユーザーのID・パスワードをGitHubリポジトリの「Settings」→「Secrets and variables」→「Actions」で登録します。
   - 例: `LIBRARY_USER_1_USERNAME`, `LIBRARY_USER_1_PASSWORD` など
2. ワークフロー内でSecretsから `config.ini` を自動生成します。

### 5. 実行方法
#### セットアップ
```bash
python -m venv .venv
source .venv/bin/activate
pip install selenium webdriver-manager beautifulsoup4
```

#### ローカル実行
```bash
source .venv/bin/activate
python library_checker.py
deactivate
```

#### GitHub Actionsによる自動実行
- `.github/workflows/daily-library-check.yml` が毎日自動で実行されます。
- 実行結果は `docs/index.html` に出力され、アーティファクトとしてダウンロード可能です。

## 出力例
- `docs/index.html` に全ユーザーの予約状況がテーブルで表示されます。
- 「ご用意できました」やタイトル重複は黄色でハイライトされます。

## 注意事項
- 認証情報は絶対にGitHubリポジトリに直接コミットしないでください。
- Secretsの管理・設定はリポジトリ管理者のみが行ってください。

## ライセンス
MIT License
