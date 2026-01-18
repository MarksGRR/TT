import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt
import random
import numpy as np
from matplotlib.colors import hsv_to_rgb
from scipy.spatial import ConvexHull

# --- CONFIGURACIÓN ---
LAT_CENTRO = 19.4841
LON_CENTRO = -99.0336
CANTIDAD_PUNTOS = 31 # 31 Paquetes

# CLUSTERING COMPACTO
TAMANO_PROMEDIO_CLUSTER = 5
MIN_PAQUETES = 2
MAX_PAQUETES = 6
UMBRAL_COMPACIDAD_SEGUNDOS = 240 

# REGLAS
VEL_CALLE = 20  # km/h
VEL_AVENIDA = 50 # km/h
TIEMPO_MIN_SERVICIO = 2
TIEMPO_MAX_SERVICIO = 5

print(f"--- SISTEMA LOGÍSTICO V36: VISUALIZACIÓN SIMULTÁNEA ---")

# 1. MAPA
print("1. Procesando mapa...")
G_gps = ox.graph_from_point((LAT_CENTRO, LON_CENTRO), dist=2000, network_type='drive')
largest_cc = max(nx.strongly_connected_components(G_gps), key=len)
G_gps = G_gps.subgraph(largest_cc).copy()
G = ox.project_graph(G_gps)

# Costos
lista_avs = ['primary', 'secondary', 'trunk', 'primary_link', 'secondary_link']
speed_calle_ms = VEL_CALLE / 3.6
speed_av_ms = VEL_AVENIDA / 3.6

for u, v, k, data in G.edges(keys=True, data=True):
    tipo = data.get('highway', 'residential')
    if isinstance(tipo, list): tipo = tipo[0]
    velocidad = speed_av_ms if tipo in lista_avs else speed_calle_ms
    data['travel_time'] = data.get('length', 10) / velocidad
    data['color_visual'] = '#FFD700' if tipo in lista_avs else '#333333'

def dibujar_base_oscura(ax):
    ax.set_facecolor('black')
    ec = [d['color_visual'] for u,v,k,d in G.edges(keys=True, data=True)]
    ox.plot_graph(G, ax=ax, node_size=0, edge_color=ec, edge_linewidth=0.5, bgcolor='black', show=False, close=False)

# 2. PUNTOS
todos = list(G.nodes())
nodos_clientes = random.sample(todos, CANTIDAD_PUNTOS)
mapa_pedidos = {nodo: i + 1 for i, nodo in enumerate(nodos_clientes)}
nodo_to_idx = {nodo: i for i, nodo in enumerate(nodos_clientes)}
mapa_tiempos = {n: random.randint(TIEMPO_MIN_SERVICIO, TIEMPO_MAX_SERVICIO) for n in nodos_clientes}

porcentaje_azar = random.uniform(0.10, 0.35)
num_prioritarios = int(CANTIDAD_PUNTOS * porcentaje_azar)
if num_prioritarios < 1: num_prioritarios = 1
indices_prioritarios = set(random.sample(range(CANTIDAD_PUNTOS), num_prioritarios))
ids_prioritarios = set([nodos_clientes[i] for i in indices_prioritarios])

# 3. MATRIZ DE TIEMPOS
print("2. Calculando matriz de tiempos...")
num = len(nodos_clientes)
cost_matrix = np.full((num, num), np.inf)
for i in range(num):
    for j in range(i + 1, num):
        u, v = nodos_clientes[i], nodos_clientes[j]
        try:
            t = nx.shortest_path_length(G, u, v, weight='travel_time')
            cost_matrix[i][j] = t; cost_matrix[j][i] = t
        except: pass

# ==============================================================================
# HERRAMIENTAS
# ==============================================================================
def format_time(mins):
    return f"{int(mins)}m" if mins < 60 else f"{int(mins//60)}:{int(mins%60):02d}h"

def get_metrics(ruta):
    if not ruta: return 0, 0
    d_km = 0; t_min = 0
    for i in range(len(ruta) - 1):
        try:
            path = nx.shortest_path(G, ruta[i], ruta[i+1], weight='travel_time')
            for u, v in zip(path[:-1], path[1:]):
                ed = min(G[u][v].values(), key=lambda x: x['travel_time'])
                d_km += ed['length']; t_min += ed['travel_time']/60.0
            t_min += mapa_tiempos[ruta[i+1]]
        except: pass
    t_min += mapa_tiempos[ruta[0]]
    return d_km/1000.0, t_min

