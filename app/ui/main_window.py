"""
main_window.py
==============
Ventana principal de la aplicacion.
Orquesta el Sidebar y el area de contenido (QStackedWidget).
Para agregar una nueva pagina:
  1. Crear el modulo en app/ui/pages/
  2. Importarlo aqui y registrarlo con _register_page()
"""
from PyQt6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QStackedWidget
from PyQt6.QtCore import Qt

from app.config import theme
from app.ui.sidebar import Sidebar
from app.ui.pages.normalizar import NormalizarPage
from app.ui.pages.procesos import ProcesosPage
from app.ui.pages.informes import InformesPage


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

        # Sidebar
        self._sidebar = Sidebar()
        self._sidebar.page_changed.connect(self._navigate)

        # Area de contenido
        self._stack = QStackedWidget()
        self._stack.setObjectName("content_area")

        root_layout.addWidget(self._sidebar)
        root_layout.addWidget(self._stack)

    # ─── Registro de paginas ─────────────────────────────────────────────────

    def _register_pages(self):
        """
        Define el menu y las paginas disponibles.
        Agregar nuevas paginas aqui siguiendo el mismo patron.
        """
        self._register_page("normalizar", "Normalizar", NormalizarPage())
        self._register_page("procesos",   "Procesos",   ProcesosPage())
        self._register_page("informes",   "Informes",   InformesPage())

    def _register_page(self, key: str, label: str, widget: QWidget):
        """Registra una pagina: agrega boton al sidebar y widget al stack."""
        self._sidebar.add_menu_item(key, label)
        self._stack.addWidget(widget)
        self._pages[key] = widget

    # ─── Navegacion ──────────────────────────────────────────────────────────

    def _navigate(self, key: str):
        """Muestra la pagina correspondiente a la clave dada."""
        page = self._pages.get(key)
        if page:
            self._stack.setCurrentWidget(page)
            self._sidebar.select(key)
