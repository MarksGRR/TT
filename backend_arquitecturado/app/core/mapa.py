import osmnx as ox
import networkx as nx
# IMPORTAMOS LA CONFIGURACIÓN CENTRALIZADA
from app.core.config import (
    LAT_CENTRO, LON_CENTRO, RADIO_CARGA_MAPA,
    VEL_CALLE_KMH, VEL_AVENIDA_KMH, TIPOS_AVENIDA
)

G = None

def get_grafo():
    return G

def cargar_mapa():
    global G
    print(f"\n>>> 📡 CARGANDO MAPA ({RADIO_CARGA_MAPA}m)...")
    try:
        # 1. Descargar Grafo
        G_gps = ox.graph_from_point((LAT_CENTRO, LON_CENTRO), dist=RADIO_CARGA_MAPA, network_type='drive')
        
        # 2. LIMPIEZA AGRESIVA DE ISLAS (Esto arregla rutas de 87km)
        # Nos quedamos solo con el grupo de calles que están todas conectadas entre sí
        largest_cc = max(nx.strongly_connected_components(G_gps), key=len)
        G = G_gps.subgraph(largest_cc).copy()
        
        # 3. Asignar Velocidades (V-Plata)
        speed_calle_ms = VEL_CALLE_KMH / 3.6
        speed_av_ms = VEL_AVENIDA_KMH / 3.6

        for u, v, k, data in G.edges(keys=True, data=True):
            tipo = data.get('highway', 'residential')
            if isinstance(tipo, list): tipo = tipo[0]
            
            length = data.get('length', 10)
            
            # Asignación precisa
            if tipo in TIPOS_AVENIDA:
                velocidad = speed_av_ms
            else:
                velocidad = speed_calle_ms
            
            # GUARDAMOS EL TIEMPO EN SEGUNDOS
            data['travel_time'] = length / velocidad

        print(">>> ✅ MAPA LISTO: Velocidades V-Plata aplicadas.")
        
    except Exception as e:
        print(f">>> ❌ ERROR CARGANDO MAPA: {e}")
        G = None