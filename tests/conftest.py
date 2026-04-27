"""
Fixtures globales para toda la suite de tests.

Cada test obtiene automaticamente:
- Una BD SQLite temporal aislada (esquema inicializado)
- MongoDB simulado como desconectado
- Session limpia (sin usuario logueado)
- MACHINE_ID fijo para reproducibilidad
"""
import os
import sys
import uuid

import pytest

# Asegurar que el proyecto raiz este en el path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Fixture autouse: aislamiento completo por test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate_environment(tmp_path, monkeypatch):
    """Cada test corre contra una BD SQLite temporal propia."""
    db_path = str(tmp_path / "test.db")

    # 1. SQLite temporal
    monkeypatch.setattr("core.db_local.SQLITE_PATH", db_path)

    # 2. MACHINE_ID fijo en todos los modulos que lo importan
    for mod in [
        "config",
        "models.base_model",
        "core.audit",
        "core.auth",
        "controllers.base_controller",
    ]:
        try:
            monkeypatch.setattr(f"{mod}.MACHINE_ID", "test-machine")
        except (AttributeError, ModuleNotFoundError):
            pass

    # 3. MongoDB desconectado por defecto
    #    Parchear tanto en db_remote como en los modulos que importan is_connected
    _fake_disconnected = lambda: False
    monkeypatch.setattr("core.db_remote.is_connected", _fake_disconnected)
    monkeypatch.setattr("core.db_remote._client", None)
    monkeypatch.setattr("core.db_remote._db", None)
    # Modulos que hacen "from core.db_remote import is_connected"
    for mod in ["core.auth", "core.sync_engine"]:
        try:
            monkeypatch.setattr(f"{mod}.is_connected", _fake_disconnected)
        except (AttributeError, ModuleNotFoundError):
            pass

    # 4. Session limpia
    from core.auth import Session
    monkeypatch.setattr(Session, "_instance", None)

    # 5. Inicializar esquema
    from core import db_local
    db_local.init_db()

    yield db_path


# ---------------------------------------------------------------------------
# Fixtures de sesion (no autouse – se usan explicitamente)
# ---------------------------------------------------------------------------

@pytest.fixture
def session_superusuario(monkeypatch):
    """Session con rol superusuario (visibilidad global)."""
    from core.auth import Session
    session = Session()
    session.usuario = {
        "_id": "test-super-id",
        "username": "testsuper",
        "nombre_completo": "Test Superusuario",
        "rol": "superusuario",
        "activo": 1,
        "eliminado": 0,
    }
    monkeypatch.setattr(Session, "_instance", session)
    return session


@pytest.fixture
def session_admin(monkeypatch):
    """Session con rol administrador."""
    from core.auth import Session
    session = Session()
    session.usuario = {
        "_id": "test-admin-id",
        "username": "testadmin",
        "nombre_completo": "Test Admin",
        "rol": "administrador",
        "activo": 1,
        "eliminado": 0,
    }
    monkeypatch.setattr(Session, "_instance", session)
    return session


@pytest.fixture
def session_secretaria(monkeypatch):
    """Session con rol secretaria (visibilidad restringida)."""
    from core.auth import Session
    session = Session()
    session.usuario = {
        "_id": "test-sec-id",
        "username": "testsec",
        "nombre_completo": "Test Secretaria",
        "rol": "secretaria",
        "activo": 1,
        "eliminado": 0,
    }
    monkeypatch.setattr(Session, "_instance", session)
    return session


@pytest.fixture
def session_abogado(monkeypatch):
    """Session con rol abogado."""
    from core.auth import Session
    session = Session()
    session.usuario = {
        "_id": "test-abo-id",
        "username": "testabo",
        "nombre_completo": "Test Abogado",
        "rol": "abogado",
        "activo": 1,
        "eliminado": 0,
    }
    monkeypatch.setattr(Session, "_instance", session)
    return session


@pytest.fixture
def session_agente(monkeypatch):
    """Session con rol agente."""
    from core.auth import Session
    session = Session()
    session.usuario = {
        "_id": "test-age-id",
        "username": "testagente",
        "nombre_completo": "Test Agente",
        "rol": "agente",
        "activo": 1,
        "eliminado": 0,
    }
    monkeypatch.setattr(Session, "_instance", session)
    return session


@pytest.fixture
def session_analisis(monkeypatch):
    """Session con rol analisis."""
    from core.auth import Session
    session = Session()
    session.usuario = {
        "_id": "test-ana-id",
        "username": "testanalisis",
        "nombre_completo": "Test Analisis",
        "rol": "analisis",
        "activo": 1,
        "eliminado": 0,
    }
    monkeypatch.setattr(Session, "_instance", session)
    return session


