"""机器人解析逆解（OpenRAVE ikfast）集成。

机型实现位于子包，例如 ``m20ia_35m`` 对应 FANUC M-20iA/35M。
HTTP 入口：``app.routers.ikfast``；业务逻辑：``app.services.ikfast_service``。
"""

from app.ikfast.native_loader import ikfast_available, robot_models

__all__ = ["ikfast_available", "robot_models"]
