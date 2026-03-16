from pathlib import Path


def get_static_dir() -> Path:
    """Return the path to this package's static directory."""
    return Path(__file__).parent / "static"
