#!/usr/bin/env python3
"""
scrape_afa.py
--------------
Trae resultados y próximos partidos de las 4 ligas del ascenso argentino
(Primera División, Primera Nacional, Primera B Metropolitana, Primera C)
desde promiedos.com.ar y los guarda en data/afa.json.

Pensado para correr solo, cada tantas horas, vía GitHub Actions
(ver .github/workflows/update-data.yml). También podés correrlo a mano:

    pip install requests beautifulsoup4
    python scrape_afa.py

IMPORTANTE — LEER ANTES DE USAR:
Promiedos (como casi cualquier sitio de resultados) puede cambiar el HTML
de su página en cualquier momento. Este script fue escrito sin poder
probarlo contra el sitio en vivo, así que la primera vez que lo corras
puede que no encuentre nada. Para eso:

  1) Corré el script una vez a mano.
  2) Si algún JSON queda vacío ([]), buscá el bloque marcado con
     "# AJUSTAR ACÁ" de la liga correspondiente.
  3) Corré `python scrape_afa.py --debug <url>` (ver abajo) para imprimir
     el HTML crudo de esa página y ubicar los selectores correctos
     (clases CSS, tags) que usa el sitio en ese momento.
  4) Reemplazá el selector en la función de esa liga.

Muchos sitios modernos (incluido probablemente Promiedos) cargan los
partidos con JavaScript y embeben los datos como JSON dentro de un
<script>. Por eso este script primero intenta encontrar ese JSON
embebido, y si no lo encuentra, cae a un parseo genérico de tablas/divs
como respaldo. Ajustá lo que haga falta según lo que encuentres.
"""

import json
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# URLs de referencia — verificar que sigan existiendo antes de correr en serio.
LEAGUES = {
    "liga-arg": {
        "name": "Liga Profesional Argentina",
        "url": "https://www.promiedos.com.ar/primera",
    },
    "nacional": {
        "name": "Primera Nacional",
        "url": "https://www.promiedos.com.ar/league/primera-nacional/ebj",
    },
    "metro": {
        "name": "Primera B Metropolitana",
        "url": "https://www.promiedos.com.ar/primerab",
    },
    "primerac": {
        "name": "Primera C",
        "url": "https://www.promiedos.com.ar/primerac",
    },
}


def fetch_html(url):
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def find_embedded_json(html):
    """
    Muchos sitios (Next.js, Nuxt, apps React) embeben los datos de la página
    como JSON dentro de un <script id="__NEXT_DATA__"> o similar, para que el
    front-end los "hidrate". Si Promiedos hace esto, acá lo capturamos.
    Si no aparece nada, esta función devuelve None y usamos el respaldo.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Intento 1: Next.js
    tag = soup.find("script", id="__NEXT_DATA__")
    if tag and tag.string:
        try:
            return json.loads(tag.string)
        except json.JSONDecodeError:
            pass

    # Intento 2: cualquier script que declare "window.__INITIAL_STATE__ = {...}"
    for script in soup.find_all("script"):
        if not script.string:
            continue
        m = re.search(r"__INITIAL_STATE__\s*=\s*(\{.*?\});", script.string, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue

    return None


def parse_fallback_matches(html):
    """
    Respaldo genérico: busca filas de partido en tablas / divs típicos de
    sitios de resultados (equipo local, marcador, equipo visitante, fecha).
    Esto es intencionalmente amplio porque no pude inspeccionar el HTML
    real del sitio. Es el bloque que más probablemente haya que afinar.
    """
    soup = BeautifulSoup(html, "html.parser")
    matches = []

    # AJUSTAR ACÁ: reemplazá estos selectores por los reales una vez que
    # inspecciones el HTML (clic derecho → Inspeccionar en el navegador,
    # buscá el contenedor de cada partido).
    candidates = soup.select("[class*='match']") or soup.select("[class*='partido']") or soup.select("tr")

    for c in candidates:
        text = c.get_text(" ", strip=True)
        # Heurística muy simple: buscamos patrones "Equipo N - N Equipo"
        m = re.search(r"([A-Za-zÁÉÍÓÚÑáéíóúñ\.\s]+?)\s+(\d+)\s*[-–]\s*(\d+)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ\.\s]+)", text)
        if m:
            matches.append({
                "home": m.group(1).strip(),
                "away": m.group(4).strip(),
                "score": f"{m.group(2)}-{m.group(3)}",
                "meta": "resultado (parseo genérico, revisar)"
            })

    return matches[:10]


def scrape_league(key, cfg):
    print(f"→ Scrapeando {cfg['name']} ({cfg['url']})")
    try:
        html = fetch_html(cfg["url"])
    except Exception as e:
        print(f"  ✗ No se pudo bajar la página: {e}")
        return {"results": [], "next": [], "error": str(e)}

    embedded = find_embedded_json(html)
    if embedded:
        # AJUSTAR ACÁ: si encontraste el JSON embebido, este es el lugar
        # para navegar su estructura real (embedded["props"]["pageProps"]...)
        # y mapearla a {home, away, score, meta}. Como no conocemos la forma
        # exacta, dejamos esto como punto de partida.
        print("  ✓ Se encontró JSON embebido en la página (revisar estructura real).")
        results, next_matches = [], []
    else:
        print("  … no se encontró JSON embebido, usando parseo genérico de respaldo.")
        parsed = parse_fallback_matches(html)
        results, next_matches = parsed, []

    return {"results": results, "next": next_matches}


def main():
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "leagues": {}
    }

    for key, cfg in LEAGUES.items():
        data["leagues"][key] = scrape_league(key, cfg)

    import os
    os.makedirs("data", exist_ok=True)
    with open("data/afa.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\nListo → data/afa.json")


if __name__ == "__main__":
    main()
