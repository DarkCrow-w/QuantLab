"""Utilities for keeping equity universes free of indices and board codes."""
from __future__ import annotations


_SH_A_PREFIXES = ("600", "601", "603", "605", "688", "689")
_SZ_A_PREFIXES = ("000", "001", "002", "003", "300", "301")
_BJ_A_PREFIXES = ("430", "830", "831", "832", "833", "834", "835", "836", "837", "838", "839", "870", "871", "872", "873", "920")


def is_a_share_symbol(symbol: object, include_bj: bool = True) -> bool:
    """Return True for ordinary listed A-share stock codes.

    This deliberately excludes broad index, board, fund and B-share ranges such
    as 39xxxx, 50xxxx, 90xxxx, because those can appear in provider security
    lists and break "download all stocks" jobs.
    """
    code = str(symbol or "").strip()
    if "." in code:
        left, right = code.split(".", 1)
        code = left if left.isdigit() else right
    code = code.zfill(6)
    if not code.isdigit() or len(code) != 6:
        return False
    prefixes = _SH_A_PREFIXES + _SZ_A_PREFIXES + (_BJ_A_PREFIXES if include_bj else ())
    return code.startswith(prefixes)


def filter_a_share_rows(rows: list[dict], include_bj: bool = True) -> list[dict]:
    """Deduplicate and filter provider symbol records to tradable A-share rows."""
    seen: set[str] = set()
    filtered: list[dict] = []
    for row in rows:
        code = str(row.get("symbol", "")).strip()
        if "." in code:
            left, right = code.split(".", 1)
            code = left if left.isdigit() else right
        code = code.zfill(6)
        if not is_a_share_symbol(code, include_bj=include_bj) or code in seen:
            continue
        next_row = dict(row)
        next_row["symbol"] = code
        if not next_row.get("market"):
            if code.startswith(("4", "8", "920")):
                next_row["market"] = "BJ"
            elif code.startswith("6"):
                next_row["market"] = "SH"
            else:
                next_row["market"] = "SZ"
        filtered.append(next_row)
        seen.add(code)
    return filtered
