"""
Scheduler para tareas periodicas: sync, alertas, backups, reportes.

Automatizaciones del pliego tecnico:
  - Sincronizacion periodica (cada N segundos)
  - Backup diario de la BD local
  - Alertas de tareas vencidas
  - Recordatorios de turnos proximos
  - Limpieza de backups antiguos
"""
import shutil
import logging
from datetime import datetime, date, timedelta
from pathlib import Path

from apscheduler.schedulers.qt import QtScheduler
from config import SYNC_INTERVAL_SECONDS, SQLITE_PATH, BACKUP_DIR, BACKUP_RETENTION_DAYS
from core import db_local

logger = logging.getLogger("scheduler")

_scheduler: QtScheduler | None = None


def get_scheduler() -> QtScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = QtScheduler()
    return _scheduler


def start_scheduler():
    sched = get_scheduler()
    if not sched.running:
        sched.start()


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None


# ── Backup diario ──

def backup_database():
    """Crea una copia de seguridad de la BD local con timestamp."""
    try:
        src = Path(SQLITE_PATH)
        if not src.exists():
            logger.warning("No se encontro la BD local para backup")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = BACKUP_DIR / f"local_backup_{timestamp}.db"
        shutil.copy2(str(src), str(dest))
        logger.info(f"Backup creado: {dest}")

        # Limpieza de backups antiguos
        cleanup_old_backups()
    except Exception:
        logger.exception("Error al crear backup")


def cleanup_old_backups():
    """Elimina backups mas antiguos que BACKUP_RETENTION_DAYS."""
    try:
        cutoff = datetime.now() - timedelta(days=BACKUP_RETENTION_DAYS)
        for f in BACKUP_DIR.glob("local_backup_*.db"):
            if f.stat().st_mtime < cutoff.timestamp():
                f.unlink()
                logger.info(f"Backup antiguo eliminado: {f.name}")
    except Exception:
        logger.exception("Error limpiando backups antiguos")


# ── Alertas de tareas vencidas ──

_alertas_pendientes: list[dict] = []


def check_tareas_vencidas():
    """Revisa tareas vencidas y genera alertas internas."""
    global _alertas_pendientes
    try:
        from controllers.tarea_controller import TareaController
        vencidas = TareaController.get_vencidas()
        _alertas_pendientes = []
        for t in vencidas:
            _alertas_pendientes.append({
                "tipo": "tarea_vencida",
                "mensaje": f"Tarea vencida: {t.get('descripcion', '')[:50]} – "
                           f"Vence: {t.get('fecha_vencimiento', '')} – "
                           f"Resp: {t.get('responsable', '')}",
                "id": t.get("_id", ""),
                "fecha_vencimiento": t.get("fecha_vencimiento", ""),
            })
        if _alertas_pendientes:
            logger.info(f"{len(_alertas_pendientes)} tareas vencidas detectadas")
    except Exception:
        logger.exception("Error al verificar tareas vencidas")


def get_alertas_pendientes() -> list[dict]:
    """Retorna las alertas pendientes generadas por el scheduler."""
    return list(_alertas_pendientes)


# ── Recordatorios de turnos proximos ──

_recordatorios_turnos: list[dict] = []


def check_turnos_proximos():
    """Revisa turnos de los proximos 30 dias y genera recordatorios."""
    global _recordatorios_turnos
    try:
        from controllers.turno_controller import TurnoController
        hoy = date.today().isoformat()
        limite = (date.today() + timedelta(days=30)).isoformat()
        from core import db_local
        turnos = db_local.find_all(
            "turnos",
            where="fecha_turno >= ? AND fecha_turno <= ? AND estado IN ('Pendiente','Confirmado')",
            params=(hoy, limite),
            order_by="fecha_turno ASC, hora_turno ASC",
        )
        _recordatorios_turnos = []
        for t in turnos:
            _recordatorios_turnos.append({
                "tipo": "turno_proximo",
                "mensaje": f"Turno {t.get('fecha_turno', '')} {t.get('hora_turno', '')} – "
                           f"{t.get('oficina_anses', '')} – {t.get('tipo_tramite', '')}",
                "id": t.get("_id", ""),
                "fecha_turno": t.get("fecha_turno", ""),
            })
        if _recordatorios_turnos:
            logger.info(f"{len(_recordatorios_turnos)} turnos proximos detectados")
    except Exception:
        logger.exception("Error al verificar turnos proximos")


