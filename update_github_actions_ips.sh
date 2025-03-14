#!/bin/bash
# 檔名: update_github_actions_ips.sh

# 安裝所需工具
command -v curl >/dev/null 2>&1 || { echo "需要安裝 curl"; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "需要安裝 jq"; exit 1; }

# 下載 GitHub IP 範圍
echo "正在獲取 GitHub Actions IP 範圍..."
GITHUB_IPS=$(curl -s https://api.github.com/meta | jq -r '.actions[]')

# 計數 IP 數量
IP_COUNT=$(echo "$GITHUB_IPS" | wc -l)
echo "找到共 $IP_COUNT 個 GitHub Actions IP 範圍"

# 檢查 UFW 是否啟用
if ! sudo ufw status | grep -q "Status: active"; then
  echo "UFW 未啟用，正在啟用..."
  sudo ufw --force enable
fi

# 移除舊有的 GitHub Actions 規則 - 修正版
echo "移除舊有的防火牆規則..."
# 使用編號方式刪除規則，從最大編號開始刪除，避免編號變化
sudo ufw status numbered | grep "GitHub" | awk '{print $1}' | sed 's/\[//' | sed 's/\]//' | sort -r | while read num; do
  echo "刪除規則編號: $num"
  sudo ufw --force delete $num
done

# 分別處理 IPv4 和 IPv6 地址
echo "開始添加新規則..."
total=0
ipv4=0
ipv6=0

# 使用更簡潔的方法 - 批次處理
# 建立臨時 IPv4 和 IPv6 文件
IPV4_FILE=$(mktemp)
IPV6_FILE=$(mktemp)

# 將 IP 分類
for ip in $GITHUB_IPS; do
  total=$((total + 1))
  # 進度顯示
  if [ $((total % 500)) -eq 0 ]; then
    echo "處理中: $total/$IP_COUNT"
  fi
  
  # 分類 IP
  if [[ $ip =~ .*:.* ]]; then
    echo "$ip" >> $IPV6_FILE
    ipv6=$((ipv6 + 1))
  else
    echo "$ip" >> $IPV4_FILE
    ipv4=$((ipv4 + 1))
  fi
done

echo "IP 分類完成: IPv4: $ipv4, IPv6: $ipv6"
echo "正在添加規則 (分批處理)..."

# 批次處理 IPv4 規則 (每批50個)
echo "添加 IPv4 規則..."
BATCH_SIZE=50
TOTAL_IPV4=$(wc -l < $IPV4_FILE)
BATCH_COUNT=$(( (TOTAL_IPV4 + BATCH_SIZE - 1) / BATCH_SIZE ))

for i in $(seq 1 $BATCH_COUNT); do
  start_line=$(( (i-1) * BATCH_SIZE + 1 ))
  end_line=$(( i * BATCH_SIZE ))
  
  # 提取當前批次的 IP
  BATCH_IPS=$(sed -n "${start_line},${end_line}p" $IPV4_FILE)
  
  echo "批次 $i/$BATCH_COUNT: 處理 IPv4 規則..."
  
  # 對每個 IP 添加規則 - 移除 comment 參數
  for ip in $BATCH_IPS; do
    # UFW 0.36 移除 comment 參數
    sudo ufw allow from $ip to any port 80 proto tcp
    sudo ufw allow from $ip to any port 443 proto tcp
  done
done

# 批次處理 IPv6 規則 (每批50個)
echo "添加 IPv6 規則..."
TOTAL_IPV6=$(wc -l < $IPV6_FILE)
BATCH_COUNT=$(( (TOTAL_IPV6 + BATCH_SIZE - 1) / BATCH_SIZE ))

for i in $(seq 1 $BATCH_COUNT); do
  start_line=$(( (i-1) * BATCH_SIZE + 1 ))
  end_line=$(( i * BATCH_SIZE ))
  
  # 提取當前批次的 IP
  BATCH_IPS=$(sed -n "${start_line},${end_line}p" $IPV6_FILE)
  
  echo "批次 $i/$BATCH_COUNT: 處理 IPv6 規則..."
  
  # 對每個 IP 添加規則 - 移除 comment 參數
  for ip in $BATCH_IPS; do
    # UFW 0.36 移除 comment 參數
    sudo ufw allow from $ip to any port 80 proto tcp
    sudo ufw allow from $ip to any port 443 proto tcp
  done
done

# 清理臨時文件
rm -f $IPV4_FILE $IPV6_FILE

echo "添加完成: IPv4: $ipv4, IPv6: $ipv6"

echo "正在重新載入 UFW..."
sudo ufw reload

echo "GitHub Actions IP ranges updated in UFW at $(date)"

# 安裝套件 
# sudo apt-get install -y curl jq
# sudo crontab -e 編輯內容:
# # 每週日午夜 00:00 更新 GitHub Actions IP 範圍
# 0 0 * * 0 /home/zero/crontab/update_github_actions_ips.sh >> /home/zero/crontab/github_ufw.log 2>&1