# ==============================================================================
# ALGORITMO: ENCADENAMIENTO DE VECINOS + 2-OPT
# ==============================================================================
def optimizar_ruta_fluida(lista_nodos):
    if len(lista_nodos) <= 1: return lista_nodos
    
    # Greedy Chain (Oeste -> Este)
    start_node = min(lista_nodos, key=lambda n: G.nodes[n]['x'])
    ruta_construida = [start_node]
    pendientes = set(lista_nodos)
    pendientes.remove(start_node)
    
    curr = start_node
    while pendientes:
        curr_idx = nodo_to_idx[curr]
        best_next = None
        min_dist = float('inf')
        
        for cand in pendientes:
            cand_idx = nodo_to_idx[cand]
            d = cost_matrix[curr_idx][cand_idx]
            if d < min_dist:
                min_dist = d
                best_next = cand
        
        if best_next:
            ruta_construida.append(best_next)
            pendientes.remove(best_next)
            curr = best_next
        else:
            nxt = list(pendientes)[0]
            ruta_construida.append(nxt)
            pendientes.remove(nxt)
            curr = nxt

    # 2-Opt
    ruta = ruta_construida
    mejoro = True
    while mejoro:
        mejoro = False
        for i in range(1, len(ruta) - 2):
            for j in range(i + 1, len(ruta)):
                if j - i == 1: continue
                ia, ib = nodo_to_idx[ruta[i-1]], nodo_to_idx[ruta[i]]
                ic, id_ = nodo_to_idx[ruta[j-1]], nodo_to_idx[ruta[j]]
                cur = cost_matrix[ia][ib] + cost_matrix[ic][id_]
                new = cost_matrix[ia][ic] + cost_matrix[ib][id_]
                if new < cur:
                    ruta[i:j] = ruta[i:j][::-1]; mejoro = True
    return ruta

# ==============================================================================
# CÁLCULOS
# ==============================================================================
print("3. Generando rutas fluidas...")

# A) RUTAS
ruta_global = optimizar_ruta_fluida(nodos_clientes)
km_glob, min_glob = get_metrics(ruta_global)

vips = list(ids_prioritarios)
if nodos_clientes[0] not in vips: vips.insert(0, nodos_clientes[0])
ruta_vip = optimizar_ruta_fluida(vips)
km_vip, min_vip = get_metrics(ruta_vip)

# C) CLUSTERS
pendientes_indices = set(range(num))
clusters_indices = []

while pendientes_indices:
    seed = min(pendientes_indices, key=lambda i: G.nodes[nodos_clientes[i]]['x'])
    cluster_actual = [seed]
    pendientes_indices.remove(seed)
    
    while len(cluster_actual) < MAX_PAQUETES and pendientes_indices:
        mejor_candidato = None
        menor_costo = float('inf')
        for cand in pendientes_indices:
            costo = min([cost_matrix[cand][membro] for membro in cluster_actual])
            if costo < menor_costo: menor_costo = costo; mejor_candidato = cand
        
        if mejor_candidato is not None:
            if len(cluster_actual) < MIN_PAQUETES or menor_costo <= UMBRAL_COMPACIDAD_SEGUNDOS:
                cluster_actual.append(mejor_candidato); pendientes_indices.remove(mejor_candidato)
            else: break
        else: break   
    clusters_indices.append(cluster_actual)

zonas_nodos = [[nodos_clientes[i] for i in idxs] for idxs in clusters_indices]

# ==============================================================================
# VISUALIZACIÓN (PREPARACIÓN DE VENTANAS)
# ==============================================================================
print("4. Generando ventanas gráficas...")

# --- MAPA 1: DEMANDA ---
fig1, ax1 = plt.subplots(figsize=(8, 8), facecolor='black')
fig1.canvas.manager.set_window_title('Mapa 1: Demanda') # Título de la ventana
dibujar_base_oscura(ax1)
for n in nodos_clientes:
    x, y = G.nodes[n]['x'], G.nodes[n]['y']
    pid = str(mapa_pedidos[n])
    if n in ids_prioritarios:
        ax1.scatter(x, y, c='#FFD700', s=200, marker='s', zorder=11, edgecolors='white')
        ax1.text(x, y, pid, color='black', fontweight='bold', fontsize=8, ha='center', va='center', zorder=12)
    else:
        ax1.scatter(x, y, c='#FF4444', s=120, zorder=10, edgecolors='white')
        ax1.text(x, y, pid, color='white', fontweight='bold', fontsize=7, ha='center', va='center', zorder=12)
ax1.set_title(f"ESCENARIO 1: Demanda ({len(ids_prioritarios)} Prioritarios)", color='white')
# ¡OJO! NO HAY plt.show() AQUÍ

