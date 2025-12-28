"""
Translate a strategy signal into a direct-exchange order call.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from app.services.live_trading.base import BaseRestClient, LiveOrderResult, LiveTradingError
from app.services.live_trading.binance import BinanceFuturesClient
from app.services.live_trading.binance_spot import BinanceSpotClient
from app.services.live_trading.okx import OkxClient
from app.services.live_trading.bitget import BitgetMixClient
from app.services.live_trading.bitget_spot import BitgetSpotClient


def _signal_to_sides(signal_type: str) -> Tuple[str, str, bool]:
    """
    Returns (side, pos_side, reduce_only)
    - side: buy/sell
    - pos_side: long/short (for OKX)
    """
    sig = (signal_type or "").strip().lower()
    if sig in ("open_long", "add_long"):
        return "buy", "long", False
    if sig in ("open_short", "add_short"):
        return "sell", "short", False
    if sig in ("close_long", "reduce_long"):
        return "sell", "long", True
    if sig in ("close_short", "reduce_short"):
        return "buy", "short", True
    raise LiveTradingError(f"Unsupported signal_type: {signal_type}")


def place_order_from_signal(
    client: BaseRestClient,
    *,
    signal_type: str,
    symbol: str,
    amount: float,
    market_type: str = "swap",
    exchange_config: Optional[Dict[str, Any]] = None,
    client_order_id: Optional[str] = None,
) -> LiveOrderResult:
    if amount is None:
        amount = 0.0
    qty = float(amount or 0.0)
    if qty <= 0:
        raise LiveTradingError("Invalid amount")

    side, pos_side, reduce_only = _signal_to_sides(signal_type)

    cfg = exchange_config if isinstance(exchange_config, dict) else {}
    mt = (market_type or cfg.get("market_type") or "swap").strip().lower()
    if mt in ("futures", "future", "perp", "perpetual"):
        mt = "swap"

    # Spot does not support short signals in this system.
    if mt == "spot" and ("short" in (signal_type or "").lower()):
        raise LiveTradingError("spot market does not support short signals")

    if isinstance(client, BinanceFuturesClient):
        return client.place_market_order(
            symbol=symbol,
            side="BUY" if side == "buy" else "SELL",
            quantity=qty,
            reduce_only=reduce_only,
            position_side=pos_side,
            client_order_id=client_order_id,
        )
    if isinstance(client, OkxClient):
        td_mode = (cfg.get("margin_mode") or cfg.get("td_mode") or "cross")
        return client.place_market_order(
            symbol=symbol,
            side=side,
            pos_side=pos_side,
            size=qty,
            td_mode=str(td_mode),
            reduce_only=reduce_only,
            client_order_id=client_order_id,
        )
    if isinstance(client, BitgetMixClient):
        margin_coin = str(cfg.get("margin_coin") or cfg.get("marginCoin") or "USDT")
        product_type = str(cfg.get("product_type") or cfg.get("productType") or "USDT-FUTURES")
        margin_mode = str(cfg.get("margin_mode") or cfg.get("marginMode") or cfg.get("td_mode") or "cross")
        return client.place_market_order(
            symbol=symbol,
            side=side,
            size=qty,
            margin_coin=margin_coin,
            product_type=product_type,
            margin_mode=margin_mode,
            reduce_only=reduce_only,
            client_order_id=client_order_id,
        )
    if isinstance(client, BinanceSpotClient):
        return client.place_market_order(
            symbol=symbol,
            side="BUY" if side == "buy" else "SELL",
            quantity=qty,
            client_order_id=client_order_id,
        )
    if isinstance(client, BitgetSpotClient):
        # For spot market BUY, Bitget may expect quote size; we pass base size here and let caller override if needed.
        return client.place_market_order(
            symbol=symbol,
            side=side,
            size=qty,
            client_order_id=client_order_id,
        )

    raise LiveTradingError(f"Unsupported client type: {type(client)}")


