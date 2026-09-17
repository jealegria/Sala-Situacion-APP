"""
processor.py  (modulo normalizar)
==================================
Logica principal de normalizacion de archivos tabulares.

Flujo por archivo:
  1. Cargar (via scanner.cargar_archivo)
  2. Normalizar nombres de columnas (snake_case, sin acentos, deduplicar)
  3. Limpiar datos (strings vacios -> NaN)
  4. Detectar y formatear columnas de fecha
  5. Guardar CSV normalizado en carpeta de salida

La funcion publica principal es procesar_carpeta().
Todas las funciones aceptan un callback `log(str)` para emitir mensajes
sin acoplarse a ninguna UI.
"""
import os
import re
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Callable

from app.modules.normalizar.utils import (
    normalizar_nombre_col,
    deduplicar_columnas,
    EXPORT_ENCODING,
    EXPORT_SEP,
)
from app.modules.normalizar.scanner import cargar_archivo

# Extensiones de archivo que el modulo puede procesar
EXTENSIONES_SOPORTADAS = {'.csv', '.txt', '.tsv', '.xlsx', '.xls'}

LogFn = Callable[[str], None]


# ══════════════════════════════════════════════════════════════
#  LIMPIEZA DE DATOS
# ══════════════════════════════════════════════════════════════

def limpiar_datos(df: pd.DataFrame) -> pd.DataFrame:
    """Reemplaza strings vacios y variantes de NaN por np.nan real."""
    for col in df.columns:
        serie = df[col].astype(str).str.strip()
        serie = serie.replace({'': np.nan, 'nan': np.nan, 'None': np.nan, 'NaN': np.nan})
        df[col] = serie
    return df


# ══════════════════════════════════════════════════════════════
#  DETECCION Y PARSEO DE FECHAS
# ══════════════════════════════════════════════════════════════

def _es_columna_de_fecha(nombre_col: str, serie: pd.Series) -> bool:
    """Heuristica: keywords en el nombre + al menos 70% de valores parseables."""
    keywords = ['fecha', 'ingreso', 'egreso', 'atencion', 'nacimiento',
                'date', 'alta', 'baja']
    if not any(k in nombre_col.lower() for k in keywords):
        return False

    no_nulos = serie.dropna().replace({'nan': np.nan}).dropna()
    if len(no_nulos) == 0:
        return False

    muestra = no_nulos.head(100).astype(str)
    try:
        mask_iso = muestra.str.match(r'^\d{4}-\d{2}-\d{2}', na=False)
        p1 = pd.to_datetime(muestra[mask_iso], errors='coerce')
        p2 = pd.to_datetime(muestra[~mask_iso], dayfirst=True, errors='coerce')
        pct_ok = pd.concat([p1, p2]).notna().mean()
        return pct_ok > 0.7
    except Exception:
        return False


def detectar_y_parsear_fechas(df: pd.DataFrame, log: LogFn) -> pd.DataFrame:
    """Detecta columnas de fecha y las convierte a formato DD/MM/YYYY."""
    cols_fecha = [col for col in df.columns if _es_columna_de_fecha(col, df[col])]

    if not cols_fecha:
        log("    (no se detectaron columnas de fecha)")
        return df

    for col in cols_fecha:
        serie_orig = df[col].copy()
        serie_clean = serie_orig.replace({'nan': np.nan, '': np.nan, 'None': np.nan})

        s = serie_clean.astype(str).str.strip()
        s = s.replace(r'^#+$', np.nan, regex=True)
        s = s.replace({'nan': np.nan, '': np.nan, 'None': np.nan})

        mask_iso = s.str.match(r'^\d{4}-\d{2}-\d{2}', na=False)
        parsed_iso = pd.to_datetime(s.where(mask_iso), errors='coerce')

        try:
            parsed_other = pd.to_datetime(
                s.where(~mask_iso), dayfirst=True, errors='coerce', format='mixed'
            )
        except Exception:
            parsed_other = pd.to_datetime(
                s.where(~mask_iso), dayfirst=True, errors='coerce'
            )

        convertida = parsed_iso.fillna(parsed_other)

        total_no_nulos = serie_clean.notna().sum()
        fallos = int(convertida.isna().sum() - serie_clean.isna().sum())
        tiene_tiempo = (convertida.dt.hour != 0).any() or (convertida.dt.minute != 0).any()
        fmt = '%d/%m/%Y %H:%M:%S' if tiene_tiempo else '%d/%m/%Y'

        df[col] = convertida.dt.strftime(fmt).where(convertida.notna(), other=np.nan)

        log(f"    [OK] {col}  (formato: {fmt})")
        log(f"         Parseadas : {total_no_nulos - fallos:,} de {total_no_nulos:,}")
        if fallos > 0:
            mask_fallo = convertida.isna() & serie_clean.notna()
            ejemplos = serie_clean[mask_fallo].dropna().head(3).tolist()
            log(f"         [WARN] {fallos} valor(es) no parsearon -> NaN")
            if ejemplos:
                log(f"         Ejemplos  : {ejemplos}")

    return df


