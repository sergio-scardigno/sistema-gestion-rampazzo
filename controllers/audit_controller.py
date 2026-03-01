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
                limit: int = 200,
                resumen_detallado: bool = False) -> list[dict]:
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

        # Enriquecer cada registro con resumen legible.
        # En listados grandes usamos resumen rapido para mejorar rendimiento.
        for row in rows:
            row["accion_label"] = ACCION_LABELS.get(row.get("accion", ""), row.get("accion", ""))
            row["coleccion_label"] = COLECCION_LABELS.get(row.get("coleccion", ""), row.get("coleccion", ""))
            if resumen_detallado:
                row["resumen"] = AuditController._generar_resumen(row)
            else:
                row["resumen"] = AuditController._generar_resumen_rapido(row)

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
    def get_responsables_tareas_asignadas() -> list[str]:
        """Lista de usuarios con asignaciones de tareas registradas."""
        conn = db_local.get_connection()
        rows = conn.execute(
            """
            SELECT username
            FROM (
                SELECT DISTINCT target_username AS username
                FROM notificaciones
                WHERE tipo = 'tarea_asignada'
                  AND target_username IS NOT NULL
                  AND target_username <> ''

                UNION

                SELECT DISTINCT t.responsable_username AS username
                FROM tareas t
                INNER JOIN usuarios u ON u.username = t.responsable_username
                WHERE COALESCE(t.responsable_username, '') <> ''
                  AND u.rol = 'administrador'
            )
            WHERE username IS NOT NULL AND username <> ''
            ORDER BY username
            """
        ).fetchall()
        conn.close()
        return [r[0] for r in rows if r[0]]

    @staticmethod
    def get_seguimiento_tareas(
        responsable: str = "",
        estado: str = "",
        fecha_desde: str = "",
        fecha_hasta: str = "",
        limit: int = 300,
    ) -> list[dict]:
        """
        Seguimiento por tarea asignada para administracion.

        Fuente principal: notificaciones tipo 'tarea_asignada' (asignacion + lectura).
        Se enriquece con tareas (estado actual) y audit_log (fecha de cumplimiento).
        """
        conditions = [
            "n.tipo = 'tarea_asignada'",
            "COALESCE(n.id_referencia, '') <> ''",
        ]
        params: list = []

        if responsable:
            conditions.append("n.target_username = ?")
            params.append(responsable)
        if estado:
            conditions.append("COALESCE(t.estado, '') = ?")
            params.append(estado)
        if fecha_desde:
            conditions.append("SUBSTR(n.created_at, 1, 10) >= ?")
            params.append(fecha_desde)
        if fecha_hasta:
            conditions.append("SUBSTR(n.created_at, 1, 10) <= ?")
            params.append(fecha_hasta)

        where_sql = " AND ".join(conditions)
        sql = f"""
            SELECT
                n._id AS notificacion_id,
                n.target_username AS asignada_a,
                n.created_at AS fecha_asignacion,
                n.leida AS leida,
                n.updated_at AS updated_at,
                n.id_referencia AS tarea_ref,
                t._id AS tarea_oid,
                t.id_tarea AS id_tarea,
                t.descripcion AS descripcion,
                t.estado AS estado_actual
            FROM notificaciones n
            LEFT JOIN tareas t ON t._id = n.id_referencia
            WHERE {where_sql}
            ORDER BY n.created_at DESC
            LIMIT ?
        """
        params.append(limit)
        conn = db_local.get_connection()
        rows = conn.execute(sql, tuple(params)).fetchall()

        # Fallback: tareas asignadas a administradores sin notificacion registrada.
        admin_conditions = ["u.rol = 'administrador'", "COALESCE(t.responsable_username, '') <> ''"]
        admin_params: list = []
        if responsable:
            admin_conditions.append("t.responsable_username = ?")
            admin_params.append(responsable)
        if estado:
            admin_conditions.append("COALESCE(t.estado, '') = ?")
            admin_params.append(estado)
        if fecha_desde:
            admin_conditions.append("SUBSTR(COALESCE(NULLIF(t.updated_at, ''), t.fecha_inicio), 1, 10) >= ?")
            admin_params.append(fecha_desde)
        if fecha_hasta:
            admin_conditions.append("SUBSTR(COALESCE(NULLIF(t.updated_at, ''), t.fecha_inicio), 1, 10) <= ?")
            admin_params.append(fecha_hasta)

        admin_where_sql = " AND ".join(admin_conditions)
        admin_sql = f"""
            SELECT
                '' AS notificacion_id,
                t.responsable_username AS asignada_a,
                COALESCE(NULLIF(t.updated_at, ''), t.fecha_inicio) AS fecha_asignacion,
                0 AS leida,
                '' AS updated_at,
                t._id AS tarea_ref,
                t._id AS tarea_oid,
                t.id_tarea AS id_tarea,
                t.descripcion AS descripcion,
                t.estado AS estado_actual
            FROM tareas t
            INNER JOIN usuarios u ON u.username = t.responsable_username
            WHERE {admin_where_sql}
              AND NOT EXISTS (
                  SELECT 1
                  FROM notificaciones n
                  WHERE n.tipo = 'tarea_asignada'
                    AND n.id_referencia = t._id
                    AND n.target_username = t.responsable_username
              )
            ORDER BY fecha_asignacion DESC
            LIMIT ?
        """
        admin_params.append(limit)
        admin_rows = conn.execute(admin_sql, tuple(admin_params)).fetchall()
        conn.close()
        rows = list(rows) + list(admin_rows)

        # Historial antiguo puede tener duplicados; se conserva el registro mas reciente por tarea+responsable.
        deduped: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for row in rows:
            data = db_local.dict_from_row(row) or {}
            key = (data.get("asignada_a", ""), data.get("tarea_ref", ""))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(data)
        deduped.sort(key=lambda item: item.get("fecha_asignacion", ""), reverse=True)

        task_ids = [r.get("tarea_oid") or r.get("tarea_ref") for r in deduped if (r.get("tarea_oid") or r.get("tarea_ref"))]
        fecha_cierre_por_tarea = AuditController._get_fecha_cumplimiento_por_tarea(task_ids)

        cierre_estados = {"Cumplida", "Completada", "Cancelada"}
        now = datetime.now(timezone.utc)
        result: list[dict] = []
        for row in deduped:
            tarea_oid = row.get("tarea_oid") or row.get("tarea_ref") or ""
            leida = int(row.get("leida") or 0) == 1
            fecha_asignacion = row.get("fecha_asignacion", "") or ""
            fecha_lectura = row.get("updated_at", "") if leida else ""
            estado_actual = row.get("estado_actual", "") or ""
            fecha_cumplimiento = fecha_cierre_por_tarea.get(tarea_oid, "")

            dias_sin_leer = 0
            if not leida and estado_actual not in cierre_estados:
                dt_asig = _parse_iso_datetime(fecha_asignacion)
                if dt_asig:
                    dias_sin_leer = max(0, (now - dt_asig).days)

            result.append(
                {
                    "id_tarea": row.get("id_tarea", "") or "",
                    "tarea_oid": tarea_oid,
                    "descripcion": row.get("descripcion", "") or "",
                    "asignada_a": row.get("asignada_a", "") or "",
                    "fecha_asignacion": fecha_asignacion,
                    "leida": leida,
                    "fecha_lectura": fecha_lectura or "",
                    "estado_actual": estado_actual,
                    "fecha_cumplimiento": fecha_cumplimiento,
                    "dias_sin_leer": dias_sin_leer,
                }
            )
        return result

    @staticmethod
    def _get_fecha_cumplimiento_por_tarea(task_ids: list[str]) -> dict[str, str]:
        """Busca en audit_log el ultimo momento en que una tarea paso a estado cerrado."""
        if not task_ids:
            return {}
        placeholders = ",".join(["?"] * len(task_ids))
        conn = db_local.get_connection()
        rows = conn.execute(
            f"""
            SELECT documento_id, datos_anteriores, datos_nuevos, timestamp
            FROM audit_log
            WHERE coleccion = 'tareas'
              AND accion = 'update'
              AND documento_id IN ({placeholders})
            ORDER BY timestamp DESC
            """,
            tuple(task_ids),
        ).fetchall()
        conn.close()

        cierre_estados = {"Cumplida", "Completada", "Cancelada"}
        fecha_por_tarea: dict[str, str] = {}
        for row in rows:
            rec = db_local.dict_from_row(row) or {}
            tarea_id = rec.get("documento_id", "")
            if not tarea_id or tarea_id in fecha_por_tarea:
                continue

            nuevos = _parse_json(rec.get("datos_nuevos"))
            anteriores = _parse_json(rec.get("datos_anteriores"))
            estado_nuevo = (nuevos or {}).get("estado")
            estado_anterior = (anteriores or {}).get("estado")
            if estado_nuevo in cierre_estados and estado_nuevo != estado_anterior:
                fecha_por_tarea[tarea_id] = rec.get("timestamp", "") or ""
        return fecha_por_tarea

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

    @staticmethod
    def _generar_resumen_rapido(row: dict) -> str:
        """Resumen liviano para tablas (evita parsear JSON pesado)."""
        accion = row.get("accion", "")
        coleccion = COLECCION_LABELS.get(row.get("coleccion", ""), row.get("coleccion", ""))
        if accion == "create":
            return f"Nuevo registro en {coleccion}"
        if accion == "delete":
            return f"Eliminado de {coleccion}"
        if accion == "update":
            return f"Editado en {coleccion}"
        return accion or "Accion"


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


def _parse_iso_datetime(value: str) -> datetime | None:
    """Parse robusto para timestamps ISO o fecha simple."""
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.strptime(value[:10], "%Y-%m-%d")
        except ValueError:
            return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
