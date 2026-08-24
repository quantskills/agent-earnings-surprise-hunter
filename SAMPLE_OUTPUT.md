# 标准样例输出 (Standard Sample Output)

本文件包含两部分：
- **A. 离线自检样例** —— `selfcheck_earnings_surprise_hunter.py` 在固定样例（fixtures）下的输出，无需凭据、可复现。
- **B. 真实运行样例** —— 连接 PandaData + DeepSeek 真实接口跑通的结果（2026-08-05）。

两者共同证明三路数据 —— **财报预告 (Forecast)**、**分析师一致预期 (Consensus)**、**审计意见 (Audit Opinion)**
—— 能够正确汇聚为一份完整的 Agent 分析结果。

---

## A. 离线自检样例

本部分是 `selfcheck_earnings_surprise_hunter.py` 在**离线固定样例**（offline fixtures）下的标准输出。

- 生成命令：`python selfcheck_earnings_surprise_hunter.py --emit`
- 数据来源：脚本内置 `FIXTURES`（无需 PandaData / OpenAI 凭据）
- 自检结果：`37/37 通过, 0 失败`

样例覆盖三种典型组合（Surprise × Audit）：

| 股票代码 | Surprise 方向 | 审计意见等级 | 场景含义 |
|----------|---------------|--------------|----------|
| 000001.SZ | `[UP]` beat (+15.35%) | `[CLEAN]` 无保留 | 超预期 + 干净意见 |
| 600519.SH | `[DOWN]` miss (-15.0%) | `[WARN]` 强调事项 | 不及预期 + 需关注 |
| 002594.SZ | `[NEUTRAL]` inline (+4.0%) | `[RISK]` 保留意见 | 符合预期 + 暴雷风险 |

---

## 完整报告

### [Input] Analyze earnings surprise for 000001.SZ

```
## Earnings Surprise Report: 000001.SZ

### [UP] Beat Expectations (15.35%)
- Forecast: 125.5 vs Consensus: 108.8

### Forecast
- Quarter: 2026q2
- Type: 预增
- Update Date: 2026-07-15

### Consensus
- Net Profit: 108.8
- EPS: 1.85
- Analysts: 18

### Audit Opinion [CLEAN]
- Opinion: 标准无保留意见
- Auditor: 安永华明会计师事务所
```

### [Input] Analyze earnings surprise for 600519.SH

```
## Earnings Surprise Report: 600519.SH

### [DOWN] Miss Expectations (-15.0%)
- Forecast: 85.0 vs Consensus: 100.0

### Forecast
- Quarter: 2026q2
- Type: 预减
- Update Date: 2026-07-14

### Consensus
- Net Profit: 100.0
- EPS: 2.1
- Analysts: 25

### Audit Opinion [WARN]
- Opinion: 带强调事项段的无保留意见
- Auditor: 普华永道中天会计师事务所
```

### [Input] Analyze earnings surprise for 002594.SZ

```
## Earnings Surprise Report: 002594.SZ

### [NEUTRAL] Inline (4.0%)
- Forecast: 52.0 vs Consensus: 50.0

### Forecast
- Quarter: 2026q2
- Type: 略增
- Update Date: 2026-07-16

### Consensus
- Net Profit: 50.0
- EPS: 0.95
- Analysts: 12

### Audit Opinion [RISK]
- Opinion: 保留意见
- Auditor: 立信会计师事务所
```

---

## 完整结果的判定标准

一份**完整的 Agent 结果**必须同时包含以下四要素，缺一不可（由自检脚本第 [3] 组用例断言）：

1. **Forecast 章节** —— 来自 `fetch_earnings_forecast`（预告净利润区间、类型、更新日期）
2. **Consensus 章节** —— 来自 `fetch_consensus`（一致预期净利润、EPS、分析师数量）
3. **Audit Opinion 章节** —— 来自 `fetch_audit_opinion`（意见文本、风险等级、审计机构）
4. **Surprise 判定** —— 由 `calculate_surprise` 基于 Forecast 与 Consensus 计算得出（beat/miss/inline）

上述三路取数结果经 `analyze_surprise` 汇聚、`generate_report` 渲染后，形成结构完整、可审阅的报告。

---

## B. 真实运行样例（PandaData + DeepSeek，2026-08-06 优化后）

命令：`python agent-earnings-surprise-hunter.py`（读取 `.env` 真实凭据）。数据均来自 PandaData 真实接口，
分析文字由 DeepSeek 基于 `generate_report` 的结构化报告生成。

### 各市场数据可得性（真实接口能力）

