from __future__ import annotations

from datetime import UTC, datetime

import ckan.plugins.toolkit as tk

Base = tk.BaseModel


def now():
    return datetime.now(UTC)
