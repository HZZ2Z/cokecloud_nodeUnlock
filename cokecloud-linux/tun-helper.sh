#!/bin/bash
# CokeCloud TUN 助手(pkexec 以 root 运行)
# 用法:
#   tun-helper.sh start <内核> <配置目录> <运行配置> <日志> <pid文件>
#   tun-helper.sh stop  <pid文件> <用户uid>
set -u

case "$1" in
  start)
    CORE="$2"; CONF="$3"; CFG="$4"; LOG="$5"; PID="$6"
    pkill -f mihomo-bin 2>/dev/null || true
    sleep 0.5
    nohup "$CORE" -d "$CONF" -f "$CFG" >> "$LOG" 2>&1 &
    echo $! > "$PID"
    ;;
  stop)
    PIDF="$2"; UID_="$3"
    if [ -f "$PIDF" ]; then
        kill "$(cat "$PIDF")" 2>/dev/null || true
    fi
    pkill -f mihomo-bin 2>/dev/null || true
    sleep 0.5
    rm -f "$PIDF"
    # 配置目录归还给普通用户
    chown -R "$UID_":"$UID_" "$(dirname "$PIDF")" 2>/dev/null || true
    ;;
  *)
    echo "用法: tun-helper.sh start|stop ..." >&2
    exit 1
    ;;
esac
