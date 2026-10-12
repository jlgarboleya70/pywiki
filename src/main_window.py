import os
import subprocess
import shutil
import platform

from datetime import datetime
import calendar

from PyQt5.QtCore import QFileSystemWatcher, QProcess, Qt, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from compiler import convert_file
from path_utils import html_to_wiki, listar_ficheros_wiki, wiki_to_html
from web_page import PaginaWikiWeb

from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QShortcut

def a_cygdrive_old(ruta_windows):
    ruta_windows = os.path.abspath(ruta_windows)
    unidad = ruta_windows[0].lower()   # c, d, etc.
    resto = ruta_windows[2:].replace("\\", "/")
    return f"/cygdrive/{unidad}{resto}"

def a_cygdrive(ruta):
    ruta = os.path.abspath(ruta)

    # Si ya es /cygdrive/... NO convertir
    if ruta.replace("\\", "/").startswith("/cygdrive/"):
        return ruta.replace("\\", "/")

    # Si es ruta Windows tipo C:\...
    if len(ruta) > 2 and ruta[1] == ":":
        unidad = ruta[0].lower()
        resto = ruta[2:].replace("\\", "/")
        return f"/cygdrive/{unidad}{resto}"

    # Si es ruta Linux normal, devolver tal cual
    return ruta.replace("\\", "/")


import os
import platform

def detectar_entorno():
    ostype = os.environ.get("OSTYPE", "").lower()
    sistema = platform.system().lower()

    if "cygwin" in ostype:
        return "cygwin"      # MobaXterm
    if sistema == "windows":
        return "windows"
    if sistema == "linux":
        return "linux"
    return "desconocido"

