import osmnx as ox
import networkx as nx
import matplotlib.pyplot as plt

# --- CONFIGURACIÓN ---
# En lugar de buscar "Ciudad Nezahualcóyotl" por nombre (que falla),
# usamos las coordenadas exactas del centro de Neza.
centro_neza = (19.4005, -99.0248) 

print("1. Descargando el mapa de Nezahualcóyotl (Radio de 2km)...")
print("   (Esto puede tardar unos segundos dependiendo de tu internet)")

# --- DESCARGAR MAPA ---
# dist=2000 significa que bajará 2000 metros (2km) a la redonda desde el punto.
# network_type='drive' baja solo calles para autos.
G = ox.graph_from_point(centro_neza, dist=2000, network_type='drive')

print("2. Mapa descargado con éxito.")

# --- SELECCIONAR PUNTOS DE PRUEBA ---
# Obtenemos la lista de todos los nodos (intersecciones) que se descargaron
nodos_lista = list(G.nodes())

# Elegimos dos puntos arbitrarios para probar el algoritmo
# (El nodo 0 y el nodo 400 de la lista)
origen_nodo = nodos_lista[0]
destino_nodo = nodos_lista[400] 

# --- APLICAR DIJKSTRA ---
print("3. Calculando la ruta más corta con Dijkstra...")
ruta = nx.shortest_path(G, source=origen_nodo, target=destino_nodo, weight='length')

# Calcular la distancia total en metros
distancia_metros = nx.shortest_path_length(G, source=origen_nodo, target=destino_nodo, weight='length')
print(f"   -> ¡Ruta encontrada! Distancia total: {distancia_metros:.2f} metros.")

# --- VISUALIZAR ---
print("4. Abriendo ventana del mapa...")
# Esto abrirá una ventana emergente con el mapa negro y la ruta en rojo/blanco
fig, ax = ox.plot_graph_route(G, ruta, route_linewidth=6, node_size=0, bgcolor='k')