"""Binärsensoren: Regen jetzt, erweiterte Funktionen."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .coordinator import PfotenwetterConfigEntry
from .entity import PfotenwetterEntity, quelle

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class PfotenBinaerBeschreibung(BinarySensorEntityDescription):
    koordinator: str
    wert: Callable[[dict[str, Any]], bool | None]


def _regnet(daten: dict[str, Any]) -> bool | None:
    zustand = (daten.get("summary") or {}).get("state")
    if zustand == "unbekannt" or zustand is None:
        return None
    return zustand == "regen"


BINAERSENSOREN: tuple[PfotenBinaerBeschreibung, ...] = (
    PfotenBinaerBeschreibung(
        key="regen_jetzt",
        translation_key="regen_jetzt",
        koordinator="nowcast",
        device_class=BinarySensorDeviceClass.MOISTURE,
        wert=_regnet,
    ),
    PfotenBinaerBeschreibung(
        key="erweiterte_funktionen",
        translation_key="erweiterte_funktionen",
        koordinator="vorhersage",
        entity_category=EntityCategory.DIAGNOSTIC,
        wert=lambda d: bool((d.get("stand") or {}).get("premium")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PfotenwetterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    laufzeit = entry.runtime_data
    async_add_entities(
        PfotenBinaersensor(getattr(laufzeit, beschreibung.koordinator), entry, beschreibung)
        for beschreibung in BINAERSENSOREN
    )


class PfotenBinaersensor(PfotenwetterEntity, BinarySensorEntity):
    entity_description: PfotenBinaerBeschreibung

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        entry: PfotenwetterConfigEntry,
        description: PfotenBinaerBeschreibung,
    ) -> None:
        super().__init__(coordinator, entry, description)

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.wert(self.coordinator.data or {})

    @property
    def attribution(self) -> str | None:
        if self.entity_description.key != "regen_jetzt":
            return None
        return quelle(self.coordinator.data)
