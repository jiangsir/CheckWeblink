import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import urllib3
import ssl
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import socket
import os, sys
import getpass

# 停用 SSL 警告訊息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 設置較低的 SSL 安全等級
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
try:
    requests.packages.urllib3.contrib.pyopenssl.util.ssl_.DEFAULT_CIPHERS += ':HIGH:!DH:!aNULL'
except AttributeError:
    # 如果沒有 PyOpenSSL
    pass

def is_google_docs_link(url):
    """判斷是否為 Google 文件連結"""
    google_patterns = [
        r'docs\.google\.com',
        r'drive\.google\.com',
        r'sheets\.google\.com',
        r'slides\.google\.com',
        r'forms\.google\.com'
    ]
    return any(re.search(pattern, url) for pattern in google_patterns)

def check_google_docs_permission(response):
    """檢查 Google 文件是否需要權限"""
    # 檢查是否有登入頁面或權限提示的關鍵詞
    permission_indicators = [
        'You need permission',
        'Request access',
        '需要權限',
        '請求存取權限'
    ]
    
    # 這些詞可能出現在正常可訪問的文檔中，但也可能出現在登入頁面
    # 所以我們需要更嚴格地判斷
    ambiguous_indicators = [
        'Sign in',
        'Google Account', 
        '登入',
        'Google 帳戶'
    ]
    
    soup = BeautifulSoup(response.text, 'html.parser')
    page_text = soup.get_text().lower()
    
    # 首先檢查明確的權限指示詞
    for indicator in permission_indicators:
        if indicator.lower() in page_text:
            return False, f"需要權限: {indicator}"
    
    # 檢查具有表單特性的元素數量，登入頁面通常有表單
    login_forms = soup.find_all('form')
    if login_forms and len(login_forms) >= 1:
        # 查看表單是否包含密碼欄位，這是登入頁面的特徵
        password_fields = soup.find_all('input', {'type': 'password'})
        if password_fields:
            # 檢查模糊指示詞
            for indicator in ambiguous_indicators:
                if indicator.lower() in page_text:
                    return False, f"疑似需要登入: 發現登入表單和指示詞 '{indicator}'"
    
    # 檢查是否有顯示 Google 文件的內容（如果是公開文件應該有這些特徵）
    content_indicators = ["viewer", "document", "spreadsheet", "presentation", "folder contents"]
    if is_google_docs_link(response.url) and any(indicator in page_text for indicator in content_indicators):
        return True, "文件可公開存取"
    
    # 檢查文件內容區塊是否存在
    content_divs = soup.find_all('div', {'role': 'presentation'}) or \
                   soup.find_all('div', {'class': 'ndfHFb-c4YZDc-cYSp0e-DARUcf'}) or \
                   soup.find_all('div', {'class': 'drive-viewer-content'}) or \
                   soup.find_all('div', {'id': 'drive-viewer-content'})
    
    if content_divs:
        return True, "發現文件內容區塊，應該可以存取"
        
    # 額外檢查：Drive 文件夾專用檢查
    if 'drive.google.com/drive/folders' in response.url:
        # 檢查是否有文件列表的特徵
        file_list_indicators = ["name", "last modified", "file", "folder", "共用", "檔案", "資料夾", "最後修改"]
        if any(indicator in page_text.lower() for indicator in file_list_indicators):
            return True, "發現資料夾內容列表，應該可以存取"
    
    # 保守結論：我們不確定，但假設可能可以訪問
    for indicator in ambiguous_indicators:
        if indicator.lower() in page_text:
            return True, f"可能需要登入但看起來可以部分存取 (含有'{indicator}'但未發現明確權限阻擋)"
            
    return True, "看起來可以存取"

