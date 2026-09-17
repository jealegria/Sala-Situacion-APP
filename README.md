# Sala de Situacion APP

Aplicacion de gestion hospitalaria. Desarrollada en Python + PyQt6.

## Estructura del proyecto

```
Sala-Situacion-APP/
├── main.py                         # Punto de entrada
├── requirements.txt                # Dependencias
├── sala_situacion.spec             # Config de compilacion (PyInstaller)
├── app/
│   ├── config/
│   │   └── theme.py                # Paleta de colores, fuentes, stylesheet global
│   └── ui/
│       ├── main_window.py          # Ventana principal
│       ├── sidebar.py              # Menu lateral
│       └── pages/
│           ├── normalizar.py
│           ├── procesos.py
│           └── informes.py
```

## Instalacion

```bash
pip install -r requirements.txt
```

## Ejecutar en desarrollo

```bash
python main.py
```

## Compilar a .exe

```bash
pyinstaller sala_situacion.spec
```

El ejecutable queda en `dist/SalaDeSituacion.exe`.
