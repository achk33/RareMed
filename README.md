
# RareMed AI
> **Explainable, Graph-Grounded Clinical Decision Support for Rare Diseases**
---
## 🌍 The Challenge
Rare diseases affect over 300 million people worldwide. For many patients, obtaining an accurate diagnosis takes an average of 4 to 7 years—a painful journey known as the "diagnostic odyssey." 
A primary reason for this delay is that rare diseases present with atypical combinations of symptoms that are difficult to correlate without specialized clinical knowledge.
While general-purpose Large Language Models (LLMs) excel at natural language understanding, they are prone to hallucinations and lack deterministic traceability. In clinical medicine:
- A plausible-sounding guess is dangerous.
- Reasoning must be auditable and grounded in authoritative data.
- The system must know when to declare uncertainty rather than generate a hallucinated diagnosis.
**RareMed AI** bridges this gap by decoupling language understanding from medical knowledge. Rather than treating an LLM as a diagnostic authority, RareMed AI anchors it to a structured medical knowledge graph, multimodal document extraction, and transparent evidence retrieval.
> **Core Principle:** Every hypothesis must carry an inspectable evidence trail, and insufficient data must never be disguised as clinical certainty.
---
## 💡 The Solution
RareMed AI is an AI-assisted clinical decision-support prototype designed to help healthcare practitioners investigate rare diseases using patient symptoms and uploaded medical records.
### The End-to-End Workflow

[01 Describe & Upload] ───► [02 Normalize (HPO)] ───► [03 Graph Retrieve]
                                                             │
                                                             ▼
[06 Abstain / Inquire] ◄─── [05 Explain Evidence] ◄─── [04 Match & Rank]

  

  
Describe & Upload: Enter symptoms in natural language (English, French, Moroccan Darija) or upload printed lab reports/prescriptions.

  
Normalize: Map free-text symptoms and OCR text into standardized ontology codes (Human Phenotype Ontology - HPO).

  
Retrieve: Traverse structured medical knowledge bases to identify candidate phenotype–disease relationships.

  
Rank: Score candidate diseases based on matched graph nodes, missing phenotypes, and discriminatory criteria.

  
Explain: Present clinicians with the exact evidence path, associated genes, and matched ontology edges.

  
Handle Uncertainty: When data is insufficient or ambiguous, the system explicitly abstains and prompts for discriminating clinical tests.

  

  

  
🚀 Key Innovations

  
1. Graph-Grounded Reasoning (Zero-Hallucination Guardrails)

  

Instead of free-form diagnostic generation, RareMed AI implements GraphRAG. The LLM acts strictly as a semantic parser and reasoning engine over a deterministic knowledge graph (JSON-based schema for the MVP, mapped to HPO and Orphanet concepts).


  
2. Multimodal Medical OCR (Qwen-VL via vLLM)

  

Clinical data often exists only on paper. RareMed AI includes an OCR pipeline powered by Qwen-VL running on vLLM to ingest printed lab panels, discharge summaries, and prescriptions directly into the normalization engine.


  
3. Traceable Evidence Paths

  

Clinicians do not receive a "black box" prediction. Every hypothesis displays:


  

  
Exact HPO symptom matches.

  
Missing phenotypes required to confirm the disease.

  
Recommended diagnostic confirmation tests (e.g., enzyme assays or genetic sequencing).

  

  
4. Multilingual Phenotype Normalization

  

Patients describe symptoms in everyday vernacular. RareMed AI supports multilingual normalization across English, French, and Moroccan Darija (e.g., mapping "كنحس بالعياء والحريق في العظام" to relevant HPO terms for fatigue and bone pain).


  
5. Unified Clinical Dashboard Integration

  

