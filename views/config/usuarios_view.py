"""Vista de gestion de empleados/usuarios con CRUD completo."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox,
    QDialog, QFormLayout, QLineEdit, QComboBox, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor

from views.widgets.filterable_table import FilterableTable
from controllers.auth_controller import AuthController
from core.auth import Session
from core.permissions import ROLES

COLUMNS = [
    ("username", "Usuario"),
    ("nombre_completo", "Nombre Completo"),
    ("email", "Email"),
    ("rol_display", "Rol"),
    ("estado_display", "Estado"),
    ("ultimo_acceso_fmt", "Ultimo Acceso"),
]


class UsuariosView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_rol = Session.get().rol

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        # ── Header ──
        header = QHBoxLayout()
        title = QLabel("Gestion de Empleados")
        title.setFont(QFont("Lato", 17, QFont.Weight.Bold))
        title.setStyleSheet("color: #1a1a1a;")
        header.addWidget(title)
        header.addStretch()

        btn_new = QPushButton("+ Nuevo Empleado")
        btn_new.clicked.connect(self._new_user)
        header.addWidget(btn_new)

        btn_edit = QPushButton("Editar")
        btn_edit.setProperty("variant", "secondary")
        btn_edit.clicked.connect(self._edit_user)
        header.addWidget(btn_edit)

        btn_reset_pw = QPushButton("Resetear Clave")
        btn_reset_pw.setProperty("variant", "secondary")
        btn_reset_pw.clicked.connect(self._reset_password)
        header.addWidget(btn_reset_pw)

        self._btn_pause = QPushButton("Pausar")
        self._btn_pause.setStyleSheet("""
            QPushButton {
                background-color: #b8963c;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #a07c30; }
        """)
        self._btn_pause.clicked.connect(self._pause_reactivate)
        header.addWidget(self._btn_pause)

        btn_delete = QPushButton("Dar de Baja")
        btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #cc3333;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #aa2222; }
        """)
        btn_delete.clicked.connect(self._delete_user)
        header.addWidget(btn_delete)

        layout.addLayout(header)

        # ── Info ──
        info = QLabel("Los empleados dados de baja no aparecen en esta lista. Su historial de actividad se conserva en auditoria.")
        info.setStyleSheet("color: #8a8a8a; font-size: 11px; font-style: italic;")
        layout.addWidget(info)

        # ── Tabla ──
        self._table = FilterableTable(COLUMNS)
        self._table.row_selected.connect(self._on_selection_changed)
        layout.addWidget(self._table)

        # Datos internos
        self._users_data: list[dict] = []

    def refresh(self):
        """Carga la lista de usuarios, excluyendo eliminados y filtrando por rol."""
        users = AuthController.list_users(include_deleted=False)
        current_rol = Session.get().rol

        # Si es administrador, ocultar superusuarios
        if current_rol != "superusuario":
            users = [u for u in users if u.get("rol") != "superusuario"]

        # Preparar datos para la tabla
        for u in users:
            u["rol_display"] = (u.get("rol") or "").capitalize()
            activo = u.get("activo") in (1, True, "1", "True")
            u["estado_display"] = "Activo" if activo else "Pausado"
            # Formatear ultimo acceso
            ua = u.get("ultimo_acceso", "") or ""
            if ua and len(ua) >= 19:
                u["ultimo_acceso_fmt"] = ua[:10] + " " + ua[11:16]
            else:
                u["ultimo_acceso_fmt"] = ua[:16] if ua else "Nunca"

        self._users_data = users
        self._table.set_data(users)

    def _get_selected_user(self) -> dict | None:
        """Obtiene el usuario seleccionado actualmente."""
        _id = self._table.get_selected_id()
        if not _id:
            return None
        for u in self._users_data:
            if u.get("_id") == _id:
                return u
        return None

    def _on_selection_changed(self, _id: str):
        """Actualiza el texto del boton pausar/reactivar segun el seleccionado."""
        for u in self._users_data:
            if u.get("_id") == _id:
                activo = u.get("activo") in (1, True, "1", "True")
                self._btn_pause.setText("Reactivar" if not activo else "Pausar")
                return
        self._btn_pause.setText("Pausar")

    def _check_not_self(self, user: dict) -> bool:
        """Verifica que no se este intentando operar sobre si mismo."""
        session = Session.get()
        if session.usuario and session.usuario.get("_id") == user.get("_id"):
            QMessageBox.warning(self, "Operacion no permitida",
                                "No puede realizar esta accion sobre su propio usuario.")
            return False
        return True

    # ── CRUD ──

    def _new_user(self):
        dlg = UserFormDialog(parent=self)
        if dlg.exec():
            self.refresh()

    def _edit_user(self):
        user = self._get_selected_user()
        if not user:
            QMessageBox.information(self, "Atencion", "Seleccione un empleado.")
            return
        dlg = UserFormDialog(user_id=user["_id"], parent=self)
        if dlg.exec():
            self.refresh()

    def _reset_password(self):
        user = self._get_selected_user()
        if not user:
            QMessageBox.information(self, "Atencion", "Seleccione un empleado.")
            return
        if not self._check_not_self(user):
            return

        dlg = ResetPasswordDialog(user.get("username", ""), parent=self)
        if dlg.exec():
            new_pw = dlg.get_password()
            if new_pw:
                ok, msg = AuthController.reset_password(user["_id"], new_pw)
                if ok:
                    QMessageBox.information(self, "Exito", f"Contrasena de '{user.get('username')}' actualizada.")
                else:
                    QMessageBox.warning(self, "Error", msg)

    def _pause_reactivate(self):
        user = self._get_selected_user()
        if not user:
            QMessageBox.information(self, "Atencion", "Seleccione un empleado.")
            return
        if not self._check_not_self(user):
            return

        activo = user.get("activo") in (1, True, "1", "True")

        if activo:
            # Pausar
            reply = QMessageBox.question(
                self, "Pausar Empleado",
                f"Esta seguro que desea pausar a '{user.get('username')}'?\n\n"
                "El empleado sera desconectado si esta usando el sistema.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            ok, msg = AuthController.pause_user(user["_id"])
        else:
            # Reactivar
            reply = QMessageBox.question(
                self, "Reactivar Empleado",
                f"Esta seguro que desea reactivar a '{user.get('username')}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            ok, msg = AuthController.reactivate_user(user["_id"])

        if ok:
            self.refresh()
        else:
            QMessageBox.warning(self, "Error", msg)

    def _delete_user(self):
        user = self._get_selected_user()
        if not user:
            QMessageBox.information(self, "Atencion", "Seleccione un empleado.")
            return
        if not self._check_not_self(user):
            return

        reply = QMessageBox.warning(
            self, "Dar de Baja Empleado",
            f"Esta seguro que desea dar de baja a '{user.get('username')}'?\n\n"
            "El empleado sera desconectado y no podra volver a iniciar sesion.\n"
            "Su historial de actividad se conservara para trazabilidad.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Segunda confirmacion
        reply2 = QMessageBox.question(
            self, "Confirmar Baja",
            f"Confirme la baja definitiva de '{user.get('username')}'.\n"
            "Esta accion no se puede deshacer facilmente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply2 != QMessageBox.StandardButton.Yes:
            return

        ok, msg = AuthController.delete_user(user["_id"])
        if ok:
            QMessageBox.information(self, "Exito",
                                    f"'{user.get('username')}' ha sido dado de baja.")
            self.refresh()
        else:
            QMessageBox.warning(self, "Error", msg)


# ══════════════════════════════════════════════
#  Dialogo de formulario de usuario
# ══════════════════════════════════════════════

class UserFormDialog(QDialog):
    def __init__(self, user_id: str = None, parent=None):
        super().__init__(parent)
        self._id = user_id
        self._is_edit = user_id is not None
        self._current_rol = Session.get().rol

        self.setWindowTitle("Editar Empleado" if self._is_edit else "Nuevo Empleado")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # Titulo
        title = QLabel("Editar Empleado" if self._is_edit else "Nuevo Empleado")
        title.setFont(QFont("Lato", 15, QFont.Weight.Bold))
        title.setStyleSheet("color: #c9a84c;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self._txt_username = QLineEdit()
        self._txt_username.setPlaceholderText("Nombre de usuario para login")
        form.addRow("Usuario *:", self._txt_username)

        self._txt_password = QLineEdit()
        self._txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._txt_password.setPlaceholderText(
            "Dejar vacio para no cambiar" if self._is_edit else "Contrasena"
        )
        form.addRow("Contrasena *:" if not self._is_edit else "Nueva contrasena:", self._txt_password)

        self._txt_nombre = QLineEdit()
        self._txt_nombre.setPlaceholderText("Nombre y apellido completo")
        form.addRow("Nombre completo *:", self._txt_nombre)

        self._txt_email = QLineEdit()
        self._txt_email.setPlaceholderText("email@ejemplo.com")
        form.addRow("Email:", self._txt_email)

        self._cmb_rol = QComboBox()
        roles_disponibles = ROLES
        # Si el usuario actual es admin (no super), no puede asignar superusuario
        if self._current_rol != "superusuario":
            roles_disponibles = [r for r in ROLES if r != "superusuario"]
        for r in roles_disponibles:
            self._cmb_rol.addItem(r.capitalize(), r)
        form.addRow("Rol *:", self._cmb_rol)

        layout.addLayout(form)

        # Botones
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("variant", "secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_save = QPushButton("Guardar")
        btn_save.clicked.connect(self._save)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

        if self._is_edit:
            self._load_data()

    def _load_data(self):
        from core import db_local
        user = db_local.find_by_id("usuarios", self._id)
        if not user:
            self.reject()
            return
        self._txt_username.setText(user.get("username", ""))
        self._txt_username.setReadOnly(True)
        self._txt_username.setStyleSheet("background-color: #2a2a2a; color: #8a8a8a;")
        self._txt_nombre.setText(user.get("nombre_completo", ""))
        self._txt_email.setText(user.get("email", ""))
        idx = self._cmb_rol.findData(user.get("rol", ""))
        if idx >= 0:
            self._cmb_rol.setCurrentIndex(idx)

    def _save(self):
        username = self._txt_username.text().strip()
        password = self._txt_password.text()
        nombre = self._txt_nombre.text().strip()
        rol = self._cmb_rol.currentData()

        if not username or not nombre:
            QMessageBox.warning(self, "Atencion", "Complete los campos obligatorios (usuario y nombre).")
            return

        if self._is_edit:
            data = {
                "nombre_completo": nombre,
                "email": self._txt_email.text().strip(),
                "rol": rol,
            }
            if password:
                data["password"] = password
            ok, msg = AuthController.update_user(self._id, data)
        else:
            if not password:
                QMessageBox.warning(self, "Atencion", "La contrasena es obligatoria para nuevos empleados.")
                return
            ok, msg = AuthController.create_user(
                username, password, nombre, self._txt_email.text().strip(), rol
            )

        if ok:
            self.accept()
        else:
            QMessageBox.warning(self, "Error", msg)


# ══════════════════════════════════════════════
#  Dialogo para resetear contrasena
# ══════════════════════════════════════════════

class ResetPasswordDialog(QDialog):
    def __init__(self, username: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Resetear Contrasena - {username}")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info = QLabel(f"Ingrese la nueva contrasena para '{username}':")
        info.setFont(QFont("Lato", 11))
        layout.addWidget(info)

        self._txt_password = QLineEdit()
        self._txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._txt_password.setPlaceholderText("Nueva contrasena")
        layout.addWidget(self._txt_password)

        self._txt_confirm = QLineEdit()
        self._txt_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._txt_confirm.setPlaceholderText("Confirmar contrasena")
        layout.addWidget(self._txt_confirm)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("variant", "secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_save = QPushButton("Guardar")
        btn_save.clicked.connect(self._save)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def _save(self):
        pw = self._txt_password.text()
        confirm = self._txt_confirm.text()

        if not pw:
            QMessageBox.warning(self, "Atencion", "La contrasena no puede estar vacia.")
            return
        if pw != confirm:
            QMessageBox.warning(self, "Atencion", "Las contrasenas no coinciden.")
            return

        self.accept()

    def get_password(self) -> str:
        return self._txt_password.text()
