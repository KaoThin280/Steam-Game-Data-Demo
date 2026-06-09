"""
Custom Exceptions - Định nghĩa các mã lỗi chung
"""
from fastapi import HTTPException, status


class AppException(HTTPException):
    """Base exception của ứng dụng."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "Internal Server Error"
    code: str = "INTERNAL_ERROR"

    def __init__(
        self,
        detail: str | None = None,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        if detail is not None:
            self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        super().__init__(status_code=self.status_code, detail=self.detail)


# ============ 400 - Bad Request ============
class BadRequestException(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Bad Request"
    code = "BAD_REQUEST"


# ============ 401 - Unauthorized ============
class UnauthorizedException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Không có quyền truy cập. Vui lòng đăng nhập."
    code = "UNAUTHORIZED"


class InvalidCredentialsException(UnauthorizedException):
    detail = "Email hoặc mật khẩu không chính xác."
    code = "INVALID_CREDENTIALS"


class TokenExpiredException(UnauthorizedException):
    detail = "Token đã hết hạn."
    code = "TOKEN_EXPIRED"


# ============ 403 - Forbidden ============
class ForbiddenException(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    detail = "Bạn không có quyền thực hiện hành động này."
    code = "FORBIDDEN"


# ============ 404 - Not Found ============
class NotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Không tìm thấy tài nguyên."
    code = "NOT_FOUND"


# ============ 409 - Conflict ============
class ConflictException(AppException):
    status_code = status.HTTP_409_CONFLICT
    detail = "Tài nguyên đã tồn tại."
    code = "CONFLICT"


# ============ 422 - Validation ============
class ValidationException(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail = "Dữ liệu không hợp lệ."
    code = "VALIDATION_ERROR"


# ============ 429 - Rate Limit ============
class RateLimitException(AppException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    detail = "Quá nhiều request. Vui lòng thử lại sau."
    code = "RATE_LIMIT_EXCEEDED"


# ============ 500 - Internal Server Error ============
class InternalServerException(AppException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "Lỗi máy chủ nội bộ."
    code = "INTERNAL_SERVER_ERROR"


# ============ 503 - Service Unavailable ============
class ServiceUnavailableException(AppException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "Dịch vụ tạm thời không khả dụng."
    code = "SERVICE_UNAVAILABLE"