@pytest.fixture
def session_admin_visor(monkeypatch):
    """Session con rol admin_visor."""
    from core.auth import Session
    session = Session()
    session.usuario = {
        "_id": "test-av-id",
        "username": "testadminvisor",
        "nombre_completo": "Test Admin Visor",
        "rol": "admin_visor",
        "activo": 1,
        "eliminado": 0,
    }
    monkeypatch.setattr(Session, "_instance", session)
    return session


# ---------------------------------------------------------------------------
# Fixtures de datos semilla
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_cliente():
    """Datos minimos de un cliente de prueba."""
    return {
        "numero_carpeta": "1001",
        "nombre_completo": "Juan Perez",
        "dni": "12345678",
        "cuil": "20-12345678-9",
        "fecha_nacimiento": "1980-01-15",
        "direccion": "Calle Falsa 123",
        "telefonos": '["3624001234"]',
        "email": "juan@test.com",
        "obra_social": "OSDE",
        "actividad": "Empleado",
        "observaciones": "",
    }


@pytest.fixture
def sample_expediente():
    """Datos minimos de un expediente de prueba."""
    return {
        "id_cliente": "cli-test-001",
        "tipo_tramite": "Jubilacion",
        "area": "Previsional",
        "fecha_apertura": "2025-01-10",
        "responsable": "Test Abogado",
        "responsable_username": "testsuper",
        "estado": "Activo",
        "prioridad": "Normal",
        "observaciones": "Expediente de prueba",
    }


@pytest.fixture
def sample_consulta():
    """Datos minimos de una consulta de prueba."""
    return {
        "fecha_ingreso": "2025-02-01",
        "canal": "Telefono",
        "nombre": "Maria Lopez",
        "dni": "87654321",
        "telefono": "3624999888",
        "email": "maria@test.com",
        "motivo": "Consulta por jubilacion",
        "estado": "Nuevo",
        "operador": "testsuper",
    }


@pytest.fixture
def sample_tarea():
    """Datos minimos de una tarea de prueba."""
    return {
        "id_expediente": "exp-test-001",
        "tipo_accion": "Turno ANSES",
        "descripcion": "Sacar turno en UDAI",
        "responsable": "Test Abogado",
        "responsable_username": "testsuper",
        "fecha_inicio": "2025-03-01",
        "fecha_vencimiento": "2025-03-15",
        "estado": "Pendiente",
    }


@pytest.fixture
def sample_turno():
    """Datos minimos de un turno de prueba."""
    return {
        "id_cliente": "cli-test-001",
        "id_expediente": "exp-test-001",
        "fecha_turno": "2025-04-10",
        "hora_turno": "09:30",
        "oficina_anses": "UDAI Resistencia",
        "tipo_tramite": "Jubilacion",
        "estado": "Pendiente",
        "responsable": "Test Abogado",
        "responsable_username": "testsuper",
    }


@pytest.fixture
def sample_movimiento():
    """Datos minimos de un movimiento economico."""
    return {
        "id_cliente": "cli-test-001",
        "id_expediente": "exp-test-001",
        "tipo": "Honorario",
        "monto": 50000.0,
        "fecha": "2025-05-01",
        "forma_pago": "Transferencia",
        "estado": "Pendiente",
        "saldo": 50000.0,
        "observaciones": "",
        "responsable_username": "testsuper",
    }


@pytest.fixture
def sample_comunicacion():
    """Datos minimos de una comunicacion."""
    return {
        "id_expediente": "exp-test-001",
        "fecha": "2025-06-01",
        "canal": "WhatsApp",
        "emisor": "Abogado",
        "receptor": "Cliente",
        "responsable_username": "testsuper",
        "motivo": "Seguimiento",
        "mensaje": "Buenos dias, le informamos que...",
        "resultado": "OK",
    }


@pytest.fixture
def sample_documento(tmp_path):
    """Datos minimos de un documento con archivo temporal."""
    # Crear un archivo ficticio
    fake_file = tmp_path / "test_doc.pdf"
    fake_file.write_text("contenido de prueba", encoding="utf-8")
    return {
        "id_expediente": "exp-test-001",
        "categoria": "Identidad",
        "subcategoria": "DNI",
        "nombre": "DNI_frente",
        "descripcion": "Foto del frente del DNI",
        "ruta_archivo": str(fake_file),
        "tamano_bytes": fake_file.stat().st_size,
        "mime_type": "application/pdf",
        "responsable": "Test Abogado",
        "responsable_username": "testsuper",
    }


