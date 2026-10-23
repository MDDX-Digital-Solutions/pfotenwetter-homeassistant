"""PfotenWetter / PawWeather für Home Assistant. docs/89."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PfotenwetterApi, PfotenwetterFehler
from .const import CONF_ACCESS_TOKEN, CONF_EXPIRES_AT, CONF_REFRESH_SECRET
from .coordinator import (
    Laufzeit,
    NowcastKoordinator,
    PfotenwetterConfigEntry,
    VorhersageKoordinator,
    WarnungsKoordinator,
)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


def _zeitpunkt(wert: str) -> datetime:
    zeit = datetime.fromisoformat(wert)
    return zeit if zeit.tzinfo else zeit.replace(tzinfo=UTC)


async def async_setup_entry(hass: HomeAssistant, entry: PfotenwetterConfigEntry) -> bool:
    """Einen gekoppelten Eintrag einrichten."""

    def merke_token(token: str, bis: datetime) -> None:
        # Das erneuerte Token gehört in den Eintrag, sonst holte HA nach jedem
        # Neustart ein neues. Der Erneuerungsschlüssel bleibt, wie er ist.
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_ACCESS_TOKEN: token, CONF_EXPIRES_AT: bis.isoformat()},
        )

    api = PfotenwetterApi(
        async_get_clientsession(hass),
        access_token=entry.data[CONF_ACCESS_TOKEN],
        expires_at=_zeitpunkt(entry.data[CONF_EXPIRES_AT]),
        refresh_secret=entry.data[CONF_REFRESH_SECRET],
        sprache=hass.config.language,
        beim_neuen_token=merke_token,
    )
    vorhersage = VorhersageKoordinator(hass, entry, api)
    nowcast = NowcastKoordinator(hass, entry, api)
    warnungen = WarnungsKoordinator(hass, entry, api)
    # Der Reihe nach: Die Vorhersage erneuert notfalls das Token, und die
    # beiden anderen sollen nicht gleichzeitig dasselbe versuchen.
    await vorhersage.async_config_entry_first_refresh()
    await nowcast.async_config_entry_first_refresh()
    await warnungen.async_config_entry_first_refresh()

    entry.runtime_data = Laufzeit(
        api=api, vorhersage=vorhersage, nowcast=nowcast, warnungen=warnungen
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PfotenwetterConfigEntry) -> bool:
    """Einen Eintrag entladen."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: PfotenwetterConfigEntry) -> None:
    """„Integration entfernen“: Die Kopplung am Server sperren.

    Scheitert das (kein Netz, schon getrennt), bleibt es dabei: Die Zeile am
    Server verfällt nach 180 Tagen ohne Abruf, und die App kann sie trennen.
    """
    api = PfotenwetterApi(
        async_get_clientsession(hass),
        access_token=entry.data[CONF_ACCESS_TOKEN],
        expires_at=_zeitpunkt(entry.data[CONF_EXPIRES_AT]),
        refresh_secret=entry.data[CONF_REFRESH_SECRET],
        sprache=hass.config.language,
    )
    with contextlib.suppress(PfotenwetterFehler):
        await api.melde_ab()
