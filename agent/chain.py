from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

from eth_account import Account
from eth_utils import keccak

from .config import config

ERC20_TRANSFER_SIG = keccak(text="transfer(address,uint256)")[:4].hex()
BASE_SEPOLIA_CHAIN_ID = 84532


def _encode_address(value: str) -> str:
    return value[2:].rjust(64, "0")


def _encode_uint(value: int) -> str:
    return f"{value:064x}"


def _rpc(method: str, params: list[Any]) -> Any:
    if not config.rpc_url:
        raise RuntimeError("BASE_RPC_URL is not set")
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    ).encode()
    req = urllib.request.Request(
        config.rpc_url, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())
    if "error" in result:
        raise RuntimeError(f"RPC error: {result['error']}")
    return result["result"]


def simulate_transfer(to: str, amount: int) -> str:
    """Deterministic fake tx hash for simulation / demo mode."""
    digest = keccak(text=f"{to}:{amount}:{time.time_ns()}").hex()[:62]
    return "0xsim" + digest


class BaseChain:
    """Minimal Base settlement client.

    Signs a real ERC-20 `transfer` of USDC and broadcasts it over the Base RPC.
    Returns the onchain tx hash that the guard journals back into memory.
    """

    def __init__(self) -> None:
        if not config.private_key:
            raise RuntimeError("BASE_PRIVATE_KEY is not set")
        self.signer = Account.from_key(config.private_key)
        self.address = self.signer.address

    def transfer(self, to: str, amount: int) -> str:
        """Send `amount` USDC (base units) to `to`. Returns the tx hash."""
        data = "0x" + ERC20_TRANSFER_SIG + _encode_address(to) + _encode_uint(amount)
        tx: dict[str, Any] = {
            "to": config.usdc_address,
            "value": 0,
            "data": data,
            "nonce": int(_rpc("eth_getTransactionCount", [self.address, "latest"]), 16),
            "chainId": BASE_SEPOLIA_CHAIN_ID,
            "gas": self._estimate_gas(to, amount, data),
            "gasPrice": int(_rpc("eth_gasPrice", []), 16),
        }
        signed = self.signer.sign_transaction(tx)
        hash_hex = _rpc("eth_sendRawTransaction", [signed.raw_transaction.hex()])
        return str(hash_hex)

    def _estimate_gas(self, to: str, amount: int, data: str) -> int:
        try:
            est = int(
                _rpc(
                    "eth_estimateGas",
                    [{"from": self.address, "to": config.usdc_address, "data": data}],
                ),
                16,
            )
            return est + 50_000  # buffer for USDC internal transfers
        except Exception:
            return 250_000
