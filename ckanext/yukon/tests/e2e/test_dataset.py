from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.playwright
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestSearch:
    def test_facets(self, page: Page, data: dict[str, Any]):
        """Dataset search contains expected facets."""
        page.goto("/data")
        section = page.get_by_text("Year published")
        expect(section).to_be_visible()