def get_recordatorios_turnos() -> list[dict]:
    """Retorna los recordatorios de turnos proximos."""
    return list(_recordatorios_turnos)


# ── Carpetas sin tarea activa ──

_alertas_sin_tarea: list[dict] = []


def check_expedientes_sin_tarea():
    """Revisa carpetas activas sin tarea activa."""
    global _alertas_sin_tarea
    try:
        from controllers.expediente_controller import ExpedienteController
        sin_tarea = ExpedienteController.get_sin_tarea_activa()
        _alertas_sin_tarea = []
        for e in sin_tarea:
            _alertas_sin_tarea.append({
                "tipo": "expediente_sin_tarea",
                "mensaje": f"Carpeta sin tarea activa: "
                           f"{e.get('tipo_tramite', '')} – Resp: {e.get('responsable', '')}",
                "id": e.get("_id", ""),
            })
        if _alertas_sin_tarea:
            logger.info(f"{len(_alertas_sin_tarea)} carpetas sin tarea activa")
    except Exception:
        logger.exception("Error al verificar expedientes sin tarea")


def get_alertas_sin_tarea() -> list[dict]:
    return list(_alertas_sin_tarea)


# ── Auto-archivado de expedientes cerrados ──

def auto_archivar_expedientes():
    """Archiva automaticamente expedientes cerrados hace mas de 30 dias."""
    try:
        from controllers.expediente_controller import ExpedienteController
        count = ExpedienteController.auto_archivar_cerrados(dias=30)
        if count:
            logger.info("Auto-archivado: %d expedientes archivados", count)
    except Exception:
        logger.exception("Error en auto-archivado de expedientes")


def check_recordatorios_expedientes():
    """Dispara notificaciones por recordatorios de carpetas con escalamiento."""
    try:
        from controllers.notificacion_controller import NotificacionController
        from controllers.expediente_controller import ExpedienteController
        hoy = date.today().isoformat()
        hoy_dt = date.today()
        rows = db_local.find_all(
            "expediente_recordatorios",
            where=(
                "estado_plazo != 'resuelto' AND fecha_disparo <= ? "
                "AND (is_deleted IS NULL OR is_deleted = 0)"
            ),
            params=((hoy_dt + timedelta(days=2)).isoformat(),),
            order_by="fecha_disparo ASC",
            limit=200,
        )
        disparados = 0
        for rec in rows:
            exp = ExpedienteController.get_by_id(rec.get("id_expediente", ""))
            if not exp:
                continue
            fecha = (rec.get("fecha_disparo") or "")[:10]
            if len(fecha) != 10:
                continue
            fecha_dt = date.fromisoformat(fecha)
            delta = (fecha_dt - hoy_dt).days
            nivel = ""
            pref = ""
            if delta < 0:
                nivel = "vencido"
                pref = "[PLAZO VENCIDO] "
            elif delta == 0:
                nivel = "hoy"
                pref = "[PLAZO HOY] "
            elif delta <= 2:
                nivel = "previo"
                pref = "[PROXIMO VENCIMIENTO] "
            if not nivel:
                continue

            ya_nivel = (rec.get("ultimo_aviso_nivel") or "").strip()
            ya_fecha = (rec.get("ultimo_aviso_fecha") or "").strip()[:10]
            if ya_nivel == nivel and ya_fecha == hoy:
                continue

            target_manual = (rec.get("notificar_a_username", "") or "").strip()
            target_sec = (
                ExpedienteController.secundario_efectivo_username(exp)
                or (exp.get("responsable_secundario_username", "") or "").strip()
            )
            target_pri = (exp.get("responsable_username", "") or "").strip()
            target_main = target_manual or target_sec or target_pri
            targets: list[tuple[str, str]] = []
            if target_main:
                targets.append((target_main, "titular"))
            if target_sec and target_sec != target_main:
                targets.append((target_sec, "copia"))
            if target_pri and target_pri != target_main:
                targets.append((target_pri, "copia"))
            if not targets:
                continue

            exp_num = exp.get("id_expediente", "")
            base_msg = (
                f"{pref}Recordatorio de carpeta #{exp_num}: "
                f"{rec.get('titulo', 'Accion pendiente')}. {rec.get('mensaje', '')}".strip()
            )
            for uname, rol_dest in targets:
                msg = base_msg if rol_dest == "titular" else f"[COPIA] {base_msg}"
                NotificacionController.create_for_recordatorio_expediente(
                    target_username=uname,
                    mensaje=msg,
                    id_referencia=exp.get("_id", ""),
                    force_new=True,
                )
            rec_estado = "vencido" if delta < 0 else "activo"
            db_local.update(
                "expediente_recordatorios",
                rec["_id"],
                {
                    "disparado_en": datetime.now().isoformat(),
                    "estado_plazo": rec_estado,
                    "ultimo_aviso_nivel": nivel,
                    "ultimo_aviso_fecha": hoy,
                    "updated_at": datetime.now().isoformat(),
                    "version": int(rec.get("version", 1) or 1) + 1,
                    "sync_status": "pending",
                },
            )
            disparados += 1
        if disparados:
            logger.info("Recordatorios de expedientes disparados: %d", disparados)
    except Exception:
        logger.exception("Error al procesar recordatorios de expedientes")


