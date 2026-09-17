"""
paths.py
========
Rutas centralizadas de la aplicacion.
Para cambiar donde se guardan los outputs, modificar solo este archivo.
"""
import sys
from pathlib import Path


def get_base_path() -> Path:
    """Raiz del proyecto, funciona tanto en desarrollo como compilado (.exe)."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def get_outputs_path() -> Path:
    """Carpeta raiz de todos los outputs de la aplicacion."""
    return get_base_path() / "Outputs"


def get_module_output_path(module_name: str) -> Path:
    """
    Retorna la carpeta de output para un modulo dado.
    La crea si no existe.
    """
    path = get_outputs_path() / module_name
    path.mkdir(parents=True, exist_ok=True)
    return path
