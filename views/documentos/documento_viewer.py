"""Visor integrado de documentos (imagenes, PDF y texto)."""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap, QPainter
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QFileDialog, QScrollArea, QWidget, QPlainTextEdit
)

try:
    import pymupdf as fitz  # PyMuPDF (nombre moderno)
except Exception:  # pragma: no cover
    try:
        import fitz  # PyMuPDF (compatibilidad versiones previas)
    except Exception:  # pragma: no cover
        fitz = None


class DocumentoViewerDialog(QDialog):
    """Dialogo para ver, descargar e imprimir archivos permitidos."""

    IMG_EXTS = {".png", ".jpg", ".jpeg"}
    TXT_EXTS = {".txt"}
    PDF_EXTS = {".pdf"}

    def __init__(self, file_path: Path, parent=None):
        super().__init__(parent)
        self._file_path = file_path
        self._ext = file_path.suffix.lower()
        self._pdf_doc = None
        self._pdf_page_index = 0

        self.setWindowTitle(f"Visor - {file_path.name}")
        self.resize(900, 650)

        layout = QVBoxLayout(self)

        title = QLabel(file_path.name)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(title)

        self._content_area = QScrollArea()
        self._content_area.setWidgetResizable(True)
        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(8, 8, 8, 8)
        self._content_area.setWidget(self._content_widget)
        layout.addWidget(self._content_area, 1)

        self._pdf_nav = QHBoxLayout()
        self._btn_prev = QPushButton("Anterior")
        self._btn_prev.clicked.connect(self._prev_pdf_page)
        self._pdf_nav.addWidget(self._btn_prev)
        self._lbl_page = QLabel("")
        self._pdf_nav.addWidget(self._lbl_page)
        self._btn_next = QPushButton("Siguiente")
        self._btn_next.clicked.connect(self._next_pdf_page)
        self._pdf_nav.addWidget(self._btn_next)
        self._pdf_nav.addStretch()
        layout.addLayout(self._pdf_nav)

        actions = QHBoxLayout()
        actions.addStretch()
        btn_download = QPushButton("Descargar")
        btn_download.clicked.connect(self._download_copy)
        actions.addWidget(btn_download)
        btn_print = QPushButton("Imprimir")
        btn_print.clicked.connect(self._print_current)
        actions.addWidget(btn_print)
        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        actions.addWidget(btn_close)
        layout.addLayout(actions)

        self._viewer_label = None
        self._text_view = None

        self._load_content()

    def _clear_content(self):
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _load_content(self):
        self._clear_content()
        self._btn_prev.setVisible(False)
        self._btn_next.setVisible(False)
        self._lbl_page.setVisible(False)

        if self._ext in self.IMG_EXTS:
            self._show_image(self._file_path)
        elif self._ext in self.TXT_EXTS:
            self._show_text(self._file_path)
        elif self._ext in self.PDF_EXTS:
            self._show_pdf(self._file_path)
        else:
            QMessageBox.warning(self, "Formato no soportado", "Tipo de archivo no soportado.")

    def _show_image(self, path: Path):
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            QMessageBox.warning(self, "Error", "No se pudo cargar la imagen.")
            return
        self._viewer_label = QLabel()
        self._viewer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._viewer_label.setPixmap(pixmap)
        self._content_layout.addWidget(self._viewer_label)

    def _show_text(self, path: Path):
        self._text_view = QPlainTextEdit()
        self._text_view.setReadOnly(True)
        self._text_view.setPlainText(path.read_text(encoding="utf-8", errors="replace"))
        self._content_layout.addWidget(self._text_view)

    def _show_pdf(self, path: Path):
        if fitz is None:
            QMessageBox.warning(
                self,
                "Dependencia faltante",
                "No se puede previsualizar PDF porque falta PyMuPDF (pymupdf).",
            )
            return
        try:
            self._pdf_doc = fitz.open(str(path))
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"No se pudo abrir el PDF:\n{exc}")
            return

        self._btn_prev.setVisible(True)
        self._btn_next.setVisible(True)
        self._lbl_page.setVisible(True)
        self._viewer_label = QLabel()
        self._viewer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._content_layout.addWidget(self._viewer_label)
        self._render_pdf_page()

    def _render_pdf_page(self):
        if not self._pdf_doc:
            return
        page = self._pdf_doc.load_page(self._pdf_page_index)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        qpix = QPixmap.fromImage(img.copy())
        self._viewer_label.setPixmap(qpix)
        self._lbl_page.setText(f"Pagina {self._pdf_page_index + 1} / {self._pdf_doc.page_count}")
        self._btn_prev.setEnabled(self._pdf_page_index > 0)
        self._btn_next.setEnabled(self._pdf_page_index < self._pdf_doc.page_count - 1)

    def _prev_pdf_page(self):
        if self._pdf_doc and self._pdf_page_index > 0:
            self._pdf_page_index -= 1
            self._render_pdf_page()

    def _next_pdf_page(self):
        if self._pdf_doc and self._pdf_page_index < self._pdf_doc.page_count - 1:
            self._pdf_page_index += 1
            self._render_pdf_page()

    def _download_copy(self):
        dst, _ = QFileDialog.getSaveFileName(self, "Guardar copia", self._file_path.name)
        if not dst:
            return
        try:
            Path(dst).write_bytes(self._file_path.read_bytes())
            QMessageBox.information(self, "Ok", "Archivo descargado correctamente.")
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"No se pudo guardar la copia:\n{exc}")

    def _print_current(self):
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            if self._ext in self.TXT_EXTS and self._text_view:
                self._text_view.print_(printer)
                return

            painter = QPainter(printer)
            if self._ext in self.IMG_EXTS:
                img = QImage(str(self._file_path))
                rect = painter.viewport()
                scaled = img.scaled(rect.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                painter.drawImage(rect.x(), rect.y(), scaled)
            elif self._ext in self.PDF_EXTS and self._pdf_doc:
                for i in range(self._pdf_doc.page_count):
                    if i > 0:
                        printer.newPage()
                    page = self._pdf_doc.load_page(i)
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                    img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
                    rect = painter.viewport()
                    scaled = img.scaled(rect.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    painter.drawImage(rect.x(), rect.y(), scaled)
            painter.end()
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"No se pudo imprimir:\n{exc}")
