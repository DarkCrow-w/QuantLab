"""把存量 parquet 的 volume 单位统一到「股」。

背景：AKShare 数据源在 quant/data/feeds/akshare.py 和 quant/data/akshare_feed.py
里曾经没有把「成交量(手)」乘 100 转成股，导致部分日期/股票的 vol 是手而不是股。
反映到前端 K 线图就是 2026-04-02 起成交量副图柱子高度突然缩小约 100 倍。

修复策略：对每行用 ratio = amount / (volume * close) 判断单位
  - ratio ∈ [0.5, 2.5]   → 已经是股，跳过
  - ratio ∈ [50, 200]    → 是手，volume *= 100
  - 其它（含 vol=0 / amt=0 停牌行）→ 跳过，记录警告

写入前会把原文件备份到 data/_volume_fix_backup/{symbol}.parquet。

用法：
  /root/quant/.venv/bin/python scripts/fix_volume_units.py --dry-run    # 只报告
  /root/quant/.venv/bin/python scripts/fix_volume_units.py              # 真改
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

DAY_DIR = Path("/root/quant/data/market/day")
BACKUP_DIR = Path("/root/quant/data/_volume_fix_backup")


def classify_row(amt: float, vol: float, close: float) -> str:
    if vol <= 0 or amt <= 0 or close <= 0:
        return "skip"
    ratio = amt / (vol * close)
    if 0.5 <= ratio <= 2.5:
        return "shares"
    if 50 <= ratio <= 200:
        return "lots"
    return "ambiguous"


def fix_one(path: Path, dry_run: bool) -> dict:
    """读 parquet → 修 vol → 写回（保留所有原列 + parquet kv-metadata）。"""
    table = pq.read_table(path)
    df = table.to_pandas()
    if df.empty:
        return {"file": path.name, "rows": 0, "fixed": 0, "skipped": 0, "ambiguous": 0}

    classes = [
        classify_row(a, v, c)
        for a, v, c in zip(df["amount"], df["volume"], df["close"])
    ]
    n_lots = sum(1 for x in classes if x == "lots")
    n_skip = sum(1 for x in classes if x == "skip")
    n_amb = sum(1 for x in classes if x == "ambiguous")

    if n_lots == 0:
        return {"file": path.name, "rows": len(df), "fixed": 0,
                "skipped": n_skip, "ambiguous": n_amb}

    if not dry_run:
        # 备份原文件
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup = BACKUP_DIR / path.name
        if not backup.exists():
            shutil.copy2(path, backup)

        # 用 numpy 改 vol，注意保持列 dtype
        new_vol = df["volume"].astype(float).copy()
        for i, c in enumerate(classes):
            if c == "lots":
                new_vol.iat[i] = new_vol.iat[i] * 100
        df["volume"] = new_vol

        # 写回，保留原 schema 的 kv-metadata（指标版本号等）
        new_table = pa.Table.from_pandas(df, preserve_index=False)
        # 把原文件的 schema metadata 合并进来
        orig_md = table.schema.metadata or {}
        new_md = new_table.schema.metadata or {}
        merged = {**dict(new_md), **dict(orig_md)}
        new_table = new_table.replace_schema_metadata(merged)
        pq.write_table(new_table, path, compression="snappy")

    return {"file": path.name, "rows": len(df), "fixed": n_lots,
            "skipped": n_skip, "ambiguous": n_amb}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只报告，不写")
    ap.add_argument("--limit", type=int, default=None, help="只处理前 N 个文件（调试）")
    args = ap.parse_args()

    files = sorted(DAY_DIR.glob("*.parquet"))
    if args.limit:
        files = files[: args.limit]

    if not files:
        print(f"no parquets in {DAY_DIR}", file=sys.stderr)
        sys.exit(1)

    print(f"扫描 {len(files)} 个 parquet @ {DAY_DIR}")
    print(f"模式: {'DRY-RUN（不写）' if args.dry_run else f'修复 + 备份到 {BACKUP_DIR}'}")
    print()

    total_files = total_rows = total_fixed = total_amb = files_changed = 0
    samples: list[dict] = []

    for i, p in enumerate(files):
        try:
            r = fix_one(p, dry_run=args.dry_run)
        except Exception as e:
            print(f"  ✗ {p.name}: {e}")
            continue
        total_files += 1
        total_rows += r["rows"]
        total_fixed += r["fixed"]
        total_amb += r["ambiguous"]
        if r["fixed"] > 0:
            files_changed += 1
            if len(samples) < 5:
                samples.append(r)
        if (i + 1) % 500 == 0:
            print(f"  已处理 {i+1}/{len(files)}", flush=True)

    print()
    print(f"总文件:        {total_files}")
    print(f"修了 vol 的:   {files_changed} 个文件 / {total_fixed} 行")
    print(f"模糊行:        {total_amb}（既不像股也不像手，已跳过）")
    print(f"总行数:        {total_rows}")
    print()
    if samples:
        print("样例：")
        for s in samples:
            print(f"  {s}")
    if args.dry_run:
        print("\n--dry-run 模式：未实际修改文件。去掉 --dry-run 真跑。")


if __name__ == "__main__":
    main()
