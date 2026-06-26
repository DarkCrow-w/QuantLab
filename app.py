#!/usr/bin/env python3
"""Streamlit quick backtest entry for QuantLab."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from server.models.backtest import BacktestRequest
from server.services.backtest_service import get_strategy_list, run_backtest


def _default_params(strategy_name: str) -> dict:
    for strategy in get_strategy_list():
        if strategy.name == strategy_name:
            return {item.name: item.default for item in strategy.params_schema}
    return {}


def _render_kline(symbol: str, bars: list) -> None:
    if not bars:
        st.info(f"{symbol} 没有可展示的 K 线数据。")
        return
    frame = pd.DataFrame([bar.model_dump() for bar in bars])
    fig = go.Figure(
        data=[
            go.Candlestick(
                x=frame["dt"],
                open=frame["open"],
                high=frame["high"],
                low=frame["low"],
                close=frame["close"],
                name=symbol,
            )
        ]
    )
    fig.update_layout(height=420, margin=dict(l=20, r=20, t=32, b=20), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)


def _render_equity(equity_curve: list) -> None:
    if not equity_curve:
        st.info("没有权益曲线数据。")
        return
    frame = pd.DataFrame([point.model_dump() for point in equity_curve])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=frame["dt"], y=frame["equity"], mode="lines", name="权益"))
    fig.update_layout(height=320, margin=dict(l=20, r=20, t=32, b=20))
    st.plotly_chart(fig, use_container_width=True)


st.set_page_config(page_title="QuantLab 快速回测", layout="wide")
st.title("QuantLab 快速回测")
st.caption("这是保留给本地快速实验的 Streamlit 入口；完整系统请使用 React 控制台。")

strategies = get_strategy_list()
strategy_options = {f"{item.display_name} ({item.name})": item.name for item in strategies}

with st.sidebar:
    st.header("参数设置")
    symbols_input = st.text_input("股票代码，多个用逗号分隔", value="600519")
    symbols = [item.strip() for item in symbols_input.split(",") if item.strip()]

    col_start, col_end = st.columns(2)
    with col_start:
        start_date = st.date_input("开始日期", value=pd.to_datetime("2023-01-01"))
    with col_end:
        end_date = st.date_input("结束日期", value=pd.to_datetime("2024-12-31"))

    strategy_label = st.selectbox("策略", list(strategy_options))
    strategy_name = strategy_options[strategy_label]

    st.subheader("策略参数")
    strategy_params = _default_params(strategy_name)
    for item in next(s for s in strategies if s.name == strategy_name).params_schema:
        if item.type == "float":
            strategy_params[item.name] = st.number_input(
                item.label,
                min_value=float(item.min) if item.min is not None else None,
                max_value=float(item.max) if item.max is not None else None,
                value=float(strategy_params[item.name]),
                step=0.01,
            )
        else:
            strategy_params[item.name] = st.number_input(
                item.label,
                min_value=int(item.min) if item.min is not None else None,
                max_value=int(item.max) if item.max is not None else None,
                value=int(strategy_params[item.name]),
                step=1,
            )

    st.subheader("资金与风控")
    initial_cash = st.number_input("初始资金", value=1_000_000.0, step=100_000.0, format="%.0f")
    max_position_pct = st.slider("单票最大仓位", 0.05, 1.0, 0.3, 0.05)
    max_drawdown = st.slider("最大回撤熔断", 0.05, 0.5, 0.2, 0.05)
    run_clicked = st.button("开始回测", type="primary", use_container_width=True)

if run_clicked:
    if not symbols:
        st.error("请至少输入一个股票代码。")
        st.stop()

    request = BacktestRequest(
        symbols=symbols,
        start_date=str(start_date),
        end_date=str(end_date),
        strategy=strategy_name,
        strategy_params=strategy_params,
        initial_cash=initial_cash,
        max_position_pct=max_position_pct,
        max_drawdown=max_drawdown,
    )
    with st.spinner("正在运行回测..."):
        st.session_state["backtest_result"] = run_backtest(request)
        st.session_state["backtest_request"] = request

result = st.session_state.get("backtest_result")
request = st.session_state.get("backtest_request")

if result is None:
    st.info("在左侧设置参数后点击“开始回测”。")
    st.stop()

metrics = result.metrics
cols = st.columns(5)
cols[0].metric("最终权益", f"{metrics.final_equity:,.0f}")
cols[1].metric("总收益", f"{metrics.total_return:.2%}")
cols[2].metric("年化收益", f"{metrics.annual_return:.2%}")
cols[3].metric("最大回撤", f"{metrics.max_drawdown:.2%}")
cols[4].metric("交易次数", str(metrics.trade_count))

tab_equity, tab_kline, tab_trades, tab_request = st.tabs(["权益曲线", "K线", "交易记录", "请求参数"])

with tab_equity:
    _render_equity(result.equity_curve)

with tab_kline:
    selected_symbol = st.selectbox("标的", list(result.kline_data.keys()))
    _render_kline(selected_symbol, result.kline_data.get(selected_symbol, []))

with tab_trades:
    if result.trades:
        st.dataframe(pd.DataFrame([trade.model_dump() for trade in result.trades]), use_container_width=True)
    else:
        st.info("本次回测没有成交记录。")

with tab_request:
    st.json(request.model_dump() if request else {})
