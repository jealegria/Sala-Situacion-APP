"""
main.py
=======
Punto de entrada de Sala de Situacion APP.
Inicializa QApplication, aplica el tema global y lanza la ventana principal.
"""
import sys
from PyQt6.QtWidgets import QApplication
from app.config.theme import get_app_stylesheet
from app.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(get_app_stylesheet())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