# ── Configurar todos los jobs ──

def setup_all_jobs(sync_engine=None):
    """Configura todos los jobs del scheduler.
    Llamar una vez despues de start_scheduler()."""
    sched = get_scheduler()

    # Sync periodica
    if sync_engine:
        sched.add_job(sync_engine.sync, 'interval',
                      seconds=SYNC_INTERVAL_SECONDS,
                      id='sync_job', replace_existing=True)

    # Backup diario a las 02:00
    sched.add_job(backup_database, 'cron', hour=2, minute=0,
                  id='backup_job', replace_existing=True)

    # Alertas de tareas vencidas cada 30 min
    sched.add_job(check_tareas_vencidas, 'interval', minutes=30,
                  id='alertas_tareas_job', replace_existing=True)

    # Recordatorios de turnos cada 1 hora
    sched.add_job(check_turnos_proximos, 'interval', minutes=60,
                  id='recordatorios_turnos_job', replace_existing=True)

    # Expedientes sin tarea activa cada 2 horas
    sched.add_job(check_expedientes_sin_tarea, 'interval', hours=2,
                  id='expedientes_sin_tarea_job', replace_existing=True)

    # Auto-archivado de expedientes cerrados (1 vez al dia a las 03:00)
    sched.add_job(auto_archivar_expedientes, 'cron', hour=3, minute=0,
                  id='auto_archivar_job', replace_existing=True)

    # Recordatorios de expedientes (intervalico para no depender de hora fija)
    sched.add_job(check_recordatorios_expedientes, 'interval', minutes=45,
                  id='recordatorios_expedientes_job', replace_existing=True)

    # Ejecutar checks iniciales
    try:
        check_tareas_vencidas()
        check_turnos_proximos()
        check_expedientes_sin_tarea()
        check_recordatorios_expedientes()
    except Exception:
        logger.exception("Error en checks iniciales del scheduler")

    # Seed de historial de estados (solo inserta segmentos para expedientes sin historial)
    try:
        from controllers.expediente_estado_controller import seed_expedientes_sin_segmento
        seed_expedientes_sin_segmento()
    except Exception:
        logger.exception("Error en seed de historial de estados")

    # Ejecutar auto-archivado inicial
    try:
        auto_archivar_expedientes()
    except Exception:
        logger.exception("Error en auto-archivado inicial")
