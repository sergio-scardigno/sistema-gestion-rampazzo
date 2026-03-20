"""Pantalla de Login."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QFrame, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont, QColor, QPixmap

from controllers.auth_controller import AuthController
from controllers.config_controller import ConfigController
from config import APP_NAME, APP_VERSION


class LoginView(QWidget):
    login_success = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(460, 620)
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} - Iniciar Sesion")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Fondo oscuro elegante para la ventana de login
        self.setStyleSheet("""
            LoginView {
                background-color: #111111;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.setContentsMargins(40, 40, 40, 40)

        # ─── Card container ───
        card = QFrame(self)
        card.setObjectName("loginCard")
        card.setStyleSheet("""
            #loginCard {
                background-color: #1a1a1a;
                border: 1px solid #333333;
                border-radius: 14px;
            }
            #loginCard QLabel {
                background: transparent;
                border: none;
            }
            #loginCard QLineEdit {
                background-color: #222222;
                color: #f0f0f0;
                border: 1px solid #444444;
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 13px;
                font-family: "Lato", "Segoe UI", sans-serif;
                selection-background-color: #c9a84c;
                selection-color: #111111;
            }
            #loginCard QLineEdit:focus {
                border: 2px solid #c9a84c;
            }
            #loginCard QLineEdit::placeholder {
                color: #666666;
            }
        """)

        # Sombra sutil dorada
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(201, 168, 76, 50))
        card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(6)
        card_layout.setContentsMargins(36, 40, 36, 36)

        # ─── Logo / Titulo ───
        # Linea dorada decorativa superior
        gold_line = QFrame()
        gold_line.setFixedHeight(3)
        gold_line.setStyleSheet("background-color: #c9a84c; border: none; border-radius: 1px;")
        card_layout.addWidget(gold_line)
        card_layout.addSpacing(20)

        # Logo principal (si esta configurado)
        self._login_logo = QLabel()
        self._login_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._login_logo.setStyleSheet("border: none; background: transparent;")
        self._login_logo.setFixedHeight(60)
        card_layout.addWidget(self._login_logo)
        self._apply_login_logo()

        title = QLabel(APP_NAME.upper())
        title.setFont(QFont("Lato", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #c9a84c; letter-spacing: 2px;")
        card_layout.addWidget(title)

        subtitle = QLabel("Sistema de Gestion")
        subtitle.setFont(QFont("Lato", 12))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #888888; margin-bottom: 24px;")
        card_layout.addWidget(subtitle)

        # ─── Campo Usuario ───
        lbl_user = QLabel("USUARIO")
        lbl_user.setFont(QFont("Lato", 10, QFont.Weight.Bold))
        lbl_user.setStyleSheet("color: #b0b0b0; letter-spacing: 1px; margin-bottom: 2px;")
        card_layout.addWidget(lbl_user)

        self._txt_username = QLineEdit()
        self._txt_username.setPlaceholderText("Ingrese su usuario")
        self._txt_username.setMinimumHeight(44)
        card_layout.addWidget(self._txt_username)
        card_layout.addSpacing(12)

        # ─── Campo Contrasena ───
        lbl_pass = QLabel("CONTRASENA")
        lbl_pass.setFont(QFont("Lato", 10, QFont.Weight.Bold))
        lbl_pass.setStyleSheet("color: #b0b0b0; letter-spacing: 1px; margin-bottom: 2px;")
        card_layout.addWidget(lbl_pass)

        self._txt_password = QLineEdit()
        self._txt_password.setPlaceholderText("Ingrese su contrasena")
        self._txt_password.setEchoMode(QLineEdit.EchoMode.Password)
        self._txt_password.setMinimumHeight(44)
        self._txt_password.returnPressed.connect(self._do_login)
        card_layout.addWidget(self._txt_password)
        card_layout.addSpacing(20)

        # ─── Boton Login ───
        self._btn_login = QPushButton("Iniciar Sesion")
        self._btn_login.setMinimumHeight(46)
        self._btn_login.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_login.setFont(QFont("Lato", 13, QFont.Weight.Bold))
        self._btn_login.setStyleSheet("""
            QPushButton {
                background-color: #c9a84c;
                color: #111111;
                border: none;
                border-radius: 8px;
                font-family: "Lato", "Segoe UI", sans-serif;
            }
            QPushButton:hover {
                background-color: #d4b85c;
            }
            QPushButton:pressed {
                background-color: #a07c30;
            }
            QPushButton:disabled {
                background-color: #444444;
                color: #888888;
            }
        """)
        self._btn_login.clicked.connect(self._do_login)
        card_layout.addWidget(self._btn_login)

        # ─── Version ───
        card_layout.addSpacing(16)
        version_lbl = QLabel(f"v{APP_VERSION}")
        version_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_lbl.setStyleSheet("color: #555555; font-size: 11px;")
        card_layout.addWidget(version_lbl)

        main_layout.addWidget(card)

    def _do_login(self):
        username = self._txt_username.text().strip()
        password = self._txt_password.text()

        if not username or not password:
            QMessageBox.warning(self, "Atencion", "Complete usuario y contrasena.")
            return

        self._btn_login.setEnabled(False)
        self._btn_login.setText("Ingresando...")

        ok, msg = AuthController.login(username, password)

        self._btn_login.setEnabled(True)
        self._btn_login.setText("Iniciar Sesion")

        if ok:
            self.login_success.emit()
        else:
            QMessageBox.critical(self, "Error de Login", msg)
            self._txt_password.clear()
            self._txt_password.setFocus()

    def _apply_login_logo(self):
        """Muestra el logo principal en la pantalla de login si esta configurado."""
        logo_path = ConfigController.get_logo_principal()
        if logo_path:
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    200, 60,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self._login_logo.setPixmap(scaled)
                self._login_logo.setVisible(True)
                return
        # Sin logo: ocultar el espacio
        self._login_logo.setVisible(False)
