import os

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

