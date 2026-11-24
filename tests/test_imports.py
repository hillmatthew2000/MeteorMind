import importlib

import pytest

MODULES = [
    "meteormind",
    "meteormind.__main__",
    "meteormind.api",
    "meteormind.cli",
    "meteormind.cache",
    "meteormind.config",
    "meteormind.console",
    "meteormind.demo",
    "meteormind.gui",
    "meteormind.history",
    "meteormind.jsonio",
    "meteormind.menu",
    "meteormind.models",
    "meteormind.paths",
    "meteormind.preferences",
    "meteormind.reporting",
    "meteormind.service",
    "meteormind.storage",
    "meteormind.units",
    "meteormind.validation",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name: str) -> None:
    importlib.import_module(name)
