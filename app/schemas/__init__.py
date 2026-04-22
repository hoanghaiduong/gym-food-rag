from __future__ import annotations

from importlib import import_module


SCHEMA_MODULES = [
    "auth",
    "rbac",
    "ecommerce",
    "blockchain",
    "chat",
    "nutrition",
    "setup",
    "users",
]


def __getattr__(name: str):
    for module_name in SCHEMA_MODULES:
        module = import_module(f"{__name__}.{module_name}")
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__() -> list[str]:
    exported = set(globals())
    for module_name in SCHEMA_MODULES:
        try:
            module = import_module(f"{__name__}.{module_name}")
        except Exception:
            continue
        exported.update(getattr(module, "__all__", []))
        exported.update(name for name in module.__dict__ if not name.startswith("_"))
    return sorted(exported)
