from typing import Dict, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse

# code -> (http status, Persian message shown to the user)
REGISTRY: Dict[str, Tuple[int, str]] = {
    "auth.required": (401, "ابتدا وارد شوید."),
    "auth.invalid": (401, "نام کاربری یا رمز عبور درست نیست."),
    "auth.forbidden": (403, "دسترسی کافی ندارید."),
    "auth.not_registered": (403, "این حساب تلگرام در پنل ثبت نشده است."),
    "auth.challenge_gone": (404, "درخواست ورود پیدا نشد یا منقضی شده است."),
    "auth.weak_password": (422, "رمز عبور باید دست‌کم ۸ نویسه باشد."),
    "auth.current_password": (403, "رمز فعلی درست نیست."),
    "auth.webapp_invalid": (401, "اعتبار Mini App تأیید نشد."),
    "rate.limited": (429, "تعداد درخواست‌ها زیاد است؛ کمی بعد دوباره تلاش کنید."),
    "server.not_found": (404, "سرور پیدا نشد."),
    "category.not_found": (404, "دسته‌بندی پیدا نشد."),
    "category.exists": (409, "دسته‌بندی‌ای با این نام قبلاً ساخته شده است."),
    "category.invalid": (422, "نام دسته‌بندی را وارد کنید."),
    "job.kind_unknown": (422, "این عمل مجاز نیست."),
    "job.args_invalid": (422, "ورودی این عمل نامعتبر است."),
    "job.permission": (403, "سطح دسترسی این سرور اجازهٔ این عمل را نمی‌دهد."),
    "agent.invalid": (401, "کلید agent معتبر نیست."),
    "agent.enroll_invalid": (401, "توکن نصب معتبر نیست یا قبلاً استفاده شده است."),
    "domain.not_found": (404, "دامنه پیدا نشد."),
    "domain.invalid": (422, "این آدرس مجاز نیست (فقط نام دامنهٔ عمومی)."),
    "domain.exists": (409, "این دامنه قبلاً ثبت شده است."),
    "key.not_found": (404, "کلید API پیدا نشد."),
    "window.invalid": (422, "بازهٔ زمانی نامعتبر است؛ شروع باید پیش از پایان باشد و حداکثر یک سال."),
    "range.invalid": (422, "بازهٔ زمانی نامعتبر است؛ ۲۴ ساعت، ۷ روز یا ۳۰ روز."),
    "bot.not_configured": (409, "ربات تلگرام تنظیم نشده است."),
}


class DLError(Exception):
    def __init__(self, code: str):
        self.code = code
        self.status, self.message = REGISTRY[code]


async def dl_error_handler(_: Request, exc: DLError) -> JSONResponse:
    return JSONResponse({"code": exc.code, "message": exc.message}, status_code=exc.status)
