from pathlib import Path

from app.utils.step_bytes import is_step_bytes, step_filename_hint

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "cad" / "box_100x60x20.step"


def test_is_step_bytes():
    assert is_step_bytes(FIXTURE.read_bytes())
    assert not is_step_bytes(b"not a step file" * 10)


def test_step_filename_hint():
    assert step_filename_hint("a.STP").endswith(".STP")
    assert step_filename_hint("").endswith(".stp")
