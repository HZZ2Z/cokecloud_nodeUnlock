#!/usr/bin/env bash
# CokeCloud Linux 一键安装(新设备复用)
# 用法: 把整个 cokecloud-linux 目录拷到新机器任意路径,执行 ./install.sh
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORE="$DIR/bin/mihomo-bin"
MIHOMO_VER="v1.19.34"
MIRROR="https://ghfast.top"

# ---------- 依赖检查
echo "== 依赖检查 =="
PY=$(command -v /usr/bin/python3 || command -v python3)
command -v curl >/dev/null || { echo "缺少 curl"; exit 1; }
"$PY" -c "import yaml" 2>/dev/null && HAVE_YAML=1 || HAVE_YAML=0
[ "$HAVE_YAML" = "1" ] || echo "提示: 无 PyYAML,节点合并功能受限(可 pip3 install pyyaml)"

# ---------- 架构
case "$(uname -m)" in
  x86_64)  ARCH=amd64 ;;
  aarch64|arm64) ARCH=arm64 ;;
  *) echo "不支持的架构: $(uname -m)"; exit 1 ;;
esac

# ---------- 内核
if [ -x "$CORE" ]; then
  echo "内核已存在: $CORE"
else
  mkdir -p "$DIR/bin"
  URL="$MIRROR/https://github.com/MetaCubeX/mihomo/releases/download/$MIHOMO_VER/mihomo-linux-$ARCH-$MIHOMO_VER.gz"
  ALT="https://github.com/MetaCubeX/mihomo/releases/download/$MIHOMO_VER/mihomo-linux-$ARCH-$MIHOMO_VER.gz"
  echo "下载 mihomo $MIHOMO_VER ($ARCH) ..."
  curl -sL -m 600 "$URL" -o /tmp/mihomo.gz || curl -sL -m 600 "$ALT" -o /tmp/mihomo.gz
  gunzip -f /tmp/mihomo.gz && mv /tmp/mihomo "$CORE" && chmod +x "$CORE"
fi
"$CORE" -v | head -1

# ---------- geo 数据(不存在才下载)
GEO_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/cokecloud"
mkdir -p "$GEO_DIR"
for f in geoip.metadb geosite.dat; do
  if [ ! -s "$GEO_DIR/$f" ]; then
    echo "下载 $f ..."
    R="https://ghfast.top/https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/$f"
    A="https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/$f"
    curl -sL -m 300 "$R" -o "$GEO_DIR/$f" || curl -sL -m 300 "$A" -o "$GEO_DIR/$f"
  fi
done

# ---------- 桌面入口(可选,需要 PyGObject)
if "$PY" -c "import gi" 2>/dev/null; then
  APPDIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
  mkdir -p "$APPDIR"
  cat > "$APPDIR/cokecloud.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=CokeCloud
Comment=CokeCloud Linux 客户端
Exec=$PY $DIR/cokecloud-gui.py
Icon=cokecloud
Terminal=false
Categories=Network;
StartupWMClass=CokeCloud
EOF
  ICO="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
  mkdir -p "$ICO"
  "$PY" - "$DIR" "$ICO" <<'PYEOF'
import sys
from PIL import Image
d, out = sys.argv[1], sys.argv[2]
img = Image.open(d + "/assets/icon-cdn.png")
img.resize((256, 256), Image.LANCZOS).save(out + "/cokecloud.png")
PYEOF
  echo "桌面入口已安装(含图形客户端)"
else
  echo "未检测到 PyGObject,跳过图形客户端入口(命令行模式可用)"
fi

# ---------- 初始化
echo
echo "== 安装完成 =="
echo "接下来:"
echo "  1) $DIR/cokectl init      # 粘贴订阅链接 或 账号密码登录"
echo "  2) $DIR/cokectl login     # 登录面板(解锁「客户端专用」节点,可选但推荐)"
echo "  3) $DIR/cokectl serve start && $DIR/cokectl verge-import"
echo "     # 或独立模式: $DIR/cokectl start && $DIR/cokectl proxy on"
