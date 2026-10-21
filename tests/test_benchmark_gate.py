"""The evidence command must fail on missing, additional or incorrect outputs."""

import pytest

from scripts import benchmark


def result(**changes):
    return {
        "file": "sample.pdf",
        "cell_accuracy": 1,
        "row_recall": 1,
        "row_precision": 1,
        "headers_exact": True,
        **changes,
    }


@pytest.mark.parametrize(
    "changed",
    [
        {"cell_accuracy": 0.99},
        {"row_recall": 0.5},
        {"row_precision": 0.5},
        {"headers_exact": False},
    ],
)
def test_evidence_gate_rejects_cell_row_and_header_regressions(changed):
    assert benchmark.regression_failures({"results": [result(**changed)]}) == [
        "sample.pdf"
    ]


def test_evidence_gate_does_not_pass_an_empty_evaluation():
    assert benchmark.regression_failures({"results": []})
    assert benchmark.regression_failures({"results": [result()]}) == []


def test_check_exit_code_and_output_directory(monkeypatch, tmp_path):
    calls = []

    def failed_run(output_dir):
        calls.append(output_dir)
        return {"results": [result(row_precision=0.5)]}

    monkeypatch.setattr(benchmark, "benchmark", failed_run)
    assert benchmark.main(["--check", "--output-dir", str(tmp_path)]) == 1
    assert calls == [tmp_path]
    assert benchmark.main([]) == 0  # Legacy report-only usage remains available.
