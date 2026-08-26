from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree

from heston_arb_lab.synthetic_evidence import write_synthetic_evidence


def test_synthetic_evidence_reproduces_committed_artifacts(tmp_path: Path) -> None:
    run = write_synthetic_evidence(tmp_path)
    committed = Path(__file__).resolve().parents[1] / "docs" / "assets"

    assert (tmp_path / "synthetic_evidence.json").read_bytes() == (
        committed / "synthetic_evidence.json"
    ).read_bytes()
    assert (tmp_path / "synthetic_evidence.svg").read_bytes() == (
        committed / "synthetic_evidence.svg"
    ).read_bytes()
    assert run.summary["label"].startswith("SYNTHETIC")
    assert run.summary["network_requests"] == 0
    assert run.summary["provider_data_rows"] == 0
    assert run.summary["pipeline"]["deliberately_invalid_rows"] == 5
    assert run.summary["pipeline"]["schema_rejected_rows"] == 4
    assert run.summary["pipeline"]["quality_rejected_rows"] == 1
    assert run.summary["pipeline"]["clean_quote_rows"] == 72
    assert run.summary["pipeline"]["iv_inversions"] == 72
    assert run.summary["forward_inference"]["max_absolute_error_bps"] == 0.0
    assert run.summary["ssvi_primary_surface"]["surface_iv_rmse_volatility_points"] < 0.0002
    assert run.summary["ssvi_primary_surface"]["sufficient_condition_failures"] == 0
    assert run.summary["price_space_static_arbitrage"]["violations"] == 0
    assert run.summary["execution_gates"]["model_relative_candidates"] == 8
    assert run.summary["execution_gates"]["rejected_by_execution_gates"] == 8
    assert run.summary["execution_gates"]["accepted_as_executable"] == 0


def test_public_evidence_contains_no_provider_or_empirical_identifier() -> None:
    evidence_root = Path(__file__).resolve().parents[1] / "docs" / "assets"
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(evidence_root.glob("synthetic_evidence.*"))
    ).casefold()

    assert "synthetic" in text
    assert "thetadata" not in text


def test_synthetic_visual_is_valid_labelled_svg() -> None:
    visual = Path(__file__).resolve().parents[1] / "docs" / "assets" / "synthetic_evidence.svg"
    root = ElementTree.fromstring(visual.read_text(encoding="utf-8"))
    visible_text = " ".join(element.text or "" for element in root.iter())

    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.attrib["viewBox"] == "0 0 1200 680"
    assert "SYNTHETIC — NO MARKET DATA OR TRADING CLAIM" in visible_text
    assert "SSVI primary smoother" in visible_text
    assert "Heston structural diagnostic" in visible_text


def test_readme_numbers_match_committed_summary() -> None:
    root = Path(__file__).resolve().parents[1]
    summary = json.loads(
        (root / "docs" / "assets" / "synthetic_evidence.json").read_text(encoding="utf-8")
    )
    readme = (root / "README.md").read_text(encoding="utf-8")

    expected_fragments = [
        f"77 / {summary['pipeline']['clean_quote_rows']}",
        f"{summary['pipeline']['deliberately_invalid_rows']} / 5",
        f"{summary['forward_inference']['max_absolute_error_bps']:.6f} bps max error",
        f"72 / 72; {summary['iv_inversion']['rmse_volatility_points']:.8f} RMSE",
        (
            f"{summary['ssvi_primary_surface']['surface_iv_rmse_volatility_points']:.8f} "
            "IV RMSE; 0 condition failures"
        ),
        f"12 points; {summary['heston_structural_diagnostic']['price_rmse']:.6f} price RMSE",
        "8 / 8; 0 accepted",
    ]
    for fragment in expected_fragments:
        assert fragment in readme
