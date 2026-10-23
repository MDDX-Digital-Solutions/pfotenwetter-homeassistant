"""Einrichten mit einem Code aus der App. docs/89, Abschnitt 3.

Der Code entsteht in der App unter Einstellungen → Home Assistant (sechs
Zeichen, zehn Minuten gültig). Das Einlösen ist zugleich die Probe, ob der
Server erreichbar ist (Regel *test-before-configure*).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .api import (
    PfotenwetterCodeFehler,
    PfotenwetterFehler,
    PfotenwetterGebremst,
    Zugang,
    koppele,
)
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CODE,
    CONF_EXPIRES_AT,
    CONF_REFRESH_SECRET,
    CONF_ZONE,
    DOMAIN,
    STANDARD_ZONE,
)
from .coordinator import PfotenwetterConfigEntry

_LOGGER = logging.getLogger(__name__)

CODE_SCHEMA = vol.Schema({vol.Required(CONF_CODE): str})


def _daten(zugang: Zugang) -> dict[str, str]:
    return {
        CONF_ACCESS_TOKEN: zugang.access_token,
        CONF_EXPIRES_AT: zugang.expires_at.isoformat(),
        CONF_REFRESH_SECRET: zugang.refresh_secret,
    }


class PfotenwetterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Koppeln per Code."""

    VERSION = 1

    def _titel(self) -> str:
        """Wie die App: Deutsch „PfotenWetter“, sonst „PawWeather“ (Entscheidung 6)."""
        return "PfotenWetter" if self.hass.config.language.startswith("de") else "PawWeather"

    async def _loese_ein(self, code: str) -> tuple[Zugang | None, dict[str, str]]:
        try:
            zugang = await koppele(
                async_get_clientsession(self.hass), code, self.hass.config.language
            )
        except PfotenwetterCodeFehler:
            return None, {"base": "code_ungueltig"}
        except PfotenwetterGebremst:
            return None, {"base": "gebremst"}
        except PfotenwetterFehler:
            return None, {"base": "nicht_erreichbar"}
        except Exception:
            _LOGGER.exception("Unerwarteter Fehler beim Koppeln")
            return None, {"base": "unknown"}
        return zugang, {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            zugang, errors = await self._loese_ein(user_input[CONF_CODE])
            if zugang is not None:
                await self.async_set_unique_id(zugang.pairing_id)
                # **Mit `updates`**: Derselbe Telefoncode ein zweites Mal hat
                # die bisherige Kopplung am Server schon ersetzt (eine HA je
                # Telefon). Der bestehende Eintrag bekommt deshalb den neuen
                # Zugang, statt mit einem toten Token stehen zu bleiben.
                self._abort_if_unique_id_configured(updates=_daten(zugang))
                return self.async_create_entry(title=self._titel(), data=_daten(zugang))
        return self.async_show_form(step_id="user", data_schema=CODE_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Die Kopplung wurde in der App getrennt oder durch eine neue ersetzt."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            zugang, errors = await self._loese_ein(user_input[CONF_CODE])
            if zugang is not None:
                await self.async_set_unique_id(zugang.pairing_id)
                self._abort_if_unique_id_mismatch(reason="anderes_telefon")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=_daten(zugang)
                )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=CODE_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: PfotenwetterConfigEntry) -> PfotenwetterOptionsFlow:
        return PfotenwetterOptionsFlow()


class PfotenwetterOptionsFlow(OptionsFlowWithReload):
    """Welche Zone abgefragt wird – Vorgabe ist das Zuhause."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        schema = vol.Schema(
            {
                vol.Required(CONF_ZONE, default=STANDARD_ZONE): EntitySelector(
                    EntitySelectorConfig(domain="zone")
                )
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, self.config_entry.options),
        )
