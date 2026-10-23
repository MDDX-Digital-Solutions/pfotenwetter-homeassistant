"""Region, Geohash, Diagnose, Manifest -- was ohne Server prüfbar ist."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.pfotenwetter.const import VERSION
from custom_components.pfotenwetter.diagnostics import async_get_config_entry_diagnostics
from custom_components.pfotenwetter.geohash import kodiere
from custom_components.pfotenwetter.region import NORDAMERIKA, wetterregion

from .conftest import SCHLUESSEL, server

WURZEL = Path(__file__).parent.parent


@pytest.mark.parametrize(
    ("breite", "laenge", "region"),
    [
        (48.14, 11.58, "eu"),  # München
        (39.74, -104.99, "us"),  # Denver
        (61.22, -149.90, "us"),  # Anchorage
        (21.31, -157.86, "us"),  # Honolulu
        (52.0, 177.0, "us"),  # Aleuten jenseits des 180. Längengrads
        (18.47, -66.11, "eu"),  # Puerto Rico fehlt mit Absicht, wie in der App
        (51.0, -62.5, "us"),  # Ränder eingeschlossen
    ],
)
def test_wetterregion(breite: float, laenge: float, region: str) -> None:
    assert wetterregion(breite, laenge) == region


def test_rechtecke_wie_in_der_app() -> None:
    """Dieselben Zahlen wie `Serverregion.swift` -- nur im Monorepo prüfbar."""
    swift = WURZEL.parent / "ios" / "Sources" / "Core" / "Serverregion.swift"
    if not swift.exists():
        pytest.skip("Nicht im Monorepo")
    gefunden = re.findall(
        r"Kiste\(west: (-?[\d.]+), sued: (-?[\d.]+), ost: (-?[\d.]+), nord: (-?[\d.]+)\)",
        swift.read_text(encoding="utf-8"),
    )
    assert tuple(tuple(float(z) for z in kiste) for kiste in gefunden) == NORDAMERIKA


def test_geohash() -> None:
    # Das Beispiel aus der Beschreibung des Verfahrens.
    assert kodiere(57.64911, 10.40744, 11) == "u4pruydqqvj"
    assert kodiere(48.137154, 11.576124) == "u281z"
    assert len(kodiere(0.0, 0.0)) == 5


def test_fassung_im_manifest() -> None:
    manifest = json.loads(
        (WURZEL / "custom_components" / "pfotenwetter" / "manifest.json").read_text()
    )
    assert manifest["version"] == VERSION
    assert manifest["iot_class"] == "cloud_polling"
    hacs = json.loads((WURZEL / "hacs.json").read_text())
    assert hacs["name"] == manifest["name"]


def test_uebersetzungen_vollstaendig() -> None:
    """Jeder Schlüssel des Englischen steht auch im Deutschen und umgekehrt."""
    ordner = WURZEL / "custom_components" / "pfotenwetter"

    def schluessel(daten: object, pfad: str = "") -> set[str]:
        if isinstance(daten, dict):
            return set().union(*(schluessel(w, f"{pfad}/{k}") for k, w in daten.items()))
        return {pfad}

    en = json.loads((ordner / "translations" / "en.json").read_text())
    de = json.loads((ordner / "translations" / "de.json").read_text())
    assert schluessel(en) == schluessel(de)
    assert en == json.loads((ordner / "strings.json").read_text())


async def test_diagnose_ohne_token_und_ort(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, eintrag: MockConfigEntry
) -> None:
    server(aioclient_mock)
    eintrag.add_to_hass(hass)
    await hass.config_entries.async_setup(eintrag.entry_id)
    await hass.async_block_till_done()
    diagnose = await async_get_config_entry_diagnostics(hass, eintrag)
    text = json.dumps(diagnose)
    assert SCHLUESSEL not in text
    assert "token-1" not in text
    assert "48.1" not in text and "11.5" not in text
    assert diagnose["stand"]["premium"] is True
