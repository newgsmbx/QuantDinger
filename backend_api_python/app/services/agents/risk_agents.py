"""
Risk debate agents.
Includes: aggressive / neutral / conservative risk analysts.
"""
import json
from typing import Dict, Any
from .base_agent import BaseAgent
from app.services.llm import LLMService

logger = __import__('app.utils.logger', fromlist=['get_logger']).get_logger(__name__)


class RiskyAnalyst(BaseAgent):
    """Aggressive risk analyst."""
    
    def __init__(self, memory=None):
        super().__init__("RiskyAnalyst", memory)
        self.llm_service = LLMService()
    
    def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze risk from an aggressive perspective."""
        market = context.get('market')
        symbol = context.get('symbol')
        language = context.get('language', 'zh-CN')
        model = context.get('model')
        trader_plan = context.get('trader_plan', {})
        
        lang_instruction = self._get_language_instruction(language)
        system_prompt = f"""You are an Aggressive Risk Analyst. You tend to:
{lang_instruction}
1. Emphasize high return potential, even with higher risks.
2. Believe current risks are controllable and worth taking.
3. Support aggressive trading strategies.

Please return in JSON format as follows:
{{
  "argument": "Aggressive risk analysis argument...",
  "risk_assessment": "Risk controllable, high return potential",
  "recommendation": "Support trading plan"
}}"""

        user_prompt = f"""Perform aggressive risk analysis for {symbol} in {market} market.

**Trading Plan:**
{json.dumps(trader_plan, ensure_ascii=False, indent=2) if trader_plan else 'No Data'}

Please analyze risk from an aggressive perspective, emphasizing return potential."""

        result = self.llm_service.safe_call_llm(
            system_prompt,
            user_prompt,
            {"argument": "", "risk_assessment": "", "recommendation": ""},
            model=model
        )
        
        return {
            "type": "risky",
            "data": result
        }
    
    def _get_language_instruction(self, language: str) -> str:
        language_map = {
            'zh-CN': 'Answer in Simplified Chinese.',
            'zh-TW': 'Answer in Traditional Chinese.',
            'en-US': 'Answer in English.',
            'ja-JP': 'Answer in Japanese.',
            'ko-KR': 'Answer in Korean.',
            'vi-VN': 'Answer in Vietnamese.',
            'th-TH': 'Answer in Thai.',
            'ar-SA': 'Answer in Arabic.',
            'fr-FR': 'Answer in French.',
            'de-DE': 'Answer in German.'
        }
        return language_map.get(language, 'Answer in English.')


class NeutralAnalyst(BaseAgent):
    """Neutral risk analyst."""
    
    def __init__(self, memory=None):
        super().__init__("NeutralAnalyst", memory)
        self.llm_service = LLMService()
    
    def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze risk from a neutral perspective."""
        market = context.get('market')
        symbol = context.get('symbol')
        language = context.get('language', 'zh-CN')
        model = context.get('model')
        trader_plan = context.get('trader_plan', {})
        
        lang_instruction = self._get_language_instruction(language)
        system_prompt = f"""You are a Neutral Risk Analyst. You tend to:
{lang_instruction}
1. Balance risk and return.
2. Objectively evaluate various possibilities.
3. Provide neutral risk advice.

Please return in JSON format as follows:
{{
  "argument": "Neutral risk analysis argument...",
  "risk_assessment": "Balance between risk and return",
  "recommendation": "Cautiously execute trading plan"
}}"""

        user_prompt = f"""Perform neutral risk analysis for {symbol} in {market} market.

**Trading Plan:**
{json.dumps(trader_plan, ensure_ascii=False, indent=2) if trader_plan else 'No Data'}

Please analyze risk from a neutral perspective, balancing risk and return."""

        result = self.llm_service.safe_call_llm(
            system_prompt,
            user_prompt,
            {"argument": "", "risk_assessment": "", "recommendation": ""},
            model=model
        )
        
        return {
            "type": "neutral",
            "data": result
        }
    
    def _get_language_instruction(self, language: str) -> str:
        language_map = {
            'zh-CN': 'Answer in Simplified Chinese.',
            'zh-TW': 'Answer in Traditional Chinese.',
            'en-US': 'Answer in English.',
            'ja-JP': 'Answer in Japanese.',
            'ko-KR': 'Answer in Korean.',
            'vi-VN': 'Answer in Vietnamese.',
            'th-TH': 'Answer in Thai.',
            'ar-SA': 'Answer in Arabic.',
            'fr-FR': 'Answer in French.',
            'de-DE': 'Answer in German.'
        }
        return language_map.get(language, 'Answer in English.')


class SafeAnalyst(BaseAgent):
    """Conservative risk analyst."""
    
    def __init__(self, memory=None):
        super().__init__("SafeAnalyst", memory)
        self.llm_service = LLMService()
    
    def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze risk from a conservative perspective."""
        market = context.get('market')
        symbol = context.get('symbol')
        language = context.get('language', 'zh-CN')
        model = context.get('model')
        trader_plan = context.get('trader_plan', {})
        risk_report = context.get('risk_report', {})
        
        lang_instruction = self._get_language_instruction(language)
        system_prompt = f"""You are a Conservative Risk Analyst. You tend to:
{lang_instruction}
1. Emphasize risk control, prioritizing capital protection.
2. Identify potential risk points.
3. Suggest cautious or conservative trading strategies.

Please return in JSON format as follows:
{{
  "argument": "Conservative risk analysis argument...",
  "risk_assessment": "High risk exists, suggest caution",
  "recommendation": "Suggest reducing position or suspending trading"
}}"""

        user_prompt = f"""Perform conservative risk analysis for {symbol} in {market} market.

**Trading Plan:**
{json.dumps(trader_plan, ensure_ascii=False, indent=2) if trader_plan else 'No Data'}

**Risk Analysis Report:**
{json.dumps(risk_report.get('data', {}), ensure_ascii=False, indent=2) if risk_report else 'No Data'}

Please analyze risk from a conservative perspective, emphasizing risk control."""

        result = self.llm_service.safe_call_llm(
            system_prompt,
            user_prompt,
            {"argument": "", "risk_assessment": "", "recommendation": ""},
            model=model
        )
        
        return {
            "type": "safe",
            "data": result
        }
    
    def _get_language_instruction(self, language: str) -> str:
        language_map = {
            'zh-CN': 'Answer in Simplified Chinese.',
            'zh-TW': 'Answer in Traditional Chinese.',
            'en-US': 'Answer in English.',
            'ja-JP': 'Answer in Japanese.',
            'ko-KR': 'Answer in Korean.',
            'vi-VN': 'Answer in Vietnamese.',
            'th-TH': 'Answer in Thai.',
            'ar-SA': 'Answer in Arabic.',
            'fr-FR': 'Answer in French.',
            'de-DE': 'Answer in German.'
        }
        return language_map.get(language, 'Answer in English.')
