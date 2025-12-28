"""
Symbol normalization helpers.

Input symbols may come from UI/strategy config in ccxt-like shape:
- "SOL/USDT:USDT"
- "SOL/USDT"

We convert them into exchange-specific identifiers.
"""

from __future__ import annotations

from typing import Tuple


def _split_base_quote(symbol: str) -> Tuple[str, str]:
    s = (symbol or "").strip()
    if ":" in s:
        s = s.split(":", 1)[0]
    if "/" not in s:
        # Already exchange-specific (best-effort)
        return s, ""
    base, quote = s.split("/", 1)
    return base.strip().upper(), quote.strip().upper()


def to_binance_futures_symbol(symbol: str) -> str:
    base, quote = _split_base_quote(symbol)
    if not quote:
        return (symbol or "").replace("/", "").replace(":", "").upper()
    return f"{base}{quote}"


def to_okx_swap_inst_id(symbol: str) -> str:
    base, quote = _split_base_quote(symbol)
    if not base or not quote:
        return symbol
    # OKX perpetual swap instrument id: BASE-QUOTE-SWAP
    return f"{base}-{quote}-SWAP"


def to_okx_spot_inst_id(symbol: str) -> str:
    base, quote = _split_base_quote(symbol)
    if not base or not quote:
        return symbol
    return f"{base}-{quote}"


def to_bitget_um_symbol(symbol: str) -> str:
    base, quote = _split_base_quote(symbol)
    if not quote:
        return (symbol or "").replace("/", "").replace(":", "").upper()
    return f"{base}{quote}"


