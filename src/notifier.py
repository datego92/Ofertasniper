import os
import requests
from typing import Optional

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"
MAX_OFFERS_PER_MESSAGE = 10


def send_offers(offers_by_category: dict, categories_config: dict) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]

    for cat_key, offers in offers_by_category.items():
        cat_config = categories_config[cat_key]
        message = _format_message(offers, cat_config)
        _send(token, chat_id, message)
        print(f"[notifier] Sent {len(offers)} offers for category '{cat_key}'")


def _format_message(offers: list[dict], cat_config: dict) -> str:
    emoji = cat_config.get("emoji", "🎮")
    name = cat_config.get("name", "")
    visible = offers[:MAX_OFFERS_PER_MESSAGE]

    lines = [f"{emoji} <b>{name} — {len(offers)} oferta(s)</b>\n"]

    for offer in visible:
        title = _truncate(offer.get("title", "Sin título"), 55)
        price = offer.get("current_price")
        original = offer.get("original_price")
        discount = offer.get("discount_pct")
        amazon_url = offer.get("amazon_url", "")

        price_str = f"<b>{price:.2f}€</b>" if price else "—"
        if original:
            price_str += f" <s>{original:.2f}€</s>"
        discount_str = f" (-{discount:.0f}%)" if discount else ""

        lines.append(
            f"• <a href='{amazon_url}'>{title}</a>\n"
            f"  {price_str}{discount_str}"
        )

    if len(offers) > MAX_OFFERS_PER_MESSAGE:
        lines.append(f"\n<i>... y {len(offers) - MAX_OFFERS_PER_MESSAGE} más.</i>")

    return "\n".join(lines)


def _send(token: str, chat_id: str, text: str) -> None:
    url = TELEGRAM_API.format(token=token)
    resp = requests.post(
        url,
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=10,
    )
    resp.raise_for_status()


def _truncate(text: str, max_len: int) -> str:
    return text if len(text) <= max_len else text[: max_len - 1] + "…"
