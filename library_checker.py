#!/usr/bin/env python
# -*- coding: utf-8 -*-

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, UnexpectedAlertPresentException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import os
import configparser
import datetime

# --- 設定 ---
CONFIG_FILE = "config.ini"
OUTPUT_DIR = "docs"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "index.html")

LOGIN_URL = "https://www.library.city.sapporo.jp/licsxp-opac/WOpacMnuTopInitAction.do?WebLinkFlag=1&moveToGamenId=mylibrary"

def load_credentials(config_file):
    """設定ファイルから認証情報を読み込む"""
    config = configparser.ConfigParser()
    config.read(config_file)

    credentials = []
    for section in config.sections():
        username = config.get(section, 'username', fallback=None)
        password = config.get(section, 'password', fallback=None)
        if username and password:
            credentials.append({"username": username, "password": password})
    return credentials

def generate_html(all_books_data):
    """予約状況のHTMLを生成する"""
    html_content = """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>図書館予約状況</title>
        <style>
            body { font-family: sans-serif; margin: 2em; }
            h1, h2 { color: #333; }
            .user-section { margin-bottom: 2em; }
            .book { border: 1px solid #ddd; padding: 1em; margin-bottom: 1em; border-radius: 5px; }
            .book p { margin: 0.5em 0; }
            .highlight { background-color: #fff3cd; }
            .timestamp { color: #777; font-size: 0.9em; }
        </style>
    </head>
    <body>
        <h1>図書館予約状況</h1>
    """

    for user, data in all_books_data.items():
        html_content += f'<div class="user-section"><h2>{user}さんの予約状況</h2>'
        if data["error"]:
            html_content += f'<p class="error">エラー: {data["error"]}</p>'
        elif not data["books"]:
            html_content += "<p>現在、予約している資料はありません。</p>"
        else:
            for book in data["books"]:
                highlight_class = "highlight" if book.get('予約状態', '') != '予約中です' else ''
                html_content += f"""
                <div class="book {highlight_class}">
                    <p><strong>{book.get('資料名', 'N/A')}</strong></p>
                    <p>状態: {book.get('予約状態', 'N/A')} (順位: {book.get('順位', 'N/A')})</p>
                    <p>期限: {book.get('取置期限', 'N/A')} | 受取館: {book.get('受取館', 'N/A')}</p>
                </div>
                """
        html_content += "</div>"

    html_content += f'<p class="timestamp">最終更新: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>'
    html_content += """
    </body>
    </html>
    """
    return html_content

def main():
    """メインの処理"""
    USER_CREDENTIALS = load_credentials(CONFIG_FILE)
    all_books_data = {}

    if not USER_CREDENTIALS:
        print(f"エラー: {CONFIG_FILE} から認証情報を読み込めませんでした。")
        return

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    for cred in USER_CREDENTIALS:
        username = cred["username"]
        password = cred["password"]
        all_books_data[username] = {"books": [], "error": None}

        print(f"--- {username}さんの予約状況を確認します ---")

        try:
            driver.get(LOGIN_URL)
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.NAME, "username"))).send_keys(username)
            driver.find_element(By.NAME, "j_password").send_keys(password)
            driver.execute_script("login();")

            try:
                alert = WebDriverWait(driver, 5).until(EC.alert_is_present())
                alert_text = alert.text
                print(f"ログイン時にアラートが表示されました: {alert_text}")
                alert.accept()
            except TimeoutException:
                pass

            WebDriverWait(driver, 20).until(EC.title_contains("マイ図書館：蔵書検索システム"))
            reserve_link = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, "stat-resv")))
            reserve_link.click()
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "ItemDetaTable")))

            soup = BeautifulSoup(driver.page_source, "html.parser")
            table = soup.find("table", {"id": "ItemDetaTable"})

            if table:
                rows = table.find("tbody").find_all("tr")
                if not rows or (len(rows) == 1 and "該当する資料はありません" in rows[0].text):
                    print("現在、予約している資料はありません。")
                else:
                    books = []
                    for row in rows:
                        if "space" in row.get("class", []):
                            continue
                        book_info = {
                            'No.': row.find('th', scope='row').get_text(strip=True),
                            '資料名': row.find('td', id=lambda x: x and x.startswith('ItemDeta0105b')).find('a').get_text(strip=True) if row.find('td', id=lambda x: x and x.startswith('ItemDeta0105b')) else '',
                            '書誌種別': row.find('td', id=lambda x: x and x.startswith('ItemDeta0105c')).get_text(strip=True) if row.find('td', id=lambda x: x and x.startswith('ItemDeta0105c')) else '',
                            '受取館': row.find('td', id=lambda x: x and x.startswith('ItemDeta0105d')).get_text(strip=True) if row.find('td', id=lambda x: x and x.startswith('ItemDeta0105d')) else '',
                            '予約日': row.find('td', class_='a-center small').get_text(separator=" ", strip=True).replace("ー", "").strip() if row.find('td', class_='a-center small') else '',
                            '順位': row.find('td', id=lambda x: x and x.startswith('ItemDeta0105h')).get_text(strip=True) if row.find('td', id=lambda x: x and x.startswith('ItemDeta0105h')) else '',
                            '予約状態': row.find('td', id=lambda x: x and x.startswith('ItemDeta0105i')).get_text(strip=True) if row.find('td', id=lambda x: x and x.startswith('ItemDeta0105i')) else '',
                            '取置期限': row.find('td', id=lambda x: x and x.startswith('ItemDeta0105j')).get_text(strip=True) if row.find('td', id=lambda x: x and x.startswith('ItemDeta0105j')) else ''
                        }
                        books.append(book_info)
                    
                    books.sort(key=lambda b: int(b.get('順位')) if b.get('順位', '').isdigit() else 0)
                    all_books_data[username]["books"] = books
                    print(f"{len(books)}件の予約が見つかりました。")

        except Exception as e:
            error_message = f"処理中にエラーが発生しました: {e}"
            print(error_message)
            all_books_data[username]["error"] = str(e)
        finally:
            print(f"--- {username}さんの確認を終了します ---")
            driver.delete_all_cookies()

    driver.quit()

    # HTMLを生成してファイルに保存
    html_output = generate_html(all_books_data)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html_output)
    print(f"結果を {OUTPUT_FILE} に出力しました。")

if __name__ == "__main__":
    main()