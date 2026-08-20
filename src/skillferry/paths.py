"""Cross-platform path topology checks used at trust boundaries."""

from __future__ import annotations

import os
import stat
from pathlib import Path


def is_linklike(path: Path) -> bool:
    """Return true for symlinks and Windows reparse points such as junctions.

    Junctions do not report as symlinks through :class:`pathlib.Path`, but
    they can redirect traversal outside a declared workspace or managed root.
    Treat every Windows reparse point as link-like and fail closed.
    """

    if path.is_symlink():
        return True
    if os.name != "nt":
        return False
    try:
        attributes = os.lstat(path).st_file_attributes
    except (FileNotFoundError, OSError):
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
