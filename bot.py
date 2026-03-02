import os
import sys
import logging
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# ─────────────────────────────────────────────
# Fix working directory (important for Render)
# ─────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

# ─────────────────────────────────────────────
# Config & Routers
# ─────────────────────────────────────────────
from config import BOT_TOKEN, ADMIN_IDS
from routers import get_all_routers

PORT = int(os.environ.get("PORT", 8080))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
WEBHOOK_PATH = "/webhook"

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN is missing!")

if not WEBHOOK_URL:
    raise ValueError("❌ WEBHOOK_URL is missing!")

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
# Startup (Set Webhook)
# ─────────────────────────────────────────────
async def on_startup(bot: Bot):
    webhook = f"{WEBHOOK_URL.rstrip('/')}{WEBHOOK_PATH}"
    await bot.set_webhook(url=webhook, drop_pending_updates=True)
    LOGGER.info(f"✅ Webhook set → {webhook}")

    # Optional: Notify admins
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text="<b><blockquote>🤖 CosmicBotz Started ✅</blockquote></b>",
            )
        except Exception as e:
            LOGGER.warning(f"Could not notify admin {admin_id}: {e}")


# ─────────────────────────────────────────────
# Shutdown (DO NOT delete webhook in production)
# ─────────────────────────────────────────────
async def on_shutdown(bot: Bot):
    LOGGER.info("⛔ Shutting down...")
    await bot.session.close()
    LOGGER.info("✅ Bot session closed.")


# ─────────────────────────────────────────────
# Main App
# ─────────────────────────────────────────────
def main():
    # Register lifecycle events
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()

    # Root endpoint
    app.router.add_get("/", lambda r: web.Response(text="CosmicBotz Running!"))

    # Health check endpoint (set this in Render settings)
    app.router.add_get("/health", lambda r: web.Response(text="OK"))

    # Allow GET on webhook (prevents 405 health check restart issue)
    app.router.add_get(WEBHOOK_PATH, lambda r: web.Response(text="Webhook Alive"))

    # Telegram webhook handler (POST)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)

    setup_application(app, dp, bot=bot)

    LOGGER.info(f"🌐 Starting on port {PORT}")
    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()