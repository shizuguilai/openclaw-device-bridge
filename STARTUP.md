# 启动与部署指南（远程控制本地手机）

本文说明如何按 **README 架构**跑通整条链路：远程 Linux 上的 **Relay + Web Console**，你本地电脑上的 **Bridge Client**，通过 **ADB** 控制已连接的手机。

```
远程 Linux          你的本地电脑              手机
OpenClaw / 浏览器 ──► Relay :8091/:8092 ◄──WS──► Bridge Client ──ADB──► USB/无线调试
```

---

## 0. 准备条件

| 位置 | 要求 |
|------|------|
| **远程服务器** | Python 3.11+（与项目一致即可），能对外提供 **8091**（Bridge 连入）和 **8092**（Web 控制台，按需） |
| **本地电脑** | Python 3.11+、已安装 **adb** 且能在终端执行 `adb devices` 看到你的手机 |
| **手机** | 开启 **开发者选项** 与 **USB 调试**（或无线 ADB）；数据线或同一局域网 ADB |
| **网络** | 本地电脑能访问远程的 **8091**（出站即可，无需给本地开端口）。公网建议 **Tailscale / 内网穿透**，并自行加固 TLS（见文末） |

---

## 1. 远程 Linux：安装并启动 Relay

在服务器上克隆仓库（或同步你已有副本），进入项目根目录（含 `relay/`、`client/` 的目录）。

```bash
cd openclaw-device-bridge
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**务必设置鉴权密钥**（不要用默认弱口令）。Bridge 与 Web Console 默认共用 `RELAY_AUTH_TOKEN`；也可单独给控制台设 `RELAY_CONSOLE_TOKEN`。

```bash
export RELAY_AUTH_TOKEN='请换成一长串随机密钥'
# 可选：只改控制台 token（与 Bridge 不同）
# export RELAY_CONSOLE_TOKEN='另一串密钥'

# 可选：监听地址与端口（默认 WS 0.0.0.0:8091，控制台 0.0.0.0:8092）
# export RELAY_WS_HOST=0.0.0.0
# export RELAY_WS_PORT=8091
# export RELAY_CONSOLE_BIND=0.0.0.0
# export RELAY_CONSOLE_PORT=8092
```

启动（项目根目录下）：

```bash
python relay/main.py
```

成功后会同时监听：

- **WebSocket**：`ws://<服务器>:8091`（供本地 Bridge 连接）
- **Web Console（HTTP）**：`http://<服务器>:8092`（浏览器里点设备、发指令）

防火墙/安全组需放行 **8091**（来自你本地出口 IP 或 Tailscale 网段）以及你需要的 **8092**（仅管理网访问更安全）。

---

## 2. 本地电脑：配置 Bridge

仍在仓库根目录，编辑 `client/config/bridge.yaml`：

1. **`relay.url`**：填远程 WebSocket 地址，例如  
   `ws://你的服务器IP或域名:8091`  
   若前面有 HTTPS 反代且已配置 WSS，则使用 `wss://...`（需与证书域名一致）。
2. **`relay.auth_token`**：与远程 **`RELAY_AUTH_TOKEN`** 一致。模板里为 `${BRIDGE_AUTH_TOKEN}`，推荐在本地 shell 里导出环境变量，避免明文写进文件：

```bash
export BRIDGE_AUTH_TOKEN='与远程 RELAY_AUTH_TOKEN 完全相同'
```

3. **`bridge.id`**：多台本地电脑同时连时，请改成互不相同的 ID（例如 `home-mac-001`）。

确认手机已被 ADB 识别：

```bash
adb devices
```

启动 Bridge（项目根目录、已 `pip install -r requirements.txt` 的同一环境）：

```bash
cd openclaw-device-bridge
source .venv/bin/activate   # 若使用 venv
python client/main.py
```

日志里应出现已连接 Relay、设备发现/上报等信息。此时在远程 **Web Console** 的设备列表中应能看到你的手机。

---

## 3. 验证：Web 控制台

浏览器打开：

```text
http://<服务器IP或域名>:8092
```

首次会 **提示输入 Console Token**：与 **`RELAY_CONSOLE_TOKEN`** 相同；若未单独设置，则与 **`RELAY_AUTH_TOKEN`** 相同。

能列出 Bridge、设备，并能截图 / 下发 tap 等，即表示 **Relay ↔ Bridge ↔ ADB** 已打通。

---

## 4. 远程 OpenClaw（可选）

若要让 **OpenClaw** 通过本仓库自带的 Skill 调设备，需把 Skill 目录部署到 OpenClaw 的技能路径，并配置环境变量（与 `skill/tool.py` 一致）：

| 变量 | 含义 |
|------|------|
| `OPENCLAW_RELAY_CONSOLE_URL` | Web Console 基址，例如 `http://127.0.0.1:8092`（OpenClaw 与 Relay **同机**时） |
| `OPENCLAW_RELAY_CONSOLE_TOKEN` 或 `RELAY_CONSOLE_TOKEN` 或 `RELAY_AUTH_TOKEN` | 与控制台校验用的 token 一致 |

OpenClaw 与 Relay **同机**时用 `http://127.0.0.1:8092` 即可；若将来拆机部署，把 URL 改成可访问的 Console 地址。

---

## 5. 常见问题

**Bridge 连不上 Relay**

- 检查远程 **8091** 是否监听、`relay.url` 是否写对（IP/域名、端口、`ws`/`wss`）。
- 检查 **`BRIDGE_AUTH_TOKEN` 与 `RELAY_AUTH_TOKEN` 是否一致**。
- 公司网络可能拦截出站 WebSocket，可换手机热点或 Tailscale 试。

**控制台 401 / 设备列表空**

- 确认浏览器里输入的 token 与 `RELAY_CONSOLE_TOKEN` 或 `RELAY_AUTH_TOKEN` 一致。
- 确认 **Bridge 进程在跑** 且 `adb devices` 里设备为 `device` 状态。

**只想本机试跑 Relay + Bridge**

- 远程与本地同一台机器时：`relay.url` 使用 `ws://127.0.0.1:8091`，先 `python relay/main.py`，再开另一终端 `python client/main.py`。

---

## 6. 安全与上线建议

- **生产环境务必更换**默认示例 token，并限制 **8092** 访问来源（防火墙、仅 Tailscale IP）。
- 公网传输建议：**Tailscale** 或 **SSH 隧道 / 反向代理 + TLS**；本仓库默认是明文 `ws://` / `http://`，适合内网或加密隧道内使用。
- 更细的架构说明见根目录 **[README.md](./README.md)**。
