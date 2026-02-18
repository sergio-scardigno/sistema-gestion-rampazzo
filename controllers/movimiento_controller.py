"""Controlador de Movimientos economicos."""
from controllers.base_controller import BaseController
from core import db_local


class MovimientoController(BaseController):
    TABLE = "movimientos"
    ID_FIELD = "id_movimiento"

    TIPOS = ["Honorario", "Gasto"]
    ESTADOS = ["Pendiente", "Parcial", "Cancelado", "Incobrable"]
    FORMAS_PAGO = ["Efectivo", "Transferencia", "Tarjeta", "Cheque", "Otro"]

    @classmethod
    def get_by_expediente(cls, id_expediente: str) -> list[dict]:
        return cls.get_all(where="id_expediente = ?", params=(id_expediente,),
                           order_by="fecha DESC")

    @classmethod
    def get_by_cliente(cls, id_cliente: str) -> list[dict]:
        return cls.get_all(where="id_cliente = ?", params=(id_cliente,),
                           order_by="fecha DESC")

    @classmethod
    def saldo_cliente(cls, id_cliente: str) -> float:
        conn = db_local.get_connection()
        row = conn.execute(
            "SELECT COALESCE(SUM(saldo), 0) FROM movimientos WHERE id_cliente = ?",
            (id_cliente,)
        ).fetchone()
        conn.close()
        return float(row[0]) if row else 0.0
