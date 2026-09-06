"""Comfort model tests (spec §9): transparent, explainable rules."""
from services.comfort_model import comfort_band, comfort_for


def test_train_class_ordering():
    sl, _ = comfort_for("train", train_class="SL", duration_minutes=300)
    a3, _ = comfort_for("train", train_class="3A", duration_minutes=300)
    a2, _ = comfort_for("train", train_class="2A", duration_minutes=300)
    assert sl < a3 < a2


def test_ac_sleeper_bus_beats_seater():
    ac_sleeper, _ = comfort_for("bus", ac=True, sleeper=True, duration_minutes=360)
    ac_seater, _ = comfort_for("bus", ac=True, sleeper=False, duration_minutes=360)
    assert ac_sleeper > ac_seater


def test_long_journey_penalty_note():
    score, notes = comfort_for("bus", ac=True, sleeper=True, duration_minutes=15 * 60)
    assert score < 7
    assert any("long journey" in n for n in notes)


def test_stops_penalty_with_elderly():
    _, notes = comfort_for("flight", duration_minutes=120, stops=1, elderly=2)
    assert any("elderly" in n for n in notes)


def test_overnight_seated_penalty():
    seated, n1 = comfort_for("train", train_class="2S", duration_minutes=600, overnight=True)
    _, n2 = comfort_for("train", train_class="SL", duration_minutes=600, overnight=True)
    assert any("overnight" in n and "seated" in n for n in n1)
    assert not any("penalty" in n and "overnight" in n for n in n2)


def test_scores_bounded_1_to_10():
    low, _ = comfort_for("bus", ac=False, sleeper=False, duration_minutes=16 * 60, stops=2)
    high, _ = comfort_for("train", train_class="1A", duration_minutes=120)
    assert 1 <= low <= 10
    assert high <= 10


def test_band_labels():
    assert comfort_band(2) == "low"
    assert comfort_band(5) == "moderate"
    assert comfort_band(7) == "high"
    assert comfort_band(9) == "premium"
    assert comfort_band(None) == "—"
