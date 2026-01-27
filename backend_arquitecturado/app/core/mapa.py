# app/core/mapa.py
import osmnx as ox
import networkx as nx
from .config import LAT_CENTRO, LON_CENTRO, RADIO_CARGA_MAPA, VEL_CALLE, VEL_AVENIDA

# Variable Global que guardará el mapa en memoria RAM
grafo_global = None

def cargar_mapa():
    """Descarga y procesa el mapa de OSMnx"""
    global grafo_global
    print(f"\n>>> 📡 CARGANDO MAPA DE: {LAT_CENTRO}, {LON_CENTRO}...")
    
    try:
        # 1. Descargar
        G = ox.graph_from_point((LAT_CENTRO, LON_CENTRO), dist=RADIO_CARGA_MAPA, network_type='drive')
        
        # 2. Limpiar (Componente más grande)
        largest_cc = max(nx.strongly_connected_components(G), key=len)
        G = G.subgraph(largest_cc).copy()
        
        # 3. Procesar Costos (Penalización de Avenidas)
        lista_avs = ['primary', 'secondary', 'trunk', 'primary_link', 'secondary_link']
        speed_calle_ms = VEL_CALLE / 3.6
        speed_av_ms = VEL_AVENIDA / 3.6

        for u, v, k, data in G.edges(keys=True, data=True):
            tipo = data.get('highway', 'residential')
            if isinstance(tipo, list): tipo = tipo[0]
            
            length = data.get('length', 10)
            
            # Costo 1: Tiempo Real
            velocidad = speed_av_ms if tipo in lista_avs else speed_calle_ms
            data['travel_time'] = length / velocidad
            
            # Costo 2: Agrupación (Penalización x10)
            if tipo in lista_avs:
                data['costo_agrupacion'] = length * 10
            else:
                data['costo_agrupacion'] = length
        
        grafo_global = G
        print(">>> ✅ MAPA LISTO Y PROCESADO.")
        return True
    except Exception as e:
        print(f">>> ❌ ERROR CARGANDO MAPA: {e}")
        return False

def get_grafo():
    """Función para obtener el mapa desde otros archivos"""
    return grafo_global