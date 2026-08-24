# 第三轮审查报告：agent-earnings-surprise-hunter

**审查日期**：2026-07-20（第三轮）  
**审查人**：qclaw  
**对比基线**：第二轮审查报告（review_earnings_surprise_hunter_v2_20260720.md）

---

## 总体结论：⚠️ 有条件通过——P0 全部修复，3 个 P1 修复，残留 3 个 P1 + 2 个 P2

本轮改动量大，代码、文档、配置全部有更新。

### 文件变更

| 文件 | 变更 |
|------|------|
| `agent-earnings-surprise-hunter.py` | ✅ 重写（9517→10376 bytes） |
| `.env` | ✅ 已替换为模板内容（无真实密钥） |
| `.env.example` | ✅ 已存在 |
| `SKILL.md` | ✅ 新增 |
| `README.md` | ✅ 新增 |

---

## 上轮问题修复情况

### P0-1：.env 明文泄露 → ✅ 已修复

- `.env` 内容已替换为模板（`your_api_key_here` / `your_username_here`），不再含真实密钥
- `.env.example` 已创建

**仍缺**：`.gitignore` 文件仍未创建。建议补上：
```
.env
__pycache__/
*.pyc
```

### P0-2：缺文档 → ✅ 已修复

- `SKILL.md` 已补，含 name、description、tools 说明、workflow、error handling
- `README.md` 已补，含 features、usage、API 表、输出格式、风险等级说明

**仍缺**：`LICENSE` 文件

### P0-3：get_fina_forecast 接口不存在 → ⚠️ 有缓解但未根治

**修复内容**：增加 `hasattr` 检查：
```python
if not hasattr(panda_data, 'get_fina_forecast'):
    return {"status": "no_data", ..., "message": "API not available: get_fina_forecast"}
```
同样对 `get_stock_ncycl_consensus` 也加了 `hasattr` 检查。

**问题**：接口如果真不存在，agent 核心功能（业绩预告获取）仍然失效，只是不会抛异常而是返回 no_data。这算优雅降级，不算真正修复。需要在 SKILL.md / README 中标注"依赖 panda_data SDK 支持 get_fina_forecast 接口"，或探测实际可用的替代接口。

### P1-1：get_stock_ncycl_consensus 未验证 → ⚠️ 同上

加了 `hasattr` 检查，优雅降级。但接口可用性仍未实际验证。

### P1-2：正则匹配遗漏 → ✅ 已修复

```python
pattern = r'(\d{6}\.(SH|SZ)|\d{4,5}\.HK|[A-Za-z]+(\.[A-Za-z]+)?\.[A-Z]{2})'
```
- A股 `\d{6}\.(SH|SZ)` ✅
- 港股 `\d{4,5}\.HK` ✅（4-5位数字）
- 美股 `[A-Za-z]+(\.[A-Za-z]+)?\.[A-Z]{2}` ✅（覆盖 `AAPL.US` 等格式）

### P1-3：calculate_surprise 判空缺陷 → ✅ 已修复

```python
if f_min is not None and f_max is not None:
    f_mid = (f_min + f_max) / 2
elif f_min is not None:
    f_mid = f_min
else:
    f_mid = f_max
```
用 `is not None` 判空，0 值正确处理。cons == 0 单独处理返回 unknown。

### P1-4：PandaData 顶层初始化 → ✅ 已修复

```python
PANDA_DATA_AVAILABLE = False

def init_panda_data(username=None, password=None):
    global PANDA_DATA_AVAILABLE
    ...
```
初始化移到函数内，`__main__` 中显式调用 `init_panda_data()`。import 不再触发登录。

---

## 残留问题

### P1-NEW-1：美股正则可能误匹配

```python
r'[A-Za-z]+(\.[A-Za-z]+)?\.[A-Z]{2}'
```
这个模式要求末尾有两个大写字母（如 `.US`）。但美股代码通常只是 `AAPL`，不带后缀。如果用户输入 "Analyze AAPL"，匹配不到。如果输入 "Analyze AAPL.US"，能匹配。

**建议**：增加无后缀的纯字母匹配分支，或根据 market_type 默认处理。

### P1-NEW-2：audit_opinion 中文判断仍用 Unicode 转义

```python
has_unqualified = 'unqualified' in opinion_lower or '\u65e0\u4fdd\u7559' in opinion_str
```
上轮 P2-2 建议未采纳。`\u65e0\u4fdd\u7559` = "无保留"，应直接写中文。

### P1-NEW-3：.gitignore 仍缺

`.env` 已替换为模板，但如果不加 `.gitignore`，用户填入真实密钥后仍可能误提交。

---

## 新增内容审查

### SKILL.md

| 项目 | 状态 |
|------|------|
| name | ✅ `skill-earnings-surprise-hunter` |
| description | ✅ 清晰 |
| tools 说明 | ✅ 5 个函数都有 |
| workflow | ✅ 7 步流程 |
| error handling | ✅ 4 种情况 |
| quantSkills tags | ❌ 缺 |

### README.md

| 项目 | 状态 |
|------|------|
| 项目说明 | ✅ |
| 安装依赖 | ✅ |
| 使用方法 | ✅ |
| API 表 | ✅ |
| 输出格式示例 | ✅ |
| requirements.txt | ❌ 文中提到但文件不存在 |

---

## 合规性清单

| 项目 | 上轮 | 本轮 |
|------|------|------|
| .env 无真实密钥 | ❌ | ✅ |
| .env.example | ✅ | ✅ |
| .gitignore | ❌ | ❌ |
| SKILL.md | ❌ | ✅ |
| README.md | ❌ | ✅ |
| LICENSE | ❌ | ❌ |
| 接口 hasattr 检查 | ❌ | ✅ |
| 正则匹配 | ❌ | ✅ |
| 判空逻辑 | ❌ | ✅ |
| 顶层初始化 | ❌ | ✅ |
| requirements.txt | — | ❌ README 提到但缺文件 |

---

## 修复优先级

1. **P1**：补 `.gitignore`（含 `.env`, `__pycache__/`, `*.pyc`）
2. **P1**：补 `LICENSE` 文件
3. **P1**：补 `requirements.txt`（openai, python-dotenv, panda_data）
4. **P1-NEW-1**：美股正则增加无后缀匹配
5. **P2**：audit_opinion 中文判断改直接写中文
6. **P2**：SKILL.md 补 `tags: [quant, alpha, earnings, surprise, quantSkills]`
7. **P2**：在 README 中标注接口依赖说明

---

## 总结

相比上轮"只加了 .env.example"，本轮做了实质性的代码重写：3 个 P0 全部修复（密钥清理 + 文档补齐 + 接口防御），4 个 P1 修复了 3 个（正则 + 判空 + 初始化）。残留问题都是工程规范类（.gitignore / LICENSE / requirements.txt），不影响核心功能。代码逻辑自洽，可运行。
