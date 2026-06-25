#!/usr/bin/env python3
"""量化回测可视化前端"""
from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from quant.data.akshare_feed import AKShareFeed
from quant.engine.backtest import BacktestEngine
from quant.execution.simulated import SimulatedBroker
from quant.risk.basic import BasicRiskManager
from quant.strategy.registry import BASIC_STRATEGY_CLASSES, STRATEGY_DISPLAY_NAMES

STRATEGY_MAP = {
    STRATEGY_DISPLAY_NAMES[name]: cls
    for name, cls in BASIC_STRATEGY_CLASSES.items()
}

st.set_page_config(page_title="量化回测", layout="wide", page_icon="📈")
st.title("📈 量化回测系统")

# ── 侧边栏 ──────────────────────────────────────────────
with st.sidebar:
    st.header("参数设置")

    symbols_input = st.text_input("股票代码（多只用逗号分隔）", value="600519")
    symbols = [s.strip() for s in symbols_input.split(",") if s.strip()]

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("开始日期", value=pd.to_datetime("2023-01-01"))
    with col2:
        end_date = st.date_input("结束日期", value=pd.to_datetime("2024-12-31"))

    st.subheader("策略")
    strategy_name = st.selectbox("选择策略", list(STRATEGY_MAP.keys()))
    fast_period = st.slider("快线周期", 2, 60, 5)
    slow_period = st.slider("慢线周期", 5, 120, 20)

    st.subheader("资金与风控")
    initial_cash = st.number_input("初始资金", value=1_000_000, step=100_000, format="%d")
    max_pos_pct = st.slider("单票最大仓位", 0.05, 1.0, 0.3, 0.05)
    max_drawdown = st.slider("最大回撤熔断", 0.05, 0.5, 0.2, 0.05)

    run_btn = st.button("🚀 开始回测", type="primary", use_container_width=True)


# ── 回测执行 ─────────────────────────────────────────────
if run_btn:
    if fast_period >= slow_period:
        st.error("快线周期必须小于慢线周期")
        st.stop()

    with st.spinner("正在获取数据并回测..."):
        feed = AKShareFeed(
            start_date=str(start_date),
            end_date=str(end_date),
            use_cache=True,
        )
        feed.subscribe(symbols)

        strategy = STRATEGY_MAP[strategy_name](
            params={"fast_period": fast_period, "slow_period": slow_period}
        )
        risk_manager = BasicRiskManager(
            max_position_pct=max_pos_pct, max_drawdown=max_drawdown,
        )
        broker = SimulatedBroker()
        engine = BacktestEngine(
            feed=feed, strategy=strategy, risk_manager=risk_manager,
            broker=broker, initial_cash=initial_cash,
        )
        eq_df = engine.run()
        trades_df = engine.get_trades()

    # 存到 session_state 以便不重跑也能看
    st.session_state["eq_df"] = eq_df
    st.session_state["trades_df"] = trades_df
    st.session_state["engine"] = engine
    st.session_state["feed"] = feed
    st.session_state["symbols"] = symbols


# ── 结果展示 ─────────────────────────────────────────────
if "engine" not in st.session_state:
    st.info("👈 在左侧设置参数后点击「开始回测」")
    st.stop()

engine: BacktestEngine = st.session_state["engine"]
eq_df: pd.DataFrame = st.session_state["eq_df"]
trades_df: pd.DataFrame = st.session_state["trades_df"]
feed: AKShareFeed = st.session_state["feed"]
symbols = st.session_state["symbols"]

# ── 绩效摘要 ─────────────────────────────────────────────
initial = engine.portfolio.initial_cash
final = eq_df["equity"].iloc[-1] if not eq_df.empty else initial
ret = (final - initial) / initial
peak = eq_df["equity"].cummax()
dd = ((eq_df["equity"] - peak) / peak).min()
days = (eq_df.index[-1] - eq_df.index[0]).days if len(eq_df) > 1 else 1
ann_ret = (1 + ret) ** (365 / max(days, 1)) - 1

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("最终权益", f"¥{final:,.0f}")
c2.metric("总收益", f"{ret:.2%}", delta=f"{ret:.2%}")
c3.metric("年化收益", f"{ann_ret:.2%}")
c4.metric("最大回撤", f"{dd:.2%}")
c5.metric("交易次数", f"{len(trades_df)}")

