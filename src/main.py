import sys
import os

from PyQt5.QtWidgets import QApplication
from main_window import NavegadorWiki

# Asegura que la raíz del proyecto esté en el sys.path
PROYECTO_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROYECTO_ROOT not in sys.path:
    sys.path.insert(0, PROYECTO_ROOT)

def cargar_tabla_caracteres(ruta_fichero):
  tabla = {}

  with open(ruta_fichero, "r", encoding="utf-8") as f:
    for linea in f:
      # Limpiar espacios en blanco al principio y final
      linea_limpia = linea.strip()

      # Ignorar líneas vacías o comentarios que empiezan por '#'
      if not linea_limpia or linea_limpia.startswith("#"):
        continue

      # Separar por espacios (o tabuladores)
      partes = linea_limpia.split()
      if len(partes) >= 2:

        escape_secuencia = partes[0]  # Ej: "\\n" o "\x00"
        codigo_str = partes[1]  # Ej: "0041" o "00a0"

        # Convertir el código numérico (asumiendo formato hexadecimal de hasta 4 dígitos)
        # Si tu código fuera decimal, cambia la base a 10: int(codigo_str, 10)
        codigo_num = int(codigo_str, 10)

        # Obtener el carácter real UTF-8 correspondiente
        caracter = codigo_num
        if escape_secuencia=="\\alpha":
            print(f"En posicion {escape_secuencia} he guardado codigo {codigo_num}")

        # Guardar en el diccionario
        tabla[escape_secuencia] = caracter

  return tabla


# --- Ejemplo de uso ---
# mi_tabla = cargar_tabla_caracteres("ruta/a/tu/tabla.txt")
# print(mi_tabla)

def main(tablachars):
    if len(sys.argv) != 2:
        print("Uso: python main.py <nombre wiki>")
        sys.exit(1)

    dirname = sys.argv[1]
    print("Abriendo wiki:", dirname)

    app = QApplication(sys.argv)
    ventana = NavegadorWiki(tablachars, dirname)
    ventana.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    tablachars = cargar_tabla_caracteres("leer.txt")
    main(tablachars)



