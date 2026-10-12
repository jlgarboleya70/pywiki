def resolve_link_to_html(ruta_local):
    """
    Resuelve un enlace local:
      - archivo existente -> ese archivo
      - directorio -> index.html
      - sin extensión -> .html
      - .html -> se conserva
    """
    ruta_local = os.path.abspath(ruta_local)

    if os.path.exists(ruta_local) and not os.path.isdir(ruta_local):
        return ruta_local

    if os.path.isdir(ruta_local):
        return os.path.join(ruta_local, "index.html")

    if not ruta_local.lower().endswith(".html"):
        return ruta_local + ".html"

    return ruta_local

def wiki_to_html(ruta_wiki, src_dir, build_dir):
    """
    Convierte una ruta .wiki de src_dir a la ruta .html equivalente
    dentro de build_dir.
    """
    ruta_wiki = os.path.abspath(ruta_wiki)
    src_dir = os.path.abspath(src_dir)
    build_dir = os.path.abspath(build_dir)

    if not is_inside(ruta_wiki, src_dir):
        return None

    if not ruta_wiki.lower().endswith(".wiki"):
        return None

    relativa = os.path.relpath(ruta_wiki, src_dir)
    relativa_html = os.path.splitext(relativa)[0] + ".html"

    ruta_html = os.path.abspath(os.path.join(build_dir, relativa_html))

    if not is_inside(ruta_html, build_dir):
        return None

    return ruta_html

import os

def resolver_ruta_html(ruta_wiki, src_dir, build_dir):
    """Calcula la ruta .html destino correspondiente a partir de un .wiki."""
    try:
        relativa = os.path.relpath(ruta_wiki, src_dir)
        if relativa.startswith(".." + os.sep) or not relativa.lower().endswith(".wiki"):
            return None
        relativa_html = os.path.splitext(relativa)[0] + ".html"
        ruta_html = os.path.abspath(os.path.join(build_dir, relativa_html))
        
        if os.path.commonpath([ruta_html, build_dir]) != build_dir:
            return None
        return ruta_html
    except ValueError:
        return None



def resolver_ruta_wiki(ruta_html, src_dir, build_dir):
    """Calcula la ruta .wiki correspondiente a partir de una ruta .html."""
    try:
        relativa = os.path.relpath(ruta_html, build_dir)
        if relativa.startswith(".." + os.sep):
            return None
        relativa_wiki = os.path.splitext(relativa)[0] + ".wiki"
        ruta_wiki = os.path.abspath(os.path.join(src_dir, relativa_wiki))
        
        if os.path.commonpath([ruta_wiki, src_dir]) != src_dir:
            return None
        return ruta_wiki if os.path.isfile(ruta_wiki) else None
    except ValueError:
        return None


def html_to_wiki(ruta_html, build_dir, src_dir):
    """
    Convierte una ruta .html de build_dir a la ruta .wiki equivalente
    dentro de src_dir.
    """
    ruta_html = os.path.abspath(ruta_html)
    build_dir = os.path.abspath(build_dir)
    src_dir = os.path.abspath(src_dir)

    if not is_inside(ruta_html, build_dir):
        return None

    if not ruta_html.lower().endswith(".html"):
        return None

    relativa = os.path.relpath(ruta_html, build_dir)
    relativa_wiki = os.path.splitext(relativa)[0] + ".wiki"

    ruta_wiki = os.path.abspath(os.path.join(src_dir, relativa_wiki))

    if not is_inside(ruta_wiki, src_dir):
        return None

    return ruta_wiki


def listar_ficheros_wiki(directorio_raiz: str) -> list[str]:
    """Recorre el directorio raíz y devuelve las rutas relativas o nombres de archivos .wiki."""
    archivos_wiki = []
    if not os.path.exists(directorio_raiz):
        return archivos_wiki

    for root, _, files in os.walk(directorio_raiz):
        for file in files:
            if file.endswith(".wiki"):
                ruta_completa = os.path.join(root, file)
                # Guardamos la ruta relativa respecto a la raíz del proyecto/notas
                ruta_relativa = os.path.relpath(ruta_completa, directorio_raiz)
                archivos_wiki.append(ruta_relativa)

    return sorted(archivos_wiki)


def is_inside(path, directory):
    """Devuelve True si path está dentro de directory."""
    path = os.path.abspath(path)
    directory = os.path.abspath(directory)

    try:
        return os.path.commonpath([path, directory]) == directory
    except ValueError:
        return False
