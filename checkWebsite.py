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
requests.packages.urllib3.util.ssl_.DEFAULT_CIPHERS += ":HIGH:!DH:!aNULL"
try:
    requests.packages.urllib3.contrib.pyopenssl.util.ssl_.DEFAULT_CIPHERS += (
        ":HIGH:!DH:!aNULL"
    )
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
        session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36"
            }
        )

        start_time = time.time()
        response = session.get(url, timeout=timeout)
        response_time = time.time() - start_time

        status_code = response.status_code
        if status_code == 200:
            print(
                f"✓ {url} 網站正常 (狀態碼: {status_code}, 回應時間: {response_time:.2f}秒)"
            )
            return {
                "url": url,
                "status": "online",
                "status_code": status_code,
                "response_time": response_time,
                "error": None,
            }
        else:
            print(f"⚠️ {url} 網站回應異常 (狀態碼: {status_code})")
            return {
                "url": url,
                "status": "error",
                "status_code": status_code,
                "response_time": response_time,
                "error": f"HTTP 狀態碼 {status_code}",
            }
    except requests.exceptions.Timeout:
        print(f"❌ {url} 網站回應逾時")
        return {
            "url": url,
            "status": "timeout",
            "status_code": None,
            "response_time": timeout,
            "error": "連線逾時",
        }
    except requests.exceptions.ConnectionError as e:
        print(f"❌ {url} 網站無法連接: {e}")
        return {
            "url": url,
            "status": "offline",
            "status_code": None,
            "response_time": None,
            "error": f"連線錯誤: {str(e)}",
        }
    except Exception as e:
        print(f"❌ {url} 網站檢測發生錯誤: {e}")
        return {
            "url": url,
            "status": "error",
            "status_code": None,
            "response_time": None,
            "error": str(e),
        }


def check_ssl_certificate(url):
    """檢查網站 SSL 憑證狀態及到期日"""
    try:
        # 從 URL 提取域名
        from urllib.parse import urlparse

        hostname = urlparse(url).netloc

        print(f"正在檢查 {hostname} 的 SSL 憑證...")
        expiry_date = get_ssl_expiry_date(hostname)

        # 計算剩餘天數
        now = datetime.now()
        remaining_days = (expiry_date - now).days

        if remaining_days <= 0:
            status = "已過期"
            alert_level = "danger"
        elif remaining_days <= 14:
            status = "即將到期"
            alert_level = "warning"
        else:
            status = "有效"
            alert_level = "success"

        print(f"✓ {hostname} SSL 憑證: {status}, 剩餘 {remaining_days} 天")
        return {
            "hostname": hostname,
            "expiry_date": expiry_date,
            "remaining_days": remaining_days,
            "status": status,
            "alert_level": alert_level,
        }

    except Exception as e:
        print(f"❌ 檢查 {url} 的 SSL 憑證時發生錯誤: {e}")
        return {
            "hostname": urlparse(url).netloc if url.startswith("http") else url,
            "expiry_date": None,
            "remaining_days": None,
            "status": "檢查失敗",
            "alert_level": "danger",
            "error": str(e),
        }


