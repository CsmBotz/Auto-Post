import os
import sys
import logging
import asyncio
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ─────────────────────────────────────────────
# Fix working directory (important for Render)
# ─────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

# ─────────────────────────────────────────────
# ✅ Runtime Font Loader (ADDED)
# ─────────────────────────────────────────────
from utils.font_loader import ensure_fonts
ensure_fonts()

# ─────────────────────────────────────────────
# Config & Routers
# ─────────────────────────────────────────────
from config import BOT_TOKEN, ADMIN_IDS
from routers import get_all_routers

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

# Load all routers
all_routers = get_all_routers()
for router in all_routers:
    dp.include_router(router)

LOGGER.info(f"✅ Loaded {len(all_routers)} routers")

# ─────────────────────────────────────────────
# Startup
# ─────────────────────────────────────────────
async def on_startup(bot: Bot):
    LOGGER.info("🚀 Bot Started in POLLING mode")

    # ❌ Remove webhook if exists (important)
    await bot.delete_webhook(drop_pending_updates=True)

    # Notify admins
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text="<b><blockquote>🤖 CosmicBotz Started (Polling) ✅</blockquote></b>",
            )
        except Exception as e:
            LOGGER.warning(f"Could not notify admin {admin_id}: {e}")


# ─────────────────────────────────────────────
# Shutdown
# ─────────────────────────────────────────────
async def on_shutdown(bot: Bot):
    LOGGER.info("⛔ Shutting down...")
    await bot.session.close()
    LOGGER.info("✅ Bot session closed.")


# ─────────────────────────────────────────────
# Web Server (for Render uptime)
# ─────────────────────────────────────────────
async def start_web_server():
    app = web.Application()

    app.router.add_get("/", lambda r: web.Response(text="CosmicBotz Running!"))
    app.router.add_get("/health", lambda r: web.Response(text="OK"))
    app.router.add_get("/webhook", lambda r: web.Response(text="Webhook  alive"))

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    LOGGER.info(f"🌐 server running on port {PORT}")


# ─────────────────────────────────────────────
# Main Runner
# ─────────────────────────────────────────────
async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Run both polling + web server together
    await asyncio.gather(
        start_web_server(),
        dp.start_polling(bot)
    )


if __name__ == "__main__":
    asyncio.run(main())