"""Geohash mit fünf Zeichen für die Warnungsabfrage.

Wie die Apps: Die Zelle (rund 4,9 × 4,9 km) rechnet das Gerät selbst; der
Server schlägt damit die Warngebiete nach und speichert nichts.
"""

from __future__ import annotations

from typing import Final

_ZEICHEN: Final = "0123456789bcdefghjkmnpqrstuvwxyz"


def kodiere(breite: float, laenge: float, laenge_zeichen: int = 5) -> str:
    """Der Geohash eines Punkts, Standard fünf Zeichen."""
    breiten = [-90.0, 90.0]
    laengen = [-180.0, 180.0]
    ergebnis: list[str] = []
    bit = 0
    wert = 0
    gerade = True
    while len(ergebnis) < laenge_zeichen:
        bereich, punkt = (laengen, laenge) if gerade else (breiten, breite)
        mitte = (bereich[0] + bereich[1]) / 2
        if punkt >= mitte:
            wert = (wert << 1) | 1
            bereich[0] = mitte
        else:
            wert <<= 1
            bereich[1] = mitte
        gerade = not gerade
        bit += 1
        if bit == 5:
            ergebnis.append(_ZEICHEN[wert])
            bit = 0
            wert = 0
    return "".join(ergebnis)
