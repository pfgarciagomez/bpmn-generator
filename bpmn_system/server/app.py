from flask import Flask, request, jsonify
from flask_cors import CORS
from llm_handler import LLMHandler
import json

app = Flask(__name__)
CORS(app)

# Inicializar el modelo una sola vez al inicio
llm_handler = LLMHandler()

@app.route('/generate_json', methods=['POST'])
def generate_json():
    try:
        data = request.json
        user_prompt = data.get('prompt', '')
        
        # Generar JSON usando el modelo
        json_output = llm_handler.generate_json(user_prompt)
        
        return jsonify({"success": True, "data": json_output})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)