# OpenClaw Device Bridge 架构设计

## 1. 需求场景

用户在远程 Linux 服务器上运行 OpenClaw（AI Agent），希望通过 OpenClaw 控制本地电脑连接的物理设备（如通过 ADB 连接的手机）。

**核心链路（混合架构）：**
```
远程 Linux:  OpenClaw ◄──localhost──► Bridge Relay Server(:8091)
                                          ▲
                                          │ WebSocket (wss://)
                                          │ (本地主动连出，无需开端口)
                                          │
本地电脑:                        Bridge Client ──ADB──> 手机
```

**为什么选择方案（混合架构）：**
- 本地电脑通常在 NAT 后面（家庭/公司网络），远程服务器无法直接连过来
- 本地 Bridge Client 主动向远程发起 WebSocket 连接（出站连接），无需本地开端口或配置穿透
- Linux 上的 Bridge Relay 和 OpenClaw 在同一台机器，走 localhost 通信，零网络障碍
- 如果未来用 Tailscale 组网，也可以直连，Relay 层可以透明退化

**关键约束：**
- 手机无法直接连接远程服务器，必须通过本地电脑中转
- 本地电脑是 macOS/Windows/Linux，通过 USB/WiFi ADB 连接手机
- 远程 OpenClaw 需要实时发送指令、获取屏幕截图、读取设备状态
- 需要支持多设备（多台手机、未来可能扩展到其他设备类型）
- 参考 kuangkuang 的设计理念：DAG 驱动、配置化、结构化日志、插件化 Agent

## 2. 架构总览（方案 C - 混合架构）

系统由四部分组成：

| 组件 | 部署位置 | 职责 |
|-----|---------|------|
| **Bridge Relay Server** | 远程 Linux（和 OpenClaw 同机器） | 消息中转，对 OpenClaw 暴露 MCP Tool，对外暴露 WebSocket 端口等待 Bridge Client 连入 |
| **Web Console** | 远程 Linux（和 Relay 同进程或独立服务） | Web 控制台，提供人工直接下发指令的界面，任何设备的浏览器均可访问 |
| **Bridge Client** | 本地电脑 | 主动 WebSocket 连接 Relay，管理本地设备，执行 ADB 操作 |
| **OpenClaw + Device Skill** | 远程 Linux | AI Agent，通过 Skill 调用 Relay 提供的工具 |

**两条指令路径并存：**
1. **AI 路径**：OpenClaw → Skill → Relay → Bridge Client → 工作手机
2. **人工路径**：任意设备浏览器 → Web Console → Relay → Bridge Client → 工作手机

