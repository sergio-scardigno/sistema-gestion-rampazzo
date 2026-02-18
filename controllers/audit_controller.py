"""Controlador de Auditoria – consultas al audit_log para trazabilidad y estadisticas."""
import json
from datetime import datetime, timedelta, timezone

from core import db_local


# Nombres amigables para las colecciones
COLECCION_LABELS = {
    "consultas": "Consultas",
    "clientes": "Clientes",
    "expedientes": "Expedientes",
    "tareas": "Tareas",
    "turnos": "Turnos ANSES",
    "comunicaciones": "Comunicaciones",
    "movimientos": "Movimientos",
    "documentos": "Documentos",
}

ACCION_LABELS = {
    "create": "Crear",
    "update": "Editar",
    "delete": "Eliminar",
}


class AuditController:
    """Consultas de solo lectura sobre la tabla audit_log."""

    @staticmethod
    def get_all(usuario: str = "", coleccion: str = "", accion: str = "",
                fecha_desde: str = "", fecha_hasta: str = "",
                limit: int = 500) -> list[dict]:
        """Log completo con filtros opcionales."""
        conditions = []
        params = []

        if usuario:
            conditions.append("usuario = ?")
            params.append(usuario)
        if coleccion:
            conditions.append("coleccion = ?")
            params.append(coleccion)
        if accion:
            conditions.append("accion = ?")
            params.append(accion)
        if fecha_desde:
            conditions.append("timestamp >= ?")
            params.append(fecha_desde)
        if fecha_hasta:
            # Agregar un dia para incluir todo el dia seleccionado
            conditions.append("timestamp <= ?")
            params.append(fecha_hasta + "T23:59:59")

        where = " AND ".join(conditions) if conditions else ""
        rows = db_local.find_all(
            "audit_log",
            where=where,
            params=tuple(params),
            order_by="timestamp DESC",
            limit=limit,
        )

        # Enriquecer cada registro con resumen legible
        for row in rows:
            row["accion_label"] = ACCION_LABELS.get(row.get("accion", ""), row.get("accion", ""))
            row["coleccion_label"] = COLECCION_LABELS.get(row.get("coleccion", ""), row.get("coleccion", ""))
            row["resumen"] = AuditController._generar_resumen(row)

        return rows

    @staticmethod
    def get_by_document(coleccion: str, documento_id: str) -> list[dict]:
        """Historial de un registro especifico."""
        rows = db_local.find_all(
            "audit_log",
            where="coleccion = ? AND documento_id = ?",
            params=(coleccion, documento_id),
            order_by="timestamp DESC",
        )
        for row in rows:
            row["accion_label"] = ACCION_LABELS.get(row.get("accion", ""), row.get("accion", ""))
            row["coleccion_label"] = COLECCION_LABELS.get(row.get("coleccion", ""), row.get("coleccion", ""))
            row["resumen"] = AuditController._generar_resumen(row)
        return rows

    @staticmethod
    def get_stats_por_usuario() -> list[dict]:
        """Estadisticas agregadas por usuario."""
        conn = db_local.get_connection()
        rows = conn.execute("""
            SELECT
                usuario,
                COUNT(*) as total,
                SUM(CASE WHEN accion = 'create' THEN 1 ELSE 0 END) as creates,
                SUM(CASE WHEN accion = 'update' THEN 1 ELSE 0 END) as updates,
                SUM(CASE WHEN accion = 'delete' THEN 1 ELSE 0 END) as deletes,
                MAX(timestamp) as ultima_actividad
            FROM audit_log
            GROUP BY usuario
            ORDER BY total DESC
        """).fetchall()
        conn.close()

        result = []
        for r in rows:
            result.append({
                "usuario": r[0] or "sistema",
                "total": r[1],
                "creates": r[2],
                "updates": r[3],
                "deletes": r[4],
                "ultima_actividad": r[5] or "",
            })
        return result

    @staticmethod
    def get_acciones_hoy() -> int:
        """Total de acciones realizadas hoy."""
        hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return db_local.count("audit_log", "timestamp >= ?", (hoy,))

    @staticmethod
    def get_actividad_diaria(dias: int = 30) -> list[dict]:
        """Cantidad de acciones por dia (ultimos N dias)."""
        desde = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime("%Y-%m-%d")
        conn = db_local.get_connection()
        rows = conn.execute("""
            SELECT
                DATE(timestamp) as fecha,
                COUNT(*) as cantidad
            FROM audit_log
            WHERE timestamp >= ?
            GROUP BY DATE(timestamp)
            ORDER BY fecha ASC
        """, (desde,)).fetchall()
        conn.close()
        return [{"fecha": r[0], "cantidad": r[1]} for r in rows]

    @staticmethod
    def get_actividad_por_usuario(dias: int = 30) -> list[dict]:
        """Cantidad de acciones por usuario (ultimos N dias)."""
        desde = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime("%Y-%m-%d")
        conn = db_local.get_connection()
        rows = conn.execute("""
            SELECT
                usuario,
                COUNT(*) as cantidad
            FROM audit_log
            WHERE timestamp >= ?
            GROUP BY usuario
            ORDER BY cantidad DESC
        """, (desde,)).fetchall()
        conn.close()
        return [{"usuario": r[0] or "sistema", "cantidad": r[1]} for r in rows]

    @staticmethod
    def get_actividad_por_modulo(dias: int = 30) -> list[dict]:
        """Cantidad de acciones por coleccion/modulo (ultimos N dias)."""
        desde = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime("%Y-%m-%d")
        conn = db_local.get_connection()
        rows = conn.execute("""
            SELECT
                coleccion,
                COUNT(*) as cantidad
            FROM audit_log
            WHERE timestamp >= ?
            GROUP BY coleccion
            ORDER BY cantidad DESC
        """, (desde,)).fetchall()
        conn.close()
        return [
            {"modulo": COLECCION_LABELS.get(r[0], r[0] or "Otro"), "cantidad": r[1]}
            for r in rows
        ]

    @staticmethod
    def get_campos_modificados(audit_id: str) -> list[dict]:
        """Compara datos_anteriores vs datos_nuevos y devuelve campos que cambiaron."""
        row = db_local.find_by_id("audit_log", audit_id)
        if not row:
            return []

        accion = row.get("accion", "")
        anteriores = _parse_json(row.get("datos_anteriores"))
        nuevos = _parse_json(row.get("datos_nuevos"))

        # Campos internos que no mostrar al usuario
        CAMPOS_OCULTOS = {"_id", "sync_status", "created_by_machine", "version", "updated_at"}

        cambios = []

        if accion == "create":
            # Mostrar todos los campos nuevos
            for campo, valor in (nuevos or {}).items():
                if campo in CAMPOS_OCULTOS:
                    continue
                cambios.append({
                    "campo": campo,
                    "anterior": "",
                    "nuevo": _format_value(valor),
                    "tipo": "nuevo",
                })
        elif accion == "delete":
            # Mostrar todos los campos eliminados
            for campo, valor in (anteriores or {}).items():
                if campo in CAMPOS_OCULTOS:
                    continue
                cambios.append({
                    "campo": campo,
                    "anterior": _format_value(valor),
                    "nuevo": "",
                    "tipo": "eliminado",
                })
        elif accion == "update":
            # Mostrar solo campos que cambiaron
            all_keys = set()
            if anteriores:
                all_keys.update(anteriores.keys())
            if nuevos:
                all_keys.update(nuevos.keys())

            for campo in sorted(all_keys):
                if campo in CAMPOS_OCULTOS:
                    continue
                val_ant = (anteriores or {}).get(campo)
                val_new = (nuevos or {}).get(campo)
                if str(val_ant) != str(val_new) and val_new is not None:
                    cambios.append({
                        "campo": campo,
                        "anterior": _format_value(val_ant),
                        "nuevo": _format_value(val_new),
                        "tipo": "modificado",
                    })

        return cambios

    @staticmethod
    def get_usuarios_activos() -> list[str]:
        """Lista de usuarios que tienen registros en el audit log."""
        conn = db_local.get_connection()
        rows = conn.execute(
            "SELECT DISTINCT usuario FROM audit_log WHERE usuario IS NOT NULL ORDER BY usuario"
        ).fetchall()
        conn.close()
        return [r[0] for r in rows if r[0]]

    @staticmethod
    def get_colecciones_activas() -> list[str]:
        """Lista de colecciones que tienen registros en el audit log."""
        conn = db_local.get_connection()
        rows = conn.execute(
            "SELECT DISTINCT coleccion FROM audit_log WHERE coleccion IS NOT NULL ORDER BY coleccion"
        ).fetchall()
        conn.close()
        return [r[0] for r in rows if r[0]]

    @staticmethod
    def _generar_resumen(row: dict) -> str:
        """Genera un resumen legible del cambio."""
        accion = row.get("accion", "")
        coleccion = COLECCION_LABELS.get(row.get("coleccion", ""), row.get("coleccion", ""))

        if accion == "create":
            nuevos = _parse_json(row.get("datos_nuevos"))
            nombre = _extraer_nombre(nuevos)
            return f"Nuevo registro en {coleccion}" + (f": {nombre}" if nombre else "")
        elif accion == "delete":
            anteriores = _parse_json(row.get("datos_anteriores"))
            nombre = _extraer_nombre(anteriores)
            return f"Eliminado de {coleccion}" + (f": {nombre}" if nombre else "")
        elif accion == "update":
            nuevos = _parse_json(row.get("datos_nuevos"))
            if nuevos:
                campos = [k for k in nuevos.keys()
                          if k not in ("_id", "sync_status", "created_by_machine", "version", "updated_at")]
                if len(campos) <= 3:
                    return f"Editado en {coleccion}: {', '.join(campos)}"
                return f"Editado en {coleccion}: {len(campos)} campos"
            return f"Editado en {coleccion}"
        return accion


# ── Helpers privados ──

def _parse_json(value) -> dict | None:
    """Parsea un valor JSON almacenado como string."""
    if not value:
        return None
    if isinstance(value, dict):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def _format_value(value) -> str:
    """Formatea un valor para mostrar al usuario."""
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


def _extraer_nombre(data: dict | None) -> str:
    """Intenta extraer un nombre legible de los datos."""
    if not data:
        return ""
    for campo in ("nombre_completo", "nombre", "descripcion", "motivo", "tipo_tramite"):
        val = data.get(campo)
        if val:
            return str(val)[:50]
    return ""
