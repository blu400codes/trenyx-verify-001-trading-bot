"""
trenyx-verify-001 — independent tests, part 2: engine loop, exits, risk, broker boundary.

Written BLIND to the target's tests/. Invariant named per test. GPL-3.0.
"""
from __future__ import annotations

import asyncio
import importlib
import os
import types

import numpy as np
import pandas as pd
import pytest

from brokers.backtest_broker import BacktestBroker
from engine.backtest_engine import BacktestEngine
from strategies.simple_ma_strategy import SimpleMACrossoverStrategy
from utils.circuit_breaker import CircuitBreaker


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def trending_series(n=120, start="2024-01-01"):
    """Down for 50 bars then up: guarantees at least one MA crossover buy then hold."""
    idx = pd.bdate_range(start=start, periods=n)
    c = np.concatenate([np.linspace(120, 90, 50), np.linspace(90, 140, n - 50)])
    return pd.DataFrame(
        {"open": c, "high": c * 1.002, "low": c * 0.998, "close": c, "volume": 5e6}, index=idx
    )


class _DataBroker(BacktestBroker):
    """A BacktestBroker preloaded with data, usable as run_backtest's data source."""


def _engine_with(symbols):
    data = _DataBroker(initial_balance=100_000, random_seed=1)
    for s in symbols:
        data.set_price_data(s, trending_series())
    return BacktestEngine(broker=data), data


# ---------------------------------------------------------------------------
# I1 — the strategy never sees the current bar
# ---------------------------------------------------------------------------
class _SpyStrategy(SimpleMACrossoverStrategy):
    seen_leaks = []

    async def generate_signals(self):
        # engine sets self.current_date? no — it sets broker._current_date; compare to that
        cur = self.broker._current_date
        for sym, df in getattr(self, "current_data", {}).items():
            if len(df) and pd.Timestamp(df.index.max()).tz_localize(None) >= pd.Timestamp(cur).tz_localize(None):
                _SpyStrategy.seen_leaks.append((sym, df.index.max(), cur))
        await super().generate_signals()


def test_I1_strategy_data_is_strictly_before_current_bar():
    _SpyStrategy.seen_leaks = []
    engine, data = _engine_with(["AAA"])
    idx = data.price_data["AAA"].index
    run(engine.run_backtest(_SpyStrategy, ["AAA"], idx[0].date(), idx[-1].date(),
                            initial_capital=100_000, strategy_params={"fast_period": 5, "slow_period": 20}))
    assert not _SpyStrategy.seen_leaks, f"strategy saw the current bar: {_SpyStrategy.seen_leaks[:3]}"


# ---------------------------------------------------------------------------
# I2 / I6 — the run loop: one equity point per session, realized at the end, deterministic
# ---------------------------------------------------------------------------
def _run_once(seed_symbols=("AAA",)):
    engine, data = _engine_with(list(seed_symbols))
    idx = data.price_data[seed_symbols[0]].index
    return run(engine.run_backtest(SimpleMACrossoverStrategy, list(seed_symbols), idx[0].date(),
                                   idx[-1].date(), initial_capital=100_000,
                                   strategy_params={"fast_period": 5, "slow_period": 20})), len(idx)


def test_I2_one_equity_point_per_session_plus_initial():
    res, n = _run_once()
    assert len(res["equity_curve"]) == n + 1, "boundary bar double-counted or dropped"


def test_I2_end_of_run_positions_are_liquidated_and_equity_is_cash():
    res, _ = _run_once()
    assert res["positions"] == [], "open positions survived end-of-run liquidation"


def test_I2_trades_happened_at_all():
    """Sanity: the harness must actually trade, or the other tests prove nothing."""
    res, _ = _run_once()
    assert res["total_trades"] >= 2


def test_I6_two_identical_runs_are_byte_identical():
    r1, _ = _run_once()
    r2, _ = _run_once()
    assert r1["equity_curve"] == r2["equity_curve"], "identical inputs produced different equity"
    assert [(t["symbol"], t["side"], t["quantity"], round(t["price"], 6)) for t in r1["trades"]] == \
           [(t["symbol"], t["side"], t["quantity"], round(t["price"], 6)) for t in r2["trades"]]


# ---------------------------------------------------------------------------
# I3 — trailing stop ratchets from the PEAK and never loosens (momentum exits)
# ---------------------------------------------------------------------------
def _momentum_exit_harness():
    from strategies.momentum.strategy import MomentumStrategy

    class _Pos:
        symbol, qty = "AAA", 10.0

    broker = BacktestBroker(initial_balance=100_000, random_seed=1)
    s = MomentumStrategy(broker=broker, parameters={"symbols": ["AAA"], "use_trailing_stop": True,
                                                    "trailing_stop_pct": 0.02,
                                                    "trailing_activation_pct": 0.02})
    exits = []

    async def _positions():
        return [_Pos()]

    async def _exit(symbol, qty, side="sell", reason=""):
        exits.append((symbol, qty, reason))
        return types.SimpleNamespace(success=True, order_id="x")

    s._get_cached_positions = _positions
    s.submit_exit_order = _exit
    s.entry_prices["AAA"] = 100.0
    return s, exits


