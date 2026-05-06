"""与 Client 共用的协议符号（定义见 shared.protocol）。"""

from shared.protocol import (  # noqa: F401
    MSG_AUTH,
    MSG_COMMAND,
    MSG_DEVICE_STATUS,
    MSG_HEARTBEAT,
    MSG_RESULT,
    build_auth_message,
    build_command_message,
    build_device_status_message,
    build_heartbeat_message,
    build_result_message,
    is_auth,
    is_command,
    is_device_status,
    is_heartbeat,
    is_result,
    new_command_id,
)
