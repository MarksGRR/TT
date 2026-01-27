import networkx as nx
import numpy as np
from app.core.config import TIEMPO_SERVICIO

# ==========================================
#      TU LÓGICA ORIGINAL (INTACTA)
# ==========================================

def calcular_metricas(ruta_indices, lista_nodos_global, G):
    if not ruta_indices or G is None: return 0, "0m"
    d_m = 0; t_sec = 0
    ruta_nodos = [lista_nodos_global[i] for i in ruta_indices]
    for i in range(len(ruta_nodos) - 1):
        try:
            u, v = ruta_nodos[i], ruta_nodos[i+1]
            t = nx.shortest_path_length(G, u, v, weight='travel_time')
            d = nx.shortest_path_length(G, u, v, weight='length')
            d_m += d; t_sec += t; t_sec += (TIEMPO_SERVICIO * 60)
        except: pass
    t_sec += (TIEMPO_SERVICIO * 60)
    km = d_m / 1000.0; mins = t_sec / 60.0
    return round(km, 2), f"{int(mins)}m" if mins < 60 else f"{int(mins//60)}h {int(mins%60)}m"

def optimizar_indices(indices_activos, sub_matriz, idx_arranque=None, idx_destino=None):
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
            nxt = list(pendientes)[0]
            ruta_local.append(nxt); pendientes.remove(nxt); curr = nxt
            
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
                if sub_matriz[ia][ic] + sub_matriz[ib][id_] < sub_matriz[ia][ib] + sub_matriz[ic][id_]:
                    ruta_local[i:j] = ruta_local[i:j][::-1]; mejoro = True
    return [indices_activos[i] for i in ruta_local]


# ==========================================
#      NUEVAS FUNCIONES AÑADIDAS
# ==========================================

def calcular_nueva_ruta_global(inicio: tuple, fin: tuple):
    """
    Genera una estructura básica de ruta cuando el usuario selecciona
    nuevos puntos de inicio/fin (Reset).
    Aquí se simula una ruta lineal, pero podrías conectar esto 
    con tu lógica de optimización si tienes la matriz completa disponible.
    """
    ruta = []
    # Generamos algunos puntos intermedios simulados para visualización
    pasos = 5 
    lat_diff = (fin[0] - inicio[0]) / pasos
    lng_diff = (fin[1] - inicio[1]) / pasos

    for i in range(pasos + 1):
        ruta.append({
            "id": i, # ID temporal
            "lat": inicio[0] + (lat_diff * i),
            "lng": inicio[1] + (lng_diff * i),
            "estado": "pendiente" 
        })
    return ruta

def obtener_cluster_manual(ruta_global: list, inicio_cluster: tuple, fin_cluster: tuple):
    """
    Filtra los nodos de la ruta global que caen dentro del área seleccionada
    (Bounding Box) sin modificar la lista original.
    """
    if not inicio_cluster or not fin_cluster or not ruta_global:
        return []

    # 1. Definir límites del rectángulo
    lat_min = min(inicio_cluster[0], fin_cluster[0])
    lat_max = max(inicio_cluster[0], fin_cluster[0])
    lng_min = min(inicio_cluster[1], fin_cluster[1])
    lng_max = max(inicio_cluster[1], fin_cluster[1])

    nodos_cluster = []

    # 2. Filtrar
    for nodo in ruta_global:
        # Soporta tanto diccionarios como objetos, ajusta según tu modelo real
        lat = nodo.get('lat') if isinstance(nodo, dict) else getattr(nodo, 'lat', 0)
        lng = nodo.get('lng') if isinstance(nodo, dict) else getattr(nodo, 'lng', 0)

        if lat_min <= lat <= lat_max and lng_min <= lng <= lng_max:
            # Devolvemos copia para evitar mutaciones accidentales
            nodos_cluster.append(nodo.copy() if isinstance(nodo, dict) else nodo)

    return nodos_cluster

def cambiar_estado_nodo(ruta: list, parada_id: int, estado: str):
    """
    Actualiza el estado ('visitado', 'omitido', 'pendiente') de una parada específica.
    """
    nueva_ruta = [p.copy() for p in ruta] # Copia superficial para inmutabilidad
    encontrado = False
    
    for parada in nueva_ruta:
        p_id = parada.get('id') if isinstance(parada, dict) else getattr(parada, 'id', None)
        if p_id == parada_id:
            parada['estado'] = estado
            encontrado = True
            break
            
    if not encontrado:
        # Opcional: lanzar error o ignorar
        pass
        
    return nueva_ruta

def eliminar_zonas(lista_zonas: list, zona_id: str = None):
    """
    Elimina una zona específica por ID o todas si zona_id es None.
    """
    if zona_id is None:
        return [] # Borrar todo
    
    return [z for z in lista_zonas if z.get('id') != zona_id]