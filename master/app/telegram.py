import logging
from typing import Any, Dict, List, Optional

import httpx

log = logging.getLogger("dl.telegram")


class Telegram:
    def __init__(self, token: str):
        self.token = token
        self.client = httpx.Client(timeout=httpx.Timeout(35, connect=10))

    def call(self, method: str, **params: Any) -> Any:
        r = self.client.post("https://api.telegram.org/bot%s/%s" % (self.token, method), json=params)
        data = r.json()
        if not data.get("ok"):
            raise RuntimeError("telegram %s failed: %s" % (method, data.get("description")))
        return data["result"]

    def me(self) -> Dict[str, Any]:
        return self.call("getMe")

    def updates(self, offset: int) -> List[Dict[str, Any]]:
        return self.call("getUpdates", offset=offset, timeout=25, allowed_updates=["message", "callback_query"])

    def send(self, chat_id: int, text: str, buttons: Optional[List[List[Dict[str, str]]]] = None) -> None:
        extra = {"reply_markup": {"inline_keyboard": buttons}} if buttons else {}
        try:
            self.call("sendMessage", chat_id=chat_id, text=text, parse_mode="HTML", disable_web_page_preview=True, **extra)
        except Exception as exc:  # a blocked bot must never break the caller
            log.warning("send to %s failed: %s", chat_id, exc)

    def edit(self, chat_id: int, message_id: int, text: str) -> None:
        try:
            self.call("editMessageText", chat_id=chat_id, message_id=message_id, text=text, parse_mode="HTML")
        except Exception as exc:
            log.warning("edit failed: %s", exc)

    def answer(self, callback_id: str, text: str = "") -> None:
        try:
            self.call("answerCallbackQuery", callback_query_id=callback_id, text=text)
        except Exception as exc:
            log.warning("answer failed: %s", exc)
