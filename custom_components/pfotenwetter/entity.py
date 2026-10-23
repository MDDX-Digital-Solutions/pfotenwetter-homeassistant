"""Gemeinsame Grundlage der Entitäten: ein Gerät je Kopplung."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import DOMAIN, VERSION
from .coordinator import PfotenwetterConfigEntry


def quelle(daten: dict[str, Any] | None) -> str | None:
    """Der Quellenhinweis der Antwort (Lizenzpflicht), etwa „Deutscher Wetterdienst“."""
    if not daten:
        return None
    # Wetter und Radar tragen `source` und `notice`, die Warnlage `quelle`.
    teile = [daten.get("source") or daten.get("quelle") or "", daten.get("notice") or ""]
    text = " – ".join(teil for teil in teile if teil)
    return text or None


class PfotenwetterEntity(CoordinatorEntity[DataUpdateCoordinator[dict[str, Any]]]):
    """Eine Entität am Gerät „PfotenWetter“ bzw. „PawWeather“."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        entry: PfotenwetterConfigEntry,
        description: EntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        kennung = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{kennung}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, kennung)},
            name=entry.title,
            manufacturer="MDDX Digital Solutions",
            model="PfotenWetter / PawWeather",
            sw_version=VERSION,
            entry_type=DeviceEntryType.SERVICE,
        )
