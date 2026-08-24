#!/usr/bin/env python3
"""
trenyx-verify-001 — planted-defect planter.

Each pre-registered defect (00-preregistration/ATTACK-PLAN.md §4) is ONE exact-string
edit to ONE file in the target checkout. The planter refuses to run if the expected
text is not found exactly once — so a defect is either planted precisely or not at all.

    python plant.py <target_repo> list
    python plant.py <target_repo> apply D05
    python plant.py <target_repo> revert          # git checkout -- <files touched>

Detection rule (plan §4): CAUGHT = ≥1 baseline-passing test fails with the patch applied.
Status NATIVE = the defect is already the target's behavior at the pinned commit; it
cannot be planted and is assessed in 04-findings instead. N/A = behavior does not exist.
"""
import subprocess
import sys
from pathlib import Path

DEFECTS = {
    "D01": dict(
        title="signal for bar t sees bar t (lookahead by one bar)",
        file="engine/backtest/runner.py",
        old="historical = df[df.index < current_date_utc]",
        new="historical = df[df.index <= current_date_utc]",
    ),
    "D02": dict(
        title="slippage sign flipped (fills improve the price)",
        file="brokers/backtest/execution.py",
        old='''        if side == "buy":
            execution_price = base_price + total_slippage  # Buy at higher price
        else:  # sell
            execution_price = base_price - total_slippage  # Sell at lower price''',
        new='''        if side == "buy":
            execution_price = base_price - total_slippage
        else:  # sell
            execution_price = base_price + total_slippage''',
    ),
    "D03": dict(status="N/A", title="commission on buys only",
                reason="no commission model exists in the fill path (Alpaca commission-free); assessed in findings"),
    "D04": dict(status="NATIVE", title="position sizing ignores available cash",
                reason="place_order applies balance -= cost with no cash check at the pinned commit; equity-based sizing can exceed cash (see 04-findings)"),
    "D05": dict(
        title="trailing stop anchored to ENTRY, not running peak",
        file="strategies/momentum/signals.py",
        old="                        trailing_stop_price = peak * (1 - self.trailing_stop_pct)",
        new="                        trailing_stop_price = entry_price * (1 - self.trailing_stop_pct)",
    ),
    "D06": dict(
        title="strategy exit signal ignored (regression of the documented bug)",
        file="strategies/simple_ma_strategy.py",
        old='''            elif action == "sell" and position is not None:''',
        new='''            elif action == "sell" and position is None:''',
    ),
    "D07": dict(
        title="circuit-breaker comparison inverted (trips when SAFE)",
        file="utils/circuit_breaker.py",
        old="            # Check if loss limit exceeded\n            if daily_loss >= self.max_daily_loss:",
        new="            # Check if loss limit exceeded\n            if daily_loss <= self.max_daily_loss:",
    ),
    "D08": dict(
        title="kill switch flag set but never read by the order path",
        file="strategies/base/position_sizing.py",
        old="        is_halted = await self.circuit_breaker.check_and_halt()\n        return not is_halted",
        new="        await self.circuit_breaker.check_and_halt()\n        return True",
    ),
    "D09": dict(
        title="paper/live default flips to LIVE",
        file="config.py",
        old='"PAPER": _parse_bool_env("PAPER", default=True),',
        new='"PAPER": _parse_bool_env("PAPER", default=False),',
    ),
    "D10": dict(status="NATIVE", title="retry resubmits without an idempotency key",
                reason="submit paths carry no client_order_id at the pinned commit; a ConnectionError after venue acceptance is retried (see 04-findings)"),
    "D11": dict(
        title="broker exception swallowed; submit returns success-shaped None",
        file="brokers/alpaca/orders.py",
        old='''        except Exception as e:
            logger.error(f"Error in _internal_submit_order: {e}", exc_info=DEBUG_MODE)
            self._audit_order_rejected(order_request, str(e))
            raise''',
        new='''        except Exception as e:
            logger.error(f"Error in _internal_submit_order: {e}", exc_info=DEBUG_MODE)
            self._audit_order_rejected(order_request, str(e))
            return None''',
    ),
    "D12": dict(
        title="equity marked at previous bar's price (stale mark)",
        file="brokers/backtest/core.py",
        old='''        for symbol, position in self.positions.items():
            price = self.get_price(symbol, current_date)
            value += position["quantity"] * price

        return value''',
        new='''        for symbol, position in self.positions.items():
            price = self.get_price(symbol, current_date - timedelta(days=1))
            value += position["quantity"] * price

        return value''',
    ),
    "D13": dict(
        title="max-position limit bypassed (off-by-one)",
        file="strategies/momentum/strategy.py",
        old='        """Execute a buy signal for the given symbol."""\n        if len(positions) >= self.max_positions:',
        new='        """Execute a buy signal for the given symbol."""\n        if len(positions) > self.max_positions:',
    ),
    "D14": dict(
        title="last bar of the window processed twice",
        file="engine/backtest/runner.py",
        old='        logger.info(f"Running backtest over {len(trading_days)} trading days...")',
        new='        trading_days = list(trading_days) + ([trading_days[-1]] if trading_days else [])\n        logger.info(f"Running backtest over {len(trading_days)} trading days...")',
    ),
}


def apply(repo: Path, key: str) -> None:
    d = DEFECTS[key]
    if d.get("status"):
        print(f"{key}: {d['status']} — {d['reason']}")
        return
    path = repo / d["file"]
    src = path.read_text()
    n = src.count(d["old"])
    if n != 1:
        raise SystemExit(f"{key}: expected exactly 1 match in {d['file']}, found {n} — refusing")
    path.write_text(src.replace(d["old"], d["new"]))
    print(f"{key} planted in {d['file']}: {d['title']}")


def revert(repo: Path) -> None:
    files = sorted({d["file"] for d in DEFECTS.values() if "file" in d})
    subprocess.run(["git", "-C", str(repo), "checkout", "--"] + files, check=True)
    print("reverted:", ", ".join(files))


if __name__ == "__main__":
    repo, cmd = Path(sys.argv[1]), sys.argv[2]
    if cmd == "list":
        for k, d in DEFECTS.items():
            print(f"{k}  {d.get('status', 'PLANTABLE'):9s} {d['title']}")
    elif cmd == "apply":
        apply(repo, sys.argv[3])
    elif cmd == "revert":
        revert(repo)