def send_report_email(
    recipient_email, subject, websites_status, elapsed_time, ssl_results=None
):
    """發送檢測報告郵件，包含 SSL 憑證資訊"""
    try:
        # 取得環境信息
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        current_user = getpass.getuser()
        script_path = os.path.abspath(__file__)

        # 創建郵件內容
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = "mailer@tea.nknush.kh.edu.tw"
        msg["To"] = recipient_email

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
            url = status["url"]
            site_status = status["status"]

            # 計算統計資料
            if site_status == "online":
                online_count += 1
                status_class = "success"
                status_text = "正常"
            elif site_status == "timeout":
                offline_count += 1
                status_class = "warning"
                status_text = "逾時"
            else:
                offline_count += 1
                status_class = "error"
                status_text = "異常"

            # 回應時間格式化
            if status["response_time"] is not None:
                response_time = f"{status['response_time']:.2f} 秒"
            else:
                response_time = "N/A"

            # 詳細資訊
            if status["error"]:
                detail = f"{status['error']}"
                if status["status_code"]:
                    detail += f" (狀態碼: {status['status_code']})"
            elif status["status_code"]:
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

        # 添加 SSL 憑證資訊部分
        if ssl_results:
            email_body += """
                <h3>SSL 憑證狀態:</h3>
                <table>
                    <tr>
                        <th>域名</th>
                        <th>狀態</th>
                        <th>到期日</th>
                        <th>剩餘天數</th>
                    </tr>
            """

            for cert in ssl_results:
                hostname = cert["hostname"]

                if cert["remaining_days"] is None:
                    status_class = "error"
                    status_text = "無法檢查"
                    expiry_date = "未知"
                    remaining_days = "N/A"
                elif cert["remaining_days"] <= 0:
                    status_class = "error"
                    status_text = "已過期"
                    expiry_date = cert["expiry_date"].strftime("%Y-%m-%d")
                    remaining_days = f"{cert['remaining_days']} 天"
                elif cert["remaining_days"] <= 7:
                    status_class = "error"
                    status_text = "即將到期 (緊急)"
                    expiry_date = cert["expiry_date"].strftime("%Y-%m-%d")
                    remaining_days = f"{cert['remaining_days']} 天"
                elif cert["remaining_days"] <= 14:
                    status_class = "warning"
                    status_text = "即將到期"
                    expiry_date = cert["expiry_date"].strftime("%Y-%m-%d")
                    remaining_days = f"{cert['remaining_days']} 天"
                else:
                    status_class = "success"
                    status_text = "有效"
                    expiry_date = cert["expiry_date"].strftime("%Y-%m-%d")
                    remaining_days = f"{cert['remaining_days']} 天"

                email_body += f"""
                    <tr>
                        <td>{hostname}</td>
                        <td class="{status_class}">{status_text}</td>
                        <td>{expiry_date}</td>
                        <td>{remaining_days}</td>
                    </tr>
                """

            email_body += """
                </table>
            """

        msg.attach(MIMEText(email_body, "html"))

        # 連接到 SMTP 伺服器並發送郵件
        print(f"\n正在發送報告郵件到 {recipient_email}...")

        # 郵件伺服器設定
        smtp_server = "smtp.gmail.com"
        smtp_port = 587

        # 郵件帳號設定
        smtp_user = "mailer@tea.nknush.kh.edu.tw"

        # 安全地獲取應用程式密碼
        app_password = os.environ.get("EMAIL_APP_PASSWORD")

        # 如果環境變數未設置，則提示輸入
        if not app_password:
            app_password = getpass.getpass("請輸入應用程式密碼: ")

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


def send_telegram_message(message):
    """發送消息到 Telegram"""
    try:
        # 檢查是否設定了 Telegram 相關環境變數
        telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

        # 如果未設定 Telegram 相關資訊，則直接返回
        if not telegram_bot_token or not telegram_chat_id:
            print("未設定 Telegram Bot Token 或 Chat ID，跳過 Telegram 通知")
            return

        print("準備發送 Telegram 通知...")
        
        # 發送消息到 Telegram
        telegram_api_url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": telegram_chat_id,
            "text": message,
            "parse_mode": "HTML",  # 支援 HTML 格式
        }

        response = requests.post(telegram_api_url, json=payload, timeout=10)

        if response.status_code == 200:
            print(f"已成功發送 Telegram 通知")
        else:
            print(f"發送 Telegram 通知失敗，狀態碼: {response.status_code}, 回應: {response.text}")

            # 如果 HTML 解析失敗，嘗試發送純文本
            if "can't parse entities" in response.text:
                print("Telegram HTML 解析失敗，嘗試以純文本格式重新發送...")
                # 移除所有 HTML 標籤
                import re
                plain_text = re.sub(r"<[^>]+>", "", message)
                
                payload = {
                    "chat_id": telegram_chat_id,
                    "text": plain_text,
                    "parse_mode": "",  # 不使用任何解析模式
                }

                response = requests.post(telegram_api_url, json=payload, timeout=10)
                if response.status_code == 200:
                    print(f"已成功以純文本格式發送 Telegram 通知")
                else:
                    print(f"純文本發送也失敗，狀態碼: {response.status_code}, 回應: {response.text}")

    except Exception as e:
        print(f"發送 Telegram 通知時發生錯誤: {str(e)}")


