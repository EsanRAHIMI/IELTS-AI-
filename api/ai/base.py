"""Abstract AI provider interface."""
from __future__ import annotations
from abc import ABC, abstractmethod


class AIProvider(ABC):
    """Common interface every provider must implement."""

    name: str = "base"

    @abstractmethod
    async def complete(self, prompt: str, *, system: str | None = None, json_mode: bool = False) -> str:
        """Return a text (or JSON string) completion for the given prompt."""
        raise NotImplementedError

    @property
    @abstractmethod
    def configured(self) -> bool:
        """Whether the provider has the credentials/config it needs."""
        raise NotImplementedError
