import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

DEFAULT_CONFIG = {
    "screenshots_folder": "",
}


def load_config() -> dict:
    """Load config from file, or return defaults if not found."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
                # Merge with defaults to handle new config options
                return {**DEFAULT_CONFIG, **config}
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    """Save config to file."""
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


def get_screenshots_folder() -> str:
    """Get the configured screenshots folder path."""
    config = load_config()
    return config.get("screenshots_folder", "")


def set_screenshots_folder(folder_path: str):
    """Set the screenshots folder path."""
    config = load_config()
    config["screenshots_folder"] = folder_path
    save_config(config)


def is_configured() -> bool:
    """Check if the app has been configured with a screenshots folder."""
    folder = get_screenshots_folder()
    return bool(folder) and Path(folder).exists()
