from __future__ import annotations


def test_classify_normalization_and_cache():
    from bot import epistemic

    epistemic._classify_normalized.cache_clear()
    first = epistemic.classify("  FORSE   funziona  ")
    second = epistemic.classify("forse funziona")
    info = epistemic.classify_cache_info()

    assert first == second
    assert first.layer == "IPOTESI"
    assert info.misses == 1
    assert info.hits == 1


def test_sdq1_limits_local_input(monkeypatch):
    from bot import config, sdq1

    monkeypatch.setattr(config, "SDQ1_URL", "")
    monkeypatch.setattr(config, "MAX_INPUT_CHARS", 12)
    result = sdq1.ask("forse " + ("x" * 500))

    assert result["provider"] == ["protocollo-nucleo"]
    assert result["agenti"] == 0
    assert result["run_id"]


def test_health_exposes_bounded_cache_metrics():
    from bot import sdq1

    health = sdq1.health()
    assert health["version"] == "0.3.0"
    assert set(health["classify_cache"]) == {"hits", "misses", "size"}
    assert health["classify_cache"]["size"] <= 1024
