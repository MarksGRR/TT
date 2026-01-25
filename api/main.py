import io
import base64
import random
import contextlib
from typing import List, Optional, Dict, Any

# --- LIBRERÍAS ---
import osmnx as ox
import networkx as nx
import numpy as np
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
from sklearn.cluster import AgglomerativeClustering

# --- FASTAPI ---
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ==============================================================================
# 1. CONFIGURACIÓN Y VARIABLES
# ==============================================================================

LAT_CENTRO = 19.4938
LON_CENTRO = -99.0478
RADIO_CARGA_MAPA = 2500 
RADIO_CLUSTER_METROS = 1000 

VEL_CALLE = 20   # km/h
VEL_AVENIDA = 50 # km/h
TIEMPO_SERVICIO = 5 

G = None 
CACHE_SIMULACION = {} 

# ==============================================================================
# 2. CARGA DEL MAPA (LIFESPAN)
# ==============================================================================

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    global G
    print(f"\n>>> 📡 CARGANDO MAPA DE: {LAT_CENTRO}, {LON_CENTRO}...")
    try:
        G_gps = ox.graph_from_point((LAT_CENTRO, LON_CENTRO), dist=RADIO_CARGA_MAPA, network_type='drive')
        largest_cc = max(nx.strongly_connected_components(G_gps), key=len)
        G_gps = G_gps.subgraph(largest_cc).copy()
        G = G_gps 
        
        lista_avs = ['primary', 'secondary', 'trunk', 'primary_link', 'secondary_link']
        speed_calle_ms = VEL_CALLE / 3.6
        speed_av_ms = VEL_AVENIDA / 3.6

        for u, v, k, data in G.edges(keys=True, data=True):
            tipo = data.get('highway', 'residential')
            if isinstance(tipo, list): tipo = tipo[0]
            length = data.get('length', 10)
            
            velocidad = speed_av_ms if tipo in lista_avs else speed_calle_ms
            data['travel_time'] = length / velocidad
            
            if tipo in lista_avs:
                data['costo_agrupacion'] = length * 10
            else:
                data['costo_agrupacion'] = length

        print(">>> ✅ MAPA LISTO Y PROCESADO.")
        yield
    except Exception as e:
        print(f">>> ❌ ERROR CARGANDO MAPA: {e}")
        yield
    finally:
        G = None

# ==============================================================================
# 3. APP SETUP
# ==============================================================================

