"""业务异常与错误码。

所有可预期的失败都以 AppError 抛出，由异常处理器统一包装成
{code, message, data} 响应，前端据 code 做分支。
"""

from __future__ import annotations


class ErrorCode:
    """错误码常量。"""

    OK = 0
    INPUT_FORMAT = "E_INPUT_FORMAT"
    KEY_LENGTH = "E_KEY_LENGTH"
    AUTH_FAILED = "E_AUTH_FAILED"
    TOKEN_INVALID = "E_TOKEN_INVALID"
    USER_EXISTS = "E_USER_EXISTS"
    NOT_FOUND = "E_NOT_FOUND"
    FORBIDDEN = "E_FORBIDDEN"
    RATE_LIMITED = "E_RATE_LIMITED"
    AI_UNAVAILABLE = "E_AI_UNAVAILABLE"
    INTERNAL = "E_INTERNAL"


class AppError(Exception):
    """业务异常。"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class InputFormatError(AppError):
    """输入格式非法。"""

    def __init__(self, message: str = "输入格式不正确") -> None:
        super().__init__(ErrorCode.INPUT_FORMAT, message, 400)


class KeyLengthError(AppError):
    """密钥长度与所选算法不匹配。"""

    def __init__(self, message: str = "密钥长度与所选算法不匹配") -> None:
        super().__init__(ErrorCode.KEY_LENGTH, message, 400)


class AuthFailedError(AppError):
    """用户名或口令错误。"""

    def __init__(self, message: str = "用户名或口令错误") -> None:
        super().__init__(ErrorCode.AUTH_FAILED, message, 401)


class TokenInvalidError(AppError):
    """令牌无效或已过期。"""

    def __init__(self, message: str = "登录状态已失效，请重新登录") -> None:
        super().__init__(ErrorCode.TOKEN_INVALID, message, 401)


class UserExistsError(AppError):
    """用户名已被占用。"""

    def __init__(self, message: str = "用户名已被占用") -> None:
        super().__init__(ErrorCode.USER_EXISTS, message, 409)


class NotFoundError(AppError):
    """资源不存在。"""

    def __init__(self, message: str = "资源不存在") -> None:
        super().__init__(ErrorCode.NOT_FOUND, message, 404)


class ForbiddenError(AppError):
    """无权访问。"""

    def __init__(self, message: str = "无权访问该资源") -> None:
        super().__init__(ErrorCode.FORBIDDEN, message, 403)


class RateLimitedError(AppError):
    """请求过于频繁。"""

    def __init__(self, message: str = "请求过于频繁，请稍后再试") -> None:
        super().__init__(ErrorCode.RATE_LIMITED, message, 429)


class AiUnavailableError(AppError):
    """AI 服务不可用。"""

    def __init__(self, message: str = "AI 服务暂不可用") -> None:
        super().__init__(ErrorCode.AI_UNAVAILABLE, message, 503)