"""Точка входа: бот (long-polling) + aiohttp-сервер для webhook AllPay в одном процессе."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web

from config import load_config
from db.database import init_db, init_engine
from handlers import (account, admin, chatinfo, menu, plans, purchase, start,
                      subscription, support)
from middlewares import UsernameMiddleware
from payments.webhook import setup_routes
from scheduler import reminder_worker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("bot")


def build_dispatcher(config) -> Dispatcher:
    dp = Dispatcher()
    dp["config"] = config
    # Запоминаем @username всех, кто пишет боту / жмёт кнопки.
    dp.message.middleware(UsernameMiddleware())
    dp.callback_query.middleware(UsernameMiddleware())
    # Порядок важен: команды и FSM-роутеры раньше, общий текстовый обработчик меню — последним.
    dp.include_router(chatinfo.router)
    dp.include_router(start.router)
    dp.include_router(admin.router)
    dp.include_router(purchase.router)
    dp.include_router(account.router)
    dp.include_router(plans.router)
    dp.include_router(subscription.router)
    dp.include_router(support.router)
    dp.include_router(menu.router)
    return dp


async def main() -> None:
    config = load_config()

    init_engine(config.database_url)
    await init_db(config.default_currency)

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = build_dispatcher(config)

    # aiohttp-сервер для webhook AllPay (заодно биндит PORT — нужно для хостинга).
    me = await bot.get_me()
    app = web.Application()
    setup_routes(app, bot, config, me.username or "")
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=config.port)
    await site.start()
    logger.info("Webhook-сервер AllPay слушает порт %s (%s)", config.port, config.allpay_webhook_url)

    # Фоновая рассылка уведомлений об окончании подписки.
    reminder_task = asyncio.create_task(reminder_worker(bot, config))

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Запуск long-polling…")
        await dp.start_polling(bot)
    finally:
        reminder_task.cancel()
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Остановлено")
