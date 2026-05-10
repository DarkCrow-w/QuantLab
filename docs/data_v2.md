# 数据管理模块 v2 — 架构与使用

## 总览

数据层在 v2 中重构为 **Parquet 主存 + DataStore 门面 + 20 TDX 指标内嵌**，
参考通达信（https://help.tdx.com.cn/quant/）的数据组织。

特点：

- **零运维**：不依赖 MySQL/MongoDB/Redis；纯文件 + Python 进程
- **快**：批量读取 ~133k rows/s；单只 5,200 个 parquet 全市场截面 30s
- **指标内嵌**：每个 symbol parquet 同时存 OHLCV + 24 指标列；策略/前端/筛选共用
- **源回退**：TDX → AKShare → Tushare 自动回退；Tushare 严格限流
- **频率**：日 / 周 / 月（周月由日重采样得到，永不外网）
- **复权**：仅前复权（qfq）

## 磁盘布局

```
data/
  market/
    day/{symbol}.parquet     # OHLCV + 20 指标（24 列）
    week/{symbol}.parquet    # 同上，由 day 重采样
    month/{symbol}.parquet
  meta/
    symbols.parquet          # 全 A 股代码、名称、市场、上市日期
    trade_calendar.parquet   # 交易日历 + 周/月收盘标记
    last_update.parquet      # 每只股票最近更新时间、来源
  legacy/                    # 迁移前的扁平 parquet 备份
```

每个 day parquet 文件：
- 列：`dt, open, high, low, close, volume, amount` + 24 个指标列
- 行：~700 条（约 3 年）
- 大小：~120 KB
- 总量：5,205 × 120 KB ≈ 1.6 GB

## 模块结构

```
quant/data/
  __init__.py            # 公共 API 入口
  store.py               # DataStore 单例：统一读写门面
  schema.py              # Freq、列类型、KV-metadata（指标版本号）
  symbols.py             # 600519 / 600519.SH / sh.600519 → 600519 归一化
  indicators.py          # 20 个 TDX 指标，向量化实现
  updater.py             # update_universe / refresh_calendar / derive_week_month
  cache.py               # 兼容垫片（旧 load_cache / save_cache 仍可用）
  feeds/
    base.py              # Source 协议
    store_feed.py        # DataFeed 实现，回测引擎用
    tdx.py               # TDXSource (pytdx)
    akshare.py           # AKShareSource
    tushare.py           # TushareSource
    csv.py               # CSVSource
```

## 公共 API

```python
from quant.data import (
    get_store,            # DataStore 单例
    StoreFeed,            # 回测/实盘用的 DataFeed
    INDICATORS,           # 20 个指标的注册表
    compute, compute_all, # 单/批量指标计算
    update_universe,      # 增量更新（并发 + 源回退）
    derive_week_month,    # 日 → 周/月 重采样
    refresh_calendar,     # 拉取最新交易日历
)
```

读 K 线（含指标）：

```python
store = get_store()
df = store.get_kline("600519", freq="day",
                     start="2024-01-01", end="2026-05-09",
                     with_indicators=True)
# df 含: dt, open, high, low, close, volume, amount,
#       ma5, ma10, ma20, ma60, ema12, ema26, dif, dea, macd,
#       kdj_k, kdj_d, kdj_j, rsi6/12/24, boll_*, bbi, ...
```

读单个指标：

```python
df = store.get_indicator("600519", "MACD")
# df 列: dt, dif, dea, macd
```

更新数据（增量、并发、源回退）：

```python
report = update_universe(workers=8)  # 全市场
print(report.updated, report.failed, report.by_source)
```

回测：

```python
from quant.data import StoreFeed
feed = StoreFeed("2024-01-01", "2026-05-09",
                 with_indicators=["MACD", "KDJ", "BBI"])
feed.subscribe(["600519", "000001"])
# 然后传入 BacktestEngine
```

## 20 个 TDX 指标

| 指标 | 默认参数 | 输出列 |
|---|---|---|
| MA | 5/10/20/60 | ma5, ma10, ma20, ma60 |
| EMA | 12/26 | ema12, ema26 |
| MACD | 12,26,9 | dif, dea, macd |
| KDJ | 9,3,3 | kdj_k, kdj_d, kdj_j |
| RSI | 6/12/24 | rsi6, rsi12, rsi24 |
| BOLL | 20,2 | boll_mid, boll_up, boll_dn |
| BBI | 3,6,12,24 | bbi |
| WR | 10,6 | wr10, wr6 |
| CCI | 14 | cci |
| DMI | 14,6 | pdi, mdi, adx, adxr |
| ATR | 14 | atr |
| OBV | — | obv |
| VOL | 5,10 | mavol5, mavol10 |
| SAR | 4,2,20 | sar |
| TRIX | 12,9 | trix, trix_ma |
| DMA | 10,50,10 | dma, dma_ama |
| EXPMA | 12,50 | expma12, expma50 |
| PSY | 12,6 | psy, psyma |
| MTM | 12,6 | mtm, mtmma |
| ROC | 12,6 | roc, rocma |

