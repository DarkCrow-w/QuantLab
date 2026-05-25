#!/usr/bin/env python3
"""Inspect quote and bar availability for selected TDX symbols."""
from __future__ import annotations

import argparse
import json

from pytdx.hq import TdxHq_API

from quant.data.feeds.tdx import refresh_hosts
from quant.data.store import get_store
from quant.data.symbols import to_tdx_market


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("symbols", nargs="+")
    args = parser.parse_args()

    store = get_store()
    universe = store.get_universe()
    names = {}
    if not universe.empty:
        names = {
            str(row["symbol"]).zfill(6): row.to_dict()
            for _, row in universe.iterrows()
        }

    host = refresh_hosts()[0]
    api = TdxHq_API(auto_retry=False, raise_exception=False)
    if api.connect(*host, time_out=2) is False:
        raise SystemExit(f"Unable to connect to {host}")
    try:
        for symbol in args.symbols:
            symbol = symbol.zfill(6)
            market = to_tdx_market(symbol)
            quote = api.get_security_quotes([(market, symbol)])
            bars = {
                str(category): len(
                    api.get_security_bars(category, market, symbol, 0, 32) or []
                )
                for category in (4, 5, 6, 7, 8, 9)
            }
            print(
                json.dumps(
                    {
                        "symbol": symbol,
                        "universe": names.get(symbol, {}),
                        "last_date": str(store.get_last_date(symbol, "day")),
                        "quote": quote,
                        "bars_by_category": bars,
                    },
                    ensure_ascii=False,
                    default=str,
                )
            )
    finally:
        api.disconnect()


if __name__ == "__main__":
    main()
