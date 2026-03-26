import os
import shutil

FONT_DIR = "assets/fonts"

SYSTEM_FONT_PATHS = {
    "DejaVuSans-Bold.ttf": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "DejaVuSans.ttf": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
}


def ensure_fonts():
    os.makedirs(FONT_DIR, exist_ok=True)

    for font_name, system_path in SYSTEM_FONT_PATHS.items():
        target_path = os.path.join(FONT_DIR, font_name)

        if not os.path.exists(target_path):
            if os.path.exists(system_path):
                try:
                    shutil.copy(system_path, target_path)
                    print(f"✅ Font copied: {font_name}")
                except Exception as e:
                    print(f"❌ Failed to copy {font_name}: {e}")
            else:
                print(f"⚠️ System font missing: {system_path}")