from __future__ import annotations

import pytest


@pytest.mark.usefixtures("with_plugins", "clean_db")
def test_plugin_loads():
    """Plugin can be enabled without errors."""
    assert True
