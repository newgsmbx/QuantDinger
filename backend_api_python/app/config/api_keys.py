"""
API key configuration.
All third-party keys should be provided via environment variables (recommended: backend_api_python/.env).
"""
import os

class MetaAPIKeys(type):
    """API Keys 元类，用于支持类属性的动态获取"""
    
    @property
    def FINNHUB_API_KEY(cls):
        from app.utils.config_loader import load_addon_config
        val = load_addon_config().get('finnhub', {}).get('api_key')
        return val if val else os.getenv('FINNHUB_API_KEY', '')
    
    @property
    def TIINGO_API_KEY(cls):
        from app.utils.config_loader import load_addon_config
        val = load_addon_config().get('tiingo', {}).get('api_key')
        return val if val else os.getenv('TIINGO_API_KEY', '')
    
    @property
    def OPENROUTER_API_KEY(cls):
        from app.utils.config_loader import load_addon_config
        val = load_addon_config().get('openrouter', {}).get('api_key')
        return val if val else os.getenv('OPENROUTER_API_KEY', '')


class APIKeys(metaclass=MetaAPIKeys):
    """API 密钥配置类"""
    
    @classmethod
    def get(cls, key_name: str, default: str = '') -> str:
        """获取 API 密钥"""
        # 尝试从类属性获取
        if hasattr(cls, key_name):
            return getattr(cls, key_name)
        return default
    
    @classmethod
    def is_configured(cls, key_name: str) -> bool:
        """检查 API 密钥是否已配置"""
        value = cls.get(key_name)
        return bool(value and value.strip())
