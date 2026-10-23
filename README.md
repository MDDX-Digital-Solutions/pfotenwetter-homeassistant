# PfotenWetter / PawWeather für Home Assistant

Gassi-Ampel, Pfotenindex, Regen in den nächsten Minuten und amtliche Warnungen
aus der App [PfotenWetter](https://pfotenwetter.app) als Sensoren in Home
Assistant.

*English below.*

## Einrichten

1. In HACS unter *Benutzerdefinierte Repositories* dieses Repository als
   *Integration* hinzufügen und „PfotenWetter / PawWeather“ installieren.
   Home Assistant neu starten.
2. In der App: **Einstellungen → Home Assistant → Code erzeugen**.
3. In Home Assistant: **Einstellungen → Geräte & Dienste → Integration
   hinzufügen → PfotenWetter / PawWeather**, den Code eingeben.

Der Code gilt zehn Minuten und nur einmal. Ein Konto braucht es nicht.

## Was es gibt

| Entität | Ohne Abo | Mit erweiterten Funktionen |
|---|---|---|
| Gassi-Ampel (grün/gelb/rot), Stunden als Attribut | für einen Durchschnittshund | für deine Hunde aus der App |
| Pfotenindex (Belagtemperatur) | ✓ | ✓ |
| Temperatur, gefühlte Temperatur, Tiefst-/Höchstwert heute | ✓ | ✓ |
| Regen jetzt, Regen beginnt/endet in, Niederschlagsrate | ✓ | ✓ |
| Amtliche Warnungen, höchste Warnstufe | ✓ | ✓ |

Abgefragt wird die Zone „Zuhause“; in den Optionen lässt sich eine andere Zone
wählen. Radar alle 5 Minuten, Vorhersage alle 30, Warnungen alle 10.

## Datenschutz

Die Koordinaten der gewählten Zone gehen bei jeder Abfrage an den
PfotenWetter-Server und werden dort nicht gespeichert. Für Warnungen geht nur
eine Zelle von rund 5 × 5 km. Die Integration hat ein eigenes Token, das du in
der App jederzeit trennen kannst. Mehr in der
[Datenschutzerklärung](https://pfotenwetter.app/datenschutz.html).

Orte in den USA (mit Alaska und Hawaii) fragt die Integration beim Server
`api.pawweather.app` ab, alle anderen bei `api.pfotenwetter.app`.

---

## English

Walk light, paw index, rain in the next minutes and official warnings from the
[PawWeather](https://pawweather.app) app as Home Assistant sensors.

1. Add this repository to HACS as a custom *Integration* repository and
   install “PfotenWetter / PawWeather”. Restart Home Assistant.
2. In the app: **Settings → Home Assistant → Create code**.
3. In Home Assistant: **Settings → Devices & services → Add integration →
   PfotenWetter / PawWeather**, enter the code.

Without a subscription the walk light is calculated for an average dog; with
extended features it uses your dogs from the app. Coordinates of the chosen
zone are sent with each request and are not stored.

## Entwicklung

```bash
uv sync --python 3.14
uv run pytest
```
