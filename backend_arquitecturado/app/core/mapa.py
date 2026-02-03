# backend_arquitecturado/app/core/mapa.py
import osmnx as ox
import os
from app.core.config import LAT_CENTRO, LON_CENTRO, DISTANCIA, TIPO_RED

# Configuración para descargas grandes
ox.settings.use_cache = True
ox.settings.log_console = True
ox.settings.timeout = 300  # 5 minutos de tolerancia para descargar

CACHE_DIR = "cache"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

_GRAFO_GLOBAL = None

def get_grafo():
    global _GRAFO_GLOBAL
    if _GRAFO_GLOBAL is not None:
        return _GRAFO_GLOBAL

    # Nombre de archivo basado en el radio para diferenciar versiones
    filename = f"mapa_cdmx_metropolitana_{DISTANCIA}.graphml"
    filepath = os.path.join(CACHE_DIR, filename)

    if os.path.exists(filepath):
        print(f"✅ Cargando mapa cacheado desde: {filename}")
        # GraphML es mucho más rápido de leer que JSON para grafos grandes
        _GRAFO_GLOBAL = ox.load_graphml(filepath)
    else:
        print(f"⬇️ Descargando mapa de la ZMVM (Radio: {DISTANCIA/1000}km)... esto tardará varios minutos.")
        try:
            # Descarga el grafo
            G = ox.graph_from_point(
                (LAT_CENTRO, LON_CENTRO), 
                dist=DISTANCIA, 
                network_type=TIPO_RED
            )
            # Guardamos en formato GraphML
            print("💾 Guardando mapa en caché para el futuro...")
            ox.save_graphml(G, filepath)
            _GRAFO_GLOBAL = G
        except Exception as e:
            print(f"❌ Error descargando el mapa: {e}")
            return None

    return _GRAFO_GLOBAL