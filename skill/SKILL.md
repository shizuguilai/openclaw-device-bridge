# Device Control Skill

控制通过 Bridge Relay 连接的本地物理设备（Android / ADB）。

截图压缩、依赖安装与 Relay 环境变量详见仓库根目录 **[SETUP.md](../SETUP.md)**（与 Bridge 同仓时路径为 `openclaw-device-bridge/SETUP.md`）。

## 环境变量

- `OPENCLAW_RELAY_CONSOLE_URL`：Web Console 基址，默认 `http://127.0.0.1:8092`
- `OPENCLAW_RELAY_CONSOLE_TOKEN`：与 Relay `web_console.auth_token` 一致（默认与 `RELAY_AUTH_TOKEN` 相同）

## 可用能力（HTTP API）

以下方法在 `tool.py` 中实现，对应 Console 的 `/api/*` 路径：

- `device_list`：列出设备
- `device_screenshot`：截图
- `device_tap` / `device_swipe` / `device_input`：触控与文本
- `device_launch_app`：启动应用
- `device_ui_dump`：UI 层级
- `device_run_dag`：执行预定义 DAG

## 使用建议

1. 在远程 Linux 启动 `python -m relay.main`（或 `python relay/main.py`）
2. 本地启动 `python client/main.py`，保证 `bridge.yaml` 中 `relay.url` 与 token 正确
3. 在 OpenClaw 中加载本 skill，由模型按需调用 `tool.py` 中的函数
