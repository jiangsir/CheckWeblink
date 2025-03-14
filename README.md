# 網站連結檢查工具

這是一個自動化工具，用於檢查網站中的失效連結，特別針對學校網站 (www.nknush.kh.edu.tw) 進行優化。

## 功能特點

- 自動爬取網站上的所有連結
- 檢查連結是否正常運作
- 特殊處理 Google Docs/Drive 連結，檢查訪問權限設定
- 檢測結果通過電子郵件發送詳細報告
- 使用 GitHub Actions 進行自動化排程檢查

## 工作原理

1. 爬取指定網站的所有連結
2. 逐一檢查每個連結的可訪問性
3. 對於 Google 文件類型的連結，執行特殊權限檢查
4. 生成詳細報告，列出所有失效連結以及失效原因
5. 通過電子郵件發送檢測報告

## 檔案結構

- [checkWeblink.py](checkWeblink.py) - 主要的檢查腳本
- [.github/workflows/check_www.nknush.kh.edu.tw.yml](.github/workflows/check_www.nknush.kh.edu.tw.yml) - GitHub Actions 排程配置

## 使用方法

### 本地運行

```bash
# 安裝依賴套件
pip install requests beautifulsoup4 urllib3==1.26.6

# 預設檢查學校網站
python checkWeblink.py

# 檢查其他網站
python checkWeblink.py https://example.com

# 檢查各個重要網站
python checkWebsite.py
