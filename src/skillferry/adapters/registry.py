"""Adapter registry: the single place new targets are registered."""

from __future__ import annotations

from .base import Adapter
from .claude import ClaudeAdapter
from .codex import CodexAdapter
from .dsh import DshAdapter

ADAPTERS: dict[str, Adapter] = {
    "codex": CodexAdapter(),
    "claude": ClaudeAdapter(),
    "dsh": DshAdapter(),
}


def get_adapter(name: str) -> Adapter:
    try:
        return ADAPTERS[name]
    except KeyError as exc:
        raise ValueError(f"unsupported target: {name}") from exc