# --- MAPA 2: GLOBAL ---
fig2, ax2 = plt.subplots(figsize=(8, 8), facecolor='black')
fig2.canvas.manager.set_window_title('Mapa 2: Ruta Global')
dibujar_base_oscura(ax2)
for i in range(len(ruta_global)-1):
    try:
        p = nx.shortest_path(G, ruta_global[i], ruta_global[i+1], weight='travel_time')
        xp=[G.nodes[n]['x'] for n in p]; yp=[G.nodes[n]['y'] for n in p]
        ax2.plot(xp, yp, c='cyan', lw=3, alpha=0.8, zorder=5)
        if len(p)>=2:
            m=len(p)//2
            ax2.annotate("", xy=(G.nodes[p[m+1]]['x'], G.nodes[p[m+1]]['y']), xytext=(G.nodes[p[m]]['x'], G.nodes[p[m]]['y']), arrowprops=dict(arrowstyle="-|>", color='white', lw=1.5, mutation_scale=15), zorder=6)
    except: pass

s, e = ruta_global[0], ruta_global[-1]
ax2.annotate(f"INICIO\n#{mapa_pedidos[s]}", xy=(G.nodes[s]['x'], G.nodes[s]['y']), xytext=(-40,40), textcoords='offset points', color='#32CD32', fontweight='bold', arrowprops=dict(arrowstyle="->", color='#32CD32', lw=2), bbox=dict(boxstyle="round", fc="black", ec="#32CD32"), zorder=30)
ax2.annotate(f"FIN\n#{mapa_pedidos[e]}", xy=(G.nodes[e]['x'], G.nodes[e]['y']), xytext=(40,-40), textcoords='offset points', color='#FF4444', fontweight='bold', arrowprops=dict(arrowstyle="->", color='#FF4444', lw=2), bbox=dict(boxstyle="round", fc="black", ec="#FF4444"), zorder=30)

for n in ruta_global:
    x,y = G.nodes[n]['x'], G.nodes[n]['y']
    c='#FFD700' if n in ids_prioritarios else '#FF4444'
    ax2.scatter(x,y,c=c,s=150, zorder=10, edgecolors='white')
    ax2.text(x,y,str(mapa_pedidos[n]), color='black' if c=='#FFD700' else 'white', fontweight='bold', fontsize=7, ha='center', va='center', zorder=11)
ax2.set_title(f"ESCENARIO 2: Ruta Fluida ({km_glob:.1f}km | {format_time(min_glob)})", color='white')
# ¡OJO! NO HAY plt.show() AQUÍ

# --- MAPA 3: ZONAS COMPACTAS ---
fig3, ax3 = plt.subplots(figsize=(8, 8), facecolor='black')
fig3.canvas.manager.set_window_title('Mapa 3: Zonas')
dibujar_base_oscura(ax3)
cols = [hsv_to_rgb([(i/len(zonas_nodos)), 0.8, 1]) for i in range(len(zonas_nodos))]

for i, pts in enumerate(zonas_nodos):
    if not pts: continue
    col = cols[i]
    ruta_int = optimizar_ruta_fluida(pts)
    dk, dm = get_metrics(ruta_int)
    px = [G.nodes[n]['x'] for n in pts]; py = [G.nodes[n]['y'] for n in pts]
    
    if len(pts)>=3:
        try:
            hull = ConvexHull(np.column_stack((px, py)))
            ax3.fill(np.array(px)[hull.vertices], np.array(py)[hull.vertices], c=col, alpha=0.3, zorder=2)
        except: pass
    elif len(pts) == 2:
        ax3.plot(px, py, c=col, lw=10, alpha=0.3, zorder=2)
    
    for j in range(len(ruta_int)-1):
        try:
            p = nx.shortest_path(G, ruta_int[j], ruta_int[j+1], weight='travel_time')
            xp=[G.nodes[n]['x'] for n in p]; yp=[G.nodes[n]['y'] for n in p]
            ax3.plot(xp, yp, c=col, lw=2, alpha=0.9, zorder=5)
        except: pass
        
    for n in pts:
        x, y = G.nodes[n]['x'], G.nodes[n]['y']
        ax3.scatter(x, y, c=[col], s=130, zorder=10, edgecolors='white')
        ax3.text(x, y, str(mapa_pedidos[n]), color='black', fontweight='bold', fontsize=7, ha='center', va='center', zorder=11)

    cx, cy = np.mean(px), np.mean(py)
    ax3.text(cx, cy, f"C{i+1}\n({len(pts)}p)\n{format_time(dm)}", color='white', fontsize=7, fontweight='bold', ha='center', bbox=dict(facecolor=col, edgecolor='white', alpha=0.8), zorder=20)
