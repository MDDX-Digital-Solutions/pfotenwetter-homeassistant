"""Drei Koordinatoren, weil drei Takte: Radar, Vorhersage, Warnungen.

Ein gemeinsamer Koordinator müsste im kürzesten Takt alles holen – die
Vorhersage alle fünf Minuten, obwohl sich die Ampel stündlich ändert. Das
wäre die Last, die docs/89 (Abschnitt 6) vermeiden will.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    PfotenwetterAboFehler,
    PfotenwetterApi,
    PfotenwetterAuthFehler,
    PfotenwetterFehler,
    PfotenwetterGebremst,
)
from .const import CONF_ZONE, DOMAIN, STANDARD_ZONE, TAKT_NOWCAST, TAKT_VORHERSAGE, TAKT_WARNUNGEN
from .geohash import kodiere
from .region import Region, wetterregion

_LOGGER = logging.getLogger(__name__)


@dataclass
class Laufzeit:
    """Was ein Eintrag zur Laufzeit hält (`entry.runtime_data`)."""

    api: PfotenwetterApi
    vorhersage: VorhersageKoordinator
    nowcast: NowcastKoordinator
    warnungen: WarnungsKoordinator


type PfotenwetterConfigEntry = ConfigEntry[Laufzeit]


@dataclass(frozen=True)
class Ort:
    breite: float
    laenge: float
    region: Region


def ort(hass: HomeAssistant, entry: ConfigEntry) -> Ort:
    """Der abgefragte Ort: die gewählte Zone, sonst der Heimatort von HA.

    **Ungerundet** (Entscheidung Lukas, 23.10.2026, „b“) – wie die App.
    """
    zone = entry.options.get(CONF_ZONE, STANDARD_ZONE)
    zustand = hass.states.get(zone)
    if zustand is not None and "latitude" in zustand.attributes:
        breite = float(zustand.attributes["latitude"])
        laenge = float(zustand.attributes["longitude"])
    else:
        breite, laenge = hass.config.latitude, hass.config.longitude
    return Ort(breite, laenge, wetterregion(breite, laenge))


class _Koordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Gemeinsame Fehlerbehandlung."""

    config_entry: PfotenwetterConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PfotenwetterConfigEntry,
        api: PfotenwetterApi,
        name: str,
        takt: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{name}",
            update_interval=takt,
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self._hole(ort(self.hass, self.config_entry))
        except PfotenwetterAuthFehler as fehler:
            # Die Kopplung wurde getrennt oder ersetzt: neuer Code nötig.
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="kopplung_ungueltig"
            ) from fehler
        except PfotenwetterGebremst as fehler:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="gebremst",
                retry_after=fehler.retry_after,
            ) from fehler
        except PfotenwetterFehler as fehler:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="nicht_erreichbar",
                translation_placeholders={"fehler": str(fehler)},
            ) from fehler

    async def _hole(self, wo: Ort) -> dict[str, Any]:
        raise NotImplementedError


class VorhersageKoordinator(_Koordinator):
    """Berechtigung, Hunde und Vorhersage – alle 30 Minuten."""

    def __init__(
        self, hass: HomeAssistant, entry: PfotenwetterConfigEntry, api: PfotenwetterApi
    ) -> None:
        super().__init__(hass, entry, api, "vorhersage", TAKT_VORHERSAGE)

    async def _hole(self, wo: Ort) -> dict[str, Any]:
        stand = await self.api.stand()
        hunde: list[str] = []
        if stand.get("premium"):
            # Mit Abo die Hunde des Telefons (Entscheidung Lukas, „a“). Ein
            # 402 heißt: Das Abo ist gerade abgelaufen – dann gilt der
            # Durchschnittshund, wie ohne Abo.
            try:
                hunde = await self.api.hunde()
            except PfotenwetterAboFehler:
                hunde = []
        vorhersage = await self.api.vorhersage(wo.region, wo.breite, wo.laenge, hunde)
        return {"stand": stand, "hunde": len(hunde), "vorhersage": vorhersage, "region": wo.region}


class NowcastKoordinator(_Koordinator):
    """Radar am Ort – alle fünf Minuten."""

    def __init__(
        self, hass: HomeAssistant, entry: PfotenwetterConfigEntry, api: PfotenwetterApi
    ) -> None:
        super().__init__(hass, entry, api, "nowcast", TAKT_NOWCAST)

    async def _hole(self, wo: Ort) -> dict[str, Any]:
        return await self.api.nowcast(wo.region, wo.breite, wo.laenge)


class WarnungsKoordinator(_Koordinator):
    """Amtliche Warnungen in der Zelle – alle zehn Minuten."""

    def __init__(
        self, hass: HomeAssistant, entry: PfotenwetterConfigEntry, api: PfotenwetterApi
    ) -> None:
        super().__init__(hass, entry, api, "warnungen", TAKT_WARNUNGEN)

    async def _hole(self, wo: Ort) -> dict[str, Any]:
        return await self.api.warnungen(
            wo.region, kodiere(wo.breite, wo.laenge), wo.breite, wo.laenge
        )
