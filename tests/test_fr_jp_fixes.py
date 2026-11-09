"""Fixes from the azsono03 fork.

- ESPAltherma v2 (individual entities): source_stale judged on the
  freshest v2 entity, not on the slow-changing `source_sensor`.
- `custom` model: the spec typed in the config flow is used as datasheet.
- Altherma 3 H HT single-phase outdoor units EPRA14/16/18DAV3.
- Leaving water before BUH (R1T) is resolved for v2 sources (delta-T).
"""
from __future__ import annotations

import time
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.daikin_cycle_ml.binary_sensor import _is_source_stale
from custom_components.daikin_cycle_ml.const import (
    CONSUMED_ATTRIBUTES,
    DOMAIN,
    MODEL_CHOICES,
    MODEL_CUSTOM,
    MODEL_EPRA14DAV3,
    MODEL_EPRA16DAV3,
    MODEL_EPRA18DAV3,
    MODEL_LABELS,
    SOURCE_TYPE_INDIVIDUAL,
    family_for_model,
    models_in_family,
)
from custom_components.daikin_cycle_ml.coordinator import DaikinCycleMLCoordinator
from custom_components.daikin_cycle_ml.engine.espaltherma_v2.resolver import (
    resolve_attrs,
)
from custom_components.daikin_cycle_ml.engine.model_datasheets import (
    get_datasheet,
    load_bundled,
    merge,
)


def _state(ts: float, eid: str) -> SimpleNamespace:
    dt = datetime.fromtimestamp(ts, tz=UTC)
    return SimpleNamespace(entity_id=eid, last_updated=dt, last_reported=dt)


class _States:
    def __init__(self, states: dict[str, SimpleNamespace]) -> None:
        self._s = states

    def get(self, eid):
        return self._s.get(eid)

    def async_all(self, domain=None):
        return [
            s for e, s in self._s.items()
            if domain is None or e.startswith(domain + ".")
        ]


def _coord(states: dict[str, SimpleNamespace]) -> SimpleNamespace:
    return SimpleNamespace(
        hass=SimpleNamespace(states=_States(states)),
        source_entity="sensor.espaltherma_operation_mode",
        source_type=SOURCE_TYPE_INDIVIDUAL,
        individual_prefix="sensor.espaltherma_",
        options={},
    )


def test_individual_source_fresh_when_any_entity_reports():
    now = time.time()
    c = _coord({
        # unchanged for an hour: used to raise a false "source stale"
        "sensor.espaltherma_operation_mode": _state(now - 3600, "sensor.espaltherma_operation_mode"),
        "sensor.espaltherma_uptime": _state(now - 20, "sensor.espaltherma_uptime"),
    })
    assert _is_source_stale(SimpleNamespace(last_success_ts=now), c) is False


def test_individual_source_stale_when_all_entities_silent():
    now = time.time()
    c = _coord({
        "sensor.espaltherma_operation_mode": _state(now - 3600, "sensor.espaltherma_operation_mode"),
        "binary_sensor.espaltherma_buh_step1": _state(now - 900, "binary_sensor.espaltherma_buh_step1"),
    })
    assert _is_source_stale(SimpleNamespace(last_success_ts=now), c) is True


@pytest.mark.parametrize(
    ("model", "kw", "cop"),
    [(MODEL_EPRA14DAV3, 5.69, 4.67), (MODEL_EPRA16DAV3, 9.0, 5.0), (MODEL_EPRA18DAV3, 9.0, 5.0)],
)
def test_ht_single_phase_models(model, kw, cop):
    assert model in MODEL_CHOICES
    assert "Altherma 3 H HT" in MODEL_LABELS[model]
    assert family_for_model(model) == "epra"
    assert model in models_in_family("epra")
    spec = get_datasheet(merge(load_bundled(), {}), model)
    assert spec is not None
    assert spec["kw"] == kw
    assert spec["nom_cop"] == cop
    assert spec["lwt_max"] == 70


def test_lw_before_buh_consumed_and_resolved_for_v2(hass):
    assert "Leaving water temp. before BUH (R1T)" in CONSUMED_ATTRIBUTES
    hass.states.async_set("sensor.espaltherma_leaving_water_temp_before_buh_r1t", "41.5")
    res = resolve_attrs(hass, prefix="sensor.espaltherma_")
    assert float(res.attrs["Leaving water temp. before BUH (R1T)"]) == 41.5


async def test_custom_flow_spec_used_as_datasheet(hass):
    spec = {
        "family": "Altherma 3 H HT", "kw": 5.69, "lwt_min": 25, "lwt_max": 70,
        "nom_cop": 4.67, "refrigerant": "R32",
        "points": [{"label": "A7/W35", "t_out": 7, "t_lwc": 35, "cop": 4.67}],
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"model": MODEL_CUSTOM, "source_sensor": "sensor.x", "custom_datasheet": spec},
    )
    coordinator = DaikinCycleMLCoordinator(hass, entry)
    await coordinator.async_reload_user_datasheets()
    assert coordinator.datasheet_sources.get(MODEL_CUSTOM) == "user"
    ds = get_datasheet(coordinator._datasheet_merged, MODEL_CUSTOM)
    assert ds is not None and ds["kw"] == 5.69


def test_french_reports_render():
    from custom_components.daikin_cycle_ml.engine.status_report import (
        ALERT_SCHEMA,
        ALERT_TITLES,
        build_cop_low_report,
        build_rich_alert,
        build_status_report,
        build_stooklijn_report,
    )

    assert set(ALERT_TITLES["fr"]) == set(ALERT_TITLES["en"])
    for kind in ALERT_SCHEMA:
        msg = build_rich_alert(kind, "warning", {"mode": "heating", "cph": 5}, language="fr")
        assert "Daikin Cycle ML" in msg
    rep = build_status_report({"state": "idle", "mode": "heating", "cycles_today": 3}, language="fr")
    assert "Cycles aujourd'hui" in rep and "chauffage" in rep
    assert "Conseil de loi d'eau" in build_stooklijn_report({"state": "keep"}, language="fr")
    assert "COP du jour bas" in build_cop_low_report(2.1, 10, language="fr")


def test_fr_json_mirrors_en_json():
    import json
    from pathlib import Path

    base = Path("custom_components/daikin_cycle_ml/translations")
    en = json.loads((base / "en.json").read_text(encoding="utf-8"))
    fr = json.loads((base / "fr.json").read_text(encoding="utf-8"))

    def keys(d, p=()):
        for k, v in d.items():
            if isinstance(v, dict):
                yield from keys(v, (*p, k))
            else:
                yield (*p, k)

    assert set(keys(en)) == set(keys(fr))
