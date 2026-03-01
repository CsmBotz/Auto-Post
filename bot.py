"""
CosmicBotz — Pyrogram Client + aiohttp health server
"""
import os
import sys
import logging

# Set working directory to project root
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aiohttp import web
from pyrogram import Client
import config as cfg

# ── Manually import all plugins so handlers register ─────────────────────────
import Plugins.start
import Plugins.content
import Plugins.settings
import Plugins.templates
import Plugins.admin
# ─────────────────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

# ── Web routes ────────────────────────────────────────────────────────────────
CosmicBotz_Web = web.RouteTableDef()


@CosmicBotz_Web.get("/", allow_head=True)
async def root_handler(request):
    return web.json_response("CosmicBotz [AutoPost Generator]")


@CosmicBotz_Web.get("/health", allow_head=True)
async def health_handler(request):
    return web.json_response({"status": "ok", "bot": cfg.BOT_USERNAME})


async def web_server():
    app = web.Application(client_max_size=30_000_000)
    app.add_routes(CosmicBotz_Web)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=cfg.PORT)
    await site.start()
    logger.info(f"🌐 Web server running on port {cfg.PORT}")


# ── Bot client ────────────────────────────────────────────────────────────────
class CosmicBotzClient(Client):
    def __init__(self):
        super().__init__(
            name="CosmicBotz",
            api_id=cfg.API_ID,
            api_hash=cfg.API_HASH,
            bot_token=cfg.BOT_TOKEN,
            workers=200,
            sleep_threshold=15,
        )

    async def start(self):
        await super().start()
        me = await self.get_me()
        logger.info(f"✅ CosmicBotz started as @{me.username}")
        await web_server()

    async def stop(self):
        await super().stop()
        logger.info("⛔ CosmicBotz stopped.")


CosmicBotz = CosmicBotzClient()
