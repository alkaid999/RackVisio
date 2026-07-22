"""统一业务异常。

业务异常会被 ``main.py`` 的全局异常处理器包装为统一响应信封
``{"code": <int>, "message": "<可读信息>", "data": null}``。
"""

from __future__ import annotations


class AppError(Exception):
    """基础业务异常。

    Attributes:
        status_code: HTTP 状态码（语义化，如 404/409/422）。
        code: 业务错误码，直接放入响应信封的 ``code`` 字段。
        message: 可读的错误信息。
    """

    def __init__(self, status_code: int, code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class NotFoundError(AppError):
    """资源不存在 (404)。"""

    def __init__(self, message: str = "资源不存在") -> None:
        super().__init__(status_code=404, code=404, message=message)


class ConflictError(AppError):
    """资源冲突 (409)，如 U 位冲突、端口重复占用、编号重复等。"""

    def __init__(self, message: str = "资源冲突") -> None:
        super().__init__(status_code=409, code=409, message=message)


class ValidationError(AppError):
    """业务校验失败 (422)。"""

    def __init__(self, message: str = "校验失败") -> None:
        super().__init__(status_code=422, code=422, message=message)
