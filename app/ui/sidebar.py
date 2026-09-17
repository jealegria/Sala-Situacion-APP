"""
sidebar.py
==========
Menu lateral izquierdo de la aplicacion.

API publica:
  add_menu_item(key, label)              — boton simple de navegacion
  add_menu_group(group_key, label, items) — boton colapsable con sub-items
  finalize()                             — llamar al terminar de agregar items
  select(key)                            — marca un item como seleccionado

Senal:
  page_changed(str)  — emite la key de la pagina cuando el usuario hace click
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel,
    QSpacerItem, QSizePolicy,
)
from PyQt6.QtCore import pyqtSignal, Qt
from app.config import theme


class Sidebar(QWidget):
    """Panel lateral con botones de navegacion, soporta grupos colapsables."""

    page_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(theme.SIDEBAR_WIDTH)

        self._buttons: dict[str, QPushButton] = {}   # key -> boton de item
        self._groups:  dict[str, dict]         = {}   # group_key -> metadata
        self._current: str | None              = None

        self._build_ui()

    # ─── Construccion base ────────────────────────────────────────────────────

    def _build_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(
            theme.SIDEBAR_PADDING, 24,
            theme.SIDEBAR_PADDING, 24
        )
        self._layout.setSpacing(4)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Nombre de la app
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

        # Separador
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background-color: {theme.COLOR_SEPARATOR};")
        self._layout.addWidget(sep)
        self._layout.addSpacing(12)

        self._spacer = QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )

    def finalize(self):
        """Llamar despues de agregar todos los items."""
        self._layout.addSpacerItem(self._spacer)

    # ─── API publica ──────────────────────────────────────────────────────────

    def add_menu_item(self, key: str, label: str):
        """Agrega un boton simple de navegacion."""
        btn = self._make_nav_button(label, indent=False)
        btn.clicked.connect(lambda checked=False, k=key: self._on_item_click(k))
        self._buttons[key] = btn
        self._layout.addWidget(btn)

    def add_menu_group(self, group_key: str, label: str, items: list[tuple[str, str]]):
        """
        Agrega un boton colapsable con sub-items.
        items: lista de (key, label) para cada sub-opcion.
        """
        # Boton cabecera del grupo
        header_btn = self._make_nav_button(f"▸  {label}", indent=False)
        header_btn.setProperty("group_header", True)
        header_btn.clicked.connect(lambda checked=False, gk=group_key: self._toggle_group(gk))
        self._layout.addWidget(header_btn)

        # Contenedor de sub-items (oculto por defecto)
        container = QWidget()
        container.setVisible(False)
        sub_layout = QVBoxLayout(container)
        sub_layout.setContentsMargins(0, 2, 0, 2)
        sub_layout.setSpacing(2)

        sub_buttons: dict[str, QPushButton] = {}
        for key, item_label in items:
            btn = self._make_nav_button(item_label, indent=True)
            btn.clicked.connect(lambda checked=False, k=key: self._on_item_click(k))
            sub_layout.addWidget(btn)
            sub_buttons[key] = btn
            self._buttons[key] = btn

        self._layout.addWidget(container)

        self._groups[group_key] = {
            'header_btn': header_btn,
            'label':      label,
            'container':  container,
            'sub_keys':   [k for k, _ in items],
            'expanded':   False,
        }

    # ─── Seleccion ────────────────────────────────────────────────────────────

    def select(self, key: str):
        """Marca el item indicado como seleccionado y deselecciona el resto."""
        for k, btn in self._buttons.items():
            selected = (k == key)
            btn.setProperty("selected", selected)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._current = key

    # ─── Internos ─────────────────────────────────────────────────────────────

    def _make_nav_button(self, label: str, indent: bool) -> QPushButton:
        btn = QPushButton(label)
        btn.setFixedHeight(theme.BUTTON_HEIGHT if not indent else 38)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setProperty("selected", False)

        left_padding = 28 if indent else 16
        font_size    = theme.FONT_SIZE_SMALL if indent else theme.FONT_SIZE_BASE

        btn.setStyleSheet(
            f"QPushButton {{"
            f"  background-color: transparent;"
            f"  color: {theme.COLOR_TEXT_PRIMARY if not indent else theme.COLOR_TEXT_SECONDARY};"
            f"  border: none;"
            f"  border-radius: 6px;"
            f"  padding: 0 16px 0 {left_padding}px;"
            f"  font-size: {font_size}px;"
            f"  text-align: left;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background-color: {theme.COLOR_BUTTON_HOVER};"
            f"  color: {theme.COLOR_TEXT_PRIMARY};"
            f"}}"
            f"QPushButton[selected=true] {{"
            f"  background-color: {theme.COLOR_BUTTON_ACTIVE};"
            f"  color: {theme.COLOR_TEXT_PRIMARY};"
            f"}}"
        )
        return btn

    def _toggle_group(self, group_key: str):
        group = self._groups.get(group_key)
        if not group:
            return

        expanded = not group['expanded']
        group['expanded'] = expanded
        group['container'].setVisible(expanded)

        arrow = "▾" if expanded else "▸"
        group['header_btn'].setText(f"{arrow}  {group['label']}")

    def _on_item_click(self, key: str):
        self.select(key)
        self.page_changed.emit(key)
