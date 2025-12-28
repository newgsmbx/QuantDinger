"""
智能体基类
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BaseAgent(ABC):
    """智能体基类，所有分析智能体都继承此类"""
    
    def __init__(self, name: str, memory: Optional[Any] = None):
        """
        初始化智能体
        
        Args:
            name: 智能体名称
            memory: 记忆系统实例（可选）
        """
        self.name = name
        self.memory = memory
        self.logger = get_logger(f"{__name__}.{name}")
    
    @abstractmethod
    def analyze(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行分析任务
        
        Args:
            context: 分析上下文，包含市场、代码、基础数据等
            
        Returns:
            分析结果字典
        """
        pass
    
    def get_memories(self, situation: str, n_matches: int = 2) -> List[Dict[str, Any]]:
        """
        从记忆中检索相似情况
        
        Args:
            situation: 当前情况描述
            n_matches: 返回的匹配数量
            
        Returns:
            匹配的历史记录列表
        """
        if self.memory:
            return self.memory.get_memories(situation, n_matches=n_matches)
        return []
    
    def format_memories_for_prompt(self, memories: List[Dict[str, Any]]) -> str:
        """
        格式化记忆为提示词
        
        Args:
            memories: 记忆列表
            
        Returns:
            格式化的字符串
        """
        if not memories:
            return "无历史经验可参考。"
        
        formatted = "历史经验参考：\n"
        for i, mem in enumerate(memories, 1):
            formatted += f"{i}. {mem.get('recommendation', 'N/A')}\n"
        
        return formatted
