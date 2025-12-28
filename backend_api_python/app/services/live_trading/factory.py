"""
Factory for direct exchange clients.
"""

from __future__ import annotations

from typing import Any, Dict

from app.services.live_trading.base import BaseRestClient, LiveTradingError
from app.services.live_trading.binance import BinanceFuturesClient
from app.services.live_trading.binance_spot import BinanceSpotClient
from app.services.live_trading.okx import OkxClient
from app.services.live_trading.bitget import BitgetMixClient
from app.services.live_trading.bitget_spot import BitgetSpotClient


def _get(cfg: Dict[str, Any], *keys: str) -> str:
    for k in keys:
        v = cfg.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def create_client(exchange_config: Dict[str, Any], *, market_type: str = "swap") -> BaseRestClient:
    if not isinstance(exchange_config, dict):
        raise LiveTradingError("Invalid exchange_config")
    exchange_id = _get(exchange_config, "exchange_id", "exchangeId").lower()
    api_key = _get(exchange_config, "api_key", "apiKey")
    secret_key = _get(exchange_config, "secret_key", "secret")
    passphrase = _get(exchange_config, "passphrase", "password")

    mt = (market_type or exchange_config.get("market_type") or exchange_config.get("defaultType") or "swap").strip().lower()
    if mt in ("futures", "future", "perp", "perpetual"):
        mt = "swap"

    if exchange_id == "binance":
        if mt == "spot":
            base_url = _get(exchange_config, "base_url", "baseUrl") or "https://api.binance.com"
            return BinanceSpotClient(api_key=api_key, secret_key=secret_key, base_url=base_url)
        # Default to USDT-M futures
        base_url = _get(exchange_config, "base_url", "baseUrl") or "https://fapi.binance.com"
        return BinanceFuturesClient(api_key=api_key, secret_key=secret_key, base_url=base_url)
    if exchange_id == "okx":
        base_url = _get(exchange_config, "base_url", "baseUrl") or "https://www.okx.com"
        return OkxClient(api_key=api_key, secret_key=secret_key, passphrase=passphrase, base_url=base_url)
    if exchange_id == "bitget":
        base_url = _get(exchange_config, "base_url", "baseUrl") or "https://api.bitget.com"
        if mt == "spot":
            channel_api_code = _get(exchange_config, "channel_api_code", "channelApiCode") or "bntva"
            return BitgetSpotClient(api_key=api_key, secret_key=secret_key, passphrase=passphrase, base_url=base_url, channel_api_code=channel_api_code)
        return BitgetMixClient(api_key=api_key, secret_key=secret_key, passphrase=passphrase, base_url=base_url)

    raise LiveTradingError(f"Unsupported exchange_id: {exchange_id}")


