async function generate() {
    const btn = document.getElementById('btn');
    const out = document.getElementById('out');
    out.style.display = 'block';
    out.textContent = 'Génération en cours…';
    btn.disabled = true;
  
    const payload = {
      project_name: document.getElementById('project_name').value || 'Mon Site',
      tone: document.getElementById('tone').value || 'moderne',
      brand_colors: JSON.parse(document.getElementById('colors').value || '[]'),
      pages: JSON.parse(document.getElementById('pages').value || '[]'),
      features: JSON.parse(document.getElementById('features').value || '[]'),
      tech: JSON.parse(document.getElementById('tech').value || '[]'),
      dark_mode: (document.getElementById('dark').value || 'true').toLowerCase() === 'true',
      model: document.getElementById('model').value || null
    };
  
    try {
      const res = await fetch('/generate?n=1', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
  
      const url = data.saved_at + '/index.html';
      out.innerHTML = `
        <div>✅ Fait. Score: <strong>${data.best?.score?.toFixed?.(3)}</strong></div>
        <div>👉 <a href="${url}" target="_blank" rel="noopener">Ouvrir le site généré</a></div>
        <div class="muted">Dossier: <code>${data.saved_at}</code></div>
      `;
    } catch (err) {
      out.textContent = 'Erreur: ' + err.message;
    } finally {
      btn.disabled = false;
    }
  }
  
  document.getElementById('btn').addEventListener('click', generate);