```
┌───────────────────────────────────────────────────────────────────────┐
│                          远程 Linux 服务器                              │
│                                                                        │
│  ┌─────────────────────┐                                               │
│  │   OpenClaw Gateway   │                                               │
│  │  ┌────────┐         │                                               │
│  │  │AI Model│         │                                               │
│  │  └───┬────┘         │                                               │
│  │  ┌───▼────────────┐ │                                               │
│  │  │Device Control  │ │    ┌─────────────────────────────────────┐   │
│  │  │Skill           │ │    │       Bridge Relay Server (:8091)    │   │
│  │  └───────┬────────┘ │    │                                      │   │
│  │   localhost调用      │    │  ┌──────────┐  ┌─────────────────┐  │   │
│  └──────────┼───────────┘    │  │ MCP Tool │  │ WebSocket Server│  │   │
│             │                │  │ Interface│  │ (等待Bridge连入) │  │   │
│             └───────────────►│  └────┬─────┘  └───────┬─────────┘  │   │
│                              │       │                │             │   │
│                              │  ┌────▼────────────────▼──────────┐ │   │
│  ┌─────────────────────┐    │  │       Session Manager           │ │   │
│  │  Web Console (:8092) │    │  │   (管理多Bridge + 消息路由)      │ │   │
│  │  ┌────────────────┐ │    │  └─────────────────────────────────┘ │   │
│  │  │ 设备列表/状态   │ │    │       ▲                              │   │
│  │  │ 实时截屏预览    │ │    │       │ 内部 API                     │   │
│  │  │ 操作按钮面板    │ │    └───────┼─────────────────────────────┘   │
│  │  │ 指令历史/日志   │ │            │                                  │
│  │  │ DAG 执行触发    │ │            │                                  │
│  │  └───────┬────────┘ │            │                                  │
│  │          │ HTTP API  │            │                                  │
│  │          └───────────┼────────────┘                                  │
│  └──────────────────────┘                                               │
└───────────────────────────────────────┬───────────────────────────────┘
                                        │
                             WebSocket (wss://:8091)
                          (本地 Bridge Client 主动连出)
                                        │
┌───────────────────────────────────────┼───────────────────────────────┐
│                      本地电脑          │                               │
│  ┌────────────────────────────────────▼─────────────────────────────┐ │
│  │                   Bridge Client (核心组件)                         │ │
│  │                                                                    │ │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐       │ │
│  │  │ Relay       │  │ Device       │  │ Task               │       │ │
│  │  │ Connector   │  │ Manager      │  │ Executor           │       │ │
│  │  │ (WS Client) │  │ (设备管理)    │  │ (DAG执行引擎)      │       │ │
│  │  └──────┬──────┘  └──────┬───────┘  └────────┬───────────┘       │ │
│  │         │                │                    │                   │ │
│  │  ┌──────▼────────────────▼────────────────────▼────────────────┐  │ │
│  │  │                    Agent Pipeline                            │  │ │
│  │  │  ┌───────────┐  ┌────────────┐  ┌────────────────────┐      │  │ │
│  │  │  │ Screen    │  │ UI Parse   │  │ ADB Action Agent   │      │  │ │
│  │  │  │ Capture   │  │ Agent      │  │ (tap/swipe/type)   │      │  │ │
│  │  │  └───────────┘  └────────────┘  └────────────────────┘      │  │ │
│  │  └──────────────────────────┬─────────────────────────────────┘  │ │
│  │                             │                                     │ │
│  │  ┌──────────────────────────▼─────────────────────────────────┐  │ │
│  │  │                    Device Drivers                           │  │ │
│  │  │  ┌────────────┐  ┌────────────┐  ┌──────────────────┐      │  │ │
│  │  │  │ ADB Driver │  │ Appium     │  │ Future Drivers   │      │  │ │
│  │  │  └────────────┘  └────────────┘  └──────────────────┘      │  │ │
│  │  └──────────────────────────┬─────────────────────────────────┘  │ │
│  └─────────────────────────────┼─────────────────────────────────────┘ │
│                                │                                       │
│               ┌────────────────┼────────────────┐                     │
│               ▼                ▼                 ▼                      │
│           ┌───────┐       ┌───────┐        ┌───────┐                 │
│           │Phone A│       │Phone B│        │Phone C│                 │
│           └───────┘       └───────┘        └───────┘                 │
└────────────────────────────────────────────────────────────────────────┘

外部访问：
┌──────────┐
│ 你的手机   │ ── 浏览器访问 http(s)://linux-server:8092 ──> Web Console
│ (随身设备) │
└──────────┘
```

**连接时序：**
```
1. 启动 Bridge Relay Server (Linux :8091) + Web Console (:8092)
2. OpenClaw 加载 Device Control Skill，Skill 内部连接 Relay (localhost:8091)
3. 启动 Bridge Client (本地电脑)，主动 WebSocket 连接 Relay (远程IP:8091)
4. Relay 建立双向通道：OpenClaw Skill ◄──► Relay ◄──► Bridge Client
5. 指令路径 A（AI）：用户对 OpenClaw 说 "截个图" → Skill → Relay → Bridge → ADB → 返回
6. 指令路径 B（人工）：手机浏览器打开 Web Console → 点击截图按钮 → Relay → Bridge → ADB → 返回网页显示
```

## 3. 核心模块设计

### 3.1 项目结构（参考 kuangkuang 风格）

