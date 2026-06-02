import asyncio
import logging
import uuid

import uvicorn
from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from fastapi import FastAPI, Request
from httpx import AsyncClient, Timeout

from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

config = Config()
bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

pending_callbacks: dict[str, dict] = {}
http_client = AsyncClient(timeout=Timeout(60.0))

fastapi_app = FastAPI()


def content_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Опубликовать сейчас", callback_data="publish")],
        [InlineKeyboardButton(text="📅 Запланировать", callback_data="schedule")],
        [InlineKeyboardButton(text="🔄 Перегенерировать", callback_data="regenerate"),
         InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")],
    ])


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🚀 <b>Content Factory Bot</b>\n\n"
        "Я помогаю создавать и публиковать контент в соцсети.\n\n"
        "Команды:\n"
        "/generate <i>текст</i> — создать пост с картинкой\n"
        "/video <i>текст</i> — создать видео\n"
        "/help — справка"
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "Просто напиши тему поста, например:\n"
        "• <code>создай пост про ИИ в образовании</code>\n"
        "• <code>видео про нейросети для бизнеса</code>\n"
        "• <code>сделай пост с фото про здоровое питание</code>\n\n"
        "Я сам сгенерирую текст и изображение."
    )


@dp.message(Command("generate"))
async def cmd_generate(message: types.Message):
    prompt = message.text.removeprefix("/generate").strip()
    if not prompt:
        await message.answer("Напиши тему после /generate, например:\n<code>/generate ИИ в образовании</code>")
        return
    status_msg = await message.answer("⏳ Генерирую контент...")
    await run_generation(chat_id=message.chat.id, prompt=prompt, content_type="photo", status_msg=status_msg)


@dp.message(Command("video"))
async def cmd_video(message: types.Message):
    prompt = message.text.removeprefix("/video").strip()
    if not prompt:
        await message.answer("Напиши тему после /video, например:\n<code>/video нейросети для бизнеса</code>")
        return
    status_msg = await message.answer("⏳ Генерирую видео...")
    await run_generation(chat_id=message.chat.id, prompt=prompt, content_type="video", status_msg=status_msg)


@dp.message()
async def handle_text(message: types.Message):
    if not message.text or message.text.startswith("/"):
        return
    status_msg = await message.answer("⏳ Генерирую контент...")
    await run_generation(chat_id=message.chat.id, prompt=message.text, content_type="photo", status_msg=status_msg)


async def run_generation(chat_id: int, prompt: str, content_type: str, status_msg: types.Message):
    callback_id = str(uuid.uuid4())
    event = asyncio.Event()
    pending_callbacks[callback_id] = {
        "event": event,
        "chat_id": chat_id,
        "status_msg_id": status_msg.message_id,
        "result": None,
    }

    try:
        resp = await http_client.post(
            f"{config.n8n_webhook_url}/generate",
            json={
                "callback_id": callback_id,
                "chat_id": chat_id,
                "prompt": prompt,
                "content_type": content_type,
                "callback_url": f"http://telegram-bot:{config.bot_internal_port}/callback",
            },
        )
        if resp.status_code != 200:
            logger.warning("n8n returned %s: %s", resp.status_code, resp.text)
    except Exception as e:
        logger.error("Failed to call n8n: %s", e)

    try:
        await asyncio.wait_for(event.wait(), timeout=120.0)
    except asyncio.TimeoutError:
        await status_msg.edit_text("⏳ Время ожидания истекло. Попробуйте ещё раз.")
        pending_callbacks.pop(callback_id, None)
        return

    data = pending_callbacks.pop(callback_id, {}).get("result")
    if not data:
        await status_msg.edit_text("❌ Ошибка генерации. Попробуйте ещё раз.")
        return

    image_url = data.get("image_url") or data.get("video_url")
    caption = data.get("caption", "")

    await status_msg.delete()

    if image_url:
        await bot.send_photo(
            chat_id=chat_id,
            photo=image_url,
            caption=caption[:1024] if caption else None,
            reply_markup=content_keyboard(),
        )
    else:
        await bot.send_message(
            chat_id=chat_id,
            text=caption or "✅ Контент готов!",
            reply_markup=content_keyboard(),
        )


@fastapi_app.post("/callback")
async def n8n_callback(request: Request):
    data = await request.json()
    callback_id = data.get("callback_id")
    if not callback_id or callback_id not in pending_callbacks:
        logger.warning("Unknown callback_id: %s", callback_id)
        return {"ok": False}

    entry = pending_callbacks[callback_id]
    entry["result"] = data
    entry["event"].set()
    logger.info("Callback received for %s", callback_id)
    return {"ok": True}


@dp.callback_query()
async def handle_callback(callback: types.CallbackQuery):
    action = callback.data
    chat_id = callback.message.chat.id
    original_text = callback.message.caption or callback.message.text or ""

    if action == "publish":
        await callback.answer("📤 Публикую...")
        try:
            await http_client.post(
                f"{config.n8n_webhook_url}/publish",
                json={"chat_id": chat_id, "text": original_text},
            )
            if callback.message.caption:
                await callback.message.edit_caption(
                    caption=f"{original_text}\n\n✅ Опубликовано!",
                    reply_markup=None,
                )
            else:
                await callback.message.edit_text(
                    text=f"{original_text}\n\n✅ Опубликовано!",
                    reply_markup=None,
                )
        except Exception as e:
            logger.error("Publish failed: %s", e)
            await callback.answer("❌ Ошибка публикации", show_alert=True)

    elif action == "schedule":
        await callback.answer("📅 Отложенный постинг — в разработке")

    elif action == "regenerate":
        await callback.answer("🔄 Перегенерирую...")
        prompt = original_text.split("\n")[0][:200] if original_text else "новый пост"
        try:
            await callback.message.delete()
        except Exception:
            pass
        status_msg = await bot.send_message(chat_id, "⏳ Перегенерирую контент...")
        await run_generation(chat_id=chat_id, prompt=prompt, content_type="photo", status_msg=status_msg)

    elif action == "cancel":
        await callback.answer("❌ Отменено")
        try:
            await callback.message.delete()
        except Exception:
            pass


async def main():
    uvicorn_config = uvicorn.Config(
        app=fastapi_app,
        host=config.bot_internal_host,
        port=config.bot_internal_port,
        log_level="info",
    )
    server = uvicorn.Server(uvicorn_config)

    polling_task = asyncio.create_task(dp.start_polling(bot))
    server_task = asyncio.create_task(server.serve())

    await asyncio.gather(polling_task, server_task)


if __name__ == "__main__":
    asyncio.run(main())
