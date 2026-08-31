# Findings — trenyx-verify-001 (gr8monk3ys/trading-bot @ 52b8dff)

Published 2026-08-31 per the disclosure terms stated in
[gr8monk3ys/trading-bot#99](https://github.com/gr8monk3ys/trading-bot/issues/99)
(created 2026-08-25T17:14:03Z / 13:14 EDT): the write-up was proposed to publish ~72
hours after disclosure ("happy to wait longer if you'd rather fix first"). The window
elapsed 2026-08-28T17:14Z; no maintainer response, fix, or request to wait as of
publication. Every "confirmed" item has a reproduction in `02-independent-tests/`
(test name given). Grades are money-path impact, recorded AFTER independent refutation:
F1 HIGH stands; F3 HIGH stands; F2 downgraded to MEDIUM by the refuter.

**One item not restated.** F6, a configuration-parsing finding with live-trading
implications, was filed through the repository's private security advisory channel
(issue #99, item 6), and this document does not restate it. To be precise about what
that does and doesn't keep private: the pre-registered blind invariant tests — public
in `02-independent-tests/` since 2026-08-24, before any triage — exercise the same
configuration surface, so the *area* is visible in this repo by design; the advisory
carries the specific production impact, grade, and reproduction, and those publish
after a fix lands or after a substantially longer window. Everything else below is
already public in #99; this document adds the reproductions, grades, and process
record.

## Confirmed defects

### F1 — HIGH — Position sizing reads equity marked at end-of-data prices (lookahead into sizing)
PLAIN: When deciding how much to buy, the simulator asks "how much is my account worth?"
and accidentally answers using prices from the END of the data, not today. It's peeking
at the future to size its bets.
- Where: `brokers/backtest/core.py` `get_account()` → `get_portfolio_value()` with no
  date → `get_price(sym, datetime.now())` pads to the last bar. Consumers:
  `strategies/base/position_sizing.py`, `utils/circuit_breaker.py`, and (per the
  refuter) `strategies/momentum_strategy_backtest.py` — the class used by
  `scripts/run_honest_baseline.py`, `run_bollinger_ab.py`, `run_etf_baseline.py` —
  sizing `equity × size_pct` with `sizing_basis="equity"` by default → every headline
  result passed through it.
- Repro: `test_I1_account_equity_is_marked_at_current_date_not_end_of_data`
  (10,999 vs 9,999).
- Refutation attempt: NOT REFUTED; independently reproduced (109,982 vs 99,982).
  Strongest counterargument: a buy-side cap `min(qty, cash/price)` bounds spending —
  binds only when `equity×size_pct > cash`, never for shorts.
- Fix: `get_account()` must use `self._current_date`.

### F2 — MEDIUM (downgraded from HIGH by independent refutation) — Buys fill into negative cash; no cash/margin check in the fill path
PLAIN: The simulator's ledger will let you buy more than you have cash for and never
complain. The strategies happen not to do that, but nothing stops them.
- Where: `brokers/backtest/execution.py` `place_order`: `balance -= cost`
  unconditionally.
- Repro: `test_I2_cash_never_negative_without_margin` (balance −4,001.20 on a 'filled'
  order).
- Refutation: REFUTED AS GRADED. Shipped strategies size from buying_power/cash or
  cash-cap; Kelly (equity) off by default; the runner's `asyncio.gather` does not
  interleave (no yields) so no stale-cash snapshots; replaying
  `results/etf_baseline_2020-2024_gross{25,50,100}.json` shows cash never negative
  (min +$5,228). Residual: the ledger trusts one `min()` line in one strategy; slippage
  is applied AFTER the cash cap; short proceeds inflate buying_power with no margin.
  The original HIGH grade was our error, recorded as such.

### F3 — HIGH (live path) — Order submission retried after a network error with no idempotency key
PLAIN: If the internet hiccups right after the broker accepts an order, the bot sends
the same order again, and there's no ID that would let the broker say "already got that
one." Real money, doubled position.
- Where: `brokers/alpaca/_retry.py` retries ConnectionError/OSError;
  `brokers/alpaca/orders.py` submit paths send no `client_order_id`.
- Repro: `test_I5_retry_after_connection_error_resubmits_without_idempotency_key`.
- Refutation: NOT REFUTED. The timeout path does NOT retry (OrderError "timed out"
  misses the "timeout" term — attempts=1). `requests.ConnectionError ⊂ OSError` →
  "accepted, then dropped" IS retried (attempts=2, booked=2); alpaca-py's RESTClient
  retries 429/504 ×3 beneath (nested retry layers); gateway risk checks run once
  before the call; `OrderBuilder.client_order_id()` exists, unused.
- Fix: `client_order_id` per logical order; query by client id before resubmitting.

### F4 — MEDIUM — Unknown symbol → fabricated random price history in a production class
PLAIN: Ask it for price history of a stock it doesn't know, and it invents random
prices instead of saying "I don't have that."
- Where: `brokers/backtest/core.py` `get_historical_prices`.
- Repro: `test_silent_failure_unknown_symbol_must_not_yield_fabricated_prices`
  (21 synthetic bars).

### F5 — MEDIUM — Backtests nondeterministic by default
PLAIN: Run the same backtest twice and you can get different results, because a random
number generator is never given a fixed starting point.
- Where: `random_seed=None`; `run_backtest` never seeds. Affects partial fills and
  rejects.
- Repro: `test_I6_default_construction_is_deterministic_or_documented`.

### F6 — NOT RESTATED HERE (filed via the private security advisory channel)
A configuration-parsing finding with live-trading implications, submitted 2026-08-25
through the repository's security advisory channel (issue #99, item 6). Its production
impact, grade, and reproduction publish after a fix lands or after a substantially
longer window — private-first for anything with live-trading consequence. (See the
note at the top on what is and isn't already visible in this repo.)

### F7 — MEDIUM (potential) — BacktestBroker-fed runs silently load only the last 100 bars
PLAIN: One way of feeding it data quietly keeps only the last 100 days, so a backtest
over a longer period silently isn't.
- Where: the runner passes no limit; `BacktestBrokerCore.get_bars` `limit=100` →
  `tail(100)`. The Alpaca path is unaffected.
- Repro: `test_I2_one_equity_point_per_session_plus_initial` (101 points for 120
  sessions).

### F8 — LOW — Over-selling a long deletes the position and credits proceeds for unheld shares
PLAIN: Sell more shares than you own and the ledger pays you for shares you never had.
The strategies clamp this; the ledger doesn't.
- Repro: `test_I2_oversell_does_not_create_free_money` (+$1,499.64). Only direct
  callers of the ledger are exposed.

## Potential defects (not fully reproduced against a venue)

### F9 — POTENTIAL (surfaced by the F3 refuter) — Orphaned order on submit timeout
PLAIN: If sending an order times out, the bot records "not sent," but the send may
still complete in the background — an order nobody is tracking.
- `_async_call_with_timeout` wraps `wait_for(to_thread(...))`, so the HTTP thread
  keeps running; the order can land after "timed out"; no audit event. Reconcile by
  `client_order_id` (same fix as F3).

### F10 — POTENTIAL (surfaced by the F2 refuter) — MomentumStrategy cannot execute a trade against BacktestBroker
PLAIN: The main strategy calls a function the wrong way when it tries to trade in a
backtest; the error is swallowed, so the backtest just shows zero trades.
- `strategies/momentum/strategy.py:636` awaits
  `gather(self.broker.get_positions(), ...)` on a sync method → TypeError whenever a
  signal fires, swallowed into `decision_errors` → zero-trade backtests.
  `MomentumStrategyBacktest` may bypass this; confirm at retest.

## What the target's own suite catches (`03-planted-defects/matrix.md`)
11 planted; 5 caught, 6 escaped. Among the escapes: D12 stale marks ↔ F1 (no test
pins equity to a date); D01 lookahead is guarded by no test.

## Design concerns
- DC1 — The circuit breaker uses wall-clock day resets and `get_account()` (F1) — not
  simulation-aware.
- DC2 — `MomentumStrategy.initialize()` try/except → proceeds half-initialized with a
  warning only.
- DC3 — No commission/regulatory-fee model (planted D03 was N/A for this reason).
  Document the assumption.
- DC4 — README says MIT; LICENSE is GPL-3.0.

## Recommendations
- R1 — An invariants test module (equity identity, cash ≥ 0, dated marks) would have
  caught F1/F2/F4 in ~40 lines.
- R2 — Record the RNG seed and data-window coverage in `run_metadata`.

## Retracted during the engagement (kept for honesty)
- "MomentumStrategy is half-initialized by partial parameters": our harness omitted
  `initialize()`. Our error, not theirs.

## Process record
Three harness bugs fixed in the open; three mechanical failures of our own standard
caught by an outside reviewer (`CORRECTIONS.md`); one grade overturned by an
independent refuter (F2). Denominators are ours and published — these numbers describe
this attack, not a universal score.
