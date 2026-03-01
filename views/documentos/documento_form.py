"""Formularios de Gestion Documental."""
import os
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QDateEdit, QPushButton, QLabel, QComboBox, QMessageBox,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QCompleter, QScrollArea, QFrame, QWidget,
)
from PySide6.QtCore import Qt, QDate, QTimer
from PySide6.QtGui import QFont

from controllers.documento_controller import DocumentoController
from controllers.expediente_controller import ExpedienteController
from controllers.cliente_controller import ClienteController
from core.auth import Session
from core.permissions import get_active_users
from views.widgets.no_wheel_datetime import NoWheelDateEdit

_INITIAL_EXP_LIMIT = 50
_SEARCH_DEBOUNCE_MS = 300
_SEARCH_MIN_CHARS = 2
_SEARCH_RESULT_LIMIT = 50


class DocumentoFormDialog(QDialog):
    """Formulario para crear/editar un documento."""

    def __init__(self, doc_id: str = None, expediente_id: str = None, parent=None):
        super().__init__(parent)
        self._id = doc_id
        self._is_edit = doc_id is not None
        self._expediente_id_preset = expediente_id

        self.setWindowTitle("Editar Documento" if self._is_edit else "Nuevo Documento")
        self.setMinimumSize(550, 500)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("Editar Documento" if self._is_edit else "Nuevo Documento")
        title.setFont(QFont("Lato", 15, QFont.Weight.Bold))
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_container = QWidget()
        form = QFormLayout(form_container)
        form.setContentsMargins(4, 4, 4, 4)
        form.setSpacing(8)

        # Carpeta (con busqueda incremental por N° carpeta, DNI o nombre)
        self._cmb_expediente = QComboBox()
        self._cmb_expediente.setEditable(True)
        self._cmb_expediente.lineEdit().setPlaceholderText(
            "Escriba N\u00b0 carpeta, DNI o nombre para buscar..."
        )
        self._cmb_expediente.addItem("-- Sin carpeta --", "")

        if expediente_id:
            self._ensure_expediente_in_combo(expediente_id)
            idx = self._cmb_expediente.findData(expediente_id)
            if idx >= 0:
                self._cmb_expediente.setCurrentIndex(idx)
        else:
            self._load_initial_expedientes()

        # Autocompletado por subcadena
        exp_completer = QCompleter(self)
        exp_completer.setModel(self._cmb_expediente.model())
        exp_completer.setCompletionColumn(0)
        exp_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        exp_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        exp_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        exp_completer.activated[str].connect(self._on_expediente_completer_activated)
        self._cmb_expediente.setCompleter(exp_completer)

        # Busqueda incremental con debounce
        self._exp_search_timer = QTimer(self)
        self._exp_search_timer.setSingleShot(True)
        self._exp_search_timer.setInterval(_SEARCH_DEBOUNCE_MS)
        self._exp_search_timer.timeout.connect(self._search_expedientes)
        if not expediente_id:
            self._cmb_expediente.lineEdit().textEdited.connect(
                lambda _: self._exp_search_timer.start()
            )

        form.addRow("Carpeta:", self._cmb_expediente)

        # Nombre
        self._txt_nombre = QLineEdit()
        self._txt_nombre.setPlaceholderText("Nombre del documento")
        form.addRow("Nombre *:", self._txt_nombre)

        # Categoria
        self._cmb_categoria = QComboBox()
        for cat in DocumentoController.CATEGORIAS:
            self._cmb_categoria.addItem(cat)
        self._cmb_categoria.currentTextChanged.connect(self._on_categoria_changed)
        form.addRow("Categoria *:", self._cmb_categoria)

        # Subcategoria
        self._cmb_subcategoria = QComboBox()
        self._on_categoria_changed(self._cmb_categoria.currentText())
        form.addRow("Subcategoria:", self._cmb_subcategoria)

        # Descripcion
        self._txt_descripcion = QTextEdit()
        self._txt_descripcion.setMaximumHeight(60)
        self._txt_descripcion.setPlaceholderText("Descripcion del documento (opcional)")
        form.addRow("Descripcion:", self._txt_descripcion)

        # Archivo
        archivo_layout = QHBoxLayout()
        self._txt_ruta = QLineEdit()
        self._txt_ruta.setReadOnly(True)
        self._txt_ruta.setPlaceholderText("Seleccionar archivo (opcional)...")
        archivo_layout.addWidget(self._txt_ruta)
        btn_browse = QPushButton("Examinar...")
        btn_browse.clicked.connect(self._browse_file)
        archivo_layout.addWidget(btn_browse)
        form.addRow("Archivo:", archivo_layout)

        # Fecha
        self._date = NoWheelDateEdit()
        self._date.setCalendarPopup(True)
        self._date.setDate(QDate.currentDate())
        self._date.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Fecha:", self._date)

        # Responsable
        self._cmb_responsable = QComboBox()
        self._cmb_responsable.setEditable(True)
        users = get_active_users()
        for u in users:
            label = f'{u.get("nombre_completo", "")} ({u.get("username", "")})'
            self._cmb_responsable.addItem(label, u.get("username", ""))
        # Preseleccionar usuario actual
        session = Session.get()
        if session.logged_in:
            idx_u = self._cmb_responsable.findData(session.username)
            if idx_u >= 0:
                self._cmb_responsable.setCurrentIndex(idx_u)
        form.addRow("Responsable:", self._cmb_responsable)

        scroll.setWidget(form_container)
        layout.addWidget(scroll)

        # Buttons
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

    def _on_categoria_changed(self, categoria: str):
        self._cmb_subcategoria.clear()
        subcats = DocumentoController.SUBCATEGORIAS.get(categoria, ["General"])
        for s in subcats:
            self._cmb_subcategoria.addItem(s)

    # ------------------------------------------------------------------
    # Helpers de carga de carpetas (combo expediente)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_expediente_label(e: dict) -> str:
        """Construir etiqueta informativa para un item del combo de carpetas."""
        partes = [f'Carpeta #{e.get("id_expediente", "")}']
        nro_carpeta = e.get("numero_carpeta_cliente", "")
        if nro_carpeta:
            partes.append(f'N\u00b0 {nro_carpeta}')
        partes.append(e.get("tipo_tramite", ""))
        cli_nombre = e.get("cli_nombre", "")
        cli_dni = e.get("cli_dni", "")
        if cli_nombre:
            cli_label = cli_nombre
            if cli_dni:
                cli_label += f' DNI {cli_dni}'
            partes.append(cli_label)
        return " - ".join(p for p in partes if p)

    def _load_initial_expedientes(self):
        """Carga las N carpetas mas recientes con datos del cliente (JOIN)."""
        exps = ExpedienteController.search_scoped_with_cliente(
            where="e.estado NOT IN ('Cerrado','Archivado')",
            order_by="e.id_expediente DESC",
            limit=_INITIAL_EXP_LIMIT,
        )
        for e in exps:
            self._cmb_expediente.addItem(self._build_expediente_label(e), e["_id"])

    def _search_expedientes(self):
        """Busqueda incremental de carpetas al escribir en el combo."""
        text = self._cmb_expediente.lineEdit().text().strip()
        if len(text) < _SEARCH_MIN_CHARS:
            return
        results = ExpedienteController.search_scoped_with_cliente(
            text=text,
            order_by="e.id_expediente DESC",
            limit=_SEARCH_RESULT_LIMIT,
        )
        current_data = self._cmb_expediente.currentData()
        self._cmb_expediente.blockSignals(True)
        self._cmb_expediente.clear()
        self._cmb_expediente.addItem("-- Sin carpeta --", "")
        for e in results:
            self._cmb_expediente.addItem(self._build_expediente_label(e), e["_id"])
        if current_data:
            idx = self._cmb_expediente.findData(current_data)
            if idx >= 0:
                self._cmb_expediente.setCurrentIndex(idx)
        self._cmb_expediente.blockSignals(False)
        self._cmb_expediente.lineEdit().setText(text)
        self._cmb_expediente.lineEdit().setCursorPosition(len(text))
        self._cmb_expediente.showPopup()

    def _on_expediente_completer_activated(self, text: str):
        """Seleccionar la carpeta del combo cuando se elige del autocompletado."""
        idx = self._cmb_expediente.findText(text)
        if idx >= 0:
            self._cmb_expediente.setCurrentIndex(idx)

    def _ensure_expediente_in_combo(self, exp_id: str) -> int:
        """Asegura que una carpeta este en el combo, cargandola si es necesario.

        Retorna el indice del item en el combo, o -1 si no se pudo agregar.
        """
        if not exp_id:
            return -1
        idx = self._cmb_expediente.findData(exp_id)
        if idx >= 0:
            return idx
        exp_data = ExpedienteController.get_by_id(exp_id)
        if not exp_data:
            return -1
        cid = exp_data.get("id_cliente", "")
        if cid:
            cli = ClienteController.get_by_id(cid)
            if cli:
                exp_data["cli_nombre"] = cli.get("nombre_completo", "")
                exp_data["cli_dni"] = cli.get("dni", "")
                exp_data["numero_carpeta_cliente"] = cli.get("numero_carpeta", "")
        label = self._build_expediente_label(exp_data)
        self._cmb_expediente.addItem(label, exp_data["_id"])
        return self._cmb_expediente.findData(exp_data["_id"])

    # ------------------------------------------------------------------

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Documento", "",
            "Todos los archivos (*.*)"
        )
        if path:
            self._txt_ruta.setText(path)

    def _load_data(self):
        data = DocumentoController.get_by_id(self._id)
        if not data:
            QMessageBox.warning(self, "Error", "Documento no encontrado.")
            self.reject()
            return

        # Asegurar que la carpeta este en el combo aunque no se haya cargado
        id_exp = data.get("id_expediente", "")
        idx = self._cmb_expediente.findData(id_exp)
        if idx < 0 and id_exp:
            idx = self._ensure_expediente_in_combo(id_exp)
        if idx >= 0:
            self._cmb_expediente.setCurrentIndex(idx)
        self._txt_nombre.setText(data.get("nombre", ""))
        self._cmb_categoria.setCurrentText(data.get("categoria", ""))
        self._cmb_subcategoria.setCurrentText(data.get("subcategoria", ""))
        self._txt_descripcion.setPlainText(data.get("descripcion", ""))
        self._txt_ruta.setText(data.get("ruta_archivo", ""))
        fd = data.get("fecha", "")
        if fd and len(fd) >= 10:
            self._date.setDate(QDate.fromString(fd[:10], "yyyy-MM-dd"))
        resp_uname = data.get("responsable_username", "")
        idx_r = self._cmb_responsable.findData(resp_uname)
        if idx_r >= 0:
            self._cmb_responsable.setCurrentIndex(idx_r)
        elif data.get("responsable", ""):
            self._cmb_responsable.setEditText(data.get("responsable", ""))

    def _save(self):
        nombre = self._txt_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Atencion", "El nombre del documento es obligatorio.")
            return

        ruta = self._txt_ruta.text().strip()

        # Calcular tamano
        tamano = 0
        if ruta and Path(ruta).exists():
            tamano = Path(ruta).stat().st_size

        data = {
            "id_expediente": self._cmb_expediente.currentData() or "",
            "nombre": nombre,
            "categoria": self._cmb_categoria.currentText(),
            "subcategoria": self._cmb_subcategoria.currentText(),
            "descripcion": self._txt_descripcion.toPlainText().strip(),
            "ruta_archivo": ruta,
            "tamano_bytes": tamano,
            "fecha": self._date.date().toString("yyyy-MM-dd"),
            "responsable": (self._cmb_responsable.currentText().split("(")[0].strip()
                            if self._cmb_responsable.currentData()
                            else self._cmb_responsable.currentText().strip()),
            "responsable_username": self._cmb_responsable.currentData() or "",
        }

        if self._is_edit:
            DocumentoController.update(self._id, data)
        else:
            DocumentoController.create(data)
        self.accept()


