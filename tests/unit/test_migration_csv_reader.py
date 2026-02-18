"""Tests unitarios para utils/migration/csv_reader.py"""
import pytest

from utils.migration.csv_reader import read_csv_data, get_csv_info, _detect_data_start


# =====================================================================
# read_csv_data
# =====================================================================

class TestReadCsvData:
    """Tests para lectura de CSV con distintos mappings."""

    def test_carpetas_mapping(self, tmp_path):
        """CARPETAS: header_row=2, data_start=3. Filas 1-2 se ignoran."""
        csv_content = (
            "CARPETAS;;;;;;\n"
            "id_carpeta;nombre_completo;cuil;observaciones;clave_mi_anses;clave_fiscal;fecha_apertura\n"
            '1;PEREZ JUAN;20-12345678-3;Obs;mianses;fiscal;2025-01-15\n'
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        records = read_csv_data(str(csv_file), "CARPETAS")
        assert len(records) == 1
        rec = records[0]
        assert rec["id_carpeta"] == "1"
        assert rec["nombre_completo"] == "PEREZ JUAN"
        assert rec["cuil"] == "20-12345678-3"
        assert rec["observaciones"] == "Obs"
        assert rec["clave_mi_anses"] == "mianses"
        assert rec["clave_fiscal"] == "fiscal"
        assert rec["fecha_apertura"] == "2025-01-15"
        assert rec["_source_sheet"] == "CARPETAS"
        assert rec["_source_row"] == 3

    def test_rti_desfavorables_no_header(self, tmp_path):
        """RTI DESFAVORABLES: data_start=1, sin encabezado."""
        csv_content = (
            '1;PEREZ JUAN;20-12345678-3;mianses;Desfavorable;RTI/MARIANO;2025-01-15;EX-2025-0001;2025-02-01\n'
            '2;GOMEZ MARIA;27-87654321-9;;Favorable;JUB/DAIRA;15/01/2025;;01/02/2025\n'
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        records = read_csv_data(str(csv_file), "RTI DESFAVORABLES")
        assert len(records) == 2

        assert records[0]["nombre_completo"] == "PEREZ JUAN"
        assert records[0]["estado"] == "Desfavorable"
        assert records[0]["tipo_responsable"] == "RTI/MARIANO"
        assert records[0]["numero_expediente"] == "EX-2025-0001"
        assert records[0]["fecha_control"] == "2025-02-01"
        assert records[0]["_source_row"] == 1

        assert records[1]["nombre_completo"] == "GOMEZ MARIA"
        assert records[1]["estado"] == "Favorable"
        assert "numero_expediente" not in records[1]  # vacio -> no se incluye

    def test_falta_edad_skips_rows(self, tmp_path):
        """FALTA EDAD: data_start=4. Las primeras 3 filas se ignoran."""
        csv_content = (
            "FALTA EDAD;;;\n"
            ";;;\n"
            "id_carpeta;nombre_completo;cuil;observaciones\n"
            '1;PEREZ JUAN;20-12345678-3;FALTA EDAD\n'
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        records = read_csv_data(str(csv_file), "FALTA EDAD")
        assert len(records) == 1
        assert records[0]["nombre_completo"] == "PEREZ JUAN"
        assert records[0]["observaciones"] == "FALTA EDAD"
        assert records[0]["_source_row"] == 4

    def test_seguimiento_exp(self, tmp_path):
        """SEGUIMIENTO EXP: data_start=4, 8 columnas."""
        csv_content = (
            "SEGUIMIENTO EXP;;;;;;;\n"
            ";;;;;;;\n"
            "id;nombre;cuil;nro;estado;clave;fecha_ap;fecha_ctrl\n"
            '1;PEREZ JUAN;20-12345678-3;EX-2025-0001;En tramite;mianses;2025-01-15;2025-02-01\n'
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        records = read_csv_data(str(csv_file), "SEGUIMIENTO EXP")
        assert len(records) == 1
        assert records[0]["numero_expediente"] == "EX-2025-0001"
        assert records[0]["estado"] == "En tramite"
        assert records[0]["clave_mi_anses"] == "mianses"
        assert records[0]["fecha_control"] == "2025-02-01"

    def test_base_de_datos(self, tmp_path):
        """BASE DE DATOS: data_start=3, solo 2 columnas."""
        csv_content = (
            "nombre_completo;direccion\n"
            ";\n"
            "PEREZ JUAN;Mitre 123\n"
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        records = read_csv_data(str(csv_file), "BASE DE DATOS")
        assert len(records) == 1
        assert records[0]["nombre_completo"] == "PEREZ JUAN"
        assert records[0]["direccion"] == "Mitre 123"

    def test_turnos_anses_nuevo(self, tmp_path):
        """TURNOS ANSES NUEVO: data_start=1, 2 columnas."""
        csv_content = '1;Turno programado UDAI\n2;Observacion del turno\n'
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        records = read_csv_data(str(csv_file), "TURNOS ANSES NUEVO")
        assert len(records) == 2
        assert records[0]["id_carpeta"] == "1"
        assert records[0]["observaciones"] == "Turno programado UDAI"

    def test_empty_csv_returns_empty(self, tmp_path):
        """CSV vacio retorna lista vacia."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("", encoding="utf-8")

        records = read_csv_data(str(csv_file), "CARPETAS")
        assert records == []

    def test_empty_rows_skipped(self, tmp_path):
        """Filas sin datos son ignoradas."""
        csv_content = (
            ";;;\n"
            ";;;\n"
            ";;;\n"
            '1;PEREZ JUAN;20-12345678-3;Obs\n'
            ";;;\n"
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        records = read_csv_data(str(csv_file), "FALTA EDAD")
        assert len(records) == 1
        assert records[0]["nombre_completo"] == "PEREZ JUAN"

    def test_multiple_data_rows(self, tmp_path):
        """Multiples filas de datos se leen correctamente."""
        csv_content = (
            "CARPETAS;;;;;;\n"
            "encabezado;;;;;;\n"
            '1;PEREZ JUAN;20-12345678-3;Obs1;clave1;fiscal1;2025-01-15\n'
            '2;GOMEZ MARIA;27-87654321-9;Obs2;clave2;fiscal2;2025-02-20\n'
            '3;LOPEZ ANA;23-11223344-5;Obs3;clave3;fiscal3;2025-03-10\n'
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        records = read_csv_data(str(csv_file), "CARPETAS")
        assert len(records) == 3
        assert records[0]["nombre_completo"] == "PEREZ JUAN"
        assert records[1]["nombre_completo"] == "GOMEZ MARIA"
        assert records[2]["nombre_completo"] == "LOPEZ ANA"
        assert records[2]["_source_row"] == 5

    def test_quoted_fields(self, tmp_path):
        """Campos con comillas dobles se parsean correctamente."""
        csv_content = (
            "titulo;;;;;;\n"
            "encabezado;;;;;;\n"
            '1;"PEREZ, JUAN CARLOS";"20-12345678-3";"Obs con; punto y coma";;;\n'
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        records = read_csv_data(str(csv_file), "CARPETAS")
        assert len(records) == 1
        assert records[0]["nombre_completo"] == "PEREZ, JUAN CARLOS"
        assert records[0]["observaciones"] == "Obs con; punto y coma"

    def test_utf8_bom_handled(self, tmp_path):
        """CSV con BOM (UTF-8-BOM) se lee correctamente."""
        csv_content = (
            '1;PEREZ JUAN;20-12345678-3;;;RTI/MARIANO;2025-01-15;;\n'
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_bytes(b'\xef\xbb\xbf' + csv_content.encode("utf-8"))

        records = read_csv_data(str(csv_file), "RTI DESFAVORABLES")
        assert len(records) == 1
        assert records[0]["id_carpeta"] == "1"

    def test_unknown_sheet_type_uses_defaults(self, tmp_path):
        """Tipo desconocido: data_start=1, sin columns -> lista vacia."""
        csv_content = 'dato1;dato2;dato3\n'
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        records = read_csv_data(str(csv_file), "TIPO_INEXISTENTE")
        assert records == []

    # ---- Auto-deteccion de header ----

    def test_carpetas_header_row1_data_row2(self, tmp_path):
        """CSV real: header en fila 1, datos desde fila 2 (sin fila titulo).

        El mapping de CARPETAS dice data_start=3, pero la auto-deteccion
        debe encontrar el header en fila 1 y empezar datos en fila 2.
        """
        csv_content = (
            "id_carpeta;nombre_completo;cuil;observaciones;clave_mi_anses;clave_fiscal;fecha_apertura\n"
            "1; CABRAL PRIMO 2241559697 ;20057079704;guaRDADA;20227814374;;5/05/2023\n"
            "2;PAIZ MARIA CRISTINA;;CARP EN ROMI;;;18/04/2022\n"
            "3;ROCHA HECTOR 2241540600;;CARP NO TIENE;Franco2004;;\n"
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        records = read_csv_data(str(csv_file), "CARPETAS")
        assert len(records) == 3
        assert records[0]["nombre_completo"] == "CABRAL PRIMO 2241559697"
        assert records[0]["cuil"] == "20057079704"
        assert records[0]["_source_row"] == 2
        assert records[1]["nombre_completo"] == "PAIZ MARIA CRISTINA"
        assert records[2]["nombre_completo"] == "ROCHA HECTOR 2241540600"

    def test_falta_edad_header_row1_data_row2(self, tmp_path):
        """FALTA EDAD con header en fila 1 (sin filas titulo/vacias previas)."""
        csv_content = (
            "id_carpeta;nombre_completo;cuil;observaciones\n"
            '1;PEREZ JUAN;20-12345678-3;FALTA EDAD\n'
            '2;GOMEZ MARIA;27-87654321-9;EN ESPERA\n'
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        records = read_csv_data(str(csv_file), "FALTA EDAD")
        assert len(records) == 2
        assert records[0]["nombre_completo"] == "PEREZ JUAN"
        assert records[0]["_source_row"] == 2

    def test_seguimiento_exp_header_row1(self, tmp_path):
        """SEGUIMIENTO EXP con header en fila 1 (data_start original=4)."""
        csv_content = (
            "id_carpeta;nombre_completo;cuil;numero_expediente;estado;clave_mi_anses;fecha_apertura;fecha_control\n"
            '1;PEREZ JUAN;20-12345678-3;EX-001;En tramite;mianses;2025-01-15;2025-02-01\n'
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        records = read_csv_data(str(csv_file), "SEGUIMIENTO EXP")
        assert len(records) == 1
        assert records[0]["nombre_completo"] == "PEREZ JUAN"
        assert records[0]["_source_row"] == 2


# =====================================================================
# _detect_data_start
# =====================================================================

class TestDetectDataStart:
    """Tests para la auto-deteccion de fila de inicio de datos."""

    def test_header_in_row1(self):
        """Header en fila 1 -> data_start = 2."""
        rows = [
            ["id_carpeta", "nombre_completo", "cuil", "observaciones",
             "clave_mi_anses", "clave_fiscal", "fecha_apertura"],
            ["1", "PEREZ", "20-12345678-3", "Obs", "clave", "fiscal", "2025-01-15"],
        ]
        assert _detect_data_start(rows, "CARPETAS") == 2

    def test_header_in_row2_with_title(self):
        """Titulo en fila 1, header en fila 2 -> data_start = 3."""
        rows = [
            ["CARPETAS", "", "", "", "", "", ""],
            ["id_carpeta", "nombre_completo", "cuil", "observaciones",
             "clave_mi_anses", "clave_fiscal", "fecha_apertura"],
            ["1", "PEREZ", "20-12345678-3", "Obs", "clave", "fiscal", "2025-01-15"],
        ]
        assert _detect_data_start(rows, "CARPETAS") == 3

    def test_no_header_uses_original_data_start(self):
        """Sin header reconocible -> usa data_start del mapping."""
        rows = [
            ["titulo", "", "", "", "", "", ""],
            ["subtitulo", "", "", "", "", "", ""],
            ["1", "PEREZ", "20-12345678-3", "Obs", "clave", "fiscal", "2025-01-15"],
        ]
        assert _detect_data_start(rows, "CARPETAS") == 3

    def test_rti_desfavorables_no_header(self):
        """RTI DESFAVORABLES sin header -> data_start = 1."""
        rows = [
            ["1", "PEREZ", "20-12345678-3", "clave", "Desfav", "RTI/M",
             "2025-01-15", "EX", "2025-02-01"],
        ]
        assert _detect_data_start(rows, "RTI DESFAVORABLES") == 1

    def test_empty_rows_list(self):
        """Lista vacia -> data_start original."""
        assert _detect_data_start([], "CARPETAS") == 3


# =====================================================================
# get_csv_info
# =====================================================================

class TestGetCsvInfo:
    """Tests para la funcion de info/preview de CSV."""

    def test_returns_row_count_and_preview(self, tmp_path):
        csv_content = (
            "CARPETAS;;;;;;\n"
            "id;nombre;cuil;obs;clave;fiscal;fecha\n"
            '1;PEREZ;20-12345678-3;Obs;m;f;2025-01-15\n'
            '2;GOMEZ;27-87654321-9;Obs2;m2;f2;2025-02-15\n'
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        info = get_csv_info(str(csv_file), "CARPETAS")
        assert info["rows"] == 2
        assert len(info["preview"]) == 2
        assert info["has_mapping"] is True
        assert info["columns"] >= 7

    def test_preview_limited_to_3(self, tmp_path):
        """Preview no retorna mas de 3 filas."""
        lines = ["titulo;;;;;;\n", "header;;;;;;\n"]
        for i in range(1, 11):
            lines.append(f'{i};Nombre{i};CUIL{i};Obs{i};cl{i};fi{i};2025-01-{i:02d}\n')
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("".join(lines), encoding="utf-8")

        info = get_csv_info(str(csv_file), "CARPETAS")
        assert info["rows"] == 10
        assert len(info["preview"]) == 3

    def test_unknown_sheet_type(self, tmp_path):
        csv_content = '1;PEREZ;20-12345678-3\n'
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        info = get_csv_info(str(csv_file), "UNKNOWN")
        assert info["has_mapping"] is False
        assert info["rows"] == 1

    def test_empty_file(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("", encoding="utf-8")

        info = get_csv_info(str(csv_file), "CARPETAS")
        assert info["rows"] == 0
        assert info["preview"] == []

    def test_rti_desfavorables_info(self, tmp_path):
        """RTI DESFAVORABLES: data_start=1, toda fila es dato."""
        csv_content = (
            '1;PEREZ;CUIL;clave;Desfav;RTI/M;2025-01-15;EX;2025-02-01\n'
            '2;GOMEZ;CUIL2;clave2;Fav;JUB/D;2025-02-15;;2025-03-01\n'
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        info = get_csv_info(str(csv_file), "RTI DESFAVORABLES")
        assert info["rows"] == 2
        assert info["has_mapping"] is True
        assert "Col1" in info["preview"][0]

    def test_carpetas_info_header_row1(self, tmp_path):
        """CARPETAS con header en fila 1: info debe contar solo datos."""
        csv_content = (
            "id_carpeta;nombre_completo;cuil;observaciones;clave_mi_anses;clave_fiscal;fecha_apertura\n"
            "1;CABRAL;20057079704;guaRDADA;20227814374;;5/05/2023\n"
            "2;PAIZ;;CARP;;;18/04/2022\n"
        )
        csv_file = tmp_path / "test.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        info = get_csv_info(str(csv_file), "CARPETAS")
        assert info["rows"] == 2
        assert len(info["preview"]) == 2
        assert "Col2" in info["preview"][0]
