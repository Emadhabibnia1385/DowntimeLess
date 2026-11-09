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
    "issue.not_found": (404, "این مشکل در فهرست مشکل‌های فعلی پیدا نشد؛ شاید همین حالا برطرف شده باشد."),
    "ack.not_found": (404, "این مشکل پذیرفته نشده بود."),
    "window.invalid": (422, "بازهٔ زمانی نامعتبر است؛ شروع باید پیش از پایان باشد و حداکثر یک سال."),
    "range.invalid": (422, "بازهٔ زمانی نامعتبر است؛ ۲۴ ساعت، ۷ روز یا ۳۰ روز."),
    "traffic.range_invalid": (422, "بازهٔ ترافیک نامعتبر است؛ ۲۴ ساعت، ۷ روز، ۳۰ روز یا ۹۰ روز."),
    "traffic.window_invalid": (422, "بازهٔ تاریخ نامعتبر است؛ شروع و پایان لازم است، پایان بعد از شروع و حداکثر ۳۶۶ روز."),
    "traffic.category_invalid": (422, "دسته‌بندی نامعتبر است؛ شناسهٔ عددی یا none."),
    "traffic.tz_invalid": (422, "اختلاف ساعت محلی نامعتبر است؛ از منفی ۷۲۰ تا ۸۴۰ دقیقه."),
    "report.param_invalid": (422, "پارامتر گزارش نامعتبر است (format: json یا md، detail: brief یا full، lang: en یا fa)."),
    "bot.not_configured": (409, "ربات تلگرام تنظیم نشده است."),
    "channel.not_found": (404, "کانال تلگرام پیدا نشد."),
    "channel.invalid": (422, "نام کانال یا شناسهٔ چت نامعتبر است؛ شناسهٔ عددی مثل -100… یا نام کاربری مثل @name بدهید."),
    "channel.exists": (409, "این چت قبلاً به‌عنوان کانال ثبت شده است."),
    "route.unknown_rule": (422, "این نوع اعلان وجود ندارد."),
    "route.unknown_channel": (422, "کانال انتخاب‌شده وجود ندارد."),
    "route.invalid": (422, "مقصد اعلان نامعتبر است؛ فقط پنل، مدیران یا یک کانال."),
    "workspace.not_found": (404, "فضای کار پیدا نشد."),
    "member.not_found": (404, "این عضو در این فضای کار پیدا نشد."),
    "member.exists": (409, "این حساب تلگرام قبلاً عضو این فضای کار است."),
    "member.role_invalid": (422, "نقش نامعتبر است؛ فقط بیننده، اپراتور یا ادمین."),
    "member.tg_id_invalid": (422, "شناسهٔ عددی تلگرام نامعتبر است؛ فقط رقم، مثل 123456789."),
    "member.name_invalid": (422, "نام حداکثر ۶۴ نویسه باشد."),
    "member.owner_locked": (409, "نقش مالک فضای کار تغییر نمی‌کند و مالک حذف نمی‌شود."),
    "member.self": (409, "نقش خودتان را نمی‌توانید تغییر دهید یا خودتان را حذف کنید."),
    "members.panel_owner_only": (403, "فقط مالک پنل می‌تواند فرد تازه‌ای اضافه کند."),
    "members.limit": (409, "این فضای کار به سقف ۵۰ عضو رسیده است."),
    "server.limit": (409, "این فضای کار به سقف ۲۰۰ سرور رسیده است."),
    "domain.limit": (409, "این فضای کار به سقف ۳۰۰ دامنه رسیده است."),
    "channel.private_not_member": (422, "شناسهٔ عددی مثبت، چت خصوصی یک نفر است؛ فقط شناسهٔ مالک یا ادمین‌های همین فضای کار مجاز است."),
    "channel.not_verified": (422, "ربات باید در این کانال یا گروه مدیر باشد و اجازهٔ ارسال پیام داشته باشد، و یکی از مالک یا ادمین‌های همین فضای کار هم مدیر آن باشد."),
    "listener.not_found": (404, "این پورت در خط پایهٔ لیسنرهای این سرور نیست."),
    "check.invalid": (422, "نام نامعتبر است؛ نام کانتینر، شناسهٔ عددی نود یا برچسب اینباند را بدهید."),
    "telegram.send_failed": (502, "ارسال پیام به تلگرام ناموفق بود؛ ربات را در آن کانال یا گروه مدیر کنید و شناسه را بررسی کنید."),
}


class DLError(Exception):
    def __init__(self, code: str):
        self.code = code
        self.status, self.message = REGISTRY[code]


async def dl_error_handler(_: Request, exc: DLError) -> JSONResponse:
    return JSONResponse({"code": exc.code, "message": exc.message}, status_code=exc.status)
