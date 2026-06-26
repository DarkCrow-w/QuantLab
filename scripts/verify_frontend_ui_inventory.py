from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


CHECKS: dict[str, list[str]] = {
    "web/src/components/layout/Header.tsx": [
        "系统总览",
        "数据平台",
        "交易运行",
        "研究资产",
        "策略管理",
        "因子研究",
        "风险控制",
        "回测研究",
        "智能选股",
        "AI 研究员",
        "数据中心",
        "下载全市场",
    ],
    "web/src/pages/DashboardPage.tsx": [
        "量化研究控制台",
        "数据准备度",
        "策略库",
        "上线验收",
    ],
    "web/src/pages/DataPage.tsx": [
        "市场数据平台",
        "数据初始化",
        "全市场下载",
        "增量更新",
    ],
    "web/src/pages/TradingPage.tsx": [
        "交易运行中心",
        "实盘启动命令",
        "仿真/回测验证",
        "Web 实盘启动保持禁用",
    ],
    "web/src/pages/ResearchPage.tsx": [
        "研究资产库",
        "回测实验记录",
        "参数网格实验",
        "导出报告",
    ],
    "web/src/pages/StrategyPage.tsx": [
        "策略管理",
        "策略库",
        "新建组合策略",
        "运行策略",
        "低位KDJ+昨日倍量",
    ],
    "web/src/pages/FactorPage.tsx": [
        "因子研究",
        "因子库",
        "因子挖掘结果",
        "运行因子挖掘",
        "自定义因子",
    ],
    "web/src/pages/RiskPage.tsx": [
        "风险控制",
        "风控规则",
        "新建风控规则",
        "规则评估样例",
    ],
    "web/src/pages/BacktestPage.tsx": [
        "策略回测工作台",
        "创建一次策略实验",
        "运行回测",
        "回测失败",
    ],
    "web/src/pages/ScreeningPage.tsx": [
        "智能选股",
        "开始选股",
        "组合策略",
    ],
    "web/src/components/agent/ChatContainer.tsx": [
        "AI 量化研究员",
        "新对话",
    ],
    "web/src/components/agent/ChatInput.tsx": [
        "请先配置 Agent 模型 API Key",
    ],
    "web/src/components/screening/FactorStrategyBuilder.tsx": [
        "保存策略",
        "复制为新策略",
        "策略名称",
        "有未保存修改",
        "策略运行结果",
    ],
    "web/src/components/layout/Sidebar.tsx": [
        "策略配置",
        "策略选择",
        "交易标的",
        "回测区间",
        "风控参数",
        "运行回测",
    ],
    "web/src/components/layout/ScreeningSidebar.tsx": [
        "策略库",
        "策略配置",
        "运行组合策略",
        "开始选股",
    ],
}


def main() -> None:
    missing: list[str] = []
    checked = 0

    for rel_path, expected_texts in CHECKS.items():
        path = ROOT / rel_path
        if not path.exists():
            missing.append(f"{rel_path}: file missing")
            continue
        text = path.read_text(encoding="utf-8")
        checked += 1
        for expected in expected_texts:
            if expected not in text:
                missing.append(f"{rel_path}: missing {expected!r}")

    if missing:
        print("Frontend UI inventory failed:")
        for item in missing:
            print(f"- {item}")
        raise SystemExit(1)

    print(f"Frontend UI inventory passed: {checked} files checked.")


if __name__ == "__main__":
    main()
