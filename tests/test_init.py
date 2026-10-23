"""Einrichten, Sensoren, Token, Region, Abo."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.pfotenwetter.const import (
    CONF_ACCESS_TOKEN,
    CONF_EXPIRES_AT,
    CONF_REFRESH_SECRET,
    CONF_ZONE,
    DOMAIN,
    KONTO_SERVER,
    WETTER_SERVER,
)

from .conftest import KOPPLUNG, SCHLUESSEL, VORHERSAGE, server, zugang


def _aufrufe(aioclient_mock: AiohttpClientMocker, pfad: str) -> list[tuple]:
    return [
        aufruf
        for aufruf in aioclient_mock.mock_calls
        if str(aufruf[1]).split("?")[0].endswith(pfad)
    ]


async def _einrichten(hass: HomeAssistant, eintrag: MockConfigEntry) -> None:
    eintrag.add_to_hass(hass)
    await hass.config_entries.async_setup(eintrag.entry_id)
    await hass.async_block_till_done()


async def test_sensoren_mit_abo(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, eintrag: MockConfigEntry
) -> None:
    hass.config.latitude, hass.config.longitude = 48.137154, 11.576124
    server(aioclient_mock, hunde=["mops:1:0", ":0:1"])
    await _einrichten(hass, eintrag)
    assert eintrag.state is ConfigEntryState.LOADED

    ampel = hass.states.get("sensor.pfotenwetter_walk_light")
    assert ampel is not None and ampel.state == "gelb"
    assert ampel.attributes["begrenzender_hund"] == 1
    assert ampel.attributes["eigene_hunde"] == 2
    assert [s["stufe"] for s in ampel.attributes["stunden"]] == ["gelb", "rot"]
    # Die Stunden beginnen bei `current_index`.
    assert ampel.attributes["stunden"][0]["zeit"] == "2026-10-23T11:00:00Z"
    assert ampel.attributes["attribution"] == "Deutscher Wetterdienst – Werte umgerechnet"

    assert hass.states.get("sensor.pfotenwetter_paw_index").state == "gelb"
    assert hass.states.get("sensor.pfotenwetter_temperature").state == "22.5"
    assert hass.states.get("sensor.pfotenwetter_low_today").state == "11.0"
    assert hass.states.get("sensor.pfotenwetter_high_today").state == "25.5"
    assert hass.states.get("sensor.pfotenwetter_rain_starts_in").state == "25"
    assert hass.states.get("binary_sensor.pfotenwetter_raining_now").state == "off"
    assert hass.states.get("sensor.pfotenwetter_official_warnings").state == "1"
    assert hass.states.get("sensor.pfotenwetter_highest_warning_level").state == "2"
    assert hass.states.get("binary_sensor.pfotenwetter_extended_features").state == "on"

    # Die Hunde gehen mit, ungerundete Koordinaten (Entscheidung „b“).
    (vorhersage,) = _aufrufe(aioclient_mock, "/v1/forecast")
    assert vorhersage[2] == {"lat": 48.137154, "lon": 11.576124, "dog": ["mops:1:0", ":0:1"]}
    # HA zählt nicht als „benutzt“.
    assert vorhersage[3]["X-Pfotenwetter-Aufruf"] == "hintergrund"
    # Die Warnungen fragen mit der Zelle aus fünf Zeichen.
    (warnung,) = _aufrufe(aioclient_mock, "/v1/warnungen")
    assert "cell=u281z" in str(warnung[1])


async def test_ohne_abo_der_durchschnittshund(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, eintrag: MockConfigEntry
) -> None:
    server(aioclient_mock, premium=False)
    await _einrichten(hass, eintrag)
    assert _aufrufe(aioclient_mock, "/v1/homeassistant/hunde") == []
    (vorhersage,) = _aufrufe(aioclient_mock, "/v1/forecast")
    assert "dog" not in vorhersage[2]
    assert hass.states.get("binary_sensor.pfotenwetter_extended_features").state == "off"
    assert hass.states.get("sensor.pfotenwetter_walk_light").state == "gelb"


async def test_us_ort_fragt_den_us_server_mit_regionstoken(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, eintrag: MockConfigEntry
) -> None:
    hass.config.latitude, hass.config.longitude = 39.74, -104.99  # Denver
    server(aioclient_mock, region="us")
    await _einrichten(hass, eintrag)
    (vorhersage,) = _aufrufe(aioclient_mock, "/v1/forecast")
    assert str(vorhersage[1]).startswith(WETTER_SERVER["us"])
    assert vorhersage[3]["Authorization"] == "Bearer region"
    # Das Konto bleibt in der EU.
    (stand,) = _aufrufe(aioclient_mock, "/v1/homeassistant")[:1]
    assert str(stand[1]).startswith(KONTO_SERVER)
    # Ein Regionstoken für alle drei Abrufe, nicht je Abruf eines.
    assert len(_aufrufe(aioclient_mock, "/v1/auth/regionstoken")) == 1


async def test_ein_bald_ablaufendes_token_wird_erneuert_und_gemerkt(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, eintrag: MockConfigEntry
) -> None:
    eintrag = MockConfigEntry(
        domain=eintrag.domain,
        title=eintrag.title,
        unique_id=eintrag.unique_id,
        data={
            **eintrag.data,
            CONF_EXPIRES_AT: (datetime.now(UTC) + timedelta(hours=5)).isoformat(),
        },
    )
    aioclient_mock.post(f"{KONTO_SERVER}/v1/homeassistant/token", json=zugang("token-2"))
    server(aioclient_mock)
    await _einrichten(hass, eintrag)
    assert len(_aufrufe(aioclient_mock, "/v1/homeassistant/token")) == 1
    assert eintrag.data[CONF_ACCESS_TOKEN] == "token-2"
    (vorhersage,) = _aufrufe(aioclient_mock, "/v1/forecast")
    assert vorhersage[3]["Authorization"] == "Bearer token-2"


async def test_getrennt_in_der_app_startet_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, eintrag: MockConfigEntry
) -> None:
    aioclient_mock.get(f"{KONTO_SERVER}/v1/homeassistant", status=401)
    aioclient_mock.post(f"{KONTO_SERVER}/v1/homeassistant/token", status=401)
    await _einrichten(hass, eintrag)
    assert eintrag.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == ["reauth"]


async def test_server_weg_heisst_spaeter_nochmal(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, eintrag: MockConfigEntry
) -> None:
    aioclient_mock.get(f"{KONTO_SERVER}/v1/homeassistant", status=503)
    await _einrichten(hass, eintrag)
    assert eintrag.state is ConfigEntryState.SETUP_RETRY


async def test_entladen_und_entfernen_meldet_ab(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, eintrag: MockConfigEntry
) -> None:
    server(aioclient_mock)
    await _einrichten(hass, eintrag)
    assert await hass.config_entries.async_unload(eintrag.entry_id)
    assert eintrag.state is ConfigEntryState.NOT_LOADED
    await hass.config_entries.async_remove(eintrag.entry_id)
    await hass.async_block_till_done()
    abmeldungen = [a for a in aioclient_mock.mock_calls if a[0] == "delete"]
    assert len(abmeldungen) == 1


async def test_gewaehlte_zone_statt_zuhause(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    hass.states.async_set("zone.hundeplatz", "0", {"latitude": 52.52, "longitude": 13.405})
    eintrag = MockConfigEntry(
        domain=DOMAIN,
        title="PfotenWetter",
        unique_id=KOPPLUNG,
        data={
            CONF_ACCESS_TOKEN: "token-1",
            CONF_EXPIRES_AT: (datetime.now(UTC) + timedelta(days=20)).isoformat(),
            CONF_REFRESH_SECRET: SCHLUESSEL,
        },
        options={CONF_ZONE: "zone.hundeplatz"},
    )
    server(aioclient_mock)
    await _einrichten(hass, eintrag)
    (vorhersage,) = _aufrufe(aioclient_mock, "/v1/forecast")
    assert vorhersage[2]["lat"] == 52.52 and vorhersage[2]["lon"] == 13.405


async def test_gebremst_heisst_spaeter_nochmal(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, eintrag: MockConfigEntry
) -> None:
    aioclient_mock.get(
        f"{KONTO_SERVER}/v1/homeassistant", status=429, headers={"Retry-After": "120"}
    )
    await _einrichten(hass, eintrag)
    assert eintrag.state is ConfigEntryState.SETUP_RETRY


async def test_abgelaufenes_token_bekommt_einen_zweiten_versuch(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, eintrag: MockConfigEntry
) -> None:
    """Ein 401 mitten im Lauf: erst erneuern, dann noch einmal fragen."""
    antworten = iter([401, 200])

    async def stand(methode, adresse, daten):  # type: ignore[no-untyped-def]
        return AiohttpClientMockResponse(
            methode,
            adresse,
            status=next(antworten),
            json={"premium": False, "valid_until": None, "paired": True},
        )

    aioclient_mock.get(f"{KONTO_SERVER}/v1/homeassistant", side_effect=stand)
    aioclient_mock.post(f"{KONTO_SERVER}/v1/homeassistant/token", json=zugang("token-2"))
    server(aioclient_mock, premium=False)
    await _einrichten(hass, eintrag)
    assert eintrag.state is ConfigEntryState.LOADED
    assert eintrag.data[CONF_ACCESS_TOKEN] == "token-2"


async def test_us_regionstoken_wird_bei_401_neu_geholt(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, eintrag: MockConfigEntry
) -> None:
    hass.config.latitude, hass.config.longitude = 21.31, -157.86  # Honolulu
    antworten = iter([401, 200])

    async def vorhersage(methode, adresse, daten):  # type: ignore[no-untyped-def]
        return AiohttpClientMockResponse(methode, adresse, status=next(antworten), json=VORHERSAGE)

    aioclient_mock.post(f"{WETTER_SERVER['us']}/v1/forecast", side_effect=vorhersage)
    server(aioclient_mock, region="us")
    await _einrichten(hass, eintrag)
    assert eintrag.state is ConfigEntryState.LOADED
    assert len(_aufrufe(aioclient_mock, "/v1/auth/regionstoken")) == 2
