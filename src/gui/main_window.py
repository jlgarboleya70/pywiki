import os
from PyQt5.QtCore import QFileSystemWatcher, QProcess, QTimer, QUrl
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import (
    QMainWindow, QToolBar, QComboBox, QMessageBox
)

from gui.web_page import PaginaWikiWeb
from core.path_utils import resolver_ruta_wiki, resolver_ruta_html

class NavegadorWiki(QMainWindow):
    def __init__(self, dirname):
        super().__init__()
        self.setWindowTitle("Wiki Local")
        self.resize(1100, 800)

        # Configuración de directorios
        self.raiz_proyecto = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.directorio_src = os.path.join(self.raiz_proyecto, dirname)
        self.directorio_build = self.directorio_src
        self.archivo_wiki_actual = None

        # Watcher y Timers para re-compilación
        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self.al_guardar_wiki)

        self.timer_build = QTimer(self)
        self.timer_build.setSingleShot(True)
        self.timer_build.timeout.connect(self.compilar)

        self.proceso_build = QProcess(self)
        self.proceso_build.finished.connect(self.build_finalizado)

        # Visor Web
        self.visor = QWebEngineView()
        self.pagina_custom = PaginaWikiWeb(self)
        self.visor.setPage(self.pagina_custom)
        self.visor.loadFinished.connect(lambda ok: self.aplicar_css_actual() if ok else None)
        self.setCentralWidget(self.visor)

        self._crear_toolbar()
        self.cargar_index()

    def _crear_toolbar(self):
        toolbar = QToolBar("Barra de Herramientas")
        self.addToolBar(toolbar)

        self.combo_css = QComboBox()
        self.combo_css.addItems(["styles/wiki1.css", "styles/wiki2.css"])
        self.combo_css.currentIndexChanged.connect(self.aplicar_css_actual)
        toolbar.addWidget(self.combo_css)

    def cargar_index(self):
        index_html = os.path.join(self.directorio_build, "index.html")
        if os.path.exists(index_html):
            self.visor.setUrl(QUrl.fromLocalFile(index_html))
            wiki_asociada = resolver_ruta_wiki(index_html, self.directorio_src, self.directorio_build)
            if wiki_asociada:
                self.observar_archivo(wiki_asociada)
        else:
            index_wiki = os.path.join(self.directorio_src, "index.wiki")
            if os.path.exists(index_wiki):
                from core.compiler import compilar_sincrono
                if compilar_sincrono(index_wiki, index_html):
                    self.visor.setUrl(QUrl.fromLocalFile(index_html))
                    self.observar_archivo(index_wiki)
            else:
                self.gestionar_pagina_inexistente(index_html)

    def observar_archivo(self, ruta_wiki):
        if self.archivo_wiki_actual and self.archivo_wiki_actual in self.watcher.files():
            self.watcher.removePath(self.archivo_wiki_actual)
        self.archivo_wiki_actual = ruta_wiki
        if os.path.exists(ruta_wiki):
            self.watcher.addPath(ruta_wiki)

    def al_guardar_wiki(self, path):
        self.timer_build.start(300)

    def compilar(self):
        if not self.archivo_wiki_actual:
            return

        ruta_html = resolver_ruta_html(
            self.archivo_wiki_actual, 
            self.directorio_src, 
            self.directorio_build
        )
        if not ruta_html:
            return

        if self.proceso_build.state() == QProcess.Running:
            self.proceso_build.kill()

        self.proceso_build.start(
            "pandoc", 
            ["-f", "mediawiki", "-t", "html", "-s", "-o", ruta_html, self.archivo_wiki_actual]
        )

    def build_finalizado(self, exit_code, exit_status):
        if exit_code == 0:
            self.visor.reload()
            if self.archivo_wiki_actual and self.archivo_wiki_actual not in self.watcher.files():
                self.watcher.addPath(self.archivo_wiki_actual)

    def aplicar_css_actual(self):
        css_relativo = self.combo_css.currentText()
        ruta_css = os.path.abspath(os.path.join(self.raiz_proyecto, css_relativo))
        if not os.path.exists(ruta_css):
            return

        url_css = QUrl.fromLocalFile(ruta_css).toString()
        js_code = f"""
        (function() {{
            let link = document.getElementById('custom-wiki-style');
            if (!link) {{
                link = document.createElement('link');
                link.id = 'custom-wiki-style';
                link.rel = 'stylesheet';
                link.type = 'text/css';
                document.getElementsByTagName('head')[0].appendChild(link);
            }}
            link.href = '{url_css}';
        }})();
        """
        self.visor.page().runJavaScript(js_code)

    def gestionar_pagina_inexistente(self, ruta_html):
        QMessageBox.warning(
            self, 
            "Página no encontrada", 
            f"No existe el archivo HTML ni el código fuente .wiki correspondiente para:\n{ruta_html}"
        )
