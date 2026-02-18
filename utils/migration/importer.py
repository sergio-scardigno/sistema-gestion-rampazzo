"""
Importador final: toma registros normalizados y los inserta en la BD.
"""
import json
import logging

logger = logging.getLogger(__name__)

from controllers.cliente_controller import ClienteController
from controllers.expediente_controller import ExpedienteController
from controllers.tarea_controller import TareaController
from utils.validators import validate_cuil as _validate_cuil


class ImportResult:
    def __init__(self):
        self.clientes_created = 0
        self.expedientes_created = 0
        self.tareas_created = 0
        self.errors: list[str] = []
        self.skipped = 0


def _resolve_numero_carpeta(record: dict) -> str:
    """Determina el numero_carpeta para un cliente a importar.

    Usa id_carpeta del registro si es numerico y esta disponible;
    de lo contrario, genera el siguiente correlativo.
    """
    id_carpeta = str(record.get("id_carpeta", "")).strip()
    if id_carpeta and id_carpeta.isdigit():
        existing = ClienteController.get_by_numero_carpeta(id_carpeta)
        if not existing:
            return id_carpeta
    return ClienteController.get_suggested_numero_carpeta()


def _serialize_telefonos(telefonos) -> str:
    """Convierte telefonos a string JSON para almacenamiento."""
    if isinstance(telefonos, list):
        return json.dumps(telefonos, ensure_ascii=False)
    if isinstance(telefonos, str):
        return telefonos
    return "[]"


def import_records(
    normalized_records: list[dict],
    merge_groups: list[set] = None,
    progress_callback=None,
) -> ImportResult:
    """
    Importar registros normalizados a la BD.
    
    normalized_records: lista de dicts con campos normalizados
    merge_groups: conjuntos de indices que deben fusionarse
    progress_callback: callable(current, total, message)
    """
    result = ImportResult()
    total = len(normalized_records)

    # Build merge map: index -> primary index
    merge_map = {}
    if merge_groups:
        for group in merge_groups:
            primary = min(group)
            for idx in group:
                if idx != primary:
                    merge_map[idx] = primary

    # Track created clients by cuil to avoid re-creation
    cuil_to_client_id = {}

    for i, record in enumerate(normalized_records):
        if progress_callback:
            progress_callback(i + 1, total, f"Procesando registro {i + 1} de {total}")

        # Skip if merged into another
        if i in merge_map:
            result.skipped += 1
            continue

        try:
            cuil = record.get("cuil", "")
            # Pre-validar CUIL: limpiar si es invalido para no abortar el registro
            if cuil:
                cuil_ok, _ = _validate_cuil(cuil)
                if not cuil_ok:
                    cuil = ""

            existing_client_id = cuil_to_client_id.get(cuil) if cuil else None

            if existing_client_id:
                client_id = existing_client_id
            else:
                numero_carpeta = _resolve_numero_carpeta(record)

                client_data = {
                    "numero_carpeta": numero_carpeta,
                    "nombre_completo": record.get("nombre_completo", ""),
                    "dni": record.get("dni", ""),
                    "cuil": cuil,
                    "telefonos": _serialize_telefonos(record.get("telefonos", [])),
                    "email": record.get("email", ""),
                    "direccion": record.get("direccion", ""),
                    "clave_mi_anses": record.get("clave_mi_anses", ""),
                    "clave_fiscal": record.get("clave_fiscal", ""),
                    "observaciones": record.get("notas", ""),
                }

                client = ClienteController.create(client_data)
                client_id = client["_id"]
                result.clientes_created += 1

                if cuil:
                    cuil_to_client_id[cuil] = client_id

            # Create expediente if there's type/state info
            tipo = record.get("tipo_tramite", "")
            estado = record.get("estado", "")
            nro_exp = record.get("numero_expediente", "")
            responsable = record.get("responsable", "")

            if tipo or estado or nro_exp:
                exp_data = {
                    "id_cliente": client_id,
                    "tipo_tramite": tipo or "Otro",
                    "estado": estado or "Activo",
                    "responsable": responsable,
                    "fecha_apertura": record.get("fecha_apertura", ""),
                    "numero_expediente_anses": nro_exp,
                    "clave_mi_anses": record.get("clave_mi_anses", ""),
                    "clave_fiscal": record.get("clave_fiscal", ""),
                    "observaciones": record.get("observaciones", ""),
                }
                ExpedienteController.create(exp_data)
                result.expedientes_created += 1

        except Exception as e:
            logger.warning("Error importando fila %d", i + 1, exc_info=True)
            result.errors.append(f"Fila {i + 1}: {str(e)[:100]}")

    return result
