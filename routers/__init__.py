from routers.start import router as start_router
from routers.content import router as content_router
from routers.settings import router as settings_router
from routers.templates import router as templates_router
from routers.admin import router as admin_router


def get_all_routers():
    # ORDER MATTERS: content must be before settings/templates
    # so the single F.text handler in content.py fires first
    return [
        start_router,
        content_router,
        settings_router,
        templates_router,
        admin_router,
    ]