# ── K线图 ────────────────────────────────────────────────
for sym in symbols:
    st.subheader(f"K线图 — {sym}")
    raw = feed._data.get(sym)
    if raw is None:
        continue

    df = raw.copy()
    df["dt"] = pd.to_datetime(df["dt"])

    # 计算均线
    df["ma_fast"] = df["close"].rolling(fast_period).mean()
    df["ma_slow"] = df["close"].rolling(slow_period).mean()

    # 买卖点
    if not trades_df.empty:
        sym_trades = trades_df[trades_df["symbol"] == sym].copy()
        sym_trades["dt"] = pd.to_datetime(sym_trades["dt"])
        buys = sym_trades[sym_trades["side"] == "BUY"]
        sells = sym_trades[sym_trades["side"] == "SELL"]
    else:
        buys = sells = pd.DataFrame()

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )

    # K线
    fig.add_trace(go.Candlestick(
        x=df["dt"], open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        name="K线",
        increasing_line_color="#ef5350",   # 中国习惯：涨红
        decreasing_line_color="#26a69a",   # 跌绿
        increasing_fillcolor="#ef5350",
        decreasing_fillcolor="#26a69a",
    ), row=1, col=1)

    # 均线
    fig.add_trace(go.Scatter(
        x=df["dt"], y=df["ma_fast"],
        name=f"MA{fast_period}", line=dict(width=1.2, color="#ff9800"),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df["dt"], y=df["ma_slow"],
        name=f"MA{slow_period}", line=dict(width=1.2, color="#2196f3"),
    ), row=1, col=1)

    # 买卖标记
    if not buys.empty:
        fig.add_trace(go.Scatter(
            x=buys["dt"], y=buys["price"],
            mode="markers", name="买入",
            marker=dict(symbol="triangle-up", size=12, color="#ff1744",
                        line=dict(width=1, color="white")),
        ), row=1, col=1)
    if not sells.empty:
        fig.add_trace(go.Scatter(
            x=sells["dt"], y=sells["price"],
            mode="markers", name="卖出",
            marker=dict(symbol="triangle-down", size=12, color="#00e676",
                        line=dict(width=1, color="white")),
        ), row=1, col=1)

    # 成交量
    colors = ["#ef5350" if c >= o else "#26a69a"
              for c, o in zip(df["close"], df["open"])]
    fig.add_trace(go.Bar(
        x=df["dt"], y=df["volume"], name="成交量",
        marker_color=colors, opacity=0.5,
    ), row=2, col=1)

    fig.update_layout(
        height=650,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        margin=dict(l=0, r=0, t=30, b=0),
    )
    fig.update_yaxes(title_text="价格", row=1, col=1)
    fig.update_yaxes(title_text="成交量", row=2, col=1)

    # 隐去非交易日空白
    fig.update_xaxes(
        rangebreaks=[dict(bounds=["sat", "mon"])],
    )

    st.plotly_chart(fig, use_container_width=True)

# ── 权益曲线 ─────────────────────────────────────────────
st.subheader("权益曲线")
fig_eq = go.Figure()
fig_eq.add_trace(go.Scatter(
    x=eq_df.index, y=eq_df["equity"],
    fill="tozeroy", fillcolor="rgba(33,150,243,0.1)",
    line=dict(color="#2196f3", width=2),
    name="权益",
))
fig_eq.add_hline(y=initial, line_dash="dash", line_color="gray",
                 annotation_text=f"初始资金 ¥{initial:,.0f}")
fig_eq.update_layout(
    height=350,
    template="plotly_dark",
    margin=dict(l=0, r=0, t=10, b=0),
    yaxis_title="权益（元）",
)
st.plotly_chart(fig_eq, use_container_width=True)

# ── 交易记录 ─────────────────────────────────────────────
st.subheader("交易记录")
if not trades_df.empty:
    display_df = trades_df.copy()
    display_df.columns = ["日期", "股票", "方向", "数量", "成交价", "手续费"]
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.info("无交易记录")