def format_telegram_message(websites_status, elapsed_time, ssl_results=None):
    """格式化 Telegram 訊息內容，包含 SSL 憑證資訊"""
    # 取得環境信息
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    current_user = getpass.getuser()

    # 統計結果
    total_sites = len(websites_status)
    online_sites = sum(1 for site in websites_status if site["status"] == "online")
    offline_sites = total_sites - online_sites

    # 建立訊息標頭
    if offline_sites > 0:
        message = f"⚠️ <b>網站可用性警報</b>\n\n"
    else:
        message = f"✅ <b>網站可用性檢查</b>\n\n"

    # 添加摘要資訊
    message += f"<b>檢測時間:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    message += f"<b>耗時:</b> {elapsed_time:.2f} 秒\n"
    message += f"<b>檢測資訊:</b> {hostname} ({ip_address}), 使用者: {current_user}\n\n"

    # 添加統計資訊
    message += f"<b>檢測結果:</b> {online_sites}/{total_sites} 個網站運作正常\n\n"

    # 如果有網站異常，列出它們
    if offline_sites > 0:
        message += "<b>異常網站:</b>\n"
        for site in websites_status:
            if site["status"] != "online":
                status_text = "逾時" if site["status"] == "timeout" else "異常"
                error_detail = site.get("error") or "無詳細資訊"
                response_time = (
                    f", 回應時間: {site['response_time']:.2f}秒"
                    if site["response_time"]
                    else ""
                )
                status_code = (
                    f", 狀態碼: {site['status_code']}" if site["status_code"] else ""
                )

                message += f"❌ <a href='{site['url']}'>{site['url']}</a>: {status_text}{response_time}{status_code}\n"
                message += f"   錯誤: {error_detail}\n"

    # 如果有 SSL 憑證資訊，添加到報告中
    if ssl_results:
        # 創建一個網址到 SSL 結果的映射，方便查找
        ssl_map = {cert["hostname"]: cert for cert in ssl_results}

        message += "\n<b>SSL 憑證狀態:</b>\n"
        print(websites_status, websites_status)
        for site in websites_status:
            if site["status"] == "online" and site["url"].startswith("https"):
                from urllib.parse import urlparse

                hostname = urlparse(site["url"]).netloc

                if hostname in ssl_map:
                    cert = ssl_map[hostname]

                    # 根據剩餘天數決定顯示圖標
                    if cert["remaining_days"] is None:
                        icon = "❓"  # 未知
                        status_text = "無法檢查"
                    elif cert["remaining_days"] <= 0:
                        icon = "🚨"  # 已過期
                        status_text = f"已過期 ({cert['remaining_days']} 天)"
                    elif cert["remaining_days"] <= 7:
                        icon = "⚠️"  # 7天內到期
                        status_text = f"即將到期 (剩餘 {cert['remaining_days']} 天)"
                    elif cert["remaining_days"] <= 14:
                        icon = "⚠️"  # 14天內到期
                        status_text = f"即將到期 (剩餘 {cert['remaining_days']} 天)"
                    else:
                        icon = "✅"  # 有效
                        status_text = f"有效 (剩餘 {cert['remaining_days']} 天)"

                    # 到期日期
                    expires_text = (
                        f", 到期日: {cert['expiry_date'].strftime('%Y-%m-%d')}"
                        if cert["expiry_date"]
                        else ""
                    )

                    message += (
                        f"{icon} https://{hostname}: {status_text}{expires_text}\n"
                    )

    # 如果訊息過長，截斷它，並加上說明
    if len(message) > 4000:
        message = message[:3950] + "\n\n... (訊息因長度限制而被截斷)"

    return message


def format_ssl_telegram_message(ssl_results):
    """格式化 SSL 憑證檢查的 Telegram 訊息"""
    # 檢查是否有需要提醒的憑證
    warning_certs = [
        cert
        for cert in ssl_results
        if cert["remaining_days"] is not None and cert["remaining_days"] <= 14
    ]

    if not warning_certs:
        return None  # 如果沒有需要提醒的憑證，返回 None

    # 建立訊息
    message = f"⚠️ <b>SSL 憑證即將到期警告</b>\n\n"
    message += f"<b>檢測時間:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    message += "<b>即將到期的 SSL 憑證:</b>\n"
    for cert in warning_certs:
        expires_text = (
            f"{cert['expiry_date'].strftime('%Y-%m-%d')}"
            if cert["expiry_date"]
            else "未知"
        )

        # 依剩餘天數決定警告級別
        if cert["remaining_days"] <= 0:
            icon = "🚨"  # 已過期
        elif cert["remaining_days"] <= 7:
            icon = "⚠️"  # 7天內到期
        else:
            icon = "⚠️"  # 14天內到期

        message += f"{icon} <a href='https://{cert['hostname']}'>{cert['hostname']}</a>: {cert['status']}\n"
        message += f"   到期日: {expires_text}, 剩餘天數: {cert['remaining_days']} 天\n"

    return message


