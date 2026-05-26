#!/usr/bin/env python3
"""Repair cached K-line rows whose volume was stored in TDX lots."""
from __future__ import annotations

import argparse
import time

from quant.data import indicators
from quant.data.schema import safe_write_parquet, volume_rows_in_hands
from quant.data.store import get_store


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--freq",
        choices=("day", "week", "month", "all"),
        default="all",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    store = get_store()
    frequencies = ("day", "week", "month") if args.freq == "all" else (args.freq,)
    scanned = changed_files = changed_rows = 0
    started = time.monotonic()

    for freq in frequencies:
        symbols = store.list_symbols(freq)
        for index, symbol in enumerate(symbols, start=1):
            scanned += 1
            frame = store.get_kline(symbol, freq=freq)
            mask = volume_rows_in_hands(frame)
            count = int(mask.sum())
            if count:
                changed_files += 1
                changed_rows += count
                if not args.dry_run:
                    path = store.kline_path(symbol, freq)
                    with store._path_lock(path):
                        frame, versions = store._read_with_versions(path)
                        mask = volume_rows_in_hands(frame)
                        frame.loc[mask, "volume"] *= 100
                        for name in ("OBV", "VOL"):
                            computed = indicators.compute(name, frame)
                            for column in computed.columns:
                                if column in frame.columns:
                                    frame[column] = computed[column].to_numpy()
                        present_versions = {
                            column: version
                            for column, version in indicators.indicator_versions(
                                ["OBV", "VOL"]
                            ).items()
                            if column in frame.columns
                        }
                        versions.update(present_versions)
                        safe_write_parquet(
                            frame,
                            path,
                            indicator_versions=versions,
                        )
                        store._index_frame(symbol, freq, frame, "")
            if index % 250 == 0 or index == len(symbols):
                print(
                    f"{freq}: {index}/{len(symbols)}, "
                    f"changed_files={changed_files}, changed_rows={changed_rows}",
                    flush=True,
                )

    print(
        f"done: scanned={scanned}, changed_files={changed_files}, "
        f"changed_rows={changed_rows}, elapsed_s={time.monotonic() - started:.2f}, "
        f"dry_run={args.dry_run}",
        flush=True,
    )


if __name__ == "__main__":
    main()
