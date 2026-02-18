"""
Wizard de migracion desde Excel / CSV – 6 pasos con UI visual.
Solo accesible para rol Direccion.
"""
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QWizard,
    QWizardPage, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QCheckBox, QProgressBar, QTextEdit, QFrame, QGroupBox,
    QComboBox, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)

from utils.migration.excel_reader import load_workbook, get_sheet_info, read_sheet_data, SHEET_MAPPINGS
from utils.migration.csv_reader import read_csv_data, get_csv_info, detect_sheet_type
from utils.migration.normalizer import (
    clean_name, normalize_cuil, parse_date, detect_estado, detect_tipo_tramite
)
from utils.migration.deduplicator import find_duplicates
from utils.migration.importer import import_records


class MigrationWizardLauncher(QWidget):
    """Launcher button for the migration wizard."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # --- Seccion: Migracion Excel/CSV ---
        title = QLabel("Migracion desde Excel / CSV")
        title.setFont(QFont("Lato", 17, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "Este asistente le permite importar datos desde archivos Excel o CSV.\n"
            "El proceso normaliza automaticamente los datos (telefonos, CUILs, fechas)\n"
            "y detecta duplicados antes de importar."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color: #6b6b6b; font-size: 14px; margin: 20px;")
        layout.addWidget(desc)

        btn = QPushButton("Iniciar Asistente de Migracion")
        btn.setMinimumSize(300, 50)
        btn.setStyleSheet("font-size: 16px; font-weight: bold; font-family: 'Lato', 'Segoe UI', sans-serif;")
        btn.clicked.connect(self._launch_wizard)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # --- Separador ---
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("color: #d0d0d0; margin: 24px 60px;")
        layout.addWidget(separator)

        # --- Seccion: Exportar / Importar sistema completo ---
        title_bundle = QLabel("Exportar / Importar Sistema Completo")
        title_bundle.setFont(QFont("Lato", 18, QFont.Weight.Bold))
        title_bundle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_bundle)

        desc_bundle = QLabel(
            "Exporte toda la base de datos (clientes, carpetas, tareas, empleados,\n"
            "claves, turnos, movimientos, documentos adjuntos, etc.) a un unico\n"
            "archivo ZIP. Luego puede importarlo en otra maquina o como respaldo."
        )
        desc_bundle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_bundle.setStyleSheet("color: #6b6b6b; font-size: 14px; margin: 12px;")
        layout.addWidget(desc_bundle)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(16)

        btn_export = QPushButton("Exportar Sistema (ZIP)")
        btn_export.setMinimumSize(260, 48)
        btn_export.setStyleSheet(
            "font-size: 15px; font-weight: bold; "
            "font-family: 'Lato', 'Segoe UI', sans-serif;"
        )
        btn_export.clicked.connect(self._export_bundle)
        btn_row.addWidget(btn_export)

        btn_import = QPushButton("Importar Sistema (ZIP)")
        btn_import.setMinimumSize(260, 48)
        btn_import.setStyleSheet(
            "font-size: 15px; font-weight: bold; "
            "font-family: 'Lato', 'Segoe UI', sans-serif;"
        )
        btn_import.clicked.connect(self._import_bundle)
        btn_row.addWidget(btn_import)

        layout.addLayout(btn_row)

        layout.addStretch()

    def _launch_wizard(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo Excel o CSV", "",
            "Excel y CSV (*.xlsx *.xls *.csv);;Excel (*.xlsx *.xls);;CSV (*.csv)"
        )
        if not path:
            return
        try:
            if path.lower().endswith(".csv"):
                wizard = MigrationWizard(parent=self, mode="csv", csv_path=path)
            else:
                wb = load_workbook(path)
                wizard = MigrationWizard(wb, self)
            wizard.exec()
        except Exception as e:
            logger.exception("Error al abrir archivo de migracion: %s", path)
            QMessageBox.critical(self, "Error", f"Error al abrir el archivo:\n{e}")

    def _export_bundle(self):
        """Exportar todo el sistema a un archivo ZIP."""
        from datetime import datetime as _dt
        default_name = f"rampazzo_backup_{_dt.now().strftime('%Y%m%d_%H%M%S')}.zip"
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar exportacion del sistema", default_name,
            "Archivos ZIP (*.zip)"
        )
        if not path:
            return

        try:
            from utils.system_bundle import export_system_bundle
            QMessageBox.information(
                self, "Exportando",
                "Se iniciara la exportacion. Esto puede tardar unos segundos\n"
                "dependiendo del tamano de la base de datos y documentos."
            )
            stats = export_system_bundle(path)

            lines = [f"  - {t}: {c} registros" for t, c in stats.get("tables", {}).items() if c > 0]
            detail = "\n".join(lines)
            QMessageBox.information(
                self, "Exportacion completada",
                f"Se exporto el sistema correctamente a:\n{path}\n\n"
                f"Total: {stats.get('total_rows', 0)} registros\n"
                f"Archivos adjuntos: {stats.get('files_copied', 0)}\n\n"
                f"Detalle por tabla:\n{detail}"
            )
        except Exception as e:
            logger.exception("Error al exportar bundle")
            QMessageBox.critical(
                self, "Error de Exportacion",
                f"Ocurrio un error al exportar:\n{e}"
            )

    def _import_bundle(self):
        """Importar sistema completo desde un archivo ZIP."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo ZIP de exportacion", "",
            "Archivos ZIP (*.zip)"
        )
        if not path:
            return

        reply = QMessageBox.warning(
            self, "Confirmar Importacion",
            "ATENCION: Esta operacion creara una nueva base de datos\n"
            "a partir del archivo ZIP seleccionado.\n\n"
            "La base de datos actual NO se eliminara, pero la aplicacion\n"
            "se reconfigurara para usar la nueva base.\n\n"
            "Debera reiniciar la aplicacion para que los cambios tengan efecto.\n\n"
            "Desea continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            from utils.system_bundle import import_system_bundle
            stats = import_system_bundle(path)

            lines = [f"  - {t}: {c} registros" for t, c in stats.get("tables", {}).items() if c > 0]
            detail = "\n".join(lines)
            QMessageBox.information(
                self, "Importacion completada",
                f"Se importo el sistema correctamente.\n\n"
                f"Nueva base de datos: {stats.get('new_db_path', '')}\n"
                f"Nuevo directorio de documentos: {stats.get('new_docs_dir', '')}\n\n"
                f"Total: {stats.get('total_rows', 0)} registros\n"
                f"Archivos restaurados: {stats.get('files_restored', 0)}\n\n"
                f"Detalle por tabla:\n{detail}\n\n"
                f"IMPORTANTE: Debe reiniciar la aplicacion para\n"
                f"cargar la nueva base de datos."
            )
        except Exception as e:
            logger.exception("Error al importar bundle")
            QMessageBox.critical(
                self, "Error de Importacion",
                f"Ocurrio un error al importar:\n{e}"
            )

    def refresh(self):
        pass


class MigrationWizard(QWizard):
    def __init__(self, workbook=None, parent=None, *, mode="excel", csv_path=None):
        super().__init__(parent)
        self.setWindowTitle("Asistente de Migracion")
        self.setMinimumSize(950, 700)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        self._mode = mode  # "excel" or "csv"
        self._wb = workbook
        self._csv_path = csv_path or ""
        self._csv_sheet_type = ""
        self._selected_sheets = []
        self._raw_records = []
        self._normalized_records = []
        self._duplicates = []
        self._merge_groups = []

        self.addPage(Step1SelectSheets(self))
        self.addPage(Step2MapColumns(self))
        self.addPage(Step3Normalize(self))
        self.addPage(Step4Deduplicate(self))
        self.addPage(Step5Review(self))
        self.addPage(Step6Import(self))


class Step1SelectSheets(QWizardPage):
    def __init__(self, wizard):
        super().__init__()
        self._wizard = wizard
        self._checks: dict = {}
        self._csv_combo: QComboBox | None = None
        self._csv_info_label: QLabel | None = None
        self._csv_mapping_label: QLabel | None = None
        self._csv_preview_table: QTableWidget | None = None

        layout = QVBoxLayout(self)

        if wizard._mode == "csv":
            self._build_csv_ui(layout)
        else:
            self._build_excel_ui(layout)

    # ---- Excel mode UI ----

    def _build_excel_ui(self, layout):
        self.setTitle("Paso 1: Seleccionar Hojas")
        self.setSubTitle("Seleccione las hojas del Excel que desea importar.")

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)

        sheets_info = get_sheet_info(self._wizard._wb)
        for info in sheets_info:
            name = info["name"]
            cb = QCheckBox(f'{name}  ({info["rows"]} filas)')
            cb.setChecked(info["recommended"])
            cb.setStyleSheet("font-size: 13px; padding: 6px; color: #1a1a1a;")
            if info["has_mapping"]:
                cb.setToolTip("Mapeo automatico disponible")
            content_layout.addWidget(cb)
            self._checks[name] = cb

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    # ---- CSV mode UI ----

    def _build_csv_ui(self, layout):
        self.setTitle("Paso 1: Seleccionar Tipo de Plantilla")
        self.setSubTitle("Seleccione el tipo de datos que contiene el archivo CSV.")

        import os
        file_label = QLabel(f"Archivo: {os.path.basename(self._wizard._csv_path)}")
        file_label.setStyleSheet("color: #4a4a4a; margin-bottom: 12px; font-size: 13px;")
        file_label.setWordWrap(True)
        layout.addWidget(file_label)

        combo_label = QLabel("Tipo de plantilla:")
        combo_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(combo_label)

        self._csv_combo = QComboBox()
        self._csv_combo.setStyleSheet("font-size: 13px; padding: 4px;")
        for key in sorted(SHEET_MAPPINGS.keys()):
            self._csv_combo.addItem(key)
        self._csv_combo.currentTextChanged.connect(self._update_csv_preview)
        layout.addWidget(self._csv_combo)

        self._csv_info_label = QLabel("")
        self._csv_info_label.setStyleSheet(
            "background: #f5ecd0; color: #8a6914; padding: 10px; border-radius: 6px; "
            "font-weight: 600; margin-top: 12px;"
        )
        self._csv_info_label.setWordWrap(True)
        layout.addWidget(self._csv_info_label)

        self._csv_mapping_label = QLabel("")
        self._csv_mapping_label.setStyleSheet(
            "color: #2d8f4e; font-weight: 600; margin-top: 8px;"
        )
        self._csv_mapping_label.setWordWrap(True)
        layout.addWidget(self._csv_mapping_label)

        self._csv_preview_table = QTableWidget()
        self._csv_preview_table.setMaximumHeight(150)
        self._csv_preview_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._csv_preview_table)

        layout.addStretch()

        # Auto-detectar tipo de plantilla por headers del CSV
        detected = detect_sheet_type(self._wizard._csv_path)
        if detected:
            idx = self._csv_combo.findText(detected)
            if idx >= 0:
                self._csv_combo.setCurrentIndex(idx)

        if self._csv_combo.count() > 0:
            self._update_csv_preview(self._csv_combo.currentText())

    def _update_csv_preview(self, sheet_type):
        if not sheet_type or self._csv_info_label is None:
            return
        try:
            info = get_csv_info(self._wizard._csv_path, sheet_type)
            self._csv_info_label.setText(
                f"Filas con datos: {info['rows']}  |  "
                f"Columnas detectadas: {info['columns']}"
            )

            mapping = SHEET_MAPPINGS.get(sheet_type, {})
            cols = mapping.get("columns", {})
            if cols:
                self._csv_mapping_label.setText(
                    "Mapeo: "
                    + " | ".join(
                        f"Col{k} -> {v}" for k, v in sorted(cols.items())
                    )
                )
            else:
                self._csv_mapping_label.setText("Sin mapeo predefinido.")

            preview = info.get("preview", [])
            if preview:
                all_cols = sorted(
                    {k for p in preview for k in p.keys()},
                    key=lambda c: int(c.replace("Col", "")) if c.startswith("Col") else 0,
                )
                self._csv_preview_table.setColumnCount(len(all_cols))
                self._csv_preview_table.setHorizontalHeaderLabels(all_cols)
                self._csv_preview_table.setRowCount(len(preview))
                for row_idx, row_data in enumerate(preview):
                    for col_idx, col_name in enumerate(all_cols):
                        val = row_data.get(col_name, "")
                        self._csv_preview_table.setItem(
                            row_idx, col_idx, QTableWidgetItem(str(val))
                        )
            else:
                self._csv_preview_table.setRowCount(0)
                self._csv_preview_table.setColumnCount(0)
        except Exception as e:
            logger.exception("Error leyendo CSV")
            self._csv_info_label.setText(f"Error leyendo CSV: {e}")

    # ---- Validation ----

    def validatePage(self):
        if self._wizard._mode == "csv":
            sheet_type = self._csv_combo.currentText() if self._csv_combo else ""
            if not sheet_type:
                QMessageBox.warning(
                    self, "Atencion", "Seleccione un tipo de plantilla."
                )
                return False
            self._wizard._csv_sheet_type = sheet_type
            self._wizard._selected_sheets = [sheet_type]
            return True

        selected = [name for name, cb in self._checks.items() if cb.isChecked()]
        if not selected:
            QMessageBox.warning(self, "Atencion", "Seleccione al menos una hoja.")
            return False
        self._wizard._selected_sheets = selected
        return True


