# Attack plan — trenyx-verify-001 (pre-registered)

**Written:** 2026-08-24, before reading any implementation or test body.
**Target commit:** 52b8dffebb683ecadff753f5efc178b4ea21a029 (2026-08-19).
**Disclosure of what WAS seen before writing this:** README.md, top-level directory
listing, per-directory line counts, the file names (not contents) under `tests/`,
and the git log (commit messages/trailers). Nothing else.

## 1. What the system is supposed to do (from its README)

Trade US equities via Alpaca (paper by default; live behind a flag) using a
momentum strategy (RSI/MACD/ADX with trailing stops), a mean-reversion strategy,
and an "adaptive" coordinator that switches by market regime. Backtest the same
strategies with "realistic slippage." Enforce risk limits (VaR, correlation,
position sizing, circuit breakers). The README states: paper-only, no proven
edge; and that a structural defect fixed in Aug 2026 had prevented the strategy
from ever exiting on its own signal.

## 2. Invariants (what must be true; each becomes attack targets)

- **I1 No lookahead.** A signal decided for bar t uses data ≤ t; execution occurs
  no earlier than the next tradable price (or at a documented, consistent price).
- **I2 Accounting.** Cash never negative without explicit margin; equity =
  cash + Σ(position × mark); slippage and commissions are charged on EVERY fill in
  the ADVERSE direction; nothing is double-counted at data boundaries.
- **I3 Exits.** A strategy exit signal closes the position (the historical bug);
  a trailing stop ratchets from the running PEAK and never loosens.
- **I4 Risk.** Circuit breaker halts NEW entries once the loss limit is breached;
  kill switch halts ALL order submission; position size is bounded by available
  cash and the configured max; limits use CURRENT positions, not stale.
- **I5 Broker boundary.** Paper is the default and live requires explicit opt-in;
  order submission is idempotent under retry; broker errors surface to the
  caller — never swallowed into a "success."
- **I6 Determinism.** Same inputs → byte-identical backtest output.
- **I7 Configuration.** Invalid/contradictory config is rejected, not defaulted.

## 3. High-risk paths (attack order)

1. Backtest fill + accounting loop (I1, I2, I6)
2. Slippage/commission application (I2)
3. Trailing stop and exit handling (I3)
4. Risk manager thresholds and kill switch (I4)
5. Broker wrapper: paper/live switch, retry, error handling (I5)
6. Config validation (I7)

## 4. Planted-defect set (pre-registered; each = one minimal patch)

| id | defect (semantic) | invariant |
|----|-------------------|-----------|
| D01 | signal for bar t filled at bar t's close (lookahead by one bar) | I1 |
| D02 | slippage sign flipped (fills improve the price) | I2 |
| D03 | commission charged on buys only | I2 |
| D04 | position sizing ignores available cash (cash can go negative) | I2 |
| D05 | trailing stop anchored to ENTRY price, not running peak | I3 |
| D06 | strategy exit signal ignored (regression of the documented bug) | I3 |
| D07 | circuit-breaker comparison inverted (trips when SAFE) | I4 |
| D08 | kill switch flag set but never read by the order path | I4 |
| D09 | paper/live default flips to LIVE | I5 |
| D10 | retry re-submits the order without an idempotency key (duplicate fill) | I5 |
| D11 | broker exception swallowed; submit returns success | I5 |
| D12 | equity marked at previous bar's price (stale mark) | I2 |
| D13 | max-position limit bypassed for one strategy path | I4 |
| D14 | last bar of the data window processed twice (boundary off-by-one) | I2/I6 |

**Detection rule:** a defect is CAUGHT if at least one test in the target's suite
that passed at baseline fails with the patch applied (same environment, same
seed). Otherwise ESCAPED. Patches are minimal (target ≤ 10 changed lines) and
must leave the suite runnable. If a defect cannot be planted because the
behavior does not exist (e.g., no retry path), that is recorded as N/A with the
reason — not silently dropped.

## 5. Independent tests

Written blind to `tests/`, targeting I1–I7 through public interfaces, using
synthetic price series with known answers. Target: ≥ 20 scenarios. Each test
states the invariant it checks. Results reported pass/fail against the pinned
commit; a failing independent test is a candidate finding, graded per §7.

## 6. Coverage reporting

Denominator published: 14 planted defects + N independent scenarios. Report:
their suite caught X/14; our scenarios passed Y/N. No bare score without the list.

## 7. Findings taxonomy

confirmed defect (reproduction runs) → potential defect (plausible, not
reproduced) → design concern → recommendation. Confirmed graded
critical/high/medium/low by money-path impact.

## 8. Environment

Python venv isolated in a scratch directory; the target's pinned requirements;
NO network calls to Alpaca (broker tests use mocked HTTP); seeds fixed.

## 9. Timebox

3–5 working days of effort; what is unfinished at the timebox is reported as
unfinished.

## 10. Disclosure

Real defects → maintainer (GitHub issue or email) before `04-findings/` publishes.

---
## APPENDIX 1 (2026-08-24 16:05 ET, after reading began) — scope clarification + disclosure

The plan above is unchanged (hash stands). Additions only:

1. **Scope clarification.** The LOC pass that defined "engine/ + brokers/ + main.py +
   config.py" missed two directories that implement pre-registered invariants:
   `strategies/` (BaseStrategy sizing, momentum exits/trailing stop, risk manager —
   I2/I3/I4) and `utils/circuit_breaker.py` (I4). They are in scope. `research/`,
   `examples/`, `web/` remain out.
2. **Incidental exposure.** While locating consumers of the PAPER flag, a repository
   grep surfaced two single assertion lines from `tests/` (one asserting the flag's
   type, one asserting `creds["PAPER"] is False` under an alias env var). No test
   bodies were read. Recorded so the "blind" claim is precise, not absolute.
3. **Pre-registered defect D03 (commission on buys only)** cannot be planted as written:
   the backtest broker has no commission model at all (Alpaca is commission-free;
   regulatory sell-side fees are not modeled). D03 is recorded N/A with this reason and
   the absence itself is assessed in findings.