# ══════════════════════════════════════════════════════════════
#  PROCESAMIENTO DE UN ARCHIVO
# ══════════════════════════════════════════════════════════════

def procesar_archivo(ruta: Path, carpeta_salida: Path, log: LogFn) -> pd.DataFrame | None:
    """
    Normaliza un archivo tabular y lo guarda en carpeta_salida.
    Emite progreso via el callback log(str).
    Retorna el DataFrame resultante, o None si hubo un error al cargar.
    """
    nombre = ruta.name
    log(f"\n{'═' * 65}")
    log(f"  PROCESANDO: {nombre}")
    log(f"{'═' * 65}")

    # ── 1. CARGAR ──────────────────────────────────────────────
    log("\n  [1/4] Cargando archivo...")
    try:
        df, encoding, separator, tipo = cargar_archivo(ruta)
        log(f"    Tipo      : {tipo}")
        log(f"    Encoding  : {encoding}")
        log(f"    Separator : {separator}")
        log(f"    Forma     : {len(df):,} filas x {len(df.columns)} columnas")
    except Exception as e:
        log(f"    [ERROR] No se pudo cargar: {e}")
        return None

    # ── 2. NORMALIZAR COLUMNAS ─────────────────────────────────
    log("\n  [2/4] Normalizando nombres de columnas...")
    cols_originales = list(df.columns)
    cols_norm  = [normalizar_nombre_col(c) for c in cols_originales]
    cols_dedup = deduplicar_columnas(cols_norm)

    cambios = [(o, n) for o, n in zip(cols_originales, cols_dedup) if str(o) != n]
    df.columns = cols_dedup

    if cambios:
        for orig, nuevo in cambios:
            log(f"    {str(orig)!r:40} -> {nuevo}")
    else:
        log("    (ningun cambio en nombres de columna)")

    duplicados = [n for n in cols_dedup if re.search(r'_\d+$', n)]
    if duplicados:
        log(f"    [WARN] Duplicados resueltos con sufijo: {duplicados}")

    # ── 3. LIMPIAR DATOS Y FECHAS ──────────────────────────────
    log("\n  [3/4] Limpiando datos y formateando fechas...")
    df = limpiar_datos(df)
    df = detectar_y_parsear_fechas(df, log)

    # ── 4. GUARDAR ─────────────────────────────────────────────
    log("\n  [4/4] Guardando CSV normalizado...")
    nombre_salida = f"{ruta.stem}_normalizado.csv"
    ruta_salida   = carpeta_salida / nombre_salida

    df.to_csv(ruta_salida, index=False, encoding=EXPORT_ENCODING, sep=EXPORT_SEP)
    tamanio = os.path.getsize(ruta_salida) / 1024

    log(f"    Archivo   : {nombre_salida}")
    log(f"    Encoding  : {EXPORT_ENCODING}")
    log(f"    Separator : {EXPORT_SEP}")
    log(f"    Ruta      : {ruta_salida}")
    log(f"    Tamaño    : {tamanio:.1f} KB")
    log(f"    [OK] Completado")

    return df


# ══════════════════════════════════════════════════════════════
#  PROCESAMIENTO DE CARPETA COMPLETA
# ══════════════════════════════════════════════════════════════

def procesar_carpeta(carpeta_input: Path, carpeta_salida: Path, log: LogFn) -> None:
    """
    Procesa todos los archivos compatibles de carpeta_input
    y guarda los resultados en carpeta_salida.
    """
    archivos = sorted([
        f for f in carpeta_input.iterdir()
        if f.is_file() and f.suffix.lower() in EXTENSIONES_SOPORTADAS
    ])

    if not archivos:
        log("  [WARN] No se encontraron archivos compatibles en la carpeta.")
        log(f"  Extensiones soportadas: {', '.join(sorted(EXTENSIONES_SOPORTADAS))}")
        return

    carpeta_salida.mkdir(parents=True, exist_ok=True)

    log(f"  Carpeta input  : {carpeta_input}")
    log(f"  Carpeta output : {carpeta_salida}")
    log(f"  Archivos encontrados: {len(archivos)}")

    exitosos = 0
    for ruta in archivos:
        resultado = procesar_archivo(ruta, carpeta_salida, log)
        if resultado is not None:
            exitosos += 1

    log(f"\n{'═' * 65}")
    log(f"  PROCESO COMPLETADO")
    log(f"  Exitosos : {exitosos} / {len(archivos)}")
    log(f"{'═' * 65}")
