from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Page, expect
from ckan import types


@pytest.mark.playwright
@pytest.mark.usefixtures("with_plugins", "clean_db")
class TestSearch:
    def test_facets(self, page: Page, data_factory: types.TestFactory, group: dict[str, Any]):
        """Group page does not contains the "Year published" facet."""
        data_factory(groups=[{"name": group["name"]}])
        page.goto("/group/" + group["name"])
        section = page.get_by_text("Year published")
        expect(section).not_to_be_visible()
