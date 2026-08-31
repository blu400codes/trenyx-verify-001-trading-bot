# trenyx-verify-001 — independent verification of an AI-built trading system

**Target:** [gr8monk3ys/trading-bot](https://github.com/gr8monk3ys/trading-bot) at commit
`52b8dffebb683ecadff753f5efc178b4ea21a029` (committed 2026-08-19 EDT / 2026-08-20T03:20:19Z). A Python trading system (Alpaca paper/live broker, momentum +
mean-reversion strategies, backtest engine, risk manager) whose commit history is
57% `Co-Authored-By: Claude` (157 of 275 commits) — i.e. exactly the population
[Trenyx](https://trenyx-site.onrender.com/work-with-me.html) sells verification for.
This is the public sample of that engagement, run on open-source code so anyone can
check the work. The maintainer did not commission it and owes nothing to it.

**Scope:** `engine/`, `brokers/`, `main.py`, `config.py` — the production path
(~11k LOC). `research/` is excluded by the target's own README ("excluded from
production"). Their tests: 121 files, ~46k LOC, not read before ours were written.

## How to verify us

| folder | what's in it | how you check it |
|---|---|---|
| `00-preregistration/` | the attack plan, written BEFORE any implementation was read, + its SHA-256 (`cd 00-preregistration && shasum -a 256 -c ATTACK-PLAN.sha256`) | the plan file is byte-frozen (additions live in `APPENDIX-1.md`); hash matches the first commit |
| `01-baseline/` | the target's own suite, run as-is: counts, failures, environment | re-run it |
| `02-independent-tests/` | tests written blind to theirs, targeting the pre-registered invariants | run them against the pinned commit |
| `03-planted-defects/` | one minimal patch per pre-registered semantic defect + the detection matrix (which of THEIR tests caught it) | apply a patch, run their suite, compare |
| `04-findings/` | confirmed / potential / design concern / recommendation, each with a reproduction | run the reproduction |
| `05-receipt/` | SHA-256 of every artifact above, dated | hash the files yourself |

## Results (2026-08-24)

| measure | result |
|---|---|
| Target's own suite at baseline | 1,921 passed · 11 skipped · 0 failed (47 s) |
| Planted semantic defects (pre-registered) | 14: 11 plantable · 2 native · 1 n/a |
| **Caught by the target's tests** | **5 / 11** — escaped: one-bar lookahead, trailing stop anchored to entry, kill switch ignored, paper→live default, stale marks, double-processed final bar |
| Independent scenarios (blind) | 26 — 17 pass · 8 fail · 1 skip |
| **Confirmed defects** (each failing scenario reproduces one) | **8** — disclosed to the maintainer in [gr8monk3ys/trading-bot#99](https://github.com/gr8monk3ys/trading-bot/issues/99) (created 2026-08-25T17:14:03Z / 13:14 EDT); the safety-adjacent item also via their private advisory channel. **[`04-findings/`](04-findings/FINDINGS.md) published 2026-08-31** — the 72-hour window elapsed 2026-08-28 with no maintainer response; the advisory-channel item is not restated there (its specifics publish after a fix lands — the findings note says precisely what is and isn't already visible in this repo) |

Denominators are ours and published (`00-preregistration/`, `02-independent-tests/`):
these numbers describe *this* attack, not a universal score.

## Rules this engagement runs under

1. **Pre-registration:** the attack plan is committed and hashed before the code is read; the plan file is never edited afterwards (additions go in `APPENDIX-1.md`). On client engagements the hash is emailed to the client before any code is shared; on public samples it is anchored externally. This sample's pre-registration rests on commit order only — see `CORRECTIONS.md`.
2. **Blind tests:** our tests are written without reading the target's `tests/`.
3. **Disclosure before publication:** planted defects and the detection matrix publish as produced (they describe the tests, not exploitable behavior). Any REAL defect goes to the maintainer first; `04-findings/` publishes after they have had the chance to see it.
4. **No guaranteed bug count.** If nothing real is found, the folders above still fill.
5. **Coverage is reported with its denominator** (the scenario list), never as a bare score.

## Corrections

An outside reviewer found three failures of this repo's own standard after publication. They are recorded, not hidden, in [`CORRECTIONS.md`](CORRECTIONS.md), together with the rules adopted because of them.

## Licensing

The target is GPL-3.0; patches and tests that touch it (`02-`, `03-`) are GPL-3.0.
Reports and documents (`00-`, `01-`, `04-`, `05-`, this README) are CC-BY-4.0.
