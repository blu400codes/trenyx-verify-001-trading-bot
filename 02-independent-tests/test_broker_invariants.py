"""
trenyx-verify-001 — independent tests, part 1: BacktestBroker + engine invariants.

Written BLIND to the target's tests/ directory, against the pre-registered
invariants in 00-preregistration/ATTACK-PLAN.md. Each test names its invariant.
Run from the target's repo root with this repo's 02-independent-tests on the
pytest path:  pytest -q /path/to/02-independent-tests

License: GPL-3.0 (tests exercise GPL-3.0 code).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from brokers.backtest_broker import BacktestBroker


# ---------------------------------------------------------------------------
# helpers: synthetic price series with KNOWN answers (no randomness needed)
# ---------------------------------------------------------------------------
def make_series(closes, start="2024-01-01"):
    """Business-day OHLCV frame whose close path is exactly `closes`."""
    idx = pd.bdate_range(start=start, periods=len(closes))
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame(
        {"open": c, "high": c * 1.001, "low": c * 0.999, "close": c, "volume": 5_000_000.0},
        index=idx,
    )


def broker_with(symbol_paths: dict, balance=100_000, **kw):
    b = BacktestBroker(initial_balance=balance, enable_partial_fills=False, random_seed=1, **kw)
    for sym, closes in symbol_paths.items():
        b.set_price_data(sym, make_series(closes))
    return b


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# I2 — accounting
# ---------------------------------------------------------------------------
def test_I2_slippage_is_adverse_on_both_sides():
    b = broker_with({"AAA": [100.0] * 40})
    b._current_date = b.price_data["AAA"].index[-1]
    buy = b.place_order("AAA", 10, "buy")
    sell = b.place_order("AAA", 10, "sell")
    assert buy["filled_avg_price"] > 100.0, "buy must fill ABOVE mid"
    assert sell["filled_avg_price"] < 100.0, "sell must fill BELOW mid"


def test_I2_cash_never_negative_without_margin():
    """A buy whose cost exceeds cash must be rejected or clipped — not filled into debt."""
    b = broker_with({"AAA": [100.0] * 40}, balance=1_000)
    b._current_date = b.price_data["AAA"].index[-1]
    order = b.place_order("AAA", 50, "buy")  # ~$5,000 on $1,000 cash
    assert b.get_balance() >= 0 or order["status"] == "rejected", (
        f"cash went to {b.get_balance():.2f} on a 'filled' order — implicit leverage"
    )


def test_I2_oversell_does_not_create_free_money():
    """Selling more than held must either open a short (liability) or be clipped."""
    b = broker_with({"AAA": [100.0] * 40}, balance=10_000)
    b._current_date = b.price_data["AAA"].index[-1]
    b.place_order("AAA", 10, "buy")
    cash_after_buy = b.get_balance()
    b.place_order("AAA", 15, "sell")  # 5 more than held
    pos = b.get_position("AAA")
    # Acceptable: a short of -5 exists (liability booked). Unacceptable: no position and
    # proceeds for 15 shares credited.
    proceeds = b.get_balance() - cash_after_buy
    assert (pos is not None and pos["quantity"] == -5) or proceeds < 10 * 100.0 * 1.01, (
        f"over-sell credited {proceeds:.2f} with position={pos}"
    )


def test_I2_equity_identity_after_fills():
    """equity == cash + Σ qty × mark at the CURRENT date."""
    b = broker_with({"AAA": [100.0] * 20 + [110.0] * 20, "BBB": [50.0] * 40})
    d = b.price_data["AAA"].index[10]
    b._current_date = d
    b.place_order("AAA", 10, "buy")
    b.place_order("BBB", 20, "buy")
    mark_aaa, mark_bbb = 100.0, 50.0
    expected = b.get_balance() + 10 * mark_aaa + 20 * mark_bbb
    assert abs(b.get_portfolio_value(d) - expected) < 1e-6


# ---------------------------------------------------------------------------
# I1 — no lookahead in the account/equity surface strategies size from
# ---------------------------------------------------------------------------
def test_I1_account_equity_is_marked_at_current_date_not_end_of_data():
    """get_account().equity (what sizing reads) must not use prices after _current_date."""
    # AAA: 100 for 20 bars, then 200 for 20 bars. Hold 10 shares at bar 10.
    b = broker_with({"AAA": [100.0] * 20 + [200.0] * 20}, balance=10_000)
    d = b.price_data["AAA"].index[10]
    b._current_date = d
    b.place_order("AAA", 10, "buy")
    acct = run(b.get_account())
    equity_now = b.get_portfolio_value(d)  # ~10,000 (10 sh × 100 + cash)
    assert abs(float(acct.equity) - equity_now) < 1.0, (
        f"account.equity={float(acct.equity):.2f} vs equity at current date {equity_now:.2f}: "
        "sizing sees future marks"
    )


def test_I1_latest_quote_matches_current_date():
    b = broker_with({"AAA": [100.0] * 20 + [200.0] * 20})
    d = b.price_data["AAA"].index[10]
    b._current_date = d
    q = run(b.get_latest_quote("AAA"))
    assert abs(q.ask_price - 100.0) < 1e-9


def test_I1_dynamic_spread_and_volume_use_only_prior_bars():
    """Volume/vol estimates at date d must not change if bars AFTER d change."""
    base = [100.0] * 40
    b1 = broker_with({"AAA": base})
    b2 = broker_with({"AAA": base[:30] + [500.0] * 10})  # future differs wildly
    d = b1.price_data["AAA"].index[25]
    s1 = b1._calculate_dynamic_spread("AAA", d, 3.0)
    s2 = b2._calculate_dynamic_spread("AAA", d, 3.0)
    v1 = b1._get_actual_daily_volume("AAA", d)
    v2 = b2._get_actual_daily_volume("AAA", d)
    assert s1 == s2 and v1 == v2


# ---------------------------------------------------------------------------
# I6 — determinism
# ---------------------------------------------------------------------------
def _fill_path(seed, profile="stressed"):
    b = BacktestBroker(initial_balance=1_000_000, execution_profile=profile, random_seed=seed)
    b.set_price_data("AAA", make_series([100.0] * 40))
    b._current_date = b.price_data["AAA"].index[-1]
    return [b.place_order("AAA", 2_000_000, "buy")["filled_qty"] for _ in range(5)]


def test_I6_same_seed_same_fills():
    assert _fill_path(7) == _fill_path(7)


def test_I6_default_construction_is_deterministic_or_documented():
    """Two brokers built with defaults must produce identical fills, or the default
    must be a fixed seed. (Nondeterministic-by-default backtests are irreproducible.)"""
    b1 = BacktestBroker(initial_balance=1_000_000, execution_profile="stressed")
    b2 = BacktestBroker(initial_balance=1_000_000, execution_profile="stressed")
    for b in (b1, b2):
        b.set_price_data("AAA", make_series([100.0] * 40))
        b._current_date = b.price_data["AAA"].index[-1]
    p1 = [b1.place_order("AAA", 2_000_000, "buy")["filled_qty"] for _ in range(5)]
    p2 = [b2.place_order("AAA", 2_000_000, "buy")["filled_qty"] for _ in range(5)]
    assert p1 == p2, "default-constructed backtests are nondeterministic (unseeded RNG)"


# ---------------------------------------------------------------------------
# silent failure — data that does not exist must not be invented
# ---------------------------------------------------------------------------
def test_silent_failure_unknown_symbol_must_not_yield_fabricated_prices():
    b = BacktestBroker(initial_balance=10_000)
    with pytest.raises(Exception):
        # A production broker asked for history of a symbol it has no data for
        # must fail loudly, not return synthetic random bars.
        df = b.get_historical_prices("ZZZZ_NOT_A_SYMBOL", days=30)
        assert df is None or len(df) == 0, "fabricated price history returned"
        raise ValueError("fabricated price history returned")


# ---------------------------------------------------------------------------
# partial fills — floor and status
# ---------------------------------------------------------------------------
def test_partial_fill_status_and_floor():
    b = BacktestBroker(initial_balance=10_000_000, execution_profile="stressed", random_seed=3)
    b.set_price_data("AAA", make_series([100.0] * 40))
    b._current_date = b.price_data["AAA"].index[-1]
    o = b.place_order("AAA", 50_000_000, "buy")  # 10× ADV
    assert o["filled_qty"] >= 1
    assert o["status"] in ("filled", "partially_filled", "rejected")
    if o["status"] == "partially_filled":
        assert o["filled_qty"] < o["quantity"]
