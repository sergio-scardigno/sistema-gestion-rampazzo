"""Controlador de Expedientes."""
import logging
from datetime import date, timedelta

from controllers.base_controller import BaseController
from core import db_local

logger = logging.getLogger(__name__)


class ExpedienteController(BaseController):
    TABLE = "expedientes"
    ID_FIELD = "id_expediente"

    TIPOS_TRAMITE = [
        "Jubilacion", "Retiro por salud", "Laboral", "Amparo",
        "Pension", "PUAM", "RTI", "Reajuste", "Otro"
    ]
    ESTADOS = [
        "Activo", "En tramite", "En espera", "Guardada",
        "Desfavorable", "Favorable", "Cerrado", "Archivado"
    ]
    ESTADOS_CIERRE = ["Cerrado", "Archivado"]
    PRIORIDADES = ["Alta", "Normal", "Baja"]
    MODALIDADES = ["Presencial", "Virtual"]
    RAMAS_CON_MODALIDAD = ["Previsional"]

    # ── Ramas jurídicas ──

    RAMAS = ["Laboral", "ART", "Previsional", "Amparos", "Migraciones", "Familia", "Daños"]

    SUBTIPOS_POR_RAMA = {
        "Laboral": [
            "Despido sin causa", "Despido indirecto", "Trabajo no registrado",
            "Diferencias salariales", "Enfermedad profesional",
            "Accidente laboral", "Ejecucion de sentencia laboral", "Amparo laboral",
        ],
        "ART": [
            "Accidente in itinere", "Accidente en establecimiento",
            "Enfermedad profesional", "Rechazo ART",
            "Revision Comision Medica", "Apelacion judicial",
            "Determinacion de incapacidad", "Ejecucion",
        ],
        "Previsional": [
            "Jubilacion ordinaria", "Jubilacion anticipada",
            "Retiro por invalidez", "Pension", "Reajuste",
            "Art. 9 Ley 24.463", "Tope docente",
            "Reconocimiento de servicios", "Moratoria",
        ],
        "Amparos": [
            "Amparo por mora administrativa", "Amparo por salud",
            "Amparo previsional", "Amparo contra ART",
            "Amparo por cobertura medica",
        ],
        "Migraciones": [
            "Ciudadania argentina", "Residencia permanente",
            "Residencia temporaria", "Recurso denegatoria",
            "Carta ciudadania judicial",
        ],
        "Familia": [
            "Alimentos", "Regimen de comunicacion", "Cuidado personal",
            "Divorcio", "Compensacion economica",
        ],
        "Daños": [
            "Accidente de transito", "Daño material",
            "Daño moral", "Mala praxis",
        ],
    }

    CAMPOS_POR_RAMA = {
        "Laboral": [
            {"key": "empresa_demandada", "label": "Empresa demandada", "tipo": "text"},
            {"key": "cuit_empresa", "label": "CUIT empresa", "tipo": "text"},
            {"key": "fecha_ingreso_laboral", "label": "Fecha ingreso", "tipo": "date"},
            {"key": "fecha_egreso", "label": "Fecha egreso", "tipo": "date"},
            {"key": "tipo_distracto", "label": "Tipo de distracto", "tipo": "text"},
            {"key": "categoria", "label": "Categoria", "tipo": "text"},
            {"key": "convenio_colectivo", "label": "Convenio colectivo", "tipo": "text"},
            {"key": "jornada", "label": "Jornada", "tipo": "text"},
            {"key": "salario_mensual", "label": "Salario mensual", "tipo": "number", "prefijo": "$ "},
            {"key": "antiguedad", "label": "Antiguedad", "tipo": "text"},
            {"key": "lugar_prestacion", "label": "Lugar de prestacion", "tipo": "text"},
            {"key": "carta_documento_enviada", "label": "Carta documento enviada", "tipo": "boolean"},
            {"key": "fecha_carta_documento", "label": "Fecha carta documento", "tipo": "date"},
            {"key": "seclo_iniciado", "label": "SECLO iniciado", "tipo": "boolean"},
            {"key": "fecha_seclo", "label": "Fecha SECLO", "tipo": "date"},
            {"key": "acuerdo_seclo", "label": "Acuerdo SECLO", "tipo": "boolean"},
            {"key": "monto_acuerdo_seclo", "label": "Monto acuerdo SECLO", "tipo": "number", "prefijo": "$ "},
        ],
        "ART": [
            {"key": "art_interviniente", "label": "ART interviniente", "tipo": "text"},
            {"key": "fecha_siniestro", "label": "Fecha siniestro", "tipo": "date"},
            {"key": "tipo_accidente", "label": "Tipo accidente", "tipo": "combo",
             "opciones": ["In itinere", "En establecimiento", "Enfermedad profesional"]},
            {"key": "denuncia_realizada", "label": "Denuncia realizada", "tipo": "boolean"},
            {"key": "fecha_denuncia", "label": "Fecha denuncia", "tipo": "date"},
            {"key": "comision_medica", "label": "Comision medica", "tipo": "text"},
            {"key": "dictamen", "label": "Dictamen", "tipo": "text"},
            {"key": "porcentaje_incapacidad", "label": "% Incapacidad", "tipo": "number"},
            {"key": "baremo_aplicado", "label": "Baremo aplicado", "tipo": "text"},
            {"key": "ingreso_base_mensual", "label": "Ingreso base mensual", "tipo": "number", "prefijo": "$ "},
            {"key": "monto_indemnizacion_estimado", "label": "Monto indemnizacion estimado", "tipo": "number", "prefijo": "$ "},
            {"key": "rechazo_art", "label": "Rechazo ART", "tipo": "boolean"},
        ],
        "Previsional": [
            {"key": "historia_laboral_cargada", "label": "Historia laboral cargada", "tipo": "boolean"},
            {"key": "anios_con_aportes", "label": "Años con aportes", "tipo": "integer", "maximo": 60},
            {"key": "servicios_insalubres", "label": "Servicios insalubres", "tipo": "boolean"},
            {"key": "regimen_especial", "label": "Regimen especial", "tipo": "text"},
            {"key": "fecha_solicitud_anses", "label": "Fecha solicitud ANSES", "tipo": "date"},
            {"key": "estado_tramite_anses", "label": "Estado tramite ANSES", "tipo": "combo",
             "opciones": ["Iniciado", "En analisis", "Observado", "Aprobado", "Rechazado"]},
            {"key": "resolucion_dictada", "label": "Resolucion dictada", "tipo": "text"},
            {"key": "haber_inicial", "label": "Haber inicial", "tipo": "number", "prefijo": "$ "},
            {"key": "diferencias_estimadas", "label": "Diferencias estimadas", "tipo": "number", "prefijo": "$ "},
            {"key": "plataforma_virtual", "label": "Plataforma virtual", "tipo": "combo",
             "opciones": ["Zoom", "Google Meet", "Teams", "WhatsApp", "Otro"], "solo_virtual": True},
            {"key": "link_reunion", "label": "Link de reunion", "tipo": "text", "solo_virtual": True},
            {"key": "fecha_reunion_virtual", "label": "Fecha reunion virtual", "tipo": "date", "solo_virtual": True},
            {"key": "hora_reunion_virtual", "label": "Hora reunion virtual", "tipo": "text", "solo_virtual": True},
            {"key": "documentos_enviados_digitalmente", "label": "Documentos enviados digitalmente",
             "tipo": "boolean", "solo_virtual": True},
            {"key": "detalle_documentos_digitales", "label": "Detalle documentos digitales",
             "tipo": "text", "solo_virtual": True},
        ],
        "Amparos": [
            {"key": "derecho_afectado", "label": "Derecho afectado", "tipo": "text"},
            {"key": "urgencia_amparo", "label": "Urgencia", "tipo": "combo",
             "opciones": ["Alta", "Media", "Baja"]},
            {"key": "cautelar_solicitada", "label": "Medida cautelar solicitada", "tipo": "boolean"},
            {"key": "fecha_interposicion", "label": "Fecha interposicion", "tipo": "date"},
            {"key": "resolucion_cautelar", "label": "Resolucion cautelar", "tipo": "text"},
            {"key": "resultado_amparo", "label": "Resultado", "tipo": "text"},
        ],
        "Migraciones": [
            {"key": "nacionalidad", "label": "Nacionalidad", "tipo": "text"},
            {"key": "fecha_ingreso_pais", "label": "Fecha ingreso al pais", "tipo": "date"},
            {"key": "tipo_residencia", "label": "Tipo residencia", "tipo": "combo",
             "opciones": ["Temporaria", "Permanente", "Precaria", "Irregular"]},
            {"key": "turno_dnm", "label": "Turno DNM", "tipo": "text"},
            {"key": "estado_tramite_migratorio", "label": "Estado tramite", "tipo": "combo",
             "opciones": ["Iniciado", "En proceso", "Observado", "Aprobado", "Rechazado"]},
            {"key": "documentacion_pendiente", "label": "Documentacion pendiente", "tipo": "text"},
        ],
        "Familia": [
            {"key": "tipo_conflicto_familia", "label": "Tipo conflicto", "tipo": "combo",
             "opciones": ["Alimentos", "Regimen de comunicacion", "Cuidado personal",
                          "Divorcio", "Compensacion economica"]},
            {"key": "hijos_cantidad", "label": "Cantidad de hijos", "tipo": "integer", "maximo": 20},
            {"key": "hijos_edades", "label": "Edades hijos", "tipo": "text"},
            {"key": "ingresos_parte_actora", "label": "Ingresos parte actora", "tipo": "number", "prefijo": "$ "},
            {"key": "ingresos_parte_demandada", "label": "Ingresos parte demandada", "tipo": "number", "prefijo": "$ "},
            {"key": "conviven", "label": "Conviven actualmente", "tipo": "boolean"},
            {"key": "acuerdo_previo", "label": "Acuerdo previo existente", "tipo": "boolean"},
            {"key": "violencia", "label": "Situacion de violencia", "tipo": "boolean"},
            {"key": "mediacion_realizada", "label": "Mediacion realizada", "tipo": "boolean"},
            {"key": "resultado_mediacion", "label": "Resultado mediacion", "tipo": "text"},
        ],
        "Daños": [
            {"key": "fecha_accidente", "label": "Fecha del accidente", "tipo": "date"},
            {"key": "lugar_accidente", "label": "Lugar del accidente", "tipo": "text"},
            {"key": "tipo_vehiculo", "label": "Tipo de vehiculo", "tipo": "text"},
            {"key": "intervencion_policial", "label": "Intervencion policial", "tipo": "boolean"},
            {"key": "testigos", "label": "Testigos", "tipo": "boolean"},
            {"key": "seguro_propio", "label": "Seguro propio", "tipo": "text"},
            {"key": "seguro_tercero", "label": "Seguro del tercero", "tipo": "text"},
            {"key": "lesiones", "label": "Lesiones sufridas", "tipo": "text"},
            {"key": "porcentaje_incapacidad_danos", "label": "% Incapacidad", "tipo": "number"},
            {"key": "dano_material", "label": "Daño material estimado", "tipo": "number", "prefijo": "$ "},
            {"key": "dano_moral", "label": "Daño moral estimado", "tipo": "number", "prefijo": "$ "},
            {"key": "gastos_medicos", "label": "Gastos medicos", "tipo": "number", "prefijo": "$ "},
            {"key": "reclamo_aseguradora", "label": "Reclamo aseguradora presentado", "tipo": "boolean"},
            {"key": "oferta_aseguradora", "label": "Oferta aseguradora", "tipo": "number", "prefijo": "$ "},
        ],
    }

    CAMPOS_JUDICIAL = [
        {"key": "fuero", "label": "Fuero", "tipo": "combo",
         "opciones": ["Federal", "Nacional", "Provincial"]},
        {"key": "juzgado", "label": "Juzgado", "tipo": "text"},
        {"key": "secretaria", "label": "Secretaria", "tipo": "text"},
        {"key": "numero_expediente_judicial", "label": "N° Expediente", "tipo": "text"},
        {"key": "provincia", "label": "Provincia", "tipo": "text"},
        {"key": "instancia", "label": "Instancia", "tipo": "combo",
         "opciones": ["Primera instancia", "Camara", "CSJN"]},
        {"key": "monto_reclamado", "label": "Monto reclamado", "tipo": "number"},
        {"key": "etapa_procesal", "label": "Etapa procesal", "tipo": "combo",
         "opciones": ["Demanda presentada", "Traslado", "Contestacion", "Prueba",
                      "Alegatos", "Sentencia", "Ejecucion", "Cobro"]},
    ]

    # ── Override create/update para registrar historial de estados ──

    @classmethod
    def _is_notifiable_role_for_assignment(cls, username: str) -> bool:
        if not username:
            return False
        rows = db_local.find_all(
            "usuarios",
            where="username = ? AND (activo = 1) AND (eliminado = 0 OR eliminado IS NULL)",
            params=(username,),
            limit=1,
        )
        if not rows:
            return False
        return rows[0].get("rol", "") in {"abogado", "administrador"}

    @classmethod
    def _notify_assignment_targets(
        cls,
        expediente: dict,
        target_usernames: set[str],
        actor_username: str,
        motivo: str,
    ):
        from controllers.notificacion_controller import NotificacionController

        exp_id = expediente.get("_id", "")
        exp_num = expediente.get("id_expediente", "")
        tipo_tramite = expediente.get("tipo_tramite", "")
        for uname in target_usernames:
            if not uname or uname == actor_username:
                continue
            if not cls._is_notifiable_role_for_assignment(uname):
                continue
            mensaje = (
                f"Se te asigno la carpeta #{exp_num} ({tipo_tramite}). "
                f"Motivo: {motivo}."
            )
            NotificacionController.create_for_expediente_asignado(
                target_username=uname,
                mensaje=mensaje,
                id_referencia=exp_id,
            )

    @classmethod
    def create(cls, data: dict) -> dict:
        """Crear expediente y abrir el primer segmento de historial."""
        record = super().create(data)
        from core.auth import Session
        session = Session.get()
        actor_username = session.username if session.logged_in else ""
        try:
            from controllers.expediente_estado_controller import abrir_segmento
            usuario = session.username if session.logged_in else "sistema"
            abrir_segmento(
                id_expediente=record["_id"],
                estado=record.get("estado", "Activo"),
                responsable_username=record.get("responsable_username", ""),
                usuario=usuario,
                origen="manual",
            )
        except Exception:
            logger.warning("Error al crear segmento inicial de historial", exc_info=True)
        try:
            targets = {
                record.get("responsable_username", "") or "",
                record.get("responsable_secundario_username", "") or "",
            }
            cls._notify_assignment_targets(record, targets, actor_username, "Alta de carpeta")
        except Exception:
            logger.warning("Error al notificar asignacion de carpeta (create)", exc_info=True)
        return record

    @classmethod
    def update(cls, _id: str, data: dict) -> dict | None:
        """Actualizar expediente y rotar historial si cambio estado o responsable."""
        existing = db_local.find_by_id(cls.TABLE, _id)
        if not existing:
            return None

        result = super().update(_id, data)
        if not result:
            return result
        from core.auth import Session
        session = Session.get()
        actor_username = session.username if session.logged_in else ""

        try:
            old_estado = existing.get("estado", "")
            old_resp = existing.get("responsable_username", "")
            new_estado = data.get("estado", old_estado)
            new_resp = data.get("responsable_username", old_resp)

            if new_estado != old_estado or new_resp != old_resp:
                from controllers.expediente_estado_controller import rotar_segmento
                usuario = session.username if session.logged_in else "sistema"
                rotar_segmento(
                    id_expediente=_id,
                    nuevo_estado=new_estado,
                    nuevo_responsable=new_resp,
                    usuario=usuario,
                    origen="manual",
                )
        except Exception:
            logger.warning("Error al rotar segmento de historial", exc_info=True)

        try:
            old_resp = existing.get("responsable_username", "") or ""
            old_resp2 = existing.get("responsable_secundario_username", "") or ""
            new_resp = result.get("responsable_username", "") or ""
            new_resp2 = result.get("responsable_secundario_username", "") or ""
            targets: set[str] = set()
            if new_resp and new_resp != old_resp:
                targets.add(new_resp)
            if new_resp2 and new_resp2 != old_resp2:
                targets.add(new_resp2)
            if targets:
                cls._notify_assignment_targets(
                    result, targets, actor_username, "Cambio de responsable"
                )
        except Exception:
            logger.warning("Error al notificar asignacion de carpeta (update)", exc_info=True)

        return result

    # ── Auto-archivado ──

    @classmethod
    def auto_archivar_cerrados(cls, dias: int = 30) -> int:
        """Pasa a Archivado los expedientes Cerrados con fecha_cierre mas antigua que `dias`.

        Retorna la cantidad de expedientes archivados.
        """
        fecha_limite = (date.today() - timedelta(days=dias)).isoformat()
        conn = db_local.get_connection()
        rows = conn.execute(
            "SELECT _id FROM expedientes "
            "WHERE estado = 'Cerrado' "
            "AND fecha_cierre IS NOT NULL AND fecha_cierre != '' "
            "AND fecha_cierre <= ?",
            (fecha_limite,)
        ).fetchall()
        conn.close()

        count = 0
        for r in rows:
            try:
                cls.update(r[0], {"estado": "Archivado"})
                count += 1
            except Exception:
                logger.warning("Error al auto-archivar expediente %s", r[0], exc_info=True)

        if count:
            logger.info("Auto-archivado: %d expedientes pasados a Archivado", count)
        return count

    @classmethod
    def search_expedientes(cls, text: str) -> list[dict]:
        return cls.search(text, [
            "id_expediente", "tipo_tramite", "rama", "subtipo",
            "estado", "responsable", "numero_expediente_anses", "observaciones"
        ])

    @classmethod
    def get_by_cliente(cls, id_cliente: str, limit: int = 0) -> list[dict]:
        return cls.get_all(where="id_cliente = ?", params=(id_cliente,),
                           order_by="fecha_apertura DESC", limit=limit)

    @classmethod
    def count_by_cliente(cls, id_cliente: str) -> int:
        return db_local.count("expedientes", "id_cliente = ?", (id_cliente,))

    @classmethod
    def get_scoped(cls, where: str = "", params: tuple = (),
                   order_by: str = "", limit: int = 0,
                   campo_responsable: str = "responsable_username",
                   campo_secundario: str = "responsable_secundario_username") -> list[dict]:
        """Override: expedientes tiene dos campos de responsable."""
        return super().get_scoped(
            where=where, params=params, order_by=order_by, limit=limit,
            campo_responsable=campo_responsable,
            campo_secundario=campo_secundario,
        )

    @classmethod
    def get_scoped_with_cliente(cls, where: str = "", params: tuple = (),
                                order_by: str = "", limit: int = 0) -> list[dict]:
        """get_scoped + LEFT JOIN clientes para traer numero_carpeta en una sola query."""
        from core.auth import Session
        from core.permissions import scope_where
        session = Session.get()
        sw, sp = scope_where(
            session.rol, session.username,
            "e.responsable_username", "e.responsable_secundario_username",
            modulo="expedientes",
        )
        sql = (
            "SELECT e.*, c.numero_carpeta AS numero_carpeta_cliente, "
            "c.nombre_completo AS cli_nombre, c.dni AS cli_dni, c.cuil AS cli_cuil "
            "FROM expedientes e "
            "LEFT JOIN clientes c ON c._id = e.id_cliente"
        )
        all_params: tuple = ()
        conditions: list[str] = []
        if where:
            conditions.append(f"({where})")
            all_params += params
        if sw:
            conditions.append(f"({sw})")
            all_params += sp
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit:
            sql += f" LIMIT {limit}"
        conn = db_local.get_connection()
        rows = conn.execute(sql, all_params).fetchall()
        conn.close()
        return db_local.rows_to_list(rows)

    @classmethod
    def _count_distinct_expedientes_in_table(
        cls,
        table: str,
        expediente_ids: list[str],
        extra_where: str,
        extra_params: tuple = (),
    ) -> int:
        """Cuenta expedientes distintos en una tabla relacionada, por lotes."""
        ids = [eid for eid in expediente_ids if eid]
        if not ids:
            return 0

        total_ids: set[str] = set()
        chunk_size = 900  # Evita limite de placeholders de SQLite.
        conn = db_local.get_connection()
        try:
            for i in range(0, len(ids), chunk_size):
                chunk = ids[i:i + chunk_size]
                placeholders = ",".join(["?"] * len(chunk))
                sql = (
                    f"SELECT DISTINCT id_expediente FROM {table} "
                    f"WHERE id_expediente IN ({placeholders}) AND {extra_where}"
                )
                rows = conn.execute(sql, tuple(chunk) + extra_params).fetchall()
                total_ids.update(r[0] for r in rows if r and r[0])
        finally:
            conn.close()
        return len(total_ids)

    @classmethod
    def get_metricas_relacionadas(
        cls,
        expediente_ids: list[str],
        dias_urgencia: int = 3,
        dias_semana: int = 7,
    ) -> dict[str, int]:
        """Retorna métricas de pendientes/urgentes/semana para carpetas dadas."""
        if not expediente_ids:
            return {"urgentes": 0, "semana": 0, "pendientes": 0}

        hoy = date.today().isoformat()
        limite_urgencia = (date.today() + timedelta(days=max(1, dias_urgencia))).isoformat()
        limite_semana = (date.today() + timedelta(days=max(1, dias_semana))).isoformat()

        pendientes = cls._count_distinct_expedientes_in_table(
            table="tareas",
            expediente_ids=expediente_ids,
            extra_where="estado IN ('Pendiente','En curso','En espera')",
        )
        urgentes = cls._count_distinct_expedientes_in_table(
            table="tareas",
            expediente_ids=expediente_ids,
            extra_where=(
                "estado IN ('Pendiente','En curso','En espera') "
                "AND fecha_vencimiento IS NOT NULL AND fecha_vencimiento != '' "
                "AND fecha_vencimiento <= ?"
            ),
            extra_params=(limite_urgencia,),
        )
        semana = cls._count_distinct_expedientes_in_table(
            table="turnos",
            expediente_ids=expediente_ids,
            extra_where=(
                "estado IN ('Pendiente','Confirmado') "
                "AND fecha_turno IS NOT NULL AND fecha_turno != '' "
                "AND fecha_turno >= ? AND fecha_turno <= ?"
            ),
            extra_params=(hoy, limite_semana),
        )
        return {"urgentes": urgentes, "semana": semana, "pendientes": pendientes}

    @classmethod
    def search_scoped_with_cliente(cls, text: str = "", where: str = "",
                                   params: tuple = (), order_by: str = "",
                                   limit: int = 50) -> list[dict]:
        """get_scoped + LEFT JOIN clientes con busqueda opcional por texto.

        Trae nombre_completo, dni y numero_carpeta del cliente en la misma
        query (evita N+1).
        El parametro 'text' busca en id_expediente, tipo_tramite,
        numero_expediente_anses, responsable, nombre_completo, dni y
        numero_carpeta del cliente.
        Los campos de WHERE deben usar prefijo 'e.' para expedientes.
        """
        from core.auth import Session
        from core.permissions import scope_where
        session = Session.get()
        sw, sp = scope_where(
            session.rol, session.username,
            "e.responsable_username", "e.responsable_secundario_username",
            modulo="expedientes",
        )
        sql = (
            "SELECT e.*, c.nombre_completo AS cli_nombre, c.dni AS cli_dni, c.cuil AS cli_cuil, "
            "c.numero_carpeta AS numero_carpeta_cliente "
            "FROM expedientes e "
            "LEFT JOIN clientes c ON c._id = e.id_cliente"
        )
        all_params: tuple = ()
        conditions: list[str] = []
        if where:
            conditions.append(f"({where})")
            all_params += params
        if sw:
            conditions.append(f"({sw})")
            all_params += sp
        if text.strip():
            text_param = f"%{text.strip()}%"
            search_cond = (
                "(CAST(e.id_expediente AS TEXT) LIKE ?"
                " OR e.tipo_tramite LIKE ?"
                " OR e.rama LIKE ?"
                " OR e.subtipo LIKE ?"
                " OR e.numero_expediente_anses LIKE ?"
                " OR e.responsable LIKE ?"
                " OR c.nombre_completo LIKE ?"
                " OR c.dni LIKE ?"
                " OR c.cuil LIKE ?"
                " OR c.numero_carpeta LIKE ?)"
            )
            conditions.append(search_cond)
            all_params += (text_param,) * 10
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit:
            sql += f" LIMIT {limit}"
        conn = db_local.get_connection()
        rows = conn.execute(sql, all_params).fetchall()
        conn.close()
        return db_local.rows_to_list(rows)

    @classmethod
    def tiene_tarea_activa(cls, expediente_id: str) -> bool:
        """Verifica si el expediente tiene al menos una tarea activa."""
        count = db_local.count(
            "tareas",
            "id_expediente = ? AND estado IN ('Pendiente','En curso','En espera')",
            (expediente_id,)
        )
        return count > 0

    @classmethod
    def get_sin_tarea_activa(cls) -> list[dict]:
        """Retorna expedientes activos que no tienen ninguna tarea activa."""
        conn = db_local.get_connection()
        rows = conn.execute("""
            SELECT e.* FROM expedientes e
            WHERE e.estado NOT IN ('Cerrado','Archivado')
            AND NOT EXISTS (
                SELECT 1 FROM tareas t
                WHERE t.id_expediente = e._id
                AND t.estado IN ('Pendiente','En curso','En espera')
            )
            ORDER BY e.fecha_apertura DESC
        """).fetchall()
        conn.close()
        return db_local.rows_to_list(rows)

    @classmethod
    def cerrar(cls, _id: str, resultado: str, fecha_cierre: str) -> dict | None:
        """Cierra formalmente un expediente con resultado y fecha."""
        return cls.update(_id, {
            "estado": "Cerrado",
            "resultado": resultado,
            "fecha_cierre": fecha_cierre,
        })
