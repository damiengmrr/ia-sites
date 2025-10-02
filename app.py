import os, re, json, time
from typing import List, Dict, Any

import requests
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ---- Config ----
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5-coder:7b"  # ou "llama3.1:8b"

# ---- FastAPI ----
app = FastAPI(title="IA Sites (Ollama + FastAPI)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

# Servir les sorties et le mini front
os.makedirs("runs", exist_ok=True)
app.mount("/runs", StaticFiles(directory="runs"), name="runs")

# ---- Brief ----
class Brief(BaseModel):
    project_name: str
    brand_colors: List[str] = ["#0ea5e9", "#111827", "#f8fafc"]
    tone: str = "moderne, pro, minimal, animations douces"
    pages: List[str] = ["home"]
    features: List[str] = ["hero", "services", "contact"]
    tech: List[str] = ["TailwindCSS", "vanilla JS"]
    dark_mode: bool = True
    model: str | None = None  # pour changer de modèle à la volée

PROMPT_TEMPLATE = """Tu es un assistant front senior.
Génère un site complet et propre pour "{name}".
- Framework CSS: Tailwind (MVP: <script src="https://cdn.tailwindcss.com"></script> dans le HTML).
- Fichiers séparés: index.html, style.css, script.js.
- Respecte ces couleurs: {colors}
- Ton: {tone}
- Sections: {features}
- Pages: {pages}
- Dark mode: {dark}

Contraintes:
- HTML sémantique, meta SEO + OpenGraph, favicon placeholder.
- Header sticky, footer, menu ancre.
- Animations CSS (transition/transform), micro-interactions boutons/liens.
- JS minimal: menu mobile + scroll reveal.
- Réponds UNIQUEMENT par un JSON valide avec trois clés:
{{
  "index.html": "...",
  "style.css": "...",
  "script.js": "..."
}}
"""

# ---- Mini "scoring" PyTorch (placeholder simple sans entraînement) ----
try:
    import torch
    import torch.nn as nn

    class TinyRater(nn.Module):
        def __init__(self):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(3, 32),
                nn.ReLU(),
                nn.Linear(32, 1)
            )
        def forward(self, x):
            return self.net(x)

    RATER = TinyRater()
    RATER.eval()

    def quick_features(index_html: str, style_css: str):
        has_aria = 1.0 if "aria-" in index_html else 0.0
        tailwind_density = min(index_html.count('class="') / 200, 1.0)
        has_contrast_hint = 1.0 if ("text-white" in index_html and "bg-") else 0.0
        import torch as _t
        return _t.tensor([[has_aria, tailwind_density, has_contrast_hint]], dtype=_t.float32)

    def score_site(files: Dict[str, str]) -> float:
        feats = quick_features(files.get("index.html",""), files.get("style.css",""))
        with torch.no_grad():
            s = RATER(feats).item()
        return float(s)
except Exception:
    # Si torch indisponible, fallback heuristique
    def score_site(files: Dict[str, str]) -> float:
        html = files.get("index.html","")
        css = files.get("style.css","")
        score = 0.0
        if "aria-" in html: score += 0.3
        score += min(html.count('class="')/400, 0.4)
        if "text-white" in html and "bg-" in html: score += 0.3
        return score

# ---- Utils ----
def ask_ollama(prompt: str, model_name: str, temperature: float = 0.4) -> str:
    data = {"model": model_name, "prompt": prompt, "stream": False,
            "options": {"temperature": temperature}}
    r = requests.post(OLLAMA_URL, json=data, timeout=180)
    r.raise_for_status()
    return r.json()["response"]

def extract_files(response_text: str) -> Dict[str, str]:
    m = re.search(r"\{.*\}", response_text, re.S)
    if not m:
        raise ValueError("Pas de JSON détecté dans la réponse du modèle.")
    return json.loads(m.group(0))

def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return s or "site"

def save_run(files: Dict[str,str], run_dir: str) -> None:
    os.makedirs(run_dir, exist_ok=True)
    for fname in ["index.html", "style.css", "script.js"]:
        with open(os.path.join(run_dir, fname), "w", encoding="utf-8") as f:
            f.write(files.get(fname, ""))

# ---- Route principale ----
@app.post("/generate")
def generate(brief: Brief, n: int = Query(1, ge=1, le=5)):
    model_name = brief.model or MODEL
    prompt = PROMPT_TEMPLATE.format(
        name=brief.project_name,
        colors=brief.brand_colors,
        tone=brief.tone,
        features=brief.features,
        pages=brief.pages,
        dark="oui" if brief.dark_mode else "non",
    )

    variants: List[Dict[str, Any]] = []
    for _ in range(n):
        raw = ask_ollama(prompt, model_name=model_name)
        files = extract_files(raw)
        score = score_site(files)
        variants.append({"files": files, "score": score})

    best = max(variants, key=lambda x: x["score"])
    ts = time.strftime("%Y%m%d-%H%M%S")
    run_name = f"{slugify(brief.project_name)}-{ts}"
    run_dir = os.path.join("runs", run_name)
    save_run(best["files"], run_dir)

    return {
        "saved_at": f"/runs/{run_name}",
        "best": best,
        "variants": variants
    }
    
# --- Mount du front en dernier pour ne pas intercepter /generate ---
app.mount("/", StaticFiles(directory="client", html=True), name="client")