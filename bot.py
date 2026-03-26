import os
import sys
import logging
import asyncio
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ─────────────────────────────────────────────
# Fix working directory
# ─────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

# ─────────────────────────────────────────────
# Config & Utils
# ─────────────────────────────────────────────
from config import BOT_TOKEN, ADMIN_IDS
from routers import get_all_routers
from utils.font_loader import ensure_fonts

PORT = int(os.environ.get("PORT", 8080))

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN is missing!")

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
LOGGER = logging.getLogger("bot")

# ─────────────────────────────────────────────
# Bot & Dispatcher
# ─────────────────────────────────────────────
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

dp = Dispatcher()

for router in get_all_routers():
    dp.include_router(router)

LOGGER.info("✅ Routers loaded")

# ─────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────
async def on_startup(bot: Bot):
    LOGGER.info("🚀 Bot Starting in POLLING mode")

    # Clean webhook (safe)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await asyncio.sleep(1)
    except Exception as e:
        LOGGER.warning(f"Webhook cleanup failed: {e}")

    # Delay to avoid duplicate instance overlap
    await asyncio.sleep(5)

    # Notify admins
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text="<b><blockquote>🤖 CosmicBotz Started (Polling) ✅</blockquote></b>",
            )
        except Exception as e:
            LOGGER.warning(f"Admin notify failed: {e}")

# ─────────────────────────────────────────────
# Shutdown
# ─────────────────────────────────────────────
async def on_shutdown(bot: Bot):
    LOGGER.info("⛔ Shutting down...")
    await bot.session.close()

# ─────────────────────────────────────────────
# Dummy Web Server (Render uptime)
# ─────────────────────────────────────────────
async def start_web_server():
    app = web.Application()

    app.router.add_get("/", lambda r: web.Response(text="CosmicBotz Running!"))
    app.router.add_get("/health", lambda r: web.Response(text="OK"))
    app.router.add_get("/webhook", lambda r: web.Response(text="Webhook alive"))

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    LOGGER.info(f"🌐 Server running on port {PORT}")

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
async def main():
    ensure_fonts()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Start web server first
    await start_web_server()

    # Extra safety delay (important for Render)
    LOGGER.info("⏳ Waiting before polling start...")
    await asyncio.sleep(10)

    # Polling loop (auto-restart safe)
    while True:
        try:
            await dp.start_polling(bot)
        except Exception as e:
            LOGGER.error(f"❌ Polling crashed: {e}")
            await asyncio.sleep(5)

# ─────────────────────────────────────────────
# Entry
# ─────────────────────────────────────────────
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        LOGGER.info("🛑 Bot stopped.")