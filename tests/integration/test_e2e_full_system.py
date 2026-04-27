"""Tests E2E de flujos completos del sistema."""

from datetime import date, timedelta

import pytest

from controllers.cliente_controller import ClienteController
from controllers.expediente_controller import ExpedienteController
from controllers.expediente_estado_controller import get_historial
from controllers.expediente_recordatorio_controller import ExpedienteRecordatorioController
from controllers.notificacion_controller import NotificacionController
from controllers.tarea_controller import TareaController
from core import db_local
from core.auth import Session
from utils import export as export_utils
from utils.migration.importer import import_records
from utils.system_bundle import export_system_bundle, import_system_bundle


def _set_session(monkeypatch, username: str, rol: str, nombre: str = ""):
    session = Session()
    session.usuario = {
        "_id": f"id-{username}",
        "username": username,
        "nombre_completo": nombre or username,
        "rol": rol,
        "activo": 1,
        "eliminado": 0,
    }
    monkeypatch.setattr(Session, "_instance", session)
    return session


def _seed_user(username: str, rol: str):
    db_local.insert(
        "usuarios",
        {
            "_id": f"user-{username}",
            "username": username,
            "password_hash": "x",
            "nombre_completo": username.upper(),
            "email": f"{username}@test.com",
            "rol": rol,
            "activo": 1,
            "eliminado": 0,
            "sync_status": "synced",
            "version": 1,
            "created_by_machine": "test-machine",
        },
    )


class TestE2EClienteToExpediente:
    def test_flujo_completo_alta_cliente_y_expediente(self, session_superusuario):
        cliente = ClienteController.create({"nombre_completo": "Cliente E2E", "dni": "30111222", "numero_carpeta": "9501"})
        expediente = ExpedienteController.create(
            {
                "id_cliente": cliente["_id"],
                "tipo_tramite": "Jubilacion",
                "responsable": "Principal",
                "responsable_username": "testsuper",
            }
        )
        historial = get_historial(expediente["_id"])

        assert expediente["id_cliente"] == cliente["_id"]
        assert expediente["etapa_codigo"] == "para_citar_o_videollamada"
        assert len(historial) == 1
        assert historial[0]["estado"] == "para_citar_o_videollamada"

    def test_cliente_con_multiples_expedientes(self, session_superusuario):
        cliente = ClienteController.create({"nombre_completo": "Cliente Multi", "dni": "30222333", "numero_carpeta": "9502"})
        for tipo in ("Jubilacion", "Pension", "RTI"):
            ExpedienteController.create({"id_cliente": cliente["_id"], "tipo_tramite": tipo})

        expedientes = ExpedienteController.get_by_cliente(cliente["_id"])
        assert len(expedientes) == 3

    def test_cerrar_expediente_con_tareas_pendientes_y_luego_sin_pendientes(self, session_superusuario):
        cliente = ClienteController.create({"nombre_completo": "Cliente Cierre", "dni": "30333444", "numero_carpeta": "9503"})
        exp = ExpedienteController.create({"id_cliente": cliente["_id"], "tipo_tramite": "Jubilacion"})
        TareaController.create(
            {
                "id_expediente": exp["_id"],
                "tipo_accion": "Seguimiento expediente",
                "estado": "Pendiente",
            }
        )
        assert ExpedienteController.tiene_tarea_activa(exp["_id"]) is True

        cerr = ExpedienteController.cerrar(exp["_id"], "Favorable", "2026-01-15")
        assert cerr["estado"] == "Cerrado"

        tareas = TareaController.get_by_expediente(exp["_id"])
        TareaController.update(tareas[0]["_id"], {"estado": "Cumplida"})
        assert ExpedienteController.tiene_tarea_activa(exp["_id"]) is False

    def test_busqueda_cliente_por_criterios(self, session_superusuario):
        ClienteController.create(
            {
                "nombre_completo": "Juana Busqueda",
                "dni": "30444555",
                "cuil": "27-30444555-9",
                "numero_carpeta": "9504",
                "email": "juana@test.com",
            }
        )
        assert len(ClienteController.search_clientes("Juana")) == 1
        assert len(ClienteController.search_clientes("30444555")) == 1
        assert len(ClienteController.search_clientes("9504")) == 1
        assert len(ClienteController.search_clientes("juana@test.com")) == 1


