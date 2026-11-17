# 逆向调研笔记:CokeCloud 官方客户端与节点体系

> 以下信息全部来自对公开分发客户端(APK/EXE)与公开网页前端的静态分析,以及对本机已购
> 订阅的黑盒测试,无任何攻击性行为。目的:让 Linux 用户获得与官方客户端一致的体验。

## 1. 官方客户端架构

- Android APK `com.nexgen.cokecloud`(Tauri 2 移动壳):
  - `libclash.so`(46MB):**mihomo (Clash Meta) 内核**,Go 符号
    `github.com/metacubex/mihomo/...`
  - `libnexgen_client_react_lib.so`:Tauri/wry 运行时 + React 前端(资源 brotli 内嵌)
  - `libnexgen_core.so`:Rust↔Java JNI 桥(SetupCore/UpdateConfig/ChangeProxy/TestDelay…)
  - 配置落盘加密:`NEXGEN_CORE_CONFIG_V1:` / `NEXGEN_CORE_KEY_V1:`(client-proxy.yaml)
- Windows 安装包为 NSIS(Tauri 打包),macOS 为 pkg。
- `tauri.conf.json` 中含 Linux(appimage/deb)打包配置,**但官方未发布 Linux 版**。
- 官方下载地址(公开,见官网「使用文档」):安卓 APK / Win x64+arm64 setup / Mac pkg。

## 2. 两层节点体系(核心发现)

| 渠道 | 内容 |
|---|---|
| 订阅接口 `GET /config?token=…`(端口 1000) | 57 个真实节点;**所有 UA 返回内容一致**(仅 `client-fingerprint` 每次随机 chrome/edge/safari/firefox/ios/qq);UA=`sing-box` 会 500;UA=`mihomo/clash*/karing` 返回完整 clash YAML,其余 UA 返回 base64 节点列表 |
| 面板 API `GET /api/v1/user/server/fetch`(登录后) | 120 个节点,其中 63 个 tags=["客户端专用"] |

「客户端专用」节点 = 同一服务的**伪装域名入口**(host 如 `www.qq.com`)与
若干新增地区(台湾A-D[BGP]、香港E/F/G)。V2Board 的订阅出口不含这些条目,
因此通用客户端(导入订阅)永远看不到它们。

## 3. 伪装域名的工作机制(关键)

- `www.qq.com` 用公共 DNS 解析到腾讯 CDN IP,直接 ss 拨号**必然超时**。
- 端口与订阅 BGP 入口体系完全一致(如香港A[BGP]:waic…:21553 与 www.qq.com:21553)。
- 实测:用订阅中转域名解析出的入口 IP 直连「客户端专用」端口,**全部 TCP 可达**。
- 结论:官方客户端内部把伪装域名映射到真实中转入口(其私有 DoH
  `koala.madns-lemon.site:2443` 等实测不可达,是死胡同,不是机制本体)。
- 本工具的实现:合并时把非中转域名统一替换为订阅中出现频次最高的 ss 中转域名。

## 4. 节点构成(实测)

- ss(chacha20-ietf-poly1305):BGP 中转,入口域名单一、端口区分地区;密码=账号 UUID
- vless:REALITY(xtls-rprx-vision),tls_settings 带 public_key/short_id/server_name;
  客户端 API 中这些节点 rate=0.1(0.1x 计费)
- 策略组模板把全部节点复制进每一个组(节点选择/自动选择/故障转移/各分流组),
  因此合并新节点时必须遍历所有「全量型」组追加,否则规则模式下分流组里看不到。

## 5. 复刻方案

Linux 上 = mihomo 内核 + (订阅 ∪ server/fetch 合并) 即可 100% 等效官方客户端:
本目录的 `cokectl` 实现,配置交给 Clash Verge(mature UI)或自研 GUI 均可。
