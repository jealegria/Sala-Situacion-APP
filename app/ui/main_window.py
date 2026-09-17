"""
main_window.py
==============
Ventana principal de la aplicacion.
Orquesta el Sidebar y el area de contenido (QStackedWidget).

Para agregar una nueva pagina simple:
  1. Crear el modulo en app/ui/pages/
  2. Importarlo y registrarlo con _register_page()

Para agregar un grupo colapsable al menu:
  1. Crear los modulos de sub-paginas
  2. Importarlos y registrarlos con _register_group()
"""
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget
from PyQt6.QtCore import Qt

from app.config import theme
from app.ui.sidebar import Sidebar

# Paginas simples
from app.ui.pages.normalizar import NormalizarPage
from app.ui.pages.procesos import ProcesosPage

# Sub-paginas de Informes
from app.ui.pages.informes.guardia      import GuardiaPage
from app.ui.pages.informes.sm_tocogineco import SmTocoginecPage
from app.ui.pages.informes.vacunatorio   import VacunatorioPage
from app.ui.pages.informes.imagenes     import ImagenesPage


class MainWindow(QMainWindow):
    """Ventana principal de Sala de Situacion APP."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sala de Situacion APP")
        self.setMinimumSize(theme.WINDOW_MIN_WIDTH, theme.WINDOW_MIN_HEIGHT)

        self._pages: dict[str, QWidget] = {}
        self._build_ui()
        self._register_pages()
        self._sidebar.finalize()

        # Seleccionar la primera pagina por defecto
        self._navigate("normalizar")

    # ─── Construccion de la UI ───────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self._sidebar = Sidebar()
        self._sidebar.page_changed.connect(self._navigate)

        self._stack = QStackedWidget()
        self._stack.setObjectName("content_area")

        root_layout.addWidget(self._sidebar)
        root_layout.addWidget(self._stack)

    # ─── Registro de paginas ─────────────────────────────────────────────────

    def _register_pages(self):
        """
        Define el menu y las paginas disponibles.

        Paginas simples    -> _register_page(key, label, widget)
        Grupos colapsables -> _register_group(group_key, label, [(key, label, widget), ...])
        """
        _register_page  = self._register_page
        _register_group = self._register_group

        # Paginas simples del menu principal
        _register_page("normalizar", "Normalizar", NormalizarPage())
        _register_page("procesos",   "Procesos",   ProcesosPage())

        # Grupo colapsable: Informes
        _register_group(
            group_key="informes",
            label="Informes",
            items=[
                ("inf_guardia",       "Guardia",          GuardiaPage()),
                ("inf_sm_tocogineco", "SM y Tocogineco",  SmTocoginecPage()),
                ("inf_vacunatorio",   "Vacunatorio",      VacunatorioPage()),
                ("inf_imagenes",      "Imágenes",         ImagenesPage()),
            ]
        )

    def _register_page(self, key: str, label: str, widget: QWidget):
        """Registra una pagina simple: boton en sidebar + widget en el stack."""
        self._sidebar.add_menu_item(key, label)
        self._stack.addWidget(widget)
        self._pages[key] = widget

    def _register_group(self, group_key: str, label: str, items: list[tuple]):
        """
        Registra un grupo colapsable en el sidebar.
        items: lista de (key, label, widget)
        """
        sidebar_items = [(key, lbl) for key, lbl, _ in items]
        self._sidebar.add_menu_group(group_key, label, sidebar_items)

        for key, _, widget in items:
            self._stack.addWidget(widget)
            self._pages[key] = widget

    # ─── Navegacion ──────────────────────────────────────────────────────────

    def _navigate(self, key: str):
        """Muestra la pagina correspondiente a la clave dada."""
        page = self._pages.get(key)
        if page:
            self._stack.setCurrentWidget(page)
            self._sidebar.select(key)
