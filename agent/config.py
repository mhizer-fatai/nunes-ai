from __future__ import annotations

import os
from pathlib import Path


def _default_db() -> Path:
    override = os.environ.get("NUNES_AI_MEMORY_DB")
    if override:
        return Path(override).expanduser()
    return Path("~/.sibyl-memory/nunes-ai.db").expanduser()


class Config:
    """Environment-driven configuration for the Nunes AI agent."""

    def __init__(self) -> None:
        self.memory_db: Path = _default_db()
        self.rpc_url: str | None = os.environ.get("BASE_RPC_URL")
        self.private_key: str | None = os.environ.get("BASE_PRIVATE_KEY")
        self.usdc_address: str = os.environ.get(
            "USDC_ADDRESS",
            # USDC on Base Sepolia
            "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        )
        self.simulate: bool = os.environ.get("NUNES_AI_SIMULATE", "0") == "1"

    @property
    def can_execute(self) -> bool:
        return bool(self.rpc_url and self.private_key)


config = Config()