class NavegadorWiki(QMainWindow):

    def __init__(self, tabla_chars, dirname="."):
        
        super().__init__()
        print(f"[DEBUG] Inicializando NavegadorWiki con dirname='{dirname}'...")
        self.setWindowTitle("Wiki Local")
        self.resize(1200, 800)
        self.tabla_chars = tabla_chars

        # desactivo el sandbox de Qt
        os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"


        # =============== detectamos entorno e inicializamos cosas
        
        entorno = detectar_entorno()

        # 1. MobaXterm/Cygwin → NO soportado
        if entorno == "cygwin":
            print("MobaXterm/Cygwin no soportado por QtWebEngine. Usa Windows nativo.")
            exit(0)

        # 2. Windows nativo → rutas Windows normales
        if entorno == "windows":
            ruta_win = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.raiz_proyecto = ruta_win

            if os.path.isabs(dirname):
                self.directorio_src = dirname
            else:
                self.directorio_src = os.path.abspath(
                    os.path.join(self.raiz_proyecto, dirname)
                )

            self.directorio_build = self.directorio_src
            self.archivo_wiki_actual = None
            print(f"*** Ajustado {self.directorio_build} y {self.directorio_src}")

        # 3. Linux → rutas Linux normales
        if entorno == "linux":
            self.raiz_proyecto = os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )

            if os.path.isabs(dirname):
                self.directorio_src = dirname
            else:
                self.directorio_src = os.path.abspath(
                    os.path.join(self.raiz_proyecto, dirname)
                )

            self.directorio_build = self.directorio_src
            self.archivo_wiki_actual = None

        # 4. Configurar el atajo de teclado Ctrl+F en __init__
        self.shortcut_find = QShortcut(QKeySequence("Ctrl+F"), self)
        self.shortcut_find.activated.connect(self.mostrar_y_enfocar_busqueda)

        # Atajo extra para cerrar con Escape
        self.shortcut_escape = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.shortcut_escape.activated.connect(self.ocultar_barra_busqueda)


        # ================== entorno inicializado. seguimos
  
        print(f"[DEBUG] Raíz del proyecto: {self.raiz_proyecto}")
        print(f"[DEBUG] Directorio de notas/wiki: {self.directorio_src}")

        # Watcher y Timers para re-compilación automática
        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self.al_guardar_wiki)

        # vigilamos tambien posibles borrados de ficheros
        self.watcher.addPath(self.directorio_src)
        self.watcher.directoryChanged.connect(self.al_refrescar_directorios)

        self.timer_build = QTimer(self)
        self.timer_build.setSingleShot(True)
        self.timer_build.timeout.connect(self.compilar)

        # Construir Interfaz Gráfica (Barra lateral + Visor)
        print("[DEBUG] Construyendo la interfaz de usuario...")
        self._init_ui()
        print(f"*** construida")

        # Toolbar
        self._crear_toolbar()

        # Cargar lista de wikis y abrir la portada inicial
        print("[DEBUG] Escaneando directorio para poblar lista lateral...")
        self.cargar_lista_wikis()

        # Actualizar URL y CSS tras la carga
        # self.visor.urlChanged.connect(self.actualizar_url)
        self.visor.loadFinished.connect(
            lambda ok: self.aplicar_css_actual() if ok else None
        )

        print("[DEBUG] Cargando portada inicial (index)...")
        self.cargar_index()


    # ------------------------------------------------------------------
    # GUI & TOOLBAR
    # ------------------------------------------------------------------

    import calendar
    from datetime import datetime
    from PyQt5.QtCore import QUrl

    def mostrar_calendario_wikis(self):
        """Genera una página HTML con el calendario de 3 meses (pasado, actual, próximo)
           y comprueba la existencia de páginas .wiki asociadas a cada día."""
        
        ahora = datetime.now()
        anio_actual = ahora.year
        mes_actual = ahora.month

        # Calcular meses anterior y siguiente
        # Mes anterior
        if mes_actual == 1:
            mes_ant, anio_ant = 12, anio_actual - 1
        else:
            mes_ant, anio_ant = mes_actual - 1, anio_actual

        # Mes siguiente
        if mes_actual == 12:
            mes_sig, anio_sig = 1, anio_actual + 1
        else:
            mes_sig, anio_sig = mes_actual + 1, anio_actual

        cal = calendar.Calendar(firstweekday=0) # Lunes como primer día

        def generar_tabla_mes(anio, mes):
            nombre_mes = calendar.month_name[mes].capitalize()
            # Generar matriz de semanas (días del mes)
            dias_mes = cal.monthdayscalendar(anio, mes)
            
            html_dias = ""
            for semana in dias_mes:
                html_dias += "<tr>"
                for dia in semana:
                    if dia == 0:
                        html_dias += "<td class='vacio'></td>"
                    else:
                        nombre_wiki = f"{anio}-{mes:02d}-{dia:02d}.wiki"
                        ruta_wiki = os.path.join(self.directorio_src, nombre_wiki)
                        ruta_html = os.path.splitext(ruta_wiki)[0] + ".html"
                        
                        existe = os.path.exists(ruta_wiki) or os.path.exists(ruta_html)
                        
                        if existe:
                            # Si existe, enlace normal para ver el HTML
                            url_fichero = QUrl.fromLocalFile(os.path.abspath(ruta_html)).toString()
                            html_dias += f"<td><a href='{url_fichero}' class='existe' title='Ver nota'>{dia}</a></td>"
                        else:
                            # Si NO existe, creamos un enlace con un esquema personalizado o parámetro 
                            # para que tu aplicación sepa que debe crear la página de ese día.
                            # Por ejemplo, usando un enlace del tipo: wiki-crear://2026-10-09
                            url_crear = f"wiki-crear://{anio}-{mes:02d}-{dia:02d}"
                            html_dias += f"<td><a href='{url_crear}' class='no-existe' title='Crear nota para el {dia}'>{dia}</a></td>"

                            # Formato de nombre de archivo para el día, ej: 2026-10-09.wiki o similar
                            # Ajusta la nomenclatura según cómo nombres tus páginas de diario/wiki (ej: YYYY-MM-DD)
                            nombre_wiki = f"{anio}-{mes:02d}-{dia:02d}.wiki"
                            ruta_wiki = os.path.join(self.directorio_src, nombre_wiki)
                            ruta_html = os.path.splitext(ruta_wiki)[0] + ".html"
                        
                html_dias += "</tr>"

            dias_semana = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
            cabecera_semana = "".join([f"<th>{d}</th>" for d in dias_semana])

            return f"""
            <div class="mes-card">
                <h3>{nombre_mes} {anio}</h3>
                <table>
                    <thead><tr>{cabecera_semana}</tr></thead>
                    <tbody>{html_dias}</tbody>
                </table>
            </div>
            """

        html_ant = generar_tabla_mes(anio_ant, mes_ant)
        html_act = generar_tabla_mes(anio_actual, mes_actual)
        html_sig = generar_tabla_mes(anio_sig, mes_sig)

        html_final = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{
                    font-family: sans-serif;
                    background-color: #fafafa;
                    color: #333;
                    padding: 20px;
                }}
                h2 {{
                    color: #0277bd;
                    border-bottom: 2px solid #0277bd;
                    padding-bottom: 8px;
                }}
                .calendarios-container {{
                    display: flex;
                    gap: 20px;
                    flex-wrap: wrap;
                }}
                .mes-card {{
                    background: white;
                    border: 1px solid #ddd;
                    border-radius: 6px;
                    padding: 15px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                }}
                .mes-card h3 {{
                    margin-top: 0;
                    text-align: center;
                    color: #444;
                    font-size: 16px;
                }}
                table {{
                    border-collapse: collapse;
                    width: 220px;
                }}
                th, td {{
                    text-align: center;
                    padding: 6px;
                    font-size: 13px;
                }}
                th {{
                    color: #666;
                }}
                .vacio {{
                    background: transparent;
                }}
                a.existe {{
                    color: #0277bd;
                    font-weight: bold;
                    text-decoration: none;
                    background-color: #e1f5fe;
                    display: block;
                    border-radius: 4px;
                }}
                a.existe:hover {{
                    background-color: #b3e5fc;
                    text-decoration: underline;
                }}
                span.no-existe {{
                    color: #c62828;
                    font-weight: bold;
                    background-color: #ffebee;
                    display: block;
                    border-radius: 4px;
                }}
            </style>
        </head>
        <body>
            <h2>Calendario de Notas / Wikis</h2>
            <div class="calendarios-container">
                {html_ant}
                {html_act}
                {html_sig}
            </div>
        </body>
        </html>
        """

        self.visor.setHtml(html_final)

    def al_refrescar_directorios(self, path):
        print(f"[DEBUG] Directorio modificado detectado: {path}. Actualizando lista...")
        self.cargar_lista_wikis()

    def ejecutar_grep(self):

        texto_busqueda = self.txt_buscar.text().strip()

        if not texto_busqueda:
            QMessageBox.information(
                self,
                "Buscador",
                "Por favor, escribe una o varias palabras para buscar."
            )
            return

        # ------------------------------------------------------------
        # Separar las palabras de búsqueda
        #
        # "perro gato casa"
        #
        # se convierte en:
        #
        # ["perro", "gato", "casa"]
        #
        # La búsqueda será AND: todas deben aparecer en la línea.
        # ------------------------------------------------------------

        palabras = texto_busqueda.lower().split()

        ruta_wiki = self.obtener_wiki_actual()

        if not ruta_wiki:
            QMessageBox.warning(
                self,
                "Aviso",
                "No se ha encontrado el fichero .wiki correspondiente al HTML actual.",
            )
            return

        ruta_dir = os.path.dirname(
            os.path.expanduser(ruta_wiki)
        )

        resultados = []

        # ------------------------------------------------------------
        # Búsqueda recursiva
        # ------------------------------------------------------------

        for root, dirs, files in os.walk(ruta_dir):

            for nombre in files:

                if not nombre.lower().endswith(".wiki"):
                    continue

                ruta_fichero = os.path.join(
                    root,
                    nombre
                )

                try:

                    with open(
                        ruta_fichero,
                        "r",
                        encoding="utf-8",
                        errors="ignore"
                    ) as f:

                        for num_linea, linea in enumerate(
                            f,
                            start=1
                        ):

                            linea_lower = linea.lower()

                            # ------------------------------------------------
                            # AND:
                            # todas las palabras tienen que estar presentes
                            # en la misma línea
                            # ------------------------------------------------

                            if all(
                                palabra in linea_lower
                                for palabra in palabras
                            ):

                                resultados.append({
                                    "ruta": ruta_fichero,
                                    "nombre": nombre,
                                    "linea": num_linea,
                                    "texto": linea.strip(),
                                })

                except Exception as e:

                    print(
                        f"[WARN] No se pudo leer "
                        f"{ruta_fichero}: {e}"
                    )

        # ------------------------------------------------------------
        # Escape HTML
        #
        # Muy importante porque el contenido del .wiki puede contener
        # etiquetas HTML.
        # ------------------------------------------------------------

        import html
        from urllib.parse import quote

        def escapar(texto):
            return html.escape(
                texto,
                quote=True
            )

        # ------------------------------------------------------------
        # Construir resultados HTML
        # ------------------------------------------------------------

        resultados_html = []

        for resultado in resultados:

            ruta_fichero = resultado["ruta"]
            nombre = resultado["nombre"]
            num_linea = resultado["linea"]
            texto = resultado["texto"]

            # --------------------------------------------------------
            # Suponemos:
            #
            #   pagina.wiki
            #
            # tiene su HTML en:
            #
            #   pagina.html
            #
            # en el mismo directorio.
            # --------------------------------------------------------

            ruta_html = os.path.splitext(
                ruta_fichero
            )[0] + ".html"

            # Convertir la ruta local a URL
            # para que sea clickable desde el visor.
            #
            # quote() permite que funcionen espacios y caracteres
            # especiales en nombres de ficheros.
            ruta_html_url = (
                "file:///"
                + quote(
                    os.path.abspath(ruta_html)
                    .replace("\\", "/"),
                    safe="/:"
                )
            )

            # --------------------------------------------------------
            # Mostrar ruta relativa respecto a la wiki actual.
            # Queda bastante más limpio que mostrar toda la ruta
            # absoluta del ordenador.
            # --------------------------------------------------------

            try:
                ruta_mostrada = os.path.relpath(
                    ruta_fichero,
                    ruta_dir
                )
            except Exception:
                ruta_mostrada = ruta_fichero

            ruta_mostrada = ruta_mostrada.replace(
                "\\",
                "/"
            )

            # --------------------------------------------------------
            # HTML del resultado
            # --------------------------------------------------------

            resultado_html = f"""
            <div class="resultado">
                <div class="cabecera-resultado">
                    <a href="{ruta_html_url}" class="wiki-link">
                        {escapar(ruta_mostrada)}
                    </a>

                    <span class="linea">
                        línea {num_linea}
                    </span>
                </div>

                <div class="contenido">
                    {escapar(texto)}
                </div>
            </div>
            """

            resultados_html.append(
                resultado_html
            )

        # ============================================================
        # RESULTADOS ENCONTRADOS
        # ============================================================

        if resultados:

            salida_html = "\n".join(
                resultados_html
            )

            palabras_mostradas = " AND ".join(
                escapar(p)
                for p in palabras
            )

            html_final = f"""
            <!DOCTYPE html>
            <html>
            <head>

                <meta charset="UTF-8">

                <style>

                    body {{
                        font-family: sans-serif;
                        font-size: 14px;
                        line-height: 1.5;
                        padding: 20px;
                        background-color: #fafafa;
                        color: #333;
                    }}

                    h3 {{
                        color: #0277bd;
                        border-bottom: 2px solid #0277bd;
                        padding-bottom: 8px;
                        margin-bottom: 20px;
                    }}

                    .resumen {{
                        color: #666;
                        margin-bottom: 20px;
                    }}

                    .resultado {{
                        background: white;
                        border: 1px solid #ddd;
                        border-radius: 5px;
                        margin-bottom: 10px;
                        padding: 10px 14px;
                    }}

                    .cabecera-resultado {{
                        margin-bottom: 6px;
                    }}

                    .wiki-link {{
                        color: #0277bd;
                        font-weight: bold;
                        text-decoration: none;
                    }}

                    .wiki-link:hover {{
                        text-decoration: underline;
                        color: #01579b;
                    }}

                    .linea {{
                        color: #888;
                        font-size: 12px;
                        margin-left: 10px;
                    }}

                    .contenido {{
                        font-family: monospace;
                        white-space: pre-wrap;
                        color: #444;
                        background: #f5f5f5;
                        border-radius: 3px;
                        padding: 7px;
                    }}

                </style>

            </head>

            <body>

                <h3>
                    Resultados de búsqueda
                </h3>

                <div class="resumen">
                    Búsqueda:
                    <strong>{palabras_mostradas}</strong>
                    &nbsp; — &nbsp;
                    {len(resultados)} coincidencia(s)
                </div>

                {salida_html}

            </body>
            </html>
            """

        # ============================================================
        # SIN RESULTADOS
        # ============================================================

        else:

            palabras_mostradas = " AND ".join(
                escapar(p)
                for p in palabras
            )

            html_final = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">

                <style>

                    body {{
                        font-family: sans-serif;
                        padding: 30px;
                        background-color: #fafafa;
                        color: #333;
                    }}

                    h3 {{
                        color: #c62828;
                    }}

                    .busqueda {{
                        font-weight: bold;
                    }}

                </style>

            </head>

            <body>

                <h3>
                    No se encontraron coincidencias
                </h3>

                <p>
                    No se encontró ninguna línea que contenga
                    <span class="busqueda">
                        todas
                    </span>
                    estas palabras:
                </p>

                <p>
                    <strong>{palabras_mostradas}</strong>
                </p>

            </body>
            </html>
            """

        # ------------------------------------------------------------
        # Mostrar resultados
        # ------------------------------------------------------------

        self.visor.setHtml(
            html_final
        )


    def _crear_toolbar(self):

        toolbar = QToolBar("Barra de Herramientas")
        self.addToolBar(toolbar)

        btn_atras = QPushButton("←")
        btn_atras.clicked.connect(self.visor.back)
        toolbar.addWidget(btn_atras)

        btn_adelante = QPushButton("→")
        btn_adelante.clicked.connect(self.visor.forward)
        toolbar.addWidget(btn_adelante)

        btn_recargar = QPushButton("↻")
        btn_recargar.clicked.connect(self.visor.reload)
        toolbar.addWidget(btn_recargar)

        # boton para mostrar calendario
        btn_calendario = QPushButton("📅 Calendario")
        btn_calendario.setStyleSheet("background-color: #e3f2fd; font-weight: bold;")
        btn_calendario.clicked.connect(self.mostrar_calendario_wikis)
        toolbar.addWidget(btn_calendario)

        # Cambiamos el textbox que no usabas por el buscador Grep
        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("Palabra a buscar...")
        self.txt_buscar.returnPressed.connect(self.ejecutar_grep) # Buscar también al pulsar Enter
        toolbar.addWidget(self.txt_buscar)

        # Cambiamos el botón "Abrir HTML" por "Buscar"
        btn_buscar = QPushButton("🔍 Buscar")
        btn_buscar.setStyleSheet("background-color: #fffde7; font-weight: bold;")
        btn_buscar.clicked.connect(self.ejecutar_grep)
        toolbar.addWidget(btn_buscar)


        btn_editar = QPushButton("📝 Editar (.wiki)")
        btn_editar.setStyleSheet(
            "font-weight: bold; background-color: #e1f5fe;"
        )
        btn_editar.clicked.connect(self.editar_fuente_wiki)
        toolbar.addWidget(btn_editar)
        

        self.btn_compilar = QPushButton("⚙ Recompilar")
        self.btn_compilar.setStyleSheet("background-color: #e8f5e9;")
        self.btn_compilar.clicked.connect(self.compilar)
        toolbar.addWidget(self.btn_compilar)

        self.btn_shell = QPushButton("shell")
        self.btn_shell.setStyleSheet("background-color: #e8f5e9;")
        self.btn_shell.clicked.connect(self.shell)
        toolbar.addWidget(self.btn_shell)

        self.btn_carpeta = QPushButton("📁 Carpeta")
        self.btn_carpeta.setStyleSheet(
            "background-color: #fff3e0;"
        )
        self.btn_carpeta.clicked.connect(self.abrir_carpeta_pagina)
        toolbar.addWidget(self.btn_carpeta)

        self.btn_borrar = QPushButton("Borrar")
        self.btn_borrar.setStyleSheet(
            "background-color: #fff3e0;"
        )
        self.btn_borrar.clicked.connect(self.borrar_pagina)
        toolbar.addWidget(self.btn_borrar)


        self.combo_css = QComboBox()
        self.combo_css.addItems(["styles/wiki1.css", "styles/wiki2.css"])
        self.combo_css.currentTextChanged.connect(self.aplicar_css_actual)
        toolbar.addWidget(self.combo_css)

    def ir_a_index(self):
        ruta_index = os.path.join(self.directorio_src, "index.wiki")
        ruta_html = os.path.join(self.directorio_build, "index.html")

        if os.path.exists(ruta_index):
            # Compilar siempre para asegurar que está actualizado
            convert_file(ruta_index, ruta_html, self.tabla_chars, self.directorio_src)
            self.visor.setUrl(QUrl.fromLocalFile(ruta_html))
            self.observar_archivo(ruta_index)
            self.seleccionar_item_en_lista(ruta_html)
        else:
            QMessageBox.warning(self, "Index no encontrado",
                                f"No existe index.wiki en:\n{self.directorio_src}")

    def filtrar_lista_wikis(self):
        texto = self.txt_filtro.text().lower().strip()

        self.lista_wikis.clear()

        wikis = listar_ficheros_wiki(self.directorio_src)

        for wiki in wikis:
            if texto in wiki.lower():   # LIKE '%texto%'
                self.lista_wikis.addItem(wiki)

    def mostrar_y_enfocar_busqueda(self):
        """Muestra la barra inferior, enfoca el texto y selecciona todo."""
        self.widget_barra_busqueda.show()
        self.txt_buscar_html.setFocus()
        self.txt_buscar_html.selectAll()

    def ocultar_barra_busqueda(self):
        """Oculta la barra de búsqueda inferior y limpia el texto."""
        self.widget_barra_busqueda.hide()
        # Limpiar resaltados de búsqueda en el visor enviando cadena vacía
        from PyQt5.QtWebEngineWidgets import QWebEnginePage
        self.visor.page().findText("")
        self.setFocus()

    def buscar_siguiente_html(self):
        """Busca la siguiente coincidencia hacia adelante."""
        texto = self.txt_buscar_html.text()
        if texto:
            from PyQt5.QtWebEngineWidgets import QWebEnginePage
            self.visor.page().findText(texto)

    def buscar_anterior_html(self):
        """Busca la coincidencia anterior hacia atrás."""
        texto = self.txt_buscar_html.text()
        if texto:
            from PyQt5.QtWebEngineWidgets import QWebEnginePage
            self.visor.page().findText(texto, QWebEnginePage.FindBackward)

    def _init_ui(self):
        """Inicializa el layout con barra lateral izquierda y visor central."""
        contenedor_principal = QWidget()
        self.setCentralWidget(contenedor_principal)

        layout_principal = QHBoxLayout(contenedor_principal)
        layout_principal.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)
        layout_principal.addWidget(splitter)

        # Panel Izquierdo: Lista de páginas .wiki
        panel_izquierdo = QWidget()
        layout_izquierdo = QVBoxLayout(panel_izquierdo)
        layout_izquierdo.setContentsMargins(8, 8, 8, 8)

        # Layout superior del panel izquierdo (Título + Botón Refrescar)
        layout_cabecera_lateral = QHBoxLayout()
        
        lbl_titulo = QLabel("Páginas Wiki")
        lbl_titulo.setStyleSheet("font-weight: bold;")
        layout_cabecera_lateral.addWidget(lbl_titulo)

        # Botón para ir directamente a index.wiki
        btn_index = QPushButton("🏠 Index")
        btn_index.setToolTip("Ir a index.wiki")
        btn_index.setFixedWidth(60)
        btn_index.clicked.connect(self.ir_a_index)
        layout_cabecera_lateral.addWidget(btn_index)


        # Botón de refresco pequeño para la barra lateral
        btn_refrescar_lista = QPushButton("🔄 Reload")
        btn_refrescar_lista.setToolTip("Refrescar lista de ficheros .wiki")
        btn_refrescar_lista.setFixedWidth(30)
        btn_refrescar_lista.clicked.connect(self.cargar_lista_wikis)
        layout_cabecera_lateral.addWidget(btn_refrescar_lista)

        layout_izquierdo.addLayout(layout_cabecera_lateral)

        self.lista_wikis = QListWidget()
        self.lista_wikis.itemClicked.connect(self.on_wiki_item_clicked)
        layout_izquierdo.addWidget(self.lista_wikis)

        self.txt_filtro = QLineEdit()
        self.txt_filtro.setPlaceholderText("Filtrar páginas...")
        self.txt_filtro.textChanged.connect(self.filtrar_lista_wikis)
        layout_izquierdo.addWidget(self.txt_filtro)


        panel_izquierdo.setMinimumWidth(220)
        splitter.addWidget(panel_izquierdo)

        # Panel Derecho: Contenedor que agrupa el Visor Web y la barra de búsqueda inferior
        panel_derecho = QWidget()
        layout_derecho = QVBoxLayout(panel_derecho)
        layout_derecho.setContentsMargins(0, 0, 0, 0)
        layout_derecho.setSpacing(0)

        # 1. El visor web
        self.visor = QWebEngineView()
        self.pagina_custom = PaginaWikiWeb(self, self.tabla_chars)
        self.visor.setPage(self.pagina_custom)
        layout_derecho.addWidget(self.visor)

        # 2. Barra de búsqueda inferior (oculta por defecto)
        self.widget_barra_busqueda = QWidget()
        self.widget_barra_busqueda.setFixedHeight(38)  # <--- FUERZA UNA ALTURA COMPACTA
        self.widget_barra_busqueda.setStyleSheet("""
            QWidget {
                background-color: #f1f3f4;
                border-top: 1px solid #dcdcdc;
                padding: 2px;
            }
        """)
        layout_barra = QHBoxLayout(self.widget_barra_busqueda)
        layout_barra.setContentsMargins(8, 2, 8, 2)  # Márgenes internos estrechos

        # Campo de texto de búsqueda
        self.txt_buscar_html = QLineEdit()
        self.txt_buscar_html.setPlaceholderText("Buscar en la página...")
        self.txt_buscar_html.setMaximumWidth(250)
        self.txt_buscar_html.setFixedHeight(24)  # <--- Altura fija para el input
        self.txt_buscar_html.returnPressed.connect(self.buscar_siguiente_html)
        layout_barra.addWidget(self.txt_buscar_html)

        # Botón Siguiente (▼)
        btn_sig = QPushButton("▼")
        btn_sig.setToolTip("Buscar siguiente")
        btn_sig.setFixedSize(26, 24)  # <--- Botón pequeño y cuadrado
        btn_sig.clicked.connect(self.buscar_siguiente_html)
        layout_barra.addWidget(btn_sig)

        # Botón Anterior (▲)
        btn_ant = QPushButton("▲")
        btn_ant.setToolTip("Buscar anterior")
        btn_ant.setFixedSize(26, 24)
        btn_ant.clicked.connect(self.buscar_anterior_html)
        layout_barra.addWidget(btn_ant)

        # Espaciador para empujar todo a la izquierda
        layout_barra.addStretch()

        # Botón Cerrar (✕)
        btn_cerrar = QPushButton("✕")
        btn_cerrar.setToolTip("Cerrar búsqueda")
        btn_cerrar.setFixedSize(24, 24)
        btn_cerrar.setStyleSheet("border: none; font-weight: bold; color: #5f6368;")
        btn_cerrar.clicked.connect(self.ocultar_barra_busqueda)
        layout_barra.addWidget(btn_cerrar)

        # Añadir la barra al layout inferior y ocultarla inicialmente
        layout_derecho.addWidget(self.widget_barra_busqueda)
        self.widget_barra_busqueda.hide()

        splitter.addWidget(panel_derecho)
        splitter.setSizes([250, 950])


    # ------------------------------------------------------------------
    # ACCIONES & COMPILACIÓN
    # ------------------------------------------------------------------
    def compilar(self):
        """Método de compilación sincrónica usando el archivo wiki actual."""
        if not self.archivo_wiki_actual:
            self.archivo_wiki_actual = self.obtener_wiki_actual()

        if not self.archivo_wiki_actual or not os.path.exists(
            self.archivo_wiki_actual
        ):
            print("[WARN] No hay un archivo .wiki seleccionado para compilar.")
            return

        ruta_wiki_abs = os.path.abspath(self.archivo_wiki_actual)
        ruta_html_abs = os.path.splitext(ruta_wiki_abs)[0] + ".html"

        print(f"[DEBUG] Compilando sincrónicamente: {ruta_wiki_abs}")
        if convert_file(ruta_wiki_abs, ruta_html_abs, self.tabla_chars, self.directorio_src):
            self.visor.reload()
            print("[DEBUG] Compilación finalizada con éxito.")
        else:
            print(f"[ERROR] Error al compilar {ruta_wiki_abs}")

    def borrar_pagina(self):

        ruta_wiki = self.obtener_wiki_actual()

        # Nombre de la página sin la extensión .wiki
        nombre_pagina = os.path.splitext(
            os.path.basename(ruta_wiki)
        )[0]

        print(f"Borrando la pagina activa {nombre_pagina} que viene de {ruta_wiki}\n")

        if os.path.isdir(nombre_pagina):
            QMessageBox.warning(
                self,
                "Aviso",
                f"No creo que sea buena idea borrar con directorio:\n{nombre_pagina}"
            )
            return
        else:
            respuesta = QMessageBox.question(
                self,
                "Página existente",
                f"La página '{nombre_pagina}' existe y tiene info.\n\n"
                f"¿Deseas borrar la nota correspondiente en:\n"
                f"{ruta_wiki}?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )

            if respuesta == QMessageBox.Yes:
                os.makedirs("./trash", exist_ok=True)

                # Los dos archivos que queremos mandar a la papelera
                archivos = [
                    ruta_wiki,
                    os.path.splitext(ruta_wiki)[0] + ".html"
                ]

                for ruta in archivos:

                    if not os.path.exists(ruta):
                        print(f"No existe: {ruta}")
                        continue

                    destino = os.path.join(
                        "./trash",
                        os.path.basename(ruta)
                    )

                    # Si ya existe en trash, lo eliminamos
                    if os.path.exists(destino):
                        os.remove(destino)

                    print(f"Moviendo: {ruta}")
                    print(f"       a: {destino}")

                    shutil.move(ruta, destino)


    def abrir_carpeta_pagina(self):
        """
        Crea y abre la carpeta asociada a la página wiki actual.

        Ejemplo:

            python.wiki
            python/

        Si la carpeta ya existe, simplemente la abre.
        """
        ruta_wiki = self.obtener_wiki_actual()

        if not ruta_wiki:
            QMessageBox.warning(
                self,
                "Aviso",
                "No se ha encontrado el fichero .wiki "
                "correspondiente a la página actual."
            )
            return

        ruta_wiki = os.path.abspath(ruta_wiki)

        if not os.path.isfile(ruta_wiki):
            QMessageBox.warning(
                self,
                "Aviso",
                f"No existe el fichero wiki:\n{ruta_wiki}"
            )
            return

        # Nombre de la página sin la extensión .wiki
        nombre_pagina = os.path.splitext(
            os.path.basename(ruta_wiki)
        )[0]

        # La carpeta se crea junto al fichero .wiki
        directorio_pagina = os.path.dirname(ruta_wiki)
        ruta_carpeta = os.path.join(
            directorio_pagina,
            nombre_pagina
        )

        try:
            os.makedirs(
                ruta_carpeta,
                exist_ok=True
            )
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Error",
                f"No se pudo crear la carpeta:\n\n"
                f"{ruta_carpeta}\n\n"
                f"{exc}"
            )
            return

        # Abrirla con el explorador de archivos
        if not QDesktopServices.openUrl(
            QUrl.fromLocalFile(ruta_carpeta)
        ):
            QMessageBox.warning(
                self,
                "Aviso",
                f"No se pudo abrir la carpeta:\n{ruta_carpeta}"
            )

    def shell(self):
        ruta_wiki = self.obtener_wiki_actual()

        if not ruta_wiki:
            QMessageBox.warning(
                self,
                "Aviso",
                "No se ha encontrado el fichero .wiki correspondiente al HTML"
                " actual.",
            )
            return

        self.archivo_wiki_actual = ruta_wiki
        self.registrar_watcher(ruta_wiki)

        terminal = os.environ.get("TERMINAL") or "gnome-terminal"

        try:
            subprocess.Popen([terminal, "--", "bash"])
        except Exception:
            QMessageBox.warning(
                self,
                "Aviso",
                "No se pudo abrir el terminal.",
            )


    # ----------------------------------------------------
    # GESTIÓN DE LISTA LATERAL Y NAVEGACIÓN
    # ----------------------------------------------------
    def cargar_lista_wikis(self):
        self.lista_wikis.clear()

        if not os.path.exists(self.directorio_src):
            print(f"[ERROR] El directorio '{self.directorio_src}' no existe.")
            return

        wikis = listar_ficheros_wiki(self.directorio_src)
        for wiki in wikis:
            self.lista_wikis.addItem(wiki)

    def on_wiki_item_clicked(self, item):
            rel_wiki_path = item.text()
            ruta_wiki_abs = os.path.abspath(
                os.path.join(self.directorio_src, rel_wiki_path)
            )
            ruta_html_abs = os.path.splitext(ruta_wiki_abs)[0] + ".html"

            # Forzamos la recompilación siempre, exista o no el HTML previo
            if not convert_file(ruta_wiki_abs, ruta_html_abs, self.tabla_chars):
                print(f"[ERROR] Error al compilar {ruta_wiki_abs}")
                return

            if os.path.exists(ruta_html_abs):
                self.visor.setUrl(QUrl.fromLocalFile(ruta_html_abs))
                self.observar_archivo(ruta_wiki_abs)


    def seleccionar_item_en_lista(self, ruta_html_abs):
        ruta_wiki_rel = os.path.relpath(
            os.path.splitext(ruta_html_abs)[0] + ".wiki", self.directorio_src
        )
        items = self.lista_wikis.findItems(ruta_wiki_rel, Qt.MatchExactly)
        if items:
            self.lista_wikis.setCurrentItem(items[0])

    """
    def cargar_url(self):
        texto = self.barra_url.text().strip()
        if not texto:
            return

        if not texto.startswith(("http://", "https://", "file://")):
            texto = "file://" + texto

        self.visor.setUrl(QUrl(texto))


    def actualizar_url(self, url):
        self.barra_url.setText(url.toString())

    """

    def abrir_archivo(self):
        archivo, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo HTML",
            self.directorio_build,
            "Archivos HTML (*.html *.htm)",
        )
        if archivo:
            self.visor.setUrl(QUrl.fromLocalFile(archivo))


    def editar_fuente_wiki(self):
        ruta_wiki = self.obtener_wiki_actual()
        if not ruta_wiki:
            QMessageBox.warning(
                self,
                "Aviso",
                "No se ha encontrado el fichero .wiki correspondiente al HTML"
                " actual.",
            )
            return
        self.abrir_editor_y_vigilar(ruta_wiki)


    def obtener_wiki_actual(self):
        ruta_html = self.visor.url().toLocalFile()
        if not ruta_html:
            return None

        return html_to_wiki(
            ruta_html,
            self.directorio_build,
            self.directorio_src,
        )


    def obtener_html_desde_wiki(self, ruta_wiki):
        return wiki_to_html(
            ruta_wiki,
            self.directorio_src,
            self.directorio_build,
        )


    def abrir_editor_y_vigilar(self, ruta_wiki):
        self.archivo_wiki_actual = os.path.abspath(ruta_wiki)
        self.registrar_watcher(self.archivo_wiki_actual)

        editor = os.environ.get("EDITOR") or "xed"

        try:
            subprocess.Popen([editor, self.archivo_wiki_actual])
        except Exception:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.archivo_wiki_actual))


    def registrar_watcher(self, path):
        path = os.path.abspath(path)
        if self.watcher.files():
            self.watcher.removePaths(self.watcher.files())
        if os.path.exists(path):
            self.watcher.addPath(path)


    # ----------------------------------------------------
    # CARGA Y VIGILANCIA DE ARCHIVOS
    # ----------------------------------------------------
    def cargar_index_old(self):
        
        index_html = os.path.join(self.directorio_build, "index.html")
        index_wiki = os.path.join(self.directorio_src, "index.wiki")

        if os.path.exists(index_html):
            self.visor.setUrl(QUrl.fromLocalFile(index_html))
            if os.path.exists(index_wiki):
                self.observar_archivo(index_wiki)
        elif os.path.exists(index_wiki):
            if convert_file(ruta_wiki_abs, ruta_html_abs, self.tabla_chars, self.directorio_src):
                self.visor.setUrl(QUrl.fromLocalFile(index_html))
                self.observar_archivo(index_wiki)
        else:
            self.gestionar_pagina_inexistente(index_html)

    def cargar_index(self):
          index_html = os.path.join(self.directorio_build, "index.html")
          index_wiki = os.path.join(self.directorio_src, "index.wiki")

          if os.path.exists(index_html):
            self.visor.setUrl(QUrl.fromLocalFile(index_html))
            if os.path.exists(index_wiki):
              self.observar_archivo(index_wiki)
          elif os.path.exists(index_wiki):
            # Aseguramos que las variables apunten a los paths correctos de build y src
            ruta_wiki_abs = index_wiki
            ruta_html_abs = index_html

            # Llamamos a convert_file pasando el directorio src para comprobar enlaces correctamente
            if convert_file(ruta_wiki_abs, ruta_html_abs, self.tabla_chars, self.directorio_src):
              self.visor.setUrl(QUrl.fromLocalFile(index_html))
              self.observar_archivo(index_wiki)
            else:
              print(f"[ERROR] No se pudo compilar el index: {index_wiki}")
          else:
            self.gestionar_pagina_inexistente(index_html)

    def observar_archivo(self, ruta_wiki):
        if (
            self.archivo_wiki_actual
            and self.archivo_wiki_actual in self.watcher.files()
        ):
            self.watcher.removePath(self.archivo_wiki_actual)
        self.archivo_wiki_actual = ruta_wiki
        if os.path.exists(ruta_wiki):
            self.watcher.addPath(ruta_wiki)


    def al_guardar_wiki(self, path):
        self.timer_build.start(300)


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


    def gestionar_pagina_inexistente(self, ruta_html_objetivo):
        ruta_wiki = html_to_wiki(
            ruta_html_objetivo,
            self.directorio_build,
            self.directorio_src,
        )

        if not ruta_wiki:
            return

        nombre_pagina = os.path.basename(
            os.path.splitext(ruta_html_objetivo)[0]
        )

        respuesta = QMessageBox.question(
            self,
            "Página inexistente",
            f"La página '{nombre_pagina}' no existe todavía.\n\n"
            f"¿Deseas crear la nota correspondiente en:\n"
            f"{ruta_wiki}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if respuesta != QMessageBox.Yes:
            return

        os.makedirs(os.path.dirname(ruta_wiki), exist_ok=True)

        if not os.path.exists(ruta_wiki):
            with open(ruta_wiki, "w", encoding="utf-8") as f:
                f.write(
                    f"= {nombre_pagina.capitalize()} =\n\n"
                    "Escribe aquí tu contenido..."
                )

        self.archivo_wiki_actual = ruta_wiki
        self.compilar()
        self.abrir_editor_y_vigilar(ruta_wiki)


