from __future__ import annotations

from ckanext.toolbelt.magic import (  # pyright: ignore[reportMissingImports]
    reveal_readonly_scheming_fields,  # pyright: ignore[reportUnknownVariableType]
)

reveal_readonly_scheming_fields(
    {
        ("visits",): 0,
        ("downloads",): 0,
        ("visit_90_days",): 0,
        ("download_90_days",): 0,
    }
)
