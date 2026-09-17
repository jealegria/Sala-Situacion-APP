"""
sidebar.py
==========
Menu lateral izquierdo de la aplicacion.
Cada boton del menu se registra con add_menu_item().
Al hacer click, emite la senal page_changed con el nombre de la pagina.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QSpacerItem, QSizePolicy
from PyQt6.QtCore import pyqtSignal, Qt
from app.config import theme


class Sidebar(QWidget):
    """Panel lateral con botones de navegacion."""

    page_changed = pyqtSignal(str)   # Emite el nombre de la pagina seleccionada

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(theme.SIDEBAR_WIDTH)

        self._buttons: dict[str, QPushButton] = {}
        self._current: str | None = None

        self._build_ui()

    # ─── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(
            theme.SIDEBAR_PADDING, 24,
            theme.SIDEBAR_PADDING, 24
        )
        self._layout.setSpacing(4)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Nombre de la app en la parte superior
        app_label = QLabel("Sala de\nSituacion")
        app_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        app_label.setStyleSheet(
            f"color: {theme.COLOR_TEXT_PRIMARY};"
            f"font-size: {theme.FONT_SIZE_SUBTITLE}px;"
            f"font-weight: bold;"
            f"padding-bottom: 20px;"
            f"padding-left: 4px;"
        )
        self._layout.addWidget(app_label)

        # Separador visual
        separator = QWidget()
        separator.setFixedHeight(1)
        separator.setStyleSheet(f"background-color: {theme.COLOR_SEPARATOR};")
        self._layout.addWidget(separator)
        self._layout.addSpacing(12)

        # Los botones de menu se agregan desde fuera con add_menu_item()
        # El spacer al fondo lo agregamos al final de la configuracion
        self._spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

    def finalize(self):
        """Llamar despues de agregar todos los items para insertar el spacer final."""
        self._layout.addSpacerItem(self._spacer)

    # ─── API publica ─────────────────────────────────────────────────────────

    def add_menu_item(self, key: str, label: str):
        """
        Agrega un boton al menu lateral.
        key:   identificador interno de la pagina
        label: texto visible en el boton
        """
        btn = QPushButton(label)
        btn.setFixedHeight(theme.BUTTON_HEIGHT)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setProperty("selected", False)
        btn.clicked.connect(lambda checked=False, k=key: self._on_click(k))
        self._buttons[key] = btn
        self._layout.addWidget(btn)

    def select(self, key: str):
        """Marca el boton indicado como seleccionado y deselecciona el resto."""
        for k, btn in self._buttons.items():
            selected = k == key
            btn.setProperty("selected", selected)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._current = key

    # ─── Internos ────────────────────────────────────────────────────────────

    def _on_click(self, key: str):
        self.select(key)
        self.page_changed.emit(key)
