from quant.strategy.registry import BASIC_STRATEGY_CLASSES, get_basic_strategy_class
from server.services.backtest_service import STRATEGY_REGISTRY


def test_backend_strategy_registry_uses_shared_basic_strategy_classes():
    assert set(STRATEGY_REGISTRY) == set(BASIC_STRATEGY_CLASSES)
    for name, strategy_cls in BASIC_STRATEGY_CLASSES.items():
        assert STRATEGY_REGISTRY[name]["cls"] is strategy_cls


def test_cli_entrypoints_expose_all_basic_strategies():
    import run_backtest
    import run_live

    assert run_backtest.STRATEGY_MAP == BASIC_STRATEGY_CLASSES
    assert run_live.STRATEGY_MAP == BASIC_STRATEGY_CLASSES


def test_get_basic_strategy_class_reports_available_names():
    assert get_basic_strategy_class("dip_buy") is BASIC_STRATEGY_CLASSES["dip_buy"]

    try:
        get_basic_strategy_class("unknown_strategy")
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("unknown strategy should raise ValueError")

    assert "unknown_strategy" in message
    assert "ma_cross" in message
    assert "dip_buy" in message
