import pandas as pd
import csv
import chardet
from bs4 import BeautifulSoup
from core.utils import *

def generar_reporte_esquema(df, nombre_archivo, log_schema):
    """Analiza un DataFrame ya limpio e imprime su esquema en la consola secundaria."""
    log_schema(f"\n{'='*65}")
    log_schema(f"  ANALISIS DE ESTRUCTURA Y TIPOS SUGERIDOS (SUPABASE)")
    log_schema(f"  Archivo: {nombre_archivo}")
    log_schema(f"{'='*65}\n")

    total_filas = len(df)
    
    for i, col in enumerate(df.columns, 1):
        serie = df[col]
        nulos = serie.isna().sum()
        pct_nulos = (nulos / total_filas) * 100 if total_filas > 0 else 0
        tipo_bd = inferir_tipo_bd(serie)
        
        # Agarrar hasta 3 valores unicos reales para mostrar como ejemplo
        ejemplos_arr = serie.dropna().unique()[:3]
        if len(ejemplos_arr) > 0:
            ejemplos_str = " | ".join([str(x) for x in ejemplos_arr])
        else:
            ejemplos_str = "N/A"

        log_schema(f" [{i}] {col}")
        log_schema(f"     -> Tipo sugerido : {tipo_bd}")
        log_schema(f"     -> Valores Nulos : {nulos:,} ({pct_nulos:.1f}%)")
        log_schema(f"     -> Ejemplos      : {ejemplos_str}")
        log_schema("-" * 65)


# ══════════════════════════════════════════════════════════════
#  HELPERS — CARGA DE ARCHIVOS
# ══════════════════════════════════════════════════════════════

def detectar_tipo_archivo(ruta):
    ext = Path(ruta).suffix.lower()
    if ext in ['.csv', '.txt', '.tsv']:
        return 'csv'
    if ext == '.xlsx':
        return 'excel_real'
    if ext == '.xls':
        with open(ruta, 'rb') as f:
            cab = f.read(512)
        
        # Magic number para Excel 97-2003 (.xls) binario (OLE2)
        if cab.startswith(b'\xd0\xcf\x11\xe0'):
            return 'excel_real'
            
        # Si no es binario y parece HTML/XML
        cab_clean = cab.strip()
        cab_lower = cab.lower()
        if cab_clean.startswith(b'<') or b'<html' in cab_lower or b'<table' in cab_lower or b'<form' in cab_lower:
            return 'html_disfrazado'
            
        return 'excel_real'
    return 'desconocido'


def cargar_csv(ruta):
    with open(ruta, 'rb') as f:
        raw = f.read(100000)
    det = chardet.detect(raw)
    encoding = det['encoding'] or 'utf-8'
    if encoding.lower() in ['iso-8859-1', 'windows-1252', 'ascii']:
        encoding = 'cp1252'

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

    try:
        dialect = csv.Sniffer().sniff(muestra, delimiters=',;|\t')
        sep = dialect.delimiter
    except:
        sep = max([',', ';', '|', '\t'], key=muestra.count)

    for enc in [enc_final, 'utf-8-sig', 'utf-8', 'cp1252', 'latin-1']:
        try:
            df = pd.read_csv(ruta, encoding=enc, sep=sep,
                             on_bad_lines='skip', engine='python',
                             dtype=str, keep_default_na=False)
            return df, enc, sep
        except:
            continue
    raise RuntimeError("No se pudo cargar el CSV.")


def cargar_excel_real(ruta):
    ext = Path(ruta).suffix.lower()
    engine = 'openpyxl' if ext == '.xlsx' else 'xlrd'
    df = pd.read_excel(ruta, engine=engine, dtype=str, keep_default_na=False)
    return df, "N/A", "N/A"


def cargar_html_disfrazado(ruta):
    from bs4 import BeautifulSoup
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
        enc_final = 'utf-8'
        with open(ruta, 'r', encoding='utf-8', errors='replace') as f:
            contenido = f.read()

    soup = BeautifulSoup(contenido, 'lxml')
    tabla = soup.find('table')
    if not tabla:
        # Si no hay tabla pero hay un form, avisamos que podría ser una página de login
        if soup.find('form'):
            raise ValueError("No se encontró tabla HTML, pero el archivo contiene un formulario. \n¿Es posible que la sesión haya caducado o sea una página de login?")
        raise ValueError("No se encontró ninguna tabla HTML en el archivo.")

    filas = tabla.find_all('tr')
    if not filas:
        raise ValueError("La tabla HTML está vacía.")

    # Intentar obtener encabezados de la primera fila
    headers = [th.get_text(strip=True) for th in filas[0].find_all('th')]
    if not headers:
        headers = [td.get_text(strip=True) for td in filas[0].find_all('td')]

    rows = []
    # Los datos siempre empiezan después de la primera fila (que usamos para headers)
    for fila in filas[1:]:
        celdas = [td.get_text(strip=True) for td in fila.find_all('td')]
        if celdas:
            # Asegurar que la fila tenga el mismo número de columnas que headers
            # o truncar/rellenar si es necesario
            if len(celdas) > len(headers):
                celdas = celdas[:len(headers)]
            elif len(celdas) < len(headers):
                celdas.extend([''] * (len(headers) - len(celdas)))
            rows.append(celdas)

    return pd.DataFrame(rows, columns=headers), enc_final, "N/A"


def cargar_archivo(ruta):
    tipo = detectar_tipo_archivo(ruta)
    if tipo == 'csv':
        return cargar_csv(ruta) + (tipo,)  # returns (df, enc, sep, tipo)
    elif tipo == 'excel_real':
        return cargar_excel_real(ruta) + (tipo,)
    elif tipo == 'html_disfrazado':
        return cargar_html_disfrazado(ruta) + (tipo,)
    else:
        raise ValueError(f"Tipo de archivo no soportado: {Path(ruta).suffix}")


# ══════════════════════════════════════════════════════════════
#  HELPERS — LIMPIEZA Y FECHAS
# ══════════════════════════════════════════════════════════════

