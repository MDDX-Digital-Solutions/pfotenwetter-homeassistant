"""Sensoren: Ampel, Pfotenindex, Temperatur, Regen, Warnungen. docs/89, Abschnitt 5."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature, UnitOfTime, UnitOfVolumetricFlux
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import AMPELSTUFEN, PFOTENSTUFEN
from .coordinator import PfotenwetterConfigEntry
from .entity import PfotenwetterEntity, quelle

PARALLEL_UPDATES = 0

Daten = dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class PfotenSensorBeschreibung(SensorEntityDescription):
    """Welcher Koordinator, welcher Wert, welche Zusatzangaben."""

    koordinator: str
    wert: Callable[[Daten], Any]
    zusatz: Callable[[Daten], dict[str, Any]] | None = None


def _vorhersage(daten: Daten) -> Daten:
    return dict(daten.get("vorhersage") or {})


def _jetzt(daten: Daten, reihe: str) -> float | None:
    vorhersage = _vorhersage(daten)
    stelle = vorhersage.get("current_index")
    werte = (vorhersage.get("series") or {}).get(reihe) or []
    if stelle is None or stelle >= len(werte):
        return None
    return werte[stelle]


def _ampel_zusatz(daten: Daten) -> dict[str, Any]:
    vorhersage = _vorhersage(daten)
    ampel = vorhersage.get("walk_light") or {}
    stelle = vorhersage.get("current_index") or 0
    zeiten = vorhersage.get("valid_at") or []
    stunden = [
        {
            "zeit": zeiten[stelle + i] if stelle + i < len(zeiten) else None,
            "stufe": stunde.get("level"),
        }
        for i, stunde in enumerate(vorhersage.get("walk_light_hours") or [])
    ]
    return {
        "gruende": ampel.get("reasons") or [],
        "begrenzender_hund": ampel.get("limiting_dog"),
        "eigene_hunde": daten.get("hunde", 0),
        "vorlaeufig": ampel.get("provisional"),
        "stunden": stunden,
    }


def _pfoten_zusatz(daten: Daten) -> dict[str, Any]:
    pfoten = _vorhersage(daten).get("paw_index") or {}
    return {
        "oberflaechentemperatur": pfoten.get("surface_temperature_celsius"),
        "handprobe": pfoten.get("hand_test"),
        "hinweis": pfoten.get("hand_test_hint"),
    }


def _alle_warnungen(daten: Daten) -> list[Daten]:
    return list(daten.get("warnungen") or []) + list(daten.get("behoerdenwarnungen") or [])


def _hoechste_stufe(daten: Daten) -> int:
    return max(
        (int((w.get("level") or {}).get("wert") or 0) for w in _alle_warnungen(daten)),
        default=0,
    )


def _warn_zusatz(daten: Daten) -> dict[str, Any]:
    return {
        "warnungen": [
            {
                "titel": w.get("headline"),
                "stufe": (w.get("level") or {}).get("wert"),
                "ereignis": w.get("event"),
                "absender": w.get("sender"),
            }
            for w in _alle_warnungen(daten)
        ]
    }


def _zusammenfassung(daten: Daten) -> Daten:
    return dict(daten.get("summary") or {})


SENSOREN: tuple[PfotenSensorBeschreibung, ...] = (
    PfotenSensorBeschreibung(
        key="gassi_ampel",
        translation_key="gassi_ampel",
        koordinator="vorhersage",
        device_class=SensorDeviceClass.ENUM,
        options=AMPELSTUFEN,
        wert=lambda d: (_vorhersage(d).get("walk_light") or {}).get("level"),
        zusatz=_ampel_zusatz,
    ),
    PfotenSensorBeschreibung(
        key="pfotenindex",
        translation_key="pfotenindex",
        koordinator="vorhersage",
        device_class=SensorDeviceClass.ENUM,
        options=PFOTENSTUFEN,
        wert=lambda d: (_vorhersage(d).get("paw_index") or {}).get("level"),
        zusatz=_pfoten_zusatz,
    ),
    PfotenSensorBeschreibung(
        key="temperatur",
        translation_key="temperatur",
        koordinator="vorhersage",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        wert=lambda d: _jetzt(d, "temperature_celsius"),
    ),
    PfotenSensorBeschreibung(
        key="gefuehlte_temperatur",
        translation_key="gefuehlte_temperatur",
        koordinator="vorhersage",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        wert=lambda d: (_vorhersage(d).get("walk_light") or {}).get("apparent_temperature_celsius"),
    ),
    PfotenSensorBeschreibung(
        key="tiefstwert_heute",
        translation_key="tiefstwert_heute",
        koordinator="vorhersage",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        wert=lambda d: _vorhersage(d).get("today_min_temperature_celsius"),
    ),
    PfotenSensorBeschreibung(
        key="hoechstwert_heute",
        translation_key="hoechstwert_heute",
        koordinator="vorhersage",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        wert=lambda d: _vorhersage(d).get("today_max_temperature_celsius"),
    ),
    PfotenSensorBeschreibung(
        key="regen_beginnt_in",
        translation_key="regen_beginnt_in",
        koordinator="nowcast",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        wert=lambda d: _zusammenfassung(d).get("starts_in_minutes"),
    ),
    PfotenSensorBeschreibung(
        key="regen_endet_in",
        translation_key="regen_endet_in",
        koordinator="nowcast",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        wert=lambda d: _zusammenfassung(d).get("ends_in_minutes"),
    ),
    PfotenSensorBeschreibung(
        key="niederschlagsrate",
        translation_key="niederschlagsrate",
        koordinator="nowcast",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        wert=lambda d: _zusammenfassung(d).get("rate_mm_per_hour"),
        zusatz=lambda d: {
            "zustand": _zusammenfassung(d).get("state"),
            "staerke": _zusammenfassung(d).get("intensity"),
        },
    ),
    PfotenSensorBeschreibung(
        key="warnungen",
        translation_key="warnungen",
        koordinator="warnungen",
        state_class=SensorStateClass.MEASUREMENT,
        wert=lambda d: len(_alle_warnungen(d)),
        zusatz=_warn_zusatz,
    ),
    PfotenSensorBeschreibung(
        key="hoechste_warnstufe",
        translation_key="hoechste_warnstufe",
        koordinator="warnungen",
        wert=_hoechste_stufe,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PfotenwetterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    laufzeit = entry.runtime_data
    async_add_entities(
        PfotenSensor(getattr(laufzeit, beschreibung.koordinator), entry, beschreibung)
        for beschreibung in SENSOREN
    )


class PfotenSensor(PfotenwetterEntity, SensorEntity):
    entity_description: PfotenSensorBeschreibung

    #: Die Stundenliste und die Warntexte ändern sich mit jedem Abruf; in der
    #: Aufzeichnung blähten sie die Datenbank auf, ohne dass jemand sie dort sucht.
    _unrecorded_attributes = frozenset({"stunden", "warnungen", "hinweis", "gruende"})

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[dict[str, Any]],
        entry: PfotenwetterConfigEntry,
        description: PfotenSensorBeschreibung,
    ) -> None:
        super().__init__(coordinator, entry, description)

    @property
    def native_value(self) -> Any:
        return self.entity_description.wert(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.zusatz is None:
            return None
        return self.entity_description.zusatz(self.coordinator.data or {})

    @property
    def attribution(self) -> str | None:
        daten = self.coordinator.data or {}
        return quelle(daten.get("vorhersage", daten))
