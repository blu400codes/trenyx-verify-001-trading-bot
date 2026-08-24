# Appendix 1 to the attack plan — additions only (the plan file is byte-frozen)

## APPENDIX 1 (committed 2026-08-24 15:23:25 EDT in 1e5c3b7 — the earlier in-text time "16:05 ET" was a hand-written estimate and wrong; see CORRECTIONS.md) — scope clarification + disclosure

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
