"""Server-local settings: credentials are never node inputs."""
import os
from pathlib import Path
from urllib.parse import urlsplit

DEFAULT_BASE = "https://api.canvasproai.com"


def data_dir():
    override = os.environ.get("CANVASPRO_DATA_DIR")
    if override:
        root = Path(override).expanduser()
    else:
        try:
            import folder_paths
            root = Path(folder_paths.get_user_directory()) / "canvaspro"
        except ImportError:
            root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local/share")) / "CanvasProComfyUI"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def settings():
    base = os.environ.get("CANVASPRO_BASE_URL", DEFAULT_BASE).rstrip("/")
    u = urlsplit(base)
    mock = os.environ.get("CANVASPRO_ALLOW_LOCAL_TEST") == "1"
    if base != DEFAULT_BASE and not (mock and u.scheme == "http" and u.hostname == "127.0.0.1" and u.path == ""):
        raise ValueError("Only CanvasPro HTTPS or explicitly enabled loopback test service is allowed")
    key = os.environ.get("CANVASPRO_API_KEY", "").strip()
    if not key:
        private_root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".config")) / "CanvasProComfyUI"
        path = Path(os.environ.get("CANVASPRO_KEY_FILE", str(private_root / "key.txt")))
        if path.exists():
            key = path.read_text(encoding="utf-8").strip()
    if not key or any(c.isspace() for c in key):
        raise ValueError("Configure CANVASPRO_API_KEY or server-local CanvasProComfyUI/key.txt; never put Key in workflow")
    return base, key
