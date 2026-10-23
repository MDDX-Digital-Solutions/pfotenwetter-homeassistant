"""Welcher Wetterserver für einen Ort zuständig ist.

Dieselben fünf Rechtecke wie `Regionen.nordamerika` in
`ios/Sources/Core/Serverregion.swift` und `Serverregion.kt` – Ränder
eingeschlossen. Die Zuordnung geschieht hier und nicht am Server, damit
keine Koordinate an einen Server geht, bevor feststeht, welcher es sein soll
(Festlegung vom 10.09.2026, docs/51).
"""

from __future__ import annotations

from typing import Final, Literal

Region = Literal["eu", "us"]

#: (west, süd, ost, nord) in Grad.
NORDAMERIKA: Final[tuple[tuple[float, float, float, float], ...]] = (
    (-125.5, 23.0, -62.5, 51.0),  # CONUS
    (-170.0, 50.5, -129.0, 72.0),  # Alaska
    (-180.0, 50.5, -170.0, 54.0),  # Aleuten West
    (172.0, 50.5, 180.0, 54.0),  # Aleuten Ost
    (-161.5, 14.5, -153.5, 23.5),  # Hawaii
)


def wetterregion(breite: float, laenge: float) -> Region:
    """`us` für einen Ort in einem der fünf Rechtecke, sonst `eu`."""
    for west, sued, ost, nord in NORDAMERIKA:
        if west <= laenge <= ost and sued <= breite <= nord:
            return "us"
    return "eu"
