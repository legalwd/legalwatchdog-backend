"""Model module registration helpers for SQLAlchemy mapper initialization."""

import importlib
import pkgutil


def ensure_model_modules_loaded() -> None:
    """Import all v1 model modules so SQLAlchemy relationships resolve reliably.

    SQLAlchemy resolves string-based relationship targets at mapper-configuration
    time. In worker processes that lazily import only a subset of modules, some
    model classes may never be imported, causing mapper initialization failures.

    Returns:
        None: Imports modules for side effects only.

    Examples:
        >>> ensure_model_modules_loaded()
    """
    package = importlib.import_module("app.api.modules.v1")
    for module_info in pkgutil.walk_packages(package.__path__, f"{package.__name__}."):
        module_name = module_info.name
        if ".models." not in module_name:
            continue
        importlib.import_module(module_name)
