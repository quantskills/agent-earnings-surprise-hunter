# Skill Definition: Earnings Surprise Hunter

## Name
skill-earnings-surprise-hunter

## Tags
[quantSkills]

## Description
财报季 Surprise / 暴雷猎手技能。获取财报预告、一致预期、审计意见数据，计算偏离度并生成分析报告。

## Tools

### 1. fetch_earnings_forecast
- **Description**: 获取财报预告数据
- **Parameters**:
  - `symbol`: 股票代码（如 000001.SZ）
- **Returns**:
  - `status`: success / no_data / error
  - `forecasts`: 预告列表
  - `message`: 错误信息

### 2. fetch_consensus
- **Description**: 获取分析师一致预期
- **Parameters**:
  - `symbol`: 股票代码
- **Returns**:
  - `status`: success / no_data / error
  - `consensus`: 预期数据（净利润、EPS、分析师数量）
  - `message`: 错误信息

### 3. fetch_audit_opinion
- **Description**: 获取审计意见
- **Parameters**:
  - `symbol`: 股票代码
- **Returns**:
  - `status`: success / no_data / error
  - `opinion`: 审计意见（意见类型、风险等级、审计机构）
  - `message`: 错误信息

### 4. calculate_surprise
- **Description**: 计算偏离度
- **Parameters**:
  - `forecast`: 预告数据
  - `consensus`: 一致预期数据
- **Returns**:
  - `surprise`: beat / miss / inline
  - `direction`: up / down / neutral
  - `deviation`: 偏离度百分比

### 5. analyze_surprise
- **Description**: 综合分析
- **Parameters**:
  - `symbol`: 股票代码
- **Returns**: 完整分析报告

## Workflow

1. 解析用户查询，提取股票代码
2. 调用 `fetch_earnings_forecast` 获取预告
3. 调用 `fetch_consensus` 获取一致预期
4. 调用 `fetch_audit_opinion` 获取审计意见
5. 调用 `calculate_surprise` 计算偏离度
6. 调用 `generate_report` 生成报告
7. 调用 `llm_analyze` 智能分析

## Error Handling

- PandaData不可用时返回友好提示
- API接口不存在时返回明确错误
- 数据为空时返回中性评分
- 0值净利润做特殊处理