"""
K线数据服务
"""
from typing import Dict, List, Any, Optional

from app.data_sources import DataSourceFactory
from app.utils.cache import CacheManager
from app.utils.logger import get_logger
from app.config import CacheConfig

logger = get_logger(__name__)


class KlineService:
    """K线数据服务"""
    
    def __init__(self):
        self.cache = CacheManager()
        self.cache_ttl = CacheConfig.KLINE_CACHE_TTL
    
    def get_kline(
        self,
        market: str,
        symbol: str,
        timeframe: str,
        limit: int = 300,
        before_time: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取K线数据
        
        Args:
            market: 市场类型 (Crypto, USStock, AShare, HShare, Forex, Futures)
            symbol: 交易对/股票代码
            timeframe: 时间周期
            limit: 数据条数
            before_time: 获取此时间之前的数据
            
        Returns:
            K线数据列表
        """
        # 构建缓存键（历史数据不缓存）
        if not before_time:
            cache_key = f"kline:{market}:{symbol}:{timeframe}:{limit}"
            cached = self.cache.get(cache_key)
            if cached:
                # logger.info(f"命中缓存: {cache_key}")
                return cached
        
        # 获取数据
        klines = DataSourceFactory.get_kline(
            market=market,
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            before_time=before_time
        )
        
        # 设置缓存（仅最新数据）
        if klines and not before_time:
            ttl = self.cache_ttl.get(timeframe, 300)
            self.cache.set(cache_key, klines, ttl)
            # logger.info(f"缓存设置: {cache_key}, TTL: {ttl}s")
        
        return klines
    
    def get_latest_price(self, market: str, symbol: str) -> Optional[Dict[str, Any]]:
        """获取最新价格"""
        klines = self.get_kline(market, symbol, '1m', 1)
        if klines:
            return klines[-1]
        return None

