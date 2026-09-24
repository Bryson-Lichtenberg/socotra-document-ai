from pathlib import Path

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def test_app_loads_without_a_run():
    app = AppTest.from_file(APP, default_timeout=60).run()
    assert not app.exception
    assert any("Source caveat" in w.value for w in app.warning)


def test_golden_run_from_the_app():
    app = AppTest.from_file(APP, default_timeout=180).run()
    next(b for b in app.button if b.label.startswith("Generate template")).click().run()
    assert not app.exception
    assert app.session_state.result["status"] in {"PASS", "REVIEW"}
    assert any("Overall status" in m.value for m in app.markdown)
