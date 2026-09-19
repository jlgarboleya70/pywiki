import sys
import os

# Asegura que la raíz del proyecto esté en el sys.path
PROYECTO_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROYECTO_ROOT not in sys.path:
    sys.path.insert(0, PROYECTO_ROOT)

from PyQt5.QtWidgets import QApplication
from gui.main_window import NavegadorWiki

def main():
    if len(sys.argv) != 2:
        print("Uso: python main.py <nombre wiki>")
        sys.exit(1)

    dirname = sys.argv[1]
    print("Abriendo wiki:", dirname)

    app = QApplication(sys.argv)
    ventana = NavegadorWiki(dirname)
    ventana.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()

