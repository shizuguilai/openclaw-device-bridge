# OpenClaw Device Bridge — 部署与截图压缩速查

本文档集中说明：**装什么、在哪装、怎么配截图压缩**，避免与主 README 的架构长文混在一起。更新代码后若截图相关行为异常，优先对照本节。

## 1. 架构里谁需要做什么

| 组件 | 典型位置 | 与截图相关 |
|------|-----------|------------|
| **Bridge Client** | 连接 ADB 的电脑（Windows / macOS / Linux） | **必须**：`adb`、Python 依赖、`Pillow` 负责缩放与编码后再发 WebSocket。 |
| **Relay Server** | 远程 Linux（与 OpenClaw 同机常见） | 只做中转与 Console HTTP；**不执行** Pillow 逻辑，但与 Bridge 共用同一 `requirements.txt` 安装即可。 |
| **Web Console** | 常与 Relay 同进程 | 浏览器调 `GET /api/screenshot/...` 带压缩查询参数。 |

数据流：**手机 ← ADB ← Bridge（PNG → Pillow 编码）← WebSocket Base64 JSON ← Relay ← Console / Skill**。

## 2. 安装依赖（Bridge 与 Relay）

仓库根目录一份 `requirements.txt`，**在每台运行 Bridge 或 Relay 的机器上**各执行一次：

```bash
cd openclaw-device-bridge   # 本仓库根目录
python3 -m pip install -r requirements.txt
```

建议使用 **Python 3.10+**。Windows 上可在「以 ADB 所在环境为准」的 venv 里安装。

### 截图压缩关键依赖

- **`pillow>=10.2.0`**：未安装时 Bridge **仍能截图**，但只发**原始 PNG**，体积大、日志里会有 WARNING。

### 开发 / 自检（可选）

```bash
python3 -m pip install -r requirements.txt
pytest -q
```

## 3. 配置截图压缩（优先级）

**后写覆盖先写**：单次请求的参数 > `client/config/bridge.yaml` 里的 `screenshot:` 默认。

### 3.1 `client/config/bridge.yaml`（Bridge 全局默认）

取消注释顶层 `screenshot:` 示例块后按需修改：

```yaml
screenshot:
  format: jpeg       # png | jpeg | webp
  quality: 72        # jpeg/webp: 1–100；png: 映射为 zlib 压缩强度
  max_width: 1080    # 0 = 不按宽度缩放；可与 max_height 联用，按比例缩小
  max_height: 0
```

- `relay.max_ws_message_bytes`（可选）应与服务器 `RELAY_WS_MAX_MESSAGE_BYTES` 一致，避免大图 Base64 超过单帧上限被断开。
- 环境变量 **`BRIDGE_AUTH_TOKEN`**（或你在 yaml 里写的 token）须在启动 Bridge 的终端中可用（见仓库 README 安全说明）。

### 3.2 Web Console（浏览器）

在「截屏」区域设置：

- **编码**：JPEG / WebP / PNG  
- **质量**：1–100  
- **最大宽**：像素；`0` = 不缩放  

控制台默认偏「快」：**JPEG、72、1080**。

### 3.3 HTTP API（Console）

```http
GET /api/screenshot/{device_id}?format=jpeg&quality=72&max_width=1080&max_height=0
```

- Header：`X-Console-Token: <与 web_console.auth_token 一致>`  
- 可选查询参数：`bridge_id`（多 Bridge 时）

单次截图命令在 Relay 侧默认 **timeout ≈ 30s**（`timeout_ms: 30000`）；特大图 + 慢机若超时，可改为走 `POST /api/command` 自定义 `timeout_ms`。

### 3.4 直连指令（`action: screenshot`）

发往 Bridge 的 JSON 里在 `params` 中带 `format`、`quality`、`max_width`、`max_height`，与上面含义相同。

### 3.5 OpenClaw Skill（`skill/tool.py`）

环境变量（见 `skill/SKILL.md`）：

- `OPENCLAW_RELAY_CONSOLE_URL` — 默认 `http://127.0.0.1:8092`  
- `OPENCLAW_RELAY_CONSOLE_TOKEN` — 与 Console `auth_token` 一致（可与 `RELAY_AUTH_TOKEN` 同源）

`device_screenshot` 关键字参数（均有默认值）：`image_format`、`quality`、`max_width`、`max_height`。

## 4. 与旧版「几乎不压缩」行为对齐

- Console：选 **PNG**，**最大宽填 0**  
- 或 API：`?format=png&max_width=0&max_height=0`  
- 若 `bridge.yaml` 里配置了全局 `screenshot:`，又被单次请求/Console 覆盖，以**当次请求**为准。

## 5. WebSocket 单帧体积与 Relay 环境变量

截图以 Base64 嵌在 JSON 里；若超过 Relay 配置的 **`max_ws_message_bytes`**，连接可能失败或报错。服务器侧可调：

- **`RELAY_WS_MAX_MESSAGE_BYTES`** — 单帧上限（默认见 `relay/config.py`）  
- **`RELAY_WS_PORT`** — Bridge 入站 WebSocket（默认 8091）  
- **`RELAY_CONSOLE_PORT`** — Web Console HTTP（默认 8092）

更稳妥的治理是 **降低 `max_width` 或改用 JPEG/WebP**，而不是一味抬高上限。

## 6. DAG / `ScreenCaptureAgent`

DAG YAML 里 `screen_capture` 节点的 `config`（如 `format`、`quality`、`max_width`）会参与 Bridge 端编码；整条链路走 DAG 时依赖 **Bridge 已安装 Pillow** 才能做有损压缩。

## 7. 更新代码后的惯用步骤（Bridge 电脑）

```bash
git pull
python3 -m pip install -r requirements.txt   # 拉取新增 pillow 等
# 重启 Bridge Client 进程
```

Linux Relay 同理：`git pull && pip install -r requirements.txt` 后重启 Relay/Web Console。

## 8. 排错备忘

| 现象 | 可能原因 |
|------|-----------|
| 日志提示未安装 Pillow | Bridge 环境执行 `pip install -r requirements.txt` |
| WebSocket / Relay 报消息过大 | 缩小 `max_width`、改用 jpeg；或调大 `RELAY_WS_MAX_MESSAGE_BYTES` |
| 截图仍慢 | 瓶颈可能在 ADB `screencap` 或网络；先确认压缩后 `bytes_length` / `source_bytes_length` 是否已下降（API 返回字段） |
| HTTP 401 | `X-Console-Token` 与 `web_console.auth_token` 不一致 |

---

更完整的系统架构与设计背景见仓库根目录 **[README.md](./README.md)**。
