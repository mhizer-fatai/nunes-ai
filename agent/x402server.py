from __future__ import annotations

"""Demo x402 vendor: a paywalled data feed on Base Sepolia.

This is the *other side* of the protocol - the shop our payments agent buys
from. It exists so the full loop (402 -> memory guard -> signature ->
facilitator settlement -> 200) can run for real on testnet.

    python -m agent.x402server --port 8077 --pay-to 0x... --amount-usdc 0.01

Settlement is performed by the public testnet facilitator
(https://x402.org/facilitator); this server never touches private keys.
"""

import argparse
import base64
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from .config import config

USDC_DECIMALS = 10 ** 6
X402_BASE_SEPOLIA = "eip155:84532"


def _b64_json(payload: dict) -> str:
    return base64.b64encode(json.dumps(payload).encode()).decode()


def payment_required_header(*, pay_to: str, amount_units: int, resource_url: str) -> str:
    from x402.schemas.payments import PaymentRequired
    pr = PaymentRequired(accepts=[{
        "scheme": "exact",
        "network": X402_BASE_SEPOLIA,
        "asset": config.usdc_address,
        "amount": str(amount_units),
        "payTo": pay_to,
        "maxTimeoutSeconds": 300,
        "extra": {"name": "USDC", "version": "2"},
    }], resource={"url": resource_url,
                  "description": "Nunes demo data feed (testnet)"})
    return base64.b64encode(pr.model_dump_json().encode()).decode()


def verify_and_settle(sig_header: str):
    """Decode the client's signature, verify + settle via the public testnet
    facilitator. Returns the SettleResponse."""
    from x402 import parse_payment_payload
    from x402.http.facilitator_client import HTTPFacilitatorClientSync
    from x402.http.utils import decode_payment_signature_header
    from x402.schemas.config import FacilitatorConfig

    raw = decode_payment_signature_header(sig_header)
    # decode_ already returns a PaymentPayload; parse only raw bytes/dicts.
    if isinstance(raw, (bytes, str, dict)):
        if isinstance(raw, str):
            raw = raw.encode()
        payload = parse_payment_payload(raw)
    else:
        payload = raw
    requirements = payload.accepted
    facilitator = HTTPFacilitatorClientSync(
        FacilitatorConfig(url="https://x402.org/facilitator"))
    try:
        verified = facilitator.verify(payload, requirements)
        if not getattr(verified, "is_valid", False):
            raise RuntimeError(f"facilitator rejected payment: {verified!r}")
        settled = facilitator.settle(payload, requirements)
        if not getattr(settled, "success", False):
            raise RuntimeError(f"facilitator failed to settle: {settled!r}")
        return settled
    finally:
        facilitator.close()


def make_handler(*, pay_to: str, amount_units: int, feed_body: dict):
    from x402 import SettleResponse

    class FeedHandler(BaseHTTPRequestHandler):
        server_version = "nunes-x402-demo"

        def log_message(self, *args):  # keep demo output clean
            pass

        def _send(self, status: int, headers: dict, body: bytes) -> None:
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/feed":
                self._send(404, {"Content-Type": "text/plain"}, b"not found")
                return
            url = f"http://{self.headers.get('Host', 'localhost')}/feed"
            sig = self.headers.get("PAYMENT-SIGNATURE")
            if not sig:
                header = payment_required_header(pay_to=pay_to,
                                                 amount_units=amount_units,
                                                 resource_url=url)
                self._send(402, {"PAYMENT-REQUIRED": header,
                                 "Content-Type": "application/json"},
                           json.dumps({"error": "payment required"}).encode())
                return
            try:
                settled = verify_and_settle(sig)
            except Exception as exc:
                self._send(402, {"Content-Type": "application/json"},
                           json.dumps({"error": f"payment invalid: {exc}"}).encode())
                return
            sr = SettleResponse(success=True,
                                transaction=getattr(settled, "transaction", ""),
                                network=X402_BASE_SEPOLIA)
            resp_header = base64.b64encode(sr.model_dump_json().encode()).decode()
            self._send(200, {"Content-Type": "application/json",
                             "PAYMENT-RESPONSE": resp_header},
                       json.dumps(feed_body).encode())

    return FeedHandler


def run_server(port: int, pay_to: str, amount_units: int) -> HTTPServer:
    feed = {"feed": "nunes-demo",
            "candle": {"pair": "ETH/USDC", "close": "3120.5", "ts": "2026-09-04"}}
    handler = make_handler(pay_to=pay_to, amount_units=amount_units, feed_body=feed)
    server = HTTPServer(("127.0.0.1", port), handler)
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Nunes demo x402 vendor (Base Sepolia).")
    parser.add_argument("--port", type=int, default=8077)
    parser.add_argument("--pay-to", required=True, help="USDC recipient for feed purchases")
    parser.add_argument("--amount-usdc", type=float, default=0.01)
    args = parser.parse_args(argv)
    amount_units = int(round(args.amount_usdc * USDC_DECIMALS))
    server = run_server(args.port, args.pay_to, amount_units)
    print(f"nunes x402 demo vendor on :{args.port}/feed")
    print(f"  price: {args.amount_usdc} USDC -> {args.pay_to} ({X402_BASE_SEPOLIA})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
