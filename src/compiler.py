import os
import re
import subprocess
import tempfile
import unicodedata
import argparse
from pathlib import Path
import ziamath as zm

TRANSLITERACION = str.maketrans({
    "Æ": "AE",
    "æ": "ae",
    "Œ": "OE",
    "œ": "oe",
    "ß": "ss",
    "ẞ": "SS",
    "Ø": "O",
    "ø": "o",
    "Ð": "D",
    "ð": "d",
    "Đ": "D",
    "đ": "d",
    "Ł": "L",
    "ł": "l",
    "Þ": "Th",
    "þ": "th",
})


def normalizar_nombre(nombre):
    """
    Convierte un nombre de página en un nombre ASCII normalizado.

    Ejemplo:
        'Esto fué Un Enlace' -> 'esto_fue_un_enlace'
    """
    nombre = nombre.translate(TRANSLITERACION)
    nombre = unicodedata.normalize("NFKD", nombre)
    nombre = "".join(
        c for c in nombre
        if not unicodedata.combining(c)
    )
    nombre = nombre.lower()
    nombre = nombre.replace(" ", "_")
    nombre = nombre.encode("ascii", "ignore").decode("ascii")
    return nombre

# =======================

import os
import re
from pathlib import Path
import html

def resolver_ruta(ruta, directorio_trabajo):
    """
    Resuelve una ruta física desde el directorio de trabajo
    y devuelve (ruta_absoluta, ruta_html).
    """
    ruta_path = Path(ruta)
    if not ruta_path.is_absolute():
        ruta_path = directorio_trabajo / ruta_path

    ruta_absoluta = ruta_path.resolve()
    ruta_html = os.path.relpath(
        ruta_absoluta, directorio_trabajo
    ).replace("\\", "/")

    return ruta_absoluta, ruta_html


def es_enlace_imagen(partes, directorio_trabajo):
    """
    Determina si un enlace debe ser tratado como imagen basándose en:
    - Si tiene el prefijo 'image:'
    - Si su nombre tiene una extensión de imagen conocida
    - O si los parámetros posteriores contienen dimensiones, alineación o miniaturas.
    """
    ruta = partes[0]
    ruta_lower = ruta.lower()
    
    if ruta_lower.startswith("image:"):
        return True
        
    extensiones_imagen = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp")
    if ruta_lower.endswith(extensiones_imagen):
        return True
        
    # Si hay partes adicionales que parecen parámetros de imagen
    if len(partes) > 1:
        for parte in partes[1:]:
            p_lower = parte.lower()
            if (re.fullmatch(r"(\d+(?:\.\d+)?)(?:px)?x(\d+(?:\.\d+)?)(?:px)?", p_lower) or
                re.fullmatch(r"\d+(?:\.\d+)?(?:px)?", p_lower) or
                p_lower in ("right", "izquierda", "left", "center", "centrado", "thumb", "thumbnail", "miniaturadeimagen")):
                return True
                
    # Comprobación física en disco
    fichero_absoluto, _ = resolver_ruta(ruta, directorio_trabajo)
    if fichero_absoluto.is_file() and fichero_absoluto.suffix.lower() in extensiones_imagen:
        return True
        
    return False


def procesar_enlace_fichero(contenido, directorio_trabajo):
    """
    Procesa enlaces del tipo [[Fichero:...]] y devuelve el HTML correspondiente.
    """
    print(f"*** Detectado enlace a fichero: {contenido}")
    contenido_fichero = contenido[len("fichero:"):].strip()

    if "|" in contenido_fichero:
        ruta, texto_enlace = contenido_fichero.split("|", 1)
        ruta = ruta.strip()
        texto_enlace = texto_enlace.strip()
    else:
        ruta = contenido_fichero
        texto_enlace = os.path.basename(ruta)

    fichero_absoluto, ruta_html = resolver_ruta(ruta, directorio_trabajo)

    if not fichero_absoluto.is_file():
        print(f"[WARN] No se encuentra el fichero: {fichero_absoluto}")

    href_html = html.escape(ruta_html, quote=True)
    texto_html = html.escape(texto_enlace)

    return f'<a href="{href_html}" class="wiki-file-link">{texto_html}</a>'


def procesar_enlace_pagina(contenido, directorio_src):
    """
    Procesa enlaces internos a páginas wiki normales.
    """
    if "|" in contenido:
        destino, texto_enlace = contenido.split("|", 1)
        destino = destino.strip()
        texto_enlace = texto_enlace.strip()
    else:
        destino = contenido
        texto_enlace = contenido

    destino_normalizado = normalizar_nombre(destino)
    ruta_wiki_destino = directorio_src / f"{destino_normalizado}.wiki"
    existe_wiki = ruta_wiki_destino.is_file()

    clase_css = "wiki-link-existing" if existe_wiki else "wiki-link-missing"

    print(
        f"[DEBUG LINK] Destino original: '{destino}' -> "
        f"'{destino_normalizado}.wiki' | ¿Existe?: {existe_wiki} | Clase: {clase_css}"
    )

    href_html = html.escape(f"{destino_normalizado}.html", quote=True)
    texto_html = html.escape(texto_enlace)

    return f'<a href="{href_html}" class="{clase_css}">{texto_html}</a>'


