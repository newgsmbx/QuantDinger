"""
Dashboard APIs (local-first).

Endpoints:
- GET /api/dashboard/summary
- GET /api/dashboard/pendingOrders?page=1&pageSize=20

Notes:
- Paper mode: no real trading execution. Metrics are best-effort based on local DB tables.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Tuple

from flask import Blueprint, jsonify, request

from app.utils.db import get_db_connection
from app.utils.logger import get_logger

logger = get_logger(__name__)

dashboard_bp = Blueprint("dashboard", __name__)


def _safe_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _safe_json_loads(value: Any, default: Any) -> Any:
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


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x) for x in value if str(x or "").strip()]
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        # allow comma-separated
        if "," in s:
            return [p.strip() for p in s.split(",") if p.strip()]
        return [s]
    return []


def _calc_unrealized_pnl(side: str, entry_price: float, current_price: float, size: float) -> float:
    try:
        ep = float(entry_price or 0.0)
        cp = float(current_price or 0.0)
        sz = float(size or 0.0)
        if ep <= 0 or cp <= 0 or sz <= 0:
            return 0.0
        s = (side or "").strip().lower()
        if s == "short":
            return (ep - cp) * sz
        return (cp - ep) * sz
    except Exception:
        return 0.0


def _calc_pnl_percent(entry_price: float, size: float, pnl: float, leverage: float = 1.0, market_type: str = "spot") -> float:
    try:
        denom = float(entry_price or 0.0) * float(size or 0.0)
        if denom <= 0:
            return 0.0
        lev = float(leverage or 1.0)
        if lev <= 0:
            lev = 1.0
        mt = str(market_type or "").strip().lower()
        # Margin PnL% (user expectation): pnl / (notional / leverage)
        # = pnl / notional * leverage
        mult = lev if mt in ("swap", "futures", "future", "perp", "perpetual") else 1.0
        return float(pnl) / denom * 100.0 * float(mult)
    except Exception:
        return 0.0


@dashboard_bp.route("/summary", methods=["GET"])
def summary():
    """
    Return dashboard summary used by `quantdinger_vue/src/views/dashboard/index.vue`.
    """
    try:
        # Strategy counts
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                SELECT id, strategy_name, strategy_type, status, initial_capital
                FROM qd_strategies_trading
                """
            )
            strategies = cur.fetchall() or []
            cur.close()

        running = [s for s in strategies if (s.get("status") or "").strip().lower() == "running"]
        indicator_strategy_count = len([s for s in running if (s.get("strategy_type") or "") == "IndicatorStrategy"])
        ai_strategy_count = max(0, len(running) - indicator_strategy_count)

        # Positions (best-effort)
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                SELECT p.*, s.strategy_name, s.initial_capital, s.leverage, s.market_type
                FROM qd_strategy_positions p
                LEFT JOIN qd_strategies_trading s ON s.id = p.strategy_id
                ORDER BY p.updated_at DESC
                """
            )
            rows = cur.fetchall() or []
            cur.close()

        current_positions: List[Dict[str, Any]] = []
        total_unrealized_pnl = 0.0
        for r in rows:
            pnl = _calc_unrealized_pnl(
                side=str(r.get("side") or ""),
                entry_price=float(r.get("entry_price") or 0.0),
                current_price=float(r.get("current_price") or 0.0),
                size=float(r.get("size") or 0.0),
            )
            pct = _calc_pnl_percent(
                float(r.get("entry_price") or 0.0),
                float(r.get("size") or 0.0),
                pnl,
                leverage=float(r.get("leverage") or 1.0),
                market_type=str(r.get("market_type") or "spot"),
            )
            total_unrealized_pnl += float(pnl)
            current_positions.append(
                {
                    **r,
                    "strategy_name": r.get("strategy_name") or "",
                    "unrealized_pnl": float(pnl),
                    "pnl_percent": float(pct),
                }
            )

        # Recent trades (best-effort)
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                SELECT t.*, s.strategy_name
                FROM qd_strategy_trades t
                LEFT JOIN qd_strategies_trading s ON s.id = t.strategy_id
                ORDER BY t.created_at DESC
                    LIMIT 200
                """
            )
            recent_trades = cur.fetchall() or []
            cur.close()

        # Total equity/pnl (best-effort)
        total_initial_capital = 0.0
        for s in strategies:
            try:
                total_initial_capital += float(s.get("initial_capital") or 0.0)
            except Exception:
                pass
        total_pnl = float(total_unrealized_pnl)
        total_equity = float(total_initial_capital + total_pnl)

        # Daily PnL chart (uses realized profit field if present, otherwise 0)
        # Keep output stable even if profit is mostly empty.
        day_to_profit: Dict[str, float] = {}
        for trow in recent_trades:
            ts = _safe_int(trow.get("created_at"), 0)
            if ts <= 0:
                continue
            day = time.strftime("%Y-%m-%d", time.localtime(ts))
            try:
                p = float(trow.get("profit") or 0.0)
            except Exception:
                p = 0.0
            day_to_profit[day] = float(day_to_profit.get(day, 0.0) + p)
        daily_pnl_chart = [{"date": d, "profit": float(v)} for d, v in sorted(day_to_profit.items())]

        # Strategy performance pie (use unrealized pnl by strategy as best-effort)
        sid_to_unreal: Dict[int, float] = {}
        sid_to_name: Dict[int, str] = {}
        for p in current_positions:
            sid = _safe_int(p.get("strategy_id"), 0)
            sid_to_name[sid] = str(p.get("strategy_name") or f"Strategy_{sid}")
            sid_to_unreal[sid] = float(sid_to_unreal.get(sid, 0.0) + float(p.get("unrealized_pnl") or 0.0))
        strategy_pnl_chart = [{"name": sid_to_name[sid], "value": float(val)} for sid, val in sid_to_unreal.items()]

        return jsonify(
            {
                "code": 1,
                "msg": "success",
                "data": {
                    "ai_strategy_count": int(ai_strategy_count),
                    "indicator_strategy_count": int(indicator_strategy_count),
                    "total_equity": float(total_equity),
                    "total_pnl": float(total_pnl),
                    "daily_pnl_chart": daily_pnl_chart,
                    "strategy_pnl_chart": strategy_pnl_chart,
                    "recent_trades": recent_trades,
                    "current_positions": current_positions,
                },
            }
        )
    except Exception as e:
        logger.error(f"dashboard summary failed: {e}", exc_info=True)
        return jsonify({"code": 0, "msg": str(e), "data": None}), 500


