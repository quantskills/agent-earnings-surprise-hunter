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

def fetch_earnings_forecast(symbol):
    if not PANDA_DATA_AVAILABLE:
        return {"status": "no_data", "forecasts": [], "message": "PandaData not available"}
    if not hasattr(panda_data, 'get_fina_forecast'):
        return {"status": "no_data", "forecasts": [], "message": "API not available: get_fina_forecast"}
    try:
        start_q, end_q = get_last_n_quarters(4)
        market = get_market_type(symbol)
        df = panda_data.get_fina_forecast(symbol, start_quarter=start_q, end_quarter=end_q, market=market)
        if df is None or df.empty:
            return {"status": "no_data", "forecasts": [], "message": "No forecast data"}
        forecasts = []
        for _, row in df.iterrows():
            forecasts.append({
                "report_date": str(row.get("report_date", "")),
                "quarter": str(row.get("quarter", "")),
                "type": str(row.get("forecast_type", "")),
                "net_profit_min": row.get("net_profit_min", None),
                "net_profit_max": row.get("net_profit_max", None),
                "update_date": str(row.get("update_date", "")),
            })
        return {"status": "success", "forecasts": forecasts}
    except Exception as e:
        return {"status": "error", "forecasts": [], "message": str(e)[:50]}

def fetch_consensus(symbol):
    if not PANDA_DATA_AVAILABLE:
        return {"status": "no_data", "consensus": None, "message": "PandaData not available"}
    if not hasattr(panda_data, 'get_stock_ncycl_consensus'):
        return {"status": "no_data", "consensus": None, "message": "API not available: get_stock_ncycl_consensus"}
    try:
        df = panda_data.get_stock_ncycl_consensus(symbol)
        if df is None or df.empty:
            return {"status": "no_data", "consensus": None, "message": "No consensus data"}
        latest = df.iloc[-1]
        return {"status": "success", "consensus": {
            "net_profit": latest.get("consensus_net_profit", None),
            "eps": latest.get("consensus_eps", None),
            "num_analysts": latest.get("num_analysts", None),
            "update_date": str(latest.get("update_date", "")),
        }}
    except Exception as e:
        return {"status": "error", "consensus": None, "message": str(e)[:50]}

def fetch_audit_opinion(symbol):
    if not PANDA_DATA_AVAILABLE:
        return {"status": "no_data", "opinion": None, "message": "PandaData not available"}
    try:
        start_q, end_q = get_last_n_quarters(4)
        market = get_market_type(symbol)
        df = panda_data.get_audit_opinion(symbol, start_quarter=start_q, end_quarter=end_q, market=market)
        if df is None or df.empty:
            return {"status": "no_data", "opinion": None, "message": "No audit data"}
        latest = df.iloc[-1]
        opinion_str = str(latest.get("audit_opinion", ""))
        opinion_lower = opinion_str.lower()
        has_unqualified = 'unqualified' in opinion_lower or '无保留' in opinion_str
        has_emphasis = 'emphasis' in opinion_lower or '强调事项' in opinion_str
        has_qualified = 'qualified' in opinion_lower or 'adverse' in opinion_lower or '保留' in opinion_str or '否定' in opinion_str
        
        if has_unqualified:
            level = "clean"
        elif has_emphasis:
            level = "warn"
        elif has_qualified:
            level = "risk"
        else:
            level = "unknown"
        return {"status": "success", "opinion": {
            "opinion": opinion_str,
            "level": level,
            "auditor": str(latest.get("auditor", "")),
        }}
    except Exception as e:
        return {"status": "error", "opinion": None, "message": str(e)[:50]}

