#!/usr/bin/env python3
"""Run a bounded real-data smoke test against the TDX updater."""
from __future__ import annotations

import argparse
import json
import time
from datetime import date

from quant.data.store import get_store
from quant.data.updater import update_symbols


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--stale-only", action="store_true")
    parser.add_argument("--symbols", help="Comma-separated symbols to test")
    args = parser.parse_args()

    store = get_store()
    if args.symbols:
        symbols = [
            symbol.strip().zfill(6)
            for symbol in args.symbols.split(",")
            if symbol.strip()
        ]
    else:
        universe = store.get_universe()
        symbols = universe["symbol"].astype(str).str.zfill(6).tolist()
        if args.stale_only:
            last_dates = store.get_last_dates(symbols, "day")
            today = date.today()
            symbols = [
                symbol
                for symbol in symbols
                if last_dates.get(symbol) is None or last_dates[symbol] < today
            ]
    symbols = symbols[: args.limit]
    started = time.monotonic()
    rows = update_symbols(
        symbols,
        source="tdx",
        max_workers=args.workers,
        delay=0,
        fallback_sources=False,
    )
    print(
        json.dumps(
            {
                "elapsed_s": round(time.monotonic() - started, 2),
                "total": len(rows),
                "updated": sum(row["status"] == "updated" for row in rows),
                "skipped": sum(
                    row["status"] in {"up_to_date", "no_new_data"}
                    for row in rows
                ),
                "failed": sum(row["status"] == "error" for row in rows),
                "errors": [
                    row for row in rows if row["status"] == "error"
                ][:5],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
