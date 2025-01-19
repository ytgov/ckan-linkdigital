"""Template helpers of the yukon plugin.

All non-private functions defined here are registered inside `tk.h` collection.
"""

from __future__ import annotations


def yukon_hello() -> str:
    """Greet the user.

    Returns:
        greeting with the plugin name.
    """
    return "Hello, yukon!"
