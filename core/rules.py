"""Motor de reglas de seguridad para determinar si un dia es apto para saltar.

Este modulo es puro: recibe valores numericos y devuelve un veredicto. No
sabe nada de agentes, de LLMs ni de HTTP, por lo que las tres arquitecturas
lo reutilizan tal cual y se puede probar con unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

from .config import SafetyThresholds, THRESHOLDS


class Status(str, Enum):
    """Estado de un criterio individual o del veredicto global."""

    IDEAL = "IDEAL"
    MARGINAL = "MARGINAL"
    NO_SEGURO = "NO_SEGURO"
    SIN_DATO = "SIN_DATO"


#: Orden de severidad: el veredicto global es el peor de los criterios.
_SEVERITY = {
    Status.IDEAL: 0,
    Status.MARGINAL: 1,
    Status.SIN_DATO: 2,
    Status.NO_SEGURO: 3,
}


@dataclass
class Criterion:
    """Resultado de evaluar una variable meteorologica contra su umbral."""

    variable: str
    etiqueta: str
    valor: Optional[float]
    unidad: str
    estado: Status
    regla: str
    comentario: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["estado"] = self.estado.value
        return data


@dataclass
class SafetyVerdict:
    """Veredicto consolidado para una fecha."""

    estado: Status
    apto_para_saltar: bool
    requiere_tandem_experimentado: bool
    criterios: List[Criterion] = field(default_factory=list)
    motivos_bloqueo: List[str] = field(default_factory=list)
    resumen: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "estado": self.estado.value,
            "apto_para_saltar": self.apto_para_saltar,
            "requiere_tandem_experimentado": self.requiere_tandem_experimentado,
            "criterios": [c.to_dict() for c in self.criterios],
            "motivos_bloqueo": self.motivos_bloqueo,
            "resumen": self.resumen,
        }


def _sin_dato(variable: str, etiqueta: str, unidad: str, regla: str) -> Criterion:
    return Criterion(
        variable=variable,
        etiqueta=etiqueta,
        valor=None,
        unidad=unidad,
        estado=Status.SIN_DATO,
        regla=regla,
        comentario="Open-Meteo no devolvio este valor; por seguridad no se aprueba el salto.",
    )


def _evaluar_viento(valor: Optional[float], t: SafetyThresholds) -> Criterion:
    regla = (
        f"Ideal < {t.wind_speed_ideal_max:g} km/h | "
        f"Marginal {t.wind_speed_ideal_max:g}-{t.wind_speed_marginal_max:g} km/h | "
        f"Prohibido > {t.wind_speed_marginal_max:g} km/h"
    )
    if valor is None:
        return _sin_dato("wind_speed_10m", "Velocidad del viento en superficie", "km/h", regla)
    if valor > t.wind_speed_marginal_max:
        estado, comentario = Status.NO_SEGURO, "Viento superior al limite: muy dificil de controlar el salto."
    elif valor >= t.wind_speed_ideal_max:
        estado, comentario = Status.MARGINAL, "Viento marginal: solo tandem con instructor experimentado."
    else:
        estado, comentario = Status.IDEAL, "Viento dentro del rango ideal."
    return Criterion("wind_speed_10m", "Velocidad del viento en superficie", valor, "km/h", estado, regla, comentario)


def _evaluar_rafagas(valor: Optional[float], t: SafetyThresholds) -> Criterion:
    regla = f"Prohibido > {t.wind_gust_max:g} km/h"
    if valor is None:
        return _sin_dato("wind_gusts_10m", "Rafagas de viento", "km/h", regla)
    if valor > t.wind_gust_max:
        estado, comentario = Status.NO_SEGURO, "Rafagas por encima del limite operativo."
    else:
        estado, comentario = Status.IDEAL, "Rafagas dentro del limite operativo."
    return Criterion("wind_gusts_10m", "Rafagas de viento", valor, "km/h", estado, regla, comentario)


def _evaluar_precipitacion(valor: Optional[float], t: SafetyThresholds) -> Criterion:
    regla = f"Prohibido > {t.precipitation_max:g} mm"
    if valor is None:
        return _sin_dato("precipitation", "Precipitacion", "mm", regla)
    if valor > t.precipitation_max:
        estado, comentario = Status.NO_SEGURO, "Hay lluvia pronosticada: dana el equipo y lastima la piel."
    else:
        estado, comentario = Status.IDEAL, "Sin precipitacion pronosticada."
    return Criterion("precipitation", "Precipitacion", valor, "mm", estado, regla, comentario)


def _evaluar_nubes(valor: Optional[float], t: SafetyThresholds) -> Criterion:
    regla = (
        f"Ideal < {t.cloud_cover_ideal_max:g}% | "
        f"Marginal {t.cloud_cover_ideal_max:g}-{t.cloud_cover_marginal_max:g}% | "
        f"Prohibido > {t.cloud_cover_marginal_max:g}%"
    )
    if valor is None:
        return _sin_dato("cloud_cover", "Cobertura de nubes / visibilidad", "%", regla)
    if valor > t.cloud_cover_marginal_max:
        estado, comentario = Status.NO_SEGURO, "Techo de nubes bajo: impide las reglas de vuelo visual."
    elif valor >= t.cloud_cover_ideal_max:
        estado, comentario = Status.MARGINAL, "Nubes dispersas: visibilidad aceptable pero no ideal."
    else:
        estado, comentario = Status.IDEAL, "Cielo despejado, visibilidad clara."
    return Criterion("cloud_cover", "Cobertura de nubes / visibilidad", valor, "%", estado, regla, comentario)


def _evaluar_temperatura(valor: Optional[float]) -> Criterion:
    regla = "Informativo (no bloquea el salto)"
    if valor is None:
        c = _sin_dato("temperature_2m", "Temperatura", "C", regla)
        c.estado = Status.IDEAL  # la temperatura no es criterio de bloqueo
        c.comentario = "Sin dato de temperatura; no afecta la decision."
        return c
    if valor <= 12:
        comentario = "Hace frio: recomendar ropa termica bajo el equipo."
    elif valor >= 32:
        comentario = "Calor alto: recomendar hidratacion antes del salto."
    else:
        comentario = "Temperatura comoda para saltar."
    return Criterion("temperature_2m", "Temperatura", valor, "C", Status.IDEAL, regla, comentario)


def evaluate_conditions(
    wind_speed_10m: Optional[float],
    wind_gusts_10m: Optional[float],
    precipitation: Optional[float],
    cloud_cover: Optional[float],
    temperature_2m: Optional[float] = None,
    thresholds: SafetyThresholds = THRESHOLDS,
) -> SafetyVerdict:
    """Aplica los criterios de Parachute S.A. y devuelve el veredicto."""

    criterios = [
        _evaluar_viento(wind_speed_10m, thresholds),
        _evaluar_rafagas(wind_gusts_10m, thresholds),
        _evaluar_precipitacion(precipitation, thresholds),
        _evaluar_nubes(cloud_cover, thresholds),
        _evaluar_temperatura(temperature_2m),
    ]

    peor = max(criterios, key=lambda c: _SEVERITY[c.estado]).estado
    bloqueos = [
        f"{c.etiqueta}: {c.valor if c.valor is not None else 's/d'} {c.unidad} ({c.comentario})"
        for c in criterios
        if c.estado in (Status.NO_SEGURO, Status.SIN_DATO)
    ]

    apto = peor in (Status.IDEAL, Status.MARGINAL)
    if peor is Status.IDEAL:
        resumen = "Condiciones ideales para saltar."
    elif peor is Status.MARGINAL:
        resumen = "Condiciones marginales: el salto solo procede en tandem con instructor experimentado."
    elif peor is Status.SIN_DATO:
        resumen = "Faltan datos meteorologicos; por politica de seguridad no se autoriza el salto."
    else:
        resumen = "Condiciones NO SEGURAS: el salto queda prohibido para esta fecha."

    return SafetyVerdict(
        estado=peor,
        apto_para_saltar=apto,
        requiere_tandem_experimentado=peor is Status.MARGINAL,
        criterios=criterios,
        motivos_bloqueo=bloqueos,
        resumen=resumen,
    )
