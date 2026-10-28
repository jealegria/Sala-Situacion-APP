"""
reader.py — Extractor y parser de planillas de Rendimiento de Internación
========================================================================
Convierte la estructura no tabular y consolidada del Excel de estadística
hospitalaria en DataFrames de pandas perfectamente limpios y tipados.
"""

from pathlib import Path
from typing import Callable, Optional
import openpyxl
import pandas as pd

DEFAULT_EXCEL_PATH = Path(r"C:\02_HPN\01_Base\rendimiento_estadistica\A- RENDIMIENTO INTERNACION GENERAL 2026.xlsx")

MESES_VALIDOS = [
    "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
    "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"
]

NUMERIC_COLUMNS = [
    "dias_funcionamiento",
    "egresos_total",
    "egresos_altas",
    "egresos_defunciones",
    "egresos_pases_a",
    "pacientes_dia",
    "camas_disponibles",
    "dias_estada",
    "prom_pacientes_dia",
    "prom_camas_disponibles",
    "prom_dias_estada",
    "porc_ocupacion",
    "giro_camas",
    "tasa_mortalidad",
    "prom_permanencia",
]

COLUMNAS_RESULTADO = [
    "anio",
    "mes",
    "tipo_registro",
    "servicio",
    *NUMERIC_COLUMNS,
]

LogFn = Callable[[str], None]


