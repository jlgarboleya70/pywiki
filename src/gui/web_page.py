import os
from PyQt5.QtCore import QUrl
from PyQt5.QtWebEngineWidgets import QWebEnginePage
from core.compiler import compilar_sincrono

class PaginaWikiWeb(QWebEnginePage):
    def __init__(self, ventana_parent):
        super().__init__(ventana_parent)
        self.ventana = ventana_parent

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if nav_type == QWebEnginePage.NavigationTypeLinkClicked and url.isLocalFile():
            ruta_local = os.path.abspath(url.toLocalFile())

            if os.path.exists(ruta_local) and not os.path.isdir(ruta_local):
                return super().acceptNavigationRequest(url, nav_type, is_main_frame)

            if os.path.isdir(ruta_local):
                ruta_html = os.path.join(ruta_local, "index.html")
            elif not ruta_local.lower().endswith(".html"):
                ruta_html = ruta_local + ".html"
            else:
                ruta_html = ruta_local

            if os.path.exists(ruta_html):
                self.ventana.visor.setUrl(QUrl.fromLocalFile(ruta_html))
                return False

            ruta_wiki = os.path.splitext(ruta_html)[0] + ".wiki"
            if os.path.exists(ruta_wiki) and compilar_sincrono(ruta_wiki, ruta_html):
                self.ventana.visor.setUrl(QUrl.fromLocalFile(ruta_html))
                return False

            self.ventana.gestionar_pagina_inexistente(ruta_html)
            return False

        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


