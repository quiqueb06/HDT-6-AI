"""Integracion con la API gratuita de Open-Meteo.

Expone una sola funcion util para el resto del sistema:
`get_forecast(fecha)` -> `WeatherSnapshot`, con las cinco variables que pide
Parachute S.A.

Detalles de la integracion:
  * Coordenadas fijas de la zona de aterrizaje (core.config.LANDING_ZONE).
  * Si la fecha es hoy se usa el bloque `current`; si es futura se usa
    `daily` (Open-Meteo solo pronostica 16 dias).
  * Hay un cache en memoria para no repetir llamadas dentro de la misma
    conversacion (los agentes tienden a consultar la misma fecha varias veces).
  * `PARACHUTE_WEATHER_MODE=mock` genera datos deterministas para poder
    demostrar el sistema sin salida a internet.
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

try:  # zoneinfo esta en la stdlib desde 3.9
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from . import config


class WeatherError(RuntimeError):
    """Error recuperable al consultar el clima (se reporta al usuario)."""


class DateOutOfRangeError(ValueError):
    """La fecha pedida esta fuera de la ventana de pronostico de Open-Meteo."""


@dataclass
class WeatherSnapshot:
    """Las cinco variables meteorologicas normalizadas para una fecha."""

    fecha: str
    fuente: str  # "current" | "daily" | "mock"
    temperature_2m: Optional[float]
    precipitation: Optional[float]
    cloud_cover: Optional[float]
    wind_speed_10m: Optional[float]
    wind_gusts_10m: Optional[float]
    unidades: Dict[str, str]
    latitud: float = config.LANDING_ZONE.latitude
    longitud: float = config.LANDING_ZONE.longitude

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# --- Utilidades de fecha ------------------------------------------------------

def today_local() -> date:
    """Fecha de hoy en la zona horaria del aeroclub."""

    if ZoneInfo is not None:
        return datetime.now(ZoneInfo(config.LANDING_ZONE.timezone)).date()
    return date.today()  # pragma: no cover


def parse_date(value: str) -> date:
    """Convierte 'YYYY-MM-DD' a date validando el formato."""

    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError) as exc:
        raise ValueError(
            f"Formato de fecha invalido: '{value}'. Usa el formato YYYY-MM-DD."
        ) from exc


def validate_forecast_date(value: str) -> date:
    """Valida que la fecha este dentro de los 16 dias de Open-Meteo."""

    fecha = parse_date(value)
    hoy = today_local()
    limite = hoy + timedelta(days=config.MAX_FORECAST_DAYS)
    if fecha < hoy:
        raise DateOutOfRangeError(
            f"La fecha {fecha.isoformat()} ya paso. Hoy es {hoy.isoformat()}."
        )
    if fecha > limite:
        dias = (fecha - hoy).days
        raise DateOutOfRangeError(
            f"Open-Meteo solo entrega pronostico para los proximos "
            f"{config.MAX_FORECAST_DAYS} dias (hasta {limite.isoformat()}). "
            f"La fecha {fecha.isoformat()} esta a {dias} dias, asi que todavia "
            f"no se puede verificar el clima ni confirmar una cita para ese dia."
        )
    return fecha


# --- Cache simple en memoria --------------------------------------------------

_CACHE: Dict[str, Any] = {}


def _cache_get(key: str) -> Optional[WeatherSnapshot]:
    hit = _CACHE.get(key)
    if hit and (time.time() - hit[0]) < config.WEATHER_CACHE_TTL:
        return hit[1]
    return None


def _cache_put(key: str, value: WeatherSnapshot) -> None:
    _CACHE[key] = (time.time(), value)


def clear_cache() -> None:
    _CACHE.clear()


# --- Llamada HTTP -------------------------------------------------------------

def _http_get_json(params: Dict[str, str], timeout: int = 20) -> Dict[str, Any]:
    url = f"{config.OPEN_METEO_URL}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - depende de la red
        raise WeatherError(f"Open-Meteo respondio {exc.code}: {exc.reason}") from exc
    except Exception as exc:  # pragma: no cover - depende de la red
        raise WeatherError(f"No se pudo contactar Open-Meteo: {exc}") from exc


def _fetch_current() -> WeatherSnapshot:
    """Bloque `current` de Open-Meteo (para el dia de hoy)."""

    params = {
        "latitude": str(config.LANDING_ZONE.latitude),
        "longitude": str(config.LANDING_ZONE.longitude),
        "current": "temperature_2m,precipitation,cloud_cover,wind_speed_10m,wind_gusts_10m",
        "timezone": config.LANDING_ZONE.timezone,
        "wind_speed_unit": "kmh",
    }
    data = _http_get_json(params)
    cur = data.get("current", {})
    units = data.get("current_units", {})
    return WeatherSnapshot(
        fecha=str(cur.get("time", ""))[:10] or today_local().isoformat(),
        fuente="current",
        temperature_2m=cur.get("temperature_2m"),
        precipitation=cur.get("precipitation"),
        cloud_cover=cur.get("cloud_cover"),
        wind_speed_10m=cur.get("wind_speed_10m"),
        wind_gusts_10m=cur.get("wind_gusts_10m"),
        unidades={
            "temperature_2m": units.get("temperature_2m", "C"),
            "precipitation": units.get("precipitation", "mm"),
            "cloud_cover": units.get("cloud_cover", "%"),
            "wind_speed_10m": units.get("wind_speed_10m", "km/h"),
            "wind_gusts_10m": units.get("wind_gusts_10m", "km/h"),
        },
    )


def _fetch_daily(fecha: date) -> WeatherSnapshot:
    """Bloque `daily` de Open-Meteo (para fechas futuras).

    Se piden los agregados diarios equivalentes a las variables horarias:
    maximos de viento y rafagas (el caso mas exigente del dia), suma de
    precipitacion y promedios de temperatura y nubosidad.
    """

    params = {
        "latitude": str(config.LANDING_ZONE.latitude),
        "longitude": str(config.LANDING_ZONE.longitude),
        "daily": (
            "temperature_2m_max,temperature_2m_min,precipitation_sum,"
            "cloud_cover_mean,wind_speed_10m_max,wind_gusts_10m_max"
        ),
        "timezone": config.LANDING_ZONE.timezone,
        "wind_speed_unit": "kmh",
        "start_date": fecha.isoformat(),
        "end_date": fecha.isoformat(),
    }
    data = _http_get_json(params)
    daily = data.get("daily", {})
    if not daily.get("time"):
        raise WeatherError(f"Open-Meteo no devolvio pronostico para {fecha.isoformat()}.")

    def first(name: str) -> Optional[float]:
        valores = daily.get(name) or []
        return valores[0] if valores else None

    tmax, tmin = first("temperature_2m_max"), first("temperature_2m_min")
    temperatura = None
    if tmax is not None and tmin is not None:
        temperatura = round((tmax + tmin) / 2, 1)
    elif tmax is not None:
        temperatura = tmax

    return WeatherSnapshot(
        fecha=fecha.isoformat(),
        fuente="daily",
        temperature_2m=temperatura,
        precipitation=first("precipitation_sum"),
        cloud_cover=first("cloud_cover_mean"),
        wind_speed_10m=first("wind_speed_10m_max"),
        wind_gusts_10m=first("wind_gusts_10m_max"),
        unidades={
            "temperature_2m": "C (promedio del dia)",
            "precipitation": "mm (acumulado del dia)",
            "cloud_cover": "% (promedio del dia)",
            "wind_speed_10m": "km/h (maximo del dia)",
            "wind_gusts_10m": "km/h (maximo del dia)",
        },
    )


def _fetch_mock(fecha: date) -> WeatherSnapshot:
    """Datos deterministas para demos sin internet (PARACHUTE_WEATHER_MODE=mock).

    Rota entre cuatro perfiles para que la demo muestre los tres veredictos
    posibles (ideal, marginal y no seguro) sin depender de la red.
    """

    perfiles = [
        # (viento, rafagas, lluvia, nubes) -> IDEAL
        (11.0, 19.0, 0.0, 18.0),
        # -> MARGINAL (viento y nubes en rango intermedio)
        (23.0, 31.0, 0.0, 55.0),
        # -> NO_SEGURO (lluvia)
        (14.0, 22.0, 2.4, 88.0),
        # -> NO_SEGURO (viento y rafagas)
        (31.0, 44.0, 0.0, 40.0),
    ]
    viento, rafagas, lluvia, nubes = perfiles[fecha.toordinal() % len(perfiles)]
    rng = random.Random(fecha.toordinal())
    return WeatherSnapshot(
        fecha=fecha.isoformat(),
        fuente="mock",
        temperature_2m=round(rng.uniform(21, 31), 1),
        precipitation=lluvia,
        cloud_cover=nubes,
        wind_speed_10m=viento,
        wind_gusts_10m=rafagas,
        unidades={
            "temperature_2m": "C",
            "precipitation": "mm",
            "cloud_cover": "%",
            "wind_speed_10m": "km/h",
            "wind_gusts_10m": "km/h",
        },
    )


def get_forecast(fecha_iso: str, mode: Optional[str] = None) -> WeatherSnapshot:
    """Devuelve el pronostico normalizado para una fecha YYYY-MM-DD.

    Lanza `DateOutOfRangeError` si la fecha esta fuera de los 16 dias y
    `WeatherError` si Open-Meteo no responde.
    """

    fecha = validate_forecast_date(fecha_iso)
    mode = (mode or config.WEATHER_MODE).lower()

    cache_key = f"{mode}:{fecha.isoformat()}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    if mode == "mock":
        snapshot = _fetch_mock(fecha)
    elif fecha == today_local():
        snapshot = _fetch_current()
    else:
        snapshot = _fetch_daily(fecha)

    _cache_put(cache_key, snapshot)
    return snapshot