def _safe_float(val) -> Optional[float]:
    """Convierte de forma segura celdas a float o None."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def _safe_int(val) -> int:
    """Convierte a entero de forma segura."""
    f = _safe_float(val)
    return int(round(f))


def parse_rendimiento_excel(
    file_path: Path = DEFAULT_EXCEL_PATH,
    mes_filtro: Optional[str] = None,
    log: Optional[LogFn] = None,
) -> pd.DataFrame:
    """
    Lee el archivo Excel de rendimiento y devuelve un DataFrame tabular limpio.

    Parámetros:
        file_path: Ruta al archivo Excel .xlsx.
        mes_filtro: Nombre del mes en mayúsculas (ej: 'JUNIO') para filtrar.
                    Si es None, procesa todos los meses disponibles.
        log: Función opcional para mensajes de progreso.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo de rendimiento en: {path}")

    if log:
        log(f"Cargando archivo: {path.name}...")

    # Cargar con data_only=True para leer los valores calculados de las fórmulas
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    sheet = wb.active

    # Detectar el año desde el título o fila 4
    # Fila 4 suele tener el año en Col A
    val_anio = sheet.cell(4, 1).value
    try:
        anio = int(val_anio)
    except (TypeError, ValueError):
        anio = 2026

    records = []
    current_mes = None

    filtro_upper = mes_filtro.strip().upper() if mes_filtro else None

    # Recorrer filas a partir de la fila 4 (donde empiezan los datos)
    for r in range(4, sheet.max_row + 1):
        c1 = sheet.cell(r, 1).value
        c2 = sheet.cell(r, 2).value

        # Detectar inicio de bloque de mes
        if c1 is not None and str(c1).strip().upper() in MESES_VALIDOS:
            current_mes = str(c1).strip().upper()

            # Si hay filtro de mes y este no coincide, continuar
            if filtro_upper and current_mes != filtro_upper:
                continue

            # Fila de TOTAL MENSUAL del Hospital
            row_data = {
                "anio": anio,
                "mes": current_mes,
                "tipo_registro": "TOTAL_MES",
                "servicio": "HOSPITAL E. CASTRO RENDON",
                "dias_funcionamiento": _safe_int(sheet.cell(r, 3).value),
                "egresos_total": _safe_int(sheet.cell(r, 4).value),
                "egresos_altas": _safe_int(sheet.cell(r, 5).value),
                "egresos_defunciones": _safe_int(sheet.cell(r, 6).value),
                "egresos_pases_a": _safe_int(sheet.cell(r, 7).value),
                "pacientes_dia": _safe_int(sheet.cell(r, 8).value),
                "camas_disponibles": _safe_int(sheet.cell(r, 9).value),
                "dias_estada": _safe_int(sheet.cell(r, 10).value),
                # Dias, camas, pacientes y permanencia redondeados a ENTERO
                "prom_pacientes_dia": _safe_int(sheet.cell(r, 11).value),
                "prom_camas_disponibles": _safe_int(sheet.cell(r, 12).value),
                "prom_dias_estada": _safe_int(sheet.cell(r, 13).value),
                "prom_permanencia": _safe_int(sheet.cell(r, 17).value),
                # Indices, porcentajes y tasas con 1 decimal
                "porc_ocupacion": round(_safe_float(sheet.cell(r, 14).value), 1),
                "giro_camas": round(_safe_float(sheet.cell(r, 15).value), 1),
                "tasa_mortalidad": round(_safe_float(sheet.cell(r, 16).value), 1),
            }
            records.append(row_data)
            continue

        # Si estamos dentro de un mes válido
        if current_mes is not None:
            if filtro_upper and current_mes != filtro_upper:
                continue

            # Si Col 2 tiene el nombre de un servicio
            if c2 is not None and str(c2).strip():
                servicio_nombre = str(c2).strip().upper()

                row_data = {
                    "anio": anio,
                    "mes": current_mes,
                    "tipo_registro": "SERVICIO",
                    "servicio": servicio_nombre,
                    "dias_funcionamiento": _safe_int(sheet.cell(r, 3).value),
                    "egresos_total": _safe_int(sheet.cell(r, 4).value),
                    "egresos_altas": _safe_int(sheet.cell(r, 5).value),
                    "egresos_defunciones": _safe_int(sheet.cell(r, 6).value),
                    "egresos_pases_a": _safe_int(sheet.cell(r, 7).value),
                    "pacientes_dia": _safe_int(sheet.cell(r, 8).value),
                    "camas_disponibles": _safe_int(sheet.cell(r, 9).value),
                    "dias_estada": _safe_int(sheet.cell(r, 10).value),
                    # Dias, camas, pacientes y permanencia redondeados a ENTERO
                    "prom_pacientes_dia": _safe_int(sheet.cell(r, 11).value),
                    "prom_camas_disponibles": _safe_int(sheet.cell(r, 12).value),
                    "prom_dias_estada": _safe_int(sheet.cell(r, 13).value),
                    "prom_permanencia": _safe_int(sheet.cell(r, 17).value),
                    # Indices, porcentajes y tasas con 1 decimal
                    "porc_ocupacion": round(_safe_float(sheet.cell(r, 14).value), 1),
                    "giro_camas": round(_safe_float(sheet.cell(r, 15).value), 1),
                    "tasa_mortalidad": round(_safe_float(sheet.cell(r, 16).value), 1),
                }
                records.append(row_data)

    wb.close()

    df = pd.DataFrame(records, columns=COLUMNAS_RESULTADO)

    # Filtrar para conservar solo hasta el último mes con datos reales
    if not df.empty:
        # Identificar meses que tienen datos > 0 (egresos_total > 0 o pacientes_dia > 0)
        totales_mes = df[df["tipo_registro"] == "TOTAL_MES"]
        meses_con_datos = totales_mes[
            (totales_mes["egresos_total"] > 0) | (totales_mes["pacientes_dia"] > 0)
        ]["mes"].tolist()

        if meses_con_datos:
            df = df[df["mes"].isin(meses_con_datos)].copy()

    if log:
        meses_str = ", ".join(df["mes"].unique()) if not df.empty else "Ninguno"
        log(f"Extracción finalizada. Meses con datos: {meses_str} ({len(df)} filas)")

    return df


if __name__ == "__main__":
    # Prueba rápida para Junio
    df_junio = parse_rendimiento_excel(mes_filtro="JUNIO")
    print(f"\n--- TABLA LIMPIA: JUNIO 2026 ({len(df_junio)} registros) ---")
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 1000)
    print(df_junio.to_string(index=False))
