import importlib

import pytest

MODULES = [
    "meteormind",
    "meteormind.__main__",
    "meteormind.api",
    "meteormind.cli",
    "meteormind.config",
    "meteormind.gui",
    "meteormind.history",
    "meteormind.models",
    "meteormind.reporting",
    "meteormind.storage",
    "meteormind.units",
    "meteormind.validation",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name: str) -> None:
    importlib.import_module(name)
