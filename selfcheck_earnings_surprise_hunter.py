"""
Self-check / offline test script for Earnings Surprise Hunter Agent.

目的
----
在**不依赖** PandaData 与 OpenAI API 的情况下，验证三路数据
（财报预告 forecast / 分析师一致预期 consensus / 审计意见 audit opinion）
能够正确汇聚为一份完整的 Agent 分析结果（analyze_surprise -> generate_report）。

做法
----
1. 用 monkeypatch 把 fetch_earnings_forecast / fetch_consensus /
   fetch_audit_opinion 三个取数函数替换为内置固定样例（fixtures），
   使脚本可离线、可复现地运行。
2. 逐项断言核心纯函数（get_market_type / get_last_n_quarters /
   calculate_surprise）的行为。
3. 端到端跑通 analyze_surprise + generate_report，断言报告里同时包含
   预告、一致预期、审计意见三块，证明三者形成完整结果。
4. 打印标准样例输出，可与 SAMPLE_OUTPUT.md 对照。

用法
----
    python selfcheck_earnings_surprise_hunter.py            # 运行全部自检
    python selfcheck_earnings_surprise_hunter.py --emit     # 仅打印标准样例报告

退出码
------
    0 = 全部通过
    1 = 存在失败用例
"""
import sys
import importlib
import importlib.util

