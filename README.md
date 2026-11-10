# gmail-sender

Gmail API を使って、あらかじめ決めておいた宛先に、自分の Gmail からメールを送る Python プログラムです。
件名と本文は実行するたびにターミナルで入力し、送信前に内容を確認してから送ります。

## 何をするものか

1. `.env` に書いた宛先を読み込む
2. 自分の Google アカウントでログインする（初回だけブラウザが開きます）
3. 件名と本文を入力する
4. 宛先・件名・本文を表示し、`y` を入力すると送信する
5. 「送信しました」とメッセージID（Gmail がメールに付ける番号）を表示する

```
宛先: someone@example.com（.env で設定）
件名を入力してください: 明日の打ち合わせ
本文を入力してください（何も入力せずに Enter を2回押すと終わり）:
明日10時からお願いします。


------------------------------
宛先: someone@example.com
件名: 明日の打ち合わせ
本文:
明日10時からお願いします。
------------------------------
この内容で送信しますか？ (y/n): y
送信しました。（メッセージID: 18f...）
```

## 使う技術

- Python 3（python-dotenv）
- Gmail API（メールを送る）
- Google Cloud（OAuth 2.0 でログイン。google-api-python-client・google-auth-oauthlib）

## 事前準備

### 1. ライブラリのインストール

```bash
pip install google-api-python-client google-auth google-auth-oauthlib python-dotenv
```

### 2. Google Cloud Console の設定

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを選ぶ（なければ作る）
2. 「API とサービス」→「ライブラリ」で **Gmail API** を検索して「有効にする」
3. OAuth 同意画面を設定する（対象：外部、テストユーザーに自分の Gmail アドレスを追加）

## 秘密ファイルの用意の仕方

次のファイルは GitHub に載せていません（`.gitignore` で除外）。自分で用意してください。

| ファイル | 中身 | 用意の仕方 |
|---|---|---|
| `credentials.json` | OAuth クライアントの鍵 | Google Cloud Console の「API とサービス」→「認証情報」→「認証情報を作成」→「OAuth クライアントID」（種類：**デスクトップアプリ**）で作り、JSON をダウンロードして `credentials.json` という名前で `main.py` と同じフォルダに置く |
| `.env` | 宛先のメールアドレス | `.env.example` をコピーして `.env` という名前にし、`RECIPIENT=` の後ろに宛先を書く |
| `token.json` | ログインの許可証 | 初回の実行でログインすると自動で作られる |

`.env` の例：

```
RECIPIENT=someone@example.com
```

## 使い方

```bash
python main.py
```

- 初回はブラウザでログイン画面が開きます。「このアプリは Google で確認されていません」と出たら「続行」を押してください（自分で作ったテスト中のアプリのため）
- 本文は複数行で書けます。何も入力せずに Enter を2回続けて押すと、入力の終わりです
- 送信前の確認で `n` を入力すると、送らずに終了します
- 途中でやめたいときは Ctrl + C を押してください

## 安全のための工夫

- プログラムに許可する範囲（スコープ）は `gmail.send`（メールを送ることだけ）です。受信箱のメールは読めません
- メールは取り消せないので、送る前に必ず内容を表示して確認します
- 宛先のメールアドレスはコードに書かず、GitHub に載せない `.env` に書きます

## うまくいかないとき

| 表示 | 対処 |
|---|---|
| 宛先が設定されていません | `.env` を作り、`RECIPIENT=` の後ろに宛先を書く |
| credentials.json が見つかりません | 上の「秘密ファイルの用意の仕方」で `credentials.json` を置く |
| Gmail を操作する許可がありません | Google Cloud Console で Gmail API を有効にする |
| ログインの有効期限が切れていたため… | そのままブラウザでログインし直す（テスト中のアプリは約7日でログインが切れます） |

詳しい仕様は [要件定義書.md](要件定義書.md) を見てください。
