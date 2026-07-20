# Agent-Earnings-Surprise-Hunter

财报季 Surprise / 暴雷猎手 Agent

## Features

- **Earnings Forecast** - 获取财报预告数据（净利润区间、同比增长）
- **Consensus Analysis** - 获取分析师一致预期（净利润、EPS、分析师数量）
- **Audit Opinion** - 审计意见扫描与颜色码标记
- **Surprise Calculation** - 预告 vs 一致预期偏离度计算
- **Multi-market Support** - 支持 A股(.SH/.SZ)、港股(.HK)、美股

## Usage

```bash
# 安装依赖
pip install -r requirements.txt

# 创建配置文件
cp .env.example .env
# 编辑 .env 填入真实凭据

# 运行
python agent-earnings-surprise-hunter.py
```

## API Endpoints

| Function | Description | PandaData API |
|----------|-------------|---------------|
| `fetch_earnings_forecast` | 获取财报预告 | `get_fina_forecast` |
| `fetch_consensus` | 获取一致预期 | `get_stock_ncycl_consensus` |
| `fetch_audit_opinion` | 获取审计意见 | `get_audit_opinion` |

## Output Format

```
## Earnings Surprise Report: 000001.SZ

### [UP] Beat Expectations (15.3%)
- Forecast: 125.5 vs Consensus: 108.8

### Audit Opinion [CLEAN]
- Opinion: Standard unqualified
- Auditor: Ernst & Young
```

## Risk Levels

- **[CLEAN]** - 标准无保留意见
- **[WARN]** - 带强调事项段的无保留意见
- **[RISK]** - 保留/否定意见

## Surprise Direction

- **[UP]** - 超预期 (≥10%)
- **[DOWN]** - 不及预期 (≤-10%)
- **[NEUTRAL]** - 符合预期

## Requirements

- Python 3.10+
- OpenAI API Key
- PandaData Account