| 数据源 | 接口 | 市场适用性 |
|--------|------|-----------|
| 业绩预告 | `get_fina_forecast` | **A 股专用**；`info_date` 为精确发布日（`symbol`/`end_quarter` 直查均返回空，实测），故按最近 90 天内的**交易日**逐日扫描并按 symbol 过滤（用 `get_trade_cal` 过滤周末/节假日，减少约 30% 无效请求） |
| 一致预期 | `get_stock_ncycl_consensus` | **港股专用**（指标口径：目标价 TP、长期增长 LTGROWTH 等），A/美股友好降级 |
| 财务快报 | `get_fina_performance` | **A 股专用**；提供归母净利润、YoY、EPS、营收等**真实业绩**。实测该接口对 `info_date`/`end_quarter` 过滤不敏感，仅按 symbol 返回覆盖到的一条快报，故作为「补充事实信息」并在报告期与预告一致时供 surprise 计算 |
| 审计意见 | `get_audit_opinion` | **A 股专用**；一次 `start_quarter`~`end_quarter` 范围查询，取最近财报审计（financial_statements）的有效意见 |

> 关键结论：一致预期为港股专用，没有任何单一标的能四路全满。**A 股可同时得到「预告 + 财务快报 + 审计意见」三路真实数据**，港股可得「一致预期」，这已构成完整的 Agent 结果。

### 本轮优化要点（依据 PandaData 说明书反复精读）

1. **预告扫描走交易日历**：`get_scan_trade_dates` 用 `get_trade_cal(is_trading_day=1)` 只扫交易日，不可用时回退自然日，兼顾提速与健壮性。
2. **新增财务快报真实业绩段**：`fetch_actual_results` 拿真实归母净利润/YoY/EPS/营收，A 股链路不再只能降级为 unknown。
3. **Surprise 报告期分级基准**（关键）：无一致预期时用财务快报净利作基准——报告期**完全一致**→直接比（`quality=exact`，高可信）；报告期**累计口径可年化对齐**（如预告半年 vs 快报全年）→按累计月数年化归一后近似比较（`quality=approx_annualized`，标注 APPROX + 归一过程）；**完全不可比**→不计 surprise，但把快报净利作为「参考基准」展示。既能真正算出 beat/miss，又不制造跨期假指标。
4. **审计意见单次范围查询**：以 `start_quarter`~`end_quarter` 一次拉取，替代逐季循环，降低限流风险（参见「常见问题」500010 每分钟请求次数超限）。

### 真实结果摘要

| 标的 | 预告 (Forecast) | 财务快报 (Actual) | Surprise 判定 | 审计意见 (Audit) |
|------|-----------------|-------------------|---------------|------------------|
| **688012.SH** | ✅ 预增，净利 27~29 亿（H1 2026, 20260630） | ✅ 真实归母净利 21.1 亿（FY2025, 20251231） | ✅ **`[UP]` Beat +165.22%**（快报年化到半年口径 10.56 亿为基准，APPROX 近似） | 近 8 季无审计记录 |
| **600889.SH** 南京化纤 | 近 90 天无预告 | ✅ 真实归母净利 4.72 亿（FY2015） | ⚪ 无预告故不计算，快报净利作参考基准展示 | ✅ 无保留意见 `[CLEAN]`，天职国际 |
| **0700.HK** 腾讯 | 港股无此预告接口 | A 股专用，不适用 | ⚪ 用港股一致预期路径（TP 692.59/46 家、LTGROWTH 7.855%/4 家） | A 股专用，不适用 |

### 真实报告示例：688012.SH（预告 + 快报 → 真正算出 Surprise）

`generate_report` 结构化输出（送入 LLM 前）：

```
## Earnings Surprise Report: 688012.SH

### [UP] Beat Expectations (165.22%)
- Forecast: 2800000000.0 vs Actual (annualized): 1055736500.0
- Confidence: APPROX (cross-period, annualized comparison)
- Note: actual np 2111473000 (20251231, 12M) annualized to forecast period 20260630 (6M) as 1055736500

### Forecast
- Quarter: 20260630
- Type: 预增
- Description: 累计利润
- Net Profit Range: 2700000000.0 ~ 2900000000.0
- Growth Rate (%): 282.48 ~ 310.81
- Update Date: 20260804

### Consensus
- consensus API is HK-only, not applicable for cn (688012.SH)

### Actual Results (Express Report)
- Report Date: 20251231
- Net Profit (parent): 2111473000.0
- Net Profit YoY (%): 30.69
- Basic EPS: 3.4
- Operating Revenue: 12384638300.0

### Audit Opinion
- No audit data
```

> 关键：预告 H1 2026（半年）净利中值 28 亿，快报 FY2025（全年）净利 21.1 亿。按累计月数把全年净利年化到半年口径（21.1 × 6/12 ≈ 10.56 亿）作为基准，
> 得出 deviation ≈ +165%，判定 **Beat**，并明确标注为跨期年化近似（APPROX）。这样既补上了 A 股一致预期缺口、真正算出 surprise，又不会把「半年」硬比「全年」造成假指标。

> 本次真实运行 A 股（预告+快报+审计）与港股一致预期均命中 PandaData，DeepSeek 三次调用均返回 200。

