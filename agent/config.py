from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv(path: str | Path = ".env") -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ without
    overwriting variables that are already set in the real environment."""
    dotenv = Path(path).expanduser()
    if not dotenv.is_file():
        return
    for raw in dotenv.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv()


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
