"""
智能体记忆系统
使用 SQLite + 简单的文本相似度匹配
"""
import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import difflib

from app.utils.logger import get_logger

logger = get_logger(__name__)


class AgentMemory:
    """智能体记忆系统"""
    
    def __init__(self, agent_name: str, db_path: Optional[str] = None):
        """
        初始化记忆系统
        
        Args:
            agent_name: 智能体名称
            db_path: 数据库路径（可选）
        """
        self.agent_name = agent_name
        
        if db_path is None:
            # 默认数据库路径
            db_dir = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'data', 'memory')
            os.makedirs(db_dir, exist_ok=True)
            db_path = os.path.join(db_dir, f'{agent_name}_memory.db')
        
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    situation TEXT NOT NULL,
                    recommendation TEXT NOT NULL,
                    result TEXT,
                    returns REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_created_at ON memories(created_at)
            ''')
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"初始化记忆数据库失败: {e}")
    
    def add_memory(self, situation: str, recommendation: str, result: Optional[str] = None, returns: Optional[float] = None):
        """
        添加记忆
        
        Args:
            situation: 情况描述
            recommendation: 建议/决策
            result: 结果描述（可选）
            returns: 收益（可选）
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO memories (situation, recommendation, result, returns)
                VALUES (?, ?, ?, ?)
            ''', (situation, recommendation, result, returns))
            
            conn.commit()
            conn.close()
            logger.info(f"{self.agent_name} 添加新记忆")
        except Exception as e:
            logger.error(f"添加记忆失败: {e}")
    
    def get_memories(self, current_situation: str, n_matches: int = 2) -> List[Dict[str, Any]]:
        """
        检索相似记忆
        
        Args:
            current_situation: 当前情况描述
            n_matches: 返回的匹配数量
            
        Returns:
            匹配的记忆列表
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取所有记忆
            cursor.execute('''
                SELECT id, situation, recommendation, result, returns, created_at
                FROM memories
                ORDER BY created_at DESC
                LIMIT 100
            ''')
            
            all_memories = cursor.fetchall()
            conn.close()
            
            if not all_memories:
                return []
            
            # 计算相似度
            scored_memories = []
            for mem in all_memories:
                mem_id, situation, recommendation, result, returns, created_at = mem
                
                # 使用简单的文本相似度
                similarity = difflib.SequenceMatcher(
                    None,
                    current_situation.lower(),
                    situation.lower()
                ).ratio()
                
                scored_memories.append({
                    'id': mem_id,
                    'matched_situation': situation,
                    'recommendation': recommendation,
                    'result': result,
                    'returns': returns,
                    'similarity_score': similarity,
                    'created_at': created_at
                })
            
            # 按相似度排序
            scored_memories.sort(key=lambda x: x['similarity_score'], reverse=True)
            
            # 返回前 n_matches 个
            return scored_memories[:n_matches]
            
        except Exception as e:
            logger.error(f"检索记忆失败: {e}")
            return []
    
    def update_memory_result(self, memory_id: int, result: str, returns: Optional[float] = None):
        """
        更新记忆的结果
        
        Args:
            memory_id: 记忆ID
            result: 结果描述
            returns: 收益
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE memories
                SET result = ?, returns = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (result, returns, memory_id))
            
            conn.commit()
            conn.close()
            logger.info(f"{self.agent_name} 更新记忆 {memory_id}")
        except Exception as e:
            logger.error(f"更新记忆失败: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM memories')
            total = cursor.fetchone()[0]
            
            cursor.execute('SELECT AVG(returns) FROM memories WHERE returns IS NOT NULL')
            avg_returns = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT COUNT(*) FROM memories WHERE returns > 0')
            positive = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total_memories': total,
                'average_returns': round(avg_returns, 2),
                'positive_decisions': positive,
                'success_rate': round(positive / total * 100, 2) if total > 0 else 0
            }
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
