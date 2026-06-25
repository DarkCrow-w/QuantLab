from quant.data.symbol_filter import filter_a_share_rows, is_active_a_share_row
from server.services.system_service import _universe_check


def test_filter_a_share_rows_excludes_indices_and_delisted_names():
    rows = [
        {"symbol": "600519", "name": "贵州茅台"},
        {"symbol": "399001", "name": "深证成指"},
        {"symbol": "600421", "name": "退市华嵘"},
        {"symbol": "600599", "name": "Delisted Example"},
        {"symbol": "000001.SZ", "name": "平安银行"},
    ]

    assert [row["symbol"] for row in filter_a_share_rows(rows)] == ["600519", "000001"]


def test_is_active_a_share_row_keeps_st_but_not_delisted():
    assert is_active_a_share_row({"symbol": "600001", "name": "*ST 测试"})
    assert not is_active_a_share_row({"symbol": "600001", "name": "终止上市测试"})


def test_system_universe_check_uses_filtered_active_a_share_rows():
    import pandas as pd

    class Store:
        def get_universe(self):
            return pd.DataFrame(
                [
                    {"symbol": "600519", "name": "贵州茅台", "market": "SH"},
                    {"symbol": "399001", "name": "深证成指", "market": "SZ"},
                    {"symbol": "600421", "name": "退市华嵘", "market": "SH"},
                ]
            )

    check = _universe_check(Store())

    assert check.detail["symbols"] == 1
    assert check.detail["markets"] == ["SH"]