def calculate_surprise(forecast, consensus):
    if not forecast or not consensus:
        return {"surprise": None, "deviation": None, "direction": "unknown"}
    cons = consensus.get("net_profit")
    if cons is None:
        return {"surprise": None, "deviation": None, "direction": "unknown"}
    if cons == 0:
        return {"surprise": None, "deviation": None, "direction": "unknown", "reason": "consensus is zero"}
    f_min = forecast.get("net_profit_min")
    f_max = forecast.get("net_profit_max")
    if f_min is None and f_max is None:
        return {"surprise": None, "deviation": None, "direction": "unknown"}
    if f_min is not None and f_max is not None:
        f_mid = (f_min + f_max) / 2
    elif f_min is not None:
        f_mid = f_min
    else:
        f_mid = f_max
    deviation = ((f_mid - cons) / abs(cons)) * 100
    if deviation >= 10:
        return {"surprise": "beat", "direction": "up", "deviation": round(deviation, 2), "forecast": round(f_mid, 2), "consensus": round(cons, 2)}
    elif deviation <= -10:
        return {"surprise": "miss", "direction": "down", "deviation": round(deviation, 2), "forecast": round(f_mid, 2), "consensus": round(cons, 2)}
    else:
        return {"surprise": "inline", "direction": "neutral", "deviation": round(deviation, 2), "forecast": round(f_mid, 2), "consensus": round(cons, 2)}

def analyze_surprise(symbol):
    forecast_data = fetch_earnings_forecast(symbol)
    consensus_data = fetch_consensus(symbol)
    audit_data = fetch_audit_opinion(symbol)
    forecast = forecast_data["forecasts"][0] if forecast_data["forecasts"] else None
    consensus = consensus_data["consensus"]
    surprise = calculate_surprise(forecast, consensus)
    return {
        "symbol": symbol,
        "forecast": forecast_data,
        "consensus": consensus_data,
        "audit": audit_data,
        "surprise": surprise,
    }

def generate_report(data):
    symbol = data["symbol"]
    surprise = data["surprise"]
    report = "## Earnings Surprise Report: " + symbol + "\n\n"
    if surprise["surprise"]:
        if surprise["direction"] == "up":
            report += "### [UP] Beat Expectations (" + str(surprise["deviation"]) + "%)\n"
        elif surprise["direction"] == "down":
            report += "### [DOWN] Miss Expectations (" + str(surprise["deviation"]) + "%)\n"
        else:
            report += "### [NEUTRAL] Inline (" + str(surprise["deviation"]) + "%)\n"
        report += "- Forecast: " + str(surprise["forecast"]) + " vs Consensus: " + str(surprise["consensus"]) + "\n\n"
    else:
        report += "### [NEUTRAL] Insufficient data\n\n"
    if data["forecast"]["forecasts"]:
        f = data["forecast"]["forecasts"][0]
        report += "### Forecast\n"
        report += "- Quarter: " + str(f["quarter"]) + "\n"
        report += "- Type: " + str(f["type"]) + "\n"
        report += "- Update Date: " + str(f["update_date"]) + "\n\n"
    if data["consensus"]["consensus"]:
        c = data["consensus"]["consensus"]
        report += "### Consensus\n"
        report += "- Net Profit: " + str(c["net_profit"]) + "\n"
        report += "- EPS: " + str(c["eps"]) + "\n"
        report += "- Analysts: " + str(c["num_analysts"]) + "\n\n"
    if data["audit"]["opinion"]:
        o = data["audit"]["opinion"]
        color = "[CLEAN]" if o["level"] == "clean" else "[WARN]" if o["level"] == "warn" else "[RISK]"
        report += "### Audit Opinion " + color + "\n"
        report += "- Opinion: " + str(o["opinion"]) + "\n"
        report += "- Auditor: " + str(o["auditor"]) + "\n"
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
        "Analyze earnings surprise for 000001.SZ",
        "Analyze earnings surprise for 600519.SH",
        "Analyze earnings surprise for 002594.SZ",
    ]
    for query in test_cases:
        print("\n[User]: " + query)
        try:
            response = chat_with_agent(query)
            print("[Agent]:")
            print(response)
        except Exception as e:
            print("[Agent] Error: " + str(e))