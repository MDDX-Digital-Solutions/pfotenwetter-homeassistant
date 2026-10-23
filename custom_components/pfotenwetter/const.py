"""Konstanten der Integration PfotenWetter / PawWeather."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "pfotenwetter"

#: Fassung der Integration. Muss mit `manifest.json` übereinstimmen
#: (geprüft in `tests/test_manifest.py`); der Server legt sie an der
#: Kopplung ab, damit sich ein Fehler einer Fassung zuordnen lässt.
VERSION: Final = "0.1.0"

#: Das Konto liegt immer auf dem EU-Server (docs/89, Abschnitt 2), auch für
#: Orte in Nordamerika. Nur das Wetter folgt dem Ort.
KONTO_SERVER: Final = "https://api.pfotenwetter.app"
WETTER_SERVER: Final = {
    "eu": "https://api.pfotenwetter.app",
    "us": "https://api.pawweather.app",
}

CONF_REFRESH_SECRET: Final = "refresh_secret"
CONF_ACCESS_TOKEN: Final = "access_token"
CONF_EXPIRES_AT: Final = "expires_at"
CONF_CODE: Final = "code"
CONF_ZONE: Final = "zone"

STANDARD_ZONE: Final = "zone.home"

#: Abfragetakt (docs/89, Abschnitt 6). Fest und kein Feld im Flow
#: (Regel *appropriate-polling*): Radar alle fünf Minuten, die Ampel ändert
#: sich stündlich, der Warnstand alle paar Minuten.
TAKT_NOWCAST: Final = timedelta(minutes=5)
TAKT_VORHERSAGE: Final = timedelta(minutes=30)
TAKT_WARNUNGEN: Final = timedelta(minutes=10)

#: Ein Token wird erneuert, sobald es weniger als so lange gilt.
ERNEUERN_VOR: Final = timedelta(days=2)

AMPELSTUFEN: Final = ["gruen", "gelb", "rot"]
PFOTENSTUFEN: Final = ["gruen", "gelb", "rot", "tiefrot"]