@dashboard_bp.route("/pendingOrders", methods=["GET"])
def pending_orders():
    """
    Return pending orders list for dashboard page.
    """
    try:
        page = max(1, _safe_int(request.args.get("page"), 1))
        page_size = max(1, min(200, _safe_int(request.args.get("pageSize"), 20)))
        offset = (page - 1) * page_size

        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute("SELECT COUNT(1) AS cnt FROM pending_orders")
            total = int((cur.fetchone() or {}).get("cnt") or 0)
            cur.close()

        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                SELECT o.*,
                       s.strategy_name,
                       s.notification_config AS strategy_notification_config,
                       s.exchange_config AS strategy_exchange_config,
                       s.market_type AS strategy_market_type,
                       s.market_category AS strategy_market_category,
                       s.execution_mode AS strategy_execution_mode
                FROM pending_orders o
                LEFT JOIN qd_strategies_trading s ON s.id = o.strategy_id
                ORDER BY o.id DESC
                LIMIT %s OFFSET %s
                """,
                (int(page_size), int(offset)),
            )
            rows = cur.fetchall() or []
            cur.close()

        out: List[Dict[str, Any]] = []
        for r in rows:
            status = (r.get("status") or "").strip().lower()
            if status == "sent":
                status = "completed"
            if status == "deferred":
                status = "pending"

            # Frontend expects these keys:
            # - filled_amount, filled_price, error_message
            filled_amount = float(r.get("filled") or 0.0)
            filled_price = float(r.get("avg_price") or 0.0) if float(r.get("avg_price") or 0.0) > 0 else float(r.get("price") or 0.0)

            # Derive exchange_id + notify channels without leaking secrets to frontend.
            ex_cfg = _safe_json_loads(r.get("strategy_exchange_config"), {}) or {}
            notify_cfg = _safe_json_loads(r.get("strategy_notification_config"), {}) or {}
            exchange_id = (r.get("exchange_id") or ex_cfg.get("exchange_id") or ex_cfg.get("exchangeId") or "").strip().lower()
            notify_channels = _as_list((notify_cfg or {}).get("channels"))
            if not notify_channels:
                notify_channels = ["browser"]
            market_type = (r.get("market_type") or r.get("strategy_market_type") or ex_cfg.get("market_type") or ex_cfg.get("marketType") or "").strip().lower()
            market_category = str(r.get("strategy_market_category") or "").strip().lower()
            execution_mode = str(r.get("strategy_execution_mode") or r.get("execution_mode") or "").strip().lower()

            # If non-crypto markets are "signal-only", show SIGNAL instead of blank exchange.
            exchange_display = exchange_id
            if not exchange_display:
                if execution_mode == "signal" or (market_category and market_category != "crypto"):
                    exchange_display = "signal"

            out.append(
                {
                    **r,
                    "strategy_name": r.get("strategy_name") or "",
                    "status": status,
                    "filled_amount": filled_amount,
                    "filled_price": filled_price,
                    "error_message": r.get("last_error") or "",
                    "exchange_id": exchange_id,
                    "exchange_display": exchange_display,
                    "notify_channels": notify_channels,
                    "market_type": market_type or (r.get("market_type") or ""),
                }
            )

        # Never expose these strategy-level config blobs.
        for item in out:
            try:
                item.pop("strategy_exchange_config", None)
                item.pop("strategy_notification_config", None)
                item.pop("strategy_market_type", None)
                item.pop("strategy_market_category", None)
                item.pop("strategy_execution_mode", None)
            except Exception:
                pass

        return jsonify(
            {
                "code": 1,
                "msg": "success",
                "data": {
                    "list": out,
                    "page": page,
                    "pageSize": page_size,
                    "total": total,
                },
            }
        )
    except Exception as e:
        logger.error(f"dashboard pendingOrders failed: {e}", exc_info=True)
        return jsonify({"code": 0, "msg": str(e), "data": None}), 500


@dashboard_bp.route("/pendingOrders/<int:order_id>", methods=["DELETE"])
def delete_pending_order(order_id: int):
    """
    Delete a pending order record (dashboard operation).
    """
    try:
        oid = int(order_id or 0)
        if oid <= 0:
            return jsonify({"code": 0, "msg": "invalid_id", "data": None}), 400

        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute("SELECT id, status FROM pending_orders WHERE id = %s", (oid,))
            row = cur.fetchone() or {}
            if not row:
                cur.close()
                return jsonify({"code": 0, "msg": "not_found", "data": None}), 404
            st = (row.get("status") or "").strip().lower()
            if st == "processing":
                cur.close()
                return jsonify({"code": 0, "msg": "cannot_delete_processing", "data": None}), 400
            cur.execute("DELETE FROM pending_orders WHERE id = %s", (oid,))
            db.commit()
            cur.close()

        return jsonify({"code": 1, "msg": "success", "data": {"id": oid}})
    except Exception as e:
        logger.error(f"dashboard delete pendingOrders failed: {e}", exc_info=True)
        return jsonify({"code": 0, "msg": str(e), "data": None}), 500