```
openclaw-device-bridge/
├── relay/                         # Bridge Relay Server（部署在远程 Linux）
│   ├── __init__.py
│   ├── relay_server.py            # Relay 主服务（WebSocket Server + 内部 API）
│   ├── session_manager.py         # Bridge Client 会话管理（支持多 Bridge）
│   ├── mcp_tool.py                # MCP Tool 接口（供 OpenClaw Skill 调用）
│   ├── protocol.py                # 通信协议定义（消息格式，与 client 共用）
│   ├── config.py                  # Relay 配置
│   ├── web_console/               # Web 控制台
│   │   ├── __init__.py
│   │   ├── app.py                 # FastAPI 应用（HTTP API + WebSocket 推送）
│   │   ├── auth.py                # 登录认证（token/密码）
│   │   └── static/                # 前端静态文件
│   │       ├── index.html         # 主页面
│   │       ├── style.css          # 样式
│   │       └── app.js             # 前端逻辑（设备列表、截图、操作面板）
│   └── main.py                    # Relay + Web Console 统一启动入口
│
├── client/                        # Bridge Client（部署在本地电脑）
│   ├── core/                      # 核心框架（从 kuangkuang 适配）
│   │   ├── __init__.py
│   │   ├── agent.py               # Agent 基类
│   │   ├── context.py             # 任务上下文（dict-based，去掉 Protobuf）
│   │   ├── dag.py                 # DAG 定义（复用）
│   │   ├── dag_factory.py         # DAG 工厂（复用）
│   │   ├── executor.py            # DAG 执行器（复用）
│   │   ├── config_manager.py      # 配置管理器
│   │   ├── logger.py              # 日志系统（复用 + 扩展）
│   │   ├── exceptions.py          # 异常定义
│   │   └── utils.py               # 工具函数
│   │
│   ├── bridge/                    # Bridge 连接层
│   │   ├── __init__.py
│   │   ├── relay_connector.py     # WebSocket Client，连接远程 Relay Server
│   │   ├── device_manager.py      # 设备管理器（发现/注册/状态监控）
│   │   ├── task_router.py         # 任务路由（将远程指令分发到对应设备）
│   │   └── heartbeat.py           # 心跳保活 & 断线重连
│   │
│   ├── drivers/                   # 设备驱动层
│   │   ├── __init__.py
│   │   ├── base_driver.py         # 驱动基类
│   │   ├── adb_driver.py          # ADB 驱动（Android 手机）
│   │   └── screen_parser.py       # 屏幕解析（accessibility tree / screenshot）
│   │
│   ├── agents/                    # 业务 Agent
│   │   ├── __init__.py
│   │   ├── screen_capture_agent.py
│   │   ├── ui_parse_agent.py
│   │   ├── adb_action_agent.py
│   │   ├── app_launch_agent.py
│   │   └── device_info_agent.py
│   │
│   ├── config/                    # 配置文件
│   │   ├── bridge.yaml            # Bridge Client 主配置
│   │   ├── agents/
│   │   │   └── agents.yaml
│   │   └── dags/
│   │       ├── screen_and_act.yaml
│   │       └── device_check.yaml
│   │
│   └── main.py                    # Bridge Client 启动入口
│
├── skill/                         # OpenClaw Device Control Skill（部署在远程 Linux）
│   ├── SKILL.md                   # Skill 描述文件
│   └── tool.py                    # Tool 实现（调用 Relay 内部 API）
│
├── shared/                        # 共享模块（Relay 和 Client 公用）
│   ├── __init__.py
│   └── protocol.py                # 通信协议定义（消息格式）
│
├── tests/
│   ├── test_relay_server.py
│   ├── test_relay_connector.py
│   ├── test_adb_driver.py
│   ├── test_device_manager.py
│   └── test_agents.py
│
├── requirements.txt
└── README.md
```

### 3.2 通信协议设计 (bridge/protocol.py)

远程 OpenClaw 和本地 Bridge 之间通过 WebSocket 通信，消息格式为 JSON：

```python
# 远程 -> 本地：指令消息
{
    "type": "command",
    "id": "cmd-uuid-001",
    "timestamp": 1711500000000,
    "device_id": "PIXEL_7_abc123",   # 目标设备，"*" 表示广播
    "action": "tap",                  # 动作类型
    "params": {                       # 动作参数
        "x": 540,
        "y": 1200
    },
    "timeout_ms": 5000,
    "dag_name": null                  # 可选：使用预定义 DAG 流程
}

# 本地 -> 远程：结果消息
{
    "type": "result",
    "id": "cmd-uuid-001",
    "timestamp": 1711500001234,
    "device_id": "PIXEL_7_abc123",
    "status": "success",              # success / error / timeout
    "data": {                         # 返回数据
        "screenshot_base64": "...",
        "ui_elements": [...],
        "action_result": "ok"
    },
    "execution_time_ms": 1234,
    "logs": [...]                     # 结构化日志
}

# 本地 -> 远程：设备状态上报
{
    "type": "device_status",
    "timestamp": 1711500000000,
    "devices": [
        {
            "device_id": "PIXEL_7_abc123",
            "model": "Pixel 7",
            "status": "online",       # online / offline / busy
            "battery": 85,
            "screen_size": "1080x2400",
            "android_version": "14"
        }
    ]
}

# 心跳
{
    "type": "heartbeat",
    "timestamp": 1711500000000,
    "bridge_id": "macbook-pro-001"
}
```

### 3.3 Bridge Relay Server (relay/relay_server.py)

运行在远程 Linux 上，充当 OpenClaw 和本地 Bridge Client 之间的消息中转站：

