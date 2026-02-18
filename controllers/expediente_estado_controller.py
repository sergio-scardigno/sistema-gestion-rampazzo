"""Controlador de historial de estados de expedientes.

Registra cada segmento de permanencia en un estado/responsable para
calcular tiempos y generar estadisticas.  Cada fila representa un
periodo continuo en el que un expediente estuvo en determinado estado
con determinado responsable.
"""
import logging
from datetime import datetime, timezone

from core import db_local
from models.base_model import new_id, now_iso, base_fields

logger = logging.getLogger(__name__)

TABLE = "expediente_estado_historial"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def abrir_segmento(id_expediente: str, estado: str,
                   responsable_username: str = "",
                   usuario: str = "sistema",
                   origen: str = "manual") -> dict:
    """Inserta un nuevo segmento abierto (fin_ts=NULL)."""
    record = base_fields()
    record.update({
        "id_expediente": id_expediente,
        "estado": estado,
        "responsable_username": responsable_username or "",
        "usuario": usuario,
        "inicio_ts": _now(),
        "fin_ts": None,
        "origen": origen,
    })
    db_local.insert(TABLE, record)
    return record


def cerrar_segmento_abierto(id_expediente: str) -> dict | None:
    """Cierra el segmento abierto actual (fin_ts IS NULL) de un expediente.

    Retorna el segmento cerrado, o None si no habia segmento abierto.
    """
    conn = db_local.get_connection()
    row = conn.execute(
        f"SELECT * FROM {TABLE} "
        "WHERE id_expediente = ? AND fin_ts IS NULL "
        "ORDER BY inicio_ts DESC LIMIT 1",
        (id_expediente,)
    ).fetchone()
    conn.close()

    if not row:
        return None

    seg = dict(row)
    ahora = _now()
    db_local.update(TABLE, seg["_id"], {
        "fin_ts": ahora,
        "updated_at": now_iso(),
        "version": seg.get("version", 1) + 1,
        "sync_status": "pending",
    })
    seg["fin_ts"] = ahora
    return seg


def rotar_segmento(id_expediente: str, nuevo_estado: str,
                   nuevo_responsable: str = "",
                   usuario: str = "sistema",
                   origen: str = "manual") -> dict:
    """Cierra el segmento anterior y abre uno nuevo.

    Solo rota si realmente cambio el estado o el responsable.
    Retorna el segmento nuevo creado.
    """
    cerrar_segmento_abierto(id_expediente)
    return abrir_segmento(
        id_expediente, nuevo_estado,
        responsable_username=nuevo_responsable,
        usuario=usuario,
        origen=origen,
    )


def get_segmento_abierto(id_expediente: str) -> dict | None:
    """Retorna el segmento abierto actual de un expediente, si existe."""
    conn = db_local.get_connection()
    row = conn.execute(
        f"SELECT * FROM {TABLE} "
        "WHERE id_expediente = ? AND fin_ts IS NULL "
        "ORDER BY inicio_ts DESC LIMIT 1",
        (id_expediente,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_historial(id_expediente: str) -> list[dict]:
    """Retorna todos los segmentos de un expediente ordenados cronologicamente."""
    return db_local.find_all(
        TABLE,
        where="id_expediente = ?",
        params=(id_expediente,),
        order_by="inicio_ts ASC",
    )


def seed_expedientes_sin_segmento():
    """Crea un segmento inicial para expedientes activos que no tengan uno.

    Debe ejecutarse una vez al arrancar la app (post-login o init).
    Solo afecta expedientes que NO estan en Cerrado/Archivado y que
    no tienen ningun segmento registrado aun.
    """
    conn = db_local.get_connection()
    rows = conn.execute("""
        SELECT e._id, e.estado, e.responsable_username
        FROM expedientes e
        WHERE e.estado NOT IN ('Cerrado', 'Archivado')
        AND NOT EXISTS (
            SELECT 1 FROM expediente_estado_historial h
            WHERE h.id_expediente = e._id
        )
    """).fetchall()
    conn.close()

    count = 0
    for r in rows:
        abrir_segmento(
            id_expediente=r[0],
            estado=r[1] or "Activo",
            responsable_username=r[2] or "",
            usuario="sistema",
            origen="seed",
        )
        count += 1

    if count:
        logger.info("Seed de historial: %d expedientes inicializados", count)
    return count
