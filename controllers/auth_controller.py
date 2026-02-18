"""Controlador de autenticacion – wrapper sobre core.auth."""
import uuid
import logging
from datetime import datetime, timezone

from core.auth import login, create_user, Session, ensure_admin_exists, hash_password
from core import db_local, db_remote
from core.db_remote import is_connected
from core.audit import log_user_action, log_login, log_logout
from models.base_model import now_iso

logger = logging.getLogger(__name__)


class AuthController:

    @staticmethod
    def login(username: str, password: str) -> tuple[bool, str]:
        ok, msg = login(username, password)
        log_login(username, ok, msg)
        return ok, msg

    @staticmethod
    def logout():
        session = Session.get()
        if session.logged_in:
            log_logout(session.username)
        session.logout()

    @staticmethod
    def current_user() -> dict | None:
        return Session.get().usuario

    @staticmethod
    def current_role() -> str:
        return Session.get().rol

    @staticmethod
    def is_logged_in() -> bool:
        return Session.get().logged_in

    @staticmethod
    def create_user(username: str, password: str, nombre_completo: str,
                    email: str, rol: str) -> tuple[bool, str]:
        result = create_user(username, password, nombre_completo, email, rol)
        if result[0]:
            log_user_action("crear_usuario", username, None,
                            {"username": username, "nombre_completo": nombre_completo,
                             "email": email, "rol": rol})
        return result

    @staticmethod
    def list_users(include_deleted: bool = False) -> list[dict]:
        """Listar usuarios. Por defecto excluye los dados de baja (soft-delete)."""
        if include_deleted:
            return db_local.find_all("usuarios", order_by="nombre_completo")
        return db_local.find_all(
            "usuarios",
            where="eliminado = 0 OR eliminado IS NULL",
            order_by="nombre_completo",
        )

    @staticmethod
    def update_user(_id: str, data: dict) -> tuple[bool, str]:
        """Actualizar usuario. Si cambia password, rehashear."""
        # Validar restriccion de rol
        ok, msg = AuthController._validate_role_restriction(_id)
        if not ok:
            return False, msg

        # Capturar estado anterior para auditoria
        anterior = db_local.find_by_id("usuarios", _id)
        datos_ant = {k: v for k, v in (anterior or {}).items()
                     if k not in ("password_hash", "sync_status", "created_by_machine")} if anterior else None

        has_password_change = "password" in data and data["password"]
        if has_password_change:
            data["password_hash"] = hash_password(data.pop("password"))
        else:
            data.pop("password", None)

        data["updated_at"] = now_iso()
        data["sync_status"] = "pending"

        try:
            db_local.update("usuarios", _id, data)
            if is_connected():
                update_data = {k: v for k, v in data.items() if k != "sync_status"}
                if "activo" in update_data:
                    update_data["activo"] = bool(update_data["activo"])
                if "eliminado" in update_data:
                    update_data["eliminado"] = bool(update_data["eliminado"])
                db_remote.get_db().usuarios.update_one({"_id": _id}, {"$set": update_data})
                db_local.mark_synced("usuarios", _id)

            # Auditoria
            datos_nuevos = {k: v for k, v in data.items()
                           if k not in ("password_hash", "sync_status", "created_by_machine")}
            if has_password_change:
                datos_nuevos["password"] = "(cambiada)"
            log_user_action("actualizar_usuario", _id, datos_ant, datos_nuevos)

            return True, "Usuario actualizado"
        except Exception as e:
            logger.exception("Error al actualizar usuario _id=%s", _id)
            return False, str(e)

    @staticmethod
    def toggle_user_active(_id: str) -> tuple[bool, str]:
        user = db_local.find_by_id("usuarios", _id)
        if not user:
            return False, "Usuario no encontrado"
        new_active = 0 if user.get("activo", 1) else 1
        return AuthController.update_user(_id, {"activo": new_active})

    @staticmethod
    def pause_user(_id: str) -> tuple[bool, str]:
        """Pausar un usuario: pone activo=0 y envia signal de force_logout."""
        user = db_local.find_by_id("usuarios", _id)
        if not user:
            return False, "Usuario no encontrado"

        # No se puede pausar a si mismo
        session = Session.get()
        if session.usuario and session.usuario.get("_id") == _id:
            return False, "No puede pausarse a si mismo"

        # Validar restriccion de rol
        ok, msg = AuthController._validate_role_restriction(_id)
        if not ok:
            return False, msg

        # Poner activo = 0
        result = AuthController.update_user(_id, {"activo": 0})
        if not result[0]:
            return result

        # Insertar signal de force_logout
        AuthController._send_signal(user.get("username", ""), "force_logout")

        log_user_action("pausar_usuario", _id,
                        {"activo": 1, "username": user.get("username", "")},
                        {"activo": 0})
        return True, "Usuario pausado y signal de desconexion enviada"

    @staticmethod
    def reactivate_user(_id: str) -> tuple[bool, str]:
        """Reactivar un usuario pausado."""
        user = db_local.find_by_id("usuarios", _id)
        if not user:
            return False, "Usuario no encontrado"

        ok, msg = AuthController._validate_role_restriction(_id)
        if not ok:
            return False, msg

        result = AuthController.update_user(_id, {"activo": 1})
        if result[0]:
            log_user_action("reactivar_usuario", _id,
                            {"activo": 0, "username": user.get("username", "")},
                            {"activo": 1})
        return result

    @staticmethod
    def delete_user(_id: str) -> tuple[bool, str]:
        """Soft-delete: marca eliminado=1 y activo=0. El historial se conserva."""
        user = db_local.find_by_id("usuarios", _id)
        if not user:
            return False, "Usuario no encontrado"

        # No se puede eliminar a si mismo
        session = Session.get()
        if session.usuario and session.usuario.get("_id") == _id:
            return False, "No puede darse de baja a si mismo"

        # Validar restriccion de rol
        ok, msg = AuthController._validate_role_restriction(_id)
        if not ok:
            return False, msg

        # No eliminar si es el ultimo superusuario
        if user.get("rol") == "superusuario":
            count = db_local.count(
                "usuarios",
                "rol = 'superusuario' AND (eliminado = 0 OR eliminado IS NULL) AND activo = 1"
            )
            if count <= 1:
                return False, "No se puede dar de baja al unico superusuario activo"

        # Enviar signal de desconexion antes del soft-delete
        AuthController._send_signal(user.get("username", ""), "force_logout")

        # Soft-delete
        result = AuthController.update_user(_id, {"eliminado": 1, "activo": 0})
        if result[0]:
            log_user_action("eliminar_usuario", _id,
                            {"eliminado": 0, "username": user.get("username", ""), "rol": user.get("rol", "")},
                            {"eliminado": 1, "activo": 0})
        return result

    @staticmethod
    def reset_password(_id: str, new_password: str) -> tuple[bool, str]:
        """Resetear la contrasena de un usuario."""
        if not new_password:
            return False, "La contrasena no puede estar vacia"

        ok, msg = AuthController._validate_role_restriction(_id)
        if not ok:
            return False, msg

        result = AuthController.update_user(_id, {"password": new_password})
        if result[0]:
            user = db_local.find_by_id("usuarios", _id)
            log_user_action("reset_password", _id,
                            None,
                            {"username": user.get("username", "") if user else _id, "password": "(reseteada)"})
        return result

    # ── Helpers privados ──

    @staticmethod
    def _validate_role_restriction(_id: str) -> tuple[bool, str]:
        """Valida que un admin no pueda modificar superusuarios."""
        session = Session.get()
        if not session.logged_in:
            return False, "No hay sesion activa"

        current_rol = session.rol
        if current_rol == "superusuario":
            return True, ""  # Superusuario puede hacer todo

        target = db_local.find_by_id("usuarios", _id)
        if not target:
            return False, "Usuario no encontrado"

        if target.get("rol") == "superusuario":
            return False, "No tiene permisos para modificar superusuarios"

        return True, ""

    @staticmethod
    def _send_signal(target_username: str, signal_type: str):
        """Inserta un signal en session_signals para forzar acciones en otros clientes."""
        signal = {
            "_id": str(uuid.uuid4()),
            "target_user": target_username,
            "signal_type": signal_type,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "processed": 0,
        }
        db_local.insert("session_signals", signal)

    @staticmethod
    def check_signals_for_user(username: str) -> list[dict]:
        """Busca signals no procesados para un usuario."""
        return db_local.find_all(
            "session_signals",
            where="target_user = ? AND processed = 0",
            params=(username,),
        )

    @staticmethod
    def mark_signal_processed(_id: str):
        """Marca un signal como procesado."""
        db_local.update("session_signals", _id, {"processed": 1})
