import os
import subprocess

def compilar_sincrono(ruta_wiki, ruta_html):
    """Ejecuta Pandoc de forma síncrona para resolución inmediata de enlaces."""
    try:
        res = subprocess.run(
            ["pandoc", "-f", "mediawiki", "-t", "html", "-s", "-o", ruta_html, ruta_wiki],
            check=False
        )
        return res.returncode == 0 and os.path.exists(ruta_html)
    except Exception:
        return False

