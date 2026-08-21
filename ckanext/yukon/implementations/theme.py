"""ITheme implementation for the Yukon theme."""

from __future__ import annotations

import pathlib

from typing_extensions import override

from ckanext.theming import lib
from ckanext.theming.base import BaseTheme
from ckanext.theming.interfaces import ITheme

root = pathlib.Path(__file__).parent.parent


class Theme(ITheme):
    @override
    def register_themes(self) -> list[BaseTheme]:
        return [lib.Theme("yukon", str(root))]
