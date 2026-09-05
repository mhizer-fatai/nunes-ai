from __future__ import annotations

from agent.ablation import obligations, run_experiment


def test_headline_invariant_single_trial(tmp_path) -> None:
    """The quantified claim, locked in: every harmful payment is blocked with
    memory and sails through without it; legit flow is untouched."""
    report = run_experiment(str(tmp_path / "abl.db"), trials=1)
    assert len(obligations(0)) == 24
    assert report["with_memory"]["harmful_blocked"] == 16
    assert report["with_memory"]["harmful_total"] == 16
    assert report["with_memory"]["legit_allowed"] == 8
    assert report["with_memory"]["legit_total"] == 8
    assert report["without_memory"]["harmful_blocked"] == 0
    assert report["without_memory"]["harmful_allowed"] == 16


def test_scales_with_trials(tmp_path) -> None:
    report = run_experiment(str(tmp_path / "abl2.db"), trials=3)
    assert report["with_memory"]["harmful_blocked"] == 48
    assert report["without_memory"]["harmful_allowed"] == 48


def test_x402_arm_included(tmp_path) -> None:
    """x402: with memory every purchase completes and every replay is
    refused; without memory ZERO purchases are possible (fails closed)."""
    report = run_experiment(str(tmp_path / "abl3.db"), trials=1)
    x_with = report["x402"]["with_memory"]
    x_without = report["x402"]["without_memory"]
    assert x_with["purchases_ok"] == 6
    assert x_with["purchases_total"] == 6
    assert x_with["replays_blocked"] == 3
    assert x_with["replays_total"] == 3
    assert x_without["purchases_ok"] == 0
    assert x_without["purchases_total"] == 6