class TestE2EExpedienteEstadosMaquina:
    def test_ciclo_etapas_y_historial(self, session_superusuario):
        cli = ClienteController.create({"nombre_completo": "Cliente Etapas", "dni": "30555666", "numero_carpeta": "9505"})
        exp = ExpedienteController.create({"id_cliente": cli["_id"], "tipo_tramite": "Jubilacion"})
        for etapa in ("para_analizar", "pendiente_turno", "turno", "iniciada_virtual", "favorable"):
            ExpedienteController.update(exp["_id"], {"etapa_codigo": etapa})
        historial = get_historial(exp["_id"])

        assert historial[-1]["estado"] == "favorable"
        assert len(historial) == 6

    def test_cambio_responsable_rota_segmento(self, session_superusuario):
        _seed_user("abogado_dest", "abogado")
        cli = ClienteController.create({"nombre_completo": "Cliente Resp", "dni": "30666777", "numero_carpeta": "9506"})
        exp = ExpedienteController.create({"id_cliente": cli["_id"], "tipo_tramite": "Jubilacion", "responsable_username": "testsuper"})
        before = len(get_historial(exp["_id"]))
        ExpedienteController.update(exp["_id"], {"responsable_username": "abogado_dest"})
        after = len(get_historial(exp["_id"]))
        assert after == before + 1

    def test_auto_archivar_cerrados_antiguos(self, session_superusuario):
        cli = ClienteController.create({"nombre_completo": "Cliente Archivo", "dni": "30777888", "numero_carpeta": "9507"})
        old_date = (date.today() - timedelta(days=90)).isoformat()
        exp = ExpedienteController.create({"id_cliente": cli["_id"], "tipo_tramite": "Pension", "estado": "Cerrado", "fecha_cierre": old_date})
        archived = ExpedienteController.auto_archivar_cerrados(dias=30)
        refreshed = ExpedienteController.get_by_id(exp["_id"])
        assert archived >= 1
        assert refreshed["estado"] == "Archivado"

    @pytest.mark.parametrize("etapa", [e["codigo"] for e in ExpedienteController.ETAPAS])
    def test_todas_etapas_validas(self, session_superusuario, etapa):
        cli = ClienteController.create({"nombre_completo": f"Cliente {etapa}", "dni": "30888999", "numero_carpeta": str(9600 + len(etapa))})
        exp = ExpedienteController.create({"id_cliente": cli["_id"], "tipo_tramite": "RTI"})
        updated = ExpedienteController.update(exp["_id"], {"etapa_codigo": etapa})
        assert updated["etapa_codigo"] == etapa


