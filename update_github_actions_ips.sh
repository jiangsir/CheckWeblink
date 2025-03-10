#!/bin/bash
# 檔名: update_github_actions_ips.sh

# 下載 GitHub IP 範圍
GITHUB_IPS=$(curl -s https://api.github.com/meta | jq -r '.actions[]')

# 移除舊有的 GitHub Actions 規則
sudo ufw status numbered | grep 'GitHub Actions' | awk '{print $1}' | sort -r | sed 's/]//' | xargs -I{} sudo ufw delete {}

# 分別處理 IPv4 和 IPv6 地址
IPV4_RANGES=()
IPV6_RANGES=()

for ip in $GITHUB_IPS; do
  if [[ $ip =~ .*:.* ]]; then
    IPV6_RANGES+=("$ip")
  else
    IPV4_RANGES+=("$ip")
  fi
done

# 添加 IPv4 規則，每次添加最多 10 個
for i in $(seq 0 10 ${#IPV4_RANGES[@]}); do
  batch=("${IPV4_RANGES[@]:i:10}")
  if [ ${#batch[@]} -gt 0 ]; then
    ip_list=$(IFS=, ; echo "${batch[*]}")
    sudo ufw allow proto tcp from $ip_list to any port 80,443 comment 'GitHub Actions IPv4'
  fi
done

# 添加 IPv6 規則，每次添加最多 10 個
for i in $(seq 0 10 ${#IPV6_RANGES[@]}); do
  batch=("${IPV6_RANGES[@]:i:10}")
  if [ ${#batch[@]} -gt 0 ]; then
    ip_list=$(IFS=, ; echo "${batch[*]}")
    sudo ufw allow proto tcp from $ip_list to any port 80,443 comment 'GitHub Actions IPv6'
  fi
done

sudo ufw reload

echo "GitHub Actions IP ranges updated in UFW at $(date)"

# 安裝套件 
# sudo apt-get install -y curl jq
# sudo crontab -e 編輯內容:
# # 每週日午夜 00:00 更新 GitHub Actions IP 範圍
# 0 0 * * 0 /home/zero/crontab/update_github_actions_ips.sh >> /home/zero/crontab/github_ufw.log 2>&1
