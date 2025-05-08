import graphviz
from typing import Dict, Any, List, Optional


class FlexibleBPMNGenerator:
    def __init__(self):
        self.node_counter = 0
        self.existing_nodes = set()
        self.node_map = {}  # Mapping of node names to IDs
        self.processed_tasks = set()  # Set of processed task names (strings)

    def get_unique_node_id(self, name: str) -> str:
        """Generates a unique ID for each node."""
        base_id = "".join(c for c in str(name) if c.isalnum())
        
        if base_id not in self.existing_nodes:
            self.existing_nodes.add(base_id)
            self.node_map[name] = base_id
            return base_id
        
        self.node_counter += 1
        new_id = f"{base_id}_{self.node_counter}"
        self.existing_nodes.add(new_id)
        self.node_map[name] = new_id
        return new_id

    def create_legend(self, dot: graphviz.Digraph) -> None:
        """Creates a horizontal legend showing different node types and their meanings."""
        with dot.subgraph(name='cluster_legend') as legend:
            legend.attr(label='Leyenda', style='rounded', color='gray', fontsize='15')
            # Configuración para forzar disposición horizontal
            legend.graph_attr.update(rankdir='TB')  # Cambiado a TB (top to bottom) para mejor alineación vertical
            
            # Definir los tipos de nodos para la leyenda
            node_types = [
                ('task', 'Tarea', 'box', 'rounded,filled', '#E6F3FF'),
                ('xor', 'XOR', 'diamond', 'filled', '#FFFACD'),
                ('and', 'AND', 'diamond', 'filled', '#98FB98'),
                ('loop', 'Bucle', 'diamond', 'filled', '#DDA0DD'),
                ('start', 'Inicio', 'circle', 'filled', '#90EE90'),
                ('end', 'Fin', 'doublecircle', 'filled', '#FFB6C1'),
                ('condition', 'Condición', 'box', 'filled,dashed', '#E0E0E0')
            ]
            
            # Crear una fila invisible para alinear los iconos
            for i, (node_type, _, _, _, _) in enumerate(node_types):
                with legend.subgraph(name=f'cluster_{node_type}') as cluster:
                    cluster.attr(style='invis')
                    
                    # Nodo del símbolo
                    icon_id = f"icon_{node_type}"
                    
                    # Establecer el texto y parámetros según el tipo
                    if node_type == 'xor':
                        node_text = 'X'
                    elif node_type == 'and':
                        node_text = '+'
                    else:
                        node_text = ''
                        
                    # Ajustar altura/anchura según el tipo
                    if node_type == 'diamond':
                        height, width = '0.5', '0.5'
                    elif node_type == 'circle':
                        height, width = '0.4', '0.4'
                    elif node_type == 'doublecircle':
                        height, width = '0.5', '0.5'
                    else:
                        height, width = '0.4', '0.6'
                        
                    # Crear nodo de icono
                    cluster.node(icon_id, node_text,
                            shape=node_types[i][2],  # shape
                            style=node_types[i][3],  # style
                            fillcolor=node_types[i][4],  # fillcolor
                            penwidth='1.5',
                            height=height,
                            width=width,
                            margin='0.1,0.1')
                    
                    # Crear nodo de etiqueta
                    label_id = f"label_{node_type}"
                    cluster.node(label_id, node_types[i][1], shape='plaintext', fontsize='12')
                    
                    # Conectar el icono con su etiqueta (vertical)
                    cluster.edge(icon_id, label_id, style='invis')
            
            # Conectar los clusters horizontalmente
            for i in range(len(node_types) - 1):
                curr_icon = f"icon_{node_types[i][0]}"
                next_icon = f"icon_{node_types[i+1][0]}"
                legend.edge(curr_icon, next_icon, style='invis', constraint='false')
            
            # Forzar alineación horizontal de los iconos
            with legend.subgraph() as row:
                row.attr(rank='same')
                for node_type, _, _, _, _ in node_types:
                    row.node(f"icon_{node_type}")

    def create_bpmn_diagram(self, data: Dict[str, Any]) -> graphviz.Digraph:
        """Creates a BPMN diagram with a fully connected flow."""
        dot = graphviz.Digraph(comment='BPMN Diagram')
        dot.attr(rankdir='TB')  # Diagrama global en dirección vertical
        dot.attr('node', fontname='Helvetica')
        dot.attr('edge', fontname='Helvetica')
        dot.attr(nodesep='0.8', ranksep='1.0')
        dot.attr(splines='ortho')
        
        # Crear el diagrama principal
        with dot.subgraph(name='cluster_main') as main:
            main.attr(style='invis')
            # Procesar el flujo principal
            if 'flow' in data:
                self.process_flow(main, data['flow'])
        
        # Crear un nodo espaciador
        dot.node('spacer', '', shape='none', height='0.5', style='invis')
        
        # Conectar el último nodo del flujo principal con el espaciador
        if 'flow' in data and len(data['flow']) > 0:
            last_elem = data['flow'][-1]
            if 'name' in last_elem and last_elem.get('type') == 'evento':
                last_node_name = last_elem['name']
                last_node_id = self.node_map.get(last_node_name)
                if last_node_id:
                    dot.edge(last_node_id, 'spacer', style='invis')
        
        # Crear la leyenda en un subgrafo separado
        with dot.subgraph(name='cluster_legend') as legend_section:
            legend_section.attr(rank='sink')  # Forzar al fondo del diagrama
            self.create_legend(legend_section)
        
        return dot

    def process_evento(self, dot: graphviz.Digraph, evento: Dict[str, Any]) -> str:
        """Procesa un evento (inicio o fin) dentro del flujo."""
        event_name = evento.get('name', '')
        node_id = self.get_unique_node_id(f"evento_{event_name}")
        
        if event_name.lower() == 'inicio':
            shape = 'circle'
            size = '0.5'
            fillcolor = '#90EE90'  # Verde claro
            dot.node(node_id, event_name,
                    shape=shape,
                    style='filled',
                    fillcolor=fillcolor,
                    width=size,
                    height=size,
                    penwidth='2.0')
            
        elif event_name.lower() == 'fin':
            shape = 'doublecircle'
            size = '0.6'
            fillcolor = '#FFB6C1'  # Rosa claro
            dot.node(node_id, event_name,
                    shape=shape,
                    style='filled',
                    fillcolor=fillcolor,
                    width=size,
                    height=size,
                    penwidth='2.0')
            
            # Añadir etiqueta para el motivo de fin si existe
            if 'condicion' in evento:
                label_id = self.get_unique_node_id(f"fin_label_{event_name}")
                condition_text = evento.get('condicion', '')
                dot.node(label_id, condition_text,
                        shape='box',
                        style='filled,dashed',
                        fillcolor='#E0E0E0',
                        fontsize='10',
                        fontcolor='#555555')
                
                # Conectamos la etiqueta con el evento de fin
                dot.edge(node_id, label_id, style='dashed', arrowhead='none')
        else:
            shape = 'circle'
            size = '0.5'
            fillcolor = '#E0E0E0'  # Gris para otros eventos
            dot.node(node_id, event_name,
                    shape=shape,
                    style='filled',
                    fillcolor=fillcolor,
                    width=size,
                    height=size,
                    penwidth='2.0')
                
        return node_id

    def create_condition_node(self, dot: graphviz.Digraph, condition_text: str, name_prefix: str) -> str:
        """Crea un nodo de condición."""
        node_id = self.get_unique_node_id(f"condition_{name_prefix}")
        
        dot.node(node_id, condition_text,
                shape='box',
                style='filled,dashed',
                fillcolor='#E0E0E0',  # Gris para condiciones
                fontsize='9',
                fontcolor='#555555')
                
        return node_id

    def process_flow(self, dot: graphviz.Digraph, flow: List[Dict[str, Any]]) -> None:
        """Processes the sequential flow array and connects all elements."""
        previous_node_id = None
        
        # Primera pasada: crear todos los nodos
        node_ids = []
        for element in flow:
            element_type = element.get('type')
            
            if not element_type:
                print(f"Warning: Skipping element without type: {element}")
                continue
            
            try:
                if element_type == 'evento':
                    node_id = self.process_evento(dot, element)
                    node_ids.append(node_id)
                    
                elif element_type == 'tarea':
                    node_id = self.process_task(dot, element)
                    node_ids.append(node_id)
                    
                elif element_type == 'pasarela':
                    # Procesamos la pasarela y obtenemos el nodo de inicio y el nodo de unión
                    gateway_id, merge_id = self.process_gateway(dot, element)
                    
                    # Guardamos directamente el merge_id como punto final
                    # Eliminamos el nodo neutro
                    node_ids.append((gateway_id, merge_id))
                    
                elif element_type == 'bucle':
                    # Procesamos el bucle y obtenemos el nodo de inicio y el nodo de salida
                    loop_start_id, loop_end_id = self.process_loop(dot, element)
                    
                    # Guardamos directamente el nodo de fin de bucle
                    node_ids.append((loop_start_id, loop_end_id))
                
                else:
                    print(f"Warning: Unrecognized element type: {element_type}")
                    node_ids.append(None)  # Placeholder para mantener la alineación
                    
            except KeyError as e:
                print(f"Error processing element: Missing key {e}")
                node_ids.append(None)
            except Exception as e:
                print(f"Unexpected error processing flow element: {e}")
                node_ids.append(None)
        
        # Segunda pasada: conectar todos los nodos en secuencia
        for i in range(len(node_ids) - 1):
            current = node_ids[i]
            next_node = node_ids[i + 1]
            
            if current is None or next_node is None:
                continue
                
            # Si el nodo actual es una tupla (inicio/fin de pasarela o bucle)
            if isinstance(current, tuple):
                from_node = current[1]  # Usar el nodo de salida (merge o fin de bucle)
            else:
                from_node = current
                
            # Si el siguiente nodo es una tupla (inicio/fin de pasarela o bucle)
            if isinstance(next_node, tuple):
                to_node = next_node[0]  # Usar el nodo de entrada
            else:
                to_node = next_node
                
            dot.edge(from_node, to_node, penwidth='1.5')

    def process_task(self, dot: graphviz.Digraph, task: Dict[str, Any]) -> str:
        """Processes a single task."""
        task_name = str(task.get('name', ''))
        task_description = task.get('description', task_name)
        
        # Verificar si ya procesamos esta tarea
        if task_name in self.processed_tasks:
            return self.node_map[task_name]

        task_id = self.get_unique_node_id(task_name)
        self.processed_tasks.add(task_name)
        
        dot.node(task_id, task_description,
                shape='box',
                style='rounded,filled',
                fillcolor='#E6F3FF',
                penwidth='2.0',
                height='0.6',
                margin='0.3,0.2')
        
        return task_id

    def process_gateway(self, dot: graphviz.Digraph, gateway: Dict[str, Any]) -> tuple:
        """Processes a gateway and returns both input and output node IDs."""
        gateway_id = self.get_unique_node_id(f"gateway_{gateway['name']}")
        merge_id = self.get_unique_node_id(f"merge_{gateway['name']}")

        # Determinar el tipo de pasarela y sus atributos visuales
        gateway_type = gateway.get('type_pasarela', 'XOR')
        
        if gateway_type == 'XOR':
            label = 'X'
            fillcolor = '#FFFACD'  # Amarillo claro para XOR
        else:  # AND
            label = '+'
            fillcolor = '#98FB98'  # Verde claro para AND

        # Nodo de decisión
        dot.node(gateway_id, label,
                shape='diamond',
                style='filled',
                fillcolor=fillcolor,
                penwidth='2.0',
                height='0.7',
                width='0.7')
        
        # Nodo de merge con el mismo estilo que el gateway
        dot.node(merge_id, label,
                shape='diamond',
                style='filled',
                fillcolor=fillcolor,
                penwidth='2.0',
                width='0.5',
                height='0.5')

        # Procesar cada rama
        for i, branch in enumerate(gateway.get('ramas', [])):
            branch_name = branch.get('name', f'Rama {i+1}')
            branch_condition = branch.get('condición', '')
            
            branch_start = gateway_id
            
            # Solo para pasarelas XOR se añade el nodo de condición
            if gateway_type == 'XOR' and branch_condition != '':
                # Creamos el nodo de condición para esta rama
                condition_id = self.create_condition_node(
                    dot, 
                    branch_condition,
                    f"branch_{gateway['name']}_{i}"
                )
                
                # Conectar el gateway al nodo de condición
                dot.edge(branch_start, condition_id, penwidth='1.5')
                
                # La condición es ahora el punto de inicio para las tareas
                branch_start = condition_id
            
            for task_name in branch.get('tareas', []):
                # Asegurarnos de que task_name sea string
                task_name = str(task_name)
                
                # Verificar si la tarea ya existe
                if task_name in self.processed_tasks:
                    task_id = self.node_map[task_name]
                else:
                    task_id = self.get_unique_node_id(task_name)
                    dot.node(task_id, task_name,
                            shape='box',
                            style='rounded,filled',
                            fillcolor='#E6F3FF',
                            penwidth='2.0',
                            height='0.6',
                            margin='0.3,0.2')
                    self.processed_tasks.add(task_name)
                
                # Conectar desde la condición o la tarea anterior
                dot.edge(branch_start, task_id, penwidth='1.5')
                branch_start = task_id
            
            # Conectar la última tarea al merge
            dot.edge(branch_start, merge_id, penwidth='1.5')

        return gateway_id, merge_id

    def process_loop(self, dot: graphviz.Digraph, loop: Dict[str, Any]) -> tuple:
        """Processes a loop structure and returns both input and output node IDs."""
        # Creamos nodos para inicio y fin del bucle
        loop_start_id = self.get_unique_node_id(f"loop_start_{loop['name']}")
        loop_end_id = self.get_unique_node_id(f"loop_end_{loop['name']}")

        # Nodo de inicio del bucle
        dot.node(loop_start_id, "",
                shape='diamond',
                style='filled',
                fillcolor='#DDA0DD',
                penwidth='2.0',
                height='0.7',
                width='0.7')
        
        # Nodo de fin del bucle (con el mismo estilo)
        dot.node(loop_end_id, "",
                shape='diamond',
                style='filled',
                fillcolor='#DDA0DD',
                penwidth='2.0',
                height='0.7',
                width='0.7')

        # Procesar las tareas del bucle
        last_task_id = loop_start_id
        for task_name in loop.get('tareas', []):
            task_name = str(task_name)
            
            # Verificar si la tarea ya existe
            if task_name in self.processed_tasks:
                task_id = self.node_map[task_name]
            else:
                task_id = self.get_unique_node_id(task_name)
                dot.node(task_id, task_name,
                        shape='box',
                        style='rounded,filled',
                        fillcolor='#E6F3FF',
                        penwidth='2.0',
                        height='0.6',
                        margin='0.3,0.2')
                self.processed_tasks.add(task_name)
            
            dot.edge(last_task_id, task_id, penwidth='1.5')
            last_task_id = task_id

        # Crear nodo de condición de cierre del bucle
        condition_text = loop.get('condición', '')
        loop_condition_id = self.create_condition_node(
            dot, 
            condition_text,
            f"loop_cond_{loop['name']}"
        )
        
        # Conectar la última tarea con el nodo de condición
        dot.edge(last_task_id, loop_condition_id, penwidth='1.5')
        
        # Conectar el nodo de condición de vuelta al nodo de inicio del bucle (sin etiqueta)
        dot.edge(loop_condition_id, loop_start_id, penwidth='1.5', constraint='false')
        
        # Conectar el nodo de condición al nodo de fin del bucle (sin etiqueta)
        dot.edge(loop_condition_id, loop_end_id, penwidth='1.5')

        return loop_start_id, loop_end_id


def create_and_save_bpmn(json_data: Dict[str, Any], output_filename: str) -> None:
    """Creates and saves a BPMN diagram from JSON data."""
    generator = FlexibleBPMNGenerator()
    diagram = generator.create_bpmn_diagram(json_data)
    
    diagram.render(output_filename, format='png', cleanup=True)
    diagram.render(output_filename, format='pdf', cleanup=True)
    diagram.render(output_filename, format='svg', cleanup=True)