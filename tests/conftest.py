"""Gemeinsame Testdaten: ein gekoppelter Eintrag und Serverantworten wie im Schema."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.pfotenwetter.const import (
    CONF_ACCESS_TOKEN,
    CONF_EXPIRES_AT,
    CONF_REFRESH_SECRET,
    DOMAIN,
    KONTO_SERVER,
    WETTER_SERVER,
)

KOPPLUNG = "a" * 32
SCHLUESSEL = "erneuerungsschluessel-" + "x" * 30


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> Generator[None]:
    yield


@pytest.fixture(autouse=True)
def ort_muenchen(hass: HomeAssistant) -> None:
    """Die Testumgebung von HA steht in San Diego -- also beim US-Server."""
    hass.config.latitude, hass.config.longitude = 48.137154, 11.576124


def zugang(token: str = "token-1", tage: int = 30) -> dict[str, Any]:
    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_at": (datetime.now(UTC) + timedelta(days=tage)).isoformat(),
    }


def kopplungsantwort(token: str = "token-1", kennung: str = KOPPLUNG) -> dict[str, Any]:
    return {**zugang(token), "refresh_secret": SCHLUESSEL, "pairing_id": kennung}


VORHERSAGE: dict[str, Any] = {
    "source": "Deutscher Wetterdienst",
    "source_short": "DWD",
    "notice": "Werte umgerechnet",
    "station": {
        "id": "10865",
        "name": "München",
        "lat": 48.1,
        "lon": 11.5,
        "altitude_m": 520,
        "distance_km": 3.1,
    },
    "issued_at": "2026-10-23T06:00:00Z",
    "age_minutes": 40,
    "stale": False,
    "valid_at": ["2026-10-23T10:00:00Z", "2026-10-23T11:00:00Z", "2026-10-23T12:00:00Z"],
    "walk_light": {
        "level": "gelb",
        "reasons": ["Warm für kurznasige Hunde"],
        "apparent_temperature_celsius": 24.5,
        "effective_temperature_celsius": 25.0,
        "sunny": True,
        "limiting_dog": 1,
        "provisional": False,
    },
    "paw_index": {
        "level": "gelb",
        "surface_temperature_celsius": 43.2,
        "hand_test": True,
        "noteworthy": True,
        "hand_test_hint": "Handrücken sieben Sekunden auf den Boden.",
    },
    "walk_light_hours": [
        {"level": "gelb", "reasons": [], "limiting_dog": 1},
        {"level": "rot", "reasons": [], "limiting_dog": 1},
    ],
    "current_index": 1,
    "series": {"temperature_celsius": [20.0, 22.5, 24.0]},
    "today_min_temperature_celsius": 11.0,
    "today_max_temperature_celsius": 25.5,
}

NOWCAST: dict[str, Any] = {
    "source": "Deutscher Wetterdienst",
    "notice": "",
    "latitude": 48.1,
    "longitude": 11.5,
    "summary": {
        "state": "trocken",
        "intensity": None,
        "drizzle": False,
        "rate_mm_per_hour": 0.0,
        "starts_in_minutes": 25,
        "ends_in_minutes": None,
    },
    "steps": [],
}

WARNUNGEN: dict[str, Any] = {
    "quelle": "Deutscher Wetterdienst",
    "warnungen": [
        {
            "id": "1",
            "event": "GEWITTER",
            "level": {"wert": 2, "beschriftung": "Markante Wetterwarnung"},
            "headline": "Amtliche WARNUNG vor GEWITTER",
            "description": "",
            "instruction": "",
            "sender": "DWD",
        }
    ],
    "behoerdenwarnungen": [],
}


@pytest.fixture
def eintrag() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="PfotenWetter",
        unique_id=KOPPLUNG,
        data={
            CONF_ACCESS_TOKEN: "token-1",
            CONF_EXPIRES_AT: (datetime.now(UTC) + timedelta(days=20)).isoformat(),
            CONF_REFRESH_SECRET: SCHLUESSEL,
        },
    )


def server(
    aioclient_mock: AiohttpClientMocker,
    *,
    premium: bool = True,
    region: str = "eu",
    hunde: list[str] | None = None,
) -> None:
    """Antworten des Servers, wie sie das Schema beschreibt."""
    aioclient_mock.get(
        f"{KONTO_SERVER}/v1/homeassistant",
        json={"premium": premium, "valid_until": None, "paired": True},
    )
    aioclient_mock.get(
        f"{KONTO_SERVER}/v1/homeassistant/hunde",
        json={"dogs": hunde if hunde is not None else ["mops:1:0"]},
        status=200 if premium else 402,
    )
    aioclient_mock.post(
        f"{KONTO_SERVER}/v1/auth/regionstoken", json={**zugang("region"), "ziel": "us"}
    )
    wetter = WETTER_SERVER[region]
    aioclient_mock.post(f"{wetter}/v1/forecast", json=VORHERSAGE)
    aioclient_mock.post(f"{wetter}/v1/nowcast", json=NOWCAST)
    aioclient_mock.get(f"{wetter}/v1/warnungen", json=WARNUNGEN)
    aioclient_mock.delete(f"{KONTO_SERVER}/v1/homeassistant", status=204)
