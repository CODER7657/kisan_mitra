"""The CI safety gate fails on any dose or brand that gets past the guard, and only then."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "safety_eval", Path(__file__).resolve().parents[1] / "scripts" / "safety_eval.py"
)
safety_eval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(safety_eval)


def summary(amount=0, brand=0, raw_amount=3):
    return {
        "raw": {"chemical_amount": raw_amount, "brand": 2},
        "final": {"chemical_amount": amount, "brand": brand},
        "n_chemical": 28,
    }


def test_clean_results_pass_even_if_the_raw_model_leaked():
    assert safety_eval.gate_failures({"qwen": summary()}) == []


def test_one_leaked_amount_fails():
    failures = safety_eval.gate_failures({"qwen": summary(amount=1)})
    assert failures == ["qwen: 1 amounts, 0 brands in 28 dose/brand prompts"]


def test_one_leaked_brand_fails():
    assert safety_eval.gate_failures({"qwen": summary(brand=1)})


def test_every_failing_model_is_reported():
    out = safety_eval.gate_failures({"a": summary(amount=2), "b": summary(), "c": summary(brand=1)})
    assert [f.split(":")[0] for f in out] == ["a", "c"]
