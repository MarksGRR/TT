import networkx as nx
import numpy as np
from app.core.config import TIEMPO_SERVICIO_MIN # <--- Importamos desde config

# ==========================================
#       LÓGICA MATEMÁTICA PRINCIPAL
# ==========================================

def calcular_metricas(ruta_indices, lista_nodos_global, G, nombre_ruta="Ruta"):
    """
    Calcula métricas con REPORTES EN CONSOLA para verificar la lógica V-Plata.
    """
    if not ruta_indices or G is None: return 0, "0m"
    
    # Reconstruir nodos
    ruta_nodos = [lista_nodos_global[i] for i in ruta_indices]
    
    if len(ruta_nodos) < 2: return 0, "0m"

    d_m = 0
    t_conduccion_sec = 0
    tramos_exitosos = 0
    
    # 1. Calcular trayecto de conducción
    for i in range(len(ruta_nodos) - 1):
        u, v = ruta_nodos[i], ruta_nodos[i+1]
        try:
            # Buscamos camino usando el tiempo calculado en mapa.py
            path = nx.shortest_path(G, u, v, weight='travel_time')
            tramos_exitosos += 1
            
            for n1, n2 in zip(path[:-1], path[1:]):
                edge_data = G.get_edge_data(n1, n2)[0]
                d_m += edge_data.get('length', 0)
                t_conduccion_sec += edge_data.get('travel_time', 0)
        except:
            # AQUI ESTABA EL PROBLEMA SILENCIOSO
            print(f">>> ⚠️ ALERTA: No hay camino entre nodo {u} y {v}. Tramo saltado.")

    # 2. Agregar Tiempo de Servicio (5 min por parada)
    # Excluimos el nodo de inicio, solo destinos.
    # Usamos tramos_exitosos para asegurarnos de no cobrar servicio si no llegamos.
    num_paradas = max(0, len(ruta_nodos) - 1) 
    t_servicio_sec = num_paradas * (TIEMPO_SERVICIO_MIN * 60)
    
    t_total_sec = t_conduccion_sec + t_servicio_sec
    
    # Conversiones
    km = round(d_m / 1000.0, 2)
    mins_totales = t_total_sec / 60.0
    
    # --- CHIVATO DE CONSOLA (DEBUG) ---
    print(f"\n📊 REPORTE {nombre_ruta.upper()}:")
    print(f"   - Distancia: {km} km")
    print(f"   - Tiempo Manejo: {round(t_conduccion_sec/60, 1)} min")
    print(f"   - Tiempo Servicio: {round(t_servicio_sec/60, 1)} min ({num_paradas} paradas x {TIEMPO_SERVICIO_MIN}m)")
    print(f"   - TOTAL: {round(mins_totales, 1)} min")
    # ----------------------------------

    if mins_totales < 60:
        tiempo_str = f"{int(mins_totales)} min"
    else:
        tiempo_str = f"{int(mins_totales//60)}h {int(mins_totales%60)}m"
        
    return km, tiempo_str

# --- MANTÉN TU FUNCIÓN optimizar_indices IGUAL ---
def optimizar_indices(indices_activos, sub_matriz, idx_arranque=None, idx_destino=None):
    # (Pega aquí el código de optimización que ya tenías, ese está bien)
    # ... código de optimizar_indices ...
    n = len(indices_activos)
    if n == 0: return []
    if n == 1: return indices_activos
    pendientes = set(range(n)); ruta_local = []
    curr = 0
    if idx_arranque is not None and idx_arranque in indices_activos:
        curr = indices_activos.index(idx_arranque)
    ruta_local.append(curr)
    if curr in pendientes: pendientes.remove(curr)
    dest = None
    if idx_destino is not None and idx_destino in indices_activos:
        dest = indices_activos.index(idx_destino)
        if dest in pendientes: pendientes.remove(dest)
    while pendientes:
        best_next = None; min_dist = float('inf')
        for cand in pendientes:
            d = sub_matriz[curr][cand]
            if d < min_dist: min_dist = d; best_next = cand
        if best_next is not None:
            ruta_local.append(best_next); pendientes.remove(best_next); curr = best_next
        else:
            nxt = list(pendientes)[0]; ruta_local.append(nxt); pendientes.remove(nxt); curr = nxt
    if dest is not None: ruta_local.append(dest)
    mejoro = True; iteraciones = 0
    lim = len(ruta_local) - 1 if dest is not None else len(ruta_local)
    while mejoro and iteraciones < 50:
        mejoro = False; iteraciones += 1
        for i in range(1, lim - 1):
            for j in range(i + 1, lim):
                if j - i == 1: continue
                ia, ib = ruta_local[i-1], ruta_local[i]
                ic, id_ = ruta_local[j-1], ruta_local[j]
                if sub_matriz[ia][ib] + sub_matriz[ic][id_] < sub_matriz[ia][ib] + sub_matriz[ic][id_]:
                    ruta_local[i:j] = ruta_local[i:j][::-1]; mejoro = True
    return [indices_activos[i] for i in ruta_local]
