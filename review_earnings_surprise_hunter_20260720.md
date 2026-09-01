# 审查报告：agent-earnings-surprise-hunter

**审查日期**：2026-07-20  
**审查对象**：E:\agent开发集\agent-earnings-surprise-hunter

---

## 一、总体结论

**❌ 不通过——存在 3 个 P0 + 4 个 P1 + 3 个 P2**

该 agent 为单文件脚本，功能是获取A股财报预告/一致预期/审计意见，计算业绩惊喜（beat/miss/inline），再用 LLM 生成分析报告。整体思路清晰，但代码质量粗糙，存在多个阻断性问题。

---

## 二、P0 问题（阻断性）

### P0-1：.env 明文泄露 API Key 和密码

**位置**：`.env` 文件  
**现状**：
```
OPENAI_API_KEY=<redacted>
PANDA_DATA_USERNAME=13812345678
PANDA_DATA_PASSWORD=panda123
```
**问题**：真实 API Key 和 PandaData 账密明文存储。如果该仓库上传到 GitHub，密钥直接泄露。  
**修复**：`.env` 加入 `.gitignore`，仓库只保留 `.env.example` 模板。当前 key 应立即轮换。

### P0-2：缺少 SKILL.md / AGENT.md 等说明文件

**现状**：整个项目只有 `agent-earnings-surprise-hunter.py` 和 `.env`，没有任何说明文档  
**问题**：不符合 quantskills 组织仓库规范。缺 SKILL.md（或 AGENT.md）、README、LICENSE  
**修复**：补齐标准模板文件

### P0-3：`get_fina_forecast` 接口不存在

**位置**：`fetch_earnings_forecast()` 函数  
**现状**：调用 `panda_data.get_fina_forecast(symbol, start_quarter=..., end_quarter=..., market=...)`  
**问题**：根据此前对 panda_data SDK 的探测（v0.0.9），`get_fina_forecast` 接口**不存在**。可用的财报接口是 `get_fina_reports`（获取实际财报）和 `get_fina_indicator`（财务指标）。业绩预告接口需确认 SDK 版本是否支持。  
**影响**：agent 核心功能（获取业绩预告）直接失效，`fetch_earnings_forecast` 会抛异常被 except 捕获，返回 no_data

---

## 三、P1 问题（需修复）

### P1-1：`get_stock_ncycl_consensus` 接口未验证

**位置**：`fetch_consensus()` 函数  
**现状**：调用 `panda_data.get_stock_ncycl_consensus(symbol)`，无 market 参数  
**问题**：此前 SDK 探测未确认此接口存在。如果不存在，一致预期数据全部为空，惊喜计算无法执行  
**修复**：探测 SDK 确认接口名和参数，或改用其他一致预期数据源

### P1-2：正则匹配遗漏港股和美股

**位置**：`chat_with_agent()` 函数  
**现状**：
```python
match = re.search(r'([\d]{6}\.[SH|HK])', query)
```
**问题**：
- `[SH|HK]` 是字符集，匹配 S/H/K 任意一个字符，不是"SH或HK"
- 港股代码格式是 `00700.HK`（5位数字），`\d{6}` 要求6位数字，港股匹配不到
- 美股完全没有匹配逻辑（代码格式如 `AAPL`）
- 深圳股票 `.SZ` 也没有匹配到

**修复**：
```python
match = re.search(r'(\d{6}\.(SH|SZ)|\d{5}\.HK|[A-Z]+)', query)
```

### P1-3：惊喜计算逻辑有缺陷

**位置**：`calculate_surprise()` 函数  
**现状**：
```python
f_mid = (f_min + f_max) / 2 if f_min and f_max else (f_min or f_max)
```
**问题**：
- `if f_min and f_max` 当任一为 0 时判定为 False，0 是合法的净利润值
- `f_min or f_max` 当 f_min=0 时会取 f_max，逻辑错误
- 没有处理 f_min 和 f_max 符号相反的情况（一个正一个负，中点可能无意义）

**修复**：用 `is not None` 判空，不用 `if x` 真值判断

### P1-4：PandaData 初始化在模块顶层，import 即触发

**位置**：文件第 22-28 行  
**现状**：
```python
try:
    panda_data.init_token(...)
    PANDA_DATA_AVAILABLE = True
except Exception:
    PANDA_DATA_AVAILABLE = False
```
**问题**：
- 模块 import 时就执行登录，如果密码错误会在 import 阶段静默失败
- 无法在运行时切换账号
- 单元测试 import 该模块会触发真实 API 调用

**修复**：将初始化移到函数内部，或提供 `init()` 函数显式调用

---

## 四、P2 问题（建议优化）

### P2-1：`get_last_n_quarters()` 计算逻辑冗余

**位置**：`get_last_n_quarters()` 函数  
**现状**：手动计算年月再转季度，逻辑绕弯  
**建议**：直接用月份除以3向上取整，或从当前季度倒推

### P2-2：审计意见中文判断硬编码 Unicode 转义

**位置**：`fetch_audit_opinion()` 函数  
**现状**：`'\u65e0\u4fdd\u7559'`（无保留）、`'\u5f3a\u8c03\u4e8b\u9879'`（强调事项）等  
**问题**：可读性差，应直接写中文  
**修复**：`'无保留' in opinion_str`

### P2-3：LLM 分析依赖 deepseek-chat，无降级方案

**位置**：`llm_analyze()` 函数  
**现状**：硬编码 DeepSeek API，如果 API 不可用整个 agent 无法工作  
**建议**：提供 fallback 到本地规则报告（`generate_report` 已有结构化输出，可独立使用）

---

## 五、合规性检查

| 项目 | 状态 | 说明 |
|------|------|------|
| SKILL.md / AGENT.md | ❌ | 缺失 |
| README | ❌ | 缺失 |
| LICENSE | ❌ | 缺失 |
| .gitignore | ❌ | 缺失，.env 会被提交 |
| 接口可用性 | ❌ | get_fina_forecast 不存在 |
| 代码可运行 | ⚠️ | 依赖接口失效，核心功能不可用 |
| 密钥安全 | ❌ | 明文泄露 |
| 异常处理 | ⚠️ | 全部静默捕获，用户不知道发生了什么 |
| 代码风格 | ⚠️ | 混用中英文注释，函数职责不够清晰 |

---

## 六、修复优先级

1. **P0-1**：立即轮换 API Key，.env 加入 .gitignore，补 .env.example
2. **P0-2**：补 SKILL.md / README / LICENSE
3. **P0-3**：探测 panda_data SDK 确认可用的业绩预告接口，或改用 `get_fina_reports`
4. **P1-1**：验证 `get_stock_ncycl_consensus` 接口
5. **P1-2**：修正正则表达式，支持 SH/SZ/HK/US
6. **P1-3**：修复 `calculate_surprise` 的 None 判断
7. **P1-4**：延迟 PandaData 初始化
8. **P2**：代码可读性和健壮性优化
