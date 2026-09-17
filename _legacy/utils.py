import os
import csv
import re
import json
import threading
import chardet
import sys
import pandas as pd
import numpy as np
import tkinter as tk
from tkinter import filedialog, scrolledtext, simpledialog, messagebox
from pathlib import Path

# Fix para UI borrosa en pantallas con alto DPI (Windows)
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

def get_base_path():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def get_asset_path():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent / "assets"

def quitar_acentos_col(texto):
    reemplazos = str.maketrans(
        'áéíóúàèìòùâêîôûäëïöüãõñÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÄËÏÖÜÃÕÑ',
        'aeiouaeiouaeiouaeiouaonAEIOUAEIOUAEIOUAEIOUAON'
    )
    s = texto.translate(reemplazos)
    s = s.replace('ç', 'c').replace('Ç', 'C')
    return s


def normalizar_nombre_col(nombre):
    s = str(nombre).strip()
    s = quitar_acentos_col(s)
    s = s.lower()
    s = re.sub(r'[^a-z0-9\s_]', '', s)
    s = re.sub(r'[\s]+', '_', s)
    s = re.sub(r'_+', '_', s)
    s = s.strip('_')
    return s or 'col'


def deduplicar_columnas(nombres):
    vistos = {}
    resultado = []
    for nombre in nombres:
        if nombre not in vistos:
            vistos[nombre] = 0
            resultado.append(nombre)
        else:
            vistos[nombre] += 1
            resultado.append(f"{nombre}_{vistos[nombre]}")
    return resultado


def inferir_tipo_bd(serie):
    """
    Infiere el tipo de dato SQL sugerido para Supabase/PostgreSQL
    basandose en los datos reales de la columna (ignorando los nulos).
    """
    no_nulos = serie.dropna()
    if len(no_nulos) == 0:
        return "NULL (Sin datos validos)"

    # Chequear fechas (nuestro script puede pasarlas a DD/MM/YYYY o YYYY-MM-DD)
    if no_nulos.str.match(r'^(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})').all():
        if no_nulos.str.endswith('00:00:00').all():
            return "DATE (Fecha)"
        return "TIMESTAMP (Fecha y Hora)"

    # Chequear booleanos
    unicos = set(no_nulos.str.lower().unique())
    if unicos.issubset({'si', 'no', 'true', 'false', '0', '1', 'v', 'f'}):
        if len(unicos) <= 2:
            return "BOOLEAN (Verdadero/Falso)"

    # Chequear numericos
    try:
        num = pd.to_numeric(no_nulos)
        # Si no salto excepcion, es numero. Revisamos si tiene decimales
        if (num % 1 == 0).all():
            return "INTEGER (Entero)"
        return "FLOAT / NUMERIC (Decimal)"
    except (ValueError, TypeError):
        pass

    # Si llego aca, es texto
    max_len = no_nulos.str.len().max()
    if max_len > 255:
        return "TEXT (Texto Largo)"
    return "VARCHAR (Texto Corto)"


def inferir_tipo_supabase(serie):
    """
    Versión simplificada para el reporte AI de Modify Data.
    """
    no_nulos = serie.dropna()
    if len(no_nulos) == 0: return "NULL"
    
    if no_nulos.str.match(r'^(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})').all():
        return "timestamp" if not no_nulos.str.endswith('00:00:00').all() else "date"
    
    try:
        num = pd.to_numeric(no_nulos)
        return "int8" if (num % 1 == 0).all() else "float8"
    except: pass
    
    return "text" if no_nulos.str.len().max() > 255 else "varchar"

# ══════════════════════════════════════════════════════════════
#  CONSTANTES DE EXPORTACION
# ══════════════════════════════════════════════════════════════
EXPORT_ENCODING = 'utf-8-sig'
EXPORT_SEP      = ';'