class Step2MapColumns(QWizardPage):
    def __init__(self, wizard):
        super().__init__()
        self._wizard = wizard
        self.setTitle("Paso 2: Mapeo de Columnas")
        self.setSubTitle("Verifique el mapeo automatico de columnas para cada hoja.")

    def initializePage(self):
        # Clear previous layout
        if self.layout():
            while self.layout().count():
                item = self.layout().takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            QVBoxLayout(self)

        layout = self.layout()

        if self._wizard._mode == "csv":
            info_label = QLabel(
                "Se aplicara el mapeo de columnas seleccionado al archivo CSV.\n"
                "Las columnas se mapean por posicion (Col1, Col2, ...)."
            )
        else:
            info_label = QLabel(
                "El sistema detecto automaticamente la estructura de cada hoja.\n"
                "Los mapeos predefinidos ya estan configurados para el Excel de Rampazzo."
            )
        info_label.setStyleSheet("color: #4a4a4a; margin-bottom: 12px;")
        layout.addWidget(info_label)

        for sheet_name in self._wizard._selected_sheets:
            group = QGroupBox(sheet_name)
            gl = QVBoxLayout(group)

            mapping = SHEET_MAPPINGS.get(sheet_name, {})
            cols = mapping.get("columns", {})

            if cols:
                lbl = QLabel(
                    " | ".join([f"Col{k} -> {v}" for k, v in sorted(cols.items())])
                )
                lbl.setWordWrap(True)
                lbl.setStyleSheet("color: #2d8f4e; font-weight: 600;")
                gl.addWidget(lbl)
            else:
                lbl = QLabel("Sin mapeo predefinido - se importaran las primeras columnas como datos genericos.")
                lbl.setStyleSheet("color: #a07c30;")
                gl.addWidget(lbl)

            layout.addWidget(group)

    def validatePage(self):
        self._wizard._raw_records = []
        if self._wizard._mode == "csv":
            records = read_csv_data(
                self._wizard._csv_path, self._wizard._csv_sheet_type
            )
            self._wizard._raw_records.extend(records)
        else:
            for sheet_name in self._wizard._selected_sheets:
                records = read_sheet_data(self._wizard._wb, sheet_name)
                self._wizard._raw_records.extend(records)
        return True


