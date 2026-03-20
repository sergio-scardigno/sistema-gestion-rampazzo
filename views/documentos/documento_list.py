"""Vista principal de Gestion Documental."""
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from controllers.documento_controller import DocumentoController
from controllers.expediente_controller import ExpedienteController
from core.auth import Session
from core.permissions import tiene_permiso
from views.widgets.filterable_table import FilterableTable


class DocumentoListView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Gestion Documental")
        title.setFont(QFont("Lato", 17, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        # Filtro por categoria
        self._cmb_categoria = QComboBox()
        self._cmb_categoria.addItem("Todas las categorias", "")
        for cat in DocumentoController.CATEGORIAS:
            self._cmb_categoria.addItem(cat, cat)
        self._cmb_categoria.currentIndexChanged.connect(lambda: self.refresh())
        header.addWidget(QLabel("Categoria:"))
        header.addWidget(self._cmb_categoria)

        # Filtro por carpeta
        self._cmb_expediente = QComboBox()
        self._cmb_expediente.addItem("Todas las carpetas", "")
        self._cmb_expediente.setMinimumWidth(200)
        self._cmb_expediente.currentIndexChanged.connect(lambda: self.refresh())
        header.addWidget(QLabel("Carpeta:"))
        header.addWidget(self._cmb_expediente)

        session = Session.get()
        if tiene_permiso(session.rol, "documentos.create"):
            btn_new = QPushButton("+ Nuevo Documento")
            btn_new.clicked.connect(self._new_document)
            header.addWidget(btn_new)

        layout.addLayout(header)

        # Tabla
        self._table = FilterableTable([
            ("nombre", "Nombre"),
            ("categoria", "Categoria"),
            ("subcategoria", "Subcategoria"),
            ("version_display", "Version"),
            ("fecha", "Fecha"),
            ("responsable", "Responsable"),
            ("tamano_display", "Tamano"),
        ])
        self._table.row_double_clicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        # Acciones
        actions = QHBoxLayout()
        if tiene_permiso(session.rol, "documentos.update"):
            btn_ver = QPushButton("Ver")
            btn_ver.clicked.connect(self._open_document)
            actions.addWidget(btn_ver)

            btn_descargar = QPushButton("Descargar")
            btn_descargar.setProperty("variant", "secondary")
            btn_descargar.clicked.connect(self._download_document)
            actions.addWidget(btn_descargar)

            btn_version = QPushButton("Nueva Version")
            btn_version.setProperty("variant", "secondary")
            btn_version.clicked.connect(self._new_version)
            actions.addWidget(btn_version)

        if tiene_permiso(session.rol, "documentos.*"):
            btn_historial = QPushButton("Historial Versiones")
            btn_historial.setProperty("variant", "secondary")
            btn_historial.clicked.connect(self._show_versiones)
            actions.addWidget(btn_historial)
        if session.rol in {"administrador", "superusuario"}:
            btn_delete = QPushButton("Eliminar")
            btn_delete.setProperty("variant", "secondary")
            btn_delete.clicked.connect(self._delete_document)
            actions.addWidget(btn_delete)

        actions.addStretch()
        layout.addLayout(actions)

    def refresh(self):
        """Cargar datos con filtros aplicados."""
        # Cargar combos de expedientes si esta vacio
        if self._cmb_expediente.count() <= 1:
            exps = ExpedienteController.get_scoped(order_by="id_expediente DESC")
            for e in exps:
                label = f'{e.get("id_expediente", "")} - {e.get("tipo_tramite", "")}'
                self._cmb_expediente.addItem(label, e["_id"])

        cat = self._cmb_categoria.currentData() or ""
        exp_id = self._cmb_expediente.currentData() or ""

        where_parts = []
        params = []

        if cat:
            where_parts.append("categoria = ?")
            params.append(cat)
        if exp_id:
            where_parts.append("id_expediente = ?")
            params.append(exp_id)

        where = " AND ".join(where_parts) if where_parts else ""

        docs = DocumentoController.get_scoped(
            where=where, params=tuple(params),
            order_by="categoria ASC, nombre ASC, version_doc DESC"
        )

        # Enriquecer datos para display
        for d in docs:
            d["version_display"] = f"v{d.get('version_doc', 1)}"
            try:
                tamano = int(d.get("tamano_bytes", 0) or 0)
            except (ValueError, TypeError):
                tamano = 0
            if tamano > 1024 * 1024:
                d["tamano_display"] = f"{tamano / (1024*1024):.1f} MB"
            elif tamano > 1024:
                d["tamano_display"] = f"{tamano / 1024:.0f} KB"
            elif tamano > 0:
                d["tamano_display"] = f"{tamano} B"
            else:
                d["tamano_display"] = "-"

        self._table.set_data(docs)

    def _selected_id(self) -> str | None:
        return self._table.get_selected_id()

    def _on_double_click(self, doc_id: str):
        self._open_document_by_id(doc_id)

    def _open_document(self):
        doc_id = self._selected_id()
        if not doc_id:
            QMessageBox.information(self, "Atencion", "Seleccione un documento.")
            return
        self._open_document_by_id(doc_id)

    def _open_document_by_id(self, doc_id: str):
        doc = DocumentoController.get_by_id(doc_id)
        if not doc:
            return
        ruta = doc.get("ruta_archivo", "")
        if not ruta:
            QMessageBox.warning(self, "Error", "El documento no tiene archivo asociado.")
            return

        local_path = DocumentoController.ensure_local_file(doc_id)
        if local_path and local_path.is_file():
            from views.documentos.documento_viewer import DocumentoViewerDialog
            dlg = DocumentoViewerDialog(local_path, self)
            dlg.exec()
        else:
            QMessageBox.warning(
                self, "Error",
                f"No se pudo obtener el archivo.\n"
                f"No existe localmente ni se pudo descargar del servidor.\n\n"
                f"Ruta registrada: {ruta}",
            )

    def _download_document(self):
        doc_id = self._selected_id()
        if not doc_id:
            QMessageBox.information(self, "Atencion", "Seleccione un documento.")
            return
        doc = DocumentoController.get_by_id(doc_id)
        if not doc:
            return
        ruta = doc.get("ruta_archivo", "")
        local_path = DocumentoController.ensure_local_file(doc_id)
        if not local_path or not local_path.is_file():
            QMessageBox.warning(self, "Error", f"No se pudo descargar el archivo:\n{ruta}")
            return
        destino, _ = QFileDialog.getSaveFileName(self, "Guardar archivo como", Path(local_path).name)
        if not destino:
            return
        try:
            Path(destino).write_bytes(Path(local_path).read_bytes())
            QMessageBox.information(self, "Ok", "Archivo descargado correctamente.")
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"No se pudo guardar el archivo:\n{exc}")

    def _new_document(self):
        from views.documentos.documento_form import DocumentoFormDialog
        dlg = DocumentoFormDialog(parent=self)
        if dlg.exec():
            self.refresh()

    def _new_version(self):
        doc_id = self._selected_id()
        if not doc_id:
            QMessageBox.information(self, "Atencion", "Seleccione un documento.")
            return
        from views.documentos.documento_form import NuevaVersionDialog
        dlg = NuevaVersionDialog(doc_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _show_versiones(self):
        doc_id = self._selected_id()
        if not doc_id:
            QMessageBox.information(self, "Atencion", "Seleccione un documento.")
            return
        from views.documentos.documento_form import VersionesDialog
        dlg = VersionesDialog(doc_id, parent=self)
        dlg.exec()

    def _delete_document(self):
        doc_id = self._selected_id()
        if not doc_id:
            QMessageBox.information(self, "Atencion", "Seleccione un documento.")
            return
        ok = QMessageBox.question(
            self,
            "Confirmar",
            "Eliminar este documento? Esta accion ocultara el documento del sistema.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        if DocumentoController.delete(doc_id):
            QMessageBox.information(self, "Ok", "Documento eliminado correctamente.")
            self.refresh()
        else:
            QMessageBox.warning(self, "Error", "No se pudo eliminar el documento.")