def test_I3_trailing_stop_fires_two_percent_below_peak():
    s, exits = _momentum_exit_harness()
    for px in (103.0, 110.0, 108.5):  # peak 110 → stop 107.8; 108.5 is above → no exit
        s.current_prices["AAA"] = px
        run(s._check_exit_conditions("AAA"))
    assert exits == [], f"exited early: {exits}"
    s.current_prices["AAA"] = 107.7
    run(s._check_exit_conditions("AAA"))
    assert len(exits) == 1 and "trailing" in exits[0][2]


def test_I3_trailing_stop_never_loosens_after_pullback():
    s, exits = _momentum_exit_harness()
    for px in (103.0, 110.0, 108.0):
        s.current_prices["AAA"] = px
        run(s._check_exit_conditions("AAA"))
    assert s.peak_prices["AAA"] == 110.0, "peak was lowered on a pullback (stop loosened)"


# ---------------------------------------------------------------------------
# I4 — circuit breaker halts at the limit, not before, and stays halted
# ---------------------------------------------------------------------------
class _Acct:
    def __init__(self, equity, cash=None):
        self.equity, self.cash = str(equity), str(cash if cash is not None else equity)


class _EqBroker:
    def __init__(self, path):
        self.path, self.i = list(path), 0

    async def get_account(self):
        a = _Acct(self.path[min(self.i, len(self.path) - 1)])
        self.i += 1
        return a


def test_I4_breaker_does_not_trip_below_limit_and_trips_at_limit():
    cb = CircuitBreaker(max_daily_loss=0.03, use_economic_calendar=False)
    run(cb.initialize(_EqBroker([100_000, 98_000, 97_000, 96_900])))
    cb._account_cache_ttl = 0
    assert run(cb.check_and_halt()) is False   # -2.0%
    assert run(cb.check_and_halt()) is False   # -3.0% exactly → depends on >=; record either way
    assert run(cb.check_and_halt()) is True    # -3.1%
    assert cb.is_halted()


def test_I4_breaker_stays_halted_even_if_equity_recovers():
    cb = CircuitBreaker(max_daily_loss=0.03, use_economic_calendar=False)
    run(cb.initialize(_EqBroker([100_000, 96_000, 100_000])))
    cb._account_cache_ttl = 0
    assert run(cb.check_and_halt()) is True
    assert run(cb.check_and_halt()) is True, "halt released without an explicit reset"


# ---------------------------------------------------------------------------
# I5 — broker boundary: paper by default and fail-CLOSED on unrecognized input
# ---------------------------------------------------------------------------
def test_I5_paper_flag_unrecognized_value_must_not_mean_live(monkeypatch):
    import config
    for bad in ("no", "ture", "paper", "0ff", "NO"):
        monkeypatch.setenv("PAPER", bad)
        creds = config.get_alpaca_creds(refresh=True)
        assert creds["PAPER"] is True or bad in ("no", "NO"), (
            f"PAPER={bad!r} parsed as LIVE — an unrecognized value must fail closed (paper)"
        )


def test_I5_alpaca_broker_string_paper_flag_fails_closed(monkeypatch):
    """AlpacaBroker(paper='ture') must not construct a live client."""
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    import brokers.alpaca_broker as ab
    captured = {}

    class _TC:
        def __init__(self, **kw):
            captured.update(kw)

    monkeypatch.setattr(ab, "TradingClient", _TC)
    monkeypatch.setattr(ab, "StockHistoricalDataClient", lambda **kw: None, raising=False)
    monkeypatch.setattr(ab, "StockDataStream", lambda *a, **kw: None, raising=False)
    try:
        ab.AlpacaBroker(paper="ture")
    except Exception as e:  # construction may fail later for unrelated reasons
        if not captured:
            pytest.skip(f"could not construct broker in isolation: {e}")
    assert captured.get("paper") is True, f"paper='ture' produced a LIVE client: {captured}"


def test_I5_retry_after_connection_error_resubmits_without_idempotency_key():
    """If the network drops AFTER the venue accepted the order, retry must not double-submit."""
    from brokers.alpaca._retry import retry_with_backoff

    submitted = []

    class _Req:
        symbol, qty, side = "AAA", 10, "buy"

    calls = {"n": 0}

    @retry_with_backoff(max_retries=3, initial_delay=0.01, max_delay=0.01)
    async def submit(order):
        calls["n"] += 1
        submitted.append(getattr(order, "client_order_id", None))
        if calls["n"] == 1:
            raise ConnectionError("connection reset after send")  # venue already has it
        return "ok"

    run(submit(_Req()))
    assert calls["n"] == 2
    keys = set(submitted)
    assert len(keys) == 1 and None not in keys, (
        f"order resubmitted with no client_order_id (keys={submitted}) — duplicate-fill risk"
    )


# ---------------------------------------------------------------------------
# I7 — config validation rejects contradictory values
# ---------------------------------------------------------------------------
def test_I7_config_rejects_out_of_range_risk(monkeypatch):
    monkeypatch.setenv("MAX_PORTFOLIO_RISK", "1.5")
    import config
    with pytest.raises(ValueError):
        importlib.reload(config)
    monkeypatch.setenv("MAX_PORTFOLIO_RISK", "0.02")
    importlib.reload(config)
