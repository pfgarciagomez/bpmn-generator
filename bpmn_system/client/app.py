# app.py
import streamlit as st
import requests
from bpmn_generator import FlexibleBPMNGenerator
import json
import tempfile
import os

# Configuración de la página
st.set_page_config(
    page_title="Generador de Diagramas BPMN",
    layout="wide"
)

# Configuración del servidor
SERVER_HOST = "localhost"  # o la IP del servidor si es necesario
SERVER_PORT = 5000
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
JSON_PATH = "/home/fgarcia/bpmn_system/client/process.json"

# Título y descripción
st.title("Generador de Diagramas BPMN")
st.markdown("""
Esta aplicación te permite generar diagramas BPMN a partir de descripciones textuales.
Simplemente ingresa una descripción del proceso y el sistema generará automáticamente el diagrama correspondiente.
""")

# Área de entrada de texto
user_prompt = st.text_area(
    "Describe el proceso que deseas modelar:",
    height=150,
    placeholder="Ejemplo: Quiero modelar el proceso de contratación de un nuevo empleado..."
)

# Botón para generar el diagrama
if st.button("Generar Diagrama BPMN"):
    if user_prompt:
        with st.spinner("Generando diagrama..."):
            try:
                # Llamada al servidor para generar el JSON
                response = requests.post(
                    f"{SERVER_URL}/generate_json",
                    json={"prompt": user_prompt},
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    # Leer el JSON del archivo guardado
                    try:
                        with open(JSON_PATH, 'r', encoding='utf-8') as f:
                            process_json = json.load(f)
                        
                        # Mostrar el JSON generado (colapsado por defecto)
                        with st.expander("Ver JSON generado"):
                            st.json(process_json)
                        
                        # Generar el diagrama BPMN
                        generator = FlexibleBPMNGenerator()
                        
                        # Crear un directorio temporal para los archivos generados
                        with tempfile.TemporaryDirectory() as temp_dir:
                            output_path = os.path.join(temp_dir, "bpmn_diagram")
                            diagram = generator.create_bpmn_diagram(process_json)
                            
                            # Guardar el diagrama en diferentes formatos
                            diagram.render(output_path, format='png', cleanup=True)
                            diagram.render(output_path, format='pdf', cleanup=True)
                            
                            # Mostrar el diagrama
                            st.image(f"{output_path}.png")
                            
                            # Botones de descarga
                            col1, col2 = st.columns(2)
                            with col1:
                                with open(f"{output_path}.png", "rb") as file:
                                    st.download_button(
                                        label="Descargar PNG",
                                        data=file,
                                        file_name="diagrama_bpmn.png",
                                        mime="image/png"
                                    )
                            with col2:
                                with open(f"{output_path}.pdf", "rb") as file:
                                    st.download_button(
                                        label="Descargar PDF",
                                        data=file,
                                        file_name="diagrama_bpmn.pdf",
                                        mime="application/pdf"
                                    )
                    except Exception as e:
                        st.error(f"Error al leer el archivo JSON: {str(e)}")
                else:
                    st.error(f"Error al generar el diagrama. Respuesta del servidor: {response.text}")
            
            except Exception as e:
                st.error(f"Error de conexión: {str(e)}")
    else:
        st.warning("Por favor, ingresa una descripción del proceso.")