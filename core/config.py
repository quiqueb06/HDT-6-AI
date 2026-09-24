"""Configuracion central del sistema multiagente de Parachute S.A.

Todo lo que puede cambiar (coordenadas, umbrales de seguridad, modelo LLM,
horarios disponibles) vive aqui para que las tres arquitecturas de
orquestacion compartan exactamente la misma configuracion.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Location:
    """Punto geografico de operaciones."""

    name: str
    latitude: float
    longitude: float
    timezone: str


@dataclass(frozen=True)
class SafetyThresholds:
    """Umbrales operativos definidos por Parachute S.A.

    Las unidades son las que devuelve Open-Meteo con el set de parametros
    que usa `core.weather`: km/h para viento, mm para precipitacion y
    porcentaje para cobertura de nubes.
    """

    # Velocidad del viento en superficie (wind_speed_10m) en km/h
    wind_speed_ideal_max: float = 20.0
    wind_speed_marginal_max: float = 28.0
    # Rafagas de viento (wind_gusts_10m) en km/h
    wind_gust_max: float = 35.0
    # Precipitacion (precipitation) en mm
    precipitation_max: float = 0.0
    # Cobertura de nubes / visibilidad (cloud_cover) en %
    cloud_cover_ideal_max: float = 30.0
    cloud_cover_marginal_max: float = 75.0


# --- Constantes del negocio ---------------------------------------------------

LANDING_ZONE = Location(
    name="Zona de aterrizaje Parachute S.A.",
    latitude=14.013722,
    longitude=-90.771611,
    timezone="America/Guatemala",
)

THRESHOLDS = SafetyThresholds()

#: Open-Meteo solo entrega pronostico hasta 16 dias hacia adelante.
MAX_FORECAST_DAYS = 16

#: Horarios en los que Parachute S.A. opera saltos.
AVAILABLE_SLOTS = ("08:00", "10:00", "13:00", "15:00")

#: Cupos maximos por horario (tandem + instructor).
SLOT_CAPACITY = 2

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

#: Archivo donde se persisten las citas agendadas.
APPOINTMENTS_FILE = os.getenv(
    "PARACHUTE_APPOINTMENTS_FILE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "citas.json"),
)

#: Modelo usado por los agentes. Se puede cambiar sin tocar el codigo.
DEFAULT_MODEL = os.getenv("PARACHUTE_MODEL", "gpt-4.1-mini")

#: "live" consulta Open-Meteo; "mock" genera datos deterministas offline.
WEATHER_MODE = os.getenv("PARACHUTE_WEATHER_MODE", "live")

#: Segundos de vida del cache en memoria de las respuestas de Open-Meteo.
WEATHER_CACHE_TTL = 300
