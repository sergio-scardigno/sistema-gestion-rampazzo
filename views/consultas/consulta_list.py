"""Vista listado de Consultas (CRM)."""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox, QComboBox
)
from PySide6.QtGui import QFont

from views.widgets.filterable_table import FilterableTable
from controllers.consulta_controller import ConsultaController

# Mapeo de valores internos de estado a labels visibles en UI
_ESTADO_LABELS = {
    "Convertido en expediente": "Convertido en carpeta",
}

COLUMNS = [
    ("id_consulta", "ID"),
    ("fecha_ingreso", "Fecha"),
    ("canal", "Canal"),
    ("nombre", "Nombre"),
    ("telefono", "Telefono"),
    ("motivo", "Motivo"),
    ("estado_display", "Estado"),
    ("operador", "Operador"),
]


class ConsultaListView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Consultas (CRM)")
        title.setFont(QFont("Lato", 17, QFont.Weight.Bold))
        header.addWidget(title)
        header.addStretch()

        self._cmb_estado = QComboBox()
        self._cmb_estado.addItem("Todos los estados", "")
        for e in ConsultaController.ESTADOS:
            label = _ESTADO_LABELS.get(e, e)
            self._cmb_estado.addItem(label, e)
        self._cmb_estado.currentIndexChanged.connect(self.refresh)
        header.addWidget(self._cmb_estado)

        btn_new = QPushButton("+ Nueva Consulta")
        btn_new.clicked.connect(self._new_consulta)
        header.addWidget(btn_new)

        btn_edit = QPushButton("Editar")
        btn_edit.setProperty("variant", "secondary")
        btn_edit.clicked.connect(self._edit_consulta)
        header.addWidget(btn_edit)

        btn_convert = QPushButton("Pasar a Cliente / Carpeta")
        btn_convert.setProperty("variant", "success")
        btn_convert.clicked.connect(self._convert_consulta)
        header.addWidget(btn_convert)

        layout.addLayout(header)

        self._table = FilterableTable(COLUMNS)
        self._table.row_double_clicked.connect(self._open_detail)
        layout.addWidget(self._table)

    def refresh(self):
        estado = self._cmb_estado.currentData()
        if estado:
            data = ConsultaController.get_all(
                where="estado = ?", params=(estado,), order_by="fecha_ingreso DESC"
            )
        else:
            data = ConsultaController.get_all(order_by="fecha_ingreso DESC")
        for row in data:
            raw = row.get("estado", "")
            row["estado_display"] = _ESTADO_LABELS.get(raw, raw)
        self._table.set_data(data)

    def _new_consulta(self):
        from views.consultas.consulta_form import ConsultaFormDialog
        dlg = ConsultaFormDialog(parent=self)
        if dlg.exec():
            self.refresh()

    def _edit_consulta(self):
        _id = self._table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione una consulta.")
            return
        from views.consultas.consulta_form import ConsultaFormDialog
        dlg = ConsultaFormDialog(consulta_id=_id, parent=self)
        if dlg.exec():
            self.refresh()

    def _open_detail(self, _id: str):
        self._edit_consulta()

    # ------------------------------------------------------------------
    # Flujo: Pasar a Cliente / Carpeta
    # ------------------------------------------------------------------

    def _convert_consulta(self):
        """Flujo unificado: pregunta si crear Solo Cliente o Cliente+Carpeta."""
        _id = self._table.get_selected_id()
        if not _id:
            QMessageBox.information(self, "Atencion", "Seleccione una consulta para convertir.")
            return
        consulta = ConsultaController.get_by_id(_id)
        if not consulta:
            return

        # Si ya fue convertida en carpeta, no permitir otra vez
        if consulta.get("estado") == "Convertido en expediente":
            QMessageBox.information(self, "Info", "Esta consulta ya fue convertida en carpeta.")
            return

        from controllers.cliente_controller import ClienteController
        from controllers.expediente_controller import ExpedienteController

        # Verificar si la consulta ya tiene un cliente asociado
        id_cliente_existente = consulta.get("id_cliente", "")
        cliente_existente = None
        if id_cliente_existente:
            cliente_existente = ClienteController.get_by_id(id_cliente_existente)

        # Preguntar que desea hacer
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Pasar a Cliente / Carpeta")
        msg_box.setIcon(QMessageBox.Icon.Question)

        if cliente_existente:
            nombre_cli = cliente_existente.get("nombre_completo", "")
            msg_box.setText(
                f"Esta consulta ya esta asociada al cliente:\n"
                f"{nombre_cli}\n\n"
                f"Que desea hacer?"
            )
        else:
            msg_box.setText(
                "Desea crear un nuevo cliente con los datos de esta consulta?\n\n"
                "Elija una opcion:"
            )

        btn_solo_cliente = msg_box.addButton("Solo Cliente", QMessageBox.ButtonRole.AcceptRole)
        btn_cliente_exp = msg_box.addButton("Cliente + Carpeta", QMessageBox.ButtonRole.AcceptRole)
        btn_cancelar = msg_box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)
        msg_box.setDefaultButton(btn_cancelar)
        msg_box.exec()

        clicked = msg_box.clickedButton()
        if clicked == btn_cancelar:
            return

        crear_expediente = (clicked == btn_cliente_exp)

        # Si ya tiene cliente asociado, no necesitamos crear otro
        if cliente_existente:
            if crear_expediente:
                self._crear_expediente_para_cliente(
                    _id, consulta, cliente_existente["_id"]
                )
            else:
                QMessageBox.information(
                    self, "Info",
                    f"Esta consulta ya esta asociada al cliente "
                    f"{cliente_existente.get('nombre_completo', '')}."
                )
            return

        # Abrir formulario de cliente con datos pre-cargados desde la consulta
        dni_consulta = str(consulta.get("dni", "")).strip()
        obs_parts = [f"Desde consulta #{consulta.get('id_consulta', '')}"]
        obs_consulta = consulta.get("observaciones", "").strip()
        if obs_consulta:
            obs_parts.append(obs_consulta)

        prefill = {
            "nombre_completo": consulta.get("nombre", "").upper(),
            "dni": dni_consulta,
            "telefonos": consulta.get("telefono", ""),
            "email": consulta.get("email", ""),
            "localidad": consulta.get("localidad", ""),
            "observaciones": ". ".join(obs_parts),
        }

        from views.clientes.cliente_form import ClienteFormDialog
        dlg = ClienteFormDialog(prefill_data=prefill, parent=self)
        dlg.setWindowTitle("Convertir Consulta en Cliente")
        if not dlg.exec():
            return  # usuario cancelo

        cliente = dlg.created_client
        if not cliente:
            return

        # Asociar consulta al nuevo cliente
        if crear_expediente:
            self._crear_expediente_para_cliente(_id, consulta, cliente["_id"])
        else:
            # Solo cliente: actualizar estado y vincular
            ConsultaController.update(_id, {
                "estado": "Convertido en cliente",
                "id_cliente": cliente["_id"],
            })
            QMessageBox.information(
                self, "Exito",
                f"Cliente creado exitosamente "
                f"(Carpeta N° {cliente.get('numero_carpeta', '')}).\n"
                f"La consulta quedo asociada al nuevo cliente."
            )
            self.refresh()

    def _crear_expediente_para_cliente(self, consulta_id: str, consulta: dict, cliente_id: str):
        """Crea una carpeta para el cliente y marca la consulta como convertida."""
        from controllers.expediente_controller import ExpedienteController

        ExpedienteController.create({
            "id_cliente": cliente_id,
            "tipo_tramite": "Otro",
            "responsable": consulta.get("operador", ""),
            "observaciones": consulta.get("motivo", ""),
        })

        ConsultaController.update(consulta_id, {
            "estado": "Convertido en expediente",
            "id_cliente": cliente_id,
        })

        QMessageBox.information(
            self, "Exito",
            "Cliente y carpeta creados exitosamente.\n"
            "La consulta quedo asociada al cliente."
        )
        self.refresh()
