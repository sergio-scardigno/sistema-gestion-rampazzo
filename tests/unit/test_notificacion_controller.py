"""Tests unitarios para controlador de notificaciones."""
from datetime import datetime, timedelta

from core import db_local
from controllers.notificacion_controller import NotificacionController


def _insert_task(_id: str, username: str, estado: str, vencimiento: str):
    db_local.insert(
        "tareas",
        {
            "_id": _id,
            "id_tarea": 1,
            "id_expediente": "exp-1",
            "tipo_accion": "Seguimiento expediente",
            "descripcion": f"Tarea {_id}",
            "responsable": username.upper(),
            "responsable_username": username,
            "fecha_inicio": datetime.now().strftime("%Y-%m-%d"),
            "fecha_vencimiento": vencimiento,
            "estado": estado,
            "version": 1,
            "sync_status": "synced",
            "created_by_machine": "test-machine",
        },
    )


class TestNotificationReadVsResolved:
    def test_mark_read_does_not_remove_active_notification(self):
        created = NotificacionController.create_for_tarea_asignada(
            "abogado1", "Tarea asignada", id_referencia="t1"
        )
        NotificacionController.mark_read(created["_id"])

        active = NotificacionController.get_active_for_user("abogado1", limit=10)
        unread = NotificacionController.get_unread_for_user("abogado1", limit=10)
        assert any(n["_id"] == created["_id"] for n in active)
        assert all(n["_id"] != created["_id"] for n in unread)

    def test_resolve_for_tarea_hides_from_active(self):
        NotificacionController.create_for_tarea_asignada(
            "abogado1", "Tarea asignada", id_referencia="t2"
        )
        NotificacionController.resolve_for_tarea("t2", resolved_by_status=True)
        active = NotificacionController.get_active_for_user("abogado1", limit=10)
        assert all(n.get("id_referencia") != "t2" for n in active)

    def test_upsert_tarea_asignada_preserva_leida_y_fecha_lectura(self):
        created = NotificacionController.create_for_tarea_asignada(
            "abogado1", "Asignacion inicial", id_referencia="t-upsert-1"
        )
        NotificacionController.mark_read(created["_id"])
        read_state = db_local.find_by_id("notificaciones", created["_id"])
        prev_updated_at = read_state.get("updated_at", "")

        refreshed = NotificacionController.create_for_tarea_asignada(
            "abogado1", "Asignacion refrescada", id_referencia="t-upsert-1"
        )
        assert refreshed["_id"] == created["_id"]

        after = db_local.find_by_id("notificaciones", created["_id"])
        assert int(after.get("leida", 0) or 0) == 1
        assert after.get("updated_at", "") == prev_updated_at


class TestNotificationTaskSync:
    def test_sync_creates_assigned_and_due_soon_alerts(self):
        today = datetime.now().strftime("%Y-%m-%d")
        soon = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        _insert_task("task-open-1", "abogado1", "Pendiente", soon)
        _insert_task("task-open-2", "abogado1", "En curso", today)

        NotificacionController.sync_task_alerts_for_user("abogado1", due_days=30)
        active = NotificacionController.get_active_for_user("abogado1", limit=50)

        tipos = {n.get("tipo") for n in active}
        refs = {n.get("id_referencia") for n in active}
        assert "tarea_asignada" in tipos
        assert "tarea_proxima_vencer" in tipos
        assert "task-open-1" in refs

    def test_sync_resolves_when_task_is_closed(self):
        due = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        _insert_task("task-close-1", "abogado1", "Pendiente", due)
        NotificacionController.sync_task_alerts_for_user("abogado1", due_days=30)

        db_local.update(
            "tareas",
            "task-close-1",
            {"estado": "Cumplida", "sync_status": "pending", "version": 2},
        )
        NotificacionController.sync_task_alerts_for_user("abogado1", due_days=30)
        active = NotificacionController.get_active_for_user("abogado1", limit=50)
        assert all(n.get("id_referencia") != "task-close-1" for n in active)


class TestExpedienteNotification:
    def test_create_for_expediente_asignado_upsert(self):
        first = NotificacionController.create_for_expediente_asignado(
            "abogado1",
            "Se te asigno la carpeta #10 (Jubilacion). Motivo: Alta de carpeta.",
            id_referencia="exp-1",
        )
        second = NotificacionController.create_for_expediente_asignado(
            "abogado1",
            "Se te asigno la carpeta #10 (Jubilacion). Motivo: Cambio de responsable.",
            id_referencia="exp-1",
        )
        assert first["_id"] == second["_id"]

        active = NotificacionController.get_active_for_user("abogado1", limit=10)
        assert len([n for n in active if n.get("tipo") == "expediente_asignado"]) == 1
        assert any("Cambio de responsable" in n.get("mensaje", "") for n in active)


class TestDismissNotification:
    def test_dismiss_hides_from_active(self):
        created = NotificacionController.create_for_expediente_etapa_encargado(
            "abogado1",
            "Cambio de etapa en carpeta",
            id_referencia="exp-dismiss-1",
        )
        assert NotificacionController.dismiss_notification(created["_id"], "abogado1")
        active = NotificacionController.get_active_for_user("abogado1", limit=20)
        assert all(n["_id"] != created["_id"] for n in active)

    def test_dismiss_wrong_user_returns_false(self):
        created = NotificacionController.create_for_tarea_asignada(
            "abogado1", "Tarea", id_referencia="t-other"
        )
        assert not NotificacionController.dismiss_notification(created["_id"], "otro")

    def test_upsert_does_not_recreate_user_dismissed_row(self):
        created = NotificacionController.create_for_tarea_asignada(
            "abogado1", "Asignacion", id_referencia="t-dismiss-upsert"
        )
        assert NotificacionController.dismiss_notification(created["_id"], "abogado1")
        again = NotificacionController.create_for_tarea_asignada(
            "abogado1", "Asignacion nueva", id_referencia="t-dismiss-upsert"
        )
        assert again["_id"] == created["_id"]
        active = NotificacionController.get_active_for_user("abogado1", limit=20)
        assert all(n.get("id_referencia") != "t-dismiss-upsert" for n in active)

    def test_dismiss_by_type_and_ref(self):
        NotificacionController.create_for_recordatorio_expediente(
            "abogado1",
            "Recordatorio",
            id_referencia="exp-rec-1",
        )
        dismissed = NotificacionController.dismiss_by_type_and_ref(
            "abogado1", "recordatorio_expediente", "exp-rec-1"
        )
        assert dismissed >= 1
        active = NotificacionController.get_active_for_user("abogado1", limit=20)
        assert all(row.get("id_referencia") != "exp-rec-1" for row in active)
