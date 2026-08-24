# Independent tests — results against the pinned commit

- 26 tests written blind to the target's `tests/` (see APPENDIX 1 of the plan for the
  two assertion lines incidentally seen).
- Run 1 (2026-08-24, between commits 8d9f543 15:30 and 68a1232 15:33 EDT): 13 passed / 10 failed / 1 skipped.
- Adjudication: 3 failures were OUR harness's fault (trailing-stop tests did not call the
  strategy's `initialize()`; a `pytest.raises` block swallowed its own assertion; a
  circuit-breaker fake broker was too naive for the breaker's two-threshold design).
  Fixed in commit history — the mistakes stay visible. (Earlier in-text times "16:45"/"17:03" were hand-written estimates and wrong; corrected to commit-anchored times — see ../CORRECTIONS.md.)
- Run 2 (committed 68a1232, 15:33:43 EDT): **17 passed / 8 failed / 1 skipped.** Every remaining failure is a
  reproduced target behavior and is written up in `04-findings/` — which publishes after
  the maintainer has had the chance to see it (README rule 3). The failing tests are the
  reproductions.
- Skipped: constructing `AlpacaBroker` in isolation needs credentials; the fail-closed
  paper-flag check on that class is covered at the config layer instead.
