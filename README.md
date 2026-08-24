#财报季 Surprise / 暴雷猎手 Agent / Earnings Surprise Hunter Agent

## 项目概述 / Overview

财报季超预期/暴雷检测 Agent。获取财报预告、分析师一致预期、审计意见三路数据，
计算偏离度并生成分析报告，支持 A 股、港股、美股。

Earnings season surprise/blowup detection agent. Fetches earnings forecasts, analyst consensus,
and audit opinions from three data sources, calculates deviation and generates analysis reports.
Supports A-shares, HK stocks, and US stocks.

## 核心功能 / Core Features

- **财报预告获取 / Earnings Forecast** — 净利润区间、同比增长
- **一致预期分析 / Consensus Analysis** — 分析师净利润/EPS/数量
- **审计意见扫描 / Audit Opinion** — 颜色码标记风险等级
- **偏离度计算 / Surprise Calculation** — 预告 vs 一致预期
- **多市场支持 / Multi-market** — A 股(.SH/.SZ)、港股(.HK)、美股

## 数据接口 / Data APIs

| 函数 | 说明 | PandaData API |
|------|------|---------------|
| `fetch_earnings_forecast` | 财报预告 / Earnings forecast | `get_fina_forecast` |
| `fetch_consensus` | 一致预期 / Analyst consensus | `get_stock_ncycl_consensus` |
| `fetch_audit_opinion` | 审计意见 / Audit opinion | `get_audit_opinion` |
| `calculate_surprise` | 偏离度计算 / Deviation calculation | — |
| `analyze_surprise` | 综合分析 / Comprehensive analysis | — |

## 关键文件 / Key Files

| 文件 | 说明 |
|------|------|
| `agent-earnings-surprise-hunter.py` | 核心引擎 / Core engine |
| `selfcheck_earnings_surprise_hunter.py` | 离线自检（37 项断言）/ Offline self-check (37 assertions) |
| `SAMPLE_OUTPUT.md` | 标准样例输出 / Standard sample output |
| `SKILL.md` | 技能定义 / Skill definition |
| `credential_encryptor.py` | 凭据加密 / Credential encryption |
| `requirements.txt` | 依赖清单 / Dependencies |

## 快速开始 / Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env   # 填入凭据 / Fill in credentials
python agent-earnings-surprise-hunter.py
```

## 自检（离线）/ Self-check (Offline)

```bash
python selfcheck_earnings_surprise_hunter.py          # 37 项断言 / 37 assertions
python selfcheck_earnings_surprise_hunter.py --emit   # 打印标准样例 / Print sample report
```

覆盖：纯函数、偏离度计算边界、端到端三路数据汇聚、Surprise × Audit 组合矩阵。
Coverage: pure functions, deviation calculation boundaries, end-to-end three-source aggregation,
Surprise × Audit combination matrix.

## 输出格式 / Output Format

```
## Earnings Surprise Report: 000001.SZ
### [UP] Beat Expectations (15.3%)
- Forecast: 125.5 vs Consensus: 108.8
### Audit Opinion [CLEAN]
- Opinion: Standard unqualified
- Auditor: Ernst & Young
```

## 风险等级 / Risk Levels

- **[CLEAN]** — 标准无保留意见 / Standard unqualified
- **[WARN]** — 带强调事项段 / Qualified with emphasis
- **[RISK]** — 保留/否定意见 / Qualified/adverse

## Surprise 方向 / Surprise Direction

- **[UP]** — 超预期（≥10%）· Beat expectations
- **[DOWN]** — 不及预期（≤-10%）· Miss expectations
- **[NEUTRAL]** — 符合预期 · In line

## 依赖 / Requirements

- Python 3.10+
- OpenAI API Key (DeepSeek)
- PandaData Account