KDJ / RSI / DMI 用 Wilder `SMA(M,N) = (N*X + (M-N)*Y_prev)/M` 平滑，与通达信对齐。

## 指标缓存策略

每个 parquet 文件的 KV-metadata 中嵌入 `{column_name: version_key}` 映射：

```
kdj_k → "KDJ:9,3,3@v1"
macd  → "MACD:12,26,9@v1"
...
```

读取时 `get_kline(..., with_indicators=True)` 校验版本一致性：

- 版本号匹配且列存在 → 直接返回（零计算）
- 版本号不匹配或列缺失 → 自动重算缺失/过期的指标 + 原子写回

只需在 `INDICATORS["KDJ"].version` 改为 `"v2"`，下次任意读取都会触发该指标全量重算。

## 数据更新流程

```
update_universe(workers=8)
  ├─ get_store().list_symbols("day")        # 取已有股票池
  ├─ load trade_calendar                     # 跳过非交易日
  ├─ ThreadPoolExecutor(8 workers)
  │    └─ for each symbol:
  │         ├─ check last_dt vs last_trade_date
  │         ├─ try TDX source     (Semaphore=4)
  │         ├─ on fail: AKShare   (Semaphore=2)
  │         ├─ on fail: Tushare   (Semaphore=1, 200ms gap)
  │         ├─ DataStore.upsert_kline → 自动指标重算 + 原子写
  │         └─ update meta/last_update
  └─ UpdateReport(updated/skipped/failed/by_source/elapsed)
```

更新周/月（不走外网）：

```python
derive_week_month(target_freq="week")   # 重采样 day → week
derive_week_month(target_freq="month")
```

刷新交易日历（每周一次足矣）：

```python
refresh_calendar()   # AKShare tool_trade_date_hist_sina
```

## 服务器端 HTTP 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/market/kline` | K 线（支持 freq=day/week/month） |
| GET | `/api/market/indicator/{name}` | 单个指标的时间序列 |
| GET | `/api/market/indicators` | 所有支持的指标列表 |
| GET | `/api/market/universe` | 全市场代码（市场过滤） |
| GET | `/api/market/calendar` | 交易日历 |
| GET | `/api/market/cache` | 已缓存代码 + 日期范围 |
| GET | `/api/market/cache/status` | 含 last_dt/source/ts_updated |
| POST | `/api/market/update` | 旧增量更新（兼容） |
| POST | `/api/market/v2/update` | 新增量更新（DataStore 后端） |
| POST | `/api/market/v2/resample` | 日 → 周/月重采样 |
| POST | `/api/market/v2/refresh-calendar` | 刷新交易日历 |
| POST | `/api/market/v2/refresh-universe` | 刷新代码池 |

## 向后兼容

迁移后这些旧的导入仍然可用：

```python
from quant.data.cache import load_cache, save_cache, CACHE_DIR
from quant.data.akshare_feed import AKShareFeed
from quant.data.tdx_feed import TDXFeed
from quant.data.tushare_feed import TuShareFeed
from quant.data.updater import (
    update_symbol, update_all, list_cached_symbols,
    fetch_all_a_symbols, download_all_a,
)
```

新数据已落到 `data/market/day/`；`load_cache(sym)` 透明读取（去掉指标列保留 OHLCV）。

## 性能基准（个人开发机参考值）

- 单只读（含指标）：avg 7.5ms / p95 13.7ms
- 批量读 100 只：0.56s（133k rows/s）
- 全市场截面 5,205 只：30s
- update_universe（mock 源，8 worker，100 只 × 500 bar）：5.1s
- 指标全量重算：15k rows/s
- 迁移：5,205 × 700 bar
  - copy: 5.9s
  - indicators: 37s
  - resample week: 204s
  - resample month: 184s

## 迁移流程（已完成，仅做参考）

```bash
python scripts/migrate_data_v2.py --dry-run        # 盘点
python scripts/migrate_data_v2.py --stage=copy     # 扁平 → 分频率布局
python scripts/migrate_data_v2.py --stage=meta     # 构建 symbols / calendar / last_update
python scripts/migrate_data_v2.py --stage=indicators  # 计算 24 指标列
python scripts/migrate_data_v2.py --stage=resample    # day → week + month
python scripts/migrate_data_v2.py --stage=flip --confirm  # 旧文件归档到 data/legacy/
```

或者一次性：

```bash
python scripts/migrate_data_v2.py --all
```

## 风险与已知限制

- **qfq 因子漂移**：分红除权时 Tushare 会重算 `adj_factor`，历史价格随之全部变化。
  当前增量更新只追加新数据，不回填历史。如需修复：`update_universe(force=True)` 强制全量重拉。
- **数据源失败重试**：单只股票回退到 Tushare 后若再失败，标记 failed 并继续；
  不会无限重试。
- **指标重算开销**：`get_kline(with_indicators=True)` 在版本不匹配时会写回文件。
  并发读同一只股票时由 `_lock` 串行化避免重复重算。
- **DuckDB 未启用**：`query.py` 已预留位置但 v1 未实现；如需 SQL 截面查询可加 `pip install duckdb` 后扩展。
