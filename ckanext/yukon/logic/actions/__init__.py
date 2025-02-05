from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ckanext.toolbelt.decorators import Collector

from . import (
    user,
)


action, get_main_actions = Collector("yukon").split()


def get_actions() -> dict[str, Callable[..., Any]]:
    return {
        **user.get_actions(),
}