def procesar_enlace_imagen(contenido, directorio_trabajo):
    """
    Procesa imágenes con sintaxis tipo MediaWiki.

    Ejemplos:
        [[Image:miwiki/prueba.png]]
        [[File:miwiki/prueba.png|300px]]
        [[File:miwiki/prueba.png|thumb|300px|right|Logotipo oficial]]
        [[File:miwiki/prueba.png|frameless|200px|center]]
        [[File:miwiki/prueba.png|frame|left|Logotipo oficial]]
        [[File:miwiki/prueba.png|300x200px|alt=Descripción]]

    Devuelve HTML.
    """

    print(f"*** Detectado enlace a imagen: {contenido}")

    partes = [p.strip() for p in contenido.split("|")]
    ruta = partes[0].strip()

    # Eliminar prefijos reconocidos por MediaWiki.
    prefijos = (
        "image:", "file:", "archivo:", "fichero:"
    )

    for prefijo in prefijos:
        if ruta.lower().startswith(prefijo):
            ruta = ruta[len(prefijo):].strip()
            break

    fichero_absoluto, ruta_html = resolver_ruta(
        ruta, directorio_trabajo
    )

    if not fichero_absoluto.is_file():
        print(f"[WARN] No se encuentra la imagen: {fichero_absoluto}")

    # Opciones por defecto.
    ancho = None
    alto = None
    alineacion = None
    formato = "normal"
    borde = False
    upright = 1.0
    alt_texto = ""
    pie_foto = None
    enlace = None
    opciones_desconocidas = []

    opciones_formato = {
        "thumb": "thumb",
        "thumbnail": "thumb",
        "miniaturadeimagen": "thumb",
        "frame": "frame",
        "framed": "frame",
        "frameless": "frameless",
    }

    alineaciones = {
        "left": "left",
        "right": "right",
        "center": "center",
        "centre": "center",
        "none": "none",
    }

    for parte in partes[1:]:
        p = parte.strip()
        pl = p.lower()

        if not p:
            continue

        # Formato de presentación.
        if pl in opciones_formato:
            formato = opciones_formato[pl]
            continue

        # Borde.
        if pl == "border":
            borde = True
            continue

        # Alineación.
        if pl in alineaciones:
            alineacion = alineaciones[pl]
            continue

        # Compatibilidad adicional con el código anterior.
        if pl in ("izquierda", "centrado", "derecha"):
            alineacion = {
                "izquierda": "left",
                "centrado": "center",
                "derecha": "right",
            }[pl]
            continue

        # Escala de miniatura.
        match_upright = re.fullmatch(
            r"upright(?:\s*=\s*(\d+(?:\.\d+)?))?",
            pl
        )
        if match_upright:
            upright = float(match_upright.group(1) or 0.75)
            formato = "thumb" if formato == "normal" else formato
            continue

        # Texto alternativo.
        if pl.startswith("alt="):
            alt_texto = p[4:].strip()
            continue

        # Enlace personalizado.
        if pl.startswith("link="):
            enlace = p[5:].strip()
            continue

        # Dimensiones: 300x200px.
        match_wh = re.fullmatch(
            r"(\d+(?:\.\d+)?)(?:px)?x"
            r"(\d+(?:\.\d+)?)(?:px)?",
            pl
        )
        if match_wh:
            ancho = float(match_wh.group(1))
            alto = float(match_wh.group(2))
            continue

        # Ancho: 300px o 300.
        match_ancho = re.fullmatch(
            r"(\d+(?:\.\d+)?)(?:px)?",
            pl
        )
        if match_ancho:
            if ancho is None:
                ancho = float(match_ancho.group(1))
            elif alto is None:
                alto = float(match_ancho.group(1))
            continue

        # La primera opción que no se reconozca puede ser
        # el pie de foto; las siguientes se conservan aparte.
        if pie_foto is None:
            pie_foto = p
        else:
            opciones_desconocidas.append(p)

    # En MediaWiki, frame conserva el tamaño original.
    # No se aplican las dimensiones indicadas en ese caso.
    if formato == "frame":
        ancho = None
        alto = None

    # upright escala el ancho de una miniatura.
    if formato == "thumb" and upright != 1.0 and ancho is None:
        ancho = 220 * upright

    estilos = [
        "max-width: 100%",
        "height: auto",
        "box-sizing: border-box",
    ]

    if ancho is not None and alto is not None:
        # Mantener la proporción como hace MediaWiki:
        # el tamaño solicitado es un límite, no una deformación.
        estilos.extend([
            f"width: {ancho:g}px",
            f"max-height: {alto:g}px",
            "object-fit: contain",
        ])
    elif ancho is not None:
        estilos.append(f"width: {ancho:g}px")
    elif alto is not None:
        estilos.append(f"max-height: {alto:g}px")

    if borde:
        estilos.append("border: 1px solid #aaa")

    # Alineación y presentación.
    if formato in ("thumb", "frame"):
        estilos.extend([
            "display: block",
            "padding: 3px",
            "border: 1px solid #ccc",
            "background: #f8f8f8",
        ])

        if alineacion == "left":
            estilos.extend([
                "float: left",
                "margin: 0.5em 1.4em 1.3em 0",
            ])
        elif alineacion == "right" or alineacion is None:
            estilos.extend([
                "float: right",
                "margin: 0.5em 0 1.3em 1.4em",
            ])
        else:
            estilos.extend([
                "margin: 1em auto",
                "clear: both",
            ])
    elif alineacion == "left":
        estilos.extend([
            "float: left",
            "margin: 0 1em 1em 0",
        ])
    elif alineacion == "right":
        estilos.extend([
            "float: right",
            "margin: 0 0 1em 1em",
        ])
    elif alineacion == "center":
        estilos.extend([
            "display: block",
            "margin: 1em auto",
            "clear: both",
        ])
    elif alineacion == "none":
        estilos.extend([
            "display: inline-block",
            "vertical-align: middle",
        ])
    else:
        estilos.extend([
            "display: inline-block",
            "vertical-align: middle",
        ])

    src_html = html.escape(ruta_html, quote=True)
    alt_html = html.escape(
        alt_texto or (pie_foto if pie_foto else ruta),
        quote=True
    )
    estilo_html = html.escape("; ".join(estilos), quote=True)

    # Construcción de la imagen.
    img_html = (
        f'<img src="{src_html}" '
        f'alt="{alt_html}" '
        f'class="wiki-image" '
        f'style="{estilo_html}" />'
    )

    # link= permite cambiar el destino del clic.
    if enlace is not None:
        if enlace == "":
            # MediaWiki: link= desactiva el enlace.
            pass
        else:
            href_html = html.escape(enlace, quote=True)
            img_html = (
                f'<a href="{href_html}">{img_html}</a>'
            )

    # Miniatura con pie de foto.
    if formato == "thumb":
        caption_html = (
            html.escape(pie_foto)
            if pie_foto is not None
            else ""
        )

        return (
            '<figure class="wiki-image-thumb" '
            'style="display: table; max-width: 100%; '
            'padding: 3px; border: 1px solid #ccc; '
            'background: #f8f8f8;">'
            f'{img_html}'
            '<figcaption style="display: table-caption; '
            'caption-side: bottom; text-align: left; '
            'font-size: 0.9em; padding: 3px;">'
            f'{caption_html}'
            '</figcaption>'
            '</figure>'
        )

    # Imagen enmarcada, sin pie de foto editable.
    if formato == "frame":
        return (
            '<figure class="wiki-image-frame" '
            'style="display: inline-block; padding: 3px; '
            'border: 1px solid #ccc; background: #f8f8f8; '
            'margin: 0.5em;">'
            f'{img_html}'
            '</figure>'
        )

    return img_html