class TestE2ETareasAsignacion:
    def test_flujo_tarea_hasta_cumplida_y_resolucion_notificacion(self, session_superusuario):
        _seed_user("abogado_tareas", "abogado")
        cli = ClienteController.create({"nombre_completo": "Cliente Tarea", "dni": "30999000", "numero_carpeta": "9510"})
        exp = ExpedienteController.create({"id_cliente": cli["_id"], "tipo_tramite": "Jubilacion"})
        tarea = TareaController.create(
            {
                "id_expediente": exp["_id"],
                "tipo_accion": "Turno ANSES",
                "descripcion": "Gestionar turno",
                "responsable": "Abogado Tareas",
                "responsable_username": "abogado_tareas",
                "estado": "Pendiente",
            }
        )
        NotificacionController.create_for_tarea_asignada("abogado_tareas", "Nueva tarea", tarea["_id"])
        TareaController.update(tarea["_id"], {"estado": "En curso"})
        TareaController.update(tarea["_id"], {"estado": "Cumplida"})
        active = NotificacionController.get_active_for_user("abogado_tareas", limit=20)
        assert all(n.get("id_referencia") != tarea["_id"] for n in active)

    def test_tarea_vencida_y_cancelada(self, session_superusuario):
        TareaController.create(
            {
                "id_expediente": "exp-venc",
                "tipo_accion": "Otro",
                "estado": "Pendiente",
                "fecha_vencimiento": "2020-01-01",
            }
        )
        c = TareaController.create(
            {
                "id_expediente": "exp-venc",
                "tipo_accion": "Otro",
                "estado": "Pendiente",
                "fecha_vencimiento": "2020-01-02",
            }
        )
        assert len(TareaController.get_vencidas()) >= 2
        TareaController.update(c["_id"], {"estado": "Cancelada"})
        ids = [t["_id"] for t in TareaController.get_vencidas()]
        assert c["_id"] not in ids

    def test_tareas_aisladas_por_expediente(self, session_superusuario):
        TareaController.create({"id_expediente": "exp-1", "tipo_accion": "Otro", "estado": "Pendiente"})
        TareaController.create({"id_expediente": "exp-2", "tipo_accion": "Otro", "estado": "Pendiente"})
        assert len(TareaController.get_by_expediente("exp-1")) == 1
        assert len(TareaController.get_by_expediente("exp-2")) == 1


class TestE2ERolePermissions:
    def test_secretaria_ve_todos_clientes_y_expedientes(self, monkeypatch, session_superusuario):
        c1 = ClienteController.create({"nombre_completo": "Cliente Sec1", "dni": "30000001", "numero_carpeta": "9520"})
        c2 = ClienteController.create({"nombre_completo": "Cliente Sec2", "dni": "30000002", "numero_carpeta": "9521"})
        ExpedienteController.create({"id_cliente": c1["_id"], "tipo_tramite": "Jubilacion", "responsable_username": "u1"})
        ExpedienteController.create({"id_cliente": c2["_id"], "tipo_tramite": "Pension", "responsable_username": "u2"})
        _set_session(monkeypatch, "testsec", "secretaria")
        assert len(ClienteController.get_scoped()) == 2
        assert len(ExpedienteController.get_scoped()) == 2

    def test_abogado_scope_expedientes_propios(self, monkeypatch, session_superusuario):
        cli = ClienteController.create({"nombre_completo": "Cliente Scope", "dni": "30000003", "numero_carpeta": "9522"})
        ExpedienteController.create({"id_cliente": cli["_id"], "tipo_tramite": "Jubilacion", "responsable_username": "abogado1"})
        ExpedienteController.create({"id_cliente": cli["_id"], "tipo_tramite": "Jubilacion", "responsable_username": "otro"})
        _set_session(monkeypatch, "abogado1", "abogado")
        rows = ExpedienteController.get_scoped()
        assert len(rows) == 1
        assert rows[0]["responsable_username"] == "abogado1"

    def test_admin_visor_y_administrador_scope_global(self, monkeypatch, session_superusuario):
        cli = ClienteController.create({"nombre_completo": "Cliente Admin", "dni": "30000004", "numero_carpeta": "9523"})
        ExpedienteController.create({"id_cliente": cli["_id"], "tipo_tramite": "RTI", "responsable_username": "x"})
        _set_session(monkeypatch, "av", "admin_visor")
        assert len(ExpedienteController.get_scoped()) == 1
        _set_session(monkeypatch, "ad", "administrador")
        assert len(ExpedienteController.get_scoped()) == 1


