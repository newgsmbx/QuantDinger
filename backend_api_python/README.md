# QuantDinger Python API Server

Python 后端服务，提供金融数据获取、技术指标分析、AI 智能体分析和回测功能。

## 项目结构

```
backend_api_python/
├── app/                          # 应用主目录
│   ├── __init__.py              # Flask 应用工厂
│   ├── config/                  # 配置模块 ⭐ (支持数据库动态配置)
│   │   ├── __init__.py          # 配置统一导出
│   │   ├── settings.py          # 服务配置
│   │   ├── api_keys.py          # API 密钥集中管理
│   │   ├── database.py          # 数据库/Redis/缓存配置
│   │   └── data_sources.py      # 数据源配置
│   ├── data_sources/            # 数据源模块
│   │   ├── base.py              # 数据源基类
│   │   ├── factory.py           # 数据源工厂
│   │   ├── crypto.py            # 加密货币 (CCXT)
│   │   ├── us_stock.py          # 美股 (yfinance/Finnhub)
│   │   ├── cn_stock.py          # A股/港股 (yfinance/akshare)
│   │   └── futures.py           # 期货数据源
│   ├── services/                # 业务服务层
│   │   ├── agents/              # AI 智能体系统 (多智能体架构) ⭐
│   │   │   ├── coordinator.py   # 智能体协调器
│   │   │   ├── tools.py         # 智能体工具集 (含搜索/数据获取)
│   │   │   ├── analyst_agents.py # 各类分析师 (技术/基本面/新闻等)
│   │   │   └── researcher_agents.py # 研究员 (多空辩论)
│   │   ├── kline.py             # K线数据服务
│   │   ├── search.py            # 搜索服务 (Google/Bing)
│   │   ├── llm.py               # LLM 调用封装 (OpenRouter)
│   │   └── analysis.py          # 分析服务入口
│   ├── routes/                  # API 路由
│   │   ├── health.py            # 健康检查
│   │   ├── kline.py             # K线数据 API
│   │   ├── analysis.py          # AI 分析 API
│   │   └── market.py            # 市场数据 API
│   └── utils/                   # 工具模块
│       ├── config_loader.py     # 数据库配置加载器
│       ├── logger.py            # 日志工具
│       └── http.py              # HTTP 请求
├── run.py                       # 入口文件 ⭐
├── gunicorn_config.py           # Gunicorn 配置
├── requirements.txt             # 依赖列表
├── start.sh                     # 启动脚本
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 数据库配置

本系统依赖 MySQL 数据库中的 `qd_addon_config` 表进行配置管理。请确保导入 `update_config_search.sql` 等 SQL 文件以初始化配置。

### 3. 启动服务

**开发环境：**
```bash
python run.py
```

**生产环境（使用 Gunicorn）：**
```bash
gunicorn -c gunicorn_config.py "run:app"
```

服务将在 `http://localhost:5000` 启动

## 主要功能

### 1. 多维度 AI 分析
基于多智能体架构 (Multi-Agent Architecture)，模拟真实投研团队：
- **市场分析师**: 技术面分析 (K线, MACD, RSI, 均线)
- **基本面分析师**: 公司财务、估值、行业地位
- **新闻分析师**: 实时新闻、舆情分析 (集成 Finnhub + Google/Bing 搜索)
- **情绪分析师**: 市场情绪评估
- **风险分析师**: 波动率、流动性风险评估
- **多空辩论**: 模拟看涨/看跌研究员辩论，提供平衡观点

### 2. 数据获取增强
- **美股**: 实时行情 (Finnhub/yfinance) + 深度公司资料
- **加密货币**: 实时行情 (CCXT/Binance) + 项目资讯搜索
- **A股/港股**: 延迟行情 + 网络资讯搜索补充

### 3. 智能搜索集成
支持 Google Custom Search 和 Bing Search，自动补全传统数据源缺失的信息（如公司简介、最新突发新闻）。

## API 接口

### 健康检查
```
GET /health
```

### K线数据
```
GET /api/indicator/kline
参数: market (Crypto/USStock/AShare), symbol, timeframe, limit
```

### AI 多维度分析
```
POST /api/analysis/multi
{
    "market": "USStock",
    "symbol": "NVDA",
    "language": "zh-CN"
}
```

## 配置说明

系统配置采用 **数据库 + 环境变量** 混合模式，支持热更新。

### 核心环境变量 (启动参数)
| 变量名 | 说明 |
|--------|------|
| PYTHON_API_HOST | 监听地址 |
| PYTHON_API_PORT | 监听端口 |
| MYSQL_HOST | MySQL 主机 |
| REDIS_HOST | Redis 主机 |

### 数据库配置 (`qd_addon_config` 表)
大部分业务配置已迁移至数据库，支持动态调整：
- **API Keys**: Finnhub, Google Search, Bing Search
- **AI 模型**: OpenRouter 模型选择
- **系统参数**: 超时时间、重试次数、缓存策略

## License
This project is released under the Apache License 2.0.
See the repository root `LICENSE` for details.
