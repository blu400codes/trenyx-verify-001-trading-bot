# Detection matrix — the target's own suite vs. planted defects

Baseline: 0 pre-existing failures (01-baseline/baseline_failures.txt).

**Result: 5 / 11 plantable defects caught by the target's tests.**

| id | defect | file | result | new failing tests |
|---|---|---|---|---|
| D01 | signal for bar t sees bar t (lookahead by one bar) | `engine/backtest/runner.py` | **ESCAPED** |  |
| D02 | slippage sign flipped (fills improve the price) | `brokers/backtest/execution.py` | **CAUGHT** | test_round_trip_trade, test_slippage_buy_market_order, test_slippage_large_order_more_impact, test_slippage_limit_order_less_than_market (+3) |
| D05 | trailing stop anchored to ENTRY, not running peak | `strategies/momentum/signals.py` | **ESCAPED** |  |
| D06 | strategy exit signal ignored (regression of the documented bug) | `strategies/simple_ma_strategy.py` | **CAUGHT** | test_execute_trade_sell_closes_position, test_execute_trade_with_dict_position |
| D07 | circuit-breaker comparison inverted (trips when SAFE) | `utils/circuit_breaker.py` | **CAUGHT** | test_check_halts_on_rapid_drawdown, test_check_no_halt_when_profit, test_check_no_halt_within_limit, test_just_under_limit_does_not_halt (+1) |
| D08 | kill switch flag set but never read by the order path | `strategies/base/position_sizing.py` | **ESCAPED** |  |
| D09 | paper/live default flips to LIVE | `config.py` | **ESCAPED** |  |
| D11 | broker exception swallowed; submit returns success-shaped None | `brokers/alpaca/orders.py` | **CAUGHT** | test_internal_submit_failure_writes_order_rejected |
| D12 | equity marked at previous bar's price (stale mark) | `brokers/backtest/core.py` | **ESCAPED** |  |
| D13 | max-position limit bypassed (off-by-one) | `strategies/momentum/strategy.py` | **CAUGHT** | test_execute_signal_respects_max_positions |
| D14 | last bar of the window processed twice | `engine/backtest/runner.py` | **ESCAPED** |  |
| D03 | commission charged on buys only | — | N/A | no commission model exists in the fill path (assessed in findings) |
| D04 | position sizing ignores available cash | — | NATIVE | already the behavior at the pinned commit — cannot be planted; confirmed finding |
| D10 | retry resubmits without an idempotency key | — | NATIVE | already the behavior at the pinned commit — cannot be planted; confirmed finding |

## Reading the matrix

- **Caught (5):** the suite has direct tests for slippage direction, the simple-MA exit,
  the circuit-breaker threshold, submit-failure auditing, and the max-positions cap.
- **Escaped (6):** one-bar lookahead into the strategy's data window (D01); trailing stop
  anchored to entry instead of the running peak (D05); the kill switch's verdict ignored by
  the order path (D08); paper/live default flipped to LIVE (D09); equity marked a bar stale
  (D12); the final session processed twice (D14). All 1,921 tests stay green through every
  one of them.
- The pattern: the suite tests *functions in isolation* thoroughly and *system invariants*
  almost never — no test asserts "the strategy cannot see today's bar", "an order cannot be
  placed while halted", or "equity is marked at the current date". Those are exactly the
  assertions in `02-independent-tests/`.
- Each run: plant → full suite → `git checkout` of every touched file; the target checkout
  is verified clean after the matrix.

