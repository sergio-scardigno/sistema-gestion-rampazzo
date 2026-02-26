"""Editor rich-text para escritos y modelos de escrito."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
)

from controllers.escrito_controller import EscritoController, ModeloEscritoController

PLACEHOLDERS_DISPONIBLES = [
    "cliente.nombre_completo",
    "cliente.dni",
    "cliente.cuil",
    "cliente.fecha_nacimiento",
    "cliente.direccion",
    "cliente.localidad",
    "cliente.telefonos",
    "cliente.email",
    "expediente.id_expediente",
    "expediente.tipo_tramite",
    "expediente.rama",
    "expediente.subtipo",
    "expediente.responsable",
    "expediente.numero_expediente_anses",
    "judicial.fuero",
    "judicial.juzgado",
    "judicial.secretaria",
    "judicial.numero_expediente_judicial",
    "judicial.provincia",
    "fecha_actual",
    "fecha_actual_texto",
    "anio_actual",
]


class _BaseRichTextEditorDialog(QDialog):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(900, 650)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        header = QLabel(title)
        header.setFont(QFont("Lato", 14, QFont.Weight.Bold))
        root.addWidget(header)

        self._toolbar = QToolBar()
        root.addWidget(self._toolbar)
        self._editor = QTextEdit()
        self._editor.setAcceptRichText(True)
        self._build_toolbar()

        self._txt_titulo = QLineEdit()
        self._txt_titulo.setPlaceholderText("Titulo")
        root.addWidget(self._txt_titulo)

        root.addWidget(self._editor, stretch=1)

        self._buttons_layout = QHBoxLayout()
        self._buttons_layout.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setProperty("variant", "secondary")
        btn_cancel.clicked.connect(self.reject)
        self._buttons_layout.addWidget(btn_cancel)
        root.addLayout(self._buttons_layout)

    def _build_toolbar(self):
        act_bold = QAction("N", self)
        act_bold.setCheckable(True)
        act_bold.triggered.connect(lambda: self._editor.setFontWeight(
            QFont.Weight.Bold if act_bold.isChecked() else QFont.Weight.Normal
        ))
        self._toolbar.addAction(act_bold)

        act_italic = QAction("K", self)
        act_italic.setCheckable(True)
        act_italic.triggered.connect(self._editor.setFontItalic)
        self._toolbar.addAction(act_italic)

        act_underline = QAction("S", self)
        act_underline.setCheckable(True)
        act_underline.triggered.connect(self._editor.setFontUnderline)
        self._toolbar.addAction(act_underline)

        self._toolbar.addSeparator()

        self._cmb_font_size = QComboBox()
        for size in (9, 10, 11, 12, 14, 16, 18):
            self._cmb_font_size.addItem(str(size), size)
        self._cmb_font_size.setCurrentText("11")
        self._cmb_font_size.currentIndexChanged.connect(self._on_font_size_changed)
        self._toolbar.addWidget(self._cmb_font_size)

        self._toolbar.addSeparator()

        act_left = QAction("Izq", self)
        act_left.triggered.connect(lambda: self._editor.setAlignment(Qt.AlignmentFlag.AlignLeft))
        self._toolbar.addAction(act_left)

        act_center = QAction("Centro", self)
        act_center.triggered.connect(lambda: self._editor.setAlignment(Qt.AlignmentFlag.AlignCenter))
        self._toolbar.addAction(act_center)

        act_right = QAction("Der", self)
        act_right.triggered.connect(lambda: self._editor.setAlignment(Qt.AlignmentFlag.AlignRight))
        self._toolbar.addAction(act_right)

        act_justify = QAction("Just", self)
        act_justify.triggered.connect(lambda: self._editor.setAlignment(Qt.AlignmentFlag.AlignJustify))
        self._toolbar.addAction(act_justify)

        self._toolbar.addSeparator()

        act_bullets = QAction("Lista", self)
        act_bullets.triggered.connect(lambda: self._editor.insertHtml("<ul><li></li></ul>"))
        self._toolbar.addAction(act_bullets)

        btn_insert_field = QPushButton("Insertar campo")
        btn_insert_field.setProperty("variant", "secondary")
        btn_insert_field.clicked.connect(self._show_placeholders_menu)
        self._toolbar.addWidget(btn_insert_field)

    def _on_font_size_changed(self):
        size = self._cmb_font_size.currentData()
        if size:
            self._editor.setFontPointSize(float(size))

    def _show_placeholders_menu(self):
        menu = QMenu(self)
        for key in PLACEHOLDERS_DISPONIBLES:
            action = menu.addAction("{{" + key + "}}")
            action.triggered.connect(lambda checked=False, k=key: self._insert_placeholder(k))
        menu.exec(self.mapToGlobal(self._toolbar.geometry().bottomLeft()))

    def _insert_placeholder(self, key: str):
        self._editor.textCursor().insertText("{{" + key + "}}")


class ModeloEditorDialog(_BaseRichTextEditorDialog):
    def __init__(self, modelo_id: str = "", parent=None):
        self._modelo_id = modelo_id
        super().__init__("Editor de Modelo de Escrito", parent=parent)

        self._cmb_rama = QComboBox()
        self._cmb_rama.addItem("Todas", "")
        from controllers.expediente_controller import ExpedienteController
        for rama in ExpedienteController.RAMAS:
            self._cmb_rama.addItem(rama, rama)
        self.layout().insertWidget(3, self._cmb_rama)

        btn_save = QPushButton("Guardar modelo")
        btn_save.clicked.connect(self._save)
        self._buttons_layout.addWidget(btn_save)

        if modelo_id:
            self._load_data()

    def _load_data(self):
        model = ModeloEscritoController.get_by_id(self._modelo_id)
        if not model:
            QMessageBox.warning(self, "Error", "Modelo no encontrado.")
            self.reject()
            return
        self._txt_titulo.setText(model.get("nombre", ""))
        self._editor.setHtml(model.get("contenido_html", ""))
        self._cmb_rama.setCurrentIndex(max(0, self._cmb_rama.findData(model.get("rama", ""))))

    def _save(self):
        nombre = self._txt_titulo.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Atencion", "El nombre del modelo es obligatorio.")
            return

        data = {
            "nombre": nombre,
            "descripcion": "",
            "rama": self._cmb_rama.currentData() or "",
            "contenido_html": self._editor.toHtml(),
            "activo": 1,
        }
        if self._modelo_id:
            ModeloEscritoController.update(self._modelo_id, data)
        else:
            ModeloEscritoController.create(data)
        self.accept()


class EscritoEditorDialog(_BaseRichTextEditorDialog):
    def __init__(self, escrito_id: str, parent=None):
        self._escrito_id = escrito_id
        super().__init__("Editor de Escrito", parent=parent)

        btn_export = QPushButton("Exportar PDF")
        btn_export.setProperty("variant", "secondary")
        btn_export.clicked.connect(self._export_pdf)
        self._buttons_layout.addWidget(btn_export)

        btn_save = QPushButton("Guardar")
        btn_save.clicked.connect(self._save)
        self._buttons_layout.addWidget(btn_save)

        self._load_data()

    def _load_data(self):
        escrito = EscritoController.get_by_id(self._escrito_id)
        if not escrito:
            QMessageBox.warning(self, "Error", "Escrito no encontrado.")
            self.reject()
            return
        self._txt_titulo.setText(escrito.get("titulo", ""))
        self._editor.setHtml(escrito.get("contenido_html", ""))

    def _save(self):
        titulo = self._txt_titulo.text().strip()
        if not titulo:
            QMessageBox.warning(self, "Atencion", "El titulo es obligatorio.")
            return

        EscritoController.update(self._escrito_id, {
            "titulo": titulo,
            "contenido_html": self._editor.toHtml(),
        })
        self.accept()

    def _export_pdf(self):
        suggested_name = (self._txt_titulo.text().strip() or "escrito") + ".pdf"
        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar escrito a PDF",
            suggested_name,
            "PDF (*.pdf)",
        )
        if not out_path:
            return
        try:
            result = EscritoController.exportar_pdf(self._escrito_id, output_path=out_path)
            QMessageBox.information(self, "Exportado", f"PDF exportado en:\n{result}")
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"No se pudo exportar el PDF.\n{exc}")

