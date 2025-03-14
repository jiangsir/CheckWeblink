#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GitHub Actions IP 範圍更新工具
此腳本獲取 GitHub Actions 的 IP 範圍並更新 UFW 規則
適用於 Ubuntu 系統的 UFW 0.36 版本
"""

import os
import sys
import json
import subprocess
import tempfile
import time
from datetime import datetime
import shutil
import re
import logging
import requests

# 設定日誌
LOG_DIR = os.path.expanduser("~/crontab")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "github_ufw.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("github-ip-updater")

def check_prerequisites():
    """檢查必要的工具是否已安裝"""
    missing_tools = []
    
    if shutil.which("ufw") is None:
        missing_tools.append("ufw")
    
    if missing_tools:
        logger.error(f"缺少必要工具: {', '.join(missing_tools)}. 請先安裝這些工具.")
        logger.info("可使用以下命令安裝: sudo apt-get install -y " + " ".join(missing_tools))
        return False
    
    return True

def run_command(command, shell=False):
    """執行命令並返回輸出和錯誤碼"""
    cmd_str = command if shell else " ".join(command)
    logger.debug(f"執行指令: {cmd_str}")
    
    try:
        if shell:
            result = subprocess.run(command, shell=True, text=True, capture_output=True)
        else:
            result = subprocess.run(command, text=True, capture_output=True)
        
        if result.returncode != 0:
            logger.warning(f"指令返回非零狀態碼: {result.returncode}")
            logger.warning(f"錯誤訊息: {result.stderr}")
        
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        logger.error(f"執行指令時發生錯誤: {e}")
        return "", str(e), 1

def get_github_ips():
    """獲取 GitHub Actions 的 IP 範圍"""
    logger.info("獲取 GitHub Actions IP 範圍...")
    
    try:
        # 使用 requests 庫替代 curl
        response = requests.get("https://api.github.com/meta", timeout=10)
        response.raise_for_status()  # 如果請求出錯則拋出異常
        
        data = response.json()
        ip_ranges = data.get("actions", [])
        logger.info(f"找到 {len(ip_ranges)} 個 GitHub Actions IP 範圍")
        return ip_ranges
    except requests.RequestException as e:
        logger.error(f"獲取 GitHub IP 範圍失敗: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"解析 GitHub API 回應時出錯: {e}")
        return None

def check_ufw_version():
    """檢查 UFW 版本"""
    stdout, stderr, exit_code = run_command(["ufw", "--version"])
    if exit_code != 0:
        logger.error(f"無法獲取 UFW 版本: {stderr}")
        return "unknown"
    
    match = re.search(r'(\d+\.\d+)', stdout)
    if match:
        return match.group(1)
    return "unknown"

def check_ufw_status():
    """檢查 UFW 是否啟用，如果未啟用則啟用它"""
    logger.info("檢查 UFW 狀態...")
    
    stdout, stderr, exit_code = run_command(["sudo", "ufw", "status"])
    if exit_code != 0:
        logger.error(f"檢查 UFW 狀態失敗: {stderr}")
        return
    
    if "Status: active" not in stdout:
        logger.info("UFW 未啟用，正在啟用...")
        run_command(["sudo", "ufw", "--force", "enable"])
        logger.info("UFW 已啟用")
    else:
        logger.info("UFW 已經啟用")

def reset_ufw():
    """完全重置 UFW 規則"""
    logger.info("重置 UFW 規則...")
    
    # 備份現有規則
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_file = os.path.join(LOG_DIR, f"ufw_backup_{timestamp}.txt")
    stdout, stderr, exit_code = run_command(["sudo", "ufw", "status", "verbose"])
    
    with open(backup_file, "w") as f:
        f.write(stdout)
    logger.info(f"UFW 規則已備份至 {backup_file}")
    
    # 重置規則
    run_command(["sudo", "ufw", "--force", "reset"])
    logger.info("UFW 規則已重置")
    
    # 設置默認策略
    run_command(["sudo", "ufw", "default", "deny", "incoming"])
    run_command(["sudo", "ufw", "default", "allow", "outgoing"])
    logger.info("UFW 默認策略已設置")

def add_basic_rules():
    """添加基本規則"""
    logger.info("添加基本規則...")
    
    # 允許 SSH 連接
    run_command(["sudo", "ufw", "allow", "ssh"])
    
    # 允許 HTTP/HTTPS 基本連接
    run_command(["sudo", "ufw", "allow", "80/tcp"])
    run_command(["sudo", "ufw", "allow", "443/tcp"])
    
    logger.info("基本規則已添加")

def classify_ip_ranges(ip_ranges):
    """分類 IP 為 IPv4 和 IPv6"""
    ipv4_ranges = []
    ipv6_ranges = []
    
    for ip in ip_ranges:
        if ":" in ip:  # IPv6
            ipv6_ranges.append(ip)
        else:  # IPv4
            ipv4_ranges.append(ip)
    
    logger.info(f"IP 分類完成: IPv4: {len(ipv4_ranges)}, IPv6: {len(ipv6_ranges)}")
    return ipv4_ranges, ipv6_ranges

def add_ip_rules(ip_ranges, ip_type="IPv4", max_rules=100, batch_size=50):
    """批次添加 IP 規則"""
    logger.info(f"添加 {ip_type} 規則 (最多 {max_rules} 條)...")
    
    count = 0
    batches = [ip_ranges[i:i+batch_size] for i in range(0, min(len(ip_ranges), max_rules), batch_size)]
    
    for i, batch in enumerate(batches, 1):
        logger.info(f"處理 {ip_type} 批次 {i}/{len(batches)}...")
        
        for ip in batch:
            # UFW 0.36 在某些系統上不支持 comment 參數，所以移除它
            # 添加 HTTP 規則
            run_command(["sudo", "ufw", "allow", "from", ip, "to", "any", "port", "80", "proto", "tcp"])
            
            # 添加 HTTPS 規則
            run_command(["sudo", "ufw", "allow", "from", ip, "to", "any", "port", "443", "proto", "tcp"])
            
            count += 1
            
            # 適當暫停避免系統過載
            if count % 10 == 0:
                time.sleep(0.1)
    
    logger.info(f"已添加 {count} 條 {ip_type} 規則")
    return count

def reload_ufw():
    """重新載入 UFW 規則"""
    logger.info("重新載入 UFW 規則...")
    stdout, stderr, exit_code = run_command(["sudo", "ufw", "reload"])
    if exit_code == 0:
        logger.info("UFW 規則重新載入成功")
    else:
        logger.error(f"重新載入 UFW 規則失敗: {stderr}")

def main():
    """主函數"""
    logger.info("===== GitHub Actions IP 更新腳本啟動 =====")
    
    if not check_prerequisites():
        sys.exit(1)
    
    # 檢查 UFW 版本
    ufw_version = check_ufw_version()
    logger.info(f"UFW 版本: {ufw_version}")
    
    # 獲取 GitHub Actions IP 範圍
    ip_ranges = get_github_ips()
    if not ip_ranges:
        logger.error("無法獲取 GitHub Actions IP 範圍，腳本終止")
        sys.exit(1)
    
    # 完全重置 UFW (比刪除個別規則更可靠)
    reset_ufw()
    
    # 添加基本規則
    add_basic_rules()
    
    # 分類 IP
    ipv4_ranges, ipv6_ranges = classify_ip_ranges(ip_ranges)
    
    # 添加新規則 (只添加 IPv4 規則以避免問題)
    ipv4_count = add_ip_rules(ipv4_ranges, "IPv4", max_rules=100)
    
    # 啟用 UFW
    check_ufw_status()
    
    # 重新載入 UFW
    reload_ufw()
    
    logger.info(f"共添加 {ipv4_count} 條 GitHub Actions IP 規則")
    logger.info("===== GitHub Actions IP 更新腳本完成 =====")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception(f"腳本執行時發生未處理的錯誤: {e}")
        sys.exit(1)