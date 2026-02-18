"""Formulario de alta/edicion de Turno ANSES."""
import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QTextEdit, QDateEdit, QTimeEdit, QPushButton, QLabel, QComboBox,
    QMessageBox, QCheckBox, QCompleter, QScrollArea, QFrame, QWidget
)
from PySide6.QtCore import QDate, QTime, Qt, QStringListModel
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)

from controllers.turno_controller import TurnoController
from controllers.cliente_controller import ClienteController
from controllers.expediente_controller import ExpedienteController
from controllers.notificacion_controller import NotificacionController
from services import anses_oficinas_service
from config import ANSES_PROVINCIA_DEFECTO
from core.auth import Session
from core.permissions import get_active_users


class TurnoFormDialog(QDialog):
    def __init__(self, turno_id: str = None, cliente_id: str = None,
                 expediente_id: str = None, parent=None):
        super().__init__(parent)
        self._id = turno_id
        self._is_edit = turno_id is not None
        self._fixed_cliente = cliente_id
        self._fixed_expediente = expediente_id

        self.setWindowTitle("Editar Turno" if self._is_edit else "Nuevo Turno ANSES")
        self.setMinimumWidth(600)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 8, 12, 8)

        title = QLabel("Editar Turno" if self._is_edit else "Nuevo Turno ANSES")
        title.setFont(QFont("Lato", 15, QFont.Weight.Bold))
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_container = QWidget()

        form = QFormLayout(form_container)
        form.setSpacing(8)
        form.setContentsMargins(4, 4, 4, 4)

        # ── Cliente ──
        self._cmb_cliente = QComboBox()
        self._cmb_cliente.setEditable(True)
        self._cmb_cliente.addItem("-- Seleccionar cliente --", "")
        if self._fixed_cliente:
            # Solo cargar el cliente pre-seleccionado
            cli = ClienteController.get_by_id(self._fixed_cliente)
            if cli:
                label = f'{cli.get("nombre_completo", "")} | CUIL: {cli.get("cuil", "")}'
                self._cmb_cliente.addItem(label, cli["_id"])
            idx = self._cmb_cliente.findData(self._fixed_cliente)
            if idx >= 0:
                self._cmb_cliente.setCurrentIndex(idx)
                self._cmb_cliente.setEnabled(False)
        else:
            clientes = ClienteController.get_all(
                order_by="nombre_completo ASC", limit=100)
            for c in clientes:
                label = f'{c.get("nombre_completo", "")} | CUIL: {c.get("cuil", "")}'
                self._cmb_cliente.addItem(label, c["_id"])
        # Cuando cambia el cliente, re-evaluar la oficina sugerida
        self._cmb_cliente.currentIndexChanged.connect(self._on_cliente_changed)
        form.addRow("Cliente *:", self._cmb_cliente)

        # ── Carpeta ──
        self._cmb_expediente = QComboBox()
        self._cmb_expediente.setEditable(True)
        self._cmb_expediente.addItem("-- Sin carpeta --", "")
        if self._fixed_expediente:
            # Solo cargar la carpeta pre-seleccionada
            exp_data = ExpedienteController.get_by_id(self._fixed_expediente)
            if exp_data:
                label = (
                    f'Carpeta #{exp_data.get("id_expediente", "")} - '
                    f'{exp_data.get("tipo_tramite", "")} ({exp_data.get("responsable", "")})'
                )
                self._cmb_expediente.addItem(label, exp_data["_id"])
            idx = self._cmb_expediente.findData(self._fixed_expediente)
            if idx >= 0:
                self._cmb_expediente.setCurrentIndex(idx)
                self._cmb_expediente.setEnabled(False)
        else:
            exps = ExpedienteController.get_scoped(
                where="estado NOT IN ('Cerrado','Archivado')",
                order_by="id_expediente DESC",
                limit=100,
            )
            for e in exps:
                label = (
                    f'Carpeta #{e.get("id_expediente", "")} - '
                    f'{e.get("tipo_tramite", "")} ({e.get("responsable", "")})'
                )
                self._cmb_expediente.addItem(label, e["_id"])
        form.addRow("Carpeta:", self._cmb_expediente)

        # ── Fecha y hora ──
        self._date_turno = QDateEdit()
        self._date_turno.setCalendarPopup(True)
        self._date_turno.setDate(QDate.currentDate().addDays(7))
        self._date_turno.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Fecha turno *:", self._date_turno)

        self._time_hora = QTimeEdit()
        self._time_hora.setDisplayFormat("HH:mm")
        self._time_hora.setTime(QTime(9, 0))
        form.addRow("Hora turno *:", self._time_hora)

        # ── Provincia (para filtrar oficinas) ──
        self._cmb_provincia = QComboBox()
        provincias = TurnoController.get_provincias()
        for p in provincias:
            self._cmb_provincia.addItem(p)
        # Seleccionar provincia por defecto
        idx_prov = self._cmb_provincia.findText(ANSES_PROVINCIA_DEFECTO)
        if idx_prov >= 0:
            self._cmb_provincia.setCurrentIndex(idx_prov)
        self._cmb_provincia.currentTextChanged.connect(self._on_provincia_changed)
        form.addRow("Provincia:", self._cmb_provincia)

        # ── Oficina ──
        self._cmb_oficina = QComboBox()
        self._cmb_oficina.setEditable(True)
        # No permitir insertar valores que no esten en la lista
        self._cmb_oficina.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        # Completer para buscar escribiendo (filtra por contenido)
        oficina_completer = QCompleter()
        oficina_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        oficina_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        oficina_completer.setMaxVisibleItems(15)
        self._cmb_oficina.setCompleter(oficina_completer)
        # Info oficina (label visible debajo del combo)
        self._lbl_oficina_info = QLabel("")
        self._lbl_oficina_info.setWordWrap(True)
        self._lbl_oficina_info.setStyleSheet(
            "color: #6b6b6b; font-size: 11px; padding: 2px 4px; "
            "background-color: #f8f8f8; border: 1px solid #e0e0e0; border-radius: 4px;"
        )
        self._lbl_oficina_info.setVisible(False)
        # Cargar oficinas (necesita _lbl_oficina_info ya creado)
        self._load_oficinas(self._cmb_provincia.currentText())
        # activated: cuando el usuario selecciona del dropdown
        self._cmb_oficina.activated.connect(self._on_oficina_selected)
        # currentTextChanged: cuando cambia el texto (seleccion o escritura manual)
        self._cmb_oficina.currentTextChanged.connect(self._on_oficina_text_changed)
        form.addRow("Oficina ANSES *:", self._cmb_oficina)
        form.addRow("", self._lbl_oficina_info)

        # ── Tipo tramite ──
        self._cmb_tipo = QComboBox()
        for t in TurnoController.TIPOS_TRAMITE:
            self._cmb_tipo.addItem(t)
        form.addRow("Tipo tramite:", self._cmb_tipo)

        # ── Codigo turno ──
        self._txt_codigo = QLineEdit()
        self._txt_codigo.setPlaceholderText("Codigo de confirmacion de ANSES")
        form.addRow("Codigo turno:", self._txt_codigo)

        # ── Estado ──
        self._cmb_estado = QComboBox()
        for e in TurnoController.ESTADOS:
            self._cmb_estado.addItem(e)
        form.addRow("Estado:", self._cmb_estado)

        # ── Responsable ──
        self._cmb_responsable = QComboBox()
        self._cmb_responsable.setEditable(True)
        self._cmb_responsable.setPlaceholderText("Quien del estudio gestiona")
        users = get_active_users()
        for u in users:
            label = f'{u.get("nombre_completo", "")} ({u.get("username", "")})'
            self._cmb_responsable.addItem(label, u.get("username", ""))
        form.addRow("Responsable *:", self._cmb_responsable)

        # ── Documentacion lista ──
        self._chk_doc = QCheckBox("La documentacion esta preparada")
        form.addRow("Documentacion:", self._chk_doc)

        # ── Notas preparacion ──
        self._txt_notas = QTextEdit()
        self._txt_notas.setMaximumHeight(70)
        self._txt_notas.setPlaceholderText("Documentos a llevar, requisitos previos...")
        form.addRow("Notas preparacion:", self._txt_notas)

        # ── Resultado (post-turno) ──
        self._txt_resultado = QTextEdit()
        self._txt_resultado.setMaximumHeight(70)
        self._txt_resultado.setPlaceholderText("Resultado del turno (completar despues)")
        form.addRow("Resultado:", self._txt_resultado)

        # ── Requiere nuevo turno ──
        self._chk_nuevo = QCheckBox("Requiere sacar un nuevo turno")
        form.addRow("Seguimiento:", self._chk_nuevo)

        # ── Observaciones ──
        self._txt_observaciones = QTextEdit()
        self._txt_observaciones.setMaximumHeight(60)
        form.addRow("Observaciones:", self._txt_observaciones)

        scroll.setWidget(form_container)
        layout.addWidget(scroll)

        # ── Botones ──
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
        else:
            # Para turnos nuevos: intentar auto-seleccionar oficina por localidad
            self._sugerir_oficina_por_cliente()

    # ── Helpers oficinas ──

    def _load_oficinas(self, provincia: str):
        """Carga las oficinas de la provincia indicada en el combo."""
        self._cmb_oficina.blockSignals(True)
        try:
            self._cmb_oficina.clear()
            nombres = TurnoController.get_oficinas_anses(provincia)
            for i, nombre in enumerate(nombres):
                self._cmb_oficina.addItem(nombre)
                # Tooltip individual por item (visible en el dropdown)
                info = anses_oficinas_service.get_oficina_info(nombre)
                if info:
                    tip = anses_oficinas_service.formato_tooltip_oficina(info)
                    self._cmb_oficina.setItemData(i, tip, Qt.ItemDataRole.ToolTipRole)
            # Actualizar modelo del completer para filtrar al escribir
            completer = self._cmb_oficina.completer()
            if completer:
                completer.setModel(QStringListModel(nombres))
        except Exception:
            logger.warning("Error al cargar oficinas ANSES en turno_form", exc_info=True)
            if self._cmb_oficina.count() == 0:
                self._cmb_oficina.addItem("Otra")
        finally:
            self._cmb_oficina.blockSignals(False)
        # Tooltip del combo = info de la oficina seleccionada
        self._update_oficina_tooltip()

    def _on_provincia_changed(self, provincia: str):
        """Cuando cambia la provincia, recarga las oficinas."""
        self._load_oficinas(provincia)

    def _on_oficina_selected(self, index: int):
        """Cuando el usuario selecciona una oficina del dropdown."""
        self._update_oficina_tooltip()

    def _on_oficina_text_changed(self, text: str):
        """Cuando cambia el texto de la oficina (seleccion o escritura)."""
        self._update_oficina_tooltip()

    def _update_oficina_tooltip(self):
        """Actualiza el tooltip y la etiqueta visible con info de la oficina seleccionada."""
        nombre = self._cmb_oficina.currentText()
        info = anses_oficinas_service.get_oficina_info(nombre)
        if info:
            tip = anses_oficinas_service.formato_tooltip_oficina(info)
            self._cmb_oficina.setToolTip(tip)
            # Mostrar info en la etiqueta visible debajo del combo
            parts = []
            if info.get("address"):
                parts.append(f"Dir: {info['address']}")
            if info.get("city"):
                parts.append(f"Ciudad: {info['city']}")
            if info.get("schedule"):
                parts.append(f"Horario: {info['schedule']}")
            if info.get("region"):
                parts.append(info["region"])
            self._lbl_oficina_info.setText("  |  ".join(parts))
            self._lbl_oficina_info.setVisible(True)
        else:
            self._cmb_oficina.setToolTip("")
            self._lbl_oficina_info.setText("")
            self._lbl_oficina_info.setVisible(False)

    def _on_cliente_changed(self, _index: int):
        """Cuando cambia el cliente seleccionado, sugerir oficina por localidad."""
        if not self._is_edit:
            self._sugerir_oficina_por_cliente()

    def _sugerir_oficina_por_cliente(self):
        """Intenta auto-seleccionar provincia y oficina ANSES segun la localidad del cliente.

        Busca la localidad del cliente (desde sus consultas) y si encuentra una
        oficina ANSES correspondiente, la pre-selecciona en los combos.
        El usuario siempre puede cambiar la seleccion manualmente.
        """
        cliente_id = self._cmb_cliente.currentData()
        if not cliente_id:
            return

        try:
            localidad = TurnoController.get_localidad_cliente(cliente_id)
            if not localidad:
                return

            oficina = TurnoController.buscar_oficina_por_localidad(localidad)
            if not oficina:
                return

            # Seleccionar la provincia correcta
            provincia = oficina.get("province", "")
            if provincia:
                idx_p = self._cmb_provincia.findText(provincia)
                if idx_p >= 0:
                    self._cmb_provincia.setCurrentIndex(idx_p)

            # Seleccionar la oficina
            nombre_oficina = oficina.get("office_name", "")
            if nombre_oficina:
                idx_o = self._cmb_oficina.findText(nombre_oficina)
                if idx_o >= 0:
                    self._cmb_oficina.setCurrentIndex(idx_o)
                else:
                    # Si no esta en la lista (podria pasar), setear como texto
                    self._cmb_oficina.setCurrentText(nombre_oficina)
                self._update_oficina_tooltip()
        except Exception:
            logger.debug("Auto-deteccion de oficina fallo (no critico)", exc_info=True)

    def _load_data(self):
        data = TurnoController.get_by_id(self._id)
        if not data:
            self.reject()
            return

        # Cliente (asegurar que este en el combo aunque no se haya cargado)
        id_cli = data.get("id_cliente", "")
        idx = self._cmb_cliente.findData(id_cli)
        if idx < 0 and id_cli:
            cli = ClienteController.get_by_id(id_cli)
            if cli:
                label = f'{cli.get("nombre_completo", "")} | CUIL: {cli.get("cuil", "")}'
                self._cmb_cliente.addItem(label, cli["_id"])
                idx = self._cmb_cliente.findData(id_cli)
        if idx >= 0:
            self._cmb_cliente.setCurrentIndex(idx)

        # Carpeta (asegurar que este en el combo aunque no se haya cargado)
        id_exp = data.get("id_expediente", "")
        idx = self._cmb_expediente.findData(id_exp)
        if idx < 0 and id_exp:
            exp_data = ExpedienteController.get_by_id(id_exp)
            if exp_data:
                label = (
                    f'Carpeta #{exp_data.get("id_expediente", "")} - '
                    f'{exp_data.get("tipo_tramite", "")} ({exp_data.get("responsable", "")})'
                )
                self._cmb_expediente.addItem(label, exp_data["_id"])
                idx = self._cmb_expediente.findData(id_exp)
        if idx >= 0:
            self._cmb_expediente.setCurrentIndex(idx)

        # Fecha
        ft = data.get("fecha_turno", "")
        if ft and len(ft) >= 10:
            self._date_turno.setDate(QDate.fromString(ft[:10], "yyyy-MM-dd"))

        hora_str = data.get("hora_turno", "")
        if hora_str:
            parsed = QTime.fromString(hora_str, "HH:mm")
            if parsed.isValid():
                self._time_hora.setTime(parsed)
        # Oficina: detectar provincia y seleccionar
        oficina_guardada = data.get("oficina_anses", "")
        provincia_oficina = anses_oficinas_service.get_provincia_de_oficina(oficina_guardada)
        if provincia_oficina:
            idx_p = self._cmb_provincia.findText(provincia_oficina)
            if idx_p >= 0:
                self._cmb_provincia.setCurrentIndex(idx_p)
        self._cmb_oficina.setCurrentText(oficina_guardada)
        self._cmb_tipo.setCurrentText(data.get("tipo_tramite", ""))
        self._txt_codigo.setText(data.get("codigo_turno", ""))
        self._cmb_estado.setCurrentText(data.get("estado", "Pendiente"))
        resp_uname = data.get("responsable_username", "")
        idx_r = self._cmb_responsable.findData(resp_uname)
        if idx_r >= 0:
            self._cmb_responsable.setCurrentIndex(idx_r)
        elif data.get("responsable", ""):
            self._cmb_responsable.setEditText(data.get("responsable", ""))
        self._chk_doc.setChecked(bool(data.get("documentacion_lista", 0)))
        self._txt_notas.setPlainText(data.get("notas_preparacion", ""))
        self._txt_resultado.setPlainText(data.get("resultado", ""))
        self._chk_nuevo.setChecked(bool(data.get("requiere_nuevo_turno", 0)))
        self._txt_observaciones.setPlainText(data.get("observaciones", ""))

    def _save(self):
        cliente_id = self._cmb_cliente.currentData()
        if not cliente_id:
            QMessageBox.warning(self, "Atencion", "Seleccione un cliente.")
            return

        hora = self._time_hora.time().toString("HH:mm")

        resp_username = self._cmb_responsable.currentData() or ""
        resp_display = self._cmb_responsable.currentText().strip()
        if not resp_username and not resp_display:
            QMessageBox.warning(self, "Atencion", "Ingrese el responsable.")
            return

        oficina = self._cmb_oficina.currentText().strip()
        if not oficina:
            QMessageBox.warning(self, "Atencion", "Seleccione una oficina.")
            return
        # Validar que la oficina sea una de las registradas
        if self._cmb_oficina.findText(oficina) < 0:
            QMessageBox.warning(
                self, "Atencion",
                "La oficina ingresada no es valida.\n"
                "Seleccione una oficina de la lista desplegable."
            )
            self._cmb_oficina.setFocus()
            return

        responsable_legible = resp_display.split("(")[0].strip() if resp_username else resp_display

        data = {
            "id_cliente": cliente_id,
            "id_expediente": self._cmb_expediente.currentData() or "",
            "fecha_turno": self._date_turno.date().toString("yyyy-MM-dd"),
            "hora_turno": hora,
            "oficina_anses": oficina,
            "tipo_tramite": self._cmb_tipo.currentText(),
            "codigo_turno": self._txt_codigo.text().strip(),
            "estado": self._cmb_estado.currentText(),
            "responsable": responsable_legible.upper(),
            "responsable_username": resp_username,
            "documentacion_lista": 1 if self._chk_doc.isChecked() else 0,
            "notas_preparacion": self._txt_notas.toPlainText().strip(),
            "resultado": self._txt_resultado.toPlainText().strip(),
            "requiere_nuevo_turno": 1 if self._chk_nuevo.isChecked() else 0,
            "observaciones": self._txt_observaciones.toPlainText().strip(),
        }

        if self._is_edit:
            TurnoController.update(self._id, data)
        else:
            result = TurnoController.create(data)
            # Notificar al responsable (si es distinto del creador)
            session = Session.get()
            if resp_username and resp_username != session.username:
                # Nombre del cliente para el mensaje
                cli = ClienteController.get_by_id(cliente_id)
                cli_nombre = cli.get("nombre_completo", "") if cli else ""
                fecha_legible = self._date_turno.date().toString("dd/MM/yyyy")
                mensaje = (
                    f"Turno ANSES asignado: {cli_nombre} - "
                    f"{data['tipo_tramite']} el {fecha_legible} a las {hora} "
                    f"en {oficina}. Asignado por {session.nombre}."
                )
                NotificacionController.create_for_turno_asignado(
                    target_username=resp_username,
                    mensaje=mensaje,
                    id_referencia=result.get("_id", ""),
                )
        self.accept()
