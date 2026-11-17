# cokecloud-linux

为 CokeCloud(V2Board 面板)Linux 用户提供的开源客户端方案。
把订阅与面板「客户端专用」节点合并成标准 Clash 配置,交给成熟前端使用:

```
                     ┌────────────────────────────────────┐
 订阅接口 /config ──▶│                                    │
                     │  cokectl serve (127.0.0.1:9100)    │
 面板节点列表 API ──▶│  合并 + 伪装域名映射 + 打安全补丁      │──▶ Clash Verge(推荐 UI)
                     └────────────────────────────────────┘    或 自研 GTK 客户端
```

> 推荐前端:**Clash Verge Rev**(开源,自带代理页/连接页/规则页/TUN/系统代理);
> 本仓库 `cokecloud-gui.py` 是一个轻量 GTK 备选界面。

## 它解决了什么

官方客户端(Win/Mac/安卓,内核同为 mihomo)通过面板 API 领取 120 个节点,
其中 63 个「客户端专用」节点(台湾A-D[BGP]、香港E/F/G 等,入口域名伪装成
`www.qq.com` 等)**不出现在任何订阅接口里**,且伪装域名公共 DNS 解析无效。
本工具登录面板拉取全量节点、把伪装域名映射回真实中转入口,生成标准 clash
配置,让 Linux 上获得与官方客户端完全一致的节点与体验。

调研细节见 [docs/RESEARCH.md](docs/RESEARCH.md)。

## 新设备安装

```bash
# 1. 拷贝本目录到新机器,执行:
./install.sh
# 2. 初始化(粘贴网页「我的订阅」里的订阅链接,或账号密码)
./cokectl init
# 3. 登录面板(解锁「客户端专用」节点,强烈推荐;密码交互输入、不回显)
./cokectl login
# 4A. Clash Verge 前端(推荐):
./cokectl serve start && ./cokectl verge-import
# 4B. 独立模式(不装 Verge):
./cokectl start && ./cokectl proxy on
```

## 命令速查

| 命令 | 说明 |
|---|---|
| `cokectl init / login` | 初始化订阅 / 登录面板 |
| `cokectl update` | 手动更新订阅并合并节点 |
| `cokectl serve start\|stop\|status` | 本地订阅提供器(Verge 用,默认开机自启) |
| `cokectl verge-import` | 一键唤起 Verge 导入订阅 |
| `cokectl start\|stop\|restart\|status` | 独立内核模式 |
| `cokectl mode rule\|global\|direct` | 规则/全局/直连 |
| `cokectl tun on\|off` | TUN 虚拟网卡(需 root 授权) |
| `cokectl premium / nodes / use / delay` | 节点查看与切换 |
| `cokectl test / env / proxy on\|off` | 连通性 / 终端代理 |
| `cokectl ui` | 内置 Web 面板(metacubexd) |

## 配置与数据(全部在本机)

`~/.config/cokecloud/`:`config.json`(订阅地址/面板 token/端口,程序强制 600 权限,
目录 700)、`runtime.yaml`(生成的运行配置)、`sub-raw.yaml`(订阅缓存)、
`plan.json`(套餐流量)、日志与 pid。卸载即删除该目录。

`config.json` 支持:`api_base`(面板地址;出于隐私不入库,需在本地配置,
或用环境变量 `COKECLOUD_API_BASE` 指定)、`mixed_port`、`api_port`、
`provider_port`。

## 安全与隐私

- 面板 token 等同账号凭证,仅存本机 `~/.config/cokecloud/config.json`;泄露可在
  面板「个人中心」重置订阅。
- 本地订阅提供器只监听 `127.0.0.1`;运行配置默认 `allow-lan: false`、控制接口
  仅本机 + 随机 secret。
- 本仓库不包含任何个人凭证与服务商端点(域名/端口);`bin/mihomo-bin` 为运行
  所需内核,已被 .gitignore 排除。

## 免责声明

仅供已购买订阅的用户在自有设备上使用。"CokeCloud" 名称与图标版权归其运营方所有,
仓库内图标仅作本地识别用途。请遵守所在地法律法规。
