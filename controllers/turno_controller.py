"""Controlador de Turnos ANSES."""
from datetime import datetime, timedelta

from controllers.base_controller import BaseController
from services import anses_oficinas_service


class TurnoController(BaseController):
    TABLE = "turnos"
    ID_FIELD = "id_turno"

    ESTADOS = [
        "Pendiente", "Confirmado", "Asistido",
        "No asistido", "Reprogramado", "Cancelado"
    ]

    TIPOS_TRAMITE = [
        "Jubilacion", "PNC", "PUAM", "Retiro por invalidez",
        "Pension derivada", "Asignaciones", "Desempleo",
        "Progresar", "SUAF", "Otro"
    ]

    # Compatibilidad: propiedad que devuelve oficinas de la provincia por defecto
    @classmethod
    def get_oficinas_anses(cls, provincia: str = "") -> list[str]:
        """Retorna nombres de oficinas para una provincia (+ opcion 'Otra').

        Si no se indica provincia, usa la configurada por defecto.
        """
        if not provincia:
            from config import ANSES_PROVINCIA_DEFECTO
            provincia = ANSES_PROVINCIA_DEFECTO
        nombres = anses_oficinas_service.get_oficinas_nombres(provincia)
        nombres.append("Otra")
        return nombres

    @classmethod
    def get_provincias(cls) -> list[str]:
        """Retorna las provincias disponibles en el JSON de oficinas."""
        return anses_oficinas_service.get_provincias()

    @classmethod
    def get_oficinas_detalle(cls, provincia: str = "") -> list[dict]:
        """Retorna oficinas con detalle completo para una provincia."""
        if not provincia:
            from config import ANSES_PROVINCIA_DEFECTO
            provincia = ANSES_PROVINCIA_DEFECTO
        return anses_oficinas_service.get_oficinas(provincia)

    @classmethod
    def get_oficina_info(cls, nombre: str) -> dict | None:
        """Busca info de una oficina por nombre."""
        return anses_oficinas_service.get_oficina_info(nombre)

    # Mantener OFICINAS_ANSES como propiedad de clase para compatibilidad
    @classmethod
    def _oficinas_default(cls) -> list[str]:
        return cls.get_oficinas_anses()

    # Atributo de clase como fallback (para codigo que acceda directamente)
    OFICINAS_ANSES = [
        "UDAI Resistencia",
        "UDAI Saenz Pena",
        "UDAI Barranqueras",
        "UDAI Villa Angela",
        "UDAI Charata",
        "UDAI General San Martin",
        "UDAI Corrientes",
        "Otra",
    ]

    @classmethod
    def get_localidad_cliente(cls, cliente_id: str) -> str:
        """Obtener la localidad de un cliente.

        Retorna el string de localidad o cadena vacia.
        """
        from controllers.cliente_controller import ClienteController
        cliente = ClienteController.get_by_id(cliente_id)
        if cliente and cliente.get("localidad", "").strip():
            return cliente["localidad"].strip()
        return ""

    @classmethod
    def buscar_oficina_por_localidad(cls, nombre_localidad: str) -> dict | None:
        """Busca la oficina ANSES correspondiente a una localidad."""
        return anses_oficinas_service.buscar_oficina_por_localidad(nombre_localidad)

    @classmethod
    def get_by_cliente(cls, id_cliente: str) -> list[dict]:
        """Obtener todos los turnos de un cliente."""
        return cls.get_all(
            where="id_cliente = ?", params=(id_cliente,),
            order_by="fecha_turno DESC, hora_turno DESC"
        )

    @classmethod
    def get_by_expediente(cls, id_expediente: str) -> list[dict]:
        """Obtener todos los turnos de un expediente."""
        return cls.get_all(
            where="id_expediente = ?", params=(id_expediente,),
            order_by="fecha_turno DESC, hora_turno DESC"
        )

    @classmethod
    def get_proximos(cls, dias: int = 7) -> list[dict]:
        """Obtener turnos futuros dentro de los proximos N dias."""
        today = datetime.now().strftime("%Y-%m-%d")
        limit_date = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
        return cls.get_all(
            where="fecha_turno >= ? AND fecha_turno <= ? AND estado IN ('Pendiente','Confirmado')",
            params=(today, limit_date),
            order_by="fecha_turno ASC, hora_turno ASC"
        )

    @classmethod
    def get_hoy(cls) -> list[dict]:
        """Obtener turnos de hoy."""
        today = datetime.now().strftime("%Y-%m-%d")
        return cls.get_all(
            where="fecha_turno = ?", params=(today,),
            order_by="hora_turno ASC"
        )

    @classmethod
    def get_sin_documentacion(cls) -> list[dict]:
        """Obtener turnos confirmados/pendientes sin documentacion preparada."""
        today = datetime.now().strftime("%Y-%m-%d")
        return cls.get_all(
            where="documentacion_lista = 0 AND estado IN ('Pendiente','Confirmado') AND fecha_turno >= ?",
            params=(today,),
            order_by="fecha_turno ASC"
        )

    @classmethod
    def get_pendientes_resultado(cls) -> list[dict]:
        """Obtener turnos asistidos que aun no tienen resultado cargado."""
        return cls.get_all(
            where="estado = 'Asistido' AND (resultado IS NULL OR resultado = '')",
            order_by="fecha_turno DESC"
        )

    @classmethod
    def marcar_asistido(cls, _id: str) -> dict | None:
        """Cambiar estado a Asistido."""
        return cls.update(_id, {"estado": "Asistido"})

    @classmethod
    def reprogramar(cls, _id: str, nueva_fecha: str, nueva_hora: str,
                    nueva_oficina: str = "") -> dict | None:
        """Marcar turno como Reprogramado y crear uno nuevo."""
        existing = cls.get_by_id(_id)
        if not existing:
            return None
        # Marcar el turno original como reprogramado
        cls.update(_id, {"estado": "Reprogramado"})
        # Crear nuevo turno con los mismos datos base
        nuevo = {
            "id_cliente": existing.get("id_cliente", ""),
            "id_expediente": existing.get("id_expediente", ""),
            "fecha_turno": nueva_fecha,
            "hora_turno": nueva_hora,
            "oficina_anses": nueva_oficina or existing.get("oficina_anses", ""),
            "tipo_tramite": existing.get("tipo_tramite", ""),
            "responsable": existing.get("responsable", ""),
            "responsable_username": existing.get("responsable_username", ""),
            "estado": "Pendiente",
            "documentacion_lista": existing.get("documentacion_lista", 0),
            "notas_preparacion": existing.get("notas_preparacion", ""),
            "observaciones": f"Reprogramado desde turno #{existing.get('id_turno', '')}",
            "id_constancia_doc": "",
        }
        return cls.create(nuevo)
