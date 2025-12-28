"""
Search service.
Integrates Google Custom Search (CSE) and Bing Search API.
Configuration is provided via environment variables (see env.example) through config_loader.
"""
import requests
import json
from typing import List, Dict, Any, Optional
from app.utils.logger import get_logger
from app.utils.config_loader import load_addon_config

logger = get_logger(__name__)


class SearchService:
    """Search service."""
    
    def __init__(self):
        self._config = {}
        self._load_config()

    def _load_config(self):
        """Load config (re-read env-config on each call for local hot-reload)."""
        config = load_addon_config()
        self._config = config.get('search', {})
        self.provider = self._config.get('provider', 'google')
        self.max_results = int(self._config.get('max_results', 10))

    def search(self, query: str, num_results: int = None, date_restrict: str = None) -> List[Dict[str, Any]]:
        """
        Execute a web search.
        
        Args:
            query: Search query
            num_results: Override default max results
            date_restrict: Time restriction like 'd7' (past 7 days), Google only
            
        Returns:
            List of search results
        """
        # 重新加载配置以支持热更新
        self._load_config()
        
        limit = num_results if num_results else self.max_results
        
        if self.provider == 'bing':
            return self._search_bing(query, limit)
        else:
            return self._search_google(query, limit, date_restrict)

    def _search_google(self, query: str, num_results: int, date_restrict: str = None) -> List[Dict[str, Any]]:
        """Google Custom Search (CSE)."""
        api_key = self._config.get('google', {}).get('api_key')
        cx = self._config.get('google', {}).get('cx')
        
        if not api_key or not cx:
            logger.warning("Google Search is not configured (missing api_key or cx).")
            return []
            
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            'key': api_key,
            'cx': cx,
            'q': query,
            'num': min(num_results, 10),  # Google API 限制每次最多10条
            'gl': 'cn' if any(c in query for c in ['A股', '利好', '利空', '财报']) else None # 针对中文内容优化地区
        }
        
        # 添加时间限制参数
        if date_restrict:
            params['dateRestrict'] = date_restrict
        
        try:
            # logger.info(f"正在调用 Google Search API: q={query}, params={params}")
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # logger.info(f"Google Search 原始响应: {json.dumps(data, ensure_ascii=False)}") # 打印全部字符
            # logger.info(f"Google Search 原始响应: {json.dumps(data, ensure_ascii=False)[:500]}...") # 打印前500字符避免日志过大
            
            results = []
            if 'items' in data:
                # logger.info(f"Google Search 返回了 {len(data['items'])} 条结果")
                for item in data['items']:
                    logger.debug(f"Search Item: {item.get('title')} - {item.get('link')}")
                    results.append({
                        'title': item.get('title'),
                        'link': item.get('link'),
                        'snippet': item.get('snippet'),
                        'source': 'Google',
                        'published': item.get('pagemap', {}).get('metatags', [{}])[0].get('article:published_time', '')
                    })
            else:
                logger.warning(f"Google Search returned no 'items'. Full response: {json.dumps(data, ensure_ascii=False)}")

            return results
            
        except Exception as e:
            logger.error(f"Google search failed: {e}")
            if 'response' in locals():
                logger.error(f"Response: {response.text}")
            return []

    def _search_bing(self, query: str, num_results: int) -> List[Dict[str, Any]]:
        """Bing search."""
        api_key = self._config.get('bing', {}).get('api_key')
        
        if not api_key:
            logger.warning("Bing Search is not configured (missing api_key).")
            return []
            
        url = "https://api.bing.microsoft.com/v7.0/search"
        headers = {"Ocp-Apim-Subscription-Key": api_key}
        params = {
            "q": query,
            "count": num_results,
            "textDecorations": True,
            "textFormat": "HTML"
        }
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            results = []
            if 'webPages' in data and 'value' in data['webPages']:
                for item in data['webPages']['value']:
                    results.append({
                        'title': item.get('name'),
                        'link': item.get('url'),
                        'snippet': item.get('snippet'),
                        'source': 'Bing',
                        'published': item.get('datePublished', '')
                    })
            return results
            
        except Exception as e:
            logger.error(f"Bing search failed: {e}")
            return []

