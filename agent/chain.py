from __future__ import annotations

import json
import time
import urllib.error
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
        config.rpc_url, data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) nunes-ai/0.1.0",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read().decode()).get("error", {}).get("message", "")
        except Exception:
            pass
        raise RuntimeError(f"RPC {method} HTTP {exc.code}: {detail or exc.reason}") from exc
    if "error" in result:
        raise RuntimeError(f"RPC error ({method}): {result['error']}")
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

    def transfer(self, to: str, amount: int) -> tuple[str, str]:
        """Send `amount` USDC (base units) to `to`.

        Returns (tx_hash, receipt_status) where receipt_status is "1" if the
        tx was mined and succeeded, "0" if it reverted, or "pending" if the
        receipt did not arrive within the wait window."""
        chain_id = int(_rpc("eth_chainId", []), 16)
        if chain_id != BASE_SEPOLIA_CHAIN_ID:
            raise RuntimeError(
                f"BASE_RPC_URL is on chain {chain_id}, but the agent only signs "
                f"for Base Sepolia ({BASE_SEPOLIA_CHAIN_ID}) - refusing to broadcast"
            )
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
        raw_hex = "0x" + signed.raw_transaction.hex()
        hash_hex = str(_rpc("eth_sendRawTransaction", [raw_hex]))
        # signed.hash is a HexBytes (bytes subclass); normalize both sides to a
        # lowercase 0x-prefixed string before comparing.
        if isinstance(signed.hash, bytes):
            local_hex = "0x" + signed.hash.hex()
        else:
            local_hex = str(signed.hash)
        if hash_hex.lower() != local_hex.lower():
            raise RuntimeError(
                f"RPC returned a different tx hash ({hash_hex}) than the locally "
                f"signed one ({local_hex}) - refusing to trust it"
            )
        return hash_hex, self.wait_for_receipt(hash_hex)

    def wait_for_receipt(self, tx_hash: str, timeout: float = 45.0, poll: float = 2.0) -> str:
        """Poll for the receipt. Returns the receipt status normalized to '1'
        (success), '0' (reverted), or 'pending' if it did not confirm within
        `timeout` seconds.

        RPC nodes disagree on the status encoding (some return hex '0x1',
        some decimal-ish '1'), so the raw value is normalized here rather than
        at the call sites - a raw '0x1' slipping through a `!= '1'` check would
        mislabel a successful settlement as a revert and allow a double-pay."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            receipt = _rpc("eth_getTransactionReceipt", [tx_hash])
            if receipt:
                status = str(receipt.get("status", "0"))
                if status in ("1", "0x1", "0x01"):
                    return "1"
                if status in ("0", "0x0", "0x00"):
                    return "0"
                return "pending"
            time.sleep(poll)
        return "pending"

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
