"""A 股代码归一化与市场识别。

各数据源对代码的格式要求不一致：
- TDX: 6 位纯数字 + 单独的 market 整数 (0=深, 1=沪)
- AKShare: 6 位纯数字
- Tushare: ``600519.SH`` / ``300750.SZ``
- 旧代码偶尔出现 ``sh.600519`` / ``sh600519``

本模块提供单一归一化点，所有 Source 在调用网络前转换。
"""
from __future__ import annotations

import re

# Shanghai stock prefixes: 6 (主板), 5 (基金), 9 (B股), 7 (新股申购占位).
_SH_PREFIXES = ("6", "5", "9", "7")
# Shenzhen stock prefixes: 0 (主板/中小板), 3 (创业板), 2 (B股).
_SZ_PREFIXES = ("0", "3", "2")
# Beijing exchange (北交所) prefixes.
_BJ_PREFIXES = ("4", "8")

_SUFFIX_RE = re.compile(r"\.(sh|sz|bj)$", re.IGNORECASE)
_PREFIX_RE = re.compile(r"^(sh|sz|bj)\.?", re.IGNORECASE)


def normalize(symbol: str) -> str:
    """Strip any prefix/suffix to a plain 6-digit code.

    >>> normalize("600519")
    '600519'
    >>> normalize("600519.SH")
    '600519'
    >>> normalize("sh.600519")
    '600519'
    >>> normalize("sh600519")
    '600519'
    """
    if symbol is None:
        raise ValueError("symbol is None")
    s = symbol.strip()
    s = _SUFFIX_RE.sub("", s)
    s = _PREFIX_RE.sub("", s)
    if not s.isdigit() or len(s) != 6:
        raise ValueError(f"invalid A-share code: {symbol!r}")
    return s


def market(symbol: str) -> str:
    """Return ``SH`` / ``SZ`` / ``BJ`` for a normalized code."""
    code = normalize(symbol)
    if code.startswith(_SH_PREFIXES):
        return "SH"
    if code.startswith(_SZ_PREFIXES):
        return "SZ"
    if code.startswith(_BJ_PREFIXES):
        return "BJ"
    raise ValueError(f"unknown market for code: {symbol!r}")


def to_ts_code(symbol: str) -> str:
    """Tushare 风格：``600519.SH``。"""
    code = normalize(symbol)
    return f"{code}.{market(code)}"


def to_tdx_market(symbol: str) -> int:
    """pytdx 的 market 整数：0=深, 1=沪。北交所暂归到 0 (pytdx 实际不返回)。"""
    m = market(symbol)
    return 1 if m == "SH" else 0
