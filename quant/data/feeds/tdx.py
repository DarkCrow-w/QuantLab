"""TongDaXin daily-bar source backed by the pytdx quote protocol."""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from loguru import logger

from quant.config import PROJECT_ROOT, get_settings
from ..symbols import market as symbol_market
from ..symbols import normalize, to_tdx_market

_FALLBACK_HOSTS = [
    ("180.153.18.172", 80),
    ("180.153.18.170", 7709),
    ("115.238.90.165", 7709),
    ("60.191.117.167", 7709),
    ("115.238.56.198", 7709),
    ("218.75.126.9", 7709),
    ("60.12.136.250", 7709),
]
_HOST_CACHE_PATH = PROJECT_ROOT / "data" / "meta" / "tdx_hosts.json"
_HOST_STATE_LOCK = threading.RLock()
_HOST_PROBE_LOCK = threading.Lock()
_THREAD_SESSION = threading.local()
_RANKED_HOSTS: list[tuple[str, int]] = []
_FAILED_UNTIL: dict[tuple[str, int], float] = {}
_EMPTY_COUNTS: dict[tuple[str, int], int] = {}
_HOST_CURSOR = 0


class TDXError(RuntimeError):
    """Base error for the pytdx transport."""


class TDXUnsupportedMarketError(TDXError):
    """The pytdx SH/SZ quote protocol cannot serve this market."""


class TDXNoDataError(TDXError):
    """All attempted servers returned no raw bars for a valid SH/SZ symbol."""


def _candidate_hosts() -> list[tuple[str, int]]:
    settings = get_settings().tdx
    if settings.host:
        return [(settings.host, settings.port)]
    hosts: list[tuple[str, int]] = []
    try:
        from pytdx.config.hosts import hq_hosts

        hosts.extend((str(ip), int(port)) for _, ip, port in hq_hosts)
    except Exception:
        pass
    hosts.extend(_FALLBACK_HOSTS)
    return list(dict.fromkeys(hosts))


def _probe_host(host: tuple[str, int]) -> tuple[float, tuple[str, int]] | None:
    from pytdx.hq import TdxHq_API

    timeout = get_settings().tdx.probe_timeout
    api = TdxHq_API(auto_retry=False, raise_exception=False)
    started = time.monotonic()
    try:
        if api.connect(*host, time_out=timeout) is False:
            return None
        rows = api.get_security_bars(9, 1, "600519", 0, 2)
        if not rows:
            return None
        return time.monotonic() - started, host
    except Exception:
        return None
    finally:
        try:
            api.disconnect()
        except Exception:
            pass


def _read_host_cache() -> list[tuple[str, int]]:
    settings = get_settings().tdx
    try:
        payload = json.loads(_HOST_CACHE_PATH.read_text(encoding="utf-8"))
        age = time.time() - float(payload["updated_at"])
        if age > settings.host_cache_seconds:
            return []
        return [
            (str(item["host"]), int(item["port"]))
            for item in payload["hosts"]
        ]
    except Exception:
        return []