ax3.set_title("ESCENARIO 3: Zonas Densas (Min 2 - Max 6)", color='white')
# ¡OJO! NO HAY plt.show() AQUÍ

# --- MAPA 4: COMPARATIVA ---
fig4, ax4 = plt.subplots(figsize=(8, 8), facecolor='black')
fig4.canvas.manager.set_window_title('Mapa 4: Comparativa')
dibujar_base_oscura(ax4)

# Fondo
for i in range(len(ruta_global)-1):
    try:
        p = nx.shortest_path(G, ruta_global[i], ruta_global[i+1], weight='travel_time')
        ax4.plot([G.nodes[n]['x'] for n in p], [G.nodes[n]['y'] for n in p], c='#555555', lw=4, alpha=0.5, zorder=4)
    except: pass

# Frente
for i in range(len(ruta_vip)-1):
    try:
        p = nx.shortest_path(G, ruta_vip[i], ruta_vip[i+1], weight='travel_time')
        xp=[G.nodes[n]['x'] for n in p]; yp=[G.nodes[n]['y'] for n in p]
        ax4.plot(xp, yp, c='#FFD700', lw=3, alpha=1.0, zorder=6)
        if len(p)>=2:
            m=len(p)//2
            ax4.annotate("", xy=(G.nodes[p[m+1]]['x'], G.nodes[p[m+1]]['y']), xytext=(G.nodes[p[m]]['x'], G.nodes[p[m]]['y']), arrowprops=dict(arrowstyle="-|>", color='white', lw=1, mutation_scale=15), zorder=7)
    except: pass

# Etiquetas
vs, ve = ruta_vip[0], ruta_vip[-1]
ax4.annotate(f"INICIO VIP\n#{mapa_pedidos[vs]}", xy=(G.nodes[vs]['x'], G.nodes[vs]['y']), xytext=(40,40), textcoords='offset points', color='#FFD700', fontweight='bold', arrowprops=dict(arrowstyle="->", color='#FFD700', lw=2), bbox=dict(boxstyle="round", fc="black", ec="#FFD700"), zorder=35)
ax4.annotate(f"FIN VIP\n#{mapa_pedidos[ve]}", xy=(G.nodes[ve]['x'], G.nodes[ve]['y']), xytext=(-40,-40), textcoords='offset points', color='#FFA500', fontweight='bold', arrowprops=dict(arrowstyle="->", color='#FFA500', lw=2), bbox=dict(boxstyle="round", fc="black", ec="#FFA500"), zorder=35)

gs, ge = ruta_global[0], ruta_global[-1]
ax4.annotate(f"INICIO GLOB\n#{mapa_pedidos[gs]}", xy=(G.nodes[gs]['x'], G.nodes[gs]['y']), xytext=(-40,40), textcoords='offset points', color='#32CD32', fontweight='bold', arrowprops=dict(arrowstyle="->", color='#32CD32', lw=2), bbox=dict(boxstyle="round", fc="black", ec="#32CD32"), zorder=35)
ax4.annotate(f"FIN GLOB\n#{mapa_pedidos[ge]}", xy=(G.nodes[ge]['x'], G.nodes[ge]['y']), xytext=(40,-40), textcoords='offset points', color='#FF4444', fontweight='bold', arrowprops=dict(arrowstyle="->", color='#FF4444', lw=2), bbox=dict(boxstyle="round", fc="black", ec="#FF4444"), zorder=35)

for n in ruta_global:
    x, y = G.nodes[n]['x'], G.nodes[n]['y']
    pid = str(mapa_pedidos[n])
    if n in ids_prioritarios:
        ax4.scatter(x, y, c='#FFD700', s=250, marker='D', zorder=15, edgecolors='white')
        ax4.text(x, y, pid, color='black', fontweight='bold', fontsize=9, ha='center', va='center', zorder=16)
    else:
        ax4.scatter(x, y, c='#FF4444', s=80, zorder=10, edgecolors='gray', alpha=0.5)

ax4.set_title(f"VIP ({km_vip:.1f}km | {format_time(min_vip)}) vs Global ({km_glob:.1f}km | {format_time(min_glob)})", color='white', fontsize=11)

print(">>> Abriendo las 4 ventanas al mismo tiempo. Cierralas todas para terminar.")
# FINALMENTE, UN SOLO SHOW() AL FINAL
plt.show()