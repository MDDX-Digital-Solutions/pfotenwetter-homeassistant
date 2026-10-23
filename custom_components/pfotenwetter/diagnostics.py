"""Diagnose ohne Token, Schlüssel und Ort.

„Location data, like coordinates and addresses“ gehört nicht in eine
Diagnose (HA-Entwicklerdoku, Diagnostics) – eine Diagnose wird gern in ein
öffentliches Fehlerticket kopiert.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_ACCESS_TOKEN, CONF_REFRESH_SECRET
from .coordinator import PfotenwetterConfigEntry

GESCHWAERZT = {
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_SECRET,
    "latitude",
    "longitude",
    "lat",
    "lon",
    "station",
    "unique_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PfotenwetterConfigEntry
) -> dict[str, Any]:
    laufzeit = entry.runtime_data
    vorhersage = laufzeit.vorhersage.data or {}
    return async_redact_data(
        {
            "eintrag": {"data": dict(entry.data), "options": dict(entry.options)},
            "region": vorhersage.get("region"),
            "stand": vorhersage.get("stand"),
            "eigene_hunde": vorhersage.get("hunde"),
            "vorhersage": {
                schluessel: wert
                for schluessel, wert in (vorhersage.get("vorhersage") or {}).items()
                if schluessel not in {"series", "valid_at", "walk_light_hours"}
            },
            "nowcast": {
                schluessel: wert
                for schluessel, wert in (laufzeit.nowcast.data or {}).items()
                if schluessel != "steps"
            },
            "warnungen": len((laufzeit.warnungen.data or {}).get("warnungen") or []),
        },
        GESCHWAERZT,
    )