```python
class BridgeRelayServer:
    """
    Bridge Relay Server - 消息中转服务

    部署在远程 Linux 上（和 OpenClaw 同一台机器），职责：
    1. 对外暴露 WebSocket Server (:8091)，等待 Bridge Client 主动连入
    2. 对内提供 HTTP/函数调用接口，供 OpenClaw Skill 调用
    3. 维护 Bridge Client 会话（支持多个 Bridge，即多台本地电脑）
    4. 消息转发：Skill 的指令 → 对应 Bridge Client，结果 → 回传 Skill
    5. Bridge Client 状态管理（在线/离线/心跳超时）
    """

    def __init__(self, config: dict):
        self.host = config.get("host", "0.0.0.0")
        self.port = config.get("port", 8091)
        self.auth_token = config["auth_token"]

    async def start(self):
        """启动 WebSocket Server，等待 Bridge Client 连入"""

    async def handle_client(self, websocket):
        """处理 Bridge Client 连接（认证、消息收发）"""

    async def send_command(self, bridge_id: str, command: dict) -> dict:
        """发送指令到指定 Bridge Client 并等待结果（供 Skill 调用）"""

    def list_bridges(self) -> list:
        """列出所有已连接的 Bridge Client"""

    def list_devices(self, bridge_id: str = None) -> list:
        """列出指定 Bridge（或所有 Bridge）的设备"""
```

### 3.4 Relay Connector (client/bridge/relay_connector.py)

本地 Bridge Client 的 WebSocket 客户端，主动连接远程 Relay Server：

```python
class RelayConnector:
    """
    WebSocket 客户端 - 主动连接远程 Bridge Relay Server

    功能：
    - 主动发起 WebSocket 连接到远程 Relay (wss://server:8091)
    - 自动断线重连（指数退避）
    - 心跳保活
    - 设备状态上报
    - Token 认证
    """

    def __init__(self, config: dict):
        self.relay_url = config["relay_url"]      # wss://remote-server:8091
        self.auth_token = config["auth_token"]
        self.bridge_id = config["bridge_id"]
        self.heartbeat_interval = config.get("heartbeat_interval", 30)
        self.reconnect_max_delay = config.get("reconnect_max_delay", 60)

    async def connect(self):
        """建立 WebSocket 连接，自动重连"""

    async def send_result(self, result: dict):
        """发送执行结果到 Relay"""

    async def send_device_status(self, devices: list):
        """上报设备状态"""

    async def on_command(self, callback):
        """注册指令回调"""
```

### 3.5 Device Manager (client/bridge/device_manager.py)

管理本地连接的所有设备：

```python
class DeviceManager:
    """
    设备管理器

    功能：
    - 自动发现 ADB 设备（定期 adb devices）
    - 设备注册/注销
    - 设备状态监控（online/offline/busy）
    - 设备信息采集（型号、Android版本、屏幕分辨率等）
    - 设备锁（防止并发操作同一设备）
    """

    def __init__(self, config: dict):
        self.poll_interval = config.get("poll_interval", 5)
        self._devices: Dict[str, DeviceInfo] = {}
        self._device_locks: Dict[str, asyncio.Lock] = {}

    async def start_discovery(self):
        """启动设备发现循环"""

    def get_device(self, device_id: str) -> DeviceInfo:
        """获取设备信息"""

    def list_devices(self) -> List[DeviceInfo]:
        """列出所有设备"""

    async def acquire_device(self, device_id: str) -> AsyncContextManager:
        """获取设备锁（防止并发冲突）"""
```

### 3.6 ADB Driver (client/drivers/adb_driver.py)

封装 ADB 操作：

```python
class ADBDriver(BaseDriver):
    """
    ADB 设备驱动

    封装所有 ADB 操作，提供统一接口：
    - 屏幕截图
    - UI Automator dump（accessibility tree）
    - 点击/滑动/输入
    - App 启动/停止
    - 文件推送/拉取
    - Shell 命令执行
    """

    def __init__(self, device_id: str, adb_path: str = "adb"):
        self.device_id = device_id
        self.adb_path = adb_path

    async def screenshot(self) -> bytes:
        """截取屏幕截图（PNG bytes）"""

    async def dump_ui(self) -> str:
        """Dump UI hierarchy (XML)"""

    async def tap(self, x: int, y: int):
        """点击屏幕坐标"""

    async def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300):
        """滑动"""

    async def input_text(self, text: str):
        """输入文本"""

    async def key_event(self, keycode: int):
        """发送按键事件"""

    async def launch_app(self, package: str, activity: str = None):
        """启动应用"""

    async def shell(self, command: str) -> str:
        """执行 Shell 命令"""

    async def get_device_info(self) -> dict:
        """获取设备信息"""
```

### 3.7 Agent Pipeline（复用 kuangkuang 模式）

核心思路：将 OpenClaw 的远程指令转化为本地 DAG 执行。

**示例 DAG：截屏 + UI解析 + 智能操作**