@pytest.fixture
def seed_usuario():
    """Inserta un usuario de prueba en la BD y lo retorna."""
    from core import db_local
    from core.auth import hash_password
    _id = str(uuid.uuid4())
    user = {
        "_id": _id,
        "username": "testuser",
        "password_hash": hash_password("test123"),
        "nombre_completo": "Test User",
        "email": "test@test.com",
        "rol": "abogado",
        "activo": 1,
        "eliminado": 0,
        "ultimo_acceso": None,
        "updated_at": "2025-01-01T00:00:00+00:00",
        "version": 1,
        "sync_status": "synced",
        "created_by_machine": "test-machine",
    }
    db_local.insert("usuarios", user)
    return user


@pytest.fixture
def populated_system(session_superusuario):
    """Escenario completo con usuarios, clientes, expedientes y tareas."""
    from core import db_local
    from controllers.cliente_controller import ClienteController
    from controllers.expediente_controller import ExpedienteController
    from controllers.tarea_controller import TareaController

    users = [
        {"username": "abogado1", "rol": "abogado", "nombre_completo": "Abogado Uno"},
        {"username": "agente1", "rol": "agente", "nombre_completo": "Agente Uno"},
        {"username": "analisis1", "rol": "analisis", "nombre_completo": "Analisis Uno"},
        {"username": "adminvisor1", "rol": "admin_visor", "nombre_completo": "Admin Visor Uno"},
    ]
    for user in users:
        db_local.insert(
            "usuarios",
            {
                "_id": f"user-{user['username']}",
                "username": user["username"],
                "password_hash": "x",
                "nombre_completo": user["nombre_completo"],
                "email": f"{user['username']}@test.com",
                "rol": user["rol"],
                "activo": 1,
                "eliminado": 0,
                "sync_status": "synced",
                "version": 1,
                "created_by_machine": "test-machine",
            },
        )

    clientes = [
        ClienteController.create({"nombre_completo": "Cliente Uno", "dni": "20111111", "numero_carpeta": "9001"}),
        ClienteController.create({"nombre_completo": "Cliente Dos", "dni": "20222222", "numero_carpeta": "9002"}),
        ClienteController.create({"nombre_completo": "Cliente Tres", "dni": "20333333", "numero_carpeta": "9003"}),
    ]

    expedientes = [
        ExpedienteController.create({
            "id_cliente": clientes[0]["_id"],
            "tipo_tramite": "Jubilacion",
            "estado": "Activo",
            "etapa_codigo": "para_citar_o_videollamada",
            "responsable": "Abogado Uno",
            "responsable_username": "abogado1",
        }),
        ExpedienteController.create({
            "id_cliente": clientes[1]["_id"],
            "tipo_tramite": "Pension",
            "estado": "Activo",
            "etapa_codigo": "pendiente_turno",
            "responsable": "Agente Uno",
            "responsable_username": "agente1",
        }),
        ExpedienteController.create({
            "id_cliente": clientes[2]["_id"],
            "tipo_tramite": "Reclamo",
            "estado": "En espera",
            "etapa_codigo": "req_analizar",
            "responsable": "Analisis Uno",
            "responsable_username": "analisis1",
        }),
        ExpedienteController.create({
            "id_cliente": clientes[0]["_id"],
            "tipo_tramite": "Jubilacion",
            "estado": "Cerrado",
            "etapa_codigo": "favorable",
            "responsable": "Abogado Uno",
            "responsable_username": "abogado1",
        }),
    ]

    tareas = [
        TareaController.create({
            "id_expediente": expedientes[0]["_id"],
            "tipo_accion": "Seguimiento expediente",
            "estado": "Pendiente",
            "responsable": "Abogado Uno",
            "responsable_username": "abogado1",
        }),
        TareaController.create({
            "id_expediente": expedientes[1]["_id"],
            "tipo_accion": "Turno ANSES",
            "estado": "En curso",
            "responsable": "Agente Uno",
            "responsable_username": "agente1",
        }),
        TareaController.create({
            "id_expediente": expedientes[2]["_id"],
            "tipo_accion": "Analizar requerimiento",
            "estado": "En espera",
            "responsable": "Analisis Uno",
            "responsable_username": "analisis1",
        }),
    ]

    return {"users": users, "clientes": clientes, "expedientes": expedientes, "tareas": tareas}
