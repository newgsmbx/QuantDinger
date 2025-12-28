"""
外汇数据源
使用 Tiingo 获取外汇数据
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import time
import requests

from app.data_sources.base import BaseDataSource, TIMEFRAME_SECONDS
from app.utils.logger import get_logger
from app.config import TiingoConfig, APIKeys

logger = get_logger(__name__)


class ForexDataSource(BaseDataSource):
    """外汇数据源 (Tiingo)"""
    
    name = "Forex/Tiingo"
    
    # Tiingo resampleFreq 映射
    # Tiingo 支持: 1min, 5min, 15min, 30min, 1hour, 4hour, 1day 等
    TIMEFRAME_MAP = {
        '1m': '1min',
        '5m': '5min',
        '15m': '15min',
        '30m': '30min',
        '1H': '1hour',
        '4H': '4hour',
        '1D': '1day',
        '1W': '1week',
        '1M': '1month'
    }
    
    # 外汇对映射 (Tiingo 使用标准 ticker，如 eurusd, audusd)
    # 大写也可以，Tiingo 通常不区分大小写，但建议统一
    SYMBOL_MAP = {
        # 贵金属 (Tiingo 不一定支持所有 OANDA 格式的贵金属，通常是 XAUUSD)
        'XAUUSD': 'xauusd',
        'XAGUSD': 'xagusd',
        # 主要货币对
        'EURUSD': 'eurusd',
        'GBPUSD': 'gbpusd',
        'USDJPY': 'usdjpy',
        'AUDUSD': 'audusd',
        'USDCAD': 'usdcad',
        'USDCHF': 'usdchf',
        'NZDUSD': 'nzdusd',
    }
    
    def __init__(self):
        self.base_url = TiingoConfig.BASE_URL
        if not APIKeys.TIINGO_API_KEY:
             logger.warning("Tiingo API key is not configured; FX data will be unavailable")
    
    def _get_timeframe_seconds(self, timeframe: str) -> int:
        """获取时间周期对应的秒数"""
        return TIMEFRAME_SECONDS.get(timeframe, 86400)
    
    def get_kline(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
        before_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取外汇K线数据
        
        Args:
            symbol: 外汇对代码（如 XAUUSD, EURUSD）
            timeframe: 时间周期
            limit: 数据条数
            before_time: 结束时间戳
        """
        # 动态获取 API Key
        api_key = APIKeys.TIINGO_API_KEY
        if not api_key:
            logger.error("Tiingo API key is not configured")
            return []
            
        try:
            # 1. 解析 Symbol
            tiingo_symbol = self.SYMBOL_MAP.get(symbol)
            if not tiingo_symbol:
                # 尝试智能转换: EURUSD -> eurusd
                tiingo_symbol = symbol.lower()

            # 2. 解析 Resolution (resampleFreq)
            resample_freq = self.TIMEFRAME_MAP.get(timeframe)
            if not resample_freq:
                logger.warning(f"Tiingo does not support timeframe: {timeframe}")
                return []
            
            # 3. 计算时间范围
            if before_time:
                end_dt = datetime.fromtimestamp(before_time)
            else:
                end_dt = datetime.now()
            
            # 根据周期和数量计算开始时间
            tf_seconds = self._get_timeframe_seconds(timeframe)
            # 多取一些缓冲时间
            start_dt = end_dt - timedelta(seconds=limit * tf_seconds * 2)
            
            # 格式化日期为 YYYY-MM-DD (Tiingo 支持该格式)
            start_date_str = start_dt.strftime('%Y-%m-%d')
            end_date_str = end_dt.strftime('%Y-%m-%d')
            
            # 4. API 请求
            # URL: https://api.tiingo.com/tiingo/fx/{ticker}/prices
            url = f"{self.base_url}/fx/{tiingo_symbol}/prices"
            
            params = {
                'startDate': start_date_str,
                'endDate': end_date_str,
                'resampleFreq': resample_freq,
                'token': api_key,
                'format': 'json'
            }
            
            # logger.info(f"Tiingo Request: {url} params={params}")
            
            response = requests.get(url, params=params, timeout=TiingoConfig.TIMEOUT)
            
            if response.status_code == 403: # 具体的权限错误
                 logger.error("Tiingo API permission error (403): check whether your API key is valid and has access to this dataset.")
                 return []
                 
            response.raise_for_status()
            data = response.json()
            
            # 5. 处理响应
            # Tiingo returns a list of dicts:
            # [
            #   {
            #     "date": "2023-01-01T00:00:00.000Z",
            #     "ticker": "eurusd",
            #     "open": 1.07,
            #     "high": 1.08,
            #     "low": 1.06,
            #     "close": 1.07
            #     "mid": ... (optional, depends on settings, usually OHLC are bid or mid)
            #   }, ...
            # ]
            # Note: Tiingo FX prices objects keys: date, open, high, low, close.
            
            if not isinstance(data, list):
                logger.warning(f"Tiingo response is not a list: {data}")
                return []
                
            klines = []
            for item in data:
                # 解析时间: "2023-01-01T00:00:00.000Z"
                dt_str = item.get('date')
                # 简化处理，Tiingo 返回的是 UTC 时间 ISO 格式
                # datetime.fromisoformat 在 Py3.7+ 支持，但要注意 Z 的处理
                # 这里简单处理一下 Z
                if dt_str.endswith('Z'):
                    dt_str = dt_str[:-1]
                
                dt = datetime.fromisoformat(dt_str)
                ts = int(dt.timestamp())
                
                klines.append({
                    'time': ts,
                    'open': float(item.get('open')),
                    'high': float(item.get('high')),
                    'low': float(item.get('low')),
                    'close': float(item.get('close')),
                    'volume': 0.0 # Tiingo FX 通常没有 volume
                })
            
            # 按时间排序
            klines.sort(key=lambda x: x['time'])
            
            # 过滤
            if len(klines) > limit:
                klines = klines[-limit:]
            
            # logger.info(f"获取到 {len(klines)} 条 Tiingo 外汇数据")
            return klines
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Tiingo API request failed: {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to process Tiingo data: {e}")
            return []
