"""核心与设备相关异常。"""


class BridgeError(Exception):
    """Bridge Client 基础错误。"""


class ConfigError(BridgeError):
    """配置加载或校验失败。"""


class DAGError(BridgeError):
    """DAG 定义或拓扑错误。"""


class ExecutionError(BridgeError):
    """DAG / Agent 执行失败。"""


class DeviceError(BridgeError):
    """设备层错误。"""


class DeviceNotFoundError(DeviceError):
    """指定 device_id 不存在。"""


class SecurityError(BridgeError):
    """操作未通过安全白名单等校验。"""


class DriverError(DeviceError):
    """设备驱动调用失败。"""
