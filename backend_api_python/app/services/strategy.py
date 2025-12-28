import os
import time
import json
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.utils.logger import get_logger
from app.utils.db import get_db_connection

logger = get_logger(__name__)

class StrategyService:
    """Strategy service."""
    
    # 类变量：限制连接测试并发数
    _connection_test_semaphore = threading.Semaphore(5)
    
    def __init__(self):
        # Local deployment: do not use encryption/decryption.
        pass
        
    def get_running_strategies(self) -> List[Dict[str, Any]]:
        """获取所有运行中的策略（仅ID）"""
        try:
            with get_db_connection() as db:
                cursor = db.cursor()
                query = "SELECT id FROM qd_strategies_trading WHERE status = 'running'"
                cursor.execute(query)
                results = cursor.fetchall()
                cursor.close()
                return [row['id'] for row in results]
        except Exception as e:
            logger.error(f"Failed to fetch running strategies: {str(e)}")
            return []

    def get_running_strategies_with_type(self) -> List[Dict[str, Any]]:
        """获取所有运行中的策略（包含类型信息）"""
        try:
            with get_db_connection() as db:
                cursor = db.cursor()
                # 假设 qd_strategies_trading 表中有 strategy_type 字段
                # 如果没有，可能需要关联查询或者根据其他字段判断
                # 这里假设表结构已更新
                query = "SELECT id, strategy_type FROM qd_strategies_trading WHERE status = 'running'"
                cursor.execute(query)
                results = cursor.fetchall()
                cursor.close()
                
                strategies = [{'id': row['id'], 'strategy_type': row.get('strategy_type', '')} for row in results]
                logger.info(f"Found {len(strategies)} running strategies: {strategies}")
                return strategies
                
        except Exception as e:
            logger.error(f"Failed to fetch running strategies: {str(e)}")
            return []
    
    def get_exchange_symbols(self, exchange_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取交易所交易对列表 (无需API Key)
        """
        try:
            import ccxt
            
            exchange_id = exchange_config.get('exchange_id', '')
            proxies = exchange_config.get('proxies')
            
            if not exchange_id:
                return {'success': False, 'message': '请选择交易所', 'symbols': []}
            
            # 创建交易所实例 (public only)
            exchange_class = getattr(ccxt, exchange_id, None)
            if not exchange_class:
                return {'success': False, 'message': f'不支持的交易所: {exchange_id}', 'symbols': []}
            
            exchange_config_dict = {
                'enableRateLimit': True,
                'options': {'defaultType': 'swap'} # 默认为 swap
            }
            if proxies:
                exchange_config_dict['proxies'] = proxies
            
            exchange = exchange_class(exchange_config_dict)
            markets = exchange.load_markets()
            
            symbols = []
            for symbol, market in markets.items():
                if market.get('active', False) and market.get('quote') == 'USDT':
                    symbols.append(symbol)
            
            symbols.sort()
            return {'success': True, 'message': f'获取成功，共 {len(symbols)} 个交易对', 'symbols': symbols}
            
        except Exception as e:
            logger.error(f"Failed to fetch symbols: {str(e)}")
            return {'success': False, 'message': f'获取交易对失败: {str(e)}', 'symbols': []}
    
    def test_exchange_connection(self, exchange_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test exchange connection via direct REST clients (no ccxt).

        Notes:
        - This is local-only; failures are returned as user-friendly messages.
        - We do not log secrets.
        """
        # Limit concurrency to protect CPU / rate limits
        with StrategyService._connection_test_semaphore:
            try:
                from app.services.exchange_execution import resolve_exchange_config, safe_exchange_config_for_log
                from app.services.live_trading.factory import create_client
                from app.services.live_trading.binance import BinanceFuturesClient
                from app.services.live_trading.binance_spot import BinanceSpotClient
                from app.services.live_trading.okx import OkxClient
                from app.services.live_trading.bitget import BitgetMixClient

                resolved = resolve_exchange_config(exchange_config or {})
                safe_cfg = safe_exchange_config_for_log(resolved)

                exchange_id = (resolved.get("exchange_id") or "").strip().lower()
                if not exchange_id:
                    return {'success': False, 'message': 'Missing exchange_id', 'data': None}

                # IMPORTANT:
                # Test connection should respect configured market_type (spot vs swap).
                # Otherwise Binance will default to futures endpoints (fapi) and spot-only keys will fail with -2015.
                market_type = str(resolved.get("market_type") or resolved.get("defaultType") or "swap").strip().lower()
                client = create_client(resolved, market_type=market_type)
                client_kind = type(client).__name__

                # Best-effort detect current egress IP (for Binance IP whitelist debugging).
                egress_ip = ""
                try:
                    import requests as _rq
                    egress_ip = str(_rq.get("https://ifconfig.me/ip", timeout=5).text or "").strip()
                except Exception:
                    egress_ip = ""

                # 1) Public connectivity
                ok_public = False
                try:
                    ok_public = bool(getattr(client, "ping")())
                except Exception:
                    ok_public = False
                if not ok_public:
                    return {
                        'success': False,
                        'message': f'Public ping failed: {exchange_id}',
                        'data': {'exchange': safe_cfg, 'client': client_kind, 'market_type': market_type, 'egress_ip': egress_ip},
                    }

                # 2) Private credential validation (best-effort)
                priv_data = None
                try:
                    if isinstance(client, BinanceFuturesClient):
                        priv_data = client.get_account()
                    elif isinstance(client, BinanceSpotClient):
                        priv_data = client.get_account()
                    elif isinstance(client, OkxClient):
                        priv_data = client.get_balance()
                    elif isinstance(client, BitgetMixClient):
                        product_type = str(resolved.get("product_type") or resolved.get("productType") or "USDT-FUTURES")
                        priv_data = client.get_accounts(product_type=product_type)
                except Exception as e:
                    msg = str(e)
                    # Add actionable hints for the most common Binance auth error.
                    if exchange_id == "binance" and ("-2015" in msg or "Invalid API-key, IP, or permissions" in msg):
                        # Auto A/B test: try the other market_type once to pinpoint permission mismatch.
                        alt_market_type = "spot" if market_type != "spot" else "swap"
                        alt_client_kind = ""
                        alt_base_url = ""
                        alt_ok = False
                        try:
                            alt_client = create_client(resolved, market_type=alt_market_type)
                            alt_client_kind = type(alt_client).__name__
                            alt_base_url = getattr(alt_client, "base_url", "") or ""
                            if isinstance(alt_client, BinanceFuturesClient) or isinstance(alt_client, BinanceSpotClient):
                                _ = alt_client.get_account()
                                alt_ok = True
                        except Exception:
                            alt_ok = False

                        base_url = getattr(client, "base_url", "") or ""
                        hint = (
                            f"Binance auth failed (-2015). Verify: "
                            f"(1) IP whitelist includes this server egress IP={egress_ip or 'unknown'}, "
                            f"(2) API key permissions match market_type={market_type} "
                            f"(spot requires Spot permissions; swap requires Futures permissions), "
                            f"(3) you're using binance.com keys for base_url={base_url or 'unknown'}."
                        )
                        if alt_ok:
                            hint += (
                                f" Auto-check: your key works for market_type={alt_market_type} "
                                f"(client={alt_client_kind}, base_url={alt_base_url or 'unknown'}) "
                                f"but fails for market_type={market_type}. This is almost always a permissions/product mismatch."
                            )
                        msg = f"{msg} | {hint}"
                    return {
                        'success': False,
                        'message': f'Auth failed: {msg}',
                        'data': {
                            'exchange': safe_cfg,
                            'client': client_kind,
                            'market_type': market_type,
                            'egress_ip': egress_ip,
                            'base_url': getattr(client, "base_url", "") or "",
                        },
                    }

                return {
                    'success': True,
                    'message': 'Connection OK',
                    'data': {
                        'exchange': safe_cfg,
                        'client': client_kind,
                        'market_type': market_type,
                        'egress_ip': egress_ip,
                        'base_url': getattr(client, "base_url", "") or "",
                        'private': priv_data,
                    },
                }
            except Exception as e:
                logger.error(f"test_exchange_connection failed: {str(e)}")
                return {'success': False, 'message': f'Connection failed: {str(e)}', 'data': None}

    def get_strategy_type(self, strategy_id: int) -> str:
        """Get strategy type from DB."""
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                cur.execute(
                    "SELECT strategy_type FROM qd_strategies_trading WHERE id = ?",
                    (strategy_id,)
                )
                row = cur.fetchone()
                cur.close()
            return (row or {}).get('strategy_type') or 'IndicatorStrategy'
        except Exception:
            return 'IndicatorStrategy'

    def update_strategy_status(self, strategy_id: int, status: str) -> bool:
        """Update strategy status."""
        try:
            now = int(time.time())
            with get_db_connection() as db:
                cur = db.cursor()
                cur.execute(
                    "UPDATE qd_strategies_trading SET status = ?, updated_at = ? WHERE id = ?",
                    (status, now, strategy_id)
                )
                db.commit()
                cur.close()
            return True
        except Exception as e:
            logger.error(f"update_strategy_status failed: {e}")
            return False

    def _safe_json_loads(self, value: Any, default: Any):
        """Load JSON string into Python object (local deployment: plaintext only)."""
        if value is None:
            return default
        if isinstance(value, (dict, list)):
            return value
        if not isinstance(value, str):
            return default
        s = value.strip()
        if not s:
            return default
        try:
            return json.loads(s)
        except Exception:
            return default

    def _dump_json_or_encrypt(self, obj: Any, encrypt: bool = False) -> str:
        if obj is None:
            return ''
        # Local deployment: always store plaintext JSON.
        return json.dumps(obj, ensure_ascii=False)

    def list_strategies(self, user_id: int = 1) -> List[Dict[str, Any]]:
        """List strategies for local single-user."""
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                cur.execute(
                    """
                    SELECT *
                    FROM qd_strategies_trading
                    ORDER BY id DESC
                    """
                )
                rows = cur.fetchall() or []
                cur.close()

            out = []
            for r in rows:
                ex = self._safe_json_loads(r.get('exchange_config'), {})
                ind = self._safe_json_loads(r.get('indicator_config'), {})
                tr = self._safe_json_loads(r.get('trading_config'), {})
                ai = self._safe_json_loads(r.get('ai_model_config'), {})
                notify = self._safe_json_loads(r.get('notification_config'), {})
                out.append({
                    **r,
                    'exchange_config': ex,
                    'indicator_config': ind,
                    'trading_config': tr,
                    'ai_model_config': ai,
                    'notification_config': notify
                })
            return out
        except Exception as e:
            logger.error(f"list_strategies failed: {e}")
            return []

    def get_strategy(self, strategy_id: int) -> Optional[Dict[str, Any]]:
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                cur.execute("SELECT * FROM qd_strategies_trading WHERE id = ?", (strategy_id,))
                r = cur.fetchone()
                cur.close()
            if not r:
                return None
            r['exchange_config'] = self._safe_json_loads(r.get('exchange_config'), {})
            r['indicator_config'] = self._safe_json_loads(r.get('indicator_config'), {})
            r['trading_config'] = self._safe_json_loads(r.get('trading_config'), {})
            r['ai_model_config'] = self._safe_json_loads(r.get('ai_model_config'), {})
            r['notification_config'] = self._safe_json_loads(r.get('notification_config'), {})
            return r
        except Exception as e:
            logger.error(f"get_strategy failed: {e}")
            return None

    def create_strategy(self, payload: Dict[str, Any]) -> int:
        now = int(time.time())
        name = (payload.get('strategy_name') or '').strip()
        if not name:
            raise ValueError("strategy_name is required")

        strategy_type = payload.get('strategy_type') or 'IndicatorStrategy'
        market_category = payload.get('market_category') or 'Crypto'
        execution_mode = payload.get('execution_mode') or 'signal'
        notification_config = payload.get('notification_config') or {}

        indicator_config = payload.get('indicator_config') or {}
        trading_config = payload.get('trading_config') or {}
        exchange_config = payload.get('exchange_config') or {}

        # Denormalized fields for quick list rendering
        symbol = (trading_config or {}).get('symbol')
        timeframe = (trading_config or {}).get('timeframe')
        initial_capital = (trading_config or {}).get('initial_capital') or payload.get('initial_capital') or 1000
        leverage = (trading_config or {}).get('leverage') or 1
        market_type = (trading_config or {}).get('market_type') or 'swap'

        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                INSERT INTO qd_strategies_trading
                (strategy_name, strategy_type, market_category, execution_mode, notification_config,
                 status, symbol, timeframe, initial_capital, leverage, market_type,
                 exchange_config, indicator_config, trading_config, ai_model_config, decide_interval,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    strategy_type,
                    market_category,
                    execution_mode,
                    self._dump_json_or_encrypt(notification_config, encrypt=False),
                    payload.get('status') or 'stopped',
                    symbol,
                    timeframe,
                    float(initial_capital or 1000),
                    int(leverage or 1),
                    market_type,
                    self._dump_json_or_encrypt(exchange_config, encrypt=False) if exchange_config else '',
                    self._dump_json_or_encrypt(indicator_config, encrypt=False),
                    self._dump_json_or_encrypt(trading_config, encrypt=False),
                    self._dump_json_or_encrypt(payload.get('ai_model_config') or {}, encrypt=False),
                    int(payload.get('decide_interval') or 300),
                    now,
                    now
                )
            )
            new_id = cur.lastrowid
            db.commit()
            cur.close()
        return int(new_id)

    def update_strategy(self, strategy_id: int, payload: Dict[str, Any]) -> bool:
        now = int(time.time())
        existing = self.get_strategy(strategy_id)
        if not existing:
            return False

        # Merge: allow partial updates
        name = (payload.get('strategy_name') or existing.get('strategy_name') or '').strip()
        market_category = payload.get('market_category') or existing.get('market_category') or 'Crypto'
        execution_mode = payload.get('execution_mode') or existing.get('execution_mode') or 'signal'
        notification_config = payload.get('notification_config') if payload.get('notification_config') is not None else (existing.get('notification_config') or {})

        indicator_config = payload.get('indicator_config') if payload.get('indicator_config') is not None else (existing.get('indicator_config') or {})
        trading_config = payload.get('trading_config') if payload.get('trading_config') is not None else (existing.get('trading_config') or {})
        exchange_config = payload.get('exchange_config') if payload.get('exchange_config') is not None else (existing.get('exchange_config') or {})

        symbol = (trading_config or {}).get('symbol')
        timeframe = (trading_config or {}).get('timeframe')
        initial_capital = (trading_config or {}).get('initial_capital') or existing.get('initial_capital') or 1000
        leverage = (trading_config or {}).get('leverage') or existing.get('leverage') or 1
        market_type = (trading_config or {}).get('market_type') or existing.get('market_type') or 'swap'

        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                UPDATE qd_strategies_trading
                SET strategy_name = ?,
                    market_category = ?,
                    execution_mode = ?,
                    notification_config = ?,
                    symbol = ?,
                    timeframe = ?,
                    initial_capital = ?,
                    leverage = ?,
                    market_type = ?,
                    exchange_config = ?,
                    indicator_config = ?,
                    trading_config = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    name,
                    market_category,
                    execution_mode,
                    self._dump_json_or_encrypt(notification_config, encrypt=False),
                    symbol,
                    timeframe,
                    float(initial_capital or 1000),
                    int(leverage or 1),
                    market_type,
                    self._dump_json_or_encrypt(exchange_config, encrypt=False) if exchange_config else '',
                    self._dump_json_or_encrypt(indicator_config, encrypt=False),
                    self._dump_json_or_encrypt(trading_config, encrypt=False),
                    now,
                    strategy_id
                )
            )
            db.commit()
            cur.close()
        return True

    def delete_strategy(self, strategy_id: int) -> bool:
        try:
            with get_db_connection() as db:
                cur = db.cursor()
                cur.execute("DELETE FROM qd_strategies_trading WHERE id = ?", (strategy_id,))
                db.commit()
                cur.close()
            return True
        except Exception as e:
            logger.error(f"delete_strategy failed: {e}")
            return False
