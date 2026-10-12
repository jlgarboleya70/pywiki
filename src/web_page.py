import os
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEnginePage

from compiler import convert_file
from path_utils import resolve_link_to_html

import sys
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

# ========= Gestionamos el visor de webs que hay incrustado en la app

class PaginaWikiWeb(QWebEnginePage):

    """QWebEnginePage con navegación especial para enlaces locales de la wiki."""

    def __init__(self, ventana_parent, tabla):
        super().__init__(ventana_parent)
        self.ventana = ventana_parent
        self.tabla = tabla

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):

        print(f"Han pinchado en {nav_type} y de enlaces es {QWebEnginePage.NavigationTypeLinkClicked}")

        # Si el usuario hace clic en un enlace que termina en .pdf
        if (
            nav_type == QWebEnginePage.NavigationTypeLinkClicked
            and url.path().lower().endswith(".pdf")
        ):
          # Abrir con el visor de PDF predeterminado del sistema operativo
          QDesktopServices.openUrl(url)
          return False  # Bloquear la carga dentro de PyQt5

        # Si el usuario hace clic en un enlace remoto lo abro en el browser
        if nav_type == QWebEnginePage.NavigationTypeLinkClicked:

            if url.isLocalFile():

                # El enlace apunta a un archivo local
                ruta = url.toLocalFile()

                print(f"*** Enlace local. Mirando existencia de {ruta} en el filesystem")

                #if not os.path.exists(ruta):
                #    QDesktopServices.openUrl(url)
                #    # return False

            else:

                print("*** Enlace remoto")

                # El enlace es remoto (http/https)
                QDesktopServices.openUrl(url)
                return False



        if nav_type == QWebEnginePage.NavigationTypeLinkClicked and url.isLocalFile():

            ruta_local = os.path.abspath(url.toLocalFile())
            print(f"Ruta local {ruta_local}")

            if os.path.exists(ruta_local) and not os.path.isdir(ruta_local):
                return super().acceptNavigationRequest(url, nav_type, is_main_frame)

            if os.path.isdir(ruta_local):
                ruta_html = os.path.join(ruta_local, "index.html")
            elif not ruta_local.lower().endswith(".html"):
                ruta_html = ruta_local + ".html"
            else:
                ruta_html = ruta_local

            print(f"ruta html {ruta_html}")

            # Dentro de acceptNavigationRequest en web_page.py, cuando la navegación sea exitosa:
            # ...
            if os.path.exists(ruta_html):
                self.ventana.visor.setUrl(QUrl.fromLocalFile(ruta_html))
                self.ventana.seleccionar_item_en_lista(ruta_html) # Opcional: resalta en el panel izquierdo
                return False

            ruta_wiki = os.path.splitext(ruta_html)[0] + ".wiki"
            print(f"ruta wiki {ruta_wiki}")

            # intento servirlo complando si no esta compilado
            if os.path.exists(ruta_wiki) and convert_file(ruta_wiki, ruta_html, self.tabla):
                   self.ventana.visor.setUrl(QUrl.fromLocalFile(ruta_html))
                   return False

            print(f"gestionando inexistencia")
            # No existe nada: ofrecer crear la página.
            self.ventana.gestionar_pagina_inexistente(ruta_html)
            return False

        # if not local file
        return super().acceptNavigationRequest(
            url,
            nav_type,
            is_main_frame,
        )


