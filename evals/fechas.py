"""Genera las fechas de los casos de prueba de agenda.

El clima simulado (`core.weather._fetch_mock`) asigna el perfil segun
`fecha.toordinal() % 4`: 0 es IDEAL y 2 es NO_SEGURO por lluvia. Aqui se
busca la primera fecha de cada tipo dentro de la ventana de 16 dias, para que
los casos no dependan del dia en que se corren los evals.
"""

from datetime import datetime, timedelta, timezone

# Guatemala esta en UTC-6 todo el anio (no usa horario de verano).
HOY = datetime.now(timezone(timedelta(hours=-6))).date()


def _primera_fecha(residuo):
    for dias in range(1, 17):
        fecha = HOY + timedelta(days=dias)
        if fecha.toordinal() % 4 == residuo:
            return fecha.isoformat()


FECHAS = {
    "fecha_ideal": _primera_fecha(0),
    "fecha_lluvia": _primera_fecha(2),
    "fecha_fuera": (HOY + timedelta(days=30)).isoformat(),
}


def get_var(var_name, prompt, other_vars):
    return {"output": FECHAS[var_name]}
