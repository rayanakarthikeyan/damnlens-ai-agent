from pathlib import Path

# Keep test data in the checkout; works in restricted hosts and on Windows.
(Path(__file__).resolve().parents[1] / "tmp").mkdir(exist_ok=True)