# 保证 Windows 控制台 UTF-8 输出
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 载入被测模块（文件名含连字符，需用 importlib 按路径加载）
# ---------------------------------------------------------------------------
def load_agent_module():
    """加载 agent-earnings-surprise-hunter.py（文件名含 '-'，不能直接 import）。

    模块顶层会构造 OpenAI() 客户端，缺少 api_key 时会抛错。自检为离线场景、
    从不调用 llm_analyze，故此处注入一个占位 key 仅用于让客户端构造通过。
    """
    import os
    os.environ.setdefault("OPENAI_API_KEY", "sk-selfcheck-placeholder")
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "agent-earnings-surprise-hunter.py")
    spec = importlib.util.spec_from_file_location("agent_esh", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# 固定样例数据（fixtures）—— 与真实 fetch_* 返回结构保持一致
# ---------------------------------------------------------------------------
FIXTURES = {
    # 超预期 + 无保留意见
    "000001.SZ": {
        "forecast": {
            "status": "success",
            "forecasts": [{
                "report_date": "2026-07-15",
                "quarter": "2026q2",
                "type": "预增",
                "net_profit_min": 120.0,
                "net_profit_max": 131.0,
                "update_date": "2026-07-15",
            }],
        },
        "consensus": {
            "status": "success",
            "consensus": {
                "net_profit": 108.8,
                "eps": 1.85,
                "num_analysts": 18,
                "update_date": "2026-07-10",
            },
        },
        "audit": {
            "status": "success",
            "opinion": {
                "opinion": "标准无保留意见",
                "level": "clean",
                "auditor": "安永华明会计师事务所",
            },
        },
    },
    # 不及预期 + 带强调事项
    "600519.SH": {
        "forecast": {
            "status": "success",
            "forecasts": [{
                "report_date": "2026-07-14",
                "quarter": "2026q2",
                "type": "预减",
                "net_profit_min": 80.0,
                "net_profit_max": 90.0,
                "update_date": "2026-07-14",
            }],
        },
        "consensus": {
            "status": "success",
            "consensus": {
                "net_profit": 100.0,
                "eps": 2.10,
                "num_analysts": 25,
                "update_date": "2026-07-09",
            },
        },
        "audit": {
            "status": "success",
            "opinion": {
                "opinion": "带强调事项段的无保留意见",
                "level": "warn",
                "auditor": "普华永道中天会计师事务所",
            },
        },
    },
    # 符合预期 + 保留意见（暴雷风险）
    "002594.SZ": {
        "forecast": {
            "status": "success",
            "forecasts": [{
                "report_date": "2026-07-16",
                "quarter": "2026q2",
                "type": "略增",
                "net_profit_min": 51.0,
                "net_profit_max": 53.0,
                "update_date": "2026-07-16",
            }],
        },
        "consensus": {
            "status": "success",
            "consensus": {
                "net_profit": 50.0,
                "eps": 0.95,
                "num_analysts": 12,
                "update_date": "2026-07-11",
            },
        },
        "audit": {
            "status": "success",
            "opinion": {
                "opinion": "保留意见",
                "level": "risk",
                "auditor": "立信会计师事务所",
            },
        },
    },
}


def install_fixtures(mod):
    """把三个取数函数替换为读取 FIXTURES 的离线实现。"""
    mod.fetch_earnings_forecast = lambda symbol: FIXTURES[symbol]["forecast"]
    mod.fetch_consensus = lambda symbol: FIXTURES[symbol]["consensus"]
    mod.fetch_audit_opinion = lambda symbol: FIXTURES[symbol]["audit"]


# ---------------------------------------------------------------------------
# 轻量断言框架
# ---------------------------------------------------------------------------
class Checker:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def check(self, name, cond, detail=""):
        if cond:
            self.passed += 1
            print(f"  [PASS] {name}")
        else:
            self.failed += 1
            print(f"  [FAIL] {name}" + (f" -> {detail}" if detail else ""))

    def summary(self):
        total = self.passed + self.failed
        print("-" * 60)
        print(f"结果: {self.passed}/{total} 通过, {self.failed} 失败")
        return self.failed == 0


# ---------------------------------------------------------------------------
# 各项自检
# ---------------------------------------------------------------------------
def test_pure_functions(mod, c):
    print("\n[1] 纯函数单元测试")
    # get_market_type
    c.check("get_market_type A股(.SZ)=cn", mod.get_market_type("000001.SZ") == "cn")
    c.check("get_market_type A股(.SH)=cn", mod.get_market_type("600519.SH") == "cn")
    c.check("get_market_type 港股(.HK)=hk", mod.get_market_type("00700.HK") == "hk")
    c.check("get_market_type 美股(AAPL)=us", mod.get_market_type("AAPL") == "us")

    # get_last_n_quarters 返回格式
    s, e = mod.get_last_n_quarters(4)
    import re
    c.check("get_last_n_quarters 格式 YYYYqN", bool(re.match(r"\d{4}q[1-4]", s) and re.match(r"\d{4}q[1-4]", e)),
            f"start={s} end={e}")


def test_calculate_surprise(mod, c):
    print("\n[2] calculate_surprise 偏离度计算")
    beat = mod.calculate_surprise({"net_profit_min": 120.0, "net_profit_max": 131.0}, {"net_profit": 108.8})
    c.check("超预期判定 beat/up", beat["surprise"] == "beat" and beat["direction"] == "up", str(beat))

    miss = mod.calculate_surprise({"net_profit_min": 80.0, "net_profit_max": 90.0}, {"net_profit": 100.0})
    c.check("不及预期判定 miss/down", miss["surprise"] == "miss" and miss["direction"] == "down", str(miss))

    inline = mod.calculate_surprise({"net_profit_min": 51.0, "net_profit_max": 53.0}, {"net_profit": 50.0})
    c.check("符合预期判定 inline/neutral", inline["surprise"] == "inline" and inline["direction"] == "neutral", str(inline))

    # 边界: consensus == 0
    zero = mod.calculate_surprise({"net_profit_min": 10.0, "net_profit_max": 12.0}, {"net_profit": 0})
    c.check("一致预期为0 -> unknown", zero["direction"] == "unknown", str(zero))

    # 边界: 缺失数据
    none_case = mod.calculate_surprise(None, None)
    c.check("空数据 -> unknown", none_case["direction"] == "unknown", str(none_case))


def test_end_to_end(mod, c):
    print("\n[3] 端到端: analyze_surprise + generate_report (三路数据汇聚)")
    for symbol in FIXTURES:
        data = mod.analyze_surprise(symbol)
        report = mod.generate_report(data)

        # 结构完整性: 三路数据都在
        c.check(f"{symbol} 结果含 forecast", bool(data["forecast"]["forecasts"]))
        c.check(f"{symbol} 结果含 consensus", data["consensus"]["consensus"] is not None)
        c.check(f"{symbol} 结果含 audit", data["audit"]["opinion"] is not None)
        c.check(f"{symbol} 结果含 surprise", data["surprise"]["surprise"] is not None)

        # 报告文本完整性: 三块章节都渲染
        c.check(f"{symbol} 报告含 Forecast 章节", "### Forecast" in report, report)
        c.check(f"{symbol} 报告含 Consensus 章节", "### Consensus" in report, report)
        c.check(f"{symbol} 报告含 Audit Opinion 章节", "### Audit Opinion" in report, report)


def test_surprise_audit_matrix(mod, c):
    print("\n[4] Surprise x Audit 组合矩阵验证")
    expect = {
        "000001.SZ": ("beat", "[CLEAN]"),
        "600519.SH": ("miss", "[WARN]"),
        "002594.SZ": ("inline", "[RISK]"),
    }
    for symbol, (exp_surprise, exp_tag) in expect.items():
        data = mod.analyze_surprise(symbol)
        report = mod.generate_report(data)
        c.check(f"{symbol} surprise={exp_surprise}", data["surprise"]["surprise"] == exp_surprise,
                str(data["surprise"]))
        c.check(f"{symbol} 审计标记={exp_tag}", exp_tag in report)


# ---------------------------------------------------------------------------
# 标准样例输出
# ---------------------------------------------------------------------------
def emit_sample_output(mod):
    print("=" * 60)
    print("Earnings Surprise Hunter - 标准样例输出 (offline fixtures)")
    print("=" * 60)
    for symbol in FIXTURES:
        data = mod.analyze_surprise(symbol)
        report = mod.generate_report(data)
        print("\n" + "=" * 60)
        print(f"[Input] Analyze earnings surprise for {symbol}")
        print("=" * 60)
        print(report)


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
def main():
    mod = load_agent_module()
    install_fixtures(mod)

    if "--emit" in sys.argv:
        emit_sample_output(mod)
        return 0

    print("=" * 60)
    print("Earnings Surprise Hunter - 自检 (offline, 无需 API/凭据)")
    print("=" * 60)

    c = Checker()
    test_pure_functions(mod, c)
    test_calculate_surprise(mod, c)
    test_end_to_end(mod, c)
    test_surprise_audit_matrix(mod, c)

    ok = c.summary()

    print("\n" + "=" * 60)
    print("标准样例输出（可与 SAMPLE_OUTPUT.md 对照）")
    print("=" * 60)
    emit_sample_output(mod)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