```yaml
# config/dags/screen_and_act.yaml
name: screen_and_act
executor: AsyncExecutor

agents:
  - name: screen_capture
    type: ScreenCaptureAgent
    depends_on: []
    config:
      format: png
      quality: 80

  - name: ui_parse
    type: UIParseAgent
    depends_on: [screen_capture]
    config:
      parse_mode: accessibility_tree   # accessibility_tree / ocr / hybrid
      max_elements: 50

  - name: adb_action
    type: ADBActionAgent
    depends_on: [ui_parse]
    config:
      timeout: 5000
```

### 3.8 Task Router (client/bridge/task_router.py)

将远程指令路由到正确的处理流程：

```python
class TaskRouter:
    """
    任务路由器

    根据远程指令类型，决定执行方式：
    1. 简单指令（tap/swipe/type）→ 直接调用 ADB Driver
    2. 复合指令（打开App搜索xxx）→ 通过 DAG 执行
    3. 查询指令（截图/获取UI）→ 调用对应 Agent
    """

    # 指令类型 -> 处理方式映射
    ROUTE_TABLE = {
        # 简单 ADB 指令 -> 直接执行
        "tap": "direct",
        "swipe": "direct",
        "input_text": "direct",
        "key_event": "direct",
        "launch_app": "direct",
        "shell": "direct",

        # 采集类指令 -> 单 Agent
        "screenshot": "agent:ScreenCaptureAgent",
        "dump_ui": "agent:UIParseAgent",
        "device_info": "agent:DeviceInfoAgent",

        # 复合任务 -> DAG
        "screen_and_act": "dag:screen_and_act",
        "app_automation": "dag:app_automation",

        # 自然语言指令 -> 先由远程 AI 解析为具体步骤
        "natural_language": "dag:nl_to_actions",
    }

    async def route(self, command: dict, device_manager: DeviceManager) -> dict:
        """路由并执行指令"""
```

### 3.9 日志系统（扩展 kuangkuang logger）

```python
# 复用 kuangkuang 日志系统，增加以下扩展：

# 1. 远程日志上报：关键日志通过 WebSocket 发送到远程 OpenClaw
# 2. 设备维度日志：每个设备独立日志文件
# 3. 操作审计日志：记录所有 ADB 操作（安全审计）

# 日志目录结构：
# logs/
# ├── bridge.log              # Bridge 主日志
# ├── gateway.log             # WebSocket 通信日志
# ├── devices/
# │   ├── PIXEL_7_abc123.log  # 设备级别日志
# │   └── SAMSUNG_S24_def456.log
# ├── audit/
# │   └── operations.log      # 操作审计日志
# └── dags/
#     └── *.md                # DAG 可视化（复用 kuangkuang）
```

配置文件 `client/config/bridge.yaml`：

```yaml
# Bridge Client 主配置
bridge:
  id: "macbook-pro-001"
  name: "KuangKuang's MacBook"

# 远程 Relay Server 连接
relay:
  url: "wss://your-server.com:8091"
  auth_token: "${BRIDGE_AUTH_TOKEN}"
  heartbeat_interval: 30    # 秒
  reconnect_max_delay: 60   # 最大重连间隔
  reconnect_base_delay: 1   # 初始重连间隔

# 设备管理
devices:
  adb_path: "adb"           # ADB 路径
  poll_interval: 5           # 设备发现轮询间隔（秒）
  auto_discover: true        # 自动发现新设备
  allowed_devices: []        # 白名单（空=允许所有）

# 任务执行
executor:
  default: AsyncExecutor
  timeout: 30.0
  max_concurrent_tasks: 5    # 最大并发任务数

# 日志
logging:
  level: INFO
  format: '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s'
  file:
    enabled: true
    path: logs/bridge.log
    rotation: time
    when: H
    interval: 1
    backup_count: 72
  console:
    enabled: true
  # 设备日志
  device_log:
    enabled: true
    dir: logs/devices
  # 审计日志
  audit_log:
    enabled: true
    path: logs/audit/operations.log

# 安全
security:
  allowed_actions:            # 允许的操作类型（白名单）
    - tap
    - swipe
    - input_text
    - screenshot
    - dump_ui
    - launch_app
    - key_event
    - device_info
  blocked_packages: []        # 禁止操作的 App 包名
  require_confirmation: false # 敏感操作是否需要确认
  max_shell_timeout: 10       # Shell 命令最大超时（秒）
```

### 3.10 启动入口

**Relay Server + Web Console 启动 (relay/main.py) - 远程 Linux 上运行：**

