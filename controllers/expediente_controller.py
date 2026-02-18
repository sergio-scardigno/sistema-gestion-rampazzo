"""Controlador de Expedientes."""
import logging
from datetime import date, timedelta

from controllers.base_controller import BaseController
from core import db_local

logger = logging.getLogger(__name__)


class ExpedienteController(BaseController):
    TABLE = "expedientes"
    ID_FIELD = "id_expediente"

    TIPOS_TRAMITE = [
        "Jubilacion", "Retiro por salud", "Laboral", "Amparo",
        "Pension", "PUAM", "RTI", "Reajuste", "Otro"
    ]
    ESTADOS = [
        "Activo", "En tramite", "En espera", "Guardada",
        "Desfavorable", "Favorable", "Cerrado", "Archivado"
    ]
    ESTADOS_CIERRE = ["Cerrado", "Archivado"]
    PRIORIDADES = ["Alta", "Normal", "Baja"]

    # ── Override create/update para registrar historial de estados ──

    @classmethod
    def create(cls, data: dict) -> dict:
        """Crear expediente y abrir el primer segmento de historial."""
        record = super().create(data)
        try:
            from controllers.expediente_estado_controller import abrir_segmento
            from core.auth import Session
            session = Session.get()
            usuario = session.username if session.logged_in else "sistema"
            abrir_segmento(
                id_expediente=record["_id"],
                estado=record.get("estado", "Activo"),
                responsable_username=record.get("responsable_username", ""),
                usuario=usuario,
                origen="manual",
            )
        except Exception:
            logger.warning("Error al crear segmento inicial de historial", exc_info=True)
        return record

    @classmethod
    def update(cls, _id: str, data: dict) -> dict | None:
        """Actualizar expediente y rotar historial si cambio estado o responsable."""
        existing = db_local.find_by_id(cls.TABLE, _id)
        if not existing:
            return None

        result = super().update(_id, data)
        if not result:
            return result

        try:
            old_estado = existing.get("estado", "")
            old_resp = existing.get("responsable_username", "")
            new_estado = data.get("estado", old_estado)
            new_resp = data.get("responsable_username", old_resp)

            if new_estado != old_estado or new_resp != old_resp:
                from controllers.expediente_estado_controller import rotar_segmento
                from core.auth import Session
                session = Session.get()
                usuario = session.username if session.logged_in else "sistema"
                rotar_segmento(
                    id_expediente=_id,
                    nuevo_estado=new_estado,
                    nuevo_responsable=new_resp,
                    usuario=usuario,
                    origen="manual",
                )
        except Exception:
            logger.warning("Error al rotar segmento de historial", exc_info=True)

        return result

    # ── Auto-archivado ──

    @classmethod
    def auto_archivar_cerrados(cls, dias: int = 30) -> int:
        """Pasa a Archivado los expedientes Cerrados con fecha_cierre mas antigua que `dias`.

        Retorna la cantidad de expedientes archivados.
        """
        fecha_limite = (date.today() - timedelta(days=dias)).isoformat()
        conn = db_local.get_connection()
        rows = conn.execute(
            "SELECT _id FROM expedientes "
            "WHERE estado = 'Cerrado' "
            "AND fecha_cierre IS NOT NULL AND fecha_cierre != '' "
            "AND fecha_cierre <= ?",
            (fecha_limite,)
        ).fetchall()
        conn.close()

        count = 0
        for r in rows:
            try:
                cls.update(r[0], {"estado": "Archivado"})
                count += 1
            except Exception:
                logger.warning("Error al auto-archivar expediente %s", r[0], exc_info=True)

        if count:
            logger.info("Auto-archivado: %d expedientes pasados a Archivado", count)
        return count

    @classmethod
    def search_expedientes(cls, text: str) -> list[dict]:
        return cls.search(text, [
            "id_expediente", "tipo_tramite", "estado",
            "responsable", "numero_expediente_anses", "observaciones"
        ])

    @classmethod
    def get_by_cliente(cls, id_cliente: str, limit: int = 0) -> list[dict]:
        return cls.get_all(where="id_cliente = ?", params=(id_cliente,),
                           order_by="fecha_apertura DESC", limit=limit)

    @classmethod
    def count_by_cliente(cls, id_cliente: str) -> int:
        return db_local.count("expedientes", "id_cliente = ?", (id_cliente,))

    @classmethod
    def get_scoped(cls, where: str = "", params: tuple = (),
                   order_by: str = "", limit: int = 0,
                   campo_responsable: str = "responsable_username",
                   campo_secundario: str = "responsable_secundario_username") -> list[dict]:
        """Override: expedientes tiene dos campos de responsable."""
        return super().get_scoped(
            where=where, params=params, order_by=order_by, limit=limit,
            campo_responsable=campo_responsable,
            campo_secundario=campo_secundario,
        )

    @classmethod
    def get_scoped_with_cliente(cls, where: str = "", params: tuple = (),
                                order_by: str = "", limit: int = 0) -> list[dict]:
        """get_scoped + LEFT JOIN clientes para traer numero_carpeta en una sola query."""
        from core.auth import Session
        from core.permissions import scope_where
        session = Session.get()
        sw, sp = scope_where(
            session.rol, session.username,
            "e.responsable_username", "e.responsable_secundario_username",
        )
        sql = (
            "SELECT e.*, c.numero_carpeta AS numero_carpeta_cliente, "
            "c.nombre_completo AS cli_nombre, c.dni AS cli_dni "
            "FROM expedientes e "
            "LEFT JOIN clientes c ON c._id = e.id_cliente"
        )
        all_params: tuple = ()
        conditions: list[str] = []
        if where:
            conditions.append(f"({where})")
            all_params += params
        if sw:
            conditions.append(f"({sw})")
            all_params += sp
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit:
            sql += f" LIMIT {limit}"
        conn = db_local.get_connection()
        rows = conn.execute(sql, all_params).fetchall()
        conn.close()
        return db_local.rows_to_list(rows)

    @classmethod
    def search_scoped_with_cliente(cls, text: str = "", where: str = "",
                                   params: tuple = (), order_by: str = "",
                                   limit: int = 50) -> list[dict]:
        """get_scoped + LEFT JOIN clientes con busqueda opcional por texto.

        Trae nombre_completo, dni y numero_carpeta del cliente en la misma
        query (evita N+1).
        El parametro 'text' busca en id_expediente, tipo_tramite,
        numero_expediente_anses, responsable, nombre_completo, dni y
        numero_carpeta del cliente.
        Los campos de WHERE deben usar prefijo 'e.' para expedientes.
        """
        from core.auth import Session
        from core.permissions import scope_where
        session = Session.get()
        sw, sp = scope_where(
            session.rol, session.username,
            "e.responsable_username", "e.responsable_secundario_username",
        )
        sql = (
            "SELECT e.*, c.nombre_completo AS cli_nombre, c.dni AS cli_dni, "
            "c.numero_carpeta AS numero_carpeta_cliente "
            "FROM expedientes e "
            "LEFT JOIN clientes c ON c._id = e.id_cliente"
        )
        all_params: tuple = ()
        conditions: list[str] = []
        if where:
            conditions.append(f"({where})")
            all_params += params
        if sw:
            conditions.append(f"({sw})")
            all_params += sp
        if text.strip():
            text_param = f"%{text.strip()}%"
            search_cond = (
                "(CAST(e.id_expediente AS TEXT) LIKE ?"
                " OR e.tipo_tramite LIKE ?"
                " OR e.numero_expediente_anses LIKE ?"
                " OR e.responsable LIKE ?"
                " OR c.nombre_completo LIKE ?"
                " OR c.dni LIKE ?"
                " OR c.numero_carpeta LIKE ?)"
            )
            conditions.append(search_cond)
            all_params += (text_param,) * 7
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit:
            sql += f" LIMIT {limit}"
        conn = db_local.get_connection()
        rows = conn.execute(sql, all_params).fetchall()
        conn.close()
        return db_local.rows_to_list(rows)

    @classmethod
    def tiene_tarea_activa(cls, expediente_id: str) -> bool:
        """Verifica si el expediente tiene al menos una tarea activa."""
        count = db_local.count(
            "tareas",
            "id_expediente = ? AND estado IN ('Pendiente','En curso','En espera')",
            (expediente_id,)
        )
        return count > 0

    @classmethod
    def get_sin_tarea_activa(cls) -> list[dict]:
        """Retorna expedientes activos que no tienen ninguna tarea activa."""
        conn = db_local.get_connection()
        rows = conn.execute("""
            SELECT e.* FROM expedientes e
            WHERE e.estado NOT IN ('Cerrado','Archivado')
            AND NOT EXISTS (
                SELECT 1 FROM tareas t
                WHERE t.id_expediente = e._id
                AND t.estado IN ('Pendiente','En curso','En espera')
            )
            ORDER BY e.fecha_apertura DESC
        """).fetchall()
        conn.close()
        return db_local.rows_to_list(rows)

    @classmethod
    def cerrar(cls, _id: str, resultado: str, fecha_cierre: str) -> dict | None:
        """Cierra formalmente un expediente con resultado y fecha."""
        return cls.update(_id, {
            "estado": "Cerrado",
            "resultado": resultado,
            "fecha_cierre": fecha_cierre,
        })
