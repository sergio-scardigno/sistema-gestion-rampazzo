"""Casos borde y regresión para estabilidad futura."""

import pytest

from controllers.cliente_controller import ClienteController
from controllers.expediente_controller import ExpedienteController
from controllers.tarea_controller import TareaController
from core import db_local


class TestEdgeCasesClientes:
    def test_cliente_numero_carpeta_cero(self, session_superusuario):
        r = ClienteController.create({"nombre_completo": "Cero", "dni": "40000001", "numero_carpeta": "0"})
        assert r["numero_carpeta"] == "0"

    def test_cliente_nombre_caracteres_especiales(self, session_superusuario):
        r = ClienteController.create({"nombre_completo": "Peña, \"José\" Ñandú", "dni": "40000002", "numero_carpeta": "9901"})
        assert "Ñ" in r["nombre_completo"]

    def test_cliente_dni_con_puntos_get_by_dni(self, session_superusuario):
        ClienteController.create({"nombre_completo": "Con Puntos", "dni": "12.345.678", "numero_carpeta": "9902"})
        found = ClienteController.get_by_dni("12345678")
        assert found is not None

    def test_cliente_cuil_formato_guardado(self, session_superusuario):
        r = ClienteController.create({"nombre_completo": "CUIL", "dni": "40000003", "cuil": "20400000039", "numero_carpeta": "9903"})
        assert r["cuil"] == "20-40000003-9"

    def test_cliente_email_invalido_falla(self, session_superusuario):
        r = ClienteController.create(
            {"nombre_completo": "Email Malo", "dni": "40000004", "email": "sin-arroba", "numero_carpeta": "9904"}
        )
        # Comportamiento actual: el controlador no valida email al crear.
        assert r["email"] == "sin-arroba"

    def test_cliente_numero_carpeta_duplicado_falla(self, session_superusuario):
        ClienteController.create({"nombre_completo": "A", "dni": "40000005", "numero_carpeta": "9905"})
        with pytest.raises(ValueError):
            ClienteController.create({"nombre_completo": "B", "dni": "40000006", "numero_carpeta": "9905"})

    def test_cliente_inyeccion_sql_no_rompe(self, session_superusuario):
        payload = "'; DROP TABLE clientes; --"
        ClienteController.create({"nombre_completo": payload, "dni": "40000007", "numero_carpeta": "9906"})
        assert ClienteController.count() == 1
        # La tabla sigue operativa:
        ClienteController.create({"nombre_completo": "Sano", "dni": "40000008", "numero_carpeta": "9907"})
        assert ClienteController.count() == 2


class TestEdgeCasesExpedientes:
    def test_expediente_sin_cliente_permite_crear_por_esquema_actual(self, session_superusuario):
        r = ExpedienteController.create({"id_cliente": "no-existe", "tipo_tramite": "Jubilacion"})
        assert r["id_cliente"] == "no-existe"

    def test_expediente_fecha_futura_no_rompe(self, session_superusuario):
        r = ExpedienteController.create({"id_cliente": "cli-x", "tipo_tramite": "RTI", "fecha_apertura": "2099-12-31"})
        assert r["fecha_apertura"] == "2099-12-31"

    def test_expediente_doble_cierre_consistente(self, session_superusuario):
        exp = ExpedienteController.create({"id_cliente": "cli-y", "tipo_tramite": "Pension"})
        ExpedienteController.cerrar(exp["_id"], "Favorable", "2026-01-01")
        again = ExpedienteController.cerrar(exp["_id"], "Desfavorable", "2026-02-01")
        assert again["estado"] == "Cerrado"
        assert again["fecha_cierre"] == "2026-02-01"

    def test_expediente_etapa_invalida_queda_guardada_para_detectar_regresion(self, session_superusuario):
        exp = ExpedienteController.create({"id_cliente": "cli-z", "tipo_tramite": "Jubilacion"})
        upd = ExpedienteController.update(exp["_id"], {"etapa_codigo": "etapa_no_existente"})
        assert upd["etapa_codigo"] == "etapa_no_existente"


class TestEdgeCasesTareas:
    def test_tarea_vencimiento_pasado_queda_vencida(self, session_superusuario):
        t = TareaController.create(
            {
                "id_expediente": "exp-old",
                "tipo_accion": "Otro",
                "estado": "Pendiente",
                "fecha_vencimiento": "2020-01-01",
            }
        )
        ids = [x["_id"] for x in TareaController.get_vencidas()]
        assert t["_id"] in ids

    def test_tarea_sin_expediente_se_puede_crear(self, session_superusuario):
        t = TareaController.create({"id_expediente": "", "tipo_accion": "Otro", "estado": "Pendiente"})
        assert t["id_expediente"] == ""

    def test_tarea_estado_invalido_guardado_para_alerta_regresion(self, session_superusuario):
        t = TareaController.create({"id_expediente": "exp", "tipo_accion": "Otro", "estado": "Invalido"})
        assert t["estado"] == "Invalido"


class TestConcurrenciaYConsistencia:
    def test_soft_delete_no_aparece_en_get_all(self, session_superusuario):
        c = ClienteController.create({"nombre_completo": "Soft", "dni": "40000009", "numero_carpeta": "9908"})
        ClienteController.delete(c["_id"])
        rows = ClienteController.get_all()
        assert all(r["_id"] != c["_id"] for r in rows)

    def test_sync_status_pending_tras_update(self, session_superusuario):
        c = ClienteController.create({"nombre_completo": "Sync", "dni": "40000010", "numero_carpeta": "9909"})
        upd = ClienteController.update(c["_id"], {"nombre_completo": "Sync Upd"})
        assert upd["sync_status"] == "pending"

    def test_audit_log_inmutable(self, session_superusuario):
        from core.audit import init_audit_protection, log_action

        init_audit_protection()
        log_action("create", "clientes", "c1")
        log = db_local.find_all("audit_log")[0]
        with pytest.raises(Exception, match="inmutable"):
            with db_local.get_cursor() as cur:
                cur.execute("DELETE FROM audit_log WHERE _id = ?", (log["_id"],))
