from sofia.voice.sapi import (
    choose_voice,
    sapi_rate,
    sapi_volume,
)


def test_sapi_rate_mapping_is_bounded_and_centered():
    assert sapi_rate(1.0) == 0
    assert sapi_rate(0.75) == -4
    assert sapi_rate(1.25) == 4
    assert sapi_rate(0.0) == -10
    assert sapi_rate(2.0) == 10


def test_sapi_volume_mapping_is_bounded():
    assert sapi_volume(1.0) == 100
    assert sapi_volume(0.75) == 75
    assert sapi_volume(0.0) == 0
    assert sapi_volume(2.0) == 100


def test_voice_hint_wins_then_feminine_fallback_then_first_voice():
    voices = (
        "Microsoft David Desktop",
        "Microsoft Zira Desktop",
        "Other Voice",
    )
    assert (
        choose_voice(voices, "David")
        == "Microsoft David Desktop"
    )
    assert (
        choose_voice(voices, None)
        == "Microsoft Zira Desktop"
    )
    assert (
        choose_voice(("Only Voice",), None)
        == "Only Voice"
    )
    assert choose_voice((), None) is None
