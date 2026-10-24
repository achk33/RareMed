import json
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from google.api_core.exceptions import GoogleAPIError
import google.generativeai as genai

load_dotenv()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file")

genai.configure(api_key=GEMINI_API_KEY)

GRAPH_PATH = Path(__file__).resolve().parent.parent / "graph.json"
with GRAPH_PATH.open(encoding="utf-8") as graph_file:
    KNOWLEDGE_GRAPH = json.load(graph_file)

SYSTEM_PROMPT = (
    "Tu es RareMed AI. Tu dois analyser les symptômes du patient en utilisant "
    "UNIQUEMENT ce Knowledge Graph : "
    f"{json.dumps(KNOWLEDGE_GRAPH, ensure_ascii=False)}. "
    "Ne devine rien. Retourne uniquement un objet JSON valide avec les clés "
    '"status" (SUCCESS, MISSING_INFO ou UNCERTAIN), "hypotheses" (une liste '
    "d'hypothèses contenant chacune un evidence_path), et "
    '"question" (une question discriminante ou null si aucune question '
    "n'est nécessaire)."
)

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
        return jsonify({"error": "A messages list is required."}), 400

    messages = []
    for message in data["messages"]:
        if (
            not isinstance(message, dict)
            or message.get("role") not in ("user", "assistant")
            or not isinstance(message.get("content"), str)
        ):
            return jsonify({"error": "Each message must have a valid role and text content."}), 400
        messages.append({
            "role": "model" if message["role"] == "assistant" else "user",
            "parts": [message["content"]],
        })

    if not messages:
        return jsonify({"error": "At least one user message is required."}), 400
    if messages[-1]["role"] != "user":
        return jsonify({"error": "The latest message must be from the user."}), 400
    if messages[0]["role"] == "model":
        messages.pop(0)

    model_name = data.get("model", "gemini-1.5-pro")
    if model_name not in ("gemini-1.5-pro", "gemini-1.5-flash"):
        return jsonify({"error": "Unsupported Gemini model."}), 400

    try:
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=SYSTEM_PROMPT,
            generation_config={"response_mime_type": "application/json"},
        )
        response = model.generate_content(messages)
        result = json.loads(response.text)
    except GoogleAPIError as error:
        return jsonify({"error": f"Gemini API request failed: {error}"}), 502
    except (json.JSONDecodeError, ValueError) as error:
        return jsonify({"error": f"Gemini returned invalid JSON: {error}"}), 502

    if (
        not isinstance(result, dict)
        or result.get("status") not in ("SUCCESS", "MISSING_INFO", "UNCERTAIN")
        or not isinstance(result.get("hypotheses"), list)
        or not all(
            isinstance(hypothesis, dict) and "evidence_path" in hypothesis
            for hypothesis in result["hypotheses"]
        )
        or not ("question" in result and (
            result["question"] is None or isinstance(result["question"], str)
        ))
    ):
        return jsonify({"error": "Gemini response does not match the required JSON schema."}), 502

    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
