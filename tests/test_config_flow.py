"""Einrichten per Code, erneut koppeln, Ort wählen."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.pfotenwetter.const import (
    CONF_ACCESS_TOKEN,
    CONF_CODE,
    CONF_REFRESH_SECRET,
    CONF_ZONE,
    DOMAIN,
    KONTO_SERVER,
    VERSION,
)

from .conftest import KOPPLUNG, SCHLUESSEL, kopplungsantwort, server

KOPPELN = f"{KONTO_SERVER}/v1/homeassistant/koppeln"


async def test_koppeln_legt_den_eintrag_an(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    hass.config.language = "de"
    aioclient_mock.post(KOPPELN, json=kopplungsantwort())
    server(aioclient_mock)
    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert ergebnis["type"] is FlowResultType.FORM
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"], {CONF_CODE: "abc-def"}
    )
    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY
    assert ergebnis["title"] == "PfotenWetter"
    assert ergebnis["data"][CONF_REFRESH_SECRET] == SCHLUESSEL
    assert ergebnis["result"].unique_id == KOPPLUNG
    # Der Code geht so an den Server, wie er eingetippt wurde, mit der Fassung.
    methode, adresse, rumpf, kopf = aioclient_mock.mock_calls[0]
    assert (methode.lower(), str(adresse)) == ("post", KOPPELN)
    assert rumpf == {"code": "abc-def", "version": VERSION}
    assert "Authorization" not in kopf


async def test_englisch_heisst_pawweather(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    hass.config.language = "en"
    aioclient_mock.post(KOPPELN, json=kopplungsantwort())
    server(aioclient_mock)
    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"], {CONF_CODE: "ABCDEF"}
    )
    assert ergebnis["title"] == "PawWeather"


async def test_falscher_code_und_kein_netz(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.post(KOPPELN, status=404)
    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"], {CONF_CODE: "ZZZZZZ"}
    )
    assert ergebnis["errors"] == {"base": "code_ungueltig"}

    aioclient_mock.clear_requests()
    aioclient_mock.post(KOPPELN, status=429)
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"], {CONF_CODE: "ZZZZZZ"}
    )
    assert ergebnis["errors"] == {"base": "gebremst"}

    aioclient_mock.clear_requests()
    aioclient_mock.post(KOPPELN, status=503)
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"], {CONF_CODE: "ZZZZZZ"}
    )
    assert ergebnis["errors"] == {"base": "nicht_erreichbar"}

    # Und danach klappt es doch.
    aioclient_mock.clear_requests()
    aioclient_mock.post(KOPPELN, json=kopplungsantwort())
    server(aioclient_mock)
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"], {CONF_CODE: "ABCDEF"}
    )
    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY


async def test_dasselbe_telefon_erneuert_den_eintrag(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, eintrag: MockConfigEntry
) -> None:
    """Ein zweiter Code desselben Telefons hat die alte Kopplung am Server
    ersetzt -- der Eintrag bekommt den neuen Zugang, statt tot stehen zu bleiben."""
    eintrag.add_to_hass(hass)
    aioclient_mock.post(KOPPELN, json=kopplungsantwort(token="token-neu"))
    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"], {CONF_CODE: "ABCDEF"}
    )
    assert ergebnis["type"] is FlowResultType.ABORT
    assert ergebnis["reason"] == "already_configured"
    assert eintrag.data[CONF_ACCESS_TOKEN] == "token-neu"


async def test_reauth_mit_neuem_code(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, eintrag: MockConfigEntry
) -> None:
    eintrag.add_to_hass(hass)
    aioclient_mock.post(KOPPELN, json=kopplungsantwort(token="token-wieder"))
    server(aioclient_mock)
    ergebnis = await eintrag.start_reauth_flow(hass)
    assert ergebnis["step_id"] == "reauth_confirm"
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"], {CONF_CODE: "ABCDEF"}
    )
    assert ergebnis["type"] is FlowResultType.ABORT
    assert ergebnis["reason"] == "reauth_successful"
    assert eintrag.data[CONF_ACCESS_TOKEN] == "token-wieder"


async def test_reauth_mit_anderem_telefon_bricht_ab(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, eintrag: MockConfigEntry
) -> None:
    eintrag.add_to_hass(hass)
    aioclient_mock.post(KOPPELN, json=kopplungsantwort(kennung="b" * 32))
    ergebnis = await eintrag.start_reauth_flow(hass)
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"], {CONF_CODE: "ABCDEF"}
    )
    assert ergebnis["type"] is FlowResultType.ABORT
    assert ergebnis["reason"] == "anderes_telefon"


async def test_zone_waehlen(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, eintrag: MockConfigEntry
) -> None:
    server(aioclient_mock)
    eintrag.add_to_hass(hass)
    await hass.config_entries.async_setup(eintrag.entry_id)
    await hass.async_block_till_done()
    ergebnis = await hass.config_entries.options.async_init(eintrag.entry_id)
    assert ergebnis["type"] is FlowResultType.FORM
    ergebnis = await hass.config_entries.options.async_configure(
        ergebnis["flow_id"], {CONF_ZONE: "zone.home"}
    )
    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY
    assert eintrag.options == {CONF_ZONE: "zone.home"}