```python
async def main():
    """Relay Server + Web Console 主入口"""

    # 1. 加载配置
    config = load_relay_config()

    # 2. 初始化日志
    setup_logging(config)

    # 3. 启动 Relay Server
    relay = BridgeRelayServer(config)

    # 4. 启动 Web Console（共享 Relay 实例）
    web_console = WebConsole(relay, config.get("web_console", {}))

    await asyncio.gather(
        relay.start(),        # WebSocket Server on :8091
        web_console.start(),  # HTTP Server on :8092
    )
```

**Bridge Client 启动 (client/main.py) - 本地电脑上运行：**

```python
async def main():
    """Bridge Client 主入口"""

    # 1. 加载配置
    config_manager = ConfigManager()
    config_manager.load_bridge_config()

    # 2. 初始化日志
    setup_logging(config_manager)

    # 3. 初始化设备管理器
    device_manager = DeviceManager(config_manager.device_config)
    await device_manager.start_discovery()

    # 4. 初始化任务路由
    task_router = TaskRouter(config_manager, device_manager)

    # 5. 连接远程 Relay Server
    relay_connector = RelayConnector(config_manager.relay_config)

    # 6. 注册指令回调
    relay_connector.on_command(task_router.route)

    # 7. 启动
    await asyncio.gather(
        relay_connector.connect(),                          # WebSocket 连接
        device_manager.monitor_loop(),                      # 设备监控
        relay_connector.heartbeat_loop(),                   # 心跳
        relay_connector.status_report_loop(device_manager), # 状态上报
    )
```

### 3.11 Web Console (relay/web_console/)

部署在远程 Linux 上，提供人工直接控制设备的 Web 界面。任何设备（手机、平板、另一台电脑）通过浏览器访问即可操作。

**技术选型：** 后端使用 FastAPI（和 Relay Server 同进程），前端使用轻量 HTML + JS（无需 React/Vue 重框架）。

```python
class WebConsole:
    """
    Web 控制台

    提供 HTTP API + 静态页面，功能：
    1. 设备仪表盘：查看所有 Bridge、设备状态
    2. 实时截屏：按需截取设备屏幕，点击图片直接转为 tap 坐标
    3. 操作面板：手动下发 tap/swipe/type/launch 等指令
    4. DAG 触发：选择预定义 DAG 流程并执行
    5. 操作历史：查看指令执行记录和日志
    6. WebSocket 推送：设备状态变更、截图结果实时推送到浏览器
    """

    def __init__(self, relay_server: BridgeRelayServer, config: dict):
        self.relay = relay_server
        self.port = config.get("port", 8092)

    # ---- HTTP API（供前端 JS 调用）----

    # GET  /api/bridges           → 列出所有 Bridge Client
    # GET  /api/devices           → 列出所有设备
    # GET  /api/devices/{id}      → 设备详情
    # POST /api/command           → 下发指令（和 Skill 调用 Relay 走同一条路）
    # GET  /api/screenshot/{id}   → 获取最新截图
    # POST /api/dag/run           → 触发 DAG 执行
    # GET  /api/history           → 操作历史

    # ---- WebSocket（实时推送）----
    # WS   /ws/console            → 设备状态变更、执行结果实时推送
```

**Web 前端页面设计（简洁实用）：**

```
┌─────────────────────────────────────────────────────────┐
│  Device Bridge Console                    [Bridge: ●online]│
├──────────────┬──────────────────────────────────────────┤
│ Devices      │  Screen                                  │
│              │  ┌──────────────────────────────────┐    │
│ ● Phone A   │  │                                    │    │
│   Pixel 7   │  │      (实时截图显示区域)              │    │
│   Online     │  │      点击图片 = tap 对应坐标        │    │
│   🔋 85%    │  │                                    │    │
│              │  └──────────────────────────────────┘    │
│ ○ Phone B   │                                          │
│   offline    │  Actions                                 │
│              │  [截图] [Home] [Back] [Recent]           │
│              │  [输入文本: _________ ] [发送]            │
│              │  [启动App: _________ ] [启动]            │
│              │  [执行DAG: ▼ screen_and_act ] [执行]     │
│              │                                          │
│              │  History                                  │
│              │  12:03:01  tap(540,1200) ✓ 120ms         │
│              │  12:03:02  screenshot ✓ 340ms            │
│              │  12:03:05  input("hello") ✓ 89ms         │
├──────────────┴──────────────────────────────────────────┤
│  Logs (实时滚动)                                         │
│  [INFO] 12:03:01 Command tap sent to PIXEL_7_abc123     │
│  [INFO] 12:03:01 ADB action completed in 120ms          │
└─────────────────────────────────────────────────────────┘
```

**安全控制：**
- Web Console 需要登录认证（简单的 token/密码）
- 可配置是否开放外部访问（默认只绑定 localhost，需要远程访问时绑定 0.0.0.0）
- 所有操作走统一的审计日志