def _write_host_cache(hosts: list[tuple[str, int]]) -> None:
    try:
        _HOST_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _HOST_CACHE_PATH.write_text(
            json.dumps(
                {
                    "updated_at": time.time(),
                    "hosts": [
                        {"host": host, "port": port}
                        for host, port in hosts
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except Exception as exc:
        logger.debug(f"Unable to persist TDX host cache: {exc}")


def refresh_hosts(force: bool = False) -> list[tuple[str, int]]:
    """Probe quote servers once and retain the fastest validated endpoints."""
    global _RANKED_HOSTS
    settings = get_settings().tdx
    if _RANKED_HOSTS and not force:
        return list(_RANKED_HOSTS)
    with _HOST_PROBE_LOCK:
        if _RANKED_HOSTS and not force:
            return list(_RANKED_HOSTS)
        cached = [] if force else _read_host_cache()
        if cached:
            _RANKED_HOSTS = cached
            return list(_RANKED_HOSTS)

        candidates = _candidate_hosts()
        results: list[tuple[float, tuple[str, int]]] = []
        workers = min(settings.probe_workers, len(candidates))
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = [executor.submit(_probe_host, host) for host in candidates]
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    results.append(result)
        results.sort(key=lambda item: item[0])
        ranked = [host for _, host in results[: settings.active_hosts]]
        if not ranked:
            ranked = _FALLBACK_HOSTS[: settings.active_hosts]
        _RANKED_HOSTS = ranked
        _write_host_cache(ranked)
        logger.info(
            f"TDX host probe selected {len(ranked)} of {len(candidates)} endpoints"
        )
        return list(_RANKED_HOSTS)


def _next_host() -> tuple[str, int]:
    global _HOST_CURSOR
    hosts = refresh_hosts()
    now = time.monotonic()
    with _HOST_STATE_LOCK:
        healthy = [host for host in hosts if _FAILED_UNTIL.get(host, 0) <= now]
        candidates = healthy or hosts
        host = candidates[_HOST_CURSOR % len(candidates)]
        _HOST_CURSOR += 1
        return host


def _connect_api():
    from pytdx.hq import TdxHq_API

    settings = get_settings().tdx
    attempts = min(settings.max_host_attempts, max(1, len(refresh_hosts())))
    errors: list[str] = []
    for _ in range(attempts):
        host = _next_host()
        api = TdxHq_API(auto_retry=False, raise_exception=False)
        try:
            if api.connect(*host, time_out=settings.connect_timeout) is not False:
                setattr(api, "_quant_host", host)
                logger.debug(f"TDX connected: {host[0]}:{host[1]}")
                return api
            errors.append(f"{host[0]}:{host[1]} refused")
        except Exception as exc:
            errors.append(f"{host[0]}:{host[1]} {exc}")
        _mark_host_failed(host)
    raise ConnectionError(
        "无法连接到可用的通达信行情服务器"
        + (f" ({'; '.join(errors[-3:])})" if errors else "")
    )


def _mark_host_failed(host: tuple[str, int] | None) -> None:
    if host is None:
        return
    with _HOST_STATE_LOCK:
        _FAILED_UNTIL[host] = (
            time.monotonic() + get_settings().tdx.host_cooldown
        )


def _record_empty_response(host: tuple[str, int] | None) -> None:
    if host is None:
        return
    threshold = get_settings().tdx.empty_response_threshold
    with _HOST_STATE_LOCK:
        count = _EMPTY_COUNTS.get(host, 0) + 1
        _EMPTY_COUNTS[host] = count
        if count >= threshold:
            _FAILED_UNTIL[host] = (
                time.monotonic() + get_settings().tdx.host_cooldown
            )
            _EMPTY_COUNTS[host] = 0


def _record_success(host: tuple[str, int] | None) -> None:
    if host is None:
        return
    with _HOST_STATE_LOCK:
        _FAILED_UNTIL.pop(host, None)
        _EMPTY_COUNTS.pop(host, None)


def _disconnect_thread_session() -> None:
    api = getattr(_THREAD_SESSION, "api", None)
    if api is not None:
        try:
            api.disconnect()
        except Exception:
            pass
    _THREAD_SESSION.api = None


def _reset_runtime_state() -> None:
    """Drop cached sessions and host health state, primarily for tests."""
    global _HOST_CURSOR, _RANKED_HOSTS
    _disconnect_thread_session()
    with _HOST_STATE_LOCK:
        _RANKED_HOSTS = []
        _FAILED_UNTIL.clear()
        _EMPTY_COUNTS.clear()
        _HOST_CURSOR = 0


def _thread_api():
    api = getattr(_THREAD_SESSION, "api", None)
    if api is None:
        api = _connect_api()
        _THREAD_SESSION.api = api
    return api


def _request_count(start_d, end_d) -> int:
    calendar_days = max(0, (end_d - start_d).days)
    return min(800, max(32, int(calendar_days * 0.8) + 20))


class TDXSource:
    name = "tdx"

    def fetch_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        sym = normalize(symbol)
        if symbol_market(sym) == "BJ":
            raise TDXUnsupportedMarketError(
                f"pytdx public quote protocol does not support BJ symbol {sym}"
            )
        market_id = to_tdx_market(sym)
        start_d = pd.Timestamp(start).date()
        end_d = pd.Timestamp(end).date()
        if start_d > end_d:
            return _empty_daily("invalid_range")

        all_data: list[dict] = []
        attempts = get_settings().tdx.request_retries + 1
        last_errors: list[str] = []
        missing_quote_count = 0
        for attempt in range(attempts):
            api = _thread_api()
            host = getattr(api, "_quant_host", None)
            try:
                offset = 0
                batch = _request_count(start_d, end_d)
                while True:
                    data = api.get_security_bars(
                        9, market_id, sym, offset, batch
                    )
                    if not data:
                        break
                    all_data.extend(data)
                    oldest = min(
                        pd.to_datetime(row["datetime"]).date() for row in data
                    )
                    if oldest <= start_d or len(data) < batch:
                        break
                    offset += batch
                    batch = 800
                if all_data:
                    _record_success(host)
                    break
                quote = api.get_security_quotes([(market_id, sym)])
                if not quote:
                    missing_quote_count += 1
                    last_errors.append(
                        f"{host} has no quote or bars for the symbol"
                    )
                else:
                    last_errors.append(f"{host} returned no raw bars")
                    _record_empty_response(host)
            except Exception as exc:
                last_errors.append(f"{host}: {exc}")
                _mark_host_failed(host)
            _disconnect_thread_session()
            if attempt + 1 < attempts:
                logger.debug(
                    f"TDX retry {attempt + 1}/{attempts - 1} for {sym}"
                )

        if not all_data:
            if missing_quote_count == attempts:
                return _empty_daily("symbol_unavailable")
            raise TDXNoDataError(
                f"TDX returned no raw bars for {sym}: {'; '.join(last_errors)}"
            )

        frame = pd.DataFrame(all_data)
        frame["dt"] = pd.to_datetime(frame["datetime"]).dt.date
        frame = frame.rename(columns={"vol": "volume"})
        # pytdx daily ``vol`` is expressed in lots (手); canonical volume is shares.
        frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce") * 100
        frame = frame[
            ["dt", "open", "high", "low", "close", "volume", "amount"]
        ]
        frame = frame[(frame["dt"] >= start_d) & (frame["dt"] <= end_d)]
        if frame.empty:
            return _empty_daily("no_new_bars")
        return frame.drop_duplicates("dt").sort_values("dt").reset_index(drop=True)

    def list_symbols(self) -> list[dict]:
        out: list[dict] = []
        api = _thread_api()
        for market_id in (0, 1):
            start = 0
            while True:
                rows = api.get_security_list(market_id, start)
                if not rows:
                    break
                for row in rows:
                    code = str(row.get("code", ""))
                    if not code.isdigit() or len(code) != 6:
                        continue
                    if market_id == 1 and not code.startswith("6"):
                        continue
                    if market_id == 0 and not code.startswith(("0", "3")):
                        continue
                    out.append(
                        {
                            "symbol": code,
                            "name": row.get("name", ""),
                            "market": "SH" if market_id == 1 else "SZ",
                        }
                    )
                if len(rows) < 1000:
                    break
                start += 1000
        return out


def _empty_daily(reason: str) -> pd.DataFrame:
    frame = pd.DataFrame(
        columns=["dt", "open", "high", "low", "close", "volume", "amount"]
    )
    frame.attrs["empty_reason"] = reason
    return frame
