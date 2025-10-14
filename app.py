from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import os, re, time, requests

app = FastAPI(title="Pridano Generator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RUNS_DIR = os.path.join(os.getcwd(), "runs")
os.makedirs(RUNS_DIR, exist_ok=True)
app.mount("/runs", StaticFiles(directory=RUNS_DIR), name="runs")

# Expose the project folder statically at /static
app.mount("/static", StaticFiles(directory=".", html=True), name="site")

# Serve index.html at root, fallback to client/index.html
@app.get("/")
def root_index():
    """
    Serve index.html if present at project root, otherwise fallback to client/index.html.
    This fixes the 404 you saw on GET /.
    """
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    candidate = os.path.join("client", "index.html")
    if os.path.exists(candidate):
        return FileResponse(candidate)
    return JSONResponse({"detail": "index.html introuvable (ni à la racine ni dans client/)"},
                        status_code=404)

class GeneratePayload(BaseModel):
    project_name: str = "Mon Site"
    tone: str = "moderne"
    brand_colors: List[str] = ["#12C2E9"]
    pages: List[str] = ["Accueil","Services","Contact"]
    features: List[str] = []
    tech: List[str] = ["HTML+Tailwind"]
    dark_mode: bool = False
    model: Optional[str] = None

class AIEDitRequest(BaseModel):
    html: str
    prompt: str
    model: Optional[str] = None
    ollama_url: Optional[str] = "http://localhost:11434"

def slugify(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9\- ]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s or "site"

def assemble_html(p: GeneratePayload) -> str:
    brand = (p.brand_colors[0] if p.brand_colors else "#12C2E9").strip()
    hero = f"""<header class='gradient text-white'><div class='max-w-5xl mx-auto px-6 py-12'><h1 class='text-4xl font-bold'>{p.project_name}</h1><p class='mt-2 max-w-2xl text-white/90'>{p.tone}</p><div class='mt-6 flex gap-3'><a class='px-5 py-3 bg-white text-slate-900 rounded-xl font-semibold'>{("Réserver" if "Réservation" in p.features else "Nous contacter")}</a><a class='px-5 py-3 border border-white/50 rounded-xl'>En savoir plus</a></div></div></header>"""
    grid = """<section class='max-w-5xl mx-auto px-6 py-12'><h2 class='text-xl font-semibold mb-4'>Nos services</h2><div class='grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6'>""" + "".join(
        [f"<div class='p-5 bg-white rounded-2xl shadow'><div class='h-32 bg-slate-100 rounded-lg mb-3'></div><div class='h-4 bg-slate-200 rounded w-4/5 mb-2'></div><div class='h-4 bg-slate-200 rounded w-2/3'></div></div>" for _ in range(6)]
    ) + "</div></section>"
    faq = """<section class='max-w-5xl mx-auto px-6 pb-12'><h2 class='text-xl font-semibold mb-4'>FAQ</h2><div class='space-y-3'><details class='bg-white rounded-xl p-4 shadow'><summary class='font-medium'>Question 1</summary><p class='text-slate-600 mt-2'>Réponse.</p></details><details class='bg-white rounded-xl p-4 shadow'><summary class='font-medium'>Question 2</summary><p class='text-slate-600 mt-2'>Réponse.</p></details></div></section>"""
    cta = """<section class='max-w-5xl mx-auto px-6 py-12 text-center'><h2 class='text-2xl font-semibold'>Prêt à démarrer ?</h2><a class='inline-block mt-4 px-6 py-3 bg-slate-900 text-white rounded-xl'>Nous contacter</a></section>"""
    footer = """<footer class='border-t'><div class='max-w-5xl mx-auto px-6 py-8 text-sm text-slate-500'>© Votre marque</div></footer>"""

    sections = [hero, grid, faq, cta, footer]
    html = f"""<!DOCTYPE html><html lang='fr'><head>
      <meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
      <link href='https://cdn.jsdelivr.net/npm/tailwindcss@3.4.12/dist/tailwind.min.css' rel='stylesheet'>
      <style>:root{{--brand:{brand}}} .gradient{{background:linear-gradient(135deg,var(--brand) 0%,#7DE3F6 100%)}}</style>
      <title>{p.project_name}</title>
    </head>
    <body class='bg-slate-50 text-slate-900'>
      {''.join(sections)}
      <section class='max-w-5xl mx-auto px-6 py-12'><h2 class='text-xl font-semibold mb-2'>Infos</h2><p class='text-slate-600'>Pages : {", ".join(p.pages) or "—"} • Modules : {", ".join(p.features) or "—"} • Stack : {", ".join(p.tech)}</p></section>
    </body></html>"""
    return html

@app.post("/generate")
def generate_site(p: GeneratePayload, n: int = 1):
    folder = f"{int(time.time())}_{slugify(p.project_name)}"
    out_dir = os.path.join(RUNS_DIR, folder)
    os.makedirs(out_dir, exist_ok=True)
    html = assemble_html(p)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    return {"saved_at": f"/runs/{folder}", "best": {"score": 1.0}}

def _heuristic_edit(html: str, prompt: str) -> (str, str):
    log = []
    low = prompt.lower()

    # changement couleur (#xxxxxx détecté)
    m = re.search(r"#([0-9a-f]{3,6})", low)
    if "couleur" in low or "color" in low:
        if m:
            hexc = f"#{m.group(1)}"
            html = re.sub(r"--brand:\s*#[0-9a-fA-F]{3,6}", f"--brand:{hexc}", html)
            log.append(f"✔ Couleur de marque -> {hexc}")
    # ajout FAQ
    if "faq" in low and "FAQ" not in html:
        html = html.replace("</body>", """<section class='max-w-5xl mx-auto px-6 pb-12'><h2 class='text-xl font-semibold mb-4'>FAQ</h2><div class='space-y-3'><details class='bg-white rounded-xl p-4 shadow'><summary class='font-medium'>Question 1</summary><p class='text-slate-600 mt-2'>Réponse.</p></details></div></section></body>""")
        log.append("✔ Section FAQ ajoutée")
    # ajout CTA
    if "cta" in low and "Prêt à démarrer" not in html:
        html = html.replace("</body>", """<section class='max-w-5xl mx-auto px-6 py-12 text-center'><h2 class='text-2xl font-semibold'>Prêt à démarrer ?</h2><a class='inline-block mt-4 px-6 py-3 bg-slate-900 text-white rounded-xl'>Nous contacter</a></section></body>""")
        log.append("✔ CTA ajouté")
    # bouton Stripe démo
    if "stripe" in low and "stripe" not in html.lower():
        html = html.replace("</body>", """<script>function fakeCheckout(){alert('Stripe (démo)')}</script><section class='max-w-5xl mx-auto px-6 py-12 text-center'><button onclick="fakeCheckout()" class='px-6 py-3 bg-emerald-600 text-white rounded-xl'>Payer avec Stripe (démo)</button></section></body>""")
        log.append("✔ Bouton Stripe démo inséré")
    if not log:
        log.append("ℹ️ Rien de spécifique détecté, aucun changement majeur.")
    return html, "\n".join(log)

@app.post("/ai/edit")
def ai_edit(req: AIEDitRequest):
    # Essaye Ollama si dispo, sinon heuristiques
    used = "heuristics"
    html_out, logs = req.html, ""
    try:
        if req.ollama_url and req.model:
            url = req.ollama_url.rstrip("/") + "/api/generate"
            sys = "Tu es un assistant front-end. Transforme le HTML fourni. Retourne uniquement le HTML final entre balises <HTML_OUTPUT>...</HTML_OUTPUT>."
            prompt = f"""{sys}
Demande: {req.prompt}
HTML:
<<<HTML
{req.html}
HTML>>>"""
            resp = requests.post(url, json={"model": req.model, "prompt": prompt, "stream": False}, timeout=60)
            if resp.ok:
                used = "ollama"
                txt = resp.json().get("response","")
                m = re.search(r"<HTML_OUTPUT>(.*)</HTML_OUTPUT>", txt, re.S)
                if m:
                    html_out = m.group(1).strip()
                    logs = "Réponse Ollama utilisée."
                else:
                    html_out = txt.strip() or req.html
                    logs = "Texte Ollama sans balises, pris tel quel."
            else:
                logs = f"Ollama non OK: {resp.status_code} {resp.text[:160]}"
        else:
            logs = "Ollama non configuré, heuristiques appliquées."
    except Exception as e:
        logs = f"Ollama indisponible: {e}. Heuristiques appliquées."
    if used != "ollama":
        html_out, more = _heuristic_edit(req.html, req.prompt)
        logs = (logs + "\n" + more).strip()
    return {"html": html_out, "log": logs}