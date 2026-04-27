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
    ETAPAS = [
        {"codigo": "para_citar_o_videollamada", "titulo": "Para citar o videollamada", "color": "#f4b400", "instruccion_corta": "Coordinar contacto inicial y agenda."},
        {"codigo": "para_analizar", "titulo": "Para analizar", "color": "#ff9800", "instruccion_corta": "Analizar el caso y documentación."},
        {"codigo": "en_espera_condicion", "titulo": "En espera / Aguardando condición", "color": "#9e9e9e", "instruccion_corta": "Registrar hitos y recordatorios (ej. fecha de jubilación); revisar cuando venza el plazo."},
        {"codigo": "para_citar", "titulo": "Para citar", "color": "#ffd54f", "instruccion_corta": "Citar al cliente o parte involucrada."},
        {"codigo": "pendiente_turno", "titulo": "Pendiente de Turno", "color": "#8bc34a", "instruccion_corta": "Gestionar solicitud y fecha de turno."},
        {"codigo": "turno", "titulo": "Turno", "color": "#4caf50", "instruccion_corta": "Preparar y asistir al turno asignado."},
        {"codigo": "enviada_iniciar", "titulo": "Enviada para Iniciar", "color": "#26c6da", "instruccion_corta": "Enviar para comienzo formal del trámite."},
        {"codigo": "iniciada_virtual", "titulo": "INICIADA - Virtual", "color": "#00acc1", "instruccion_corta": "Carpeta INICIADA - Modalidad Virtual. Gestionar acciones de trámite iniciado."},
        {"codigo": "iniciada_presencial", "titulo": "INICIADA - Presencial", "color": "#29b6f6", "instruccion_corta": "Carpeta INICIADA - Modalidad Presencial. Gestionar acciones de trámite iniciado."},
        {"codigo": "req_analizar", "titulo": "Requerimientos - Analizar", "color": "#ab47bc", "instruccion_corta": "Carpeta NO INICIADA. Resolver requerimiento de análisis antes de reiniciar."},
        {"codigo": "req_migraciones", "titulo": "Requerimientos - Migraciones", "color": "#7e57c2", "instruccion_corta": "Carpeta NO INICIADA. Resolver requerimiento de migraciones antes de reiniciar."},
        {"codigo": "req_citar", "titulo": "Requerimientos - Citar", "color": "#5c6bc0", "instruccion_corta": "Carpeta NO INICIADA. Resolver requerimiento de citación antes de reiniciar."},
        {"codigo": "citado_anses", "titulo": "Citado por ANSES", "color": "#42a5f5", "instruccion_corta": "ANSES citó personalmente. Preparar gestión; resultado pendiente (Favorable/Desfavorable)."},
        {"codigo": "favorable", "titulo": "Favorable", "color": "#2e7d32", "instruccion_corta": "Registrar resolución favorable."},
        {"codigo": "desfavorable", "titulo": "Desfavorable", "color": "#c62828", "instruccion_corta": "Registrar resolución desfavorable."},
        {"codigo": "enviar_notificarse", "titulo": "Enviar a notificarse", "color": "#78909c", "instruccion_corta": "Enviar para notificación final."},
    ]
    PRIORIDADES = ["Alta", "Normal", "Baja"]
    MODALIDADES = ["Presencial", "Virtual"]
    RAMAS_CON_MODALIDAD = ["Previsional"]

    ETAPAS_NO_INICIADA = frozenset({"req_analizar", "req_migraciones", "req_citar"})
    ETAPAS_INICIADA = frozenset({"iniciada_virtual", "iniciada_presencial"})
    ETAPAS_RESULTADO = frozenset({"favorable", "desfavorable"})

    @classmethod
    def etapa_por_codigo(cls, codigo: str) -> dict:
        for etapa in cls.ETAPAS:
            if etapa["codigo"] == codigo:
                return etapa
        return cls.ETAPAS[0]

    @classmethod
    def clasificacion_etapa(cls, codigo: str) -> dict:
        """Clasificación de etapa para UI (No iniciada / Iniciada / ANSES / Resultado).

        Retorna dict con:
        - mostrar: si conviene mostrar el bloque de clasificación
        - categoria: clave para estilo (no_iniciada, iniciada, citado_anses, resultado_favorable, resultado_desfavorable)
        - texto: mensaje para el usuario
        """
        c = (codigo or "").strip()
        if c in cls.ETAPAS_NO_INICIADA:
            motivos = {
                "req_analizar": "Requerimiento de análisis",
                "req_migraciones": "Requerimiento de migraciones",
                "req_citar": "Requerimiento de citación",
            }
            return {
                "mostrar": True,
                "categoria": "no_iniciada",
                "texto": f"Carpeta NO INICIADA — Motivo: {motivos.get(c, c)}.",
            }
        if c == "iniciada_virtual":
            return {
                "mostrar": True,
                "categoria": "iniciada",
                "texto": "Carpeta INICIADA — Modalidad: Virtual.",
            }
        if c == "iniciada_presencial":
            return {
                "mostrar": True,
                "categoria": "iniciada",
                "texto": "Carpeta INICIADA — Modalidad: Presencial.",
            }
        if c == "citado_anses":
            return {
                "mostrar": True,
                "categoria": "citado_anses",
                "texto": "Citado por ANSES — Pendiente de resultado (Favorable / Desfavorable).",
            }
        if c == "favorable":
            return {
                "mostrar": True,
                "categoria": "resultado_favorable",
                "texto": "Resultado: Favorable.",
            }
        if c == "desfavorable":
            return {
                "mostrar": True,
                "categoria": "resultado_desfavorable",
                "texto": "Resultado: Desfavorable.",
            }
        return {"mostrar": False, "categoria": "", "texto": ""}

    @classmethod
    def aplicar_colores_items_combo_etapas(cls, combo) -> None:
        """Fondo en el desplegable: rojizo (No iniciada / req), verde (Iniciada virtual/presencial)."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QBrush, QColor

        rojizo = QColor("#f0dede")
        verde = QColor("#e0f0e0")
        role = Qt.ItemDataRole.BackgroundRole
        for i in range(combo.count()):
            codigo = combo.itemData(i)
            if codigo is None:
                continue
            sc = str(codigo).strip() if codigo != "" else ""
            if not sc:
                combo.setItemData(i, None, role)
                continue
            if sc in cls.ETAPAS_NO_INICIADA:
                combo.setItemData(i, QBrush(rojizo), role)
            elif sc in cls.ETAPAS_INICIADA:
                combo.setItemData(i, QBrush(verde), role)
            else:
                combo.setItemData(i, None, role)

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

    # Referencias de expediente (datos_rama): lista en clave expedientes_referencia; legacy: una clave por tipo.
    TIPOS_EXPEDIENTE_REF = (
        ("anses", "ANSES"),
        ("ips", "IPS"),
        ("srt", "SRT"),
        ("judicial", "Judicial"),
    )
    LEGACY_KEY_TO_TIPO_EXPEDIENTE = {
        "expediente_anses": "anses",
        "expediente_ips": "ips",
        "expediente_srt": "srt",
        "expediente_judicial": "judicial",
    }
    KEYS_REFERENCIA_EXPEDIENTES = frozenset({"expedientes_referencia"})
    KEYS_REFERENCIA_EXPEDIENTES_LEGACY = frozenset(LEGACY_KEY_TO_TIPO_EXPEDIENTE.keys())
    KEYS_TODAS_REFERENCIAS_EXPEDIENTE_RAMA = (
        KEYS_REFERENCIA_EXPEDIENTES | KEYS_REFERENCIA_EXPEDIENTES_LEGACY
    )

    # ── Override create/update para registrar historial de estados ──

    _ROLES_PRINCIPAL_NOTIF = {"abogado", "analisis", "administrador"}
    _ROLES_SECUNDARIO_NOTIF = {"abogado", "analisis", "administrador", "secretaria"}

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
        return rows[0].get("rol", "") in cls._ROLES_PRINCIPAL_NOTIF

    @classmethod
    def _is_notifiable_for_secondary_assignment(cls, username: str) -> bool:
        """Roles que reciben notificacion como responsable secundario (incluye secretaria)."""
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
        return rows[0].get("rol", "") in cls._ROLES_SECUNDARIO_NOTIF

    @classmethod
    def _notify_assignment_targets(
        cls,
        expediente: dict,
        actor_username: str,
        motivo: str,
        *,
        primary_username: str = "",
        secondary_username: str = "",
    ):
        from controllers.notificacion_controller import NotificacionController

        exp_id = expediente.get("_id", "")
        exp_num = expediente.get("id_expediente", "")
        tipo_tramite = expediente.get("tipo_tramite", "")
        pu = (primary_username or "").strip()
        su = (secondary_username or "").strip()
        if pu and pu != actor_username and cls._is_notifiable_role_for_assignment(pu):
            mensaje = (
                f"Se te asigno como responsable principal la carpeta #{exp_num} ({tipo_tramite}). "
                f"Motivo: {motivo}."
            )
            NotificacionController.create_for_expediente_asignado(
                target_username=pu,
                mensaje=mensaje,
                id_referencia=exp_id,
            )
        if su and su != actor_username and cls._is_notifiable_for_secondary_assignment(su):
            mensaje = (
                f"Se te designo responsable secundario de la carpeta #{exp_num} ({tipo_tramite}). "
                f"Motivo: {motivo}."
            )
            NotificacionController.create_for_expediente_asignado(
                target_username=su,
                mensaje=mensaje,
                id_referencia=exp_id,
            )

    @classmethod
    def create(cls, data: dict) -> dict:
        """Crear expediente y abrir el primer segmento de historial."""
        data = dict(data)
        if not data.get("etapa_codigo"):
            data["etapa_codigo"] = "para_citar_o_videollamada"
        etapa = data.get("etapa_codigo", "para_citar_o_videollamada")
        if etapa == "iniciada_virtual":
            data["modalidad"] = "Virtual"
        elif etapa == "iniciada_presencial":
            data["modalidad"] = "Presencial"
        record = super().create(data)
        from core.auth import Session
        session = Session.get()
        actor_username = session.username if session.logged_in else ""
        try:
            from controllers.expediente_estado_controller import abrir_segmento
            usuario = session.username if session.logged_in else "sistema"
            abrir_segmento(
                id_expediente=record["_id"],
                estado=record.get("etapa_codigo", "para_citar_o_videollamada"),
                responsable_username=record.get("responsable_username", ""),
                encargado_username=record.get("responsable_secundario_username", ""),
                etapa_anterior="",
                usuario=usuario,
                origen="manual",
            )
        except Exception:
            logger.warning("Error al crear segmento inicial de historial", exc_info=True)
        try:
            from controllers.notificacion_controller import NotificacionController
            cls._notify_assignment_targets(
                record,
                actor_username,
                "Alta de carpeta",
                primary_username=record.get("responsable_username", "") or "",
                secondary_username=record.get("responsable_secundario_username", "") or "",
            )
            encargado = record.get("responsable_secundario_username", "") or ""
            if encargado and encargado != actor_username and cls._is_notifiable_for_secondary_assignment(encargado):
                etapa_meta = cls.etapa_por_codigo(record.get("etapa_codigo", ""))
                mensaje = (
                    f"Como responsable secundario, tenes a cargo la gestion de la etapa "
                    f"'{etapa_meta.get('titulo', '')}' en la carpeta #{record.get('id_expediente', '')}. "
                    f"{etapa_meta.get('instruccion_corta', '')}"
                )
                NotificacionController.create_for_expediente_etapa_encargado(
                    target_username=encargado,
                    mensaje=mensaje,
                    id_referencia=record.get("_id", ""),
                )
        except Exception:
            logger.warning("Error al notificar asignacion de carpeta (create)", exc_info=True)
        return record

    @classmethod
    def update(cls, _id: str, data: dict) -> dict | None:
        """Actualizar expediente y rotar historial si cambio estado o responsable."""
        existing = db_local.find_by_id(cls.TABLE, _id)
        if not existing:
            return None

        payload = dict(data)
        observacion_transicion = (payload.pop("observacion_transicion", None) or "").strip()
        if payload.get("etapa_codigo") == "iniciada_virtual":
            payload["modalidad"] = "Virtual"
        elif payload.get("etapa_codigo") == "iniciada_presencial":
            payload["modalidad"] = "Presencial"
        result = super().update(_id, payload)
        if not result:
            return result
        from core.auth import Session
        session = Session.get()
        actor_username = session.username if session.logged_in else ""

        old_etapa = existing.get("etapa_codigo", "para_citar_o_videollamada")
        old_resp = (existing.get("responsable_username", "") or "")
        old_encargado = (existing.get("responsable_secundario_username", "") or "")
        new_etapa = result.get("etapa_codigo", old_etapa)
        new_resp = (result.get("responsable_username", old_resp) or "")
        new_encargado = (result.get("responsable_secundario_username", old_encargado) or "")
        hubo_cambio_gestion = (
            new_etapa != old_etapa or new_resp != old_resp or new_encargado != old_encargado
        )

        try:
            if hubo_cambio_gestion:
                from controllers.expediente_estado_controller import rotar_segmento
                usuario = session.username if session.logged_in else "sistema"
                rotar_segmento(
                    id_expediente=_id,
                    nuevo_estado=new_etapa,
                    nuevo_responsable=new_resp,
                    nuevo_encargado=new_encargado,
                    observacion_transicion=observacion_transicion,
                    usuario=usuario,
                    origen="manual",
                )
        except Exception:
            logger.warning("Error al rotar segmento de historial", exc_info=True)

        try:
            if hubo_cambio_gestion:
                from controllers.notificacion_controller import NotificacionController
                etapa_meta = cls.etapa_por_codigo(new_etapa)
                exp_num = result.get("id_expediente", "")
                obs_show = observacion_transicion
                if len(obs_show) > 800:
                    obs_show = obs_show[:800] + "..."
                obs_suffix = f" Indicaciones: {obs_show}" if obs_show else ""

                targets = {new_resp, new_encargado} - {""}
                for uname in targets:
                    if uname == actor_username:
                        continue
                    if uname == new_encargado and new_encargado:
                        if not cls._is_notifiable_for_secondary_assignment(uname):
                            continue
                        secparts: list[str] = []
                        if new_encargado != old_encargado:
                            secparts.append(
                                f"Te designaron responsable secundario de la carpeta #{exp_num}."
                            )
                        if new_resp != old_resp:
                            secparts.append(
                                "La carpeta tiene nuevo responsable principal. "
                                "Seguis como responsable secundario."
                            )
                        if new_etapa != old_etapa:
                            secparts.append(
                                f"Etapa: {etapa_meta.get('titulo', '')}. "
                                f"{etapa_meta.get('instruccion_corta', '')} "
                                f"(gestion como responsable secundario)."
                            )
                        if not secparts:
                            continue
                        mensaje = " ".join(secparts) + obs_suffix
                    elif uname == new_resp and new_resp:
                        if not cls._is_notifiable_role_for_assignment(uname):
                            continue
                        prparts: list[str] = []
                        if new_resp != old_resp:
                            prparts.append(
                                f"Te asignaron como responsable principal la carpeta #{exp_num}."
                            )
                        if new_etapa != old_etapa:
                            prparts.append(
                                f"Etapa: {etapa_meta.get('titulo', '')}. "
                                f"{etapa_meta.get('instruccion_corta', '')}"
                            )
                        if not prparts:
                            continue
                        mensaje = " ".join(prparts) + obs_suffix
                    else:
                        continue
                    NotificacionController.create_for_expediente_etapa_encargado(
                        target_username=uname,
                        mensaje=mensaje,
                        id_referencia=result.get("_id", ""),
                    )
        except Exception:
            logger.warning("Error al notificar cambio de etapa o responsables (update)", exc_info=True)

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
            "estado", "etapa_codigo", "responsable", "numero_expediente_anses", "observaciones"
        ])

    @classmethod
    def get_pendientes_etapa_para_usuario(
        cls, username: str, etapa_codigo: str = "", limit: int = 200
    ) -> list[dict]:
        where = (
            "(e.responsable_username = ? OR COALESCE(NULLIF(TRIM(ee.responsable_secundario_username), ''), "
            "e.responsable_secundario_username) = ?) AND e.estado NOT IN ('Cerrado','Archivado')"
        )
        params: tuple = (username, username)
        if etapa_codigo:
            where += " AND e.etapa_codigo = ?"
            params += (etapa_codigo,)
        return cls.get_scoped_with_cliente(where=where, params=params, order_by="e.updated_at DESC", limit=limit)

    @classmethod
    def get_pendientes_citar_sin_cita(
        cls, username: str = "", limit: int = 50
    ) -> list[dict]:
        """Carpetas en etapa de citar sin cita Pendiente/Confirmada vinculada."""
        not_exists = (
            "NOT EXISTS (SELECT 1 FROM citas ci WHERE ci.id_expediente = e._id "
            "AND (ci.is_deleted IS NULL OR ci.is_deleted = 0) "
            "AND ci.estado IN ('Pendiente','Confirmada'))"
        )
        where_parts = [
            "e.etapa_codigo IN (?, ?)",
            "e.estado NOT IN ('Cerrado','Archivado')",
            not_exists,
        ]
        params: list = ["para_citar_o_videollamada", "para_citar"]
        if username:
            where_parts.append(
                "(e.responsable_username = ? OR COALESCE(NULLIF(TRIM(ee.responsable_secundario_username), ''), "
                "e.responsable_secundario_username) = ?)"
            )
            params.extend([username, username])
        where = " AND ".join(where_parts)
        return cls.get_scoped_with_cliente(
            where=where,
            params=tuple(params),
            order_by="e.updated_at DESC",
            limit=limit,
        )

    @classmethod
    def get_by_cliente(cls, id_cliente: str, limit: int = 0) -> list[dict]:
        return cls.get_all(where="id_cliente = ?", params=(id_cliente,),
                           order_by="fecha_apertura DESC", limit=limit)

    @classmethod
    def count_by_cliente(cls, id_cliente: str) -> int:
        return db_local.count("expedientes", "id_cliente = ?", (id_cliente,))

    _JOIN_ETAPA_ENCARGADO = (
        "LEFT JOIN expediente_etapa_responsables ee ON ee.id_expediente = e._id "
        "AND ee.etapa_codigo = e.etapa_codigo AND (ee.is_deleted IS NULL OR ee.is_deleted = 0)"
    )

    @staticmethod
    def _qualify_order_exp(order_by: str) -> str:
        if not (order_by or "").strip():
            return ""
        parts_out: list[str] = []
        for part in order_by.split(","):
            p = part.strip()
            if not p:
                continue
            tokens = p.split()
            col = tokens[0]
            if not col.startswith("e.") and "." not in col:
                col = f"e.{col}"
            tokens[0] = col
            parts_out.append(" ".join(tokens))
        return ", ".join(parts_out)

    @classmethod
    def _scope_expediente_efectivo_sql(cls, session) -> tuple[str, tuple]:
        """Visibilidad: principal o encargado secundario efectivo por etapa actual."""
        from core.permissions import es_scope_global_por_modulo
        if es_scope_global_por_modulo(session.rol, "expedientes"):
            return "", ()
        return (
            "(e.responsable_username = ? OR COALESCE(NULLIF(TRIM(ee.responsable_secundario_username), ''), "
            "e.responsable_secundario_username) = ?)",
            (session.username, session.username),
        )

    @classmethod
    def secundario_efectivo_username(cls, expediente: dict, overrides: dict[str, str] | None = None) -> str:
        """Encargado para la etapa actual: override por etapa o global en expediente."""
        etapa = (expediente or {}).get("etapa_codigo", "") or ""
        if overrides is not None and etapa in overrides:
            return (overrides.get(etapa) or "").strip()
        exp_id = (expediente or {}).get("_id", "")
        if exp_id and not overrides:
            rows = db_local.find_all(
                "expediente_etapa_responsables",
                where="id_expediente = ? AND etapa_codigo = ? AND (is_deleted IS NULL OR is_deleted = 0)",
                params=(exp_id, etapa),
                limit=1,
            )
            if rows and (rows[0].get("responsable_secundario_username") or "").strip():
                return rows[0]["responsable_secundario_username"].strip()
        return ((expediente or {}).get("responsable_secundario_username") or "").strip()

    @classmethod
    def get_scoped(cls, where: str = "", params: tuple = (),
                   order_by: str = "", limit: int = 0,
                   campo_responsable: str = "responsable_username",
                   campo_secundario: str = "responsable_secundario_username") -> list[dict]:
        """Visibilidad por responsable principal o encargado efectivo segun etapa (JOIN ee)."""
        del campo_responsable, campo_secundario  # compatibilidad con firma base
        from core.auth import Session
        session = Session.get()
        conditions: list[str] = ["(e.is_deleted IS NULL OR e.is_deleted = 0)"]
        all_params: list = []
        if where:
            conditions.append(f"({where})")
            all_params.extend(params)
        sw, sp = cls._scope_expediente_efectivo_sql(session)
        if sw:
            conditions.append(f"({sw})")
            all_params.extend(sp)
        sql = (
            "SELECT e.* FROM expedientes e "
            + cls._JOIN_ETAPA_ENCARGADO
            + " WHERE " + " AND ".join(conditions)
        )
        if order_by:
            sql += f" ORDER BY {cls._qualify_order_exp(order_by)}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        conn = db_local.get_connection()
        rows = conn.execute(sql, tuple(all_params)).fetchall()
        conn.close()
        result = db_local.rows_to_list(rows)
        for r in result:
            cls._deserialize(r)
        return result

    @classmethod
    def get_scoped_with_cliente(cls, where: str = "", params: tuple = (),
                                order_by: str = "", limit: int = 0) -> list[dict]:
        """get_scoped + LEFT JOIN clientes; encargado efectivo por etapa en el scope."""
        from core.auth import Session
        session = Session.get()
        conditions: list[str] = ["(e.is_deleted IS NULL OR e.is_deleted = 0)"]
        all_params: list = []
        if where:
            conditions.append(f"({where})")
            all_params.extend(params)
        sw, sp = cls._scope_expediente_efectivo_sql(session)
        if sw:
            conditions.append(f"({sw})")
            all_params.extend(sp)
        sql = (
            "SELECT e.*, c.numero_carpeta AS numero_carpeta_cliente, "
            "c.nombre_completo AS cli_nombre, c.dni AS cli_dni, c.cuil AS cli_cuil, "
            "c.telefonos AS cli_telefonos "
            "FROM expedientes e "
            "LEFT JOIN clientes c ON c._id = e.id_cliente "
            + cls._JOIN_ETAPA_ENCARGADO
            + " WHERE " + " AND ".join(conditions)
        )
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        conn = db_local.get_connection()
        rows = conn.execute(sql, tuple(all_params)).fetchall()
        conn.close()
        result = db_local.rows_to_list(rows)
        for r in result:
            cls._deserialize(r)
        return result

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
        session = Session.get()
        sw, sp = cls._scope_expediente_efectivo_sql(session)
        sql = (
            "SELECT e.*, c.nombre_completo AS cli_nombre, c.dni AS cli_dni, c.cuil AS cli_cuil, "
            "c.numero_carpeta AS numero_carpeta_cliente "
            "FROM expedientes e "
            "LEFT JOIN clientes c ON c._id = e.id_cliente "
            + cls._JOIN_ETAPA_ENCARGADO
        )
        all_params: list = []
        conditions: list[str] = ["(e.is_deleted IS NULL OR e.is_deleted = 0)"]
        if where:
            conditions.append(f"({where})")
            all_params.extend(params)
        if sw:
            conditions.append(f"({sw})")
            all_params.extend(sp)
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
        sql += " WHERE " + " AND ".join(conditions)
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit:
            sql += f" LIMIT {limit}"
        conn = db_local.get_connection()
        rows = conn.execute(sql, tuple(all_params)).fetchall()
        conn.close()
        result = db_local.rows_to_list(rows)
        for r in result:
            cls._deserialize(r)
        return result

    @classmethod
    def list_recordatorios_agenda_scoped(
        cls,
        fecha_desde: str,
        fecha_hasta: str,
        *,
        solo_pendientes_disparo: bool = True,
        limit: int = 400,
    ) -> list[dict]:
        """Plazos (recordatorios) en rango de fechas, con scope de expediente."""
        from core.auth import Session
        session = Session.get()
        conditions = [
            "(r.is_deleted IS NULL OR r.is_deleted = 0)",
            "(e.is_deleted IS NULL OR e.is_deleted = 0)",
            "r.fecha_disparo >= ?",
            "r.fecha_disparo <= ?",
            "e.estado NOT IN ('Cerrado','Archivado')",
        ]
        params: list = [fecha_desde[:10], fecha_hasta[:10]]
        if solo_pendientes_disparo:
            conditions.append("(r.disparado_en IS NULL OR r.disparado_en = '')")
        sw, sp = cls._scope_expediente_efectivo_sql(session)
        if sw:
            conditions.append(f"({sw})")
            params.extend(sp)
        sql = (
            "SELECT r.*, e.id_expediente AS exp_id_expediente, e.etapa_codigo AS exp_etapa_actual, "
            "e.responsable_username AS exp_responsable_username, "
            "e.responsable_secundario_username AS exp_responsable_secundario_username, "
            "c.nombre_completo AS cli_nombre, c.numero_carpeta AS numero_carpeta_cliente "
            "FROM expediente_recordatorios r "
            "JOIN expedientes e ON e._id = r.id_expediente "
            "LEFT JOIN clientes c ON c._id = e.id_cliente "
            + cls._JOIN_ETAPA_ENCARGADO
            + " WHERE " + " AND ".join(conditions)
            + " ORDER BY r.fecha_disparo ASC, r.es_critico DESC"
        )
        if limit:
            sql += f" LIMIT {int(limit)}"
        conn = db_local.get_connection()
        rows = conn.execute(sql, tuple(params)).fetchall()
        conn.close()
        return db_local.rows_to_list(rows)

    @classmethod
    def count_plazos_por_estado_scoped(cls, dias_atras: int = 30, dias_adelante: int = 60) -> dict[str, int]:
        """KPIs: criticos vencidos (pendientes), proximos 7 dias, hoy."""
        from core.auth import Session
        session = Session.get()
        d0 = date.today()
        hoy = d0.isoformat()
        desde = (d0 - timedelta(days=dias_atras)).isoformat()[:10]
        lim7 = (d0 + timedelta(days=7)).isoformat()[:10]

        sw, sp = cls._scope_expediente_efectivo_sql(session)
        scope_sql = f" AND ({sw})" if sw else ""
        pend_sql = (
            "(r.is_deleted IS NULL OR r.is_deleted = 0) AND (e.is_deleted IS NULL OR e.is_deleted = 0) "
            "AND (r.disparado_en IS NULL OR r.disparado_en = '') AND e.estado NOT IN ('Cerrado','Archivado')"
        )

        def _count(extra: str, xp: tuple) -> int:
            conn = db_local.get_connection()
            q = (
                "SELECT COUNT(*) FROM expediente_recordatorios r "
                "JOIN expedientes e ON e._id = r.id_expediente "
                + cls._JOIN_ETAPA_ENCARGADO
                + " WHERE " + pend_sql + extra + scope_sql
            )
            row = conn.execute(q, xp + sp).fetchone()
            conn.close()
            return int(row[0]) if row else 0

        crit_venc = _count(
            " AND r.es_critico = 1 AND r.fecha_disparo < ? AND r.fecha_disparo >= ?",
            (hoy, desde),
        )
        prox7 = _count(
            " AND r.fecha_disparo >= ? AND r.fecha_disparo <= ?",
            (hoy, lim7),
        )
        hoy_n = _count(" AND r.fecha_disparo = ?", (hoy,))
        return {
            "criticos_vencidos": crit_venc,
            "proximos_7": prox7,
            "hoy": hoy_n,
        }

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