Built natively into the SCHMS clinical monitoring dashboard, enabling doctors to triage patients from anomalous vital signs directly into deep GraphRAG investigations.


  

  
🧠 Technical Architecture

  
text
┌─────────────────────────────────────────────────────────┐
│              SCHMS Clinical Dashboard                   │
│          Patient Vitals, Symptoms & Uploads             │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│                    Flask Backend API                    │
│               Request Routing & Orchestration           │
└────────────┬───────────────────────────────┬────────────┘
             │ (Text Input)                  │ (Documents/PDFs)
             ▼                               ▼
┌──────────────────────────┐    ┌─────────────────────────┐
│     Language Layer       │    │     Vision/OCR Layer    │
│  Symptom Normalization   │    │    Qwen-VL via vLLM     │
│ (EN / FR / Darija ➔ HPO) │    │  Entity & Text Extract  │
└────────────┬─────────────┘    └────────────┬────────────┘
             │                               │
             └───────────────┬───────────────┘
                             ▼
┌─────────────────────────────────────────────────────────┐
│               Structured Knowledge Layer                │
│       JSON Knowledge Graph (HPO / Orphanet Schema)      │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│                Candidate Analysis Engine                │
│            Matching, Ranking & Discriminator            │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│                   Result Presentation                   │
│          Candidate Hypotheses & Evidence Paths          │
│          Uncertainty Handling & Next Steps              │
└─────────────────────────────────────────────────────────┘

  
Technology Stack

Layer	Component	Purpose
Frontend	HTML5, JavaScript, Tailwind CSS	SCHMS Clinical Dashboard
Backend	Python 3.10+, Flask	API routing, triage orchestration
LLM Engine	Google Gemini API / Configured LLM	Semantic parsing, symptom extraction
Document Vision	Qwen-VL (vLLM local inference)	Medical document and lab report OCR
Knowledge Store	Structured JSON (Graph Schema)	Phenotype-disease relationship store
Ontology	Human Phenotype Ontology (HPO)	Standardized clinical vocabulary

🛠️ Getting Started


Prerequisites

  

  
Python 3.10+

  
Git

  
An API Key for language modeling (e.g., GEMINI_API_KEY)

  
(Optional) CUDA-compatible GPU if running local Qwen-VL via vLLM

  

  
1. Clone the Repository

  
bash
git clone https://github.com/achk33/Medical-Dash.git
cd Medical-Dash/template

  
2. Setup Environment

  
bash
python -m venv .venv
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate
pip install -r requirements.txt

  
3. Configure Credentials

  
bash
cp .env.example .env

  

Open .env and configure your API key:


  
env
GEMINI_API_KEY=your_gemini_api_key_here

  
4. Run the Application

  
bash
python chatbot.py

  

Visit http://127.0.0.1:5000/health-monitor in your browser.


  

  
🧪 Demo Scenario

  

  
Navigate to the dashboard at http://127.0.0.1:5000/health-monitor.

  
Inspect the simulated patient with anomalous vitals (e.g., Fatima El Amrani) or input free-text symptoms in Darija:
  

  

"كنحس بالعياء الشديد، الحريق فالعظام، والكرش منفوخة"


  

  

  
Click "Évaluer avec l'IA".

  
Review the generated Evidence Path:
  
  

  
Symptoms mapped to standard HPO terms (HP:0001903, HP:0002829, HP:0001744).

  
Hypothesis surfaced: Gaucher Disease Type 1.

  
Review the recommended confirmatory test: Beta-glucosidase leukocyte assay.

  

  

  

  
🗺️ Product Roadmap

  

  
 Phase 1: Knowledge Scaling
  
  

  
Migrate JSON graph store to Neo4j.

  
Ingest full Orphanet and MONDO ontology dumps.

  

  
 Phase 2: Local Reasoning & Privacy
  
  

  
Containerize the complete pipeline with Docker Compose.

  
Support fully offline inference with local quantized LLMs.

  

  
 Phase 3: Clinical Validation
  
  

  
Benchmark Darija symptom mapping against synthetic clinical datasets.

  
Evaluate conformity with Moroccan Law 09-08 and HIPAA data security guidelines.
