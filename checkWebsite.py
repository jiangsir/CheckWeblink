import requests
import time
import urllib3
import ssl
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import socket
import os
import sys
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

def check_website(url, timeout=10):
    """檢查網站是否正常運作"""
    try:
        print(f"正在檢查網站：{url}...")
        # 建立自訂的 Session，設定特定的 SSL 選項
        session = requests.Session()
        session.verify = False  # 停用 SSL 驗證
        # 設定 User-Agent 模擬瀏覽器，避免被阻擋
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36'
        })
        
        start_time = time.time()
        response = session.get(url, timeout=timeout)
        response_time = time.time() - start_time
        
        status_code = response.status_code
        if status_code == 200:
            print(f"✓ {url} 網站正常 (狀態碼: {status_code}, 回應時間: {response_time:.2f}秒)")
            return {
                'url': url,
                'status': 'online',
                'status_code': status_code,
                'response_time': response_time,
                'error': None
            }
        else:
            print(f"⚠️ {url} 網站回應異常 (狀態碼: {status_code})")
            return {
                'url': url,
                'status': 'error',
                'status_code': status_code,
                'response_time': response_time,
                'error': f"HTTP 狀態碼 {status_code}"
            }
    except requests.exceptions.Timeout:
        print(f"❌ {url} 網站回應逾時")
        return {
            'url': url,
            'status': 'timeout',
            'status_code': None,
            'response_time': timeout,
            'error': "連線逾時"
        }
    except requests.exceptions.ConnectionError as e:
        print(f"❌ {url} 網站無法連接: {e}")
        return {
            'url': url,
            'status': 'offline',
            'status_code': None,
            'response_time': None,
            'error': f"連線錯誤: {str(e)}"
        }
    except Exception as e:
        print(f"❌ {url} 網站檢測發生錯誤: {e}")
        return {
            'url': url,
            'status': 'error',
            'status_code': None,
            'response_time': None,
            'error': str(e)
        }

def send_report_email(recipient_email, subject, websites_status, elapsed_time):
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
        msg['From'] = 'mailer@tea.nknush.kh.edu.tw'
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
                .warning {{ color: #f39c12; }}
                .success {{ color: #2ecc71; }}
                .info {{ color: #3498db; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2>網站可用性檢測報告</h2>
                
                <div class="summary">
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

                <h3>網站狀態總覽:</h3>
                <table>
                    <tr>
                        <th>#</th>
                        <th>網站</th>
                        <th>狀態</th>
                        <th>回應時間</th>
                        <th>詳細資訊</th>
                    </tr>
        """
        
        # 統計結果
        online_count = 0
        offline_count = 0
        
        for i, status in enumerate(websites_status, 1):
            url = status['url']
            site_status = status['status']
            
            # 計算統計資料
            if site_status == 'online':
                online_count += 1
                status_class = 'success'
                status_text = '正常'
            elif site_status == 'timeout':
                offline_count += 1
                status_class = 'warning'
                status_text = '逾時'
            else:
                offline_count += 1
                status_class = 'error'
                status_text = '異常'
                
            # 回應時間格式化
            if status['response_time'] is not None:
                response_time = f"{status['response_time']:.2f} 秒"
            else:
                response_time = "N/A"
                
            # 詳細資訊
            if status['error']:
                detail = f"{status['error']}"
                if status['status_code']:
                    detail += f" (狀態碼: {status['status_code']})"
            elif status['status_code']:
                detail = f"狀態碼: {status['status_code']}"
            else:
                detail = "無詳細資訊"
                
            email_body += f"""
                <tr>
                    <td>{i}</td>
                    <td><a href="{url}" target="_blank">{url}</a></td>
                    <td class="{status_class}">{status_text}</td>
                    <td>{response_time}</td>
                    <td>{detail}</td>
                </tr>
            """
        
        # 結果總結
        total_sites = len(websites_status)
        email_body += f"""
                </table>
                
                <div class="summary">
                    <p>檢測總結: 共檢測 {total_sites} 個網站</p>
                    <ul>
                        <li class="success">正常運作: {online_count} 個網站</li>
                        <li class="error">異常或無法訪問: {offline_count} 個網站</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(email_body, 'html'))
        
        # 連接到 SMTP 伺服器並發送郵件
        print(f"\n正在發送報告郵件到 {recipient_email}...")
        
        # 郵件伺服器設定
        smtp_server = 'smtp.gmail.com'
        smtp_port = 587
        
        # 郵件帳號設定
        smtp_user = 'mailer@tea.nknush.kh.edu.tw'
        
        # 安全地獲取應用程式密碼
        app_password = os.environ.get('EMAIL_APP_PASSWORD')
        
        # 如果環境變數未設置，則提示輸入
        if not app_password:
            app_password = getpass.getpass('請輸入應用程式密碼: ')
        
        # 連接到 SMTP 伺服器並發送郵件
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, app_password)
            server.send_message(msg)
            
        print(f"報告郵件已成功發送到 {recipient_email}")
        return True
    except Exception as e:
        print(f"發送報告郵件時發生錯誤: {e}")
        return False

def main():
    # 定義要檢測的重要網站清單
    websites = [
        'https://www.nknush.kh.edu.tw',
        'https://zerojudge.tw',
        'https://apcs.zerojudge.tw',
        'https://dump.zerojudge.tw',
        'https://slave1.zerojudge.tw',
        'https://ashs.zerojudge.tw',
    ]
    
    # 如果有命令列參數，使用提供的網站列表
    if len(sys.argv) > 1:
        websites = sys.argv[1:]
    
    recipient_email = '555@tea.nknush.kh.edu.tw'
    
    print("開始檢查網站運作狀態...")
    start_time = time.time()
    
    # 儲存所有網站的檢測結果
    all_results = []
    
    # 檢測每個網站
    for website in websites:
        result = check_website(website)
        all_results.append(result)
    
    elapsed_time = time.time() - start_time
    
    # 統計結果
    total_sites = len(all_results)
    online_sites = sum(1 for site in all_results if site['status'] == 'online')
    offline_sites = total_sites - online_sites
    
    print("\n檢測完成！")
    print(f"總計耗時: {elapsed_time:.2f} 秒")
    print(f"檢測結果: {online_sites}/{total_sites} 個網站正常運作")
    
    if offline_sites > 0:
        print("\n異常網站列表:")
        for site in all_results:
            if site['status'] != 'online':
                print(f"- {site['url']}: {site['error']}")
    
    # 只有當有異常網站時才發送郵件
    if offline_sites > 0:
        email_subject = f"⚠️ 網站可用性警報 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        send_report_email(recipient_email, email_subject, all_results, elapsed_time)
    else:
        # 可選：每天只發送一次正常報告
        current_hour = datetime.now().hour
        if current_hour == 8:  # 每天早上 8 點發送
            email_subject = f"✓ 網站可用性日報 - {datetime.now().strftime('%Y-%m-%d')}"
            send_report_email(recipient_email, email_subject, all_results, elapsed_time)

if __name__ == "__main__":
    main()