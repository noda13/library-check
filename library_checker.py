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

def parse_book_title(title):
    """書籍タイトルから著者と出版社を分離する"""
    # 最後の部分が出版社
    parts = title.split('　')
    if len(parts) >= 3:
        publisher = parts[-1]
        author_part = parts[-2]
        title_part = '　'.join(parts[:-2])
        
        # 著者部分から著者名を抽出（／著、／作など）
        if '／' in author_part:
            author = author_part.split('／')[0]
        else:
            author = author_part
            
        return title_part, author, publisher
    else:
        return title, '', ''

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
            h1 { color: #333; }
            table { border-collapse: collapse; width: 100%; margin-bottom: 2em; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; font-weight: bold; }
            .highlight { background-color: #fff3cd; }
            .timestamp { color: #777; font-size: 0.9em; }
            .error { color: red; margin: 1em 0; }
        </style>
    </head>
    <body>
        <h1>図書館予約状況</h1>
    """

    # 全ユーザーの本をまとめる
    all_books = []
    errors = []
    
    for user, data in all_books_data.items():
        if data["error"]:
            errors.append(f"{user}さん: {data['error']}")
        elif data["books"]:
            for book in data["books"]:
                book_copy = book.copy()
                book_copy['ユーザー'] = user
                # タイトルを分離
                title, author, publisher = parse_book_title(book.get('資料名', ''))
                book_copy['タイトル'] = title
                book_copy['著者'] = author
                book_copy['出版社'] = publisher
                all_books.append(book_copy)

    # タイトル重複チェック
    title_count = {}
    for book in all_books:
        t = book.get('タイトル', '')
        if t:
            title_count[t] = title_count.get(t, 0) + 1
    duplicate_titles = {t for t, c in title_count.items() if c > 1}

    # エラーがある場合は表示
    if errors:
        html_content += "<div class='error'><h2>エラー</h2><ul>"
        for error in errors:
            html_content += f"<li>{error}</li>"
        html_content += "</ul></div>"

    if not all_books:
        html_content += "<p>現在、予約している資料はありません。</p>"
    else:
        # ソート: 「ご用意できました」を先頭に、その後は順位順
        def sort_key(book):
            if book.get('予約状態', '') == 'ご用意できました':
                return (0, 0)  # 最優先
            else:
                order = book.get('順位', '')
                if order and order.isdigit():
                    return (1, int(order))
                else:
                    return (1, 999)  # 順位不明は最後
        
        all_books.sort(key=sort_key)
        
        # テーブル作成
        html_content += """
        <table>
            <thead>
                <tr>
                    <th>ユーザー</th>
                    <th>タイトル</th>
                    <th>著者</th>
                    <th>出版社</th>
                    <th>状態</th>
                    <th>順位</th>
                    <th>期限</th>
                    <th>受取館</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for book in all_books:
            # ハイライト条件: 予約状態が「予約中です」以外 または タイトル重複
            highlight = False
            if book.get('予約状態', '') != '予約中です':
                highlight = True
            if book.get('タイトル', '') in duplicate_titles:
                highlight = True
            highlight_class = "highlight" if highlight else ''

            # 期限と受取館の表示制御
            deadline = book.get('取置期限', '') if book.get('予約状態', '') != '予約中です' else ''
            pickup_location = book.get('受取館', '') if book.get('予約状態', '') != '予約中です' else ''

            html_content += f"""
                <tr class="{highlight_class}">
                    <td>{book.get('ユーザー', '')}</td>
                    <td>{book.get('タイトル', '')}</td>
                    <td>{book.get('著者', '')}</td>
                    <td>{book.get('出版社', '')}</td>
                    <td>{book.get('予約状態', '')}</td>
                    <td>{book.get('順位', '')}</td>
                    <td>{deadline}</td>
                    <td>{pickup_location}</td>
                </tr>
            """
        
        html_content += """
            </tbody>
        </table>
        """

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