def normalizar_enlaces_mediawiki(texto, directorio_src=None):
    """
    Función principal que orquesta la conversión de enlaces MediaWiki en HTML.
    Los 3 elementos basicos son enlace, imagen y fichero.
    Los demas se procesan antes para generar imagenes
    La sintaxis de las imagenes es asi:
    [[image:miwiki/prueba.png|thumb|300px|right|Logotipo oficial]]
    """
    directorio_trabajo = Path.cwd()

    if directorio_src is None:
        directorio_src = directorio_trabajo
    else:
        directorio_src = Path(directorio_src)
        if not directorio_src.is_absolute():
            directorio_src = directorio_trabajo / directorio_src
        directorio_src = directorio_src.resolve()

    patron = re.compile(r"\[\[([^\[\]\n]+?)\]\]")

    def reemplazar(match):
        contenido = match.group(1).strip()
        contenido_lower = contenido.lower()
        partes = [p.strip() for p in contenido.split("|")]

        if contenido_lower.startswith("fichero:"):
            return procesar_enlace_fichero(
                contenido, directorio_trabajo
            )
        elif es_enlace_imagen(partes, directorio_trabajo):
            return procesar_enlace_imagen(
                contenido, directorio_trabajo
            )
        else:
            return procesar_enlace_pagina(
                contenido, directorio_src
            )


    return patron.sub(reemplazar, texto)

# ========================

def sustituir_linea_pre(linea: str, tabla: dict) -> str:
    """
    Sustituye palabras dentro de una línea PRE, pero conserva
    exactamente todos los espacios y tabuladores originales.
    """

    def reemplazar(match):
        palabra = match.group(0)

        if palabra in tabla:
            codigo = tabla[palabra]
            print(f"[PRE] Sustituyendo '{palabra}' por código hex '{codigo}'")
            return "<span>&#{};</span>".format(codigo)

        return palabra

    # Busca palabras sin modificar los espacios que las rodean.
    return re.sub(r"\S+", reemplazar, linea)


def sustituir_linea(linea: str, tabla: dict) -> str:
  palabras = linea.split()
  if not palabras:
    return linea

  palabras_sustituidas = []
  for palabra in palabras:
      if palabra in tabla:
        codigo = tabla[palabra]
        print(f"buscamos el codigo de {palabra} y me sale {codigo}")
        print(f"Sustituyendo '{palabra}' por código hex '{codigo}'")
        palabras_sustituidas.append("<span>&#"+str(codigo)+";</span>")
      else:
        palabras_sustituidas.append(palabra)

  print(f"Volviendo con {palabras_sustituidas}")
  return " ".join(palabras_sustituidas)


def generar_svg_con_ecuacion(formula_latex, path_absoluto):
    try:
        ecuacion_vectorial = zm.Math.fromlatex(formula_latex, size=18)
        codigo_svg = ecuacion_vectorial.svg()
        
        with open(path_absoluto, "w", encoding="utf-8") as f:
            f.write(codigo_svg)
            
        print(f"¡Éxito! Archivo '{path_absoluto}' generado correctamente en directorio {Path.cwd()}")
    except Exception as e:
        print(f"[ERROR] No se pudo generar el SVG para la fórmula: {e}")


import os
import re
import shutil
import subprocess


def generar_svg_con_grafo(
    codigo,
    fichero_absoluto,
    directorio_iconos
):
    """
    Genera un SVG mediante Graphviz.

    Las referencias image="xxx.svg" se resuelven
    contra directorio_iconos.

    Si falta un SVG, se crea uno temporal.
    """

    print()
    print("#" * 80)
    print("*** generar_svg_con_grafo()")
    print("#" * 80)

    print(f"*** fichero salida: {fichero_absoluto}")
    print(f"*** directorio iconos: {directorio_iconos}")

    # --------------------------------------------------------------
    # Preparar DOT
    # --------------------------------------------------------------

    codigo_preparado = preparar_dot_con_iconos(
        codigo,
        directorio_iconos
    )

    print()
    print("*** DOT después de resolver iconos:")
    print("-" * 40)
    print(codigo_preparado)
    print("-" * 40)

    # --------------------------------------------------------------
    # Fichero DOT temporal
    # --------------------------------------------------------------

    fichero_dot = fichero_absoluto + ".dot"

    with open(
        fichero_dot,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(codigo_preparado)

    print(f"*** DOT escrito: {fichero_dot}")

    # --------------------------------------------------------------
    # Buscar dot
    # --------------------------------------------------------------

    ejecutable_dot = shutil.which("dot")

    print(f"*** Ejecutable dot: {ejecutable_dot}")

    if ejecutable_dot is None:
        raise RuntimeError(
            "No se encuentra 'dot' en PATH"
        )

    # --------------------------------------------------------------
    # Ejecutar Graphviz
    # --------------------------------------------------------------

    comando = [
        ejecutable_dot,
        "-Tsvg",
        fichero_dot,
        "-o",
        fichero_absoluto
    ]

    print("*** Ejecutando:")
    print(" ".join(comando))

    proceso = subprocess.run(
        comando,
        capture_output=True,
        text=True
    )

    print(f"*** Return code: {proceso.returncode}")

    if proceso.stdout:
        print("*** stdout:")
        print(proceso.stdout)

    if proceso.stderr:
        print("*** stderr:")
        print(proceso.stderr)

    if proceso.returncode != 0:
        raise RuntimeError(
            f"Graphviz terminó con código "
            f"{proceso.returncode}"
        )

    if not os.path.exists(fichero_absoluto):
        raise RuntimeError(
            "Graphviz terminó correctamente "
            "pero no creó el SVG"
        )

    print(
        f"*** SVG generado: "
        f"{fichero_absoluto}"
    )

    print(
        f"*** Tamaño: "
        f"{os.path.getsize(fichero_absoluto)} bytes"
    )


from graphviz import Source

def generar_svg_con_grafo_dot(dot, fichero_absoluto):
    print(f"DOT recibido:\n{dot}")

    grafo = Source(dot, format="svg")

    # Graphviz añade ".svg" automáticamente
    salida = fichero_absoluto[:-4] if fichero_absoluto.endswith(".svg") else fichero_absoluto

    grafo.render(
        filename=salida,
        cleanup=True
    )


import os
import re
import traceback

from diagrams import Diagram


import os
import re
import shutil
import subprocess


def generar_svg_con_d2(codigo, fichero_absoluto, fichero_d2):
    """
    Genera un SVG a partir de código D2 utilizando el ejecutable
    'd2' instalado en el sistema.

    codigo:
        Texto fuente D2.

    fichero_absoluto:
        Ruta absoluta del SVG de salida.

    fichero_d2:
        Ruta del fichero .d2 temporal/de depuración.
    """

    print()
    print("*** generar_svg_con_d2()")
    print(f"*** fichero_d2: {fichero_d2}")
    print(f"*** fichero_svg: {fichero_absoluto}")

    # ------------------------------------------------------------------
    # Comprobar que d2 existe en PATH
    # ------------------------------------------------------------------

    ejecutable_d2 = shutil.which("d2")

    print(f"*** Ejecutable d2 encontrado: {ejecutable_d2}")

    if ejecutable_d2 is None:
        raise RuntimeError(
            "No se encuentra el ejecutable 'd2' en PATH. "
            "Comprueba que D2 está instalado."
        )

    # ------------------------------------------------------------------
    # Crear directorio de salida
    # ------------------------------------------------------------------

    directorio_svg = os.path.dirname(fichero_absoluto)

    if directorio_svg:
        os.makedirs(directorio_svg, exist_ok=True)

    # ------------------------------------------------------------------
    # Escribir el fuente D2
    # ------------------------------------------------------------------

    print("*** Escribiendo fichero D2")

    with open(fichero_d2, "w", encoding="utf-8") as f:
        f.write(codigo)
        f.write("\n")

    print(f"*** Fichero D2 escrito: {fichero_d2}")

    # ------------------------------------------------------------------
    # Ejecutar D2
    # ------------------------------------------------------------------

    comando = [
        ejecutable_d2,
        fichero_d2,
        fichero_absoluto,
    ]

    print("*** Ejecutando:")
    print(" ".join(comando))

    proceso = subprocess.run(
        comando,
        capture_output=True,
        text=True
    )

    print(f"*** Return code: {proceso.returncode}")

    if proceso.stdout:
        print("*** stdout:")
        print("-" * 40)
        print(proceso.stdout)
        print("-" * 40)

    if proceso.stderr:
        print("*** stderr:")
        print("-" * 40)
        print(proceso.stderr)
        print("-" * 40)

    # ------------------------------------------------------------------
    # Comprobar resultado
    # ------------------------------------------------------------------

    if proceso.returncode != 0:
        raise RuntimeError(
            f"D2 terminó con código {proceso.returncode}"
        )

    if not os.path.exists(fichero_absoluto):
        raise RuntimeError(
            f"D2 terminó correctamente pero no creó el SVG: "
            f"{fichero_absoluto}"
        )

    tamaño = os.path.getsize(fichero_absoluto)

    print(f"*** SVG generado correctamente")
    print(f"*** fichero: {fichero_absoluto}")
    print(f"*** tamaño: {tamaño} bytes")

import os
import html


def crear_svg_temporal(
    fichero_svg,
    texto,
    ancho=180,
    alto=80
):
    """
    Crea un SVG provisional sencillo cuando no existe
    el icono solicitado.

    El SVG contiene una caja con el texto indicado.
    """

    print()
    print("*** crear_svg_temporal()")
    print(f"*** fichero: {fichero_svg}")
    print(f"*** texto: {texto}")

    directorio = os.path.dirname(fichero_svg)

    if directorio:
        os.makedirs(directorio, exist_ok=True)

    texto_svg = html.escape(str(texto))

    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     width="{ancho}"
     height="{alto}"
     viewBox="0 0 {ancho} {alto}">

    <rect
        x="2"
        y="2"
        width="{ancho - 4}"
        height="{alto - 4}"
        rx="8"
        ry="8"
        fill="#eeeeee"
        stroke="#555555"
        stroke-width="2"
    />

    <text
        x="{ancho / 2}"
        y="{alto / 2}"
        text-anchor="middle"
        dominant-baseline="middle"
        font-family="Arial, sans-serif"
        font-size="18"
        fill="#222222"
    >{texto_svg}</text>

</svg>
'''

    with open(fichero_svg, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"*** SVG temporal creado: {fichero_svg}")


def preparar_dot_con_iconos(
    codigo,
    directorio_iconos
):
    """
    Resuelve las referencias image="xxx.svg" del DOT.

    Si falta un icono, crea un SVG temporal.
    """

    patron = r'image\s*=\s*"([^"]+)"'

    def reemplazar(match):

        nombre_icono = match.group(1).strip()

        print()
        print("*** Procesando referencia a icono")
        print(f"*** image original: {nombre_icono}")

        ruta_icono = resolver_icono(
            nombre_icono,
            directorio_iconos,
            os.path.splitext(
                os.path.basename(nombre_icono)
            )[0].upper()
        )

        print(f"*** image sustituido por: {ruta_icono}")

        return f'image="{ruta_icono}"'

    return re.sub(
        patron,
        reemplazar,
        codigo
    )

def resolver_icono(
    nombre_icono,
    directorio_iconos,
    texto_temporal
):
    """
    Busca un icono SVG.

    Si no existe, crea un SVG temporal.
    Devuelve la ruta absoluta al SVG.
    """

    nombre_icono = os.path.basename(nombre_icono)

    fichero_svg = os.path.abspath(
        os.path.join(
            directorio_iconos,
            nombre_icono
        )
    )

    print()
    print("*** resolver_icono()")
    print(f"*** icono solicitado: {nombre_icono}")
    print(f"*** ruta buscada: {fichero_svg}")

    if os.path.exists(fichero_svg):
        print("*** Icono encontrado")

    else:
        print("*** Icono NO encontrado")
        print("*** Creando SVG temporal")

        crear_svg_temporal(
            fichero_svg,
            texto_temporal
        )

    return fichero_svg

def procesar_d2(texto, path_salida):
    """
    Busca bloques:

        [[D2=nombre]]
        ... código D2 ...
        [[/D2]]

    Genera:

        path_salida/nombre.svg

    y sustituye el bloque por:

        [[Image:nombre.svg]]
    """

    print()
    print("#" * 80)
    print("*** procesar_d2()")
    print("#" * 80)

    print(f"*** path_salida: {path_salida}")
    print(f"*** path_salida absoluto: {os.path.abspath(path_salida)}")
    print(f"*** longitud texto: {len(texto)}")

    patron = r'\[\[D2=([^\]]+)\]\](.*?)\[\[/D2\]\]'

    matches = list(re.finditer(
        patron,
        texto,
        flags=re.DOTALL
    ))

    print(f"*** Bloques D2 encontrados: {len(matches)}")

    def reemplazar(match):

        print()
        print("-" * 80)
        print("*** Procesando un bloque D2")
        print("-" * 80)

        filename = match.group(1).strip()
        codigo = match.group(2).strip()

        print(f"*** filename original: [{filename}]")
        print(f"*** longitud código: {len(codigo)}")

        print("*** Código D2:")
        print("-" * 40)
        print(codigo)
        print("-" * 40)

        # --------------------------------------------------------------
        # Evitamos que el nombre pueda contener rutas
        # --------------------------------------------------------------

        filename = os.path.basename(filename)

        print(f"*** filename normalizado: [{filename}]")

        # --------------------------------------------------------------
        # Ficheros de salida
        # --------------------------------------------------------------

        fichero_absoluto = os.path.abspath(
            os.path.join(
                path_salida,
                filename + ".svg"
            )
        )

        fichero_d2 = os.path.abspath(
            os.path.join(
                path_salida,
                filename + ".d2"
            )
        )

        fichero_salida = filename + ".svg"

        print(f"*** path_salida: {path_salida}")
        print(f"*** fichero_d2: {fichero_d2}")
        print(f"*** fichero_absoluto: {fichero_absoluto}")
        print(f"*** fichero_salida para Image: {fichero_salida}")

        # --------------------------------------------------------------
        # Generar SVG con D2
        # --------------------------------------------------------------

        generar_svg_con_d2(
            codigo,
            fichero_absoluto,
            fichero_d2
        )

        # --------------------------------------------------------------
        # Sustituir bloque
        # --------------------------------------------------------------

        resultado = f"[[Image:{fichero_salida} | 200px]]" # parece que 200px es el ancho pero algo hay que poner

        print(f"*** Sustituyendo bloque por: {resultado}")

        return resultado

    resultado = re.sub(
        patron,
        reemplazar,
        texto,
        flags=re.DOTALL
    )

    print()
    print("*** procesar_d2() terminado")
    print(f"*** Longitud resultado: {len(resultado)}")
    print("#" * 80)
    print()

    return resultado

def procesar_graphs(texto, path_salida):

    print()
    print("#" * 80)
    print("*** procesar_graphs()")
    print("#" * 80)

    print(f"*** path_salida: {path_salida}")

    patron = (
        r'\[\[Graph=([^\]]+)\]\]'
        r'(.*?)'
        r'\[\[/Graph\]\]'
    )

    matches = list(
        re.finditer(
            patron,
            texto,
            flags=re.DOTALL
        )
    )

    print(
        f"*** Bloques Graph encontrados: "
        f"{len(matches)}"
    )

    # Directorio de iconos
    directorio_iconos = os.path.abspath(
        os.path.join(
            path_salida,
            "icons"
        )
    )

    print(
        f"*** Directorio iconos: "
        f"{directorio_iconos}"
    )

    # Crear directorio si no existe
    os.makedirs(
        directorio_iconos,
        exist_ok=True
    )

    def reemplazar(match):

        print()
        print("-" * 80)
        print("*** Procesando bloque Graph")
        print("-" * 80)

        filename = match.group(1).strip()
        codigo = match.group(2).strip()

        filename = os.path.basename(
            filename
        )

        print(f"*** filename: {filename}")

        fichero_absoluto = os.path.abspath(
            os.path.join(
                path_salida,
                filename + ".svg"
            )
        )

        fichero_salida = filename + ".svg"

        print(
            f"*** fichero SVG: "
            f"{fichero_absoluto}"
        )

        generar_svg_con_grafo(
            codigo,
            fichero_absoluto,
            directorio_iconos
        )

        resultado = (
            f"[[Image:{fichero_salida}|200px]]"
        )

        print(
            f"*** Sustitución: {resultado}"
        )

        return resultado

    resultado = re.sub(
        patron,
        reemplazar,
        texto,
        flags=re.DOTALL
    )

    print("*** procesar_graphs() terminado")

    return resultado

def procesar_graphs_old(texto, path_salida):
    patron = r'\[\[Graph=([^\]]+)\]\](.*?)\[\[/Graph\]\]'
    print(f"*** Encontrado patron de grafo procesando {texto} sobre {path_salida}")

    def reemplazar(match):
        filename = match.group(1).strip()
        dot = match.group(2).strip()

        fichero_absoluto = path_salida + "/" + filename + ".svg"
        if not fichero_absoluto.startswith("/"):
            fichero_absoluto = "/" + fichero_absoluto

        fichero_salida = filename + ".svg"

        print(f"Generando grafo SVG en {fichero_absoluto}")

        generar_svg_con_grafo(dot, fichero_absoluto)

        return f"[[Image:{fichero_salida}]]"

    return re.sub(patron, reemplazar, texto, flags=re.DOTALL)



import hashlib
import os
import re
import xml.etree.ElementTree as ET

def obtener_dimensiones_svg(fichero_path):
    """Lee el viewBox o ancho/alto de un SVG existente para deducir su aspecto original."""
    try:
        tree = ET.parse(fichero_path)
        root = tree.getroot()
        # Intentar extraer viewBox ("min-x min-y width height")
        viewbox = root.attrib.get('viewBox')
        if viewbox:
            partes = viewbox.split()
            if len(partes) == 4:
                return float(partes[2]), float(partes[3])
        
        # Si no hay viewBox, buscar atributos width y height
        w = root.attrib.get('width', '').replace('px', '')
        h = root.attrib.get('height', '').replace('px', '')
        if w and h:
            return float(w), float(h)
    except Exception:
        pass
    return None, None

import hashlib
import os
import re
import xml.etree.ElementTree as ET

def obtener_dimensiones_svg(fichero_path):
    """Lee el viewBox o ancho/alto de un SVG existente para deducir su aspecto original."""
    try:
        tree = ET.parse(fichero_path)
        root = tree.getroot()
        viewbox = root.attrib.get('viewBox')
        if viewbox:
            partes = viewbox.split()
            if len(partes) == 4:
                return float(partes[2]), float(partes[3])
        
        w = root.attrib.get('width', '').replace('px', '')
        h = root.attrib.get('height', '').replace('px', '')
        if w and h:
            return float(w), float(h)
    except Exception:
        pass
    return None, None

def procesar_equations(texto, path_trabajo, dirpage):
    """
    Convierte bloques [[Equation...]]...[[/Equation]] en referencias SVG.

    Formatos admitidos:
        [[Equation]]formula[[/Equation]]
        [[Equation|50]]formula[[/Equation]]
        [[Equation|50|200]]formula[[/Equation]]
        [[Equation||200]]formula[[/Equation]]

    El primer parámetro es la altura y el segundo la anchura.
    """

    patron = re.compile(
        r'\[\[Equation(?:\|([^|\]]*)(?:\|([^|\]]*))?)?\]\]'
        r'(.*?)'
        r'\[\[/Equation\]\]',
        flags=re.DOTALL
    )

    print(f"*** Procesando ecuaciones en {path_trabajo}/{dirpage}")

    os.makedirs(path_trabajo+"/"+dirpage, exist_ok=True)

    def reemplazar(match):
        h_str = match.group(1)
        w_str = match.group(2)
        formula = match.group(3).strip()

        if not formula:
            print("Advertencia: ecuación vacía; se conserva el bloque original.")
            return match.group(0)

        # Interpretar dimensiones opcionales.
        try:
            target_h = float(h_str.strip()) if h_str and h_str.strip() else None
        except (ValueError, AttributeError):
            target_h = None

        try:
            target_w = float(w_str.strip()) if w_str and w_str.strip() else None
        except (ValueError, AttributeError):
            target_w = None

        # Generar un nombre determinista para la caché.
        formula_hash = hashlib.sha256(
            formula.encode("utf-8")
        ).hexdigest()[:16]

        fichero_salida = f"eq_{formula_hash}.svg"
        fichero_absoluto = os.path.join(path_trabajo+"/"+dirpage, fichero_salida)

        # Generar el SVG si no existe.
        if not os.path.exists(fichero_absoluto):
            print(f"Generando SVG: {fichero_absoluto}")
            generar_svg_con_ecuacion(formula, fichero_absoluto)

        # Obtener las dimensiones originales para mantener la proporción.
        orig_w, orig_h = obtener_dimensiones_svg(fichero_absoluto)

        if orig_w and orig_h and orig_w > 0 and orig_h > 0:
            proporcion = orig_w / orig_h

            if target_h is not None and target_w is None:
                target_w = target_h * proporcion
            elif target_w is not None and target_h is None:
                target_h = target_w / proporcion
            elif target_h is None and target_w is None:
                target_w = 200
                target_h = target_w / proporcion
        else:
            if target_w is None:
                target_w = 200
            if target_h is None:
                target_h = 50

        # Evitar dimensiones inválidas.
        target_w = max(1, round(target_w))
        target_h = max(1, round(target_h))

        print(
            f"Ecuación procesada: {formula_hash}, "
            f"altura={target_h}, anchura={target_w}"
        )

        # la sintaxis de imagenes es [[image:miwiki/prueba.png|thumb|300px|right|Logotipo oficial]]
        # return f"[[Image:{dirpage}/{fichero_salida}|{target_w}px]]"
        return f"[[Image:{dirpage}/{fichero_salida}|{target_h}px|{target_w}px|inline]]"

    resultado = patron.sub(reemplazar, texto)

    # Diagnóstico de posibles bloques que hayan quedado sin procesar.
    if re.search(r'\[\[Equation(?:\||\]\])', resultado):
        print(
            "Advertencia: quedan etiquetas [[Equation]] sin procesar. "
            "Comprueba que cada bloque tenga su cierre [[/Equation]]."
        )

    return resultado # fin procesar equations


def procesar_estilos_mediawiki(texto: str) -> str:
    texto = re.sub(r"''''''(.*?)''''''", r'<span style="background-color: lightgreen">\1</span>', texto)
    texto = re.sub(r"'''''(.*?)'''''", r'<b><mark>\1</mark></b>', texto)
    texto = re.sub(r"''''(.*?)''''", r'<mark>\1</mark>', texto)
    texto = re.sub(r"'''(.*?)'''", r"<strong>\1</strong>", texto)
    texto = re.sub(r"''(.*?)''", r"<em>\1</em>", texto)
    return texto


def procesar_linea_verbatim(linea: str, en_pre: bool, html_lineas: list):
    if not en_pre:
        html_lineas.append("<pre>")
    contenido = linea[1:] if linea.startswith(" ") else linea
    html_lineas.append(contenido)


def procesar_cabecera(linea_trim: str) -> str | None:
    match_header = re.match(r"^(=+)\s*(.*?)\s*\1$", linea_trim)
    if match_header:
        nivel = len(match_header.group(1))
        texto_head = match_header.group(2).strip()
        slug = re.sub(r"[^\w]+", "_", texto_head.lower()).strip("_")
        return f'<h{nivel} id="w_{slug}">{texto_head}</h{nivel}>'
    return None


def gestionar_pila_wiki(prefijo: str, pila_actual: list, html_lineas: list) -> str:
    """
    Gestiona una pila multinivel para listas y definiciones de MediaWiki (*, #, ;, :).
    Abre y cierra contenedores (<ul>, <ol>, <dl>) según el prefijo actual.
    """
    info_chars = {
        '*': ('ul', 'li'),
        '#': ('ol', 'li'),
        ';': ('dl', 'dt'),
        ':': ('dl', 'dd'),
    }
    
    comunes = 0
    for c1, c2 in zip(pila_actual, prefijo):
        if c1 == c2:
            comunes += 1
        else:
            break
            
    while len(pila_actual) > comunes:
        char_cerrar = pila_actual.pop()
        container, _ = info_chars.get(char_cerrar, ('ul', 'li'))
        html_lineas.append(f"</{container}>")
        
    for i in range(comunes, len(prefijo)):
        char_abrir = prefijo[i]
        pila_actual.append(char_abrir)
        container, _ = info_chars.get(char_abrir, ('ul', 'li'))
        html_lineas.append(f"<{container}>")
        
    ultimo_char = prefijo[-1]
    _, item_tag = info_chars.get(ultimo_char, ('ul', 'li'))
    return item_tag


def cerrar_todas_listas(pila_listas: list, html_lineas: list):
    """Cierra todas las estructuras abiertas en la pila."""
    info_chars = {
        '*': ('ul', 'li'),
        '#': ('ol', 'li'),
        ';': ('dl', 'dt'),
        ':': ('dl', 'dd'),
    }
    while pila_listas:
        char_cerrar = pila_listas.pop()
        container, _ = info_chars.get(char_cerrar, ('ul', 'li'))
        html_lineas.append(f"</{container}>")


# ============================================================
# COMPLEMENTO DEL FINAL. GESTIÓN DE LISTAS ANIDADAS MEDIAWIKI
# ============================================================
import re
import os

INFO_LISTAS_WIKI = {
    '*': ('ul', 'li'),
    '#': ('ol', 'li'),
    # ';' eliminado de las listas wiki
    ':': ('dl', 'dd'),
}


def abrir_nivel_lista(char, html_lineas):
    """
    Abre un contenedor de lista y devuelve la información del nivel.

    Ejemplo:
        * -> <ul>
        # -> <ol>
        : -> <dl>
    """
    container, item_tag = INFO_LISTAS_WIKI.get(char, ('ul', 'li'))

    html_lineas.append(f"<{container}>")
    html_lineas.append(f"<{item_tag}>")

    return {
        'char': char,
        'container': container,
        'item_tag': item_tag,
    }


def cerrar_nivel_lista(nivel, html_lineas):
    """
    Cierra un nivel de lista.

    El nivel siempre tiene un <li>/<dt>/<dd> abierto,
    por lo que primero cerramos el elemento y después
    el contenedor.
    """
    html_lineas.append(f"</{nivel['item_tag']}>")
    html_lineas.append(f"</{nivel['container']}>")


def gestionar_pila_wiki(
    prefijo: str,
    pila_actual: list,
    html_lineas: list,
    contenido_item: str
):
    """
    Gestiona listas MediaWiki con profundidad arbitraria.

    Ejemplos de prefijos:

        *
        **
        ***
        ****
        *****

    También soporta:

        *
        #
        **
        *#
        *##
        etc.

    La pila contiene los niveles actualmente abiertos.

    Es importante que el <li> actual permanezca abierto para
    poder introducir dentro de él una lista hija.
    """

    if not prefijo:
        return

    # --------------------------------------------------------
    # CASO INICIAL: no hay ninguna lista abierta
    # --------------------------------------------------------
    if not pila_actual:

        for char in prefijo:
            nivel = abrir_nivel_lista(char, html_lineas)
            pila_actual.append(nivel)

        # El contenido pertenece al último <li>/<dt>/<dd>
        html_lineas.append(contenido_item)
        return

    # --------------------------------------------------------
    # Determinar cuántos niveles coinciden
    # --------------------------------------------------------
    comunes = 0

    for nivel, char in zip(pila_actual, prefijo):
        if nivel['char'] == char:
            comunes += 1
        else:
            break

    # ========================================================
    # CASO 1:
    # Hay niveles que desaparecen
    #
    #     *
    #     **
    #     ***
    #     *
    #
    # Hay que cerrar *** y ** antes de continuar con *
    # ========================================================

    while len(pila_actual) > comunes:
        nivel = pila_actual.pop()
        cerrar_nivel_lista(nivel, html_lineas)

    # ========================================================
    # CASO 2:
    # Seguimos en el mismo nivel
    #
    #     * Uno
    #     * Dos
    #
    # comunes == len(prefijo)
    #
    # Tenemos que cerrar el <li> anterior, pero NO el <ul>.
    # ========================================================

    if comunes == len(prefijo) and comunes > 0:

        nivel = pila_actual[-1]

        # Cerrar el elemento anterior
        html_lineas.append(f"</{nivel['item_tag']}>")

        # Abrir el nuevo elemento hermano
        html_lineas.append(f"<{nivel['item_tag']}>")

        # Añadir su contenido
        html_lineas.append(contenido_item)

        return

    # ========================================================
    # CASO 3:
    # Tenemos que abrir niveles nuevos
    #
    #     * Uno
    #     ** Dos
    #     *** Tres
    #
    # El <ul> del nivel hijo se abre DENTRO del <li>
    # del nivel padre, que sigue abierto.
    # ========================================================

    for i in range(comunes, len(prefijo)):

        char = prefijo[i]

        nivel = abrir_nivel_lista(char, html_lineas)
        pila_actual.append(nivel)

        # El contenido solo se añade al último nivel
        if i == len(prefijo) - 1:
            html_lineas.append(contenido_item)


def cerrar_todas_listas(pila_listas: list, html_lineas: list):
    """
    Cierra correctamente todas las listas abiertas.

    Se cierran de dentro hacia fuera.
    """

    while pila_listas:
        nivel = pila_listas.pop()
        cerrar_nivel_lista(nivel, html_lineas)

import os
import re
import subprocess

def procesar_plantuml(texto, path_salida):

    patron = r'\[\[PlantUML=([^\]]+)\]\](.*?)\[\[/PlantUML\]\]'

    def reemplazar(match):

        filename = match.group(1).strip()
        contenido = match.group(2).strip()

        # Evitar que un nombre accidental cree directorios
        filename = os.path.basename(filename)

        fichero_puml = os.path.join(
            path_salida,
            filename + ".puml"
        )

        fichero_svg = os.path.join(
            path_salida,
            filename + ".svg"
        )

        print(f"*** Network encontrado: {filename}")
        print(f"*** Generando PUML: {fichero_puml}")

        # Crear el fichero PlantUML
        try:
            with open(fichero_puml, "w", encoding="utf-8") as f:
                f.write("@startnwdiag\n\n")
                f.write("nwdiag {\n")
                f.write(contenido)
                f.write("\n}\n\n")
                f.write("@endnwdiag\n")

        except Exception as e:
            print(f"*** ERROR escribiendo {fichero_puml}: {e}")
            return match.group(0)

        # Ejecutar PlantUML
        if not generar_svg_con_plantuml(fichero_puml):
            print(f"*** ERROR ejecutando PlantUML para {filename}")
            return match.group(0)

        # Comprobar que realmente se ha creado el SVG
        if not os.path.exists(fichero_svg):
            print(f"*** ERROR: no se ha generado {fichero_svg}")
            return match.group(0)

        print(f"*** SVG generado: {fichero_svg}")

        # Sustituir el bloque Network por la imagen
        return f"[[Image:{filename}.svg|800px]]"

    return re.sub(
        patron,
        reemplazar,
        texto,
        flags=re.DOTALL
    )

def generar_svg_con_plantuml(fichero_puml):

    plantuml_jar = os.path.expanduser(
        "~/Notas/misnotas/plantuml.jar"
    )

    if not os.path.exists(plantuml_jar):
        print(f"*** ERROR: no existe PlantUML: {plantuml_jar}")
        return False

    comando = [
        "java",
        "-jar",
        plantuml_jar,
        "-tsvg",
        fichero_puml
    ]

    print("*** Ejecutando PlantUML:")
    print("    " + " ".join(comando))

    try:
        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True
        )

    except Exception as e:
        print(f"*** ERROR ejecutando PlantUML: {e}")
        return False

    if resultado.stdout:
        print("*** PlantUML stdout:")
        print(resultado.stdout)

    if resultado.stderr:
        print("*** PlantUML stderr:")
        print(resultado.stderr)

    if resultado.returncode != 0:
        print(
            f"*** ERROR PlantUML. Código de salida: "
            f"{resultado.returncode}"
        )
        return False

    return True

def generar_svg_con_plantuml(fichero_puml):
    """
    Convierte un fichero .puml en SVG usando PlantUML.
    """
    plantuml_jar = os.path.expanduser("~/Notas/misnotas/plantuml.jar")

    comando = [
        "java",
        "-jar",
        plantuml_jar,
        "-tsvg",
        fichero_puml
    ]

    print("Ejecutando:", " ".join(comando))

    resultado = subprocess.run(
        comando,
        capture_output=True,
        text=True
    )

    if resultado.returncode != 0:
        print("ERROR PlantUML:")
        print(resultado.stdout)
        print(resultado.stderr)
        return False

    return True

def procesar_enlaces_mediawiki(wiki_text: str) -> str:
    """
    Convierte:
    1. Enlaces estilo MediaWiki [URL texto] o [URL] en <a href="URL">texto</a>.
    2. URLs sueltas (http://... o https://...) en enlaces clicables <a href="URL">URL</a>.
    """
    
    # 1. Enlaces con corchetes simples: [url texto opcional]
    # Ejemplo: [https://ejemplo.com mi web] -> <a href="https://ejemplo.com">mi web</a>
    # Ejemplo: [https://ejemplo.com] -> <a href="https://ejemplo.com">https://ejemplo.com</a>
    def reemplazar_corchetes(match):
        url = match.group(1)
        texto = match.group(2)
        if not texto:
            texto = url
        #return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{texto}</a>'
        return f'<a href="{url}">{texto}</a>'

    # Expresión regular para [URL] o [URL texto]
    wiki_text = re.sub(
        r'\[(https?://[^\s\]]+)(?:\s+([^\]]+))?\]',
        reemplazar_corchetes,
        wiki_text
    )

    # 2. URLs directas que no estén ya dentro de un atributo href="..." o etiquetas HTML
    # Buscamos URLs que comiencen por http:// o https:// y no vayan precedidas de un href="
    url_pattern = re.compile(r'(?<!href=["\'])(https?://[^\s<]+)')
    
    def reemplazar_url_suelta(match):
        url = match.group(1)
        # return f'<a href="{url}" target="_blank" rel="noopener noreferrer">{url}</a>'
        return f'<a href="{url}">{url}</a>'

    wiki_text = url_pattern.sub(reemplazar_url_suelta, wiki_text)

    return wiki_text

# ============================================================
# FUNCION PRINCIPAL DE CONVERSIÓN DEL FICHERO
# ============================================================


def convert_file(
    input_path: str,
    output_path: str,
    tabla,
    directorio_src: str = None
) -> bool:

    pagename = os.path.basename(input_path)
    dirpage = os.path.splitext(os.path.basename(input_path))[0]


    print(f"*** Comenzamos a compilar la página {input_path} con dir {dirpage}")

    try:

        print(f"[DEBUG] Leyendo fichero de entrada: {input_path} de dir {dirpage}")

        with open(input_path, "r", encoding="utf-8") as f:
            wiki_text = f.read()

        if not directorio_src:
            directorio_src = os.path.dirname(
                os.path.abspath(input_path)
            )

        print(f"*** trabajando en {directorio_src} sobre la pagina {pagename}")

        # ====================================================
        # 1. PREPROCESAMIENTO GLOBAL
        # ====================================================

        wiki_text = procesar_plantuml(
            wiki_text,
            directorio_src
        )

        wiki_text = procesar_d2(
            wiki_text,
            directorio_src
        )

        wiki_text = procesar_graphs(
            wiki_text,
            directorio_src
        )

        wiki_text = procesar_equations(
            wiki_text,
            directorio_src,
            dirpage
        )

        # Las imagenes se procesan al final ya que los anteriores generan imagenes

        wiki_text = normalizar_enlaces_mediawiki(
            wiki_text,
            directorio_src
        )

        # --- NUEVO: Procesar enlaces con corchetes simples y URLs directas ---
        wiki_text = procesar_enlaces_mediawiki(
            wiki_text
        )

        wiki_text = procesar_estilos_mediawiki(
            wiki_text
        )

        # ====================================================
        # 2. ESTRUCTURA HTML INICIAL
        # ====================================================

        html_lineas = [
            '<!DOCTYPE html>',
            '<html lang="es">',
            '<head>',
            '<meta charset="UTF-8">',
            '<title>Mi página</title>',
            '</head>',
            '<body>'
        ]

        en_pre = False
        pila_listas = []

        # ====================================================
        # 3. PROCESAMIENTO LÍNEA A LÍNEA
        # ====================================================

        for linea in wiki_text.splitlines():

            # ------------------------------------------------
            # VERBATIM / PRE
            # ------------------------------------------------

            es_verbatim = (
                linea.startswith(" ")
                or linea.startswith("\t")
            )

            if es_verbatim:
                linea = sustituir_linea_pre(linea, tabla)
            else:
                linea = sustituir_linea(linea, tabla)

            if es_verbatim:

                cerrar_todas_listas(
                    pila_listas,
                    html_lineas
                )

                procesar_linea_verbatim(
                    linea,
                    en_pre,
                    html_lineas
                )

                en_pre = True
                continue

            else:

                if en_pre:
                    html_lineas.append("</pre>")
                    en_pre = False

            # ------------------------------------------------
            # Limpiar espacios exteriores
            # ------------------------------------------------

            linea_trim = linea.strip()

            # ------------------------------------------------
            # CABECERAS
            # ------------------------------------------------

            html_header = procesar_cabecera(
                linea_trim
            )

            if html_header:

                cerrar_todas_listas(
                    pila_listas,
                    html_lineas
                )

                html_lineas.append(
                    html_header
                )

                continue

            # ------------------------------------------------
            # LISTAS MEDIAWIKI
            # ------------------------------------------------

            match_wiki_line = re.match(
                r"^([*#:]+)\s*(.*)",
                linea_trim
            )

            if match_wiki_line:

                prefijo = match_wiki_line.group(1)

                contenido_item = (
                    match_wiki_line.group(2).strip()
                )

                gestionar_pila_wiki(
                    prefijo,
                    pila_listas,
                    html_lineas,
                    contenido_item
                )

                continue

            # ------------------------------------------------
            # PÁRRAFO NORMAL / HTML DIRECTO
            # ------------------------------------------------

            cerrar_todas_listas(
                pila_listas,
                html_lineas
            )

            if linea_trim:

                # HTML directo
                if (
                    linea_trim.startswith("<")
                    and (
                        linea_trim.endswith("/>")
                        or linea_trim.endswith(">")
                    )
                ):
                    html_lineas.append(
                        linea_trim
                    )

                else:
                    html_lineas.append(
                        f"<p>{linea_trim}</p>"
                    )

        # ====================================================
        # 4. CIERRE FINAL
        # ====================================================

        cerrar_todas_listas(
            pila_listas,
            html_lineas
        )

        if en_pre:
            html_lineas.append("</pre>")

        html_lineas.append("</body>")
        html_lineas.append("</html>")

        # ====================================================
        # 5. GENERAR HTML
        # ====================================================

        html_final = "\n".join(
            html_lineas
        )

        # ====================================================
        # 6. ESCRIBIR FICHERO
        # ====================================================

        with open(
            output_path,
            "w",
            encoding="utf-8"
        ) as f:

            f.write(html_final)

        print(
            f"Convertido: {input_path} -> {output_path}"
        )

        return True

    except Exception as e:

        print(
            f"[ERROR] Fallo en convert_file: {e}"
        )

        return False


