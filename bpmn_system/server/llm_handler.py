import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from sentence_transformers import SentenceTransformer
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
import json
import os
import PyPDF2
import re
import time

class CustomEmbeddings:
    def __init__(self, embedding_model):
        self.embedding_model = embedding_model
    
    def embed_documents(self, texts):
        # Convert texts to embeddings
        return [self.embedding_model.encode(text).tolist() for text in texts]
    
    def embed_query(self, query):
        # Embed a single query
        return self.embedding_model.encode(query).tolist()

class LLMHandler:
    def __init__(self):
        # Paths and configurations
        self.model_path = "/mnt/backupnas/fgarcia/Llama3"
        self.json_path = "/home/fgarcia/bpmn_system/client/process.json"
        self.context_pdf_path = "/home/fgarcia/bpmn_system/server/context/contexto.pdf"
        self.vectorstore_path = os.path.join(
            os.path.dirname(self.context_pdf_path), 
            'faiss_index'
        )
        
        # Similarity threshold for context retrieval
        self.similarity_threshold = 0.2
        
        # Setup model and RAG components
        self.setup_model()
        self.setup_embedding()
        
        # Check if vectorstore exists, create only if not
        if not os.path.exists(os.path.join(self.vectorstore_path, 'index.faiss')):
            self.create_vectorstore()
        
    def setup_model(self):
        # Quantization configuration
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4"
        )
        
        # Load model and tokenizer
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            device_map="auto",
            torch_dtype=torch.bfloat16,
            quantization_config=quantization_config
        )
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        
    def setup_embedding(self):
        # Use GPU-accelerated embedding model
        self.embedding_model = SentenceTransformer(
            'sentence-transformers/all-MiniLM-L6-v2', 
            device='cuda'
        )
        
        # Create custom embeddings wrapper
        self.embeddings = CustomEmbeddings(self.embedding_model)
        
    def extract_pdf_text(self):
        """Extract text from PDF file and split into paragraphs"""
        with open(self.context_pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            full_text = ""
            for page in reader.pages:
                # Reemplazar saltos de línea por espacios al extraer el texto
                page_text = page.extract_text().replace('\n', ' ')
                full_text += page_text + " "
            
            # Usar regex para separar párrafos que comienzan con un número seguido de punto
            paragraphs = re.split(r'(?=\d+\.)', full_text)
            
            # Limpiar y filtrar párrafos
            paragraphs = [
                ' '.join(p.strip().split()) 
                for p in paragraphs 
                if p.strip() and len(p.strip()) > 50
            ]
            
            # Eliminar el primer elemento si está vacío (puede ocurrir con el split)
            if paragraphs and not paragraphs[0].startswith('1.'):
                paragraphs = paragraphs[1:]
            
            # Mostrar los párrafos 1 y 2 por terminal
            if len(paragraphs) >= 2:
                print("Párrafo 1:", paragraphs[0])
                print("\nPárrafo 2:", paragraphs[1])
            
            print("\nTotal de párrafos:", len(paragraphs))
            
            return paragraphs
    
    def create_vectorstore(self):
        print("Creating vectorstore...")
        
        # Extract paragraphs from PDF
        paragraphs = self.extract_pdf_text()
        
        # Create documents from paragraphs
        documents = [Document(page_content=para) for para in paragraphs]
        
        # Create FAISS vectorstore with custom embeddings
        vectorstore = FAISS.from_documents(
            documents, 
            embedding=self.embeddings
        )
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.vectorstore_path), exist_ok=True)
        
        # Save vectorstore locally
        vectorstore.save_local(self.vectorstore_path)
        print("Vectorstore created successfully.")
        
    def retrieve_context(self, query, k=1):
        """
        Retrieve top k most relevant context documents above similarity threshold
        
        Args:
            query (str): Input query to find relevant context
            k (int, optional): Maximum number of documents to retrieve. Defaults to 3.
        
        Returns:
            str: Concatenated relevant context paragraphs
        """
        # Load existing vectorstore
        vectorstore = FAISS.load_local(
            self.vectorstore_path, 
            HuggingFaceBgeEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2'),
            allow_dangerous_deserialization=True
        )
        
        # Compute similarity scores for all documents
        retriever = vectorstore.as_retriever(
            search_type="similarity_score_threshold",
            search_kwargs={
                "k": k,
                "score_threshold": self.similarity_threshold
            }
        )
        
        # Retrieve similar documents
        similar_docs = retriever.get_relevant_documents(query)

        # Return concatenated paragraphs or empty string if no relevant docs
        return "\n".join([doc.page_content for doc in similar_docs]) if similar_docs else ""
    
    def generate_json(self, user_prompt):

        ti = time.time()

        # Retrieve relevant context
        context = self.retrieve_context(user_prompt)
        
        print("CONTEXT: ",context)

        # Augment system prompt with context
        system_prompt = f"""Eres un experto en modelado de procesos y generación de diagramas BPMN. 
        
        Contexto adicional relevante para generar la información del JSON:
        
        {context}
        """

        system_prompt = system_prompt + """
        **Requisitos principales**:

        1. **Único flujo secuencial**:
            - Todo el proceso debe estar estructurado en un único flujo de principio a fin.
            - Cada elemento del proceso (tareas, pasarelas, bucles) debe integrarse en el flujo principal sin interrupciones.

        2. **Estructura secuencial**:
            - El flujo debe seguir un orden estricto definido por el arreglo `flow`. Este orden determina cómo se ejecutan las tareas, pasarelas y bucles.

        3. **Eventos**:
            - Debe existir un único evento de inicio (`inicio`) y uno o varios eventos de fin (`fin`). El evento de fin contendrá un campo de condición.

        4. **Tareas**:
            - Cada tarea debe incluir un `name` único y una descripción opcional (`description`).
            - Deben estar alineadas en el flujo secuencial.

        5. **Pasarelas (Gateways)**:
            - Representan decisiones (XOR) o paralelismos (AND).
            - Cada pasarela debe incluir:
                - `name`: Identificador único.
                - `type_pasarela`: Especifica si es "XOR" o "AND". En caso de ser "AND" no llevará condición. En caso de sr "XOR" llevará condición.
                - `ramas`: Listas de tareas o elementos dentro de cada rama.
                - Cada rama debe incluir:
                    `name`: Nombre de la rama
                    `condición`: Condición de elección de la rama   
                    `tareas`: Tareas a realizar en la rama


        6. **Bucles**:
            - Representan tareas o procesos repetitivos.
            - Deben incluir:
                - `name`: Identificador único del bucle.
                - `condición`: Criterio para detener el bucle.
                - `tareas`: Lista de elementos que forman parte del bucle.

        7. **Formato JSON actualizado**:
            - Todo el proceso debe estar contenido en un único flujo dentro del arreglo `flow`.
            - Los elementos en el flujo deben ser secuenciales, respetando las conexiones lógicas.
            - Cuando generes tareas dentro de las ramas de una pasarela o bucle, SIEMPRE utiliza listas de strings simples para los nombres de las tareas.
            - Si una tarea requiere más detalles, conviértela en un elemento completo de diccionario dentro del flujo principal, y en las ramas de pasarelas o bucles, usa solo su nombre como string.

        A continuación se te proporciona un ejemplo de JSON. ES SOLO UN EJEMPLO de como se representa cada tipo de suceso. Los eventos serán distintos para cada proceso.
        Basándote en esta estructura deberás de la manera más óptima posible como experto que eres seleccionar que tipo de pasarelas, bucles, eventos y tareas utilizar y en que orden. 
        Deberás tratar de ser lo más variado posible a la vez que óptimo en la selección de eventos.

        **Ejemplo de Formato JSON esperado**:

        ```json
        {
            "flow": [
                {"type": "evento", "name": "inicio"},
                {"type": "tarea", "name": "Preparar contrato de empleo", "description": "Preparar el contrato de empleo y los documentos necesarios"},
                {
                    "type": "pasarela",
                    "name": "Evaluación del candidato",
                    "type_pasarela": "XOR",
                    "ramas": [
                        {
                            "name": "Contratar al candidato", 
                            "condición": "El candidato cumple con los requisitos del puesto",
                            "tareas": [
                                "Preparar contrato de empleo", 
                                "Realizar entrevista de ingreso"
                            ]
                        },
                        {
                            "name": "Revisar otros candidatos",
                            "condición": "El candidato no cumple con los requisitos del puesto", 
                            "tareas": ["Evaluar otros candidatos"]
                        }
                    ]
                },
                {
                    "type": "bucle",
                    "name": "Revisión de documentos",
                    "condición": "Hasta que todos los documentos estén aprobados",
                    "tareas": [
                        "Revisar documento", 
                        "Solicitar correcciones si es necesario"
                    ]
                },
                {"type": "evento", "name": "fin", "condicion": "Empleado contratado"}
            ]
        }
        ```

        DEVUELVE ÚNICAMENTE EL JSON PEDIDO SIN NINGÚN COMENTARIO ADICIONAL.
        """

        # Rest of the generation logic remains the same
        input_text = f"""
        <|begin_of_text|><|start_header_id|>system<|end_header_id|>
        {system_prompt}<|eot_id|>
        <|start_header_id|>user<|end_header_id|>
        {user_prompt}<|eot_id|>
        <|start_header_id|>assistant<|end_header_id|>
        """
        
        input_ids = self.tokenizer(input_text, return_tensors="pt").to("cuda")
        output = self.model.generate(**input_ids, max_new_tokens=2000)
        decoded_output = self.tokenizer.decode(output[0], skip_special_tokens=False)
        
        tf = time.time()

        print("JSON generado en ", tf-ti , " segundos.")

        # Extract assistant's response (same as before)
        assistant_start = "<|start_header_id|>assistant<|end_header_id|>"
        if assistant_start in decoded_output:
            generated_text = decoded_output.split(assistant_start)[-1].strip()
        else:
            generated_text = decoded_output
        
        try:
            # Extract JSON (same as before)
            json_start = generated_text.find('{')
            json_end = generated_text.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No se encontró JSON válido en la respuesta")
            
            json_text = generated_text[json_start:json_end]
            process_json = json.loads(json_text)

            print(json_text)

            # Save JSON
            with open(self.json_path, 'w', encoding='utf-8') as f:
                json.dump(process_json, f, indent=2, ensure_ascii=False)
            
            return 200
        except Exception as e:
            print(f"Error al procesar o guardar el JSON: {str(e)}")
            print(f"Texto generado: {json_text}")  # For debugging
            return 500

# Usage example
if __name__ == "__main__":
    llm_handler = LLMHandler()