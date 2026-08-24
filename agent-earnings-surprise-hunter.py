"""
Earnings Surprise Hunter Agent
"""
import sys
import os
import json
import datetime
from typing import Dict, List

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

from openai import OpenAI
from dotenv import load_dotenv
import panda_data

load_dotenv()

# ── 凭据解密：从 .env.enc 读取加密的敏感字段，注入环境变量 ──
try:
    from credential_encryptor import decrypt_into_dict
    enc = decrypt_into_dict()
    for k, v in enc.items():
        if v:
            os.environ[k] = v
except Exception:
    # .env.enc 不存在或密钥缺失 — 回退到 .env 中的明文（仅限开发/自检场景）
    pass
# ──────────────────────────────────────────────────────────────────────

PANDA_DATA_AVAILABLE = False

def init_panda_data(username=None, password=None):
    global PANDA_DATA_AVAILABLE
    try:
        un = username or os.getenv("PANDA_DATA_USERNAME")
        pw = password or os.getenv("PANDA_DATA_PASSWORD")
        if un and pw:
            panda_data.init_token(username=un, password=pw)
            PANDA_DATA_AVAILABLE = True
        return True
    except Exception:
        PANDA_DATA_AVAILABLE = False
        return False

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1"),
)
MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")

def get_market_type(symbol):
    if symbol.endswith('.SH') or symbol.endswith('.SZ'):
        return "cn"
    elif symbol.endswith('.HK'):
        return "hk"
    else:
        return "us"

def get_last_n_quarters(n=4):
    now = datetime.datetime.now()
    end_year = now.year
    end_quarter = (now.month - 1) // 3 + 1
    start_month = now.month - (n - 1) * 3
    start_year = end_year
    while start_month <= 0:
        start_month += 12
        start_year -= 1
    start_quarter = (start_month - 1) // 3 + 1
    return f"{start_year}q{start_quarter}", f"{end_year}q{end_quarter}"

# A 股 .SH/.SZ 都在上交所日历口径下同步开闭市，扫描统一用 "SH"。
_EXCHANGE_BY_MARKET = {"cn": "SH", "hk": "HK", "us": "US"}

def get_scan_trade_dates(symbol, scan_days=90):
    """返回最近 scan_days 自然日范围内的交易日列表（YYYYMMDD，最新在前）。

    经实测：get_fina_forecast 的 info_date 为「精确发布日」，只能逐日探测；
    但预告只会在交易日发布，故用交易日历过滤掉周末/节假日，减少 ~30% 无效请求。
    交易日历不可用时回退为自然日全扫描，保证健壮性。
    """
    today = datetime.date.today()
    exchange = _EXCHANGE_BY_MARKET.get(get_market_type(symbol), "SH")
    start = (today - datetime.timedelta(days=scan_days)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    if PANDA_DATA_AVAILABLE and hasattr(panda_data, "get_trade_cal"):
        try:
            cal = panda_data.get_trade_cal(start_date=start, end_date=end,
                                           exchange=exchange, is_trading_day=1)
            if cal is not None and not cal.empty and "nature_date" in cal.columns:
                dates = sorted({str(d) for d in cal["nature_date"].tolist()}, reverse=True)
                if dates:
                    return dates
        except Exception:
            pass
    # 回退：自然日逐日
    return [(today - datetime.timedelta(days=b)).strftime("%Y%m%d") for b in range(scan_days)]

def fetch_earnings_forecast(symbol, scan_days=90):
    if not PANDA_DATA_AVAILABLE:
        return {"status": "no_data", "forecasts": [], "message": "PandaData not available"}
    if not hasattr(panda_data, 'get_fina_forecast'):
        return {"status": "no_data", "forecasts": [], "message": "API not available: get_fina_forecast"}
    # get_fina_forecast 的 info_date 为「精确发布日」，不带则无数据；symbol/end_quarter 直查亦返回空（实测）。
    # 因此按最近 scan_days 内的「交易日」逐日拉取全市场预告并按 symbol 过滤，取最新一条。
    try:
        rows = []
        for info in get_scan_trade_dates(symbol, scan_days):
            try:
                df = panda_data.get_fina_forecast(info_date=info)
            except Exception:
                continue
            if df is None or df.empty or "symbol" not in df.columns:
                continue
            hit = df[df["symbol"].astype(str) == symbol]
            for _, row in hit.iterrows():
                rows.append((info, row))
        if not rows:
            return {"status": "no_data", "forecasts": [],
                    "message": f"No forecast in last {scan_days} days for {symbol}"}
        rows.sort(key=lambda x: x[0], reverse=True)  # 最新发布在前
        forecasts = []
        for info, row in rows:
            forecasts.append({
                "report_date": str(row.get("end_date", "")),
                "quarter": str(row.get("end_date", "")),
                "type": str(row.get("forecast_type", "")),
                "description": str(row.get("forecast_description", "")),
                "net_profit_min": row.get("forecast_np_floor", None),
                "net_profit_max": row.get("forecast_np_ceiling", None),
                "growth_min": row.get("forecast_growth_rate_floor", None),
                "growth_max": row.get("forecast_growth_rate_ceiling", None),
                "update_date": str(info),
            })
        return {"status": "success", "forecasts": forecasts}
    except Exception as e:
        return {"status": "error", "forecasts": [], "message": str(e)[:80]}

def fetch_consensus(symbol):
    if not PANDA_DATA_AVAILABLE:
        return {"status": "no_data", "consensus": None, "message": "PandaData not available"}
    if not hasattr(panda_data, 'get_stock_ncycl_consensus'):
        return {"status": "no_data", "consensus": None, "message": "API not available: get_stock_ncycl_consensus"}
    # get_stock_ncycl_consensus 仅支持港股（symbol 须为 xxxx.HK）。
    # A 股 / 美股传入会被接口拒绝，这里直接友好降级。
    market = get_market_type(symbol)
    if market != "hk":
        return {"status": "no_data", "consensus": None,
                "message": f"consensus API is HK-only, not applicable for {market} ({symbol})"}
    try:
        df = panda_data.get_stock_ncycl_consensus(symbol=symbol)
        if df is None or df.empty:
            return {"status": "no_data", "consensus": None, "message": "No consensus data"}
        # 返回为「指标 x 预测值」结构：indicator / mean / median / high / low / estimates_num
        indicators = {}
        for _, row in df.iterrows():
            ind = str(row.get("indicator", ""))
            indicators[ind] = {
                "mean": row.get("mean", None),
                "median": row.get("median", None),
                "high": row.get("high", None),
                "low": row.get("low", None),
                "estimates_num": row.get("estimates_num", None),
            }
        return {"status": "success", "consensus": {
            "indicators": indicators,
            "currency": str(df.iloc[0].get("currency", "")) if "currency" in df.columns else "",
        }}
    except Exception as e:
        return {"status": "error", "consensus": None, "message": str(e)[:80]}

def fetch_audit_opinion(symbol):
    if not PANDA_DATA_AVAILABLE:
        return {"status": "no_data", "opinion": None, "message": "PandaData not available"}
    if not hasattr(panda_data, 'get_audit_opinion'):
        return {"status": "no_data", "opinion": None, "message": "API not available: get_audit_opinion"}
    # get_audit_opinion 要求 A 股 6 位代码（如 000001.SZ）；港美股会被接口拒绝。
    market = get_market_type(symbol)
    if market != "cn":
        return {"status": "no_data", "opinion": None,
                "message": f"audit API is A-share only, not applicable for {market} ({symbol})"}
    try:
        start_q, end_q = get_last_n_quarters(8)
        df = panda_data.get_audit_opinion(symbol, start_quarter=start_q, end_quarter=end_q, market=market)
        if df is None or df.empty:
            return {"status": "no_data", "opinion": None, "message": "No audit data"}
        # 真实字段为 opinion / agency / audit_type / quarter / date。
        # 优先取「财报审计（financial_statements）」且已实际出具意见（非 no_audit_performed）的最新一条。
        cand = df.copy()
        if "audit_type" in cand.columns:
            fs = cand[cand["audit_type"] == "financial_statements"]
            if not fs.empty:
                cand = fs
        if "opinion" in cand.columns:
            performed = cand[cand["opinion"].astype(str) != "no_audit_performed"]
            if not performed.empty:
                cand = performed
        if "date" in cand.columns:
            cand = cand.sort_values("date")
        latest = cand.iloc[-1]

        opinion_str = str(latest.get("opinion", ""))
        opinion_lower = opinion_str.lower()
        # 分级：无保留=clean；带强调事项=warn；保留/否定/无法表示=risk；未审计/未知=unknown
        if "no_audit_performed" in opinion_lower:
            level = "unknown"
        elif "unqualified" in opinion_lower or "无保留" in opinion_str:
            level = "warn" if ("emphasis" in opinion_lower or "强调事项" in opinion_str) else "clean"
        elif "emphasis" in opinion_lower or "强调事项" in opinion_str:
            level = "warn"
        elif ("qualified" in opinion_lower or "adverse" in opinion_lower or "disclaimer" in opinion_lower
              or "保留" in opinion_str or "否定" in opinion_str or "无法表示" in opinion_str):
            level = "risk"
        else:
            level = "unknown"
        return {"status": "success", "opinion": {
            "opinion": opinion_str,
            "level": level,
            "auditor": str(latest.get("agency", "")),
            "quarter": str(latest.get("quarter", "")),
            "date": str(latest.get("date", "")),
        }}
    except Exception as e:
        return {"status": "error", "opinion": None, "message": str(e)[:80]}

def fetch_actual_results(symbol):
    """财务快报真实业绩（归母净利润 / YoY / EPS / 营收）。

    仅 A 股 get_fina_performance 提供。实测该接口对 info_date/end_quarter 过滤不敏感，
    只按 symbol 返回其覆盖到的一条快报，故作为「补充事实信息」展示，
    并在报告期与预告一致时供 calculate_surprise 作真实基准使用。
    """
    if not PANDA_DATA_AVAILABLE:
        return {"status": "no_data", "actual": None, "message": "PandaData not available"}
    if not hasattr(panda_data, 'get_fina_performance'):
        return {"status": "no_data", "actual": None, "message": "API not available: get_fina_performance"}
    market = get_market_type(symbol)
    if market != "cn":
        return {"status": "no_data", "actual": None,
                "message": f"performance API is A-share only, not applicable for {market} ({symbol})"}
    try:
        df = panda_data.get_fina_performance(symbol=symbol)
        if df is None or df.empty:
            return {"status": "no_data", "actual": None, "message": "No performance data"}
        # 取最新发布（info_date 最大）的一条
        row = df.copy()
        if "info_date" in row.columns:
            row = row.sort_values("info_date")
        latest = row.iloc[-1]

        def _num(key):
            v = latest.get(key, None)
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        return {"status": "success", "actual": {
            "report_date": str(latest.get("end_date", "")),
            "info_date": str(latest.get("info_date", "")),
            "net_profit_parent": _num("net_profit_parent"),
            "net_profit_parent_yoy": _num("net_profit_parent_yoy"),
            "basic_eps": _num("basic_eps"),
            "operating_revenue": _num("operating_revenue"),
            "operating_revenue_yoy": _num("operating_revenue_yoy"),
        }}
    except Exception as e:
        return {"status": "error", "actual": None, "message": str(e)[:80]}

def _period_months(report_date):
    """由报告期 end_date（YYYYMMDD）推断其覆盖的累计月数：Q1=3, 半年=6, Q3=9, 全年=12。

    A 股预告/快报的 net_profit 均为「年初至报告期末」的累计口径，故用累计月数即可做年化归一。
    无法识别时返回 None。
    """
    s = str(report_date)
    if len(s) < 8:
        return None
    mmdd = s[4:8]
    return {"0331": 3, "0630": 6, "0930": 9, "1231": 12}.get(mmdd)

def calculate_surprise(forecast, consensus, actual=None):
    # 基准优先级：可比一致预期净利润（consensus）> 财务快报真实净利润（actual）。
    cons = consensus.get("net_profit") if isinstance(consensus, dict) else None

    # 预告净利润中值（beat/miss 判断的被检验对象）
    f_min = forecast.get("net_profit_min") if forecast else None
    f_max = forecast.get("net_profit_max") if forecast else None
    if f_min is not None and f_max is not None:
        f_mid = (f_min + f_max) / 2
    elif f_min is not None:
        f_mid = f_min
    elif f_max is not None:
        f_mid = f_max
    else:
        f_mid = None

    def _verdict(basis, label, quality, note=None):
        if f_mid is None:
            return {"surprise": None, "deviation": None, "direction": "unknown",
                    "reason": "forecast has no net_profit range"}
        deviation = ((f_mid - basis) / abs(basis)) * 100
        if deviation >= 10:
            direction, surprise = "up", "beat"
        elif deviation <= -10:
            direction, surprise = "down", "miss"
        else:
            direction, surprise = "neutral", "inline"
        out = {"surprise": surprise, "direction": direction,
               "deviation": round(deviation, 2), "forecast": round(f_mid, 2),
               "consensus": round(basis, 2), "basis": label, "quality": quality}
        if note:
            out["note"] = note
        return out

    # 1) 一致预期可用（港股）：最可信基准，报告期口径由接口保证。
    if cons is not None and cons != 0:
        return _verdict(cons, "consensus", "exact")

    # 2) 只有财务快报（A 股）：按报告期口径对齐分级。
    a_np = actual.get("net_profit_parent") if actual else None
    if a_np not in (None, 0) and f_mid is not None:
        f_rd = str(forecast.get("report_date", "")) if forecast else ""
        a_rd = str(actual.get("report_date", ""))
        f_m = _period_months(f_rd)
        a_m = _period_months(a_rd)

        # 2a) 报告期完全一致 —— 高可信，直接比。
        if f_rd and f_rd == a_rd:
            return _verdict(a_np, "actual", "exact")

        # 2b) 报告期不同但累计口径可年化对齐 —— 把快报净利折算到预告口径后近似比较。
        if f_m and a_m and f_m != a_m:
            basis_norm = a_np * (f_m / a_m)
            note = (f"actual np {a_np:.0f} ({a_rd}, {a_m}M) annualized to forecast "
                    f"period {f_rd} ({f_m}M) as {basis_norm:.0f}")
            return _verdict(basis_norm, "actual_annualized", "approx_annualized", note)

    # 3) 完全不可比：不计算 surprise，但把快报净利作为「参考基准」附上，供报告展示。
    result = {"surprise": None, "deviation": None, "direction": "unknown"}
    if a_np not in (None, 0):
        result["reason"] = "actual results available but period not comparable to forecast"
        result["reference_basis"] = round(a_np, 2)
        result["reference_report_date"] = str(actual.get("report_date", ""))
    else:
        result["reason"] = "no comparable consensus net_profit"
    return result

def analyze_surprise(symbol):
    forecast_data = fetch_earnings_forecast(symbol)
    consensus_data = fetch_consensus(symbol)
    audit_data = fetch_audit_opinion(symbol)
    actual_data = fetch_actual_results(symbol)
    forecast = forecast_data["forecasts"][0] if forecast_data["forecasts"] else None
    consensus = consensus_data["consensus"]
    actual = actual_data["actual"]
    surprise = calculate_surprise(forecast, consensus, actual)
    return {
        "symbol": symbol,
        "forecast": forecast_data,
        "consensus": consensus_data,
        "audit": audit_data,
        "actual": actual_data,
        "surprise": surprise,
    }

def generate_report(data):
    symbol = data["symbol"]
    surprise = data["surprise"]
    report = "## Earnings Surprise Report: " + symbol + "\n\n"
    if surprise["surprise"]:
        basis = surprise.get("basis", "consensus")
        basis_label = {"consensus": "Consensus", "actual": "Actual",
                       "actual_annualized": "Actual (annualized)"}.get(basis, "Basis")
        if surprise["direction"] == "up":
            report += "### [UP] Beat Expectations (" + str(surprise["deviation"]) + "%)\n"
        elif surprise["direction"] == "down":
            report += "### [DOWN] Miss Expectations (" + str(surprise["deviation"]) + "%)\n"
        else:
            report += "### [NEUTRAL] Inline (" + str(surprise["deviation"]) + "%)\n"
        report += "- Forecast: " + str(surprise["forecast"]) + " vs " + basis_label + ": " + str(surprise["consensus"]) + "\n"
        quality = surprise.get("quality")
        if quality == "approx_annualized":
            report += "- Confidence: APPROX (cross-period, annualized comparison)\n"
        elif quality == "exact":
            report += "- Confidence: HIGH (same-period comparison)\n"
        if surprise.get("note"):
            report += "- Note: " + str(surprise["note"]) + "\n"
        report += "\n"
    else:
        reason = surprise.get("reason", "insufficient data")
        report += "### [NEUTRAL] Surprise not computed (" + reason + ")\n"
        if surprise.get("reference_basis") is not None:
            report += ("- Reference basis (latest actual net profit, not period-aligned): "
                       + str(surprise["reference_basis"])
                       + " @ " + str(surprise.get("reference_report_date", "")) + "\n")
        report += "\n"
    if data["forecast"]["forecasts"]:
        f = data["forecast"]["forecasts"][0]
        report += "### Forecast\n"
        report += "- Quarter: " + str(f["quarter"]) + "\n"
        report += "- Type: " + str(f["type"]) + "\n"
        if f.get("description"):
            report += "- Description: " + str(f["description"]) + "\n"
        if f.get("net_profit_min") is not None or f.get("net_profit_max") is not None:
            report += "- Net Profit Range: " + str(f.get("net_profit_min")) + " ~ " + str(f.get("net_profit_max")) + "\n"
        if f.get("growth_min") is not None or f.get("growth_max") is not None:
            report += "- Growth Rate (%): " + str(f.get("growth_min")) + " ~ " + str(f.get("growth_max")) + "\n"
        report += "- Update Date: " + str(f["update_date"]) + "\n\n"
    else:
        report += "### Forecast\n- " + str(data["forecast"].get("message", "No forecast data")) + "\n\n"
    c = data["consensus"]["consensus"]
    if c:
        report += "### Consensus\n"
        if "net_profit" in c:
            report += "- Net Profit: " + str(c.get("net_profit")) + "\n"
            report += "- EPS: " + str(c.get("eps")) + "\n"
            report += "- Analysts: " + str(c.get("num_analysts")) + "\n\n"
        else:
            inds = c.get("indicators", {})
            report += "- Currency: " + str(c.get("currency", "")) + "\n"
            for name, v in list(inds.items())[:6]:
                report += "- " + name + ": mean=" + str(v.get("mean")) + ", n=" + str(v.get("estimates_num")) + "\n"
            report += "\n"
    else:
        report += "### Consensus\n- " + str(data["consensus"].get("message", "No consensus data")) + "\n\n"
    a = data.get("actual", {}).get("actual")
    if a:
        report += "### Actual Results (Express Report)\n"
        report += "- Report Date: " + str(a.get("report_date")) + "\n"
        if a.get("net_profit_parent") is not None:
            report += "- Net Profit (parent): " + str(a.get("net_profit_parent")) + "\n"
        if a.get("net_profit_parent_yoy") is not None:
            report += "- Net Profit YoY (%): " + str(a.get("net_profit_parent_yoy")) + "\n"
        if a.get("basic_eps") is not None:
            report += "- Basic EPS: " + str(a.get("basic_eps")) + "\n"
        if a.get("operating_revenue") is not None:
            report += "- Operating Revenue: " + str(a.get("operating_revenue")) + "\n"
        report += "\n"
    elif data.get("actual"):
        report += "### Actual Results (Express Report)\n- " + str(data["actual"].get("message", "No actual data")) + "\n\n"
    if data["audit"]["opinion"]:
        o = data["audit"]["opinion"]
        color = "[CLEAN]" if o["level"] == "clean" else "[WARN]" if o["level"] == "warn" else "[RISK]" if o["level"] == "risk" else "[UNKNOWN]"
        report += "### Audit Opinion " + color + "\n"
        report += "- Opinion: " + str(o["opinion"]) + "\n"
        report += "- Auditor: " + str(o["auditor"]) + "\n"
        if o.get("quarter"):
            report += "- Quarter: " + str(o["quarter"]) + "\n"
    else:
        report += "### Audit Opinion\n- " + str(data["audit"].get("message", "No audit data")) + "\n"
    return report

def llm_analyze(prompt):
    system_prompt = """You are a professional earnings analysis assistant. 
    Analyze earnings surprise data and provide investment insights.
    Use [UP], [DOWN], [NEUTRAL] for surprise direction.
    Use [CLEAN], [WARN], [RISK] for audit opinion."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content.strip()

def chat_with_agent(query):
    import re
    pattern = r'(\d{6}\.(SH|SZ)|\d{4,5}\.HK|[A-Z]{2,5}(\.[A-Z]{2})?)'
    match = re.search(pattern, query)
    if match:
        symbol = match.group(1)
        data = analyze_surprise(symbol)
        report = generate_report(data)
        return llm_analyze("Analyze the following earnings data:\n\n" + report)
    return llm_analyze(query)

if __name__ == "__main__":
    print("=" * 60)
    print("Earnings Surprise Hunter Agent")
    print("=" * 60)
    
    init_panda_data()
    
    test_cases = [
        "Analyze earnings surprise for 600889.SH",
        "Analyze earnings surprise for 688012.SH",
        "Analyze earnings surprise for 0700.HK",
    ]
    for query in test_cases:
        print("\n[User]: " + query)
        try:
            response = chat_with_agent(query)
            print("[Agent]:")
            print(response)
        except Exception as e:
            print("[Agent] Error: " + str(e))