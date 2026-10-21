"""
Gmail メール送信プログラム（課題：Gmail API）

Gmail API を使い、.env に書いた宛先（特定の宛先）に、自分の Gmail からメールを送る。
件名と本文は、実行するたびにターミナルで入力する。

使い方：ターミナルで  python main.py  を実行する。
"""

import base64
import os
import re
import sys
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv
from google.auth.exceptions import RefreshError, TransportError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ============================================================
# 設定（ここをまとめて書いておく）
# ============================================================

# このプログラム（main.py）が置いてあるフォルダ
BASE_DIR = Path(__file__).resolve().parent

# OAuth クライアントの鍵（Google Cloud Console からダウンロードしたもの）
CREDENTIALS_FILE = BASE_DIR / "credentials.json"

# 初回ログインで自動で作られる許可証
TOKEN_FILE = BASE_DIR / "token.json"

# 宛先を書いておくファイルと、その中の項目名
ENV_FILE = BASE_DIR / ".env"
ENV_EXAMPLE_FILE = BASE_DIR / ".env.example"
RECIPIENT_KEY = "RECIPIENT"

# プログラムに許可する範囲。gmail.send は「メールを送ることだけ」できる（受信箱は読めない）
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

# メールアドレスの形（xxx@yyy.zz）かどうかを、ざっくり確かめるための決まり
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# 送信前の確認画面の区切り線
SEPARATOR = "-" * 30


# ============================================================
# F1 宛先の読み込み
# ============================================================
def load_recipient():
    """
    .env の RECIPIENT から宛先のメールアドレスを読み込んで返す。
    .env が無い・空・メールアドレスの形でない場合は、理由を表示して終了する（F7）。
    """
    # .env の中身を「環境変数」（プログラムが読める設定値）として読み込む
    load_dotenv(ENV_FILE)
    recipient = os.getenv(RECIPIENT_KEY, "").strip()

    if not recipient:
        show_error_and_exit(
            f"宛先が設定されていません。\n"
            f"{ENV_EXAMPLE_FILE.name} をコピーして「{ENV_FILE.name}」という名前にし、\n"
            f"{RECIPIENT_KEY}= の後ろに宛先のメールアドレスを書いてください。\n"
            f"置き場所: {BASE_DIR}"
        )
    if not EMAIL_PATTERN.match(recipient):
        show_error_and_exit(
            f"{ENV_FILE.name} の {RECIPIENT_KEY} がメールアドレスの形になっていません: {recipient}\n"
            f"例: {RECIPIENT_KEY}=someone@example.com のように書き直してください。"
        )
    return recipient


# ============================================================
# F2 ログイン（認証）
# ============================================================
def login():
    """
    Google にログインして、Gmail を操作するための「サービス」を返す。

    1. token.json があれば、それを読み込む
    2. 期限切れで更新できるなら、自動で更新する
    3. token.json が無い・更新できない場合は、ブラウザでログイン画面を開く
    4. 許可されたら、次回のために token.json を保存する
    """
    creds = None

    # token.json があれば読み込む（壊れていたら無視して、ログインからやり直す）
    if TOKEN_FILE.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except ValueError:
            creds = None

    # 期限切れだが更新できる場合は、自動で更新する
    if creds and not creds.valid and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            # 同意画面が「テスト中」だと約7日で更新できなくなる → ログインし直す
            print("ログインの有効期限が切れていたため、もう一度ログインします。")
            creds = None

    # まだ使える許可証が無い場合は、ブラウザでログインする
    if not creds or not creds.valid:
        # credentials.json が無いとログインできないので、理由を表示して終了する（F7）
        if not CREDENTIALS_FILE.exists():
            show_error_and_exit(
                f"{CREDENTIALS_FILE.name} が見つかりません。\n"
                f"Google Cloud Console で OAuth クライアントID（デスクトップアプリ）を作成し、\n"
                f"ダウンロードした JSON を「{CREDENTIALS_FILE.name}」という名前で\n"
                f"次のフォルダに置いてください: {BASE_DIR}"
            )

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
        except ValueError:
            show_error_and_exit(
                f"{CREDENTIALS_FILE.name} の中身が正しくありません。\n"
                "OAuth クライアントID（デスクトップアプリ）の JSON をダウンロードし直してください。"
            )

        # ブラウザが開き、ログインして「許可」を押すと続きに進む
        creds = flow.run_local_server(port=0)

        # 次回からログインしなくていいように、許可証を保存する
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")

    # Gmail を操作するための「サービス」を作って返す
    return build("gmail", "v1", credentials=creds)


# ============================================================
# F3 件名・本文の入力
# ============================================================
def ask_subject():
    """
    件名を入力してもらう。空欄なら、もう一度聞く。
    """
    while True:
        subject = input("件名を入力してください: ").strip()
        if subject:
            return subject
        print("件名が空です。件名を入力してください。")