def get_ssl_expiry_date(hostname, port=443):
    context = ssl.create_default_context()
    with socket.create_connection((hostname, port)) as sock:
        with context.wrap_socket(sock, server_hostname=hostname) as ssock:
            cert = ssock.getpeercert()
            expiry_date = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
            return expiry_date


def main():
    # 定義要檢測的重要網站清單
    websites = [
        "https://www.nknush.kh.edu.tw",
        "https://zerojudge.tw",
        "https://ashs.zerojudge.tw",
        "https://slave1.zerojudge.tw",
        "https://dump.zerojudge.tw/Login",
        "https://apcs.zerojudge.tw",
    ]

    # 如果有命令列參數，使用提供的網站列表
    if len(sys.argv) > 1:
        websites = sys.argv[1:]

    recipient_email = "555@tea.nknush.kh.edu.tw"

    print("開始檢查網站運作狀態...")
    start_time = time.time()

    # 儲存所有網站的檢測結果
    all_results = []
    ssl_results = []

    # 檢測每個網站
    for website in websites:
        # 檢查網站可用性
        result = check_website(website)
        all_results.append(result)

        # 如果網站可連接且是 HTTPS，檢查 SSL 憑證
        if result["status"] == "online" and website.startswith("https"):
            try:
                from urllib.parse import urlparse

                hostname = urlparse(website).netloc
                ssl_result = check_ssl_certificate(website)
                ssl_results.append(ssl_result)
            except Exception as e:
                print(f"無法檢查 {website} 的 SSL 憑證: {e}")

    elapsed_time = time.time() - start_time

    # 統計結果
    total_sites = len(all_results)
    online_sites = sum(1 for site in all_results if site["status"] == "online")
    offline_sites = total_sites - online_sites

    print("\n檢測完成！")
    print(f"總計耗時: {elapsed_time:.2f} 秒")
    print(f"檢測結果: {online_sites}/{total_sites} 個網站正常運作")

    if offline_sites > 0:
        print("\n異常網站列表:")
        for site in all_results:
            if site["status"] != "online":
                print(f"- {site['url']}: {site['error']}")

    # 檢查是否有即將到期的 SSL 憑證
    ssl_warnings = [
        cert
        for cert in ssl_results
        if cert["remaining_days"] is not None and cert["remaining_days"] <= 14
    ]
    if ssl_warnings:
        print("\nSSL 憑證警告:")
        for cert in ssl_warnings:
            print(
                f"- {cert['hostname']}: 剩餘 {cert['remaining_days']} 天，到期日: {cert['expiry_date'].strftime('%Y-%m-%d')}"
            )

    # 準備網站可用性的 Telegram 訊息，將 SSL 結果一併傳入
    telegram_message = format_telegram_message(all_results, elapsed_time, ssl_results)

    # 準備單獨的 SSL 憑證警告訊息 (僅包含即將到期的憑證)
    ssl_warning_message = format_ssl_telegram_message(ssl_results)

    # 處理網站可用性通知 (已包含 SSL 狀態)
    if offline_sites > 0:
        email_subject = (
            f"⚠️ 網站可用性警報 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        send_report_email(
            recipient_email, email_subject, all_results, elapsed_time, ssl_results
        )  # 加入 ssl_results 參數
        send_telegram_message(telegram_message)  # 發送 Telegram 通知
    else:
        current_hour = datetime.now().hour
        if 8 <= current_hour < 9:
            email_subject = f"✓ 網站可用性日報 - {datetime.now().strftime('%Y-%m-%d')}"
            send_report_email(
                recipient_email, email_subject, all_results, elapsed_time, ssl_results
            )  # 加入 ssl_results 參數
            send_telegram_message(telegram_message)  # 發送 Telegram 通知

    # 處理 SSL 憑證到期警告 (只有即將到期的憑證才需要額外單獨發送)
    if ssl_warning_message:
        print("\n發送 SSL 憑證到期警告...")
        # 如果不想重複發送，可以考慮只在非報告日或有特別緊急情況時發送
        # 例如，只在憑證剩餘天數 <= 7 天時才發送額外警告
        critical_ssl_warnings = [
            cert
            for cert in ssl_results
            if cert["remaining_days"] is not None and cert["remaining_days"] <= 7
        ]
        if critical_ssl_warnings:
            send_telegram_message(ssl_warning_message)  # 發送 SSL 憑證警告


if __name__ == "__main__":
    main()