class Step3Normalize(QWizardPage):
    def __init__(self, wizard):
        super().__init__()
        self._wizard = wizard
        self.setTitle("Paso 3: Normalizacion Automatica")
        self.setSubTitle("Preview de datos normalizados. Puede editar cualquier celda.")

    def initializePage(self):
        if self.layout():
            while self.layout().count():
                item = self.layout().takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            QVBoxLayout(self)

        layout = self.layout()

        # Normalize all records
        self._wizard._normalized_records = []
        stats = {"phones": 0, "emails": 0, "cuils_fixed": 0, "dates_fixed": 0}

        for raw in self._wizard._raw_records:
            normalized = dict(raw)

            # Clean name
            raw_name = str(raw.get("nombre_completo", ""))
            if raw_name:
                name_data = clean_name(raw_name)
                normalized["nombre_completo"] = name_data["nombre"]
                normalized["telefonos"] = name_data["telefonos"]
                if name_data["telefonos"]:
                    stats["phones"] += len(name_data["telefonos"])
                if name_data["email"]:
                    normalized["email"] = name_data["email"]
                    stats["emails"] += 1
                if name_data["notas"]:
                    existing_notes = normalized.get("notas", "") or ""
                    normalized["notas"] = (existing_notes + " " + name_data["notas"]).strip()

            # Normalize CUIL
            raw_cuil = raw.get("cuil")
            if raw_cuil:
                cuil_data = normalize_cuil(raw_cuil)
                normalized["cuil"] = cuil_data["cuil"]
                if cuil_data["cuil_secundario"]:
                    normalized["cuil_secundario"] = cuil_data["cuil_secundario"]
                    stats["cuils_fixed"] += 1

            # Parse dates
            for date_field in ["fecha_apertura", "fecha_control"]:
                raw_date = raw.get(date_field)
                if raw_date:
                    parsed = parse_date(raw_date)
                    if parsed != str(raw_date):
                        stats["dates_fixed"] += 1
                    normalized[date_field] = parsed

            # Detect estado
            obs = str(raw.get("observaciones", "") or "")
            estado_raw = str(raw.get("estado", "") or "")
            if not estado_raw and obs:
                normalized["estado"] = detect_estado(obs)

            # Detect tipo tramite
            tipo_resp = str(raw.get("tipo_responsable", "") or "")
            if tipo_resp:
                tr = detect_tipo_tramite(tipo_resp)
                normalized["tipo_tramite"] = tr["tipo"]
                normalized["responsable"] = tr["responsable"]

            self._wizard._normalized_records.append(normalized)

        # Stats display
        stats_text = (
            f"Se extrajeron {stats['phones']} telefonos del campo nombre  |  "
            f"Se extrajeron {stats['emails']} emails  |  "
            f"Se normalizaron {stats['cuils_fixed']} CUILs dobles  |  "
            f"Se corrigieron {stats['dates_fixed']} fechas"
        )
        stats_label = QLabel(stats_text)
        stats_label.setStyleSheet(
            "background: #f5ecd0; color: #8a6914; padding: 10px; border-radius: 6px; font-weight: 600;"
        )
        stats_label.setWordWrap(True)
        layout.addWidget(stats_label)

        # Preview table
        table = QTableWidget()
        preview = self._wizard._normalized_records[:100]
        cols = ["nombre_completo", "cuil", "telefonos", "email", "clave_mi_anses", "clave_fiscal",
                "estado", "tipo_tramite", "responsable", "fecha_apertura", "_source_sheet"]
        table.setColumnCount(len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.setRowCount(len(preview))
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        for row_idx, rec in enumerate(preview):
            for col_idx, col_name in enumerate(cols):
                val = rec.get(col_name, "")
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                table.setItem(row_idx, col_idx, QTableWidgetItem(str(val) if val else ""))

        layout.addWidget(table)

        total_label = QLabel(
            f"Total registros: {len(self._wizard._normalized_records)} "
            f"(mostrando primeros 100 en preview)"
        )
        total_label.setStyleSheet("color: #6b6b6b; margin-top: 8px;")
        layout.addWidget(total_label)


class Step4Deduplicate(QWizardPage):
    def __init__(self, wizard):
        super().__init__()
        self._wizard = wizard
        self.setTitle("Paso 4: Deduplicacion")
        self.setSubTitle("Se detectaron posibles duplicados entre las hojas.")

    def initializePage(self):
        if self.layout():
            while self.layout().count():
                item = self.layout().takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            QVBoxLayout(self)

        layout = self.layout()

        self._wizard._duplicates = find_duplicates(self._wizard._normalized_records)
        dups = self._wizard._duplicates

        if not dups:
            lbl = QLabel("No se detectaron duplicados.")
            lbl.setStyleSheet("color: #2d8f4e; font-size: 16px; font-weight: 600; padding: 20px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(lbl)
            return

        lbl = QLabel(f"Se detectaron {len(dups)} posibles duplicados. Revise y decida:")
        lbl.setStyleSheet("color: #a07c30; font-weight: 600; margin-bottom: 12px;")
        layout.addWidget(lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        cl = QVBoxLayout(content)

        self._merge_checks = []

        for i, dup in enumerate(dups[:50]):  # Limit to 50 for UI performance
            frame = QFrame()
            frame.setStyleSheet("background: #ffffff; border: 1px solid #e0e0e0; border-radius: 6px; padding: 8px;")
            fl = QVBoxLayout(frame)

            a = dup["record_a"]
            b = dup["record_b"]
            header = QLabel(
                f'Duplicado #{i+1} ({dup["type"]}, confianza: {dup["confidence"]:.0%})'
            )
            header.setStyleSheet("font-weight: bold; color: #1a1a1a;")
            fl.addWidget(header)

            fl.addWidget(QLabel(
                f'  [A] {a.get("nombre_completo","")} | CUIL: {a.get("cuil","")} | '
                f'Hoja: {a.get("_source_sheet","")}'
            ))
            fl.addWidget(QLabel(
                f'  [B] {b.get("nombre_completo","")} | CUIL: {b.get("cuil","")} | '
                f'Hoja: {b.get("_source_sheet","")}'
            ))

            cb = QCheckBox("Fusionar (usar datos de A, crear un solo cliente)")
            cb.setChecked(dup["confidence"] >= 0.95)
            fl.addWidget(cb)
            self._merge_checks.append((i, cb))

            cl.addWidget(frame)

        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def validatePage(self):
        merge_groups = []
        for i, cb in self._merge_checks:
            if cb.isChecked():
                dup = self._wizard._duplicates[i]
                merge_groups.append({dup["record_a_idx"], dup["record_b_idx"]})
        self._wizard._merge_groups = merge_groups
        return True


class Step5Review(QWizardPage):
    def __init__(self, wizard):
        super().__init__()
        self._wizard = wizard
        self.setTitle("Paso 5: Revision Final")
        self.setSubTitle("Resumen de lo que se importara.")

    def initializePage(self):
        if self.layout():
            while self.layout().count():
                item = self.layout().takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            QVBoxLayout(self)

        layout = self.layout()

        total = len(self._wizard._normalized_records)
        merged = sum(len(g) - 1 for g in self._wizard._merge_groups)

        summary = QLabel(
            f"RESUMEN DE IMPORTACION\n\n"
            f"Registros totales: {total}\n"
            f"Duplicados a fusionar: {merged}\n"
            f"Registros efectivos: {total - merged}\n\n"
            f"Hojas seleccionadas: {', '.join(self._wizard._selected_sheets)}"
        )
        summary.setStyleSheet(
            "background: #ffffff; border: 1px solid #e0e0e0; border-radius: 8px; "
            "padding: 20px; font-size: 14px; color: #1a1a1a;"
        )
        layout.addWidget(summary)

        warning = QLabel(
            "ATENCION: La importacion creara clientes y expedientes en la base de datos.\n"
            "Se recomienda hacer un backup antes de continuar."
        )
        warning.setStyleSheet("color: #cc3333; font-weight: 600; margin-top: 16px;")
        layout.addWidget(warning)

        layout.addStretch()

    def validatePage(self):
        reply = QMessageBox.question(
            self, "Confirmar Importacion",
            "Esta seguro que desea proceder con la importacion?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes


class ImportWorker(QThread):
    progress = Signal(int, int, str)
    finished = Signal(object)

    def __init__(self, records, merge_groups):
        super().__init__()
        self._records = records
        self._merge_groups = merge_groups

    def run(self):
        result = import_records(
            self._records,
            self._merge_groups,
            progress_callback=lambda c, t, m: self.progress.emit(c, t, m),
        )
        self.finished.emit(result)


class Step6Import(QWizardPage):
    def __init__(self, wizard):
        super().__init__()
        self._wizard = wizard
        self.setTitle("Paso 6: Importacion")
        self.setSubTitle("Importando datos...")
        self._complete = False

    def initializePage(self):
        if self.layout():
            while self.layout().count():
                item = self.layout().takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            QVBoxLayout(self)

        layout = self.layout()

        self._progress = QProgressBar()
        self._progress.setRange(0, len(self._wizard._normalized_records))
        layout.addWidget(self._progress)

        self._lbl_status = QLabel("Iniciando importacion...")
        self._lbl_status.setStyleSheet("font-size: 14px; color: #4a4a4a; margin: 8px;")
        layout.addWidget(self._lbl_status)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(300)
        layout.addWidget(self._log)

        layout.addStretch()

        # Start import in background thread
        self._worker = ImportWorker(
            self._wizard._normalized_records,
            self._wizard._merge_groups,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, current, total, msg):
        self._progress.setValue(current)
        self._lbl_status.setText(msg)

    def _on_finished(self, result):
        self._complete = True
        self._progress.setValue(self._progress.maximum())
        self._lbl_status.setText("Importacion completada!")
        self._lbl_status.setStyleSheet("font-size: 16px; color: #2d8f4e; font-weight: bold;")

        summary = (
            f"=== RESULTADO ===\n"
            f"Clientes creados: {result.clientes_created}\n"
            f"Carpetas creadas: {result.expedientes_created}\n"
            f"Registros omitidos (fusionados): {result.skipped}\n"
            f"Errores: {len(result.errors)}\n"
        )
        if result.errors:
            summary += "\n=== ERRORES ===\n"
            for err in result.errors[:50]:
                summary += f"  - {err}\n"

        self._log.setPlainText(summary)
        self.completeChanged.emit()

    def isComplete(self):
        return self._complete
