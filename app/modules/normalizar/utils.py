"""
utils.py  (modulo normalizar)
==============================
Funciones utilitarias puras: normalizacion de nombres de columnas,
deduplicacion, inferencia de tipos y constantes de exportacion.
Sin dependencias de UI.
"""
import re
import pandas as pd

# ══════════════════════════════════════════════════════════════
#  CONSTANTES DE EXPORTACION
# ══════════════════════════════════════════════════════════════
EXPORT_ENCODING = 'utf-8-sig'
EXPORT_SEP      = ';'


# ══════════════════════════════════════════════════════════════
#  NORMALIZACION DE COLUMNAS
# ══════════════════════════════════════════════════════════════

def quitar_acentos(texto: str) -> str:
    reemplazos = str.maketrans(
        'áéíóúàèìòùâêîôûäëïöüãõñÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÄËÏÖÜÃÕÑ',
        'aeiouaeiouaeiouaeiouaonAEIOUAEIOUAEIOUAEIOUAON'
    )
    s = texto.translate(reemplazos)
    s = s.replace('ç', 'c').replace('Ç', 'C')
    return s


def normalizar_nombre_col(nombre: str) -> str:
    """Convierte un nombre de columna a snake_case ASCII sin caracteres especiales."""
    s = str(nombre).strip()
    s = quitar_acentos(s)
    s = s.lower()
    s = re.sub(r'[^a-z0-9\s_]', '', s)
    s = re.sub(r'[\s]+', '_', s)
    s = re.sub(r'_+', '_', s)
    s = s.strip('_')
    return s or 'col'


def deduplicar_columnas(nombres: list[str]) -> list[str]:
    """Agrega sufijo numerico a columnas duplicadas."""
    vistos: dict[str, int] = {}
    resultado = []
    for nombre in nombres:
        if nombre not in vistos:
            vistos[nombre] = 0
            resultado.append(nombre)
        else:
            vistos[nombre] += 1
            resultado.append(f"{nombre}_{vistos[nombre]}")
    return resultado


# ══════════════════════════════════════════════════════════════
#  INFERENCIA DE TIPOS
# ══════════════════════════════════════════════════════════════

def inferir_tipo(serie: pd.Series) -> str:
    """
    Infiere el tipo de dato de una columna basandose en sus valores reales.
    Retorna una descripcion legible del tipo detectado.
    """
    no_nulos = serie.dropna()
    if len(no_nulos) == 0:
        return "NULL (Sin datos validos)"

    # Fechas
    if no_nulos.str.match(r'^(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})').all():
        if no_nulos.str.endswith('00:00:00').all():
            return "DATE (Fecha)"
        return "TIMESTAMP (Fecha y Hora)"

    # Booleanos
    unicos = set(no_nulos.str.lower().unique())
    if unicos.issubset({'si', 'no', 'true', 'false', '0', '1', 'v', 'f'}) and len(unicos) <= 2:
        return "BOOLEAN (Verdadero/Falso)"

    # Numericos
    try:
        num = pd.to_numeric(no_nulos)
        if (num % 1 == 0).all():
            return "INTEGER (Entero)"
        return "FLOAT / NUMERIC (Decimal)"
    except (ValueError, TypeError):
        pass

    # Texto
    max_len = no_nulos.str.len().max()
    return "TEXT (Texto Largo)" if max_len > 255 else "VARCHAR (Texto Corto)"
