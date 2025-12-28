"""
回测服务
"""
import math
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import pandas as pd
import numpy as np

from app.data_sources import DataSourceFactory
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BacktestService:
    """回测服务"""
    
    # 时间周期秒数
    TIMEFRAME_SECONDS = {
        '1m': 60, '5m': 300, '15m': 900, '30m': 1800,
        '1H': 3600, '4H': 14400, '1D': 86400, '1W': 604800
    }
    
    def run_code_strategy(
        self,
        code: str,
        symbol: str,
        timeframe: str,
        limit: int = 1000
    ) -> Dict[str, Any]:
        """
        运行策略代码并返回代码中定义的 'output' 变量。
        用于信号机器人的预览功能。
        """
        # 1. 计算时间范围
        end_date = datetime.now()
        tf_seconds = self.TIMEFRAME_SECONDS.get(timeframe, 3600)
        start_date = end_date - timedelta(seconds=tf_seconds * limit)
        
        # 2. 获取数据 (假设 market='crypto'，后续可优化)
        df = self._fetch_kline_data('crypto', symbol, timeframe, start_date, end_date)
        
        if df.empty:
            return {"error": "No data found"}

        # 3. 准备执行环境
        local_vars = {
            'df': df.copy(),
            'np': np,
            'pd': pd,
            'output': {} # 默认空输出
        }
        
        # 4. 执行代码
        try:
            import builtins
            def safe_import(name, *args, **kwargs):
                allowed = ['numpy', 'pandas', 'math', 'json', 'datetime', 'time']
                if name in allowed or name.split('.')[0] in allowed:
                    return builtins.__import__(name, *args, **kwargs)
                raise ImportError(f"Import not allowed: {name}")
            
            safe_builtins = {k: getattr(builtins, k) for k in dir(builtins) 
                           if not k.startswith('_') and k not in ['eval', 'exec', 'compile', 'open', 'input', 'exit']}
            safe_builtins['__import__'] = safe_import
            
            exec_env = local_vars.copy()
            exec_env['__builtins__'] = safe_builtins
            
            exec(code, exec_env)
            
            return exec_env.get('output', {})
            
        except Exception as e:
            logger.error(f"Strategy execution failed: {e}")
            logger.error(traceback.format_exc())
            return {"error": str(e)}

    def run(
        self,
        indicator_code: str,
        market: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        initial_capital: float = 10000.0,
        commission: float = 0.001,
        slippage: float = 0.0,  # 理想回测环境，不考虑滑点
        leverage: int = 1,
        trade_direction: str = 'long',
        strategy_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        运行回测
        
        Args:
            indicator_code: 指标代码
            market: 市场类型
            symbol: 交易标的
            timeframe: 时间周期
            start_date: 开始日期
            end_date: 结束日期
            initial_capital: 初始资金
            commission: 手续费率
            slippage: 滑点
            
        Returns:
            回测结果
        """
        
        # 1. 获取K线数据
        df = self._fetch_kline_data(market, symbol, timeframe, start_date, end_date)
        if df.empty:
            raise ValueError("回测日期范围内没有K线数据")
        
        
        # 2. 执行指标代码获取信号（传入回测参数）
        backtest_params = {
            'leverage': leverage,
            'initial_capital': initial_capital,
            'commission': commission,
            'trade_direction': trade_direction
        }
        signals = self._execute_indicator(indicator_code, df, backtest_params)
        
        # 3. 模拟交易
        equity_curve, trades, total_commission = self._simulate_trading(
            df, signals, initial_capital, commission, slippage, leverage, trade_direction, strategy_config
        )
        
        # 4. 计算指标
        metrics = self._calculate_metrics(equity_curve, trades, initial_capital, timeframe, start_date, end_date, total_commission)
        
        # 5. 格式化结果
        return self._format_result(metrics, equity_curve, trades)
    
    def _fetch_kline_data(
        self,
        market: str,
        symbol: str,
        timeframe: str,
        start_date: datetime,
        end_date: datetime
    ) -> pd.DataFrame:
        """获取K线数据并转换为DataFrame"""
        # 计算需要的K线数量
        total_seconds = (end_date - start_date).total_seconds()
        tf_seconds = self.TIMEFRAME_SECONDS.get(timeframe, 86400)
        limit = math.ceil(total_seconds / tf_seconds) + 200
        
        # 计算before_time（结束日期+1天）
        before_time = int((end_date + timedelta(days=1)).timestamp())
        
        
        # 获取数据
        kline_data = DataSourceFactory.get_kline(
            market=market,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            before_time=before_time
        )
        
        if not kline_data:
            logger.warning("未获取到K线数据")
            return pd.DataFrame()
        
        if kline_data:
            first_time = datetime.fromtimestamp(kline_data[0]['time'])
            last_time = datetime.fromtimestamp(kline_data[-1]['time'])
        
        # 转换为DataFrame
        df = pd.DataFrame(kline_data)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df = df.set_index('time')
        
        if len(df) > 0:
            pass
        
        # 过滤日期范围
        df = df[(df.index >= start_date) & (df.index <= end_date)].copy()
        
        if len(df) > 0:
            pass
        
        return df
    
    def _execute_indicator(self, code: str, df: pd.DataFrame, backtest_params: dict = None):
        """执行指标代码获取信号
        
        Args:
            code: 指标代码
            df: K线数据
            backtest_params: 回测参数字典（leverage, initial_capital, commission, trade_direction）
        """
        # Supported indicator signal formats:
        # - Preferred (simple): df['buy'], df['sell'] as boolean
        # - Backtest/internal (4-way): df['open_long'], df['close_long'], df['open_short'], df['close_short'] as boolean
        signals = pd.Series(0, index=df.index)
        
        try:
            # 准备执行环境
            local_vars = {
                'df': df.copy(),
                'open': df['open'],
                'high': df['high'],
                'low': df['low'],
                'close': df['close'],
                'volume': df['volume'],
                'signals': signals,
                'np': np,
                'pd': pd,
            }
            
            # 添加回测参数到执行环境（如果提供了）
            if backtest_params:
                local_vars['backtest_params'] = backtest_params
                local_vars['leverage'] = backtest_params.get('leverage', 1)
                local_vars['initial_capital'] = backtest_params.get('initial_capital', 10000)
                local_vars['commission'] = backtest_params.get('commission', 0.0002)
                local_vars['trade_direction'] = backtest_params.get('trade_direction', 'both')
            
            # 添加技术指标函数
            local_vars.update(self._get_indicator_functions())
            
            # 添加安全的内置函数（保留完整的 builtins 以支持 lambda 等语法）
            # 但移除危险的函数如 eval, exec, open 等
            import builtins
            
            # 创建受限的 __import__ 函数，只允许导入已经加载的安全模块
            def safe_import(name, *args, **kwargs):
                """只允许导入 numpy, pandas, math, json 等安全模块"""
                allowed_modules = ['numpy', 'pandas', 'math', 'json', 'datetime', 'time']
                if name in allowed_modules or name.split('.')[0] in allowed_modules:
                    return builtins.__import__(name, *args, **kwargs)
                raise ImportError(f"不允许导入模块: {name}")
            
            safe_builtins = {k: getattr(builtins, k) for k in dir(builtins) 
                           if not k.startswith('_') and k not in [
                               'eval', 'exec', 'compile', 'open', 'input',
                               'help', 'exit', 'quit',
                               'copyright', 'credits', 'license'
                           ]}
            
            # 添加受限的 __import__
            safe_builtins['__import__'] = safe_import
            
            # 创建统一的执行环境（globals 和 locals 使用同一个字典）
            # 这样函数内部才能访问到 np, pd 等变量
            exec_env = local_vars.copy()
            exec_env['__builtins__'] = safe_builtins
            
            # 预执行 import 语句，确保 np 和 pd 可用
            pre_import_code = """
import numpy as np
import pandas as pd
"""
            exec(pre_import_code, exec_env)
            
            # 安全检查：验证代码不包含危险操作
            from app.utils.safe_exec import validate_code_safety
            is_safe, error_msg = validate_code_safety(code)
            if not is_safe:
                logger.error(f"回测代码安全检查失败: {error_msg}")
                raise ValueError(f"代码包含不安全操作: {error_msg}")
            
            # 安全执行用户代码（带超时）
            from app.utils.safe_exec import safe_exec_code
            exec_result = safe_exec_code(
                code=code,
                exec_globals=exec_env,
                exec_locals=exec_env,
                timeout=60  # 回测允许更长时间（60秒）
            )
            
            if not exec_result['success']:
                raise RuntimeError(f"代码执行失败: {exec_result['error']}")
            
            # Get the executed df
            executed_df = exec_env.get('df', df)

            # Validation: if chart signals are provided, df['buy']/df['sell'] must exist for backtest normalization.
            # This keeps indicator scripts simple and consistent (chart=buy/sell, execution=normalized in backend).
            output_obj = exec_env.get('output')
            has_output_signals = isinstance(output_obj, dict) and isinstance(output_obj.get('signals'), list) and len(output_obj.get('signals')) > 0
            if has_output_signals and not all(col in executed_df.columns for col in ['buy', 'sell']):
                raise ValueError(
                    "Invalid indicator script: output['signals'] is provided, but df['buy'] and df['sell'] are missing. "
                    "Please set df['buy'] and df['sell'] as boolean columns (len == len(df))."
                )
            
            # Extract signals from executed df
            if all(col in executed_df.columns for col in ['open_long', 'close_long', 'open_short', 'close_short']):
                
                signals = {
                    'open_long': executed_df['open_long'].fillna(False).astype(bool),
                    'close_long': executed_df['close_long'].fillna(False).astype(bool),
                    'open_short': executed_df['open_short'].fillna(False).astype(bool),
                    'close_short': executed_df['close_short'].fillna(False).astype(bool)
                }
                
                # Convention: backtest uses 4-way signals only.
                # Position sizing, TP/SL, trailing, etc must be handled by strategy_config / strategy logic.
            elif all(col in executed_df.columns for col in ['buy', 'sell']):
                # Simple buy/sell signals (recommended for indicator authors)
                signals = {
                    'buy': executed_df['buy'].fillna(False).astype(bool),
                    'sell': executed_df['sell'].fillna(False).astype(bool)
                }
            
            else:
                raise ValueError(
                    "Indicator must define either 4-way columns "
                    "(df['open_long'], df['close_long'], df['open_short'], df['close_short']) "
                    "or simple columns (df['buy'], df['sell'])."
                )
            
        except Exception as e:
            logger.error(f"指标代码执行错误: {e}")
            logger.error(traceback.format_exc())
        
        return signals
    
    def _get_indicator_functions(self) -> Dict:
        """获取技术指标函数"""
        def SMA(series, period):
            return series.rolling(window=period).mean()
        
        def EMA(series, period):
            return series.ewm(span=period, adjust=False).mean()
        
        def RSI(series, period=14):
            delta = series.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))
        
        def MACD(series, fast=12, slow=26, signal=9):
            exp1 = series.ewm(span=fast, adjust=False).mean()
            exp2 = series.ewm(span=slow, adjust=False).mean()
            macd = exp1 - exp2
            macd_signal = macd.ewm(span=signal, adjust=False).mean()
            macd_hist = macd - macd_signal
            return macd, macd_signal, macd_hist
        
        def BOLL(series, period=20, std_dev=2):
            middle = series.rolling(window=period).mean()
            std = series.rolling(window=period).std()
            upper = middle + std_dev * std
            lower = middle - std_dev * std
            return upper, middle, lower
        
        def ATR(high, low, close, period=14):
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            return tr.rolling(window=period).mean()
        
        def CROSSOVER(series1, series2):
            return (series1 > series2) & (series1.shift(1) <= series2.shift(1))
        
        def CROSSUNDER(series1, series2):
            return (series1 < series2) & (series1.shift(1) >= series2.shift(1))
        
        return {
            'SMA': SMA,
            'EMA': EMA,
            'RSI': RSI,
            'MACD': MACD,
            'BOLL': BOLL,
            'ATR': ATR,
            'CROSSOVER': CROSSOVER,
            'CROSSUNDER': CROSSUNDER,
        }
    
    def _simulate_trading(
        self,
        df: pd.DataFrame,
        signals,
        initial_capital: float,
        commission: float,
        slippage: float,
        leverage: int = 1,
        trade_direction: str = 'long',
        strategy_config: Optional[Dict[str, Any]] = None
    ) -> tuple:
        """
        模拟交易
        
        Args:
            signals: 信号，可以是 pd.Series (旧格式) 或 dict (新格式四种信号)
            trade_direction: 交易方向
                - 'long': 只做多 (buy->sell)
                - 'short': 只做空 (sell->buy, 收益反向)
                - 'both': 双向 (buy->sell做多 + sell->buy做空)
        """
        # Normalize supported signal formats into 4-way signals.
        if not isinstance(signals, dict):
            raise ValueError("signals must be a dict (either 4-way or buy/sell).")

        if all(k in signals for k in ['open_long', 'close_long', 'open_short', 'close_short']):
            norm = signals
        elif all(k in signals for k in ['buy', 'sell']):
            buy = signals['buy'].fillna(False).astype(bool)
            sell = signals['sell'].fillna(False).astype(bool)

            td = (trade_direction or 'both')
            td = str(td).lower()
            if td not in ['long', 'short', 'both']:
                td = 'both'

            # Mapping rules:
            # - long: buy=open_long, sell=close_long
            # - short: sell=open_short, buy=close_short
            # - both: buy=open_long+close_short, sell=open_short+close_long
            if td == 'long':
                norm = {
                    'open_long': buy,
                    'close_long': sell,
                    'open_short': pd.Series([False] * len(df), index=df.index),
                    'close_short': pd.Series([False] * len(df), index=df.index),
                }
            elif td == 'short':
                norm = {
                    'open_long': pd.Series([False] * len(df), index=df.index),
                    'close_long': pd.Series([False] * len(df), index=df.index),
                    'open_short': sell,
                    'close_short': buy,
                }
            else:
                norm = {
                    'open_long': buy,
                    'close_long': sell,
                    'open_short': sell,
                    'close_short': buy,
                }
        else:
            raise ValueError("signals dict must contain either 4-way keys or buy/sell keys.")

        return self._simulate_trading_new_format(df, norm, initial_capital, commission, slippage, leverage, trade_direction, strategy_config)
    
    def _simulate_trading_new_format(
        self,
        df: pd.DataFrame,
        signals: dict,
        initial_capital: float,
        commission: float,
        slippage: float,
        leverage: int = 1,
        trade_direction: str = 'both',
        strategy_config: Optional[Dict[str, Any]] = None
    ) -> tuple:
        """
        使用新格式四种信号进行交易模拟（支持仓位管理和加仓）
        
        Args:
            trade_direction: 交易方向 ('long', 'short', 'both')
        """
        equity_curve = []
        trades = []
        total_commission_paid = 0
        is_liquidated = False
        liquidation_price = 0
        min_capital_to_trade = 1.0  # 余额低于该值则视为赔光，不再开新单
        
        capital = initial_capital
        position = 0  # 正数=多头持仓，负数=空头持仓
        entry_price = 0  # 平均开仓价格
        position_type = None  # 'long' or 'short'
        
        # 仓位管理相关
        has_position_management = 'add_long' in signals and 'add_short' in signals
        position_batches = []  # 存储每批持仓：[{'price': xxx, 'amount': xxx}, ...]

        # --- Strategy config: signals + parameters = strategy (sent from BacktestModal as strategyConfig) ---
        cfg = strategy_config or {}
        exec_cfg = cfg.get('execution') or {}
        # Signal confirmation / execution timing:
        # - bar_close: execute on the same bar close (more aggressive)
        # - next_bar_open: execute on next bar open after signal is confirmed on bar close (recommended, closer to live)
        signal_timing = str(exec_cfg.get('signalTiming') or 'next_bar_open').strip().lower()
        risk_cfg = cfg.get('risk') or {}
        stop_loss_pct = float(risk_cfg.get('stopLossPct') or 0.0)
        take_profit_pct = float(risk_cfg.get('takeProfitPct') or 0.0)
        trailing_cfg = risk_cfg.get('trailing') or {}
        trailing_enabled = bool(trailing_cfg.get('enabled'))
        trailing_pct = float(trailing_cfg.get('pct') or 0.0)
        trailing_activation_pct = float(trailing_cfg.get('activationPct') or 0.0)

        # Risk percentages are defined on margin PnL; convert to price move thresholds by leverage.
        lev = max(int(leverage or 1), 1)
        stop_loss_pct_eff = stop_loss_pct / lev
        take_profit_pct_eff = take_profit_pct / lev
        trailing_pct_eff = trailing_pct / lev
        trailing_activation_pct_eff = trailing_activation_pct / lev

        # Conflict rule (TP vs trailing):
        # - If trailing is enabled, it takes precedence.
        # - If activationPct is not provided, reuse takeProfitPct as the trailing activation threshold.
        # - When trailing is enabled, fixed take-profit exits are disabled to avoid ambiguity.
        if trailing_enabled and trailing_pct_eff > 0:
            if trailing_activation_pct_eff <= 0 and take_profit_pct_eff > 0:
                trailing_activation_pct_eff = take_profit_pct_eff

        # IMPORTANT: risk percentages are defined on margin PnL (user expectation):
        # e.g. 10x leverage + 5% SL means ~0.5% adverse price move.
        lev = max(int(leverage or 1), 1)
        stop_loss_pct_eff = stop_loss_pct / lev
        take_profit_pct_eff = take_profit_pct / lev
        trailing_pct_eff = trailing_pct / lev
        trailing_activation_pct_eff = trailing_activation_pct / lev

        pos_cfg = cfg.get('position') or {}
        entry_pct_cfg = float(pos_cfg.get('entryPct') or 1.0)  # expected 0~1
        # Accept both 0~1 and 0~100 inputs (some clients may send percent units).
        if entry_pct_cfg > 1:
            entry_pct_cfg = entry_pct_cfg / 100.0
        entry_pct_cfg = max(0.0, min(entry_pct_cfg, 1.0))

        scale_cfg = cfg.get('scale') or {}
        trend_add_cfg = scale_cfg.get('trendAdd') or {}
        dca_add_cfg = scale_cfg.get('dcaAdd') or {}
        trend_reduce_cfg = scale_cfg.get('trendReduce') or {}
        adverse_reduce_cfg = scale_cfg.get('adverseReduce') or {}

        trend_add_enabled = bool(trend_add_cfg.get('enabled'))
        trend_add_step_pct = float(trend_add_cfg.get('stepPct') or 0.0)
        trend_add_size_pct = float(trend_add_cfg.get('sizePct') or 0.0)
        trend_add_max_times = int(trend_add_cfg.get('maxTimes') or 0)

        dca_add_enabled = bool(dca_add_cfg.get('enabled'))
        dca_add_step_pct = float(dca_add_cfg.get('stepPct') or 0.0)
        dca_add_size_pct = float(dca_add_cfg.get('sizePct') or 0.0)
        dca_add_max_times = int(dca_add_cfg.get('maxTimes') or 0)

        # Prevent logical conflict: trend scale-in and mean-reversion scale-in should not run together.
        # Otherwise both may trigger in the same candle (high/low both hit), causing double scaling unexpectedly.
        if trend_add_enabled and dca_add_enabled:
            dca_add_enabled = False

        trend_reduce_enabled = bool(trend_reduce_cfg.get('enabled'))
        trend_reduce_step_pct = float(trend_reduce_cfg.get('stepPct') or 0.0)
        trend_reduce_size_pct = float(trend_reduce_cfg.get('sizePct') or 0.0)
        trend_reduce_max_times = int(trend_reduce_cfg.get('maxTimes') or 0)

        adverse_reduce_enabled = bool(adverse_reduce_cfg.get('enabled'))
        adverse_reduce_step_pct = float(adverse_reduce_cfg.get('stepPct') or 0.0)
        adverse_reduce_size_pct = float(adverse_reduce_cfg.get('sizePct') or 0.0)
        adverse_reduce_max_times = int(adverse_reduce_cfg.get('maxTimes') or 0)

        # 触发百分比按“杠杆后的保证金阈值”理解：换算为价格触发阈值需要除以杠杆倍数
        # 例如 10x + 5% 触发，意味着约 0.5% 的价格波动触发
        trend_add_step_pct_eff = trend_add_step_pct / lev
        dca_add_step_pct_eff = dca_add_step_pct / lev
        trend_reduce_step_pct_eff = trend_reduce_step_pct / lev
        adverse_reduce_step_pct_eff = adverse_reduce_step_pct / lev

        # State: used for trailing exits and scale-in/scale-out anchor levels
        highest_since_entry = None
        lowest_since_entry = None
        trend_add_times = 0
        dca_add_times = 0
        trend_reduce_times = 0
        adverse_reduce_times = 0
        last_trend_add_anchor = None
        last_dca_add_anchor = None
        last_trend_reduce_anchor = None
        last_adverse_reduce_anchor = None
        
        # 转换信号为数组
        open_long_arr = signals['open_long'].values
        close_long_arr = signals['close_long'].values
        open_short_arr = signals['open_short'].values
        close_short_arr = signals['close_short'].values

        # Apply execution timing to avoid look-ahead bias:
        # If signals are computed using bar close, realistic execution is next bar open.
        if signal_timing in ['next_bar_open', 'next_open', 'nextopen', 'next']:
            open_long_arr = np.insert(open_long_arr[:-1], 0, False)
            close_long_arr = np.insert(close_long_arr[:-1], 0, False)
            open_short_arr = np.insert(open_short_arr[:-1], 0, False)
            close_short_arr = np.insert(close_short_arr[:-1], 0, False)
        
        # 根据交易方向过滤信号
        if trade_direction == 'long':
            # 只做多：禁用所有做空信号
            open_short_arr = np.zeros(len(df), dtype=bool)
            close_short_arr = np.zeros(len(df), dtype=bool)
        elif trade_direction == 'short':
            # 只做空：禁用所有做多信号
            open_long_arr = np.zeros(len(df), dtype=bool)
            close_long_arr = np.zeros(len(df), dtype=bool)
        else:
            pass
        
        # 加仓信号
        if has_position_management:
            add_long_arr = signals['add_long'].values
            add_short_arr = signals['add_short'].values
            position_size_arr = signals.get('position_size', pd.Series([0.0] * len(df))).values
            
            # 根据交易方向过滤加仓信号
            if trade_direction == 'long':
                add_short_arr = np.zeros(len(df), dtype=bool)
            elif trade_direction == 'short':
                add_long_arr = np.zeros(len(df), dtype=bool)
        
        # 开仓触发价格（如果指标提供了精确开仓价格）
        open_long_price_arr = signals.get('open_long_price', pd.Series([0.0] * len(df))).values
        open_short_price_arr = signals.get('open_short_price', pd.Series([0.0] * len(df))).values
        
        # 平仓目标价格（如果指标提供了精确平仓价格）
        close_long_price_arr = signals.get('close_long_price', pd.Series([0.0] * len(df))).values
        close_short_price_arr = signals.get('close_short_price', pd.Series([0.0] * len(df))).values
        
        # 加仓目标价格（如果指标提供了精确加仓价格）
        add_long_price_arr = signals.get('add_long_price', pd.Series([0.0] * len(df))).values
        add_short_price_arr = signals.get('add_short_price', pd.Series([0.0] * len(df))).values
        
        for i, (timestamp, row) in enumerate(df.iterrows()):
            if is_liquidated:
                equity_curve.append({
                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                    'value': 0
                })
                continue

            # 若已无持仓且余额过低，视为赔光并停止后续交易
            if position == 0 and capital < min_capital_to_trade:
                is_liquidated = True
                capital = 0
                trades.append({
                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                    'type': 'liquidation',
                    'price': round(float(row.get('close', 0) or 0), 4),
                    'amount': 0,
                    'profit': round(-initial_capital, 2),
                    'balance': 0
                })
                equity_curve.append({'time': timestamp.strftime('%Y-%m-%d %H:%M'), 'value': 0})
                continue
            
            # Use OHLC to evaluate triggers.
            high = row['high']
            low = row['low']
            close = row['close']
            open_ = row.get('open', close)
            
            # Default execution price depends on timing mode
            # - bar_close: close
            # - next_bar_open: open (this bar is the next bar for a prior signal)
            exec_price = open_ if signal_timing in ['next_bar_open', 'next_open', 'nextopen', 'next'] else close

            # --- Risk controls: SL / TP / trailing exit (highest priority) ---
            if position != 0 and position_type in ['long', 'short']:
                # 更新持仓期间极值（用于移动止盈止损）
                if position_type == 'long':
                    if highest_since_entry is None:
                        highest_since_entry = entry_price
                    if lowest_since_entry is None:
                        lowest_since_entry = entry_price
                    highest_since_entry = max(highest_since_entry, high)
                    lowest_since_entry = min(lowest_since_entry, low)
                else:  # short
                    if lowest_since_entry is None:
                        lowest_since_entry = entry_price
                    if highest_since_entry is None:
                        highest_since_entry = entry_price
                    lowest_since_entry = min(lowest_since_entry, low)
                    highest_since_entry = max(highest_since_entry, high)

                # 收集同一根K线内触发的强制平仓点
                # 回测为K线级别，无法确定同一根K线内的真实触发顺序；这里按“确定性优先级”处理：
                # 止损 > 移动止盈(回撤) > 固定止盈
                candidates = []  # [(trade_type, trigger_price)]
                if position_type == 'long' and position > 0:
                    if stop_loss_pct_eff > 0:
                        sl_price = entry_price * (1 - stop_loss_pct_eff)
                        if low <= sl_price:
                            candidates.append(('close_long_stop', sl_price))
                    # Fixed take-profit exit is disabled when trailing is enabled (see conflict rule above).
                    if (not trailing_enabled) and take_profit_pct_eff > 0:
                        tp_price = entry_price * (1 + take_profit_pct_eff)
                        if high >= tp_price:
                            candidates.append(('close_long_profit', tp_price))
                    if trailing_enabled and trailing_pct_eff > 0 and highest_since_entry is not None:
                        trail_active = True
                        if trailing_activation_pct_eff > 0:
                            trail_active = highest_since_entry >= entry_price * (1 + trailing_activation_pct_eff)
                        if trail_active:
                            tr_price = highest_since_entry * (1 - trailing_pct_eff)
                            if low <= tr_price:
                                candidates.append(('close_long_trailing', tr_price))

                    if candidates:
                        # 按优先级选择触发点：止损 > 移动止盈 > 止盈
                        pri = {'close_long_stop': 0, 'close_long_trailing': 1, 'close_long_profit': 2}
                        trade_type, trigger_price = sorted(candidates, key=lambda x: (pri.get(x[0], 99), x[1]))[0]
                        exec_price_close = trigger_price * (1 - slippage)
                        commission_fee_close = position * exec_price_close * commission
                        # 开仓手续费已在开仓时扣除，这里只扣平仓手续费
                        profit = (exec_price_close - entry_price) * position - commission_fee_close
                        capital += profit
                        total_commission_paid += commission_fee_close

                        trades.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'type': trade_type,
                            'price': round(exec_price_close, 4),
                            'amount': round(position, 4),
                            'profit': round(profit, 2),
                            'balance': round(capital, 2)
                        })

                        position = 0
                        position_type = None
                        liquidation_price = 0
                        highest_since_entry = None
                        lowest_since_entry = None
                        trend_add_times = dca_add_times = trend_reduce_times = adverse_reduce_times = 0
                        last_trend_add_anchor = last_dca_add_anchor = last_trend_reduce_anchor = last_adverse_reduce_anchor = None

                        equity_curve.append({'time': timestamp.strftime('%Y-%m-%d %H:%M'), 'value': round(capital, 2)})
                        continue

                if position_type == 'short' and position < 0:
                    shares = abs(position)
                    if stop_loss_pct_eff > 0:
                        sl_price = entry_price * (1 + stop_loss_pct_eff)
                        if high >= sl_price:
                            candidates.append(('close_short_stop', sl_price))
                    # Fixed take-profit exit is disabled when trailing is enabled (see conflict rule above).
                    if (not trailing_enabled) and take_profit_pct_eff > 0:
                        tp_price = entry_price * (1 - take_profit_pct_eff)
                        if low <= tp_price:
                            candidates.append(('close_short_profit', tp_price))
                    if trailing_enabled and trailing_pct_eff > 0 and lowest_since_entry is not None:
                        trail_active = True
                        if trailing_activation_pct_eff > 0:
                            trail_active = lowest_since_entry <= entry_price * (1 - trailing_activation_pct_eff)
                        if trail_active:
                            tr_price = lowest_since_entry * (1 + trailing_pct_eff)
                            if high >= tr_price:
                                candidates.append(('close_short_trailing', tr_price))

                    if candidates:
                        # 按优先级选择触发点：止损 > 移动止盈 > 止盈
                        pri = {'close_short_stop': 0, 'close_short_trailing': 1, 'close_short_profit': 2}
                        trade_type, trigger_price = sorted(candidates, key=lambda x: (pri.get(x[0], 99), -x[1]))[0]
                        exec_price_close = trigger_price * (1 + slippage)
                        commission_fee_close = shares * exec_price_close * commission
                        # 开仓手续费已在开仓时扣除，这里只扣平仓手续费
                        profit = (entry_price - exec_price_close) * shares - commission_fee_close

                        if capital + profit <= 0:
                            capital = 0
                            is_liquidated = True
                            trades.append({
                                'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                'type': 'liquidation',
                                'price': round(exec_price_close, 4),
                                'amount': round(shares, 4),
                                'profit': round(-initial_capital, 2),
                                'balance': 0
                            })
                            position = 0
                            position_type = None
                            liquidation_price = 0
                            equity_curve.append({'time': timestamp.strftime('%Y-%m-%d %H:%M'), 'value': 0})
                            continue

                        capital += profit
                        total_commission_paid += commission_fee_close

                        trades.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'type': trade_type,
                            'price': round(exec_price_close, 4),
                            'amount': round(shares, 4),
                            'profit': round(profit, 2),
                            'balance': round(capital, 2)
                        })

                        position = 0
                        position_type = None
                        liquidation_price = 0
                        highest_since_entry = None
                        lowest_since_entry = None
                        trend_add_times = dca_add_times = trend_reduce_times = adverse_reduce_times = 0
                        last_trend_add_anchor = last_dca_add_anchor = last_trend_reduce_anchor = last_adverse_reduce_anchor = None

                        equity_curve.append({'time': timestamp.strftime('%Y-%m-%d %H:%M'), 'value': round(capital, 2)})
                        continue
            
            # 处理平仓信号（优先处理，包括止损/止盈）
            if position > 0 and close_long_arr[i]:
                # 平多：使用指标提供的目标价格（如果有），否则使用收盘价
                if signal_timing in ['next_bar_open', 'next_open', 'nextopen', 'next']:
                    target_price = open_
                else:
                    target_price = close_long_price_arr[i] if close_long_price_arr[i] > 0 else close
                exec_price = target_price * (1 - slippage)
                commission_fee = position * exec_price * commission
                profit = (exec_price - entry_price) * position - commission_fee
                capital += profit
                total_commission_paid += commission_fee

                # NOTE:
                # This is a "signal close" (not a forced stop-loss/take-profit/trailing exit).
                # Do NOT label it as *_stop/*_profit based on PnL sign, otherwise it looks like a stop-loss happened
                # even when risk controls are disabled (stopLossPct/takeProfitPct == 0).
                trade_type = 'close_long'

                trades.append({
                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                    'type': trade_type,
                    'price': round(exec_price, 4),
                    'amount': round(position, 4),
                    'profit': round(profit, 2),
                    'balance': round(capital, 2)
                })
                
                position = 0
                position_type = None
                liquidation_price = 0
                highest_since_entry = None
                lowest_since_entry = None
                trend_add_times = dca_add_times = trend_reduce_times = adverse_reduce_times = 0
                last_trend_add_anchor = last_dca_add_anchor = last_trend_reduce_anchor = last_adverse_reduce_anchor = None

                # 平仓后余额过低则停止交易（避免同K线反手开仓）
                if capital < min_capital_to_trade:
                    is_liquidated = True
                    capital = 0
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'liquidation',
                        'price': round(exec_price, 4),
                        'amount': 0,
                        'profit': round(-initial_capital, 2),
                        'balance': 0
                    })
            
            elif position < 0 and close_short_arr[i]:
                # 平空：使用指标提供的目标价格（如果有），否则使用收盘价
                if signal_timing in ['next_bar_open', 'next_open', 'nextopen', 'next']:
                    target_price = open_
                else:
                    target_price = close_short_price_arr[i] if close_short_price_arr[i] > 0 else close
                exec_price = target_price * (1 + slippage)
                shares = abs(position)
                commission_fee = shares * exec_price * commission
                profit = (entry_price - exec_price) * shares - commission_fee
                
                if capital + profit <= 0:
                    logger.warning(f"平空时资金不足爆仓")
                    capital = 0
                    is_liquidated = True
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'liquidation',
                        'price': round(exec_price, 4),
                        'amount': round(shares, 4),
                        'profit': round(-capital, 2),
                        'balance': 0
                    })
                    position = 0
                    position_type = None
                    equity_curve.append({'time': timestamp.strftime('%Y-%m-%d %H:%M'), 'value': 0})
                    continue
                
                capital += profit
                total_commission_paid += commission_fee

                # Signal close (not forced TP/SL/trailing).
                trade_type = 'close_short'

                trades.append({
                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                    'type': trade_type,
                    'price': round(exec_price, 4),
                    'amount': round(shares, 4),
                    'profit': round(profit, 2),
                    'balance': round(capital, 2)
                })
                
                position = 0
                position_type = None
                liquidation_price = 0
                highest_since_entry = None
                lowest_since_entry = None
                trend_add_times = dca_add_times = trend_reduce_times = adverse_reduce_times = 0
                last_trend_add_anchor = last_dca_add_anchor = last_trend_reduce_anchor = last_adverse_reduce_anchor = None

                if capital < min_capital_to_trade:
                    is_liquidated = True
                    capital = 0
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'liquidation',
                        'price': round(exec_price, 4),
                        'amount': 0,
                        'profit': round(-initial_capital, 2),
                        'balance': 0
                    })
            
            # If this candle has a main strategy signal (open/close long/short),
            # we must NOT apply any scale-in/scale-out actions on the same candle.
            main_signal_on_bar = bool(open_long_arr[i] or open_short_arr[i] or close_long_arr[i] or close_short_arr[i])

            # --- Parameterized scaling rules (no strategy code needed) ---
            # Rules:
            # - Trend scale-in: long triggers when price rises stepPct from anchor; short triggers when price falls stepPct from anchor
            # - Mean-reversion DCA: long triggers when price falls stepPct from anchor; short triggers when price rises stepPct from anchor
            # - Trend reduce: long reduces on rise; short reduces on fall
            # - Adverse reduce: long reduces on fall; short reduces on rise
            if (not main_signal_on_bar) and position != 0 and position_type in ['long', 'short'] and capital >= min_capital_to_trade:
                # 做多
                if position_type == 'long' and position > 0:
                    # Trend scale-in (trigger on higher price)
                    if trend_add_enabled and trend_add_step_pct_eff > 0 and trend_add_size_pct > 0 and (trend_add_max_times == 0 or trend_add_times < trend_add_max_times):
                        anchor = last_trend_add_anchor if last_trend_add_anchor is not None else entry_price
                        trigger = anchor * (1 + trend_add_step_pct_eff)
                        if high >= trigger:
                            order_pct = trend_add_size_pct
                            if order_pct > 0:
                                exec_price_add = trigger * (1 + slippage)
                                use_capital = capital * order_pct
                                # 手续费按成交名义价值扣除；下单数量不再除以(1+commission)
                                shares_add = (use_capital * leverage) / exec_price_add
                                commission_fee = shares_add * exec_price_add * commission

                                total_cost_before = position * entry_price
                                total_cost_after = total_cost_before + shares_add * exec_price_add
                                position += shares_add
                                entry_price = total_cost_after / position

                                capital -= commission_fee
                                total_commission_paid += commission_fee
                                liquidation_price = entry_price * (1 - 1.0 / leverage)

                                trend_add_times += 1
                                last_trend_add_anchor = trigger

                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'add_long',
                                    'price': round(exec_price_add, 4),
                                    'amount': round(shares_add, 4),
                                    'profit': 0,
                                    'balance': round(capital, 2)
                                })

                    # Mean-reversion DCA (trigger on lower price)
                    if dca_add_enabled and dca_add_step_pct_eff > 0 and dca_add_size_pct > 0 and (dca_add_max_times == 0 or dca_add_times < dca_add_max_times):
                        anchor = last_dca_add_anchor if last_dca_add_anchor is not None else entry_price
                        trigger = anchor * (1 - dca_add_step_pct_eff)
                        if low <= trigger:
                            order_pct = dca_add_size_pct
                            if order_pct > 0:
                                exec_price_add = trigger * (1 + slippage)
                                use_capital = capital * order_pct
                                shares_add = (use_capital * leverage) / exec_price_add
                                commission_fee = shares_add * exec_price_add * commission

                                total_cost_before = position * entry_price
                                total_cost_after = total_cost_before + shares_add * exec_price_add
                                position += shares_add
                                entry_price = total_cost_after / position

                                capital -= commission_fee
                                total_commission_paid += commission_fee
                                liquidation_price = entry_price * (1 - 1.0 / leverage)

                                dca_add_times += 1
                                last_dca_add_anchor = trigger

                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'add_long',
                                    'price': round(exec_price_add, 4),
                                    'amount': round(shares_add, 4),
                                    'profit': 0,
                                    'balance': round(capital, 2)
                                })

                    # Trend reduce (trigger on higher price)
                    if trend_reduce_enabled and trend_reduce_step_pct_eff > 0 and trend_reduce_size_pct > 0 and (trend_reduce_max_times == 0 or trend_reduce_times < trend_reduce_max_times):
                        anchor = last_trend_reduce_anchor if last_trend_reduce_anchor is not None else entry_price
                        trigger = anchor * (1 + trend_reduce_step_pct_eff)
                        if high >= trigger:
                            reduce_pct = max(trend_reduce_size_pct, 0.0)
                            reduce_shares = position * reduce_pct
                            if reduce_shares > 0:
                                exec_price_reduce = trigger * (1 - slippage)
                                commission_fee = reduce_shares * exec_price_reduce * commission
                                profit = (exec_price_reduce - entry_price) * reduce_shares - commission_fee
                                capital += profit
                                total_commission_paid += commission_fee
                                position -= reduce_shares
                                if position <= 1e-12:
                                    position = 0
                                    position_type = None
                                    liquidation_price = 0
                                else:
                                    liquidation_price = entry_price * (1 - 1.0 / leverage)

                                trend_reduce_times += 1
                                last_trend_reduce_anchor = trigger

                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'reduce_long',
                                    'price': round(exec_price_reduce, 4),
                                    'amount': round(reduce_shares, 4),
                                    'profit': round(profit, 2),
                                    'balance': round(capital, 2)
                                })

                    # Adverse reduce (trigger on lower price)
                    if position_type == 'long' and position > 0 and adverse_reduce_enabled and adverse_reduce_step_pct_eff > 0 and adverse_reduce_size_pct > 0 and (adverse_reduce_max_times == 0 or adverse_reduce_times < adverse_reduce_max_times):
                        anchor = last_adverse_reduce_anchor if last_adverse_reduce_anchor is not None else entry_price
                        trigger = anchor * (1 - adverse_reduce_step_pct_eff)
                        if low <= trigger:
                            reduce_pct = max(adverse_reduce_size_pct, 0.0)
                            reduce_shares = position * reduce_pct
                            if reduce_shares > 0:
                                exec_price_reduce = trigger * (1 - slippage)
                                commission_fee = reduce_shares * exec_price_reduce * commission
                                profit = (exec_price_reduce - entry_price) * reduce_shares - commission_fee
                                capital += profit
                                total_commission_paid += commission_fee
                                position -= reduce_shares
                                if position <= 1e-12:
                                    position = 0
                                    position_type = None
                                    liquidation_price = 0
                                else:
                                    liquidation_price = entry_price * (1 - 1.0 / leverage)

                                adverse_reduce_times += 1
                                last_adverse_reduce_anchor = trigger

                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'reduce_long',
                                    'price': round(exec_price_reduce, 4),
                                    'amount': round(reduce_shares, 4),
                                    'profit': round(profit, 2),
                                    'balance': round(capital, 2)
                                })

                # 做空
                if position_type == 'short' and position < 0:
                    shares_total = abs(position)

                    # Trend scale-in (trigger on lower price)
                    if trend_add_enabled and trend_add_step_pct_eff > 0 and trend_add_size_pct > 0 and (trend_add_max_times == 0 or trend_add_times < trend_add_max_times):
                        anchor = last_trend_add_anchor if last_trend_add_anchor is not None else entry_price
                        trigger = anchor * (1 - trend_add_step_pct_eff)
                        if low <= trigger:
                            order_pct = trend_add_size_pct
                            if order_pct > 0:
                                exec_price_add = trigger * (1 - slippage)  # 卖出加空，滑点不利
                                use_capital = capital * order_pct
                                shares_add = (use_capital * leverage) / exec_price_add
                                commission_fee = shares_add * exec_price_add * commission

                                total_cost_before = shares_total * entry_price
                                total_cost_after = total_cost_before + shares_add * exec_price_add
                                position -= shares_add
                                shares_total = abs(position)
                                entry_price = total_cost_after / shares_total

                                capital -= commission_fee
                                total_commission_paid += commission_fee
                                liquidation_price = entry_price * (1 + 1.0 / leverage)

                                trend_add_times += 1
                                last_trend_add_anchor = trigger

                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'add_short',
                                    'price': round(exec_price_add, 4),
                                    'amount': round(shares_add, 4),
                                    'profit': 0,
                                    'balance': round(capital, 2)
                                })

                    # Mean-reversion DCA (trigger on higher price)
                    if dca_add_enabled and dca_add_step_pct_eff > 0 and dca_add_size_pct > 0 and (dca_add_max_times == 0 or dca_add_times < dca_add_max_times):
                        anchor = last_dca_add_anchor if last_dca_add_anchor is not None else entry_price
                        trigger = anchor * (1 + dca_add_step_pct_eff)
                        if high >= trigger:
                            order_pct = dca_add_size_pct
                            if order_pct > 0:
                                exec_price_add = trigger * (1 - slippage)
                                use_capital = capital * order_pct
                                shares_add = (use_capital * leverage) / exec_price_add
                                commission_fee = shares_add * exec_price_add * commission

                                total_cost_before = shares_total * entry_price
                                total_cost_after = total_cost_before + shares_add * exec_price_add
                                position -= shares_add
                                shares_total = abs(position)
                                entry_price = total_cost_after / shares_total

                                capital -= commission_fee
                                total_commission_paid += commission_fee
                                liquidation_price = entry_price * (1 + 1.0 / leverage)

                                dca_add_times += 1
                                last_dca_add_anchor = trigger

                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'add_short',
                                    'price': round(exec_price_add, 4),
                                    'amount': round(shares_add, 4),
                                    'profit': 0,
                                    'balance': round(capital, 2)
                                })

                    # Trend reduce (trigger on lower price)
                    if trend_reduce_enabled and trend_reduce_step_pct_eff > 0 and trend_reduce_size_pct > 0 and (trend_reduce_max_times == 0 or trend_reduce_times < trend_reduce_max_times):
                        anchor = last_trend_reduce_anchor if last_trend_reduce_anchor is not None else entry_price
                        trigger = anchor * (1 - trend_reduce_step_pct_eff)
                        if low <= trigger:
                            reduce_pct = max(trend_reduce_size_pct, 0.0)
                            reduce_shares = shares_total * reduce_pct
                            if reduce_shares > 0:
                                exec_price_reduce = trigger * (1 + slippage)  # 回补更贵
                                commission_fee = reduce_shares * exec_price_reduce * commission
                                profit = (entry_price - exec_price_reduce) * reduce_shares - commission_fee
                                capital += profit
                                total_commission_paid += commission_fee
                                position += reduce_shares
                                shares_total = abs(position)
                                if shares_total <= 1e-12:
                                    position = 0
                                    position_type = None
                                    liquidation_price = 0
                                else:
                                    liquidation_price = entry_price * (1 + 1.0 / leverage)

                                trend_reduce_times += 1
                                last_trend_reduce_anchor = trigger

                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'reduce_short',
                                    'price': round(exec_price_reduce, 4),
                                    'amount': round(reduce_shares, 4),
                                    'profit': round(profit, 2),
                                    'balance': round(capital, 2)
                                })

                    # Adverse reduce (trigger on higher price)
                    if position_type == 'short' and position < 0 and adverse_reduce_enabled and adverse_reduce_step_pct_eff > 0 and adverse_reduce_size_pct > 0 and (adverse_reduce_max_times == 0 or adverse_reduce_times < adverse_reduce_max_times):
                        anchor = last_adverse_reduce_anchor if last_adverse_reduce_anchor is not None else entry_price
                        trigger = anchor * (1 + adverse_reduce_step_pct_eff)
                        if high >= trigger:
                            reduce_pct = max(adverse_reduce_size_pct, 0.0)
                            reduce_shares = shares_total * reduce_pct
                            if reduce_shares > 0:
                                exec_price_reduce = trigger * (1 + slippage)
                                commission_fee = reduce_shares * exec_price_reduce * commission
                                profit = (entry_price - exec_price_reduce) * reduce_shares - commission_fee
                                capital += profit
                                total_commission_paid += commission_fee
                                position += reduce_shares
                                shares_total = abs(position)
                                if shares_total <= 1e-12:
                                    position = 0
                                    position_type = None
                                    liquidation_price = 0
                                else:
                                    liquidation_price = entry_price * (1 + 1.0 / leverage)

                                adverse_reduce_times += 1
                                last_adverse_reduce_anchor = trigger

                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'reduce_short',
                                    'price': round(exec_price_reduce, 4),
                                    'amount': round(reduce_shares, 4),
                                    'profit': round(profit, 2),
                                    'balance': round(capital, 2)
                                })

            # 处理加仓信号（仓位管理模式）
            if has_position_management and (not main_signal_on_bar):
                if position > 0 and add_long_arr[i] and capital >= min_capital_to_trade:
                    # 加多仓：使用指标提供的目标价格（如果有），否则使用收盘价
                    target_price = add_long_price_arr[i] if add_long_price_arr[i] > 0 else close
                    exec_price = target_price * (1 + slippage)
                    
                    # 使用指定比例的资金加仓
                    position_pct = position_size_arr[i] if position_size_arr[i] > 0 else 0.1
                    use_capital = capital * position_pct
                    shares = (use_capital * leverage) / exec_price
                    commission_fee = shares * exec_price * commission
                    
                    # 更新平均成本
                    total_cost_before = position * entry_price
                    total_cost_after = total_cost_before + shares * exec_price
                    position += shares
                    entry_price = total_cost_after / position
                    
                    capital -= commission_fee
                    total_commission_paid += commission_fee
                    
                    # 重新计算爆仓线
                    liquidation_price = entry_price * (1 - 1.0 / leverage)
                    
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'add_long',
                        'price': round(exec_price, 4),
                        'amount': round(shares, 4),
                        'profit': 0,
                        'balance': round(capital, 2)
                    })
                
                elif position < 0 and add_short_arr[i] and capital >= min_capital_to_trade:
                    # 加空仓：使用指标提供的目标价格（如果有），否则使用收盘价
                    target_price = add_short_price_arr[i] if add_short_price_arr[i] > 0 else close
                    exec_price = target_price * (1 - slippage)
                    
                    # 使用指定比例的资金加仓
                    position_pct = position_size_arr[i] if position_size_arr[i] > 0 else 0.1
                    use_capital = capital * position_pct
                    shares = (use_capital * leverage) / exec_price
                    commission_fee = shares * exec_price * commission
                    
                    # 更新平均成本
                    current_shares = abs(position)
                    total_cost_before = current_shares * entry_price
                    total_cost_after = total_cost_before + shares * exec_price
                    position -= shares  # 空头是负数
                    current_shares = abs(position)
                    entry_price = total_cost_after / current_shares
                    
                    capital -= commission_fee
                    total_commission_paid += commission_fee
                    
                    # 重新计算爆仓线
                    liquidation_price = entry_price * (1 + 1.0 / leverage)
                    
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'add_short',
                        'price': round(exec_price, 4),
                        'amount': round(shares, 4),
                        'profit': 0,
                        'balance': round(capital, 2)
                    })
            
            # 处理开仓信号
            # 注意：code6.py已经处理了反转（先平后开），所以这里只需要处理position==0的情况
            if open_long_arr[i] and position == 0 and capital >= min_capital_to_trade:
                    # 使用指标提供的开仓触发价格（如果有），否则使用收盘价
                    if signal_timing in ['next_bar_open', 'next_open', 'nextopen', 'next']:
                        base_price = open_
                    else:
                        base_price = open_long_price_arr[i] if open_long_price_arr[i] > 0 else close
                    exec_price = base_price * (1 + slippage)
                    
                    # 使用指定比例的资金开仓（优先采用回测弹窗的 entryPct；其次采用指标提供的 position_size；否则全仓）
                    position_pct = None
                    if entry_pct_cfg and entry_pct_cfg > 0:
                        position_pct = entry_pct_cfg
                    elif has_position_management and position_size_arr[i] > 0:
                        position_pct = position_size_arr[i]
                    if position_pct is not None and position_pct > 0 and position_pct < 1:
                        use_capital = capital * position_pct
                        shares = (use_capital * leverage) / exec_price
                    else:
                        shares = (capital * leverage) / exec_price
                    
                    commission_fee = shares * exec_price * commission
                    
                    position = shares
                    entry_price = exec_price
                    position_type = 'long'
                    capital -= commission_fee
                    total_commission_paid += commission_fee
                    liquidation_price = entry_price * (1 - 1.0 / leverage)
                    highest_since_entry = entry_price
                    lowest_since_entry = entry_price
                    last_trend_add_anchor = entry_price
                    last_dca_add_anchor = entry_price
                    last_trend_reduce_anchor = entry_price
                    last_adverse_reduce_anchor = entry_price
                    
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'open_long',
                        'price': round(exec_price, 4),
                        'amount': round(shares, 4),
                        'profit': 0,
                        'balance': round(capital, 2)
                    })
                    
                    # Strict intrabar stop-loss / liquidation check right after entry (closer to live trading).
                    # If this bar touches stop-loss price, close immediately at stop price (with slippage).
                    # If this bar also touches liquidation price, assume stop-loss triggers first only if it is above liquidation.
                    if position_type == 'long' and position > 0:
                        sl_price = entry_price * (1 - stop_loss_pct_eff) if stop_loss_pct_eff > 0 else None
                        hit_sl = (sl_price is not None) and (low <= sl_price)
                        hit_liq = liquidation_price > 0 and (low <= liquidation_price)
                        if hit_sl or hit_liq:
                            if hit_liq and (not hit_sl or (sl_price is not None and sl_price <= liquidation_price)):
                                # Liquidation happens before stop-loss (or stop-loss not configured).
                                is_liquidated = True
                                capital = 0
                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'liquidation',
                                    'price': round(liquidation_price, 4),
                                    'amount': round(position, 4),
                                    'profit': round(-initial_capital, 2),
                                    'balance': 0
                                })
                            else:
                                # Stop-loss triggers first.
                                exec_price_close = sl_price * (1 - slippage)
                                commission_fee_close = position * exec_price_close * commission
                                profit = (exec_price_close - entry_price) * position - commission_fee_close
                                capital += profit
                                total_commission_paid += commission_fee_close
                                if capital <= 0:
                                    is_liquidated = True
                                    capital = 0
                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'close_long_stop',
                                    'price': round(exec_price_close, 4),
                                    'amount': round(position, 4),
                                    'profit': round(profit, 2),
                                    'balance': round(capital, 2)
                                })

                            position = 0
                            position_type = None
                            liquidation_price = 0
                            highest_since_entry = None
                            lowest_since_entry = None
                            equity_curve.append({'time': timestamp.strftime('%Y-%m-%d %H:%M'), 'value': round(capital, 2)})
                            continue
            
            elif open_short_arr[i] and position == 0 and capital >= min_capital_to_trade:
                    # 使用指标提供的开仓触发价格（如果有），否则使用收盘价
                    if signal_timing in ['next_bar_open', 'next_open', 'nextopen', 'next']:
                        base_price = open_
                    else:
                        base_price = open_short_price_arr[i] if open_short_price_arr[i] > 0 else close
                    exec_price = base_price * (1 - slippage)
                    
                    # 使用指定比例的资金开仓（优先采用回测弹窗的 entryPct；其次采用指标提供的 position_size；否则全仓）
                    position_pct = None
                    if entry_pct_cfg and entry_pct_cfg > 0:
                        position_pct = entry_pct_cfg
                    elif has_position_management and position_size_arr[i] > 0:
                        position_pct = position_size_arr[i]
                    if position_pct is not None and position_pct > 0 and position_pct < 1:
                        use_capital = capital * position_pct
                        shares = (use_capital * leverage) / exec_price
                    else:
                        shares = (capital * leverage) / exec_price
                    
                    commission_fee = shares * exec_price * commission
                    
                    position = -shares
                    entry_price = exec_price
                    position_type = 'short'
                    capital -= commission_fee
                    total_commission_paid += commission_fee
                    liquidation_price = entry_price * (1 + 1.0 / leverage)
                    highest_since_entry = entry_price
                    lowest_since_entry = entry_price
                    last_trend_add_anchor = entry_price
                    last_dca_add_anchor = entry_price
                    last_trend_reduce_anchor = entry_price
                    last_adverse_reduce_anchor = entry_price
                    
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'open_short',
                        'price': round(exec_price, 4),
                        'amount': round(shares, 4),
                        'profit': 0,
                        'balance': round(capital, 2)
                    })
                    
                    # Strict intrabar stop-loss / liquidation check right after entry (closer to live trading).
                    if position_type == 'short' and position < 0:
                        sl_price = entry_price * (1 + stop_loss_pct_eff) if stop_loss_pct_eff > 0 else None
                        hit_sl = (sl_price is not None) and (high >= sl_price)
                        hit_liq = liquidation_price > 0 and (high >= liquidation_price)
                        if hit_sl or hit_liq:
                            if hit_liq and (not hit_sl or (sl_price is not None and sl_price >= liquidation_price)):
                                # Liquidation happens before stop-loss (or stop-loss not configured).
                                is_liquidated = True
                                capital = 0
                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'liquidation',
                                    'price': round(liquidation_price, 4),
                                    'amount': round(abs(position), 4),
                                    'profit': round(-initial_capital, 2),
                                    'balance': 0
                                })
                            else:
                                # Stop-loss triggers first.
                                exec_price_close = sl_price * (1 + slippage)
                                shares_close = abs(position)
                                commission_fee_close = shares_close * exec_price_close * commission
                                profit = (entry_price - exec_price_close) * shares_close - commission_fee_close
                                capital += profit
                                total_commission_paid += commission_fee_close
                                if capital <= 0:
                                    is_liquidated = True
                                    capital = 0
                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'close_short_stop',
                                    'price': round(exec_price_close, 4),
                                    'amount': round(shares_close, 4),
                                    'profit': round(profit, 2),
                                    'balance': round(capital, 2)
                                })

                            position = 0
                            position_type = None
                            liquidation_price = 0
                            highest_since_entry = None
                            lowest_since_entry = None
                            equity_curve.append({'time': timestamp.strftime('%Y-%m-%d %H:%M'), 'value': round(capital, 2)})
                            continue
            
            # 检测持仓期间是否触及爆仓线（作为兜底保护）
            # 注意：这个检查在所有主动平仓信号处理之后
            # 如果触及爆仓线，检查是否有止损信号，止损优先
            if position != 0 and not is_liquidated:
                if position_type == 'long' and low <= liquidation_price:
                    # 做多触及爆仓线：检查是否有止损信号
                    has_stop_loss = close_long_arr[i] and close_long_price_arr[i] > 0
                    stop_loss_price = close_long_price_arr[i] if has_stop_loss else 0
                    
                    # 判断先触发止损还是爆仓
                    if has_stop_loss and stop_loss_price > liquidation_price:
                        # 止损在爆仓前触发，使用止损价平仓
                        exec_price_close = stop_loss_price * (1 - slippage)
                        commission_fee_close = position * exec_price_close * commission
                        profit = (exec_price_close - entry_price) * position - commission_fee_close
                        capital += profit
                        total_commission_paid += commission_fee_close
                        
                        trades.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'type': 'close_long_stop',
                            'price': round(exec_price_close, 4),
                            'amount': round(position, 4),
                            'profit': round(profit, 2),
                            'balance': round(capital, 2)
                        })
                    else:
                        # 止损不够严格或无止损，触发爆仓
                        logger.warning(f"做多爆仓！开仓价={entry_price:.2f}, 最低价={low:.2f}, "
                                     f"爆仓线={liquidation_price:.2f}, 止损价={stop_loss_price:.2f}")
                        is_liquidated = True
                        capital = 0
                        trades.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'type': 'liquidation',
                            'price': round(liquidation_price, 4),
                            'amount': round(abs(position), 4),
                            'profit': round(-initial_capital, 2),
                            'balance': 0
                        })
                    
                    position = 0
                    position_type = None
                    equity_curve.append({'time': timestamp.strftime('%Y-%m-%d %H:%M'), 'value': capital})
                    continue
                    
                elif position_type == 'short' and high >= liquidation_price:
                    # 做空触及爆仓线：检查是否有止损信号
                    has_stop_loss = close_short_arr[i] and close_short_price_arr[i] > 0
                    stop_loss_price = close_short_price_arr[i] if has_stop_loss else 0
                    
                    logger.warning(f"[K线{i}] 做空触及爆仓线！开仓={entry_price:.2f}, 最高={high:.2f}, 爆仓线={liquidation_price:.2f}, "
                              f"止损信号={close_short_arr[i]}, 止损价={stop_loss_price:.4f}, 时间={timestamp}")
                    
                    # 判断先触发止损还是爆仓
                    if has_stop_loss and stop_loss_price < liquidation_price:
                        # 止损在爆仓前触发，使用止损价平仓
                        exec_price_close = stop_loss_price * (1 + slippage)
                        shares_close = abs(position)
                        commission_fee_close = shares_close * exec_price_close * commission
                        profit = (entry_price - exec_price_close) * shares_close - commission_fee_close
                        capital += profit
                        total_commission_paid += commission_fee_close
                        
                        trades.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'type': 'close_short_stop',
                            'price': round(exec_price_close, 4),
                            'amount': round(shares_close, 4),
                            'profit': round(profit, 2),
                            'balance': round(capital, 2)
                        })
                    else:
                        # 止损不够严格或无止损，触发爆仓
                        logger.warning(f"做空爆仓！开仓价={entry_price:.2f}, 最高价={high:.2f}, "
                                     f"爆仓线={liquidation_price:.2f}, 止损价={stop_loss_price:.2f}")
                        is_liquidated = True
                        capital = 0
                        trades.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'type': 'liquidation',
                            'price': round(liquidation_price, 4),
                            'amount': round(abs(position), 4),
                            'profit': round(-initial_capital, 2),
                            'balance': 0
                        })
                    
                    position = 0
                    position_type = None
                    equity_curve.append({'time': timestamp.strftime('%Y-%m-%d %H:%M'), 'value': capital})
                    continue
            
            # 记录权益（使用收盘价计算未实现盈亏）
            if position_type == 'long':
                unrealized_pnl = (close - entry_price) * position
                total_value = capital + unrealized_pnl
            elif position_type == 'short':
                shares = abs(position)
                unrealized_pnl = (entry_price - close) * shares
                total_value = capital + unrealized_pnl
            else:
                total_value = capital
            
            if total_value < 0:
                total_value = 0
            
            equity_curve.append({
                'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                'value': round(total_value, 2)
            })
        
        # 回测结束时强制平仓
        if position != 0:
            timestamp = df.index[-1]
            final_close = df.iloc[-1]['close']
            
            if position > 0:  # 平多
                exec_price = final_close * (1 - slippage)
                commission_fee = position * exec_price * commission
                profit = (exec_price - entry_price) * position - commission_fee
                capital += profit
                total_commission_paid += commission_fee
                
                trades.append({
                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                    'type': 'close_long',
                    'price': round(exec_price, 4),
                    'amount': round(position, 4),
                    'profit': round(profit, 2),
                    'balance': round(capital, 2)
                })
            else:  # 平空
                exec_price = final_close * (1 + slippage)
                shares = abs(position)
                commission_fee = shares * exec_price * commission
                profit = (entry_price - exec_price) * shares - commission_fee
                
                if capital + profit <= 0:
                    logger.warning(f"回测结束爆仓！")
                    capital = 0
                    is_liquidated = True
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'liquidation',
                        'price': round(exec_price, 4),
                        'amount': round(shares, 4),
                        'profit': round(-capital, 2),
                        'balance': 0
                    })
                else:
                    capital += profit
                    total_commission_paid += commission_fee
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'close_short',
                        'price': round(exec_price, 4),
                        'amount': round(shares, 4),
                        'profit': round(profit, 2),
                        'balance': round(capital, 2)
                    })
            
            if equity_curve:
                equity_curve[-1]['value'] = round(capital, 2)
        
        return equity_curve, trades, total_commission_paid
    
    def _simulate_trading_old_format(
        self,
        df: pd.DataFrame,
        signals: pd.Series,
        initial_capital: float,
        commission: float,
        slippage: float,
        leverage: int = 1,
        trade_direction: str = 'long',
        strategy_config: Optional[Dict[str, Any]] = None
    ) -> tuple:
        """
        使用旧格式信号进行交易模拟（保持兼容性）
        """
        equity_curve = []
        trades = []
        total_commission_paid = 0  # 累计手续费
        is_liquidated = False  # 爆仓标志
        liquidation_price = 0  # 爆仓价格
        min_capital_to_trade = 1.0  # 余额低于该值则视为赔光，不再开新单
        
        capital = initial_capital
        position = 0  # 正数=多头持仓，负数=空头持仓
        entry_price = 0
        position_type = None  # 'long' or 'short'

        # Risk controls (also supported for legacy signals): SL / TP / trailing exit
        cfg = strategy_config or {}
        exec_cfg = cfg.get('execution') or {}
        # Signal confirmation / execution timing (legacy mode):
        # - bar_close: execute on the same bar close
        # - next_bar_open: execute on next bar open after signal is confirmed on bar close (recommended)
        signal_timing = str(exec_cfg.get('signalTiming') or 'next_bar_open').strip().lower()
        risk_cfg = cfg.get('risk') or {}
        stop_loss_pct = float(risk_cfg.get('stopLossPct') or 0.0)
        take_profit_pct = float(risk_cfg.get('takeProfitPct') or 0.0)
        trailing_cfg = risk_cfg.get('trailing') or {}
        trailing_enabled = bool(trailing_cfg.get('enabled'))
        trailing_pct = float(trailing_cfg.get('pct') or 0.0)
        trailing_activation_pct = float(trailing_cfg.get('activationPct') or 0.0)
        
        # Risk percentages are defined on margin PnL; convert to price move thresholds by leverage.
        lev = max(int(leverage or 1), 1)
        stop_loss_pct_eff = stop_loss_pct / lev
        take_profit_pct_eff = take_profit_pct / lev
        trailing_pct_eff = trailing_pct / lev
        trailing_activation_pct_eff = trailing_activation_pct / lev
        highest_since_entry = None
        lowest_since_entry = None

        # --- Position / scaling config (make old-format strategies support the same backtest modal features) ---
        pos_cfg = cfg.get('position') or {}
        entry_pct_cfg = float(pos_cfg.get('entryPct') if pos_cfg.get('entryPct') is not None else 1.0)  # expected 0~1
        # Accept both 0~1 and 0~100 inputs (some clients may send percent units).
        if entry_pct_cfg > 1:
            entry_pct_cfg = entry_pct_cfg / 100.0
        entry_pct_cfg = max(0.0, min(entry_pct_cfg, 1.0))

        scale_cfg = cfg.get('scale') or {}
        trend_add_cfg = scale_cfg.get('trendAdd') or {}
        dca_add_cfg = scale_cfg.get('dcaAdd') or {}
        trend_reduce_cfg = scale_cfg.get('trendReduce') or {}
        adverse_reduce_cfg = scale_cfg.get('adverseReduce') or {}

        trend_add_enabled = bool(trend_add_cfg.get('enabled'))
        trend_add_step_pct = float(trend_add_cfg.get('stepPct') or 0.0)
        trend_add_size_pct = float(trend_add_cfg.get('sizePct') or 0.0)
        trend_add_max_times = int(trend_add_cfg.get('maxTimes') or 0)

        dca_add_enabled = bool(dca_add_cfg.get('enabled'))
        dca_add_step_pct = float(dca_add_cfg.get('stepPct') or 0.0)
        dca_add_size_pct = float(dca_add_cfg.get('sizePct') or 0.0)
        dca_add_max_times = int(dca_add_cfg.get('maxTimes') or 0)

        trend_reduce_enabled = bool(trend_reduce_cfg.get('enabled'))
        trend_reduce_step_pct = float(trend_reduce_cfg.get('stepPct') or 0.0)
        trend_reduce_size_pct = float(trend_reduce_cfg.get('sizePct') or 0.0)
        trend_reduce_max_times = int(trend_reduce_cfg.get('maxTimes') or 0)

        adverse_reduce_enabled = bool(adverse_reduce_cfg.get('enabled'))
        adverse_reduce_step_pct = float(adverse_reduce_cfg.get('stepPct') or 0.0)
        adverse_reduce_size_pct = float(adverse_reduce_cfg.get('sizePct') or 0.0)
        adverse_reduce_max_times = int(adverse_reduce_cfg.get('maxTimes') or 0)

        # 触发百分比按杠杆后换算为价格阈值
        trend_add_step_pct_eff = trend_add_step_pct / lev
        dca_add_step_pct_eff = dca_add_step_pct / lev
        trend_reduce_step_pct_eff = trend_reduce_step_pct / lev
        adverse_reduce_step_pct_eff = adverse_reduce_step_pct / lev

        # State for scaling
        trend_add_times = 0
        dca_add_times = 0
        trend_reduce_times = 0
        adverse_reduce_times = 0
        last_trend_add_anchor = None
        last_dca_add_anchor = None
        last_trend_reduce_anchor = None
        last_adverse_reduce_anchor = None
        
        # Apply execution timing to avoid look-ahead bias in legacy signals (buy/sell series):
        # If signal is computed on bar close, realistic execution is next bar open.
        signals_exec = signals
        if signal_timing in ['next_bar_open', 'next_open', 'nextopen', 'next']:
            try:
                signals_exec = signals.shift(1).fillna(0)
            except Exception:
                signals_exec = signals

        for i, (timestamp, row) in enumerate(df.iterrows()):
            # 如果已爆仓，停止交易
            if is_liquidated:
                # 记录爆仓后的权益（保持为0）
                equity_curve.append({
                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                    'value': 0
                })
                continue

            # 若已无持仓且余额过低，视为赔光并停止后续交易
            if position == 0 and capital < min_capital_to_trade:
                is_liquidated = True
                capital = 0
                trades.append({
                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                    'type': 'liquidation',
                    'price': round(float(row.get('close', 0) or 0), 4),
                    'amount': 0,
                    'profit': round(-initial_capital, 2),
                    'balance': 0
                })
                equity_curve.append({'time': timestamp.strftime('%Y-%m-%d %H:%M'), 'value': 0})
                continue
            
            signal = signals_exec.iloc[i] if i < len(signals_exec) else 0
            high = row['high']
            low = row['low']
            price = row['close']
            open_ = row.get('open', price)

            # 强制平仓（止盈止损/移动止盈）优先于信号
            if position != 0 and position_type in ['long', 'short']:
                if position_type == 'long' and position > 0:
                    if highest_since_entry is None:
                        highest_since_entry = entry_price
                    highest_since_entry = max(highest_since_entry, high)
                    candidates = []
                    if stop_loss_pct_eff > 0:
                        sl_price = entry_price * (1 - stop_loss_pct_eff)
                        if low <= sl_price:
                            candidates.append(('stop', sl_price))
                    if take_profit_pct_eff > 0:
                        tp_price = entry_price * (1 + take_profit_pct_eff)
                        if high >= tp_price:
                            candidates.append(('profit', tp_price))
                    if trailing_enabled and trailing_pct_eff > 0:
                        trail_active = True
                        if trailing_activation_pct_eff > 0:
                            trail_active = highest_since_entry >= entry_price * (1 + trailing_activation_pct_eff)
                        if trail_active:
                            tr_price = highest_since_entry * (1 - trailing_pct_eff)
                            if low <= tr_price:
                                candidates.append(('trailing', tr_price))
                    if candidates:
                        # 止损 > 移动止盈(回撤) > 止盈
                        pri = {'stop': 0, 'trailing': 1, 'profit': 2}
                        reason, trigger_price = sorted(candidates, key=lambda x: (pri.get(x[0], 99), x[1]))[0]
                        exec_price = trigger_price * (1 - slippage)
                        commission_fee = position * exec_price * commission
                        # 开仓手续费已在开仓时扣除，这里只扣平仓手续费
                        profit = (exec_price - entry_price) * position - commission_fee
                        capital += profit
                        total_commission_paid += commission_fee
                        trades.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'type': {'stop': 'close_long_stop', 'profit': 'close_long_profit', 'trailing': 'close_long_trailing'}.get(reason, 'close_long'),
                            'price': round(exec_price, 4),
                            'amount': round(position, 4),
                            'profit': round(profit, 2),
                            'balance': round(capital, 2)
                        })
                        position = 0
                        position_type = None
                        liquidation_price = 0
                        highest_since_entry = None
                        lowest_since_entry = None
                        equity_curve.append({'time': timestamp.strftime('%Y-%m-%d %H:%M'), 'value': round(capital, 2)})
                        continue

                if position_type == 'short' and position < 0:
                    shares = abs(position)
                    if lowest_since_entry is None:
                        lowest_since_entry = entry_price
                    lowest_since_entry = min(lowest_since_entry, low)
                    candidates = []
                    if stop_loss_pct_eff > 0:
                        sl_price = entry_price * (1 + stop_loss_pct_eff)
                        if high >= sl_price:
                            candidates.append(('stop', sl_price))
                    if take_profit_pct_eff > 0:
                        tp_price = entry_price * (1 - take_profit_pct_eff)
                        if low <= tp_price:
                            candidates.append(('profit', tp_price))
                    if trailing_enabled and trailing_pct_eff > 0:
                        trail_active = True
                        if trailing_activation_pct_eff > 0:
                            trail_active = lowest_since_entry <= entry_price * (1 - trailing_activation_pct_eff)
                        if trail_active:
                            tr_price = lowest_since_entry * (1 + trailing_pct_eff)
                            if high >= tr_price:
                                candidates.append(('trailing', tr_price))
                    if candidates:
                        # 止损 > 移动止盈(回撤) > 止盈
                        pri = {'stop': 0, 'trailing': 1, 'profit': 2}
                        reason, trigger_price = sorted(candidates, key=lambda x: (pri.get(x[0], 99), -x[1]))[0]
                        exec_price = trigger_price * (1 + slippage)
                        commission_fee = shares * exec_price * commission
                        # 开仓手续费已在开仓时扣除，这里只扣平仓手续费
                        profit = (entry_price - exec_price) * shares - commission_fee
                        if capital + profit <= 0:
                            capital = 0
                            is_liquidated = True
                            trades.append({
                                'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                'type': 'liquidation',
                                'price': round(exec_price, 4),
                                'amount': round(shares, 4),
                                'profit': round(-initial_capital, 2),
                                'balance': 0
                            })
                            position = 0
                            position_type = None
                            liquidation_price = 0
                            equity_curve.append({'time': timestamp.strftime('%Y-%m-%d %H:%M'), 'value': 0})
                            continue
                        capital += profit
                        total_commission_paid += commission_fee
                        trades.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'type': {'stop': 'close_short_stop', 'profit': 'close_short_profit', 'trailing': 'close_short_trailing'}.get(reason, 'close_short'),
                            'price': round(exec_price, 4),
                            'amount': round(shares, 4),
                            'profit': round(profit, 2),
                            'balance': round(capital, 2)
                        })
                        position = 0
                        position_type = None
                        liquidation_price = 0
                        highest_since_entry = None
                        lowest_since_entry = None
                        equity_curve.append({'time': timestamp.strftime('%Y-%m-%d %H:%M'), 'value': round(capital, 2)})
                        continue
            
            # --- Parameterized scaling rules (also for old-format strategies) ---
            # 说明：旧格式只有 buy/sell 信号，但回测弹窗的“顺势/逆势加减仓、最小下单比例”等参数仍应生效。
            # 触发百分比按杠杆后阈值理解（已除以 leverage）。
            # IMPORTANT: if this candle has a main buy/sell signal, do NOT apply any scale-in/scale-out.
            if signal == 0 and position != 0 and position_type in ['long', 'short'] and capital >= min_capital_to_trade:
                # 做多
                if position_type == 'long' and position > 0:
                    # Trend add（顺势加仓：上涨触发）
                    if trend_add_enabled and trend_add_step_pct_eff > 0 and trend_add_size_pct > 0 and (trend_add_max_times == 0 or trend_add_times < trend_add_max_times):
                        anchor = last_trend_add_anchor if last_trend_add_anchor is not None else entry_price
                        trigger = anchor * (1 + trend_add_step_pct_eff)
                        if high >= trigger:
                            order_pct = trend_add_size_pct
                            if order_pct > 0:
                                exec_price_add = trigger * (1 + slippage)
                                use_capital = capital * order_pct
                                shares_add = (use_capital * leverage) / exec_price_add
                                commission_fee = shares_add * exec_price_add * commission

                                total_cost_before = position * entry_price
                                total_cost_after = total_cost_before + shares_add * exec_price_add
                                position += shares_add
                                entry_price = total_cost_after / position

                                capital -= commission_fee
                                total_commission_paid += commission_fee
                                liquidation_price = entry_price * (1 - 1.0 / leverage)

                                trend_add_times += 1
                                last_trend_add_anchor = trigger

                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'add_long',
                                    'price': round(exec_price_add, 4),
                                    'amount': round(shares_add, 4),
                                    'profit': 0,
                                    'balance': round(capital, 2)
                                })

                    # DCA add（逆势加仓：下跌触发）
                    if dca_add_enabled and dca_add_step_pct_eff > 0 and dca_add_size_pct > 0 and (dca_add_max_times == 0 or dca_add_times < dca_add_max_times):
                        anchor = last_dca_add_anchor if last_dca_add_anchor is not None else entry_price
                        trigger = anchor * (1 - dca_add_step_pct_eff)
                        if low <= trigger:
                            order_pct = dca_add_size_pct
                            if order_pct > 0:
                                exec_price_add = trigger * (1 + slippage)
                                use_capital = capital * order_pct
                                shares_add = (use_capital * leverage) / exec_price_add
                                commission_fee = shares_add * exec_price_add * commission

                                total_cost_before = position * entry_price
                                total_cost_after = total_cost_before + shares_add * exec_price_add
                                position += shares_add
                                entry_price = total_cost_after / position

                                capital -= commission_fee
                                total_commission_paid += commission_fee
                                liquidation_price = entry_price * (1 - 1.0 / leverage)

                                dca_add_times += 1
                                last_dca_add_anchor = trigger

                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'add_long',
                                    'price': round(exec_price_add, 4),
                                    'amount': round(shares_add, 4),
                                    'profit': 0,
                                    'balance': round(capital, 2)
                                })

                    # Trend reduce（顺势减仓：上涨触发）
                    if trend_reduce_enabled and trend_reduce_step_pct_eff > 0 and trend_reduce_size_pct > 0 and (trend_reduce_max_times == 0 or trend_reduce_times < trend_reduce_max_times):
                        anchor = last_trend_reduce_anchor if last_trend_reduce_anchor is not None else entry_price
                        trigger = anchor * (1 + trend_reduce_step_pct_eff)
                        if high >= trigger:
                            reduce_pct = max(trend_reduce_size_pct, 0.0)
                            reduce_shares = position * reduce_pct
                            if reduce_shares > 0:
                                exec_price_reduce = trigger * (1 - slippage)
                                commission_fee = reduce_shares * exec_price_reduce * commission
                                profit = (exec_price_reduce - entry_price) * reduce_shares - commission_fee
                                capital += profit
                                total_commission_paid += commission_fee
                                position -= reduce_shares
                                if position <= 1e-12:
                                    position = 0
                                    position_type = None
                                    liquidation_price = 0
                                    last_trend_add_anchor = last_dca_add_anchor = last_trend_reduce_anchor = last_adverse_reduce_anchor = None
                                    trend_add_times = dca_add_times = trend_reduce_times = adverse_reduce_times = 0
                                else:
                                    liquidation_price = entry_price * (1 - 1.0 / leverage)

                                trend_reduce_times += 1
                                last_trend_reduce_anchor = trigger

                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'reduce_long',
                                    'price': round(exec_price_reduce, 4),
                                    'amount': round(reduce_shares, 4),
                                    'profit': round(profit, 2),
                                    'balance': round(capital, 2)
                                })

                    # Adverse reduce（逆势减仓：下跌触发）
                    if position_type == 'long' and position > 0 and adverse_reduce_enabled and adverse_reduce_step_pct_eff > 0 and adverse_reduce_size_pct > 0 and (adverse_reduce_max_times == 0 or adverse_reduce_times < adverse_reduce_max_times):
                        anchor = last_adverse_reduce_anchor if last_adverse_reduce_anchor is not None else entry_price
                        trigger = anchor * (1 - adverse_reduce_step_pct_eff)
                        if low <= trigger:
                            reduce_pct = max(adverse_reduce_size_pct, 0.0)
                            reduce_shares = position * reduce_pct
                            if reduce_shares > 0:
                                exec_price_reduce = trigger * (1 - slippage)
                                commission_fee = reduce_shares * exec_price_reduce * commission
                                profit = (exec_price_reduce - entry_price) * reduce_shares - commission_fee
                                capital += profit
                                total_commission_paid += commission_fee
                                position -= reduce_shares
                                if position <= 1e-12:
                                    position = 0
                                    position_type = None
                                    liquidation_price = 0
                                    last_trend_add_anchor = last_dca_add_anchor = last_trend_reduce_anchor = last_adverse_reduce_anchor = None
                                    trend_add_times = dca_add_times = trend_reduce_times = adverse_reduce_times = 0
                                else:
                                    liquidation_price = entry_price * (1 - 1.0 / leverage)

                                adverse_reduce_times += 1
                                last_adverse_reduce_anchor = trigger

                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'reduce_long',
                                    'price': round(exec_price_reduce, 4),
                                    'amount': round(reduce_shares, 4),
                                    'profit': round(profit, 2),
                                    'balance': round(capital, 2)
                                })

                # 做空
                if position_type == 'short' and position < 0:
                    shares_total = abs(position)

                    # Trend add（顺势加空：下跌触发）
                    if trend_add_enabled and trend_add_step_pct_eff > 0 and trend_add_size_pct > 0 and (trend_add_max_times == 0 or trend_add_times < trend_add_max_times):
                        anchor = last_trend_add_anchor if last_trend_add_anchor is not None else entry_price
                        trigger = anchor * (1 - trend_add_step_pct_eff)
                        if low <= trigger:
                            order_pct = trend_add_size_pct
                            if order_pct > 0:
                                exec_price_add = trigger * (1 - slippage)
                                use_capital = capital * order_pct
                                shares_add = (use_capital * leverage) / exec_price_add
                                commission_fee = shares_add * exec_price_add * commission

                                total_cost_before = shares_total * entry_price
                                total_cost_after = total_cost_before + shares_add * exec_price_add
                                position -= shares_add
                                shares_total = abs(position)
                                entry_price = total_cost_after / shares_total

                                capital -= commission_fee
                                total_commission_paid += commission_fee
                                liquidation_price = entry_price * (1 + 1.0 / leverage)

                                trend_add_times += 1
                                last_trend_add_anchor = trigger

                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'add_short',
                                    'price': round(exec_price_add, 4),
                                    'amount': round(shares_add, 4),
                                    'profit': 0,
                                    'balance': round(capital, 2)
                                })

                    # DCA add（逆势加空：上涨触发）
                    if dca_add_enabled and dca_add_step_pct_eff > 0 and dca_add_size_pct > 0 and (dca_add_max_times == 0 or dca_add_times < dca_add_max_times):
                        anchor = last_dca_add_anchor if last_dca_add_anchor is not None else entry_price
                        trigger = anchor * (1 + dca_add_step_pct_eff)
                        if high >= trigger:
                            order_pct = dca_add_size_pct
                            if order_pct > 0:
                                exec_price_add = trigger * (1 - slippage)
                                use_capital = capital * order_pct
                                shares_add = (use_capital * leverage) / exec_price_add
                                commission_fee = shares_add * exec_price_add * commission

                                total_cost_before = shares_total * entry_price
                                total_cost_after = total_cost_before + shares_add * exec_price_add
                                position -= shares_add
                                shares_total = abs(position)
                                entry_price = total_cost_after / shares_total

                                capital -= commission_fee
                                total_commission_paid += commission_fee
                                liquidation_price = entry_price * (1 + 1.0 / leverage)

                                dca_add_times += 1
                                last_dca_add_anchor = trigger

                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'add_short',
                                    'price': round(exec_price_add, 4),
                                    'amount': round(shares_add, 4),
                                    'profit': 0,
                                    'balance': round(capital, 2)
                                })

                    # Trend reduce（顺势减空：下跌触发，回补一部分）
                    if trend_reduce_enabled and trend_reduce_step_pct_eff > 0 and trend_reduce_size_pct > 0 and (trend_reduce_max_times == 0 or trend_reduce_times < trend_reduce_max_times):
                        anchor = last_trend_reduce_anchor if last_trend_reduce_anchor is not None else entry_price
                        trigger = anchor * (1 - trend_reduce_step_pct_eff)
                        if low <= trigger:
                            reduce_pct = max(trend_reduce_size_pct, 0.0)
                            reduce_shares = shares_total * reduce_pct
                            if reduce_shares > 0:
                                exec_price_reduce = trigger * (1 + slippage)
                                commission_fee = reduce_shares * exec_price_reduce * commission
                                profit = (entry_price - exec_price_reduce) * reduce_shares - commission_fee
                                capital += profit
                                total_commission_paid += commission_fee
                                position += reduce_shares
                                shares_total = abs(position)
                                if shares_total <= 1e-12:
                                    position = 0
                                    position_type = None
                                    liquidation_price = 0
                                    last_trend_add_anchor = last_dca_add_anchor = last_trend_reduce_anchor = last_adverse_reduce_anchor = None
                                    trend_add_times = dca_add_times = trend_reduce_times = adverse_reduce_times = 0
                                else:
                                    liquidation_price = entry_price * (1 + 1.0 / leverage)

                                trend_reduce_times += 1
                                last_trend_reduce_anchor = trigger

                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'reduce_short',
                                    'price': round(exec_price_reduce, 4),
                                    'amount': round(reduce_shares, 4),
                                    'profit': round(profit, 2),
                                    'balance': round(capital, 2)
                                })

                    # Adverse reduce（逆势减空：上涨触发）
                    if position_type == 'short' and position < 0 and adverse_reduce_enabled and adverse_reduce_step_pct_eff > 0 and adverse_reduce_size_pct > 0 and (adverse_reduce_max_times == 0 or adverse_reduce_times < adverse_reduce_max_times):
                        anchor = last_adverse_reduce_anchor if last_adverse_reduce_anchor is not None else entry_price
                        trigger = anchor * (1 + adverse_reduce_step_pct_eff)
                        if high >= trigger:
                            reduce_pct = max(adverse_reduce_size_pct, 0.0)
                            reduce_shares = shares_total * reduce_pct
                            if reduce_shares > 0:
                                exec_price_reduce = trigger * (1 + slippage)
                                commission_fee = reduce_shares * exec_price_reduce * commission
                                profit = (entry_price - exec_price_reduce) * reduce_shares - commission_fee
                                capital += profit
                                total_commission_paid += commission_fee
                                position += reduce_shares
                                shares_total = abs(position)
                                if shares_total <= 1e-12:
                                    position = 0
                                    position_type = None
                                    liquidation_price = 0
                                    last_trend_add_anchor = last_dca_add_anchor = last_trend_reduce_anchor = last_adverse_reduce_anchor = None
                                    trend_add_times = dca_add_times = trend_reduce_times = adverse_reduce_times = 0
                                else:
                                    liquidation_price = entry_price * (1 + 1.0 / leverage)

                                adverse_reduce_times += 1
                                last_adverse_reduce_anchor = trigger

                                trades.append({
                                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                                    'type': 'reduce_short',
                                    'price': round(exec_price_reduce, 4),
                                    'amount': round(reduce_shares, 4),
                                    'profit': round(profit, 2),
                                    'balance': round(capital, 2)
                                })

            # 处理不同的交易方向
            if trade_direction == 'long':
                # 只做多模式
                if signal == 1 and position == 0 and capital >= min_capital_to_trade:  # 买入开多
                    logger.debug(f"[做多模式] 买入开多: 时间={timestamp}, 价格={price}, 杠杆={leverage}x")
                    base_price = open_ if signal_timing in ['next_bar_open', 'next_open', 'nextopen', 'next'] else price
                    exec_price = base_price * (1 + slippage)
                    # 使用杠杆：实际持仓 = 本金 × 杠杆 / 价格
                    # 使用指定比例的资金开仓（entryPct 优先；否则全仓）
                    position_pct = None
                    if entry_pct_cfg is not None and entry_pct_cfg > 0:
                        position_pct = entry_pct_cfg
                    if position_pct is not None and 0 < position_pct < 1:
                        use_capital = capital * position_pct
                        shares = (use_capital * leverage) / exec_price
                    else:
                        shares = (capital * leverage) / exec_price
                    # 保证金（手续费从本金扣除）
                    margin = capital
                    commission_fee = shares * exec_price * commission
                    
                    position = shares
                    entry_price = exec_price
                    position_type = 'long'
                    capital -= commission_fee  # 只扣手续费，不扣全部成本
                    total_commission_paid += commission_fee
                    
                    # 计算爆仓线：做多时，价格跌到 entry_price × (1 - 1/leverage) 就爆仓
                    liquidation_price = entry_price * (1 - 1.0 / leverage)
                    logger.debug(f"做多爆仓线: {liquidation_price:.2f}")

                    # init scaling anchors
                    last_trend_add_anchor = entry_price
                    last_dca_add_anchor = entry_price
                    last_trend_reduce_anchor = entry_price
                    last_adverse_reduce_anchor = entry_price
                    
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'open_long',
                        'price': round(exec_price, 4),
                        'amount': round(shares, 4),
                        'profit': 0,
                        'balance': round(capital, 2)
                    })
                
                elif signal == -1 and position > 0:  # 卖出平多
                    logger.debug(f"[做多模式] 卖出平多: 时间={timestamp}, 价格={price}")
                    base_price = open_ if signal_timing in ['next_bar_open', 'next_open', 'nextopen', 'next'] else price
                    exec_price = base_price * (1 - slippage)
                    # 盈亏 = (平仓价 - 开仓价) × 股数 - 手续费
                    commission_fee = position * exec_price * commission
                    profit = (exec_price - entry_price) * position - commission_fee
                    capital += profit
                    total_commission_paid += commission_fee
                    liquidation_price = 0  # 清除爆仓线
                    
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'close_long',
                        'price': round(exec_price, 4),
                        'amount': round(position, 4),
                        'profit': round(profit, 2),
                        'balance': round(capital, 2)
                    })
                    
                    position = 0
                    position_type = None
                    last_trend_add_anchor = last_dca_add_anchor = last_trend_reduce_anchor = last_adverse_reduce_anchor = None
                    trend_add_times = dca_add_times = trend_reduce_times = adverse_reduce_times = 0
                    if capital < min_capital_to_trade:
                        is_liquidated = True
                        capital = 0
                        trades.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'type': 'liquidation',
                            'price': round(exec_price, 4),
                            'amount': 0,
                            'profit': round(-initial_capital, 2),
                            'balance': 0
                        })
            
            elif trade_direction == 'short':
                # 只做空模式
                if signal == -1 and position == 0 and capital >= min_capital_to_trade:  # 卖出开空
                    logger.debug(f"[做空模式] 卖出开空: 时间={timestamp}, 价格={price}, 杠杆={leverage}x")
                    base_price = open_ if signal_timing in ['next_bar_open', 'next_open', 'nextopen', 'next'] else price
                    exec_price = base_price * (1 - slippage)
                    # 使用杠杆：实际持仓 = 本金 × 杠杆 / 价格
                    position_pct = None
                    if entry_pct_cfg is not None and entry_pct_cfg > 0:
                        position_pct = entry_pct_cfg
                    if position_pct is not None and 0 < position_pct < 1:
                        use_capital = capital * position_pct
                        shares = (use_capital * leverage) / exec_price
                    else:
                        shares = (capital * leverage) / exec_price
                    commission_fee = shares * exec_price * commission
                    
                    position = -shares  # 负数表示空头（欠股票）
                    entry_price = exec_price
                    position_type = 'short'
                    capital -= commission_fee  # 只扣手续费
                    total_commission_paid += commission_fee
                    
                    # 计算爆仓线：做空时，价格涨到 entry_price × (1 + 1/leverage) 就爆仓
                    liquidation_price = entry_price * (1 + 1.0 / leverage)
                    logger.debug(f"做空爆仓线: {liquidation_price:.2f}")

                    last_trend_add_anchor = entry_price
                    last_dca_add_anchor = entry_price
                    last_trend_reduce_anchor = entry_price
                    last_adverse_reduce_anchor = entry_price
                    
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'open_short',
                        'price': round(exec_price, 4),
                        'amount': round(shares, 4),
                        'profit': 0,
                        'balance': round(capital, 2)
                    })
                
                elif signal == 1 and position < 0:  # 买入平空
                    logger.debug(f"[做空模式] 买入平空: 时间={timestamp}, 价格={price}")
                    base_price = open_ if signal_timing in ['next_bar_open', 'next_open', 'nextopen', 'next'] else price
                    exec_price = base_price * (1 + slippage)
                    shares = abs(position)  # 需要买回的股数
                    # 盈亏 = (开仓价 - 平仓价) × 股数 - 手续费
                    commission_fee = shares * exec_price * commission
                    profit = (entry_price - exec_price) * shares - commission_fee
                    
                    # 检查是否爆仓
                    if capital + profit <= 0:
                        logger.warning(f"平空时资金不足爆仓: 本金={capital:.2f}, 亏损={-profit:.2f}")
                        capital = 0
                        is_liquidated = True
                        trades.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'type': 'liquidation',
                            'price': round(exec_price, 4),
                            'amount': round(shares, 4),
                            'profit': round(-capital, 2),
                            'balance': 0
                        })
                    else:
                        capital += profit
                        total_commission_paid += commission_fee
                        
                        trades.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'type': 'close_short',
                            'price': round(exec_price, 4),
                            'amount': round(shares, 4),
                            'profit': round(profit, 2),
                            'balance': round(capital, 2)
                        })
                    
                    position = 0
                    position_type = None
                    liquidation_price = 0  # 清除爆仓线
                    last_trend_add_anchor = last_dca_add_anchor = last_trend_reduce_anchor = last_adverse_reduce_anchor = None
                    trend_add_times = dca_add_times = trend_reduce_times = adverse_reduce_times = 0
                    if capital < min_capital_to_trade and not is_liquidated:
                        is_liquidated = True
                        capital = 0
                        trades.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'type': 'liquidation',
                            'price': round(exec_price, 4),
                            'amount': 0,
                            'profit': round(-initial_capital, 2),
                            'balance': 0
                        })
            
            elif trade_direction == 'both':
                # 双向模式
                if signal == 1 and position == 0 and capital >= min_capital_to_trade:  # 买入开多
                    logger.debug(f"[双向模式] 买入开多: 时间={timestamp}, 价格={price}, 杠杆={leverage}x")
                    base_price = open_ if signal_timing in ['next_bar_open', 'next_open', 'nextopen', 'next'] else price
                    exec_price = base_price * (1 + slippage)
                    # 使用杠杆：实际持仓 = 本金 × 杠杆 / 价格
                    position_pct = None
                    if entry_pct_cfg is not None and entry_pct_cfg > 0:
                        position_pct = entry_pct_cfg
                    if position_pct is not None and 0 < position_pct < 1:
                        use_capital = capital * position_pct
                        shares = (use_capital * leverage) / exec_price
                    else:
                        shares = (capital * leverage) / exec_price
                    commission_fee = shares * exec_price * commission
                    
                    position = shares
                    entry_price = exec_price
                    position_type = 'long'
                    capital -= commission_fee  # 只扣手续费
                    total_commission_paid += commission_fee
                    
                    # 计算爆仓线
                    liquidation_price = entry_price * (1 - 1.0 / leverage)
                    logger.debug(f"做多爆仓线: {liquidation_price:.2f}")

                    last_trend_add_anchor = entry_price
                    last_dca_add_anchor = entry_price
                    last_trend_reduce_anchor = entry_price
                    last_adverse_reduce_anchor = entry_price
                    
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'open_long',
                        'price': round(exec_price, 4),
                        'amount': round(shares, 4),
                        'profit': 0,
                        'balance': round(capital, 2)
                    })
                
                elif signal == -1 and position == 0 and capital >= min_capital_to_trade:  # 卖出开空
                    logger.debug(f"[双向模式] 卖出开空: 时间={timestamp}, 价格={price}, 杠杆={leverage}x")
                    base_price = open_ if signal_timing in ['next_bar_open', 'next_open', 'nextopen', 'next'] else price
                    exec_price = base_price * (1 - slippage)
                    # 使用杠杆：实际持仓 = 本金 × 杠杆 / 价格
                    position_pct = None
                    if entry_pct_cfg is not None and entry_pct_cfg > 0:
                        position_pct = entry_pct_cfg
                    if position_pct is not None and 0 < position_pct < 1:
                        use_capital = capital * position_pct
                        shares = (use_capital * leverage) / exec_price
                    else:
                        shares = (capital * leverage) / exec_price
                    commission_fee = shares * exec_price * commission
                    
                    position = -shares
                    entry_price = exec_price
                    position_type = 'short'
                    capital -= commission_fee
                    total_commission_paid += commission_fee
                    
                    # 计算爆仓线
                    liquidation_price = entry_price * (1 + 1.0 / leverage)
                    logger.debug(f"做空爆仓线: {liquidation_price:.2f}")

                    last_trend_add_anchor = entry_price
                    last_dca_add_anchor = entry_price
                    last_trend_reduce_anchor = entry_price
                    last_adverse_reduce_anchor = entry_price

                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'open_short',
                        'price': round(exec_price, 4),
                        'amount': round(shares, 4),
                        'profit': 0,
                        'balance': round(capital, 2)
                    })
                
                elif signal == -1 and position > 0:  # 平多开空
                    logger.debug(f"[双向模式] 平多开空: 时间={timestamp}, 价格={price}")
                    # 先平多
                    base_price = open_ if signal_timing in ['next_bar_open', 'next_open', 'nextopen', 'next'] else price
                    exec_price = base_price * (1 - slippage)
                    commission_fee_close = position * exec_price * commission
                    profit = (exec_price - entry_price) * position - commission_fee_close
                    capital += profit
                    total_commission_paid += commission_fee_close
                    
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'close_long',
                        'price': round(exec_price, 4),
                        'amount': round(position, 4),
                        'profit': round(profit, 2),
                        'balance': round(capital, 2)
                    })
                    
                    # 若平仓后余额过低则停止（避免同K线反手开仓）
                    if capital < min_capital_to_trade or is_liquidated:
                        is_liquidated = True
                        capital = 0
                        trades.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'type': 'liquidation',
                            'price': round(exec_price, 4),
                            'amount': 0,
                            'profit': round(-initial_capital, 2),
                            'balance': 0
                        })
                        continue

                    # Re-open short (respects entryPct; default entryPct=100%)
                    position_pct = None
                    if entry_pct_cfg is not None and entry_pct_cfg > 0:
                        position_pct = entry_pct_cfg
                    if position_pct is not None and 0 < position_pct < 1:
                        use_capital = capital * position_pct
                        shares = (use_capital * leverage) / exec_price
                    else:
                        shares = (capital * leverage) / exec_price
                    commission_fee_open = shares * exec_price * commission
                    
                    position = -shares
                    entry_price = exec_price
                    position_type = 'short'
                    capital -= commission_fee_open
                    total_commission_paid += commission_fee_open
                    
                    # 计算爆仓线
                    liquidation_price = entry_price * (1 + 1.0 / leverage)
                    logger.debug(f"做空爆仓线: {liquidation_price:.2f}")
                    
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'open_short',
                        'price': round(exec_price, 4),
                        'amount': round(shares, 4),
                        'profit': 0,
                        'balance': round(capital, 2)
                    })
                
                elif signal == 1 and position < 0:  # 平空开多
                    logger.debug(f"[双向模式] 平空开多: 时间={timestamp}, 价格={price}")
                    # 先平空
                    base_price = open_ if signal_timing in ['next_bar_open', 'next_open', 'nextopen', 'next'] else price
                    exec_price = base_price * (1 + slippage)
                    shares = abs(position)
                    commission_fee_close = shares * exec_price * commission
                    profit = (entry_price - exec_price) * shares - commission_fee_close
                    
                    # 检查是否爆仓
                    if capital + profit <= 0:
                        logger.warning(f"平空时资金不足爆仓: 本金={capital:.2f}, 亏损={-profit:.2f}")
                        capital = 0
                        is_liquidated = True
                        trades.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'type': 'liquidation',
                            'price': round(exec_price, 4),
                            'amount': round(shares, 4),
                            'profit': round(-capital, 2),
                            'balance': 0
                        })
                        position = 0
                        position_type = None
                        continue  # 爆仓后不再开新仓
                    
                    capital += profit
                    total_commission_paid += commission_fee_close
                    
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'close_short',
                        'price': round(exec_price, 4),
                        'amount': round(shares, 4),
                        'profit': round(profit, 2),
                        'balance': round(capital, 2)
                    })
                    
                    if capital < min_capital_to_trade or is_liquidated:
                        is_liquidated = True
                        capital = 0
                        trades.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'type': 'liquidation',
                            'price': round(exec_price, 4),
                            'amount': 0,
                            'profit': round(-initial_capital, 2),
                            'balance': 0
                        })
                        continue

                    # Re-open long (respects entryPct; default entryPct=100%)
                    position_pct = None
                    if entry_pct_cfg is not None and entry_pct_cfg > 0:
                        position_pct = entry_pct_cfg
                    if position_pct is not None and 0 < position_pct < 1:
                        use_capital = capital * position_pct
                        shares = (use_capital * leverage) / exec_price
                    else:
                        shares = (capital * leverage) / exec_price
                    commission_fee_open = shares * exec_price * commission
                    
                    position = shares
                    entry_price = exec_price
                    position_type = 'long'
                    capital -= commission_fee_open
                    total_commission_paid += commission_fee_open
                    
                    # 计算爆仓线
                    liquidation_price = entry_price * (1 - 1.0 / leverage)
                    logger.debug(f"做多爆仓线: {liquidation_price:.2f}")
                    
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'open_long',
                        'price': round(exec_price, 4),
                        'amount': round(shares, 4),
                        'profit': 0,
                        'balance': round(capital, 2)
                    })
            
            # 检测持仓期间是否触及爆仓线（作为兜底保护，仅在没有主动平仓的情况下检查）
            # 注意：这个检查在所有信号处理之后，确保止损/止盈优先执行
            if position != 0 and not is_liquidated:
                if position_type == 'long':
                    # 做多爆仓：价格跌破爆仓线
                    if price <= liquidation_price:
                        logger.warning(f"做多爆仓！开仓价={entry_price:.2f}, 当前价={price:.2f}, 爆仓线={liquidation_price:.2f}")
                        is_liquidated = True
                        capital = 0
                        trades.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'type': 'liquidation',
                            'price': round(liquidation_price, 4),
                            'amount': round(abs(position), 4),
                            'profit': round(-initial_capital, 2),
                            'balance': 0
                        })
                        position = 0
                        position_type = None
                        equity_curve.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'value': 0
                        })
                        continue
                elif position_type == 'short':
                    # 做空爆仓：价格涨破爆仓线
                    if price >= liquidation_price:
                        logger.warning(f"做空爆仓！开仓价={entry_price:.2f}, 当前价={price:.2f}, 爆仓线={liquidation_price:.2f}")
                        is_liquidated = True
                        capital = 0
                        trades.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'type': 'liquidation',
                            'price': round(liquidation_price, 4),
                            'amount': round(abs(position), 4),
                            'profit': round(-initial_capital, 2),
                            'balance': 0
                        })
                        position = 0
                        position_type = None
                        equity_curve.append({
                            'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                            'value': 0
                        })
                        continue
            
            # 记录权益
            if position_type == 'long':
                # 多头权益 = 现金 + 未实现盈亏
                # 未实现盈亏 = (当前价 - 开仓价) × 股数
                unrealized_pnl = (price - entry_price) * position
                total_value = capital + unrealized_pnl
            elif position_type == 'short':
                # 空头权益 = 现金 + 未实现盈亏
                # 未实现盈亏 = (开仓价 - 当前价) × 股数
                shares = abs(position)
                unrealized_pnl = (entry_price - price) * shares
                total_value = capital + unrealized_pnl
            else:
                total_value = capital
            
            # 确保权益不为负（如果已经爆仓，在前面已经处理了）
            if total_value < 0:
                total_value = 0
            
            equity_curve.append({
                'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                'value': round(total_value, 2)
            })
        
        # 回测结束时强制平仓
        if position != 0:
            timestamp = df.index[-1]
            price = df.iloc[-1]['close']
            
            if position > 0:  # 平多
                exec_price = price * (1 - slippage)
                commission_fee = position * exec_price * commission
                profit = (exec_price - entry_price) * position - commission_fee
                capital += profit
                total_commission_paid += commission_fee
                
                # 记录平多交易
                trades.append({
                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                    'type': 'close_long',
                    'price': round(exec_price, 4),
                    'amount': round(position, 4),
                    'profit': round(profit, 2),
                    'balance': round(capital, 2)
                })
            else:  # 平空
                exec_price = price * (1 + slippage)
                shares = abs(position)
                commission_fee = shares * exec_price * commission
                profit = (entry_price - exec_price) * shares - commission_fee
                
                # 检查是否爆仓
                if capital + profit <= 0:
                    logger.warning(f"回测结束爆仓！平空亏损过大: 本金={capital:.2f}, 亏损={-profit:.2f}")
                    is_liquidated = True
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'liquidation',
                        'price': round(exec_price, 4),
                        'amount': round(shares, 4),
                        'profit': round(-capital, 2),
                        'balance': 0
                    })
                    capital = 0
                else:
                    capital += profit
                    total_commission_paid += commission_fee
                    
                    # 记录平空交易
                    trades.append({
                        'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                        'type': 'close_short',
                        'price': round(exec_price, 4),
                        'amount': round(shares, 4),
                        'profit': round(profit, 2),
                        'balance': round(capital, 2)
                    })
            
            # 更新权益曲线的最后一个值，包含强制平仓后的资金
            if equity_curve:
                equity_curve[-1]['value'] = round(capital, 2)
        
        return equity_curve, trades, total_commission_paid
    
    def _calculate_metrics(
        self,
        equity_curve: List,
        trades: List,
        initial_capital: float,
        timeframe: str,
        start_date: datetime,
        end_date: datetime,
        total_commission: float = 0
    ) -> Dict:
        """计算回测指标"""
        if not equity_curve:
            return {}
        
        final_value = equity_curve[-1]['value']
        total_return = (final_value - initial_capital) / initial_capital * 100
        
        # 计算年化收益：使用简单年化而不是复利年化
        # 对于高收益率策略，复利年化会产生天文数字，不具备参考价值
        actual_days = (end_date - start_date).total_seconds() / 86400
        years = actual_days / 365.0
        
        # 简单年化：年化收益率 = 总收益率 / 年数
        if years > 0:
            annual_return = total_return / years
        else:
            annual_return = 0
        
        # 计算最大回撤
        values = [e['value'] for e in equity_curve]
        max_drawdown = self._calculate_max_drawdown(values)
        
        # 计算夏普比率
        sharpe = self._calculate_sharpe(values, timeframe)
        
        # 计算总盈亏：用最终权益减去初始资金（最准确）
        total_profit = final_value - initial_capital
        
        # 计算胜率（包含所有平仓操作）
        # 平仓操作：profit != 0 的交易
        closing_trades = [t for t in trades if t.get('profit', 0) != 0]
        win_trades = [t for t in closing_trades if t['profit'] > 0]
        loss_trades = [t for t in closing_trades if t['profit'] < 0]
        total_trades = len(closing_trades)
        win_rate = len(win_trades) / total_trades * 100 if total_trades > 0 else 0
        
        # 计算盈亏比（Profit Factor = 总盈利 / 总亏损）
        total_wins = sum(t['profit'] for t in win_trades)
        total_losses = abs(sum(t['profit'] for t in loss_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else (total_wins if total_wins > 0 else 0)
        
        return {
            'totalReturn': round(total_return, 2),
            'annualReturn': round(annual_return, 2),
            'maxDrawdown': round(max_drawdown, 2),
            'sharpeRatio': round(sharpe, 2),
            'winRate': round(win_rate, 2),
            'profitFactor': round(profit_factor, 2),
            'totalTrades': total_trades,
            'totalProfit': round(total_profit, 2),
            'totalCommission': round(total_commission, 2)
        }
    
    def _calculate_max_drawdown(self, values: List[float]) -> float:
        """计算最大回撤"""
        if not values:
            return 0
        
        peak = values[0]
        max_dd = 0
        
        for value in values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak * 100
            if dd > max_dd:
                max_dd = dd
        
        return -max_dd
    
    def _calculate_sharpe(self, values: List[float], timeframe: str = '1D', risk_free_rate: float = 0.02) -> float:
        """
        计算夏普比率
        
        Args:
            values: 权益曲线数值列表
            timeframe: 时间周期
            risk_free_rate: 无风险收益率（年化）
        """
        if len(values) < 2:
            return 0
        
        # 过滤掉0值（爆仓后的数据），避免除以0
        valid_values = [v for v in values if v > 0]
        if len(valid_values) < 2:
            return 0
        
        # 根据时间周期确定年化系数
        annualization_factor = {
            '1m': 252 * 24 * 60,      # 分钟K：约362,880
            '5m': 252 * 24 * 12,      # 5分钟K：约72,576
            '15m': 252 * 24 * 4,      # 15分钟K：约24,192
            '30m': 252 * 24 * 2,      # 30分钟K：约12,096
            '1H': 252 * 24,           # 小时K：6,048
            '4H': 252 * 6,            # 4小时K：1,512
            '1D': 252,                # 日K：252
            '1W': 52                  # 周K：52
        }.get(timeframe, 252)
        
        try:
            # 计算周期收益率
            returns = np.diff(valid_values) / valid_values[:-1]
            
            # 过滤无效值
            returns = returns[np.isfinite(returns)]
            if len(returns) == 0:
                return 0
            
            # 年化平均收益率
            avg_return = np.mean(returns) * annualization_factor
            
            # 年化标准差（波动率）
            std_return = np.std(returns) * np.sqrt(annualization_factor)
            
            if std_return == 0 or not np.isfinite(std_return):
                return 0
            
            # 夏普比率 = (年化收益 - 无风险利率) / 年化波动率
            sharpe = (avg_return - risk_free_rate) / std_return
            return sharpe if np.isfinite(sharpe) else 0
        except Exception as e:
            logger.warning(f"夏普比率计算失败: {e}")
            return 0
    
    def _format_result(
        self,
        metrics: Dict,
        equity_curve: List,
        trades: List
    ) -> Dict[str, Any]:
        """格式化回测结果"""
        # 精简权益曲线
        max_points = 500
        if len(equity_curve) > max_points:
            step = len(equity_curve) // max_points
            equity_curve = equity_curve[::step]
        
        # 清理数据中的NaN、Inf值，确保可以被JSON序列化
        def clean_value(value):
            """清理数值，将NaN/Inf转换为0"""
            if isinstance(value, float):
                if np.isnan(value) or np.isinf(value):
                    return 0
            return value
        
        # 清理metrics
        cleaned_metrics = {}
        for key, value in metrics.items():
            cleaned_metrics[key] = clean_value(value)
        
        # 清理equity_curve
        cleaned_curve = []
        for item in equity_curve:
            cleaned_curve.append({
                'time': item['time'],
                'value': clean_value(item['value'])
            })
        
        # 清理trades
        cleaned_trades = []
        # 不截断交易记录：有多少条就返回多少条（前端可自行分页展示）
        for trade in trades:
            cleaned_trade = {}
            for key, value in trade.items():
                cleaned_trade[key] = clean_value(value)
            cleaned_trades.append(cleaned_trade)
        
        return {
            **cleaned_metrics,
            'equityCurve': cleaned_curve,
            'trades': cleaned_trades
        }