app = FastAPI(title="Logística API V-Gold", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================================
# 4. ALGORITMOS MATEMÁTICOS
# ==============================================================================

def calcular_metricas(ruta):
    if not ruta: return 0, "0m"
    d_m = 0
    t_sec = 0
    
    for i in range(len(ruta) - 1):
        try:
            path = nx.shortest_path(G, ruta[i], ruta[i+1], weight='travel_time')
            for u, v in zip(path[:-1], path[1:]):
                edge_data = min(G[u][v].values(), key=lambda x: x['travel_time'])
                d_m += edge_data['length']
                t_sec += edge_data['travel_time']
            t_sec += (TIEMPO_SERVICIO * 60)
        except: pass
    
    t_sec += (TIEMPO_SERVICIO * 60)
    km = d_m / 1000.0
    mins = t_sec / 60.0
    
    tiempo_str = f"{int(mins)}m" if mins < 60 else f"{int(mins//60)}h {int(mins%60)}m"
    return round(km, 2), tiempo_str

def optimizar_ruta_fluida(lista_nodos, matriz_tiempos, nodo_to_idx, nodo_arranque=None, nodo_destino=None):
    if not lista_nodos: return []
    if len(lista_nodos) == 1: return lista_nodos
    
    pendientes = set(lista_nodos)
    ruta = []

    # 1. GESTIÓN INICIO
    if nodo_arranque and nodo_arranque in pendientes:
        curr = nodo_arranque
    else:
        lista_ordenada = sorted(lista_nodos, key=lambda n: G.nodes[n]['x'])
        curr = lista_ordenada[0]
        if curr == nodo_destino and len(lista_ordenada) > 1:
            curr = lista_ordenada[1]

    ruta.append(curr)
    if curr in pendientes: pendientes.remove(curr)

    # 2. GESTIÓN DESTINO (Lo apartamos)
    if nodo_destino and nodo_destino in pendientes:
        pendientes.remove(nodo_destino)
    
    # 3. GREEDY (Vecino más cercano)
    while pendientes:
        curr_idx = nodo_to_idx[curr]
        best_next = None
        min_dist = float('inf')
        
        for cand in pendientes:
            cand_idx = nodo_to_idx[cand]
            d = matriz_tiempos[curr_idx][cand_idx]
            if d < min_dist:
                min_dist = d
                best_next = cand
        
        if best_next:
            ruta.append(best_next)
            pendientes.remove(best_next)
            curr = best_next
        else:
            nxt = list(pendientes)[0]
            ruta.append(nxt)
            pendientes.remove(nxt)
            curr = nxt
            
    # 4. PEGAR DESTINO
    if nodo_destino:
        ruta.append(nodo_destino)

    # 5. 2-OPT (Mejora)
    mejoro = True
    iteraciones = 0
    limite_inf = 1
    limite_sup = len(ruta) - 1 if nodo_destino else len(ruta)

    while mejoro and iteraciones < 30:
        mejoro = False
        iteraciones += 1
        for i in range(limite_inf, limite_sup - 1): 
            for j in range(i + 1, limite_sup):
                if j - i == 1: continue
                ia, ib = nodo_to_idx[ruta[i-1]], nodo_to_idx[ruta[i]]
                ic, id_ = nodo_to_idx[ruta[j-1]], nodo_to_idx[ruta[j]]
                cur = matriz_tiempos[ia][ib] + matriz_tiempos[ic][id_]
                new = matriz_tiempos[ia][ic] + matriz_tiempos[ib][id_]
                if new < cur:
                    ruta[i:j] = ruta[i:j][::-1]
                    mejoro = True
    return ruta

# ==============================================================================
# 5. ENDPOINT PRINCIPAL (Con VIPs Persistentes)
# ==============================================================================

@app.get("/simulacion-leaflet")
def simulacion_leaflet(
    id_inicio: str = None, 
    id_fin: str = None, 
    accion_id: str = None, 
    accion_tipo: str = None
):
    global CACHE_SIMULACION
    if G is None: raise HTTPException(503, "Mapa cargando...")

    puntos_totales = []
    
    # 1. GESTIÓN DE MEMORIA
    if CACHE_SIMULACION and CACHE_SIMULACION.get("puntos"):
        puntos_totales = CACHE_SIMULACION.get("puntos", [])
        
        # Aplicar Acciones
        if accion_id and accion_tipo:
            for p in puntos_totales:
                if p["id"] == accion_id:
                    if accion_tipo == "visitar": p["estado"] = "VISITADO"
                    elif accion_tipo == "omitir": p["estado"] = "OMITIDO"
                    elif accion_tipo == "restaurar": p["estado"] = "PENDIENTE"
                    break
            CACHE_SIMULACION["puntos"] = puntos_totales

        # Reset total forzado
        if id_inicio is None and id_fin is None and accion_id is None:
             puntos_totales = [] 
    
    # 2. GENERACIÓN DE PUNTOS (UNA SOLA VEZ CON ROLES FIJOS)
    if not puntos_totales:
        print(">>> Generando puntos nuevos...")
        CANTIDAD = 30
        puntos_totales = []
        for i in range(CANTIDAD):
            lat = LAT_CENTRO + random.uniform(-0.010, 0.010)
            lon = LON_CENTRO + random.uniform(-0.010, 0.010)
            
            # Determinamos rol al nacer
            es_vip = random.random() < 0.20
            rol = "VIP" if es_vip else "NORMAL"
            
            puntos_totales.append({
                "id": f"P-{i+1}", 
                "lat": lat, 
                "lon": lon, 
                "estado": "PENDIENTE",
                "rol_base": rol # <--- PERSISTENCIA
            })
        CACHE_SIMULACION = {"puntos": puntos_totales}

    # 3. FILTRADO (Quiénes juegan en el mapa actual)
    punto_arranque = next((p for p in puntos_totales if p["id"] == id_inicio), None)
    punto_destino = next((p for p in puntos_totales if p["id"] == id_fin), None)
    
    puntos_ruteables = [
        p for p in puntos_totales 
        if p["estado"] == "PENDIENTE" or p["id"] == id_inicio or p["id"] == id_fin
    ]
    
    # Mapeo a Nodos
    lats_r = [p["lat"] for p in puntos_ruteables]
    lons_r = [p["lon"] for p in puntos_ruteables]
    nodos_mapeados_ruteables = ox.distance.nearest_nodes(G, lons_r, lats_r) if lats_r else []
    
    nodo_arranque_id = ox.distance.nearest_nodes(G, punto_arranque["lon"], punto_arranque["lat"]) if punto_arranque else None
    nodo_destino_id = ox.distance.nearest_nodes(G, punto_destino["lon"], punto_destino["lat"]) if punto_destino else None

    nodos_unicos = list(set(nodos_mapeados_ruteables))
    nodo_to_idx = {n: i for i, n in enumerate(nodos_unicos)}
    
    # Mapeos inversos
    nodo_to_pedido_id = {}
    id_pedido_to_nodo = {} 
    
    for i, p in enumerate(puntos_ruteables):
        n = nodos_mapeados_ruteables[i]
        nodo_to_pedido_id[n] = p["id"]
        id_pedido_to_nodo[p["id"]] = n

    # 4. RECUPERAR VIPs ACTIVOS (Sin re-calcular azar)
    nodos_vip = []
    for p in puntos_ruteables:
        if p["rol_base"] == "VIP" and p["id"] != id_inicio and p["id"] != id_fin:
            if p["id"] in id_pedido_to_nodo:
                nodos_vip.append(id_pedido_to_nodo[p["id"]])
    
    nodos_vip = list(set(nodos_vip))
    set_vips_activos = set(nodos_vip)

    # 5. MATRICES DE COSTOS
    num = len(nodos_unicos)
    cost_matrix_time = np.full((num, num), np.inf)
    cost_matrix_barrio = np.full((num, num), np.inf)
    
    for i in range(num):
        cost_matrix_barrio[i][i] = 0
        for j in range(i + 1, num):
            u, v = nodos_unicos[i], nodos_unicos[j]
            try:
                t = nx.shortest_path_length(G, u, v, weight='travel_time')
                cost_matrix_time[i][j] = t; cost_matrix_time[j][i] = t
                cb = nx.shortest_path_length(G, u, v, weight='costo_agrupacion')
                cost_matrix_barrio[i][j] = cb; cost_matrix_barrio[j][i] = cb
            except: pass
    cost_matrix_barrio = np.nan_to_num(cost_matrix_barrio, posinf=999999999)
    
    # 6. CLUSTERING
    if num > 1:
        model = AgglomerativeClustering(n_clusters=None, metric='precomputed', linkage='complete', distance_threshold=RADIO_CLUSTER_METROS)
        model.fit(cost_matrix_barrio)
        labels = model.labels_
        n_clusters = model.n_clusters_
        zonas = [[] for _ in range(n_clusters)]
        for i, nodo in enumerate(nodos_unicos): zonas[labels[i]].append(nodo)
    else:
        zonas = [[nodos_unicos[0]]] if nodos_unicos else []
        n_clusters = 1

    # 7. RESPUESTA JSON
    response = {
        "paradas": [],
        "ruta_global": {"coords": [], "ids": [], "km": 0, "tiempo": ""},
        "rutas_clusters": [],
        "ruta_vip": {"coords": [], "km": 0, "tiempo": ""}
    }

    # A) Paradas
    for p in puntos_totales:
        tipo_final = "NORMAL"
        if p["id"] == id_inicio: tipo_final = "INICIO"
        elif p["id"] == id_fin: tipo_final = "FIN"
        elif p["rol_base"] == "VIP": tipo_final = "VIP"
        
        response["paradas"].append({
            "id": p["id"],
            "lat": p["lat"],
            "lon": p["lon"],
            "tipo": tipo_final,
            "estado": p["estado"]
        })

    # B) Ruta Global
    if len(nodos_unicos) > 1:
        ruta_g = optimizar_ruta_fluida(nodos_unicos, cost_matrix_time, nodo_to_idx, nodo_arranque_id, nodo_destino_id)
        coords_glob = []
        ids_glob = []
        for k in range(len(ruta_g)):
            node_id = ruta_g[k]
            p_id = nodo_to_pedido_id.get(node_id)
            if p_id: ids_glob.append(p_id)
            if k < len(ruta_g) - 1:
                try:
                    path = nx.shortest_path(G, ruta_g[k], ruta_g[k+1], weight='travel_time')
                    for nid in path: coords_glob.append([G.nodes[nid]['y'], G.nodes[nid]['x']])
                except: pass
        k_g, t_g = calcular_metricas(ruta_g)
        response["ruta_global"] = {"coords": coords_glob, "ids": ids_glob, "km": k_g, "tiempo": t_g}

    # C) Ruta VIP
    if len(nodos_vip) > 1:
        ini_v = nodo_arranque_id if nodo_arranque_id else None
        
        # Agregar inicio a la lista VIP temporalmente para el cálculo
        lista_optimizar = nodos_vip.copy()
        if ini_v and ini_v not in lista_optimizar:
            lista_optimizar.append(ini_v)
            
        fin_v = nodo_destino_id if (nodo_destino_id and nodo_destino_id in set_vips_activos) else None

        ruta_v = optimizar_ruta_fluida(lista_optimizar, cost_matrix_time, nodo_to_idx, ini_v, fin_v)
        coords_vip = []
        for k in range(len(ruta_v)-1):
            try:
                path = nx.shortest_path(G, ruta_v[k], ruta_v[k+1], weight='travel_time')
                for nid in path: coords_vip.append([G.nodes[nid]['y'], G.nodes[nid]['x']])
            except: pass
        k_v, t_v = calcular_metricas(ruta_v)
        response["ruta_vip"] = {"coords": coords_vip, "km": k_v, "tiempo": t_v}

    # D) Clusters
    for z_idx in range(n_clusters):
        puntos_zona = zonas[z_idx]
        if not puntos_zona: continue
        ini_z = nodo_arranque_id if (nodo_arranque_id and nodo_arranque_id in puntos_zona) else None
        fin_z = nodo_destino_id if (nodo_destino_id and nodo_destino_id in puntos_zona) else None
        
        ruta_int = optimizar_ruta_fluida(puntos_zona, cost_matrix_time, nodo_to_idx, ini_z, fin_z)
        coords = []
        for k in range(len(ruta_int)-1):
            try:
                path = nx.shortest_path(G, ruta_int[k], ruta_int[k+1], weight='travel_time')
                for nid in path: coords.append([G.nodes[nid]['y'], G.nodes[nid]['x']])
            except: pass
        kms, tiempo = calcular_metricas(ruta_int)
        if coords: 
            response["rutas_clusters"].append({"coords": coords, "km": kms, "tiempo": tiempo, "label": f"Zona {z_idx+1}"})

    return response
