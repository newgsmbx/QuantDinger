# 多智能体分析系统

基于 TradingAgents 架构优化的多智能体股票分析系统。

## 架构特点

### 1. 多智能体协作
- **分析师团队**：市场分析师、基本面分析师、新闻分析师、情绪分析师、风险分析师
- **研究团队**：看涨研究员、看跌研究员
- **交易团队**：交易员、风险分析师（激进/中性/保守）

### 2. 工作流程
```
分析师团队分析 → 研究辩论 → 交易员决策 → 风险辩论 → 最终决策
```

### 3. 记忆系统
- 使用 SQLite 存储历史决策
- 基于文本相似度检索历史经验
- 支持从交易结果中学习

### 4. 工具调用
- 智能体可以主动获取数据
- 支持多数据源（yfinance, finnhub, ccxt, 腾讯接口）

## 使用方法

### 基本使用

```python
from app.services.analysis import AnalysisService

# 使用多智能体架构（默认）
service = AnalysisService(use_multi_agent=True)
result = service.analyze("USStock", "AAPL", "zh-CN")

# 使用传统架构（向后兼容）
service = AnalysisService(use_multi_agent=False)
result = service.analyze("USStock", "AAPL", "zh-CN")
```

### 环境变量配置

在 `.env` 文件中设置：

```bash
# 是否启用多智能体架构（默认：True）
USE_MULTI_AGENT=True

# 最大辩论轮数（默认：2）
MAX_DEBATE_ROUNDS=2
```

### 反思学习

```python
from app.services.analysis import reflect_analysis

# 从交易结果中学习
reflect_analysis(
    market="USStock",
    symbol="AAPL",
    decision="BUY",
    returns=1000.0,  # 收益
    result="交易成功，收益 10%"
)
```

## 智能体说明

### 分析师智能体

- **MarketAnalyst**: 技术分析，计算技术指标
- **FundamentalAnalyst**: 基本面分析，财务数据
- **NewsAnalyst**: 新闻事件分析
- **SentimentAnalyst**: 市场情绪分析
- **RiskAnalyst**: 风险评估

### 研究员智能体

- **BullResearcher**: 构建看涨论据
- **BearResearcher**: 构建看跌论据

### 交易员智能体

- **TraderAgent**: 综合所有分析，做出交易决策

### 风险分析师智能体

- **RiskyAnalyst**: 激进风险分析
- **NeutralAnalyst**: 中性风险分析
- **SafeAnalyst**: 保守风险分析

## 返回结果格式

多智能体模式返回的完整结果包括：

```json
{
  "overview": {
    "overallScore": 75,
    "recommendation": "BUY",
    "confidence": 82,
    "dimensionScores": {...},
    "report": "..."
  },
  "fundamental": {...},
  "technical": {...},
  "news": {...},
  "sentiment": {...},
  "risk": {...},
  "debate": {
    "bull": {...},
    "bear": {...},
    "research_decision": "..."
  },
  "trader_decision": {
    "decision": "BUY",
    "confidence": 85,
    "trading_plan": {...}
  },
  "risk_debate": {
    "risky": {...},
    "neutral": {...},
    "safe": {...}
  },
  "final_decision": {
    "decision": "BUY",
    "confidence": 85,
    "reasoning": "..."
  }
}
```

## 优势

1. **多角度分析**：多个智能体从不同角度分析，减少盲点
2. **辩论机制**：看涨/看跌辩论，发现潜在问题
3. **风险控制**：多维度风险分析，提高决策质量
4. **持续学习**：记忆系统支持从历史经验中学习
5. **向后兼容**：可以切换到传统模式

## 注意事项

1. 多智能体模式会产生更多的 API 调用，成本较高
2. 分析时间会比传统模式长
3. 记忆系统需要 SQLite 数据库支持
4. 建议在生产环境中根据需求选择合适的模式
