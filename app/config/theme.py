"""
theme.py
========
Definicion centralizada del tema visual de la aplicacion.
Para cambiar colores, fuentes o estilos, modificar SOLO este archivo.
"""

# ─── Paleta de colores ────────────────────────────────────────────────────────
COLOR_BG_PRIMARY      = "#1a1816"   # Fondo principal (negro calido)
COLOR_BG_SECONDARY    = "#232120"   # Fondo secundario / sidebar
COLOR_BG_CONTENT      = "#1e1c1a"   # Fondo del area de contenido
COLOR_BUTTON_ACTIVE   = "#2563eb"   # Boton activo / accion principal
COLOR_BUTTON_HOVER    = "#1d4ed8"   # Hover del boton activo
COLOR_BUTTON_SELECTED = "#1e40af"   # Boton seleccionado en el menu
COLOR_TEXT_PRIMARY    = "#f5f0e6"   # Texto principal
COLOR_TEXT_SECONDARY  = "#a09c94"   # Texto secundario / subtitulos
COLOR_BORDER          = "#2e2c2a"   # Bordes y separadores
COLOR_SEPARATOR       = "#2e2c2a"   # Linea separadora

# ─── Tipografia ──────────────────────────────────────────────────────────────
FONT_FAMILY           = "Segoe UI"
FONT_SIZE_BASE        = 14
FONT_SIZE_SMALL       = 11
FONT_SIZE_TITLE       = 20
FONT_SIZE_SUBTITLE    = 16

# ─── Dimensiones ─────────────────────────────────────────────────────────────
SIDEBAR_WIDTH         = 200
WINDOW_MIN_WIDTH      = 900
WINDOW_MIN_HEIGHT     = 600
BUTTON_HEIGHT         = 44
SIDEBAR_PADDING       = 12

# ─── Stylesheet global ────────────────────────────────────────────────────────
def get_app_stylesheet() -> str:
    """
    Retorna el stylesheet QSS global de la aplicacion.
    Se aplica una sola vez al QApplication en main.py.
    """
    return f"""
        /* ── Base ── */
        QWidget {{
            background-color: {COLOR_BG_PRIMARY};
            color: {COLOR_TEXT_PRIMARY};
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE_BASE}px;
        }}

        /* ── Sidebar ── */
        #sidebar {{
            background-color: {COLOR_BG_SECONDARY};
            border-right: 1px solid {COLOR_BORDER};
        }}

        /* ── Botones del sidebar ── */
        #sidebar QPushButton {{
            background-color: transparent;
            color: {COLOR_TEXT_PRIMARY};
            border: none;
            border-radius: 6px;
            padding: 0 16px;
            height: {BUTTON_HEIGHT}px;
            font-size: {FONT_SIZE_BASE}px;
            text-align: left;
        }}
        #sidebar QPushButton:hover {{
            background-color: {COLOR_BUTTON_HOVER};
        }}
        #sidebar QPushButton[selected="true"] {{
            background-color: {COLOR_BUTTON_ACTIVE};
            color: {COLOR_TEXT_PRIMARY};
        }}

        /* ── Area de contenido ── */
        #content_area {{
            background-color: {COLOR_BG_CONTENT};
        }}

        /* ── Titulo de pagina ── */
        #page_title {{
            color: {COLOR_TEXT_PRIMARY};
            font-size: {FONT_SIZE_TITLE}px;
            font-weight: bold;
        }}

        /* ── Texto secundario ── */
        #page_subtitle {{
            color: {COLOR_TEXT_SECONDARY};
            font-size: {FONT_SIZE_SMALL}px;
        }}

        /* ── Scrollbars ── */
        QScrollBar:vertical {{
            background: {COLOR_BG_SECONDARY};
            width: 8px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical {{
            background: {COLOR_BORDER};
            border-radius: 4px;
            min-height: 20px;
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
    """
