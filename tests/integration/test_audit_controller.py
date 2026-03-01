"""Tests de integracion para seguimiento de tareas en auditoria."""
import json
from datetime import datetime, timedelta, timezone

from core import db_local
from controllers.audit_controller import AuditController
from controllers.notificacion_controller import NotificacionController


def _insert_user(username: str, rol: str):
    db_local.insert(
        "usuarios",
        {
            "_id": f"user-{username}",
            "username": username,
            "password_hash": "hash",
            "nombre_completo": username,
            "email": f"{username}@test.local",
            "rol": rol,
            "activo": 1,
            "eliminado": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "version": 1,
            "sync_status": "synced",
            "created_by_machine": "test-machine",
        },
    )


def _insert_task(_id: str, responsable: str, estado: str, id_tarea: int = 1):
    db_local.insert(
        "tareas",
        {
            "_id": _id,
            "id_tarea": id_tarea,
            "id_expediente": "exp-1",
            "tipo_accion": "Seguimiento expediente",
            "descripcion": f"Tarea {_id}",
            "responsable": responsable.upper(),
            "responsable_username": responsable,
            "fecha_inicio": "2026-01-01",
            "fecha_vencimiento": "2026-01-10",
            "estado": estado,
            "version": 1,
            "sync_status": "synced",
            "created_by_machine": "test-machine",
        },
    )


class TestAuditTaskTracking:
    def test_get_responsables_tareas_asignadas(self):
        _insert_task("task-r1", "abogado1", "Pendiente", id_tarea=11)
        _insert_task("task-r2", "abogado2", "Pendiente", id_tarea=12)
        NotificacionController.create_for_tarea_asignada("abogado1", "Tarea 1", id_referencia="task-r1")
        NotificacionController.create_for_tarea_asignada("abogado2", "Tarea 2", id_referencia="task-r2")

        users = AuditController.get_responsables_tareas_asignadas()
        assert "abogado1" in users
        assert "abogado2" in users

    def test_get_seguimiento_tareas_informa_lectura_y_cumplimiento(self):
        _insert_task("task-seg-1", "abogado1", "Cumplida", id_tarea=21)
        notif = NotificacionController.create_for_tarea_asignada(
            "abogado1", "Asignada", id_referencia="task-seg-1"
        )
        NotificacionController.mark_read(notif["_id"])

        db_local.insert(
            "audit_log",
            {
                "_id": "audit-1",
                "usuario": "admin",
                "rol": "administrador",
                "accion": "update",
                "coleccion": "tareas",
                "documento_id": "task-seg-1",
                "datos_anteriores": json.dumps({"estado": "En curso"}),
                "datos_nuevos": json.dumps({"estado": "Cumplida"}),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sync_status": "synced",
                "created_by_machine": "test-machine",
            },
        )

        rows = AuditController.get_seguimiento_tareas(responsable="abogado1")
        assert len(rows) == 1
        row = rows[0]
        assert row["id_tarea"] == 21
        assert row["leida"] is True
        assert row["fecha_lectura"] != ""
        assert row["estado_actual"] == "Cumplida"
        assert row["fecha_cumplimiento"] != ""

    def test_get_seguimiento_tareas_calcula_dias_sin_leer(self):
        _insert_task("task-seg-2", "abogado1", "Pendiente", id_tarea=22)
        notif = NotificacionController.create_for_tarea_asignada(
            "abogado1", "Asignada", id_referencia="task-seg-2"
        )
        old_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        db_local.update("notificaciones", notif["_id"], {"created_at": old_date})

        rows = AuditController.get_seguimiento_tareas(responsable="abogado1", estado="Pendiente")
        assert len(rows) == 1
        assert rows[0]["leida"] is False
        assert rows[0]["dias_sin_leer"] >= 5

    def test_incluye_tareas_de_administrador_sin_notificacion(self):
        _insert_user("admin1", "administrador")
        _insert_task("task-admin-1", "admin1", "Pendiente", id_tarea=31)

        rows = AuditController.get_seguimiento_tareas(responsable="admin1")
        assert len(rows) == 1
        assert rows[0]["asignada_a"] == "admin1"
        assert rows[0]["id_tarea"] == 31
        assert rows[0]["leida"] is False

    def test_responsables_incluye_administrador_sin_notificacion(self):
        _insert_user("admin2", "administrador")
        _insert_task("task-admin-2", "admin2", "Pendiente", id_tarea=32)

        users = AuditController.get_responsables_tareas_asignadas()
        assert "admin2" in users