class TestE2EExportImportMigracion:
    def test_migracion_records_crea_clientes_y_expedientes(self, session_superusuario):
        records = [
            {"nombre_completo": "Mig Uno", "dni": "31111111", "cuil": "20-31111111-9", "id_carpeta": "9701", "tipo_tramite": "Jubilacion", "estado": "Activo"},
            {"nombre_completo": "Mig Dos", "dni": "32222222", "cuil": "20-32222222-9", "id_carpeta": "9702", "tipo_tramite": "Pension", "estado": "Activo"},
        ]
        result = import_records(records)
        assert result.clientes_created == 2
        assert result.expedientes_created == 2
        assert result.errors == []

    def test_migracion_cuil_duplicado_deduplica(self, session_superusuario):
        records = [
            {"nombre_completo": "Dup Uno", "dni": "33333331", "cuil": "20-33333333-9", "id_carpeta": "9710", "tipo_tramite": "Jubilacion"},
            {"nombre_completo": "Dup Dos", "dni": "33333332", "cuil": "20-33333333-9", "id_carpeta": "9711", "tipo_tramite": "Pension"},
        ]
        result = import_records(records)
        assert result.clientes_created == 1
        assert result.expedientes_created == 2

    def test_export_import_bundle_roundtrip(self, session_superusuario, tmp_path):
        cli = ClienteController.create({"nombre_completo": "Bundle Cli", "dni": "34444444", "numero_carpeta": "9720"})
        ExpedienteController.create({"id_cliente": cli["_id"], "tipo_tramite": "Jubilacion"})
        TareaController.create({"id_expediente": "exp-bundle", "tipo_accion": "Otro", "estado": "Pendiente"})
        zip_path = tmp_path / "bundle.zip"
        stats_export = export_system_bundle(str(zip_path))
        stats_import = import_system_bundle(str(zip_path))

        assert stats_export["total_rows"] >= 3
        assert stats_import["total_rows"] >= 3
        assert stats_import["new_db_path"]

    def test_export_analisis_clientes_y_carpetas(self, session_superusuario, tmp_path):
        cli = ClienteController.create({"nombre_completo": "Export Cli", "dni": "35555555", "numero_carpeta": "9730"})
        ExpedienteController.create({"id_cliente": cli["_id"], "tipo_tramite": "RTI"})
        clientes_csv = tmp_path / "clientes.csv"
        carpetas_csv = tmp_path / "carpetas.csv"
        export_utils.export_clientes_csv(str(clientes_csv))
        export_utils.export_carpetas_csv(str(carpetas_csv))
        assert clientes_csv.exists()
        assert carpetas_csv.exists()


class TestE2ERecordatoriosYNotificaciones:
    def test_recordatorio_genera_notificacion_manual(self, session_superusuario):
        _seed_user("notif_user", "abogado")
        cli = ClienteController.create({"nombre_completo": "Cli Notif", "dni": "36666666", "numero_carpeta": "9740"})
        exp = ExpedienteController.create({"id_cliente": cli["_id"], "tipo_tramite": "Jubilacion"})
        rec = ExpedienteRecordatorioController.create_for_expediente(
            exp["_id"],
            {
                "fecha_disparo": date.today().isoformat(),
                "titulo": "Recordatorio",
                "mensaje": "Llamar cliente",
                "notificar_a_username": "notif_user",
                "etapa_codigo": "para_analizar",
                "es_critico": 1,
            },
        )
        NotificacionController.create_for_recordatorio_expediente("notif_user", "Recordatorio activo", rec["_id"])
        active = NotificacionController.get_active_for_user("notif_user", limit=20)
        assert any(n.get("tipo") == "recordatorio_expediente" for n in active)

    def test_dismiss_no_recrea_notificacion(self, session_superusuario):
        NotificacionController.create_for_expediente_asignado("testsuper", "Asignacion", "exp-1")
        active = NotificacionController.get_active_for_user("testsuper", limit=20)
        notif = next(n for n in active if n.get("id_referencia") == "exp-1")
        ok = NotificacionController.dismiss_notification(notif["_id"], "testsuper")
        NotificacionController.create_for_expediente_asignado("testsuper", "Asignacion", "exp-1")
        still = NotificacionController.get_active_for_user("testsuper", limit=20)

        assert ok is True
        assert all(n.get("id_referencia") != "exp-1" for n in still)