## 4. 远程 OpenClaw 侧配置

在远程 OpenClaw 中注册一个 Device Control Skill，它通过 localhost 调用 Relay Server 的内部 API：

```
~/.clawhub/skills/device-control/
├── SKILL.md          # Skill 描述（告诉 AI 如何使用）
└── tool.py           # Tool 实现（调用 localhost:8091 的 Relay 内部 API）
```

`SKILL.md` 示例：
```markdown
# Device Control Skill

控制通过 Bridge 连接的本地设备。

## 可用工具

- `device_list`: 列出所有在线设备
- `device_screenshot`: 截取指定设备的屏幕截图
- `device_tap`: 在指定坐标点击
- `device_swipe`: 在指定方向滑动
- `device_input`: 输入文本
- `device_launch_app`: 启动 App
- `device_ui_dump`: 获取当前页面 UI 元素
- `device_run_dag`: 执行预定义的 DAG 流程
```

## 5. 数据流路径

### 典型场景：用户对 OpenClaw 说"打开微信搜索xxx"

```
1. 用户 → OpenClaw: "打开微信搜索 外卖优惠"
2. OpenClaw AI 解析意图，调用 Device Control Skill
3. Skill 调用 Relay Server (localhost:8091) 的内部 API
4. Relay Server 通过 WebSocket 转发指令到 Bridge Client：
   a. {"action": "launch_app", "params": {"package": "com.tencent.mm"}}
   b. {"action": "screenshot"} → Bridge 截图 → Relay → Skill → AI 确认已打开
   c. {"action": "tap", "params": {"x": 540, "y": 200}} → 点击搜索框
   d. {"action": "input_text", "params": {"text": "外卖优惠"}}
   e. {"action": "key_event", "params": {"keycode": 66}} → 回车搜索
   f. {"action": "screenshot"} → 返回搜索结果截图
5. AI 分析搜索结果截图，决定下一步操作
6. 每一步结果通过 Bridge Client → Relay → Skill → OpenClaw 原路返回
```

### 典型场景：使用 DAG 执行复合操作

```
1. OpenClaw → Skill → Relay → Bridge Client: {"action": "screen_and_act", "dag_name": "screen_and_act", ...}
2. Bridge Client TaskRouter 识别为 DAG 任务
3. DAGFactory 创建 DAG 实例
4. AsyncExecutor 按层执行：
   Layer 0: [ScreenCaptureAgent]  → 截图
   Layer 1: [UIParseAgent]        → 解析 UI 元素
   Layer 2: [ADBActionAgent]      → 执行操作
5. 执行结果 + 结构化日志通过 Bridge Client → Relay → Skill 返回
```

## 6. 安全考虑

| 安全措施 | 说明 |
|---------|------|
| 认证 | Bridge 连接 Gateway 时需要 token 认证 |
| 操作白名单 | 只允许配置中声明的操作类型 |
| 包名黑名单 | 可禁止操作敏感 App（如支付、银行） |
| 敏感操作确认 | 可选的人工确认机制 |
| Shell 命令限制 | 严格超时限制，可选禁用 |
| 审计日志 | 所有操作记录到独立审计日志 |
| TLS 加密 | WebSocket 使用 wss:// 加密传输 |
| Tailscale | 可选方案：通过 Tailscale 组网替代公网暴露 |

## 7. 网络方案选择

| 方案 | 优点 | 缺点 | 推荐场景 |
|-----|------|------|---------|
| **Tailscale (推荐)** | 零配置组网，NAT 穿透，加密 | 需要安装 Tailscale | 最优选择 |
| SSH 隧道 | 不需要额外软件 | 需要手动维护隧道 | 临时使用 |
| frp/ngrok 内网穿透 | 灵活 | 需要额外服务器/付费 | 有现成穿透服务时 |
| 公网 IP + 防火墙 | 延迟最低 | 安全风险高 | 不推荐 |

## 8. 与 kuangkuang 的关系

| kuangkuang 组件 | 本项目复用方式 |
|----------------|--------------|
| Agent 基类 | 直接复用，Agent 抽象不变 |
| DAG / DAGFactory | 直接复用，用于编排本地设备操作 |
| Executor | 直接复用 AsyncExecutor |
| Context | 适配：去掉 Protobuf 依赖，改为通用 dict 上下文 |
| ConfigManager | 复用模式，扩展 bridge/device 配置 |
| Logger | 复用 + 扩展（设备日志、审计日志、远程上报） |
| Exceptions | 复用 + 扩展设备相关异常 |
| BackendClient | 参考模式，用于 ADB Driver 的日志记录 |

## 9. 技术栈

