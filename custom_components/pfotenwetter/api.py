"""Der Weg zum PfotenWetter-Server.

Kein Client-Geheimnis: Die Integration bekommt ihr Token, indem sie einen
Code aus der App einlöst (`koppele`), und erneuert es mit dem
Erneuerungsschlüssel, den sie dabei einmal erhält (`_token`). docs/89,
Abschnitt 3.

Für einen Ort in Nordamerika fragt sie den US-Server mit einem
Regionstoken, das sie beim EU-Server holt – genau wie die App.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp

from .const import ERNEUERN_VOR, KONTO_SERVER, VERSION, WETTER_SERVER
from .region import Region

ZEITLIMIT = aiohttp.ClientTimeout(total=20)


class PfotenwetterFehler(Exception):
    """Der Server war nicht erreichbar oder antwortete unerwartet."""


class PfotenwetterAuthFehler(PfotenwetterFehler):
    """Code, Token oder Erneuerungsschlüssel gelten nicht (mehr)."""


class PfotenwetterCodeFehler(PfotenwetterFehler):
    """Der Code ist unbekannt, abgelaufen oder schon eingelöst."""


class PfotenwetterAboFehler(PfotenwetterFehler):
    """Dafür braucht es die erweiterten Funktionen (402)."""


class PfotenwetterGebremst(PfotenwetterFehler):
    """Zu viele Anfragen (429). `retry_after` in Sekunden, wenn der Server es sagt."""

    def __init__(self, retry_after: int | None = None) -> None:
        super().__init__("Zu viele Anfragen")
        self.retry_after = retry_after


@dataclass(frozen=True)
class Zugang:
    """Was das Einlösen eines Codes ergibt."""

    access_token: str
    expires_at: datetime
    refresh_secret: str
    pairing_id: str


def _zeitpunkt(wert: str) -> datetime:
    zeit = datetime.fromisoformat(wert.replace("Z", "+00:00"))
    return zeit if zeit.tzinfo else zeit.replace(tzinfo=UTC)


def _kopf(sprache: str, token: str | None = None) -> dict[str, str]:
    kopf = {
        "User-Agent": f"PfotenWetter-HomeAssistant/{VERSION}",
        "Accept-Language": sprache,
        # Kein Mensch schaut gerade hin: HA zählt nicht als „benutzt“
        # (`Device.zuletzt_benutzt_am`, 19.09.2026).
        "X-Pfotenwetter-Aufruf": "hintergrund",
    }
    if token is not None:
        kopf["Authorization"] = f"Bearer {token}"
    return kopf


async def _antwort(antwort: aiohttp.ClientResponse) -> Any:
    if antwort.status == 401:
        raise PfotenwetterAuthFehler
    if antwort.status == 402:
        raise PfotenwetterAboFehler
    if antwort.status == 429:
        wert = antwort.headers.get("Retry-After")
        raise PfotenwetterGebremst(int(wert) if wert and wert.isdigit() else None)
    if antwort.status == 204:
        return None
    if antwort.status >= 400:
        raise PfotenwetterFehler(f"HTTP {antwort.status}")
    return await antwort.json()


async def koppele(session: aiohttp.ClientSession, code: str, sprache: str) -> Zugang:
    """Löst einen Code aus der App ein. Ohne Token und ohne Geheimnis."""
    try:
        async with session.post(
            f"{KONTO_SERVER}/v1/homeassistant/koppeln",
            json={"code": code, "version": VERSION},
            headers=_kopf(sprache),
            timeout=ZEITLIMIT,
        ) as antwort:
            if antwort.status in (404, 422):
                raise PfotenwetterCodeFehler
            daten = await _antwort(antwort)
    except (aiohttp.ClientError, TimeoutError) as fehler:
        raise PfotenwetterFehler(str(fehler)) from fehler
    return Zugang(
        access_token=daten["access_token"],
        expires_at=_zeitpunkt(daten["expires_at"]),
        refresh_secret=daten["refresh_secret"],
        pairing_id=daten["pairing_id"],
    )


class PfotenwetterApi:
    """Ein Zugang für einen Konfigurationseintrag."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        access_token: str,
        expires_at: datetime,
        refresh_secret: str,
        sprache: str,
        beim_neuen_token: Callable[[str, datetime], Awaitable[None] | None] | None = None,
    ) -> None:
        self._session = session
        self._token_wert = access_token
        self._token_bis = expires_at
        self._schluessel = refresh_secret
        self.sprache = sprache
        self._beim_neuen_token = beim_neuen_token
        self._sperre = asyncio.Lock()
        self._regionstoken: tuple[str, datetime] | None = None

    # --- Token ---------------------------------------------------------

    async def _token(self, *, erzwingen: bool = False) -> str:
        """Das Gerätetoken, erneuert, sobald es weniger als zwei Tage gilt."""
        async with self._sperre:
            if not erzwingen and self._token_bis - datetime.now(UTC) > ERNEUERN_VOR:
                return self._token_wert
            daten = await self._anfrage(
                "post",
                f"{KONTO_SERVER}/v1/homeassistant/token",
                json={"refresh_secret": self._schluessel, "version": VERSION},
                token=None,
            )
            self._token_wert = daten["access_token"]
            self._token_bis = _zeitpunkt(daten["expires_at"])
            if self._beim_neuen_token is not None:
                ergebnis = self._beim_neuen_token(self._token_wert, self._token_bis)
                if ergebnis is not None:
                    await ergebnis
            return self._token_wert

    async def _wettertoken(self, region: Region) -> str:
        """Für die EU das Gerätetoken, für die USA ein Regionstoken (15 Minuten)."""
        if region == "eu":
            return await self._token()
        if self._regionstoken is not None and self._regionstoken[1] - datetime.now(UTC) > timedelta(
            minutes=1
        ):
            return self._regionstoken[0]
        daten = await self._mit_token(
            "post", f"{KONTO_SERVER}/v1/auth/regionstoken", json={"ziel": region}
        )
        self._regionstoken = (daten["access_token"], _zeitpunkt(daten["expires_at"]))
        return self._regionstoken[0]

    # --- Anfragen ------------------------------------------------------

    async def _anfrage(
        self,
        methode: str,
        adresse: str,
        *,
        token: str | None,
        json: Any = None,
        params: Any = None,
    ) -> Any:
        try:
            async with self._session.request(
                methode,
                adresse,
                json=json,
                params=params,
                headers=_kopf(self.sprache, token),
                timeout=ZEITLIMIT,
            ) as antwort:
                return await _antwort(antwort)
        except (aiohttp.ClientError, TimeoutError) as fehler:
            raise PfotenwetterFehler(str(fehler)) from fehler

    async def _mit_token(self, methode: str, adresse: str, **argumente: Any) -> Any:
        """Mit dem Gerätetoken; ein 401 bekommt genau einen zweiten Versuch mit
        frisch erneuertem Token, bevor er nach außen geht."""
        try:
            return await self._anfrage(methode, adresse, token=await self._token(), **argumente)
        except PfotenwetterAuthFehler:
            neu = await self._token(erzwingen=True)
            return await self._anfrage(methode, adresse, token=neu, **argumente)

    async def _wetter(self, region: Region, methode: str, pfad: str, **argumente: Any) -> Any:
        adresse = f"{WETTER_SERVER[region]}{pfad}"
        if region == "eu":
            return await self._mit_token(methode, adresse, **argumente)
        try:
            return await self._anfrage(
                methode, adresse, token=await self._wettertoken(region), **argumente
            )
        except PfotenwetterAuthFehler:
            self._regionstoken = None
            return await self._anfrage(
                methode, adresse, token=await self._wettertoken(region), **argumente
            )

    # --- Konto ---------------------------------------------------------

    async def stand(self) -> dict[str, Any]:
        """`premium`, `valid_until`, `paired`."""
        return dict(await self._mit_token("get", f"{KONTO_SERVER}/v1/homeassistant"))

    async def hunde(self) -> list[str]:
        """Die Hunde des Telefons als `rasse:hitze:kaelte`. 402 ohne Abo."""
        daten = await self._mit_token("get", f"{KONTO_SERVER}/v1/homeassistant/hunde")
        return [str(hund) for hund in daten["dogs"]]

    async def melde_ab(self) -> None:
        """„Integration entfernen“: Der Server sperrt diese Kopplung."""
        await self._mit_token("delete", f"{KONTO_SERVER}/v1/homeassistant")

    # --- Wetter --------------------------------------------------------

    async def vorhersage(
        self, region: Region, breite: float, laenge: float, hunde: list[str]
    ) -> dict[str, Any]:
        rumpf: dict[str, Any] = {"lat": breite, "lon": laenge}
        if hunde:
            rumpf["dog"] = hunde
        return dict(await self._wetter(region, "post", "/v1/forecast", json=rumpf))

    async def nowcast(self, region: Region, breite: float, laenge: float) -> dict[str, Any]:
        return dict(
            await self._wetter(region, "post", "/v1/nowcast", json={"lat": breite, "lon": laenge})
        )

    async def warnungen(
        self, region: Region, zelle: str, breite: float, laenge: float
    ) -> dict[str, Any]:
        return dict(
            await self._wetter(
                region,
                "get",
                "/v1/warnungen",
                params={"cell": zelle, "lat": breite, "lon": laenge},
            )
        )
