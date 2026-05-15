# Data Module Architecture

## Storage layout

The data layer uses a hybrid design:

- Parquet remains the source of truth for OHLCV and materialized indicators.
- `data/meta/catalog.sqlite3` stores file metadata: symbol, frequency,
  first/last date, row count, source, update timestamp, and file mtime. It also
  keeps one JSON snapshot row per symbol for fast all-market latest queries.
- `data/meta/jobs.sqlite3` stores download/update jobs and recent per-symbol
  results. Progress survives page refreshes and interrupted backend processes
  are marked explicitly after restart.
- New Parquet writes use 256-row groups so recent-window reads can skip old
  row groups.

SQLite is intentionally not used for all K-line values. The dominant workloads
scan selected columns across many symbols, which is better served by Parquet's
columnar layout. SQLite removes the expensive small metadata reads that were
previously performed by opening every Parquet file.

## Read path

`DataStore.get_kline()` supports:

- `columns`: Parquet column projection.
- `start` and `end`: predicate filtering before pandas conversion.
- `tail`: trailing row-group selection followed by an exact row limit.
- `with_indicators`: version checking and on-demand materialization.

Normal reads no longer take a process-wide lock. Indicator rewrites use a
per-file lock, so unrelated symbols can be processed concurrently.

## Write path

`upsert_kline()` reads only old OHLCV columns, merges incoming bars, recomputes
indicators, atomically replaces the Parquet file, and updates SQLite in one
short metadata transaction. It does not retain the old indicator panel during
the merge.

Bulk-download API requests default to deferred indicator materialization. This
keeps network ingestion fast and writes OHLCV immediately; the first
`with_indicators=True` read materializes the current indicator panel. Direct
`update_universe()` calls retain the compatible eager-materialization default.

## Concurrency and memory

Large executor workloads use `bounded_futures()`. At most `workers * 2` tasks
are submitted at once instead of creating more than 5,000 futures immediately.
Interactive data jobs are single-flight: only one update or download may run
at once. TDX/AKShare use at most two workers and TuShare/Baostock are forced to
one worker. This keeps Parquet rewrites and Arrow allocations within a stable
memory budget.

TDX incremental requests stop paging once the requested start date is covered.
Working hosts are remembered, failed hosts enter a cooldown window, and each
connection performs only a bounded number of host attempts.

The trading calendar and the SQLite last-date snapshot are loaded once per
universe update. Each worker receives the cached last date instead of opening
the symbol's full history.

## Compatibility and maintenance

Existing public methods remain compatible. Callers that need the old complete
panel can omit `columns` and `tail`.

Build or refresh the catalog with:

```bash
python scripts/migrate_data_v2.py --stage=catalog
```

Warm the persistent latest-row snapshots for existing files with:

```bash
python scripts/migrate_data_v2.py --stage=snapshots
```

Existing Parquet files continue to work. They gain the smaller row-group layout
the next time they are written; a full data rewrite is not required.
