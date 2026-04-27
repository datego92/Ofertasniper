import os
import requests
from typing import Optional

TELEGRAM_SEND_PHOTO = "https://api.telegram.org/bot{token}/sendPhoto"
TELEGRAM_SEND_MESSAGE = "https://api.telegram.org/bot{token}/sendMessage"
MAX_OFFERS_PER_CATEGORY = 10


def send_offers(offers_by_category: dict, categories_config: dict) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    for cat_key, offers in offers_by_category.items():
        cat_config = categories_config[cat_key]
        for offer in offers[:MAX_OFFERS_PER_CATEGORY]:
            _send_offer(token, chat_id, offer, cat_config)
        print(f"[notifier] Sent {min(len(offers), MAX_OFFERS_PER_CATEGORY)} offers for '{cat_key}'")


def _send_offer(token: str, chat_id: str, offer: dict, cat_config: dict) -> None:
    caption = _format_caption(offer, cat_config)
    image_url = offer.get("image_url")

    if image_url and _try_send_photo(token, chat_id, image_url, caption):
        return

    # Fallback a mensaje de texto si la imagen no está disponible
    _send_message(token, chat_id, caption)


def _format_caption(offer: dict, cat_config: dict) -> str:
    emoji = cat_config.get("emoji", "🎮")
    name = cat_config.get("name", "")
    title = _truncate(offer.get("title", "Sin título"), 80)
    amazon_url = offer.get("amazon_url", "")

    current = offer.get("current_price")
    original = offer.get("original_price")
    min_price = offer.get("min_price")

    price_actual = f"<b>{_fmt(current)}</b>" if current else "—"
    price_recomendado = f"<s>{_fmt(original)}</s>" if original else "—"
    price_minimo = _fmt(min_price) if min_price else "—"

    return (
        f"{emoji} <b>{name}</b>\n\n"
        f"<b>{title}</b>\n\n"
        f"💸 <b>P. recomendado</b>   {price_recomendado}\n"
        f"📉 <b>P. mínimo 30d</b>    {price_minimo}\n"
        f"🏷️ <b>P. actual</b>        {price_actual}\n\n"
        f"<a href='{amazon_url}'>🛒 Ver oferta en Amazon</a>"
    )


def _try_send_photo(token: str, chat_id: str, image_url: str, caption: str) -> bool:
    try:
        resp = requests.post(
            TELEGRAM_SEND_PHOTO.format(token=token),
            json={
                "chat_id": chat_id,
                "photo": image_url,
                "caption": caption,
                "parse_mode": "HTML",
            },
            timeout=10,
        )
        if resp.ok:
            return True
        print(f"[notifier] Photo send failed ({resp.status_code}), falling back to text")
        return False
    except Exception as e:
        print(f"[notifier] Photo send error: {e}, falling back to text")
        return False


def _send_message(token: str, chat_id: str, text: str) -> None:
    resp = requests.post(
        TELEGRAM_SEND_MESSAGE.format(token=token),
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=10,
    )
    resp.raise_for_status()


def _fmt(price: Optional[float]) -> str:
    if price is None:
        return "—"
    return f"{price:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[: max_len - 1] + "…"