def check_links(url):
    try:
        print(f"正在連接網站：{url}...")
        # 建立自訂的 Session，設定特定的 SSL 選項
        session = requests.Session()
        session.verify = False  # 停用 SSL 驗證
        # 設定 User-Agent 模擬瀏覽器，避免被阻擋
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'
        })
        
        response = session.get(url, timeout=10)
        response.raise_for_status()
        print("成功連接網站！正在解析頁面...")
    except Exception as e:
        print(f"無法存取主頁面 {url}，錯誤：{e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    # 擷取所有連結及其文字內容
    links_info = []
    for a in soup.find_all('a', href=True):
        links_info.append({
            'href': a['href'],
            'text': a.get_text(strip=True) or "[無文字]",
            'parent': str(a.parent.name),
            'parent_class': a.parent.get('class', []),
            'parent_id': a.parent.get('id', '')
        })
    
    base_url = url
    broken_links_info = []
    
    print(f"找到 {len(links_info)} 個連結，開始檢查...")
    for i, link_info in enumerate(links_info, 1):
        link = link_info['href']
        absolute_link = urllib.parse.urljoin(base_url, link)
        print(f"[{i}/{len(links_info)}] 檢查: {absolute_link} (顯示文字: {link_info['text']})")
        try:
            # 使用同一個 session 物件
            link_response = session.get(absolute_link, timeout=5)
            
            # 針對 Google 文件連結特殊處理
            if is_google_docs_link(absolute_link):
                print("  檢測到 Google 文件連結，檢查權限...")
                is_accessible, message = check_google_docs_permission(link_response)
                if not is_accessible:
                    print(f"⚠️ Google 文件需要權限: {absolute_link} ({message})")
                    broken_links_info.append({
                        'url': absolute_link,
                        'google_docs_issue': True,
                        'permission_message': message,
                        'text': link_info['text'],
                        'parent': link_info['parent'],
                        'parent_class': link_info['parent_class'],
                        'parent_id': link_info['parent_id']
                    })
                else:
                    print(f"✓ Google 文件可訪問 ({message})")
            # 一般連結檢查
            elif link_response.status_code != 200:
                print(f"⚠️ 失效連結：{absolute_link} (狀態碼：{link_response.status_code})")
                # 儲存失效連結的詳細資訊
                broken_links_info.append({
                    'url': absolute_link,
                    'status_code': link_response.status_code,
                    'text': link_info['text'],
                    'parent': link_info['parent'],
                    'parent_class': link_info['parent_class'],
                    'parent_id': link_info['parent_id']
                })
            else:
                print(f"✓ 連結正常")
            # 加入短暫延遲，避免對目標網站發送過多請求
            time.sleep(0.5)
        except Exception as e:
            print(f"❌ 檢查連結 {absolute_link} 時發生錯誤：{e}")
            # 將異常連結也加入失效連結清單
            broken_links_info.append({
                'url': absolute_link,
                'error': str(e),
                'text': link_info['text'],
                'parent': link_info['parent'],
                'parent_class': link_info['parent_class'],
                'parent_id': link_info['parent_id']
            })
    return broken_links_info

def send_report_email(recipient_email, subject, broken_links_info, checked_url, elapsed_time):
    """發送檢測報告郵件"""
    try:
        # 取得環境信息
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        current_user = getpass.getuser()
        script_path = os.path.abspath(__file__)
        
        # 創建郵件內容
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = 'mailer@tea.nknush.kh.edu.tw'  # 修改寄件者
        msg['To'] = recipient_email
        
        # 郵件正文
        email_body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                h2 {{ color: #2c3e50; }}
                .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                .summary {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                .error {{ color: #e74c3c; }}
                .info {{ color: #3498db; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>網站連結檢測報告</h2>
                
                <div class="summary">
                    <p><strong>檢測網址:</strong> {checked_url}</p>
                    <p><strong>檢測時間:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <p><strong>耗時:</strong> {elapsed_time:.2f} 秒</p>
                    <p><strong>檢測發起資訊:</strong></p>
                    <ul>
                        <li>主機名稱: {hostname}</li>
                        <li>IP 位址: {ip_address}</li>
                        <li>使用者: {current_user}</li>
                        <li>腳本路徑: {script_path}</li>
                    </ul>
                </div>
        """
        
        if broken_links_info:
            email_body += f"""
                <h3>檢測到 {len(broken_links_info)} 個失效連結:</h3>
                <table>
                    <tr>
                        <th>#</th>
                        <th>連結</th>
                        <th>顯示文字</th>
                        <th>問題</th>
                    </tr>
            """
            
            for i, info in enumerate(broken_links_info, 1):
                url = info['url']
                text = info['text']
                
                if 'google_docs_issue' in info:
                    issue = f"Google 文件權限問題 - {info['permission_message']}"
                elif 'status_code' in info:
                    issue = f"HTTP 狀態碼: {info['status_code']}"
                else:
                    issue = f"錯誤: {info['error']}"
                
                email_body += f"""
                    <tr>
                        <td>{i}</td>
                        <td><a href="{url}" target="_blank">{url}</a></td>
                        <td>{text}</td>
                        <td class="error">{issue}</td>
                    </tr>
                """
            
            email_body += "</table>"
        else:
            email_body += "<p class='info'>恭喜！沒有發現失效連結。</p>"
        
        email_body += """
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(email_body, 'html'))
        
        # 連接到 SMTP 伺服器並發送郵件
        print(f"\n正在發送報告郵件到 {recipient_email}...")
        
        # 郵件伺服器設定
        smtp_server = 'smtp.gmail.com'  # 假設使用 Gmail SMTP
        smtp_port = 587  # TLS 端口
        
        # 郵件帳號設定
        smtp_user = 'mailer@tea.nknush.kh.edu.tw'
        
        # 安全地獲取應用程式密碼
        # 方法 1: 環境變數
        app_password = os.environ.get('EMAIL_APP_PASSWORD')
              
        # 如果環境變數未設置，則提示輸入
        if not app_password:
            app_password = getpass.getpass('請輸入應用程式密碼: ')
        
        # 連接到 SMTP 伺服器並發送郵件
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()  # 向郵件伺服器打招呼
            server.starttls()  # 啟用 TLS 加密
            server.ehlo()  # 再次打招呼
            server.login(smtp_user, app_password)  # 使用應用程式密碼登入
            server.send_message(msg)
            
        print(f"報告郵件已成功發送到 {recipient_email}")
        return True
    except Exception as e:
        print(f"發送報告郵件時發生錯誤: {e}")
        return False

# 主程式
def main():
    # 指定要檢查的網站主頁
    url = 'https://www.nknush.kh.edu.tw'
    recipient_email = '555@tea.nknush.kh.edu.tw'  # 目標郵件地址
    
    # 如果有命令列參數，使用第一個參數作為網站 URL
    if len(sys.argv) > 1:
        url = sys.argv[1]
    
    print("開始檢查網站連結...")
    print("注意：已停用 SSL 憑證驗證，這可能存在安全風險")
    start_time = time.time()
    broken_links_info = check_links(url)
    elapsed_time = time.time() - start_time

    print("\n檢測完成！")
    print(f"總計耗時: {elapsed_time:.2f} 秒")
    if broken_links_info:
        print(f"檢測到 {len(broken_links_info)} 個失效連結：")
        for i, info in enumerate(broken_links_info, 1):
            print(f"\n{i}. 失效連結：{info['url']}")
            print(f"   顯示文字：{info['text']}")
            print(f"   父元素：{info['parent']}" + 
                (f", ID: {info['parent_id']}" if info['parent_id'] else "") + 
                (f", 類別: {', '.join(info['parent_class'])}" if info['parent_class'] else ""))
                
            if 'google_docs_issue' in info:
                print(f"   問題：Google 文件權限問題 - {info['permission_message']}")
            elif 'status_code' in info:
                print(f"   狀態碼：{info['status_code']}")
            else:
                print(f"   錯誤：{info['error']}")
    else:
        print("恭喜！沒有發現失效連結。")
    
    # 發送報告郵件
    email_subject = f"網站連結檢測報告 - {datetime.now().strftime('%Y-%m-%d')}"
    send_report_email(recipient_email, email_subject, broken_links_info, url, elapsed_time)

if __name__ == "__main__":
    main()