def ask_body():
    """
    本文を複数行で入力してもらう。
    何も入力せずに Enter を2回続けて押すと、入力の終わりとする。
    （空行1つは段落の区切りとして本文に残す）
    本文が空なら、もう一度聞く。
    """
    while True:
        print("本文を入力してください（何も入力せずに Enter を2回押すと終わり）:")
        lines = []
        while True:
            try:
                line = input()
            except EOFError:
                # 流し込んだ入力が終わった（Ctrl + D）ときも、入力の終わりとする
                break
            # 直前の行も空なら、Enter が2回続いたので終わり
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)

        # 前後の余分な空行を取り除いて、1つの文章にまとめる
        body = "\n".join(lines).strip("\n")
        if body.strip():
            return body
        print("本文が空です。本文を入力してください。")


# ============================================================
# F4 送信前の確認
# ============================================================
def confirm_send(recipient, subject, body):
    """
    宛先・件名・本文を表示し、送信してよいかを y / n で聞く。
    y なら True、n なら False を返す。それ以外の入力なら、もう一度聞く。
    """
    print(SEPARATOR)
    print(f"宛先: {recipient}")
    print(f"件名: {subject}")
    print("本文:")
    print(body)
    print(SEPARATOR)

    while True:
        answer = input("この内容で送信しますか？ (y/n): ").strip().lower()
        if answer == "y":
            return True
        if answer == "n":
            return False
        print("y か n を入力してください。")


# ============================================================
# F5 送信
# ============================================================
def build_message(recipient, subject, body):
    """
    宛先・件名・本文から、Gmail API に渡す形のメールを組み立てる。

    1. EmailMessage で、メールの決まった書き方（MIME）にする。日本語は UTF-8 で入る
    2. それを Base64URL（英数字だけの文字列）に置き換える。Gmail API はこの形で受け取る
    差出人（From）は書かなくても、ログインした自分の Gmail アドレスになる。
    """
    message = EmailMessage()
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    encoded = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
    return {"raw": encoded}


def send_mail(service, message):
    """
    組み立てたメールを Gmail API の users.messages.send で送り、Google からの返事を返す。
    userId の "me" は「ログインしている自分」という意味。
    """
    return service.users().messages().send(userId="me", body=message).execute()


# ============================================================
# F6 結果の表示
# ============================================================
def show_result(sent):
    """
    送信できたことと、Gmail が付けたメッセージIDを表示する。
    """
    print(f"送信しました。（メッセージID: {sent['id']}）")


# ============================================================
# F7 エラー表示
# ============================================================
def show_error_and_exit(message):
    """
    原因が分かる日本語のエラーメッセージを表示して、プログラムを終了する。
    """
    print(f"エラー: {message}", file=sys.stderr)
    sys.exit(1)


def explain_http_error(error):
    """
    Google とのやりとりで起きたエラー（HttpError）を、日本語の説明に直して返す。
    """
    # Gmail API が有効になっていない、または権限が足りない
    if error.status_code == 403:
        return (
            "Gmail を操作する許可がありません。\n"
            "Google Cloud Console の「API とサービス」→「ライブラリ」で\n"
            "「Gmail API」が有効になっているか確認してください。\n"
            f"詳細: {error.reason}"
        )
    # 宛先などの中身が正しくないと言われた
    if error.status_code == 400:
        return (
            "Google にメールを受け付けてもらえませんでした。\n"
            f"{ENV_FILE.name} の {RECIPIENT_KEY}（宛先）が正しいか確認してください。\n"
            f"詳細: {error.reason}"
        )
    return (
        "Gmail とのやりとりに失敗しました。\n"
        f"ステータスコード: {error.status_code}\n"
        f"詳細: {error.reason}"
    )


# ============================================================
# メインの処理（上の関数を順番に呼ぶ）
# ============================================================
def main():
    """
    プログラム全体の流れ：
    宛先の読み込み → ログイン → 件名・本文の入力 → 送信前の確認 → 送信 → 結果の表示
    """
    try:
        # F1 宛先の読み込み（ログインより先に確かめる）
        recipient = load_recipient()

        # F2 ログイン
        service = login()

        # F3 件名・本文の入力
        print(f"宛先: {recipient}（{ENV_FILE.name} で設定）")
        subject = ask_subject()
        body = ask_body()

        # F4 送信前の確認（n ならここで終わる）
        if not confirm_send(recipient, subject, body):
            print("送信をやめました。")
            return

        # F5 送信
        sent = send_mail(service, build_message(recipient, subject, body))

        # F6 結果の表示
        show_result(sent)

    except HttpError as error:
        # Google とのやりとりで失敗した（F7）
        show_error_and_exit(explain_http_error(error))
    except (TransportError, OSError) as error:
        # インターネットにつながらない など（F7）
        show_error_and_exit(
            "Google につながりませんでした。インターネット接続を確認してください。\n"
            f"詳細: {error}"
        )
    except (KeyboardInterrupt, EOFError):
        # Ctrl + C で途中でやめた場合（入力中・ログインの待ち中など）
        print("\n中断しました。（メールは送信していません）")
        sys.exit(1)


# このファイルを直接実行したときだけ main() を動かす
if __name__ == "__main__":
    main()