class NuevaVersionDialog(QDialog):
    """Dialogo para crear una nueva version de un documento existente."""

    def __init__(self, doc_id: str, parent=None):
        super().__init__(parent)
        self._doc_id = doc_id
        self.setWindowTitle("Nueva Version del Documento")
        self.setMinimumSize(450, 300)

        layout = QVBoxLayout(self)

        doc = DocumentoController.get_by_id(doc_id)
        if not doc:
            QMessageBox.warning(self, "Error", "Documento no encontrado.")
            self.reject()
            return

        title = QLabel(f"Nueva version de: {doc.get('nombre', '')}")
        title.setFont(QFont("Lato", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        info = QLabel(f"Version actual: v{doc.get('version_doc', 1)}")
        info.setStyleSheet("color: #6b6b6b;")
        layout.addWidget(info)

        form = QFormLayout()

        # Archivo nuevo
        archivo_layout = QHBoxLayout()
        self._txt_ruta = QLineEdit()
        self._txt_ruta.setReadOnly(True)
        self._txt_ruta.setPlaceholderText("Seleccionar nuevo archivo...")
        archivo_layout.addWidget(self._txt_ruta)
        btn_browse = QPushButton("Examinar...")
        btn_browse.clicked.connect(self._browse_file)
        archivo_layout.addWidget(btn_browse)
        form.addRow("Nuevo archivo *:", archivo_layout)

        # Notas de version
        self._txt_notas = QTextEdit()
        self._txt_notas.setMaximumHeight(80)
        self._txt_notas.setPlaceholderText("Notas sobre los cambios en esta version...")
        form.addRow("Notas version:", self._txt_notas)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("variant", "secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_save = QPushButton("Crear Version")
        btn_save.clicked.connect(self._save)
        btn_layout.addWidget(btn_save)
        layout.addLayout(btn_layout)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Nuevo Archivo", "",
            "Todos los archivos (*.*)"
        )
        if path:
            self._txt_ruta.setText(path)

    def _save(self):
        ruta = self._txt_ruta.text().strip()
        if not ruta:
            QMessageBox.warning(self, "Atencion", "Debe seleccionar un archivo.")
            return

        session = Session.get()
        resp = session.username if session.logged_in else ""

        result = DocumentoController.crear_nueva_version(
            self._doc_id,
            ruta,
            notas=self._txt_notas.toPlainText().strip(),
            responsable=resp,
        )
        if result:
            QMessageBox.information(self, "Exito", "Nueva version creada correctamente.")
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "No se pudo crear la nueva version.")


class VersionesDialog(QDialog):
    """Dialogo para ver el historial de versiones de un documento."""

    def __init__(self, doc_id: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Historial de Versiones")
        self.setMinimumSize(650, 400)

        layout = QVBoxLayout(self)

        doc = DocumentoController.get_by_id(doc_id)
        if not doc:
            QMessageBox.warning(self, "Error", "Documento no encontrado.")
            self.reject()
            return

        title = QLabel(f"Versiones de: {doc.get('nombre', '')}")
        title.setFont(QFont("Lato", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        versiones = DocumentoController.get_versiones(doc_id)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "Version", "Fecha", "Responsable", "Tamano", "Notas", "Archivo"
        ])
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setRowCount(len(versiones))

        for i, v in enumerate(versiones):
            table.setItem(i, 0, QTableWidgetItem(f"v{v.get('version_doc', 1)}"))
            table.setItem(i, 1, QTableWidgetItem(v.get("fecha", "")))
            table.setItem(i, 2, QTableWidgetItem(v.get("responsable", "")))
            tamano = v.get("tamano_bytes", 0) or 0
            if tamano > 1024 * 1024:
                tam_str = f"{tamano / (1024*1024):.1f} MB"
            elif tamano > 1024:
                tam_str = f"{tamano / 1024:.0f} KB"
            else:
                tam_str = f"{tamano} B" if tamano else "-"
            table.setItem(i, 3, QTableWidgetItem(tam_str))
            table.setItem(i, 4, QTableWidgetItem(v.get("notas_version", "")))
            ruta = v.get("ruta_archivo", "")
            table.setItem(i, 5, QTableWidgetItem(Path(ruta).name if ruta else "-"))

        layout.addWidget(table)

        # Boton cerrar
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)
