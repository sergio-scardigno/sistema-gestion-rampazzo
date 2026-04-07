"""Controlador de Reportes – consultas de datos para KPIs y graficos.

Metricas del pliego tecnico incluidas:
  - KPIs operativos / comerciales / economicos
  - Tiempos promedio de resolucion
  - Retrasos por etapa
  - Turnos vs casos
  - Perdidas (consultas no convertidas)
  - Indicadores humanos (rendimiento, carga, errores)
"""
from datetime import datetime, date
from core import db_local


class ReporteController:

    # ── KPIs basicos ──

    @staticmethod
    def kpis_operativos() -> dict:
        total_exp = db_local.count("expedientes")
        activos = db_local.count("expedientes", "estado NOT IN ('Cerrado','Archivado')")
        cerrados = db_local.count("expedientes", "estado IN ('Cerrado','Archivado')")
        tareas_pend = db_local.count("tareas", "estado IN ('Pendiente','En curso','En espera')")
        from controllers.tarea_controller import TareaController
        vencidas = len(TareaController.get_vencidas())
        return {
            "total_expedientes": total_exp,
            "expedientes_activos": activos,
            "expedientes_cerrados": cerrados,
            "tareas_pendientes": tareas_pend,
            "tareas_vencidas": vencidas,
        }

    @staticmethod
    def kpis_comerciales() -> dict:
        """KPIs basados en clientes (reemplaza antiguas metricas de consultas CRM)."""
        total_clientes = db_local.count("clientes")
        return {
            "total_clientes": total_clientes,
        }

    @staticmethod
    def kpis_economicos() -> dict:
        conn = db_local.get_connection()
        ingresos = conn.execute(
            "SELECT COALESCE(SUM(monto), 0) FROM movimientos WHERE tipo = 'Honorario' AND estado = 'Cancelado'"
        ).fetchone()[0]
        pendientes = conn.execute(
            "SELECT COALESCE(SUM(saldo), 0) FROM movimientos WHERE estado IN ('Pendiente','Parcial')"
        ).fetchone()[0]
        conn.close()
        return {
            "ingresos_cobrados": float(ingresos),
            "pendientes_cobro": float(pendientes),
        }

    # ── Desglose ──

    @staticmethod
    def expedientes_por_tipo() -> list[dict]:
        conn = db_local.get_connection()
        rows = conn.execute(
            "SELECT tipo_tramite, COUNT(*) as cantidad FROM expedientes GROUP BY tipo_tramite ORDER BY cantidad DESC"
        ).fetchall()
        conn.close()
        return [{"tipo": r[0] or "Sin tipo", "cantidad": r[1]} for r in rows]

    @staticmethod
    def expedientes_por_responsable() -> list[dict]:
        conn = db_local.get_connection()
        rows = conn.execute("""
            SELECT COALESCE(u.nombre_completo, e.responsable, 'Sin asignar') as resp,
                   COUNT(*) as cantidad
            FROM expedientes e
            LEFT JOIN usuarios u ON e.responsable_username = u.username
            WHERE e.estado NOT IN ('Cerrado','Archivado')
            GROUP BY resp
            ORDER BY cantidad DESC
        """).fetchall()
        conn.close()
        return [{"responsable": r[0] or "Sin asignar", "cantidad": r[1]} for r in rows]

    @staticmethod
    def clientes_por_procedencia() -> list[dict]:
        """Agrupa clientes por procedencia del contacto."""
        conn = db_local.get_connection()
        rows = conn.execute(
            "SELECT procedencia_contacto, COUNT(*) as cantidad FROM clientes "
            "GROUP BY procedencia_contacto ORDER BY cantidad DESC"
        ).fetchall()
        conn.close()
        return [{"procedencia": r[0] or "Sin especificar", "cantidad": r[1]} for r in rows]

    # ── Tiempos promedio de resolucion ──

    @staticmethod
    def tiempo_promedio_resolucion() -> dict:
        """Retorna el tiempo promedio en dias entre apertura y cierre de expedientes cerrados."""
        conn = db_local.get_connection()
        rows = conn.execute("""
            SELECT fecha_apertura, fecha_cierre
            FROM expedientes
            WHERE estado IN ('Cerrado','Archivado')
              AND fecha_apertura IS NOT NULL AND fecha_apertura != ''
              AND fecha_cierre IS NOT NULL AND fecha_cierre != ''
        """).fetchall()
        conn.close()

        if not rows:
            return {"promedio_dias": 0, "total_cerrados": 0, "min_dias": 0, "max_dias": 0}

        dias_list = []
        for r in rows:
            try:
                fa = datetime.strptime(r[0][:10], "%Y-%m-%d").date()
                fc = datetime.strptime(r[1][:10], "%Y-%m-%d").date()
                d = (fc - fa).days
                if d >= 0:
                    dias_list.append(d)
            except (ValueError, TypeError):
                continue

        if not dias_list:
            return {"promedio_dias": 0, "total_cerrados": 0, "min_dias": 0, "max_dias": 0}

        return {
            "promedio_dias": round(sum(dias_list) / len(dias_list), 1),
            "total_cerrados": len(dias_list),
            "min_dias": min(dias_list),
            "max_dias": max(dias_list),
        }

    @staticmethod
    def tiempo_promedio_por_tipo() -> list[dict]:
        """Tiempo promedio de resolucion por tipo de tramite."""
        conn = db_local.get_connection()
        rows = conn.execute("""
            SELECT tipo_tramite, fecha_apertura, fecha_cierre
            FROM expedientes
            WHERE estado IN ('Cerrado','Archivado')
              AND fecha_apertura IS NOT NULL AND fecha_apertura != ''
              AND fecha_cierre IS NOT NULL AND fecha_cierre != ''
        """).fetchall()
        conn.close()

        por_tipo: dict[str, list[int]] = {}
        for r in rows:
            tipo = r[0] or "Sin tipo"
            try:
                fa = datetime.strptime(r[1][:10], "%Y-%m-%d").date()
                fc = datetime.strptime(r[2][:10], "%Y-%m-%d").date()
                d = (fc - fa).days
                if d >= 0:
                    por_tipo.setdefault(tipo, []).append(d)
            except (ValueError, TypeError):
                continue

        return [
            {"tipo": t, "promedio_dias": round(sum(ds) / len(ds), 1), "cantidad": len(ds)}
            for t, ds in sorted(por_tipo.items(), key=lambda x: sum(x[1]) / len(x[1]), reverse=True)
        ]

    # ── Retrasos por etapa (tareas vencidas por tipo de accion) ──

    @staticmethod
    def retrasos_por_etapa() -> list[dict]:
        """Tareas vencidas agrupadas por tipo de accion."""
        today = date.today().isoformat()
        conn = db_local.get_connection()
        rows = conn.execute("""
            SELECT tipo_accion, COUNT(*) as vencidas,
                   AVG(julianday(?) - julianday(fecha_vencimiento)) as dias_retraso_prom
            FROM tareas
            WHERE estado IN ('Pendiente','En curso')
              AND fecha_vencimiento < ?
              AND fecha_vencimiento IS NOT NULL AND fecha_vencimiento != ''
            GROUP BY tipo_accion
            ORDER BY vencidas DESC
        """, (today, today)).fetchall()
        conn.close()
        return [
            {"etapa": r[0] or "Sin tipo", "vencidas": r[1], "dias_retraso_prom": round(r[2] or 0, 1)}
            for r in rows
        ]

    # ── Turnos vs Casos ──

    @staticmethod
    def turnos_vs_casos() -> dict:
        """Compara cantidad de turnos ANSES contra cantidad de expedientes."""
        total_turnos = db_local.count("turnos")
        turnos_realizados = db_local.count("turnos", "estado = 'Realizado'")
        turnos_pendientes = db_local.count("turnos", "estado IN ('Pendiente','Confirmado')")
        total_exp = db_local.count("expedientes")
        exp_activos = db_local.count("expedientes", "estado NOT IN ('Cerrado','Archivado')")

        return {
            "total_turnos": total_turnos,
            "turnos_realizados": turnos_realizados,
            "turnos_pendientes": turnos_pendientes,
            "total_expedientes": total_exp,
            "expedientes_activos": exp_activos,
            "ratio": round(total_turnos / total_exp, 2) if total_exp else 0,
        }

    # ── Perdidas (consultas no convertidas) ──

    @staticmethod
    def analisis_clientes_sin_carpeta() -> dict:
        """Clientes que no tienen ninguna carpeta asociada."""
        total = db_local.count("clientes")
        conn = db_local.get_connection()
        con_carpeta = conn.execute(
            "SELECT COUNT(DISTINCT id_cliente) FROM expedientes"
        ).fetchone()[0]
        conn.close()
        sin_carpeta = total - con_carpeta
        tasa_sin_carpeta = round((sin_carpeta / total * 100), 1) if total else 0

        return {
            "total_clientes": total,
            "con_carpeta": con_carpeta,
            "sin_carpeta": sin_carpeta,
            "tasa_sin_carpeta": tasa_sin_carpeta,
        }

    # ── Indicadores humanos (rendimiento, carga, errores) ──

    @staticmethod
    def indicadores_humanos() -> list[dict]:
        """Indicadores por responsable: carga de expedientes, tareas activas,
        tareas vencidas, acciones de auditoria. Usa responsable_username."""
        today = date.today().isoformat()
        conn = db_local.get_connection()

        # Carga de expedientes activos por responsable
        exp_rows = conn.execute("""
            SELECT COALESCE(u.nombre_completo, e.responsable, 'Sin asignar') as resp,
                   e.responsable_username, COUNT(*) as exp_activos
            FROM expedientes e
            LEFT JOIN usuarios u ON e.responsable_username = u.username
            WHERE e.estado NOT IN ('Cerrado','Archivado')
            GROUP BY resp
        """).fetchall()
        carga = {}
        for r in exp_rows:
            key = r[1] or r[0]
            carga[key] = {"responsable": r[0] or "Sin asignar",
                          "username": r[1] or "", "exp_activos": r[2]}

        # Tareas pendientes por responsable
        tar_rows = conn.execute("""
            SELECT COALESCE(u.nombre_completo, t.responsable, 'Sin asignar') as resp,
                   t.responsable_username, COUNT(*) as tareas_pendientes
            FROM tareas t
            LEFT JOIN usuarios u ON t.responsable_username = u.username
            WHERE t.estado IN ('Pendiente','En curso','En espera')
            GROUP BY resp
        """).fetchall()
        for r in tar_rows:
            key = r[1] or r[0]
            if key in carga:
                carga[key]["tareas_pendientes"] = r[2]
            else:
                carga[key] = {"responsable": r[0] or "Sin asignar",
                              "username": r[1] or "", "exp_activos": 0,
                              "tareas_pendientes": r[2]}

        # Tareas vencidas por responsable
        venc_rows = conn.execute("""
            SELECT COALESCE(t.responsable_username, t.responsable) as key,
                   COUNT(*) as tareas_vencidas
            FROM tareas t
            WHERE t.estado IN ('Pendiente','En curso')
              AND t.fecha_vencimiento < ?
              AND t.fecha_vencimiento IS NOT NULL AND t.fecha_vencimiento != ''
            GROUP BY key
        """, (today,)).fetchall()
        for r in venc_rows:
            key = r[0] or "Sin asignar"
            if key in carga:
                carga[key]["tareas_vencidas"] = r[1]

        # Acciones en auditoria (ultimos 30 dias) por usuario
        audit_rows = conn.execute("""
            SELECT usuario, COUNT(*) as acciones_30d
            FROM audit_log
            WHERE timestamp >= date('now', '-30 days')
            GROUP BY usuario
        """).fetchall()
        audit_map = {r[0]: r[1] for r in audit_rows}
        for key, data in carga.items():
            uname = data.get("username", "")
            if uname in audit_map:
                data["acciones_30d"] = audit_map[uname]

        conn.close()

        result = []
        for data in carga.values():
            data.setdefault("tareas_pendientes", 0)
            data.setdefault("tareas_vencidas", 0)
            data.setdefault("acciones_30d", 0)
            result.append(data)

        result.sort(key=lambda x: x["exp_activos"], reverse=True)
        return result

    # ── Tiempos por estado (desde historial de estados) ──

    @staticmethod
    def tiempos_por_estado_expediente(id_expediente: str) -> dict:
        """Retorna el tiempo total (en dias) que un expediente paso en cada estado.

        Para segmentos abiertos (fin_ts IS NULL) usa la fecha actual como fin.
        Retorna: {"estados": [{"estado": str, "dias": float}], "total_dias": float}
        """
        from datetime import timezone
        conn = db_local.get_connection()
        rows = conn.execute("""
            SELECT estado, etapa_anterior, inicio_ts, fin_ts
            FROM expediente_estado_historial
            WHERE id_expediente = ?
            ORDER BY inicio_ts ASC
        """, (id_expediente,)).fetchall()
        conn.close()

        now = datetime.now(timezone.utc)
        por_estado: dict[str, float] = {}
        total = 0.0

        for r in rows:
            estado = r[0]
            try:
                inicio = datetime.fromisoformat(r[2])
                if r[3]:
                    fin = datetime.fromisoformat(r[3])
                else:
                    fin = now
                # Asegurar que ambos sean aware para poder restar
                if inicio.tzinfo is None:
                    inicio = inicio.replace(tzinfo=timezone.utc)
                if fin.tzinfo is None:
                    fin = fin.replace(tzinfo=timezone.utc)
                dias = max((fin - inicio).total_seconds() / 86400, 0)
            except (ValueError, TypeError):
                continue
            por_estado[estado] = por_estado.get(estado, 0) + dias
            total += dias

        from controllers.expediente_controller import ExpedienteController
        estados_list = [
            {
                "estado": e,
                "estado_label": ExpedienteController.etapa_por_codigo(e).get("titulo", e),
                "dias": round(d, 1),
            }
            for e, d in sorted(por_estado.items(), key=lambda x: x[1], reverse=True)
        ]
        return {"estados": estados_list, "total_dias": round(total, 1)}

    @staticmethod
    def tiempos_por_estado_responsable(desde: str = "", hasta: str = "") -> list[dict]:
        """Tiempo promedio (en dias) por estado agrupado por responsable.

        Usa segmentos cerrados (fin_ts IS NOT NULL) dentro del rango de fechas.
        Retorna: [{"responsable": str, "estado": str, "promedio_dias": float, "cantidad": int}]
        """
        conn = db_local.get_connection()
        conditions = ["h.fin_ts IS NOT NULL"]
        params: list = []
        if desde:
            conditions.append("h.inicio_ts >= ?")
            params.append(desde)
        if hasta:
            conditions.append("h.inicio_ts <= ?")
            params.append(hasta + "T23:59:59")
        where = " AND ".join(conditions)

        rows = conn.execute(f"""
            SELECT COALESCE(u.nombre_completo, h.responsable_username, 'Sin asignar') as resp,
                   h.estado,
                   AVG(julianday(h.fin_ts) - julianday(h.inicio_ts)) as promedio_dias,
                   COUNT(*) as cantidad
            FROM expediente_estado_historial h
            LEFT JOIN usuarios u ON h.responsable_username = u.username
            WHERE {where}
            GROUP BY resp, h.estado
            ORDER BY resp, promedio_dias DESC
        """, params).fetchall()
        conn.close()

        return [
            {
                "responsable": r[0] or "Sin asignar",
                "estado": r[1],
                "promedio_dias": round(r[2] or 0, 1),
                "cantidad": r[3],
            }
            for r in rows
        ]

    @staticmethod
    def aperturas_y_cierres_por_responsable(desde: str = "", hasta: str = "") -> list[dict]:
        """Cantidad de carpetas iniciadas y cerradas por responsable, con tiempo promedio.

        Retorna: [{"responsable": str, "iniciadas": int, "cerradas": int, "promedio_dias_cierre": float}]
        """
        conn = db_local.get_connection()

        # Filtro de fechas
        where_ini = "1=1"
        where_cierre = "1=1"
        params_ini: list = []
        params_cierre: list = []
        if desde:
            where_ini += " AND e.fecha_apertura >= ?"
            params_ini.append(desde)
            where_cierre += " AND e.fecha_cierre >= ?"
            params_cierre.append(desde)
        if hasta:
            where_ini += " AND e.fecha_apertura <= ?"
            params_ini.append(hasta)
            where_cierre += " AND e.fecha_cierre <= ?"
            params_cierre.append(hasta)

        # Iniciadas por responsable
        ini_rows = conn.execute(f"""
            SELECT COALESCE(u.nombre_completo, e.responsable, 'Sin asignar') as resp,
                   e.responsable_username,
                   COUNT(*) as iniciadas
            FROM expedientes e
            LEFT JOIN usuarios u ON e.responsable_username = u.username
            WHERE {where_ini}
            GROUP BY resp
        """, params_ini).fetchall()

        # Cerradas por responsable (con promedio de dias apertura->cierre)
        cierre_rows = conn.execute(f"""
            SELECT COALESCE(u.nombre_completo, e.responsable, 'Sin asignar') as resp,
                   e.responsable_username,
                   COUNT(*) as cerradas,
                   AVG(julianday(e.fecha_cierre) - julianday(e.fecha_apertura)) as prom_dias
            FROM expedientes e
            LEFT JOIN usuarios u ON e.responsable_username = u.username
            WHERE e.estado IN ('Cerrado','Archivado')
              AND e.fecha_apertura IS NOT NULL AND e.fecha_apertura != ''
              AND e.fecha_cierre IS NOT NULL AND e.fecha_cierre != ''
              AND {where_cierre}
            GROUP BY resp
        """, params_cierre).fetchall()
        conn.close()

        # Combinar resultados
        data: dict[str, dict] = {}
        for r in ini_rows:
            key = r[1] or r[0]
            data[key] = {"responsable": r[0], "iniciadas": r[2], "cerradas": 0, "promedio_dias_cierre": 0}
        for r in cierre_rows:
            key = r[1] or r[0]
            if key in data:
                data[key]["cerradas"] = r[2]
                data[key]["promedio_dias_cierre"] = round(r[3] or 0, 1)
            else:
                data[key] = {
                    "responsable": r[0], "iniciadas": 0,
                    "cerradas": r[2], "promedio_dias_cierre": round(r[3] or 0, 1),
                }

        result = sorted(data.values(), key=lambda x: x["iniciadas"], reverse=True)
        return result

    # ── Datasets de análisis (export separados) ──

    @staticmethod
    def clientes_para_analisis() -> list[dict]:
        """Dataset estable de clientes para análisis externo (Excel/CSV)."""
        conn = db_local.get_connection()
        rows = conn.execute("""
            SELECT
                _id,
                id_cliente,
                numero_carpeta,
                nombre_completo,
                dni,
                cuil,
                fecha_nacimiento,
                direccion,
                localidad,
                telefonos,
                email,
                obra_social,
                actividad,
                procedencia_contacto,
                observaciones,
                is_deleted,
                deleted_at,
                deleted_by,
                updated_at,
                version,
                sync_status,
                created_by_machine
            FROM clientes
            ORDER BY nombre_completo ASC
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @staticmethod
    def carpetas_para_analisis() -> list[dict]:
        """Dataset estable de carpetas/expedientes para análisis externo."""
        conn = db_local.get_connection()
        rows = conn.execute("""
            SELECT
                e._id,
                e.id_expediente,
                e.id_cliente,
                c.numero_carpeta,
                c.nombre_completo AS cliente_nombre,
                c.dni AS cliente_dni,
                c.cuil AS cliente_cuil,
                e.tipo_tramite,
                e.area,
                e.rama,
                e.subtipo,
                e.estado,
                e.prioridad,
                e.responsable,
                e.responsable_username,
                e.responsable_secundario,
                e.responsable_secundario_username,
                e.fecha_apertura,
                e.fecha_cierre,
                e.numero_expediente_anses,
                e.ubicacion_fisica,
                e.link_drive,
                e.resultado,
                e.observaciones,
                e.is_deleted,
                e.deleted_at,
                e.deleted_by,
                e.updated_at,
                e.version,
                e.sync_status,
                e.created_by_machine
            FROM expedientes e
            LEFT JOIN clientes c ON c._id = e.id_cliente
            ORDER BY e.id_expediente DESC
        """).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    # ── Economicos extendidos por periodo ──

    @staticmethod
    def kpis_economicos_periodo(desde: str = "", hasta: str = "") -> dict:
        """KPIs economicos filtrados por rango de fechas (formato YYYY-MM-DD)."""
        conn = db_local.get_connection()
        where_parts = []
        params = []
        if desde:
            where_parts.append("fecha >= ?")
            params.append(desde)
        if hasta:
            where_parts.append("fecha <= ?")
            params.append(hasta)
        where = " AND ".join(where_parts) if where_parts else "1=1"

        ingresos = conn.execute(
            f"SELECT COALESCE(SUM(monto), 0) FROM movimientos WHERE tipo = 'Honorario' AND estado = 'Cancelado' AND {where}",
            params
        ).fetchone()[0]
        pendientes = conn.execute(
            f"SELECT COALESCE(SUM(saldo), 0) FROM movimientos WHERE estado IN ('Pendiente','Parcial') AND {where}",
            params
        ).fetchone()[0]
        total_movs = conn.execute(
            f"SELECT COUNT(*) FROM movimientos WHERE {where}",
            params
        ).fetchone()[0]
        conn.close()

        return {
            "ingresos_cobrados": float(ingresos),
            "pendientes_cobro": float(pendientes),
            "total_movimientos": total_movs,
            "desde": desde or "inicio",
            "hasta": hasta or "hoy",
        }
