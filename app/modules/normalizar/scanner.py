"""
scanner.py  (modulo normalizar)
================================
Deteccion y carga de archivos tabulares:
  - CSV / TXT / TSV  (con deteccion de encoding y separador)
  - Excel real       (.xlsx, .xls binario)
  - XLS disfrazado   (.xls que en realidad es HTML de una exportacion web)

Sin dependencias de UI. La funcion principal es cargar_archivo().
"""
import csv
from pathlib import Path

import chardet
import pandas as pd
from bs4 import BeautifulSoup

from app.modules.normalizar.utils import inferir_tipo


# ══════════════════════════════════════════════════════════════
#  DETECCION DE TIPO
# ══════════════════════════════════════════════════════════════

def detectar_tipo_archivo(ruta) -> str:
    ext = Path(ruta).suffix.lower()

    if ext in ['.csv', '.txt', '.tsv']:
        return 'csv'

    if ext == '.xlsx':
        return 'excel_real'

    if ext == '.xls':
        with open(ruta, 'rb') as f:
            cab = f.read(512)

        # Magic number Excel 97-2003 binario (OLE2)
        if cab.startswith(b'\xd0\xcf\x11\xe0'):
            return 'excel_real'

        # Si no es binario y parece HTML exportado
        cab_lower = cab.lower()
        if (cab.strip().startswith(b'<') or
                b'<html' in cab_lower or
                b'<table' in cab_lower or
                b'<form' in cab_lower):
            return 'html_disfrazado'

        return 'excel_real'

    return 'desconocido'


# ══════════════════════════════════════════════════════════════
#  CARGADORES POR TIPO
# ══════════════════════════════════════════════════════════════

def cargar_csv(ruta):
    """Carga un CSV/TXT/TSV detectando encoding y separador automaticamente."""
    with open(ruta, 'rb') as f:
        raw = f.read(100_000)
    det = chardet.detect(raw)
    encoding = det['encoding'] or 'utf-8'
    if encoding.lower() in ['iso-8859-1', 'windows-1252', 'ascii']:
        encoding = 'cp1252'

    # Intentar leer muestra con distintos encodings
    muestra = ''
    enc_final = encoding
    for enc in [encoding, 'utf-8-sig', 'utf-8', 'cp1252', 'latin-1']:
        try:
            with open(ruta, 'r', encoding=enc, errors='strict') as f:
                muestra = f.read(4096)
            enc_final = enc
            break
        except UnicodeDecodeError:
            continue

    # Detectar separador
    try:
        dialect = csv.Sniffer().sniff(muestra, delimiters=',;|\t')
        sep = dialect.delimiter
    except Exception:
        sep = max([',', ';', '|', '\t'], key=muestra.count)

    # Cargar DataFrame
    for enc in [enc_final, 'utf-8-sig', 'utf-8', 'cp1252', 'latin-1']:
        try:
            df = pd.read_csv(
                ruta, encoding=enc, sep=sep,
                on_bad_lines='skip', engine='python',
                dtype=str, keep_default_na=False
            )
            return df, enc, sep
        except Exception:
            continue

    raise RuntimeError("No se pudo cargar el CSV con ningun encoding conocido.")


def cargar_excel_real(ruta):
    """Carga un .xlsx o .xls binario real."""
    ext = Path(ruta).suffix.lower()
    engine = 'openpyxl' if ext == '.xlsx' else 'xlrd'
    df = pd.read_excel(ruta, engine=engine, dtype=str, keep_default_na=False)
    return df, "N/A", "N/A"


def cargar_html_disfrazado(ruta):
    """Carga un .xls que en realidad es una tabla HTML exportada desde un sistema web."""
    contenido = None
    enc_final = 'utf-8'

    for enc in ['utf-8', 'utf-8-sig', 'cp1252', 'latin-1']:
        try:
            with open(ruta, 'r', encoding=enc, errors='strict') as f:
                contenido = f.read()
            enc_final = enc
            break
        except UnicodeDecodeError:
            continue

    if contenido is None:
        with open(ruta, 'r', encoding='utf-8', errors='replace') as f:
            contenido = f.read()

    soup = BeautifulSoup(contenido, 'lxml')
    tabla = soup.find('table')

    if not tabla:
        if soup.find('form'):
            raise ValueError(
                "No se encontro tabla HTML en el archivo. "
                "Parece ser una pagina de login (sesion caducada)."
            )
        raise ValueError("No se encontro ninguna tabla HTML en el archivo.")

    filas = tabla.find_all('tr')
    if not filas:
        raise ValueError("La tabla HTML esta vacia.")

    headers = [th.get_text(strip=True) for th in filas[0].find_all('th')]
    if not headers:
        headers = [td.get_text(strip=True) for td in filas[0].find_all('td')]

    rows = []
    for fila in filas[1:]:
        celdas = [td.get_text(strip=True) for td in fila.find_all('td')]
        if celdas:
            if len(celdas) > len(headers):
                celdas = celdas[:len(headers)]
            elif len(celdas) < len(headers):
                celdas.extend([''] * (len(headers) - len(celdas)))
            rows.append(celdas)

    return pd.DataFrame(rows, columns=headers), enc_final, "N/A"


# ══════════════════════════════════════════════════════════════
#  FUNCION PRINCIPAL
# ══════════════════════════════════════════════════════════════

def cargar_archivo(ruta):
    """
    Detecta el tipo del archivo y lo carga.
    Retorna: (df, encoding, separator, tipo)
    """
    tipo = detectar_tipo_archivo(ruta)
    if tipo == 'csv':
        df, enc, sep = cargar_csv(ruta)
    elif tipo == 'excel_real':
        df, enc, sep = cargar_excel_real(ruta)
    elif tipo == 'html_disfrazado':
        df, enc, sep = cargar_html_disfrazado(ruta)
    else:
        raise ValueError(f"Tipo de archivo no soportado: {Path(ruta).suffix}")
    return df, enc, sep, tipo


# ══════════════════════════════════════════════════════════════
#  REPORTE DE ESTRUCTURA
# ══════════════════════════════════════════════════════════════

def generar_reporte_esquema(df, nombre_archivo: str, log):
    """Analiza el DataFrame normalizado e imprime su estructura de columnas."""
    log(f"\n{'='*65}")
    log(f"  ANALISIS DE ESTRUCTURA Y TIPOS")
    log(f"  Archivo: {nombre_archivo}")
    log(f"{'='*65}\n")

    total_filas = len(df)

    for i, col in enumerate(df.columns, 1):
        serie = df[col]
        nulos = serie.isna().sum()
        pct_nulos = (nulos / total_filas) * 100 if total_filas > 0 else 0
        tipo_dato = inferir_tipo(serie)

        ejemplos_arr = serie.dropna().unique()[:3]
        ejemplos_str = " | ".join([str(x) for x in ejemplos_arr]) if len(ejemplos_arr) > 0 else "N/A"

        log(f" [{i}] {col}")
        log(f"     -> Tipo       : {tipo_dato}")
        log(f"     -> Nulos      : {nulos:,} ({pct_nulos:.1f}%)")
        log(f"     -> Ejemplos   : {ejemplos_str}")
        log("-" * 65)
