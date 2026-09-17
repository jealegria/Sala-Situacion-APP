import pandas as pd
import numpy as np
import os
import re
from pathlib import Path
from core.utils import *
from core.scanner import cargar_archivo

def limpiar_datos(df):
    for col in df.columns:
        serie = df[col].astype(str)
        serie = serie.str.strip()
        serie = serie.replace({'': np.nan, 'nan': np.nan, 'None': np.nan, 'NaN': np.nan})
        df[col] = serie
    return df


def es_columna_de_fecha(nombre_col, serie):
    keywords = ['fecha', 'ingreso', 'egreso', 'atencion', 'nacimiento', 'date', 'alta', 'baja']
    nombre = nombre_col.lower()
    tiene_keyword = any(k in nombre for k in keywords)
    if not tiene_keyword:
        return False

    no_nulos = serie.dropna()
    no_nulos = no_nulos[no_nulos != 'nan']
    if len(no_nulos) == 0:
        return False

    muestra = no_nulos.head(100).astype(str)
    
    try:
        # Intento de parseo robusto en dos pasos
        # 1. ISO-like (YYYY-MM-DD)
        mask_iso = muestra.str.match(r'^\d{4}-\d{2}-\d{2}', na=False)
        p1 = pd.to_datetime(muestra[mask_iso], errors='coerce')
        # 2. Otros (DayFirst=True)
        p2 = pd.to_datetime(muestra[~mask_iso], dayfirst=True, errors='coerce')
        
        parseada = pd.concat([p1, p2])
        pct_ok = parseada.notna().mean()
        return pct_ok > 0.7
    except:
        return False


def detectar_y_parsear_fechas(df, log):
    cols_fecha = [col for col in df.columns if es_columna_de_fecha(col, df[col])]

    if not cols_fecha:
        log("    (no se detectaron columnas de fecha)")
        return df

    for col in cols_fecha:
        serie_orig = df[col].copy()
        serie_clean = serie_orig.replace({'nan': np.nan, '': np.nan, 'None': np.nan})
        
        # Limpiar strings antes de procesar
        s_clean = serie_clean.astype(str).str.strip()
        # Eliminar valores que son solo '#' (errores de visualización de Excel exportados)
        s_clean = s_clean.replace(r'^#+$', np.nan, regex=True)
        s_clean = s_clean.replace({'nan': np.nan, '': np.nan, 'None': np.nan})

        # Parseo robusto de dos pasos:
        # 1. Identificar strings que parecen ISO (YYYY-MM-DD)
        mask_iso = s_clean.str.match(r'^\d{4}-\d{2}-\d{2}', na=False)
        
        # 2. Parsear ISOs sin dayfirst
        parsed_iso = pd.to_datetime(s_clean.where(mask_iso), errors='coerce')
        
        # 3. Parsear el resto con dayfirst=True
        # Usamos format='mixed' si está disponible (Pandas >= 2.0)
        try:
            parsed_arg = pd.to_datetime(s_clean.where(~mask_iso), dayfirst=True, errors='coerce', format='mixed')
        except:
            parsed_arg = pd.to_datetime(s_clean.where(~mask_iso), dayfirst=True, errors='coerce')
        
        # 4. Combinar resultados
        convertida = parsed_iso.fillna(parsed_arg)

        total_no_nulos = serie_clean.notna().sum()
        fallos = int(convertida.isna().sum() - serie_clean.isna().sum())
        # Elegir formato de salida: si no hay horas/minutos en toda la columna, solo DD/MM/YYYY
        tiene_tiempo = (convertida.dt.hour != 0).any() or (convertida.dt.minute != 0).any()
        formato_final = '%d/%m/%Y %H:%M:%S' if tiene_tiempo else '%d/%m/%Y'

        df[col] = convertida.dt.strftime(formato_final).where(
            convertida.notna(), other=np.nan
        )

        log(f"    [OK] {col} (Formato: {formato_final})")
        log(f"       Parseadas OK : {total_no_nulos - fallos:,} de {total_no_nulos:,}")

        if fallos > 0:
            mask_fallo = convertida.isna() & serie_clean.notna()
            ejemplos = serie_clean[mask_fallo].dropna().head(3).tolist()
            log(f"       [WARN] Fallos : {fallos} valores no parsearon -> NaN")
            if ejemplos:
                log(f"       Ejemplos   : {ejemplos}")

    return df


# ══════════════════════════════════════════════════════════════
#  PROCESAMIENTO PRINCIPAL
# ══════════════════════════════════════════════════════════════

def procesar_archivo(ruta, carpeta_salida, log, accion):
    nombre = Path(ruta).name
    log(f"\n{'═' * 65}")
    log(f"  PROCESANDO: {nombre} ({accion.upper()})")
    log(f"{'═' * 65}")

    # ── 1. CARGAR ─────────────────────────────────────────────
    log("\n  [1/4] Cargando archivo...")
    try:
        df, encoding, separator, tipo = cargar_archivo(ruta)
        log(f"    Tipo      : {tipo}")
        log(f"    Encoding  : {encoding}")
        log(f"    Separator : {separator}")
        log(f"    Forma     : {len(df):,} filas x {len(df.columns)} columnas")
    except Exception as e:
        log(f"    [ERROR] Error al cargar: {e}")
        return None

    # ── 2. NORMALIZAR COLUMNAS ────────────────────────────────
    log("\n  [2/4] Normalizando nombres de columnas...")
    cols_originales = list(df.columns)
    cols_norm = [normalizar_nombre_col(c) for c in cols_originales]
    cols_dedup = deduplicar_columnas(cols_norm)

    cambios = [(o, n) for o, n in zip(cols_originales, cols_dedup) if str(o) != n]
    df.columns = cols_dedup

    if cambios:
        for orig, nuevo in cambios:
            log(f"    {str(orig)!r:40} -> {nuevo}")
    else:
        log("    (ningun cambio necesario en nombres de columna)")

    duplicados = [n for n in cols_dedup if re.search(r'_\d+$', n)]
    if duplicados:
        log(f"    [WARN] Duplicados resueltos con sufijo: {duplicados}")

    # ── 3. LIMPIAR DATOS Y FECHAS ─────────────────────────────
    log("\n  [3/4] Limpiando datos (vacios -> NaN) y formateando fechas...")
    df = limpiar_datos(df)
    df = detectar_y_parsear_fechas(df, log)

    if accion == "analizar":
        log("\n  [INFO] Analisis finalizado. Revisa la pestaña 'Estructura y Tipos'.")
        return df

    # ── 4. GUARDAR ────────────────────────────────────────────
    log("\n  [4/4] Guardando CSV normalizado...")
    stem = Path(ruta).stem
    nombre_salida = f"{stem}_normalizado.csv"
    ruta_salida = Path(carpeta_salida) / nombre_salida

    df.to_csv(ruta_salida, index=False, encoding=EXPORT_ENCODING, sep=EXPORT_SEP)
    tamanio = os.path.getsize(ruta_salida) / 1024

    log(f"    Archivo   : {nombre_salida}")
    log(f"    Encoding  : {EXPORT_ENCODING}")
    log(f"    Separator : {EXPORT_SEP}")
    log(f"    Ruta      : {ruta_salida}")
    log(f"    Tamaño    : {tamanio:.1f} KB")
    log(f"    [OK] Normalizacion y guardado completados")

    return df


# ══════════════════════════════════════════════════════════════
#  GUI
# ══════════════════════════════════════════════════════════════

