from pathlib import Path
from n3tx_core.models.proto_model import register_mixin
from n3tx_ui.mixin import ViewableMixin  # also registers @schema_extension side-effect


def get_static_dir() -> Path:
    """Return the path to this package's static directory."""
    return Path(__file__).parent / "static"


# Register ViewableMixin: __viewable__ = True OR __ui__ set triggers injection
register_mixin('__viewable__', ViewableMixin, also_if=['__ui__'])
