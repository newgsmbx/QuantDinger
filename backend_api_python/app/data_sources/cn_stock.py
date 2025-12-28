"""
CN/HK stock data source.
Supports A-Share and H-Share with multiple public sources.
Priority (AShare): Eastmoney (intraday/daily) > yfinance (daily) > akshare (daily, optional).
Priority (HShare): Tencent (intraday) > Eastmoney/Tencent (daily) > yfinance (daily) > akshare (daily, optional).
"""
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import requests

import yfinance as yf

from app.data_sources.base import BaseDataSource
from app.data_sources.us_stock import USStockDataSource
from app.utils.logger import get_logger
from app.utils.http import get_retry_session

logger = get_logger(__name__)

# Optional dependency: akshare
try:
    import akshare as ak  # type: ignore
    HAS_AKSHARE = True
    logger.debug("akshare is available")
except ImportError:
    HAS_AKSHARE = False
    # Keep it quiet to avoid noisy startup logs on Windows.
    logger.debug("akshare is not installed; akshare-based features are disabled")


class TencentDataMixin:
    """Tencent quote API mixin (mostly for H-Share and legacy fallback)."""
    
    # 腾讯 K 线周期映射（注意：腾讯分钟级接口不支持240分钟，4H需要特殊处理）
    TENCENT_PERIOD_MAP = {
        '1m': 1,
        '5m': 5,
        '15m': 15,
        '30m': 30,
        '1H': 60,
        '1D': 'day',
        '1W': 'week'
    }
    
    def _fetch_tencent_kline(
        self,
        symbol_code: str,
        timeframe: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        使用腾讯财经接口获取K线数据
        
        Args:
            symbol_code: 腾讯格式的代码 (sh600000, sz000001, hk00700)
            timeframe: 时间周期
            limit: 数据条数
        """
        klines = []
        
        # 4H 需要特殊处理：获取1H数据然后聚合
        if timeframe == '4H':
            return self._fetch_and_aggregate_4h(symbol_code, limit)
        
        try:
            period = self.TENCENT_PERIOD_MAP.get(timeframe)
            if period is None:
                logger.warning(f"Unsupported timeframe: {timeframe}")
                return []
            
            # 构建请求URL
            if isinstance(period, int):
                # 分钟级数据
                url = f"http://ifzq.gtimg.cn/appstock/app/kline/mkline?param={symbol_code},m{period},,{limit}"
            else:
                # 日线/周线数据
                url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={symbol_code},{period},,,{limit},qfq"
            
            # logger.info(f"腾讯财经请求: {symbol_code}, 周期: {timeframe}, URL: {url[:80]}...")
            
            session = get_retry_session()
            response = session.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.warning(f"Tencent quote returned status: {response.status_code}")
                return []
            
            data = response.json()
            
            # 解析响应数据
            if data.get('code') == 0 and 'data' in data:
                stock_data = data['data'].get(symbol_code)
                if stock_data:
                    # 分钟级数据格式
                    if isinstance(period, int):
                        candles = stock_data.get(f'm{period}', [])
                    else:
                        # 日线/周线数据格式
                        candles = stock_data.get('qfqday', stock_data.get('day', []))
                    
                    for candle in candles:
                        if len(candle) >= 5:
                            # 解析时间
                            time_str = str(candle[0])
                            try:
                                if len(time_str) == 12:  # 分钟级: 202411301430
                                    dt = datetime.strptime(time_str, '%Y%m%d%H%M')
                                elif len(time_str) == 10:  # 日线: 2024-11-30
                                    dt = datetime.strptime(time_str, '%Y-%m-%d')
                                else:
                                    continue
                                
                                klines.append(self.format_kline(
                                    timestamp=int(dt.timestamp()),
                                    open_price=float(candle[1]),
                                    high=float(candle[3]),
                                    low=float(candle[4]),
                                    close=float(candle[2]),
                                    volume=float(candle[5]) if len(candle) > 5 else 0
                                ))
                            except (ValueError, IndexError) as e:
                                logger.debug(f"Failed to parse kline candle: {candle}, error: {e}")
                                continue
                    
                    # logger.info(f"腾讯财经返回 {len(klines)} 条数据")
            else:
                logger.warning(f"Tencent quote returned unexpected data: code={data.get('code')}")
                
        except Exception as e:
            logger.error(f"Tencent quote fetch failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return klines
    
    def _fetch_and_aggregate_4h(self, symbol_code: str, limit: int) -> List[Dict[str, Any]]:
        """获取1H数据并聚合为4H"""
        # 获取足够多的1H数据
        hour_klines = self._fetch_tencent_kline(symbol_code, '1H', limit * 4 + 10)
        
        if not hour_klines:
            return []
        
        # 按4小时聚合
        aggregated = []
        i = 0
        while i < len(hour_klines):
            # 取4根K线
            batch = hour_klines[i:i+4]
            if len(batch) < 4:
                break
            
            aggregated.append(self.format_kline(
                timestamp=batch[0]['time'],
                open_price=batch[0]['open'],
                high=max(k['high'] for k in batch),
                low=min(k['low'] for k in batch),
                close=batch[-1]['close'],
                volume=sum(k['volume'] for k in batch)
            ))
            i += 4
        
        # logger.info(f"聚合生成 {len(aggregated)} 条 4H 数据")
        return aggregated[-limit:] if len(aggregated) > limit else aggregated


class AShareDataSource(BaseDataSource, TencentDataMixin):
    """A-Share data source."""
    
    name = "AShare"
    
    # akshare 时间周期映射
    AKSHARE_PERIOD_MAP = {
        '1D': 'daily',
        '1W': 'weekly'
    }
    
    # 东方财富 K 线周期映射
    EM_PERIOD_MAP = {
        '1m': '1',
        '5m': '5',
        '15m': '15',
        '30m': '30',
        '1H': '60',
        '4H': '240',
        '1D': '101',
        '1W': '102',
    }
    
    def __init__(self):
        self.us_stock_source = USStockDataSource()
    
    def get_kline(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        before_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch A-Share Kline data."""
        klines = []
        
        # Prefer Eastmoney (supports most intraday timeframes)
        klines = self._fetch_eastmoney_ashare(symbol, timeframe, limit)
        if klines:
            klines = self.filter_and_limit(klines, limit, before_time)
            self.log_result(symbol, klines, timeframe)
            return klines
        
        # Fallback: yfinance (daily/weekly)
        if timeframe in ('1D', '1W'):
            yahoo_symbol = self._to_yahoo_symbol(symbol)
            if yahoo_symbol:
                # logger.info(f"尝试使用 yfinance 获取A股: {yahoo_symbol}")
                klines = self.us_stock_source.get_kline(yahoo_symbol, timeframe, limit, before_time)
                if klines:
                    # logger.info(f"yfinance 成功获取 {len(klines)} 条A股数据")
                    return klines
        
        # Fallback: akshare (daily/weekly)
        if HAS_AKSHARE and timeframe in self.AKSHARE_PERIOD_MAP:
            klines = self._fetch_akshare(symbol, timeframe, limit, before_time)
            if klines:
                return klines
        
        logger.warning(f"AShare {symbol} data fetch failed")
        return klines
    
    def _to_tencent_symbol(self, symbol: str) -> Optional[str]:
        """转换为腾讯财经格式"""
        if symbol.startswith('6'):
            return f"sh{symbol}"
        elif symbol.startswith('0') or symbol.startswith('3'):
            return f"sz{symbol}"
        elif symbol.startswith('4') or symbol.startswith('8'):
            return f"bj{symbol}"  # 北交所
        return None
    
    def _to_yahoo_symbol(self, symbol: str) -> Optional[str]:
        """转换为 Yahoo Finance 格式"""
        if symbol.startswith('6'):
            return f"{symbol}.SS"
        elif symbol.startswith('0') or symbol.startswith('3'):
            return f"{symbol}.SZ"
        elif symbol.startswith('4') or symbol.startswith('8'):
            return f"{symbol}.BJ"
        return None
    
    def _fetch_eastmoney_ashare(
        self,
        symbol: str,
        timeframe: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """使用东方财富获取A股数据"""
        klines = []
        
        period = self.EM_PERIOD_MAP.get(timeframe)
        if not period:
            logger.warning(f"Eastmoney unsupported timeframe: {timeframe}")
            return []
        
        try:
            # 确定市场代码: 上海=1, 深圳=0, 北交所=0
            if symbol.startswith('6'):
                secid = f"1.{symbol}"
            else:
                secid = f"0.{symbol}"
            
            # 东方财富K线接口
            url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
            params = {
                'secid': secid,
                'fields1': 'f1,f2,f3,f4,f5,f6',
                'fields2': 'f51,f52,f53,f54,f55,f56,f57',
                'klt': period,
                'fqt': '1',  # 前复权
                'end': '20500101',
                'lmt': limit,
            }
            
            # logger.info(f"东方财富A股请求: {symbol}, 周期: {timeframe}")
            
            # 添加浏览器请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://quote.eastmoney.com/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
            
            session = get_retry_session()
            response = session.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"Eastmoney HTTP status: {response.status_code}")
                return []
            
            data = response.json()
            
            # 解析响应
            if data.get('data') and data['data'].get('klines'):
                for line in data['data']['klines']:
                    try:
                        parts = line.split(',')
                        if len(parts) >= 6:
                            time_str = parts[0]
                            if ' ' in time_str:
                                dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
                            else:
                                dt = datetime.strptime(time_str, '%Y-%m-%d')
                            
                            klines.append(self.format_kline(
                                timestamp=int(dt.timestamp()),
                                open_price=float(parts[1]),
                                high=float(parts[3]),
                                low=float(parts[4]),
                                close=float(parts[2]),
                                volume=float(parts[5])
                            ))
                    except (ValueError, IndexError) as e:
                        logger.debug(f"Failed to parse Eastmoney data line: {line}, error: {e}")
                        continue
                
                # logger.info(f"东方财富返回 {len(klines)} 条A股数据")
            else:
                logger.warning("Eastmoney returned no data")
            
        except Exception as e:
            logger.error(f"Eastmoney A-share fetch failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return klines
    
    def _fetch_akshare(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        before_time: Optional[int]
    ) -> List[Dict[str, Any]]:
        """使用 akshare 获取数据"""
        klines = []
        
        try:
            period = self.AKSHARE_PERIOD_MAP.get(timeframe, 'daily')
            
            # 计算日期范围
            if before_time:
                end_date = datetime.fromtimestamp(before_time).strftime('%Y%m%d')
            else:
                end_date = datetime.now().strftime('%Y%m%d')
            
            days = limit * 2 if timeframe == '1D' else limit * 10
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
            
            # logger.info(f"使用 akshare 获取A股: {symbol}, 周期: {period}")
            
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period=period,
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"  # 前复权
            )
            
            if df is not None and not df.empty:
                df = df.tail(limit)
                for _, row in df.iterrows():
                    ts = int(datetime.strptime(str(row['日期']), '%Y-%m-%d').timestamp())
                    klines.append(self.format_kline(
                        timestamp=ts,
                        open_price=row['开盘'],
                        high=row['最高'],
                        low=row['最低'],
                        close=row['收盘'],
                        volume=row['成交量']
                    ))
                # logger.info(f"akshare 返回 {len(klines)} 条A股数据")
                
        except Exception as e:
            logger.error(f"Akshare A-share fetch failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return klines


class HShareDataSource(BaseDataSource, TencentDataMixin):
    """港股数据源"""
    
    name = "HShare"
    
    def __init__(self):
        self.us_stock_source = USStockDataSource()
    
    def get_kline(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        before_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """获取港股K线数据"""
        klines = []
        
        # 方案1: 腾讯财经 (港股日线/周线首选，稳定可靠)
        if timeframe in ('1D', '1W'):
            tencent_symbol = self._to_tencent_symbol(symbol)
            if tencent_symbol:
                # logger.info(f"尝试使用腾讯财经获取港股: {tencent_symbol}")
                klines = self._fetch_tencent_kline(tencent_symbol, timeframe, limit)
                if klines:
                    klines = self.filter_and_limit(klines, limit, before_time)
                    self.log_result(symbol, klines, timeframe)
                    return klines
        
        # 方案2: 东方财富 (支持所有周期，但可能有地域限制)
        klines = self._fetch_eastmoney_kline(symbol, timeframe, limit)
        if klines:
            klines = self.filter_and_limit(klines, limit, before_time)
            self.log_result(symbol, klines, timeframe)
            return klines
        
        # 方案3: 尝试 yfinance (日线级别备选)
        if timeframe in ('1D', '1W'):
            yahoo_symbol = self._to_yahoo_symbol(symbol)
            if yahoo_symbol:
                # logger.info(f"尝试使用 yfinance 获取港股: {yahoo_symbol}")
                klines = self.us_stock_source.get_kline(yahoo_symbol, timeframe, limit, before_time)
                if klines:
                    # logger.info(f"yfinance 成功获取 {len(klines)} 条港股数据")
                    return klines
        
        # 方案4: 尝试 akshare (日线级别)
        if HAS_AKSHARE and timeframe in ('1D', '1W'):
            klines = self._fetch_akshare(symbol, timeframe, limit, before_time)
            if klines:
                return klines
        
        # 分钟级数据获取失败提示
        if timeframe not in ('1D', '1W'):
            logger.warning(f"HK stock {symbol}: minute-level data is not supported (data source limitations)")
        else:
            logger.warning(f"HK stock {symbol}: data fetch failed (timeframe: {timeframe})")
        return klines
    
    def _to_tencent_symbol(self, symbol: str) -> str:
        """转换为腾讯财经格式"""
        # 港股代码补齐到5位
        padded = symbol.zfill(5)
        return f"hk{padded}"
    
    def _to_yahoo_symbol(self, symbol: str) -> str:
        """转换为 Yahoo Finance 格式"""
        # 港股代码补齐到4位
        padded = symbol.zfill(4)
        return f"{padded}.HK"
    
    def _fetch_eastmoney_kline(
        self,
        symbol: str,
        timeframe: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """使用东方财富获取港股分钟级数据"""
        klines = []
        
        # 东方财富 K 线周期映射
        em_period_map = {
            '1m': '1',
            '5m': '5',
            '15m': '15',
            '30m': '30',
            '1H': '60',
            '4H': '240',
            '1D': '101',
            '1W': '102',
        }
        
        period = em_period_map.get(timeframe)
        if not period:
            logger.warning(f"Eastmoney unsupported timeframe: {timeframe}")
            return []
        
        try:
            # 港股代码补齐到5位
            hk_symbol = symbol.zfill(5)
            # 东方财富港股代码格式: 116.00700 (116是港股市场代码)
            secid = f"116.{hk_symbol}"
            
            # 东方财富K线接口
            url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get"
            params = {
                'secid': secid,
                'fields1': 'f1,f2,f3,f4,f5,f6',
                'fields2': 'f51,f52,f53,f54,f55,f56,f57',
                'klt': period,  # K线类型
                'fqt': '1',  # 前复权
                'end': '20500101',
                'lmt': limit,
            }
            
            # logger.info(f"东方财富港股请求: {hk_symbol}, 周期: {timeframe}")
            
            # 添加浏览器请求头，避免被拒绝
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://quote.eastmoney.com/',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
            
            session = get_retry_session()
            response = session.get(url, params=params, headers=headers, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"Eastmoney HTTP status: {response.status_code}")
                return []
            
            data = response.json()
            
            # 解析响应
            if data.get('data') and data['data'].get('klines'):
                for line in data['data']['klines']:
                    try:
                        # 格式: "2025-11-28 15:00,400.0,401.0,399.0,400.5,1000,100000"
                        # 日期,开盘,收盘,最高,最低,成交量,成交额
                        parts = line.split(',')
                        if len(parts) >= 6:
                            time_str = parts[0]
                            # 解析时间
                            if ' ' in time_str:
                                dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
                            else:
                                dt = datetime.strptime(time_str, '%Y-%m-%d')
                            
                            klines.append(self.format_kline(
                                timestamp=int(dt.timestamp()),
                                open_price=float(parts[1]),
                                high=float(parts[3]),
                                low=float(parts[4]),
                                close=float(parts[2]),
                                volume=float(parts[5])
                            ))
                    except (ValueError, IndexError) as e:
                        logger.debug(f"Failed to parse Eastmoney data line: {line}, error: {e}")
                        continue
                
                # logger.info(f"东方财富返回 {len(klines)} 条港股数据")
            else:
                logger.warning("Eastmoney returned no data")
            
        except Exception as e:
            logger.error(f"Eastmoney HK stock fetch failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return klines
    
    def _fetch_akshare(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        before_time: Optional[int]
    ) -> List[Dict[str, Any]]:
        """使用 akshare 获取港股数据"""
        klines = []
        
        try:
            # 计算日期范围
            if before_time:
                end_date = datetime.fromtimestamp(before_time).strftime('%Y%m%d')
            else:
                end_date = datetime.now().strftime('%Y%m%d')
            
            days = limit * 2 if timeframe == '1D' else limit * 10
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
            
            # 港股代码补齐到5位
            hk_symbol = symbol.zfill(5)
            
            # logger.info(f"使用 akshare 获取港股: {hk_symbol}")
            
            df = ak.stock_hk_hist(
                symbol=hk_symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust="qfq"
            )
            
            if df is not None and not df.empty:
                df = df.tail(limit)
                for _, row in df.iterrows():
                    ts = int(datetime.strptime(str(row['日期']), '%Y-%m-%d').timestamp())
                    klines.append(self.format_kline(
                        timestamp=ts,
                        open_price=row['开盘'],
                        high=row['最高'],
                        low=row['最低'],
                        close=row['收盘'],
                        volume=row['成交量']
                    ))
                # logger.info(f"akshare 返回 {len(klines)} 条港股数据")
                
        except Exception as e:
            logger.error(f"Akshare HK stock fetch failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return klines