| 组件 | 技术选择 | 理由 |
|-----|---------|------|
| 语言 | Python 3.11+ | 与 kuangkuang 一致 |
| WebSocket (Relay) | websockets | 成熟、性能好 |
| Web Console 后端 | FastAPI + Uvicorn | 异步、自带 OpenAPI 文档、和 Relay 同进程运行 |
| Web Console 前端 | 原生 HTML + JS + CSS | 轻量无依赖，无需构建工具 |
| ADB | adb CLI + asyncio subprocess | 简单可靠 |
| 配置 | YAML | 与 kuangkuang 一致 |
| 异步 | asyncio | 与 kuangkuang 一致 |
| 序列化 | JSON（WebSocket消息） | 与 OpenClaw 兼容 |
| 日志 | logging + 自定义 Handler | 与 kuangkuang 一致 |

## 10. 待讨论事项

1. **Context 是否保留 Protobuf？** 本地设备操作场景可能不需要 Protobuf 序列化，改用纯 dict 更轻量。但如果需要和 kuangkuang 后端互通，保留 Protobuf 也有好处。

2. **OpenClaw Skill 的实现方式：** OpenClaw 支持多种 Skill 形式（SKILL.md + tool、MCP Server 等），需要确定用哪种方式注册设备控制能力。

3. **实时屏幕流：** 是否需要支持实时屏幕流（类似 scrcpy），还是按需截图即可？实时流需要 minicap/scrcpy，复杂度显著增加。

4. **多 Bridge 支持：** 是否需要支持多个 Bridge Client（比如家里和公司各一台电脑连不同设备）？当前 Relay 设计已支持多 Bridge 会话，但需要在 Skill 侧做 Bridge 选择逻辑。

5. **是否集成 Phone Agent/DroidClaw：** 是否在 Bridge Client 内集成现有的 Phone Agent（用 AutoGLM 模型做端上 AI），让本地具备 AI 能力，还是完全依赖远程 OpenClaw 的 AI？

6. **Relay Server 网络暴露方式：** Relay Server 的 :8091 端口需要对外暴露以接受 Bridge Client 连接。可选方案：直接开放端口（配合防火墙）、Tailscale 组网、SSH 反向隧道等。

## 11. 受影响的文件

本项目为全新项目，不修改 kuangkuang 现有代码。项目分为四个部署单元：

### Relay Server（远程 Linux）

| 文件 | 说明 |
|-----|------|
| `relay/relay_server.py` | Relay 主服务（WebSocket Server + 内部 API） |
| `relay/session_manager.py` | Bridge Client 会话管理 |
| `relay/mcp_tool.py` | MCP Tool 接口（供 OpenClaw 调用） |
| `relay/config.py` | Relay 配置加载 |
| `relay/main.py` | Relay + Web Console 统一启动入口 |
| `shared/protocol.py` | 通信协议定义 |

### Web Console（远程 Linux，和 Relay 同进程）

| 文件 | 说明 |
|-----|------|
| `relay/web_console/app.py` | FastAPI 应用（HTTP API + WebSocket 推送） |
| `relay/web_console/auth.py` | 登录认证 |
| `relay/web_console/static/index.html` | 主页面 |
| `relay/web_console/static/style.css` | 样式 |
| `relay/web_console/static/app.js` | 前端逻辑 |

### Bridge Client（本地电脑）

| 源文件 (kuangkuang) | 目标文件 | 修改类型 |
|---------------------|---------|---------|
| `core/agent.py` | `client/core/agent.py` | 复用，去除 Protobuf 依赖 |
| `core/dag.py` | `client/core/dag.py` | 直接复用 |
| `core/dag_factory.py` | `client/core/dag_factory.py` | 直接复用 |
| `core/executor.py` | `client/core/executor.py` | 直接复用 |
| `core/context.py` | `client/core/context.py` | 重写，改为 dict-based |
| `core/config_manager.py` | `client/core/config_manager.py` | 扩展 bridge 配置 |
| `core/logger.py` | `client/core/logger.py` | 扩展设备日志/审计日志 |
| `core/exceptions.py` | `client/core/exceptions.py` | 扩展设备相关异常 |
| `core/utils.py` | `client/core/utils.py` | 直接复用 |
| - | `client/bridge/*.py` | 新增全部 |
| - | `client/drivers/*.py` | 新增全部 |
| - | `client/agents/*.py` | 新增全部 |
| - | `client/config/*.yaml` | 新增全部 |
| - | `client/main.py` | 新增 |

### OpenClaw Skill（远程 Linux）

| 文件 | 说明 |
|-----|------|
| `skill/SKILL.md` | Skill 描述文件 |
| `skill/tool.py` | Tool 实现（调用 Relay 内部 API） |
