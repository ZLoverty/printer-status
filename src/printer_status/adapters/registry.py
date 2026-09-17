"""Brand-to-adapter registry."""

from .base import AdapterUnavailable
from .bambu import BambuAdapter
from .creality import CrealityAdapter
from .raise3d import Raise3DAdapter
from .snapmaker import SnapmakerAdapter


ADAPTERS = {
    "bambu": BambuAdapter,
    "bambulab": BambuAdapter,
    "creality": CrealityAdapter,
    "raise3d": Raise3DAdapter,
    "raise": Raise3DAdapter,
    "snapmaker": SnapmakerAdapter,
}


def get_adapter(brand: str):
    key = brand.strip().lower().replace(" ", "")
    adapter = ADAPTERS.get(key)
    if adapter is None:
        raise AdapterUnavailable(f"不支持的品牌: {brand}")
    return adapter()


def supported_brands():
    return ("bambu", "creality", "raise3d", "snapmaker")
