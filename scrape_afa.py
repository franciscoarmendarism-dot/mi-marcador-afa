#!/usr/bin/env python3
"""
scrape_afa.py — v2 (con navegador headless)
--------------------------------------------
Trae resultados y próximos partidos de las 4 ligas del ascenso argentino
desde promiedos.com.ar y los guarda en data/afa.json.

POR QUÉ CAMBIÓ ESTA VERSIÓN:
La v1 usaba `requests` para bajar el HTML crudo de la página, pero
Promiedos es una app que arma la lista de partidos con JavaScript
DESPUÉS de cargar la página (se ve un "Loading..." en el HTML crudo,
sin ningún partido adentro). Por eso la v1 devolvía todo vacío: no era
un tema de selectores mal puestos, era que directamente no había nada
que leer en el HTML plano.

La solución real para este tipo de sitios es usar un navegador headless
(Playwright) que SÍ ejecuta el JavaScript, espera a que carguen los
partidos, y ahí recién lee el contenido — igual que hace tu navegador
normal cuando abrís la página.

URLs correctas (verificadas, no son las de la v1):
  Liga Profesional Argentina : /league/liga-profesional/hc
  Primera Nacional           : /league/primera-nacional/ebj
  Primera B Metropolitana    : /league/primera-b-metropolitana/fahh
  Primera C                  : /league/primera-c/ffjb

CÓMO PROBARLO LOCAL:
    pip install playwright beautifulsoup4
    playwright install chromium --with-deps
    python scrape_afa.py

SI SIGUE SIN ENCONTRAR PARTIDOS:
Es posible que Promiedos también cambie las clases CSS de sus tarjetas
de partido con el tiempo. Si `data/afa.json` sigue vacío después de este
cambio, corré:
    python scrape_afa.py --dump-html liga-arg
Eso guarda el HTML ya renderizado (después del JavaScript) en
`debug_liga-arg.html`. Pegame el contenido de ese archivo (o subilo al
chat) y te ajusto los selectores con el DOM real en la mano, en vez de
adivinar.
"""

import json
import re
import sys
import os
from datetime import datetime, timezone

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

LEAGUES = {
    "liga-arg": {
        "name": "Liga Profesional Argentina",
        "url": "https://www.promiedos.com.ar/league/liga-profesional/hc",
    },
    "nacional": {
        "name": "Primera Nacional",
        "url": "https://www.promiedos.com.ar/league/primera-nacional/ebj",
    },
    "metro": {
        "name": "Primera B Metropolitana",
        "url": "https://www.promiedos.com.ar/league/primera-b-metropolitana/fahh",
    },
    "primerac": {
        "name": "Primera C",
        "url": "https://www.promiedos.com.ar/league/primera-c/ffjb",
    },
}

# Patrón para detectar resultados ya jugados: "Equipo A  2 - 1  Equipo B"
RESULT_PATTERN = re.compile(
    r"([A-Za-zÀ-ÿ0-9\.\'\s]{3,35}?)\s+(\d{1,2})\s*[-–]\s*(\d{1,2})\s+([A-Za-zÀ-ÿ0-9\.\'\s]{3,35}?)(?=\s{2,}|\n|$)"
)

# Patrón para próximos partidos sin marcador: "Equipo A  vs  Equipo B  21:00"
NEXT_PATTERN = re.compile(
    r"([A-Za-zÀ-ÿ0-9\.\'\s]{3,35}?)\s+(?:vs\.?|-)\s+([A-Za-zÀ-ÿ0-9\.\'\s]{3,35}?)\s+(\d{1,2}:\d{2})"
)


def render_page(url, wait_ms=4000):
    """Abre la página con un navegador headless real y devuelve el HTML
    ya con el JavaScript ejecutado (a diferencia de requests.get, que
    solo trae el HTML crudo antes de que corra el JS)."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        # espera extra por si el fixture tarda en pintarse después del
        # evento "networkidle" (common en apps que hacen requests en cadena)
        page.wait_for_timeout(wait_ms)
        html = page.content()
        browser.close()
        return html


def extract_matches(html):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)

    results = []
    for m in RESULT_PATTERN.finditer(text):
        home, s1, s2, away = m.groups()
        home, away = home.strip(), away.strip()
        if len(home) < 3 or len(away) < 3:
            continue
        results.append({"home": home, "away": away, "score": f"{s1}-{s2}", "meta": "resultado"})

    next_matches = []
    for m in NEXT_PATTERN.finditer(text):
        home, away, time = m.groups()
        home, away = home.strip(), away.strip()
        if len(home) < 3 or len(away) < 3:
            continue
        next_matches.append({"home": home, "away": away, "meta": f"próximo · {time}"})

    # de-duplicar conservando orden
    def dedup(items, keyfn):
        seen, out = set(), []
        for it in items:
            k = keyfn(it)
            if k not in seen:
                seen.add(k)
                out.append(it)
        return out

    results = dedup(results, lambda m: (m["home"], m["away"], m["score"]))[:10]
    next_matches = dedup(next_matches, lambda m: (m["home"], m["away"]))[:10]

    return results, next_matches


def scrape_league(key, cfg):
    print(f"→ Renderizando {cfg['name']} ({cfg['url']})")
    try:
        html = render_page(cfg["url"])
    except Exception as e:
        print(f"  ✗ Error al renderizar: {e}")
        return {"results": [], "next": [], "error": str(e)}

    results, next_matches = extract_matches(html)
    print(f"  ✓ {len(results)} resultados, {len(next_matches)} próximos partidos detectados")
    return {"results": results, "next": next_matches}


def dump_html_mode(key):
    """Modo debug: guarda el HTML renderizado de una liga puntual para
    que se pueda inspeccionar manualmente qué está pasando."""
    cfg = LEAGUES.get(key)
    if not cfg:
        print(f"Liga desconocida: {key}. Opciones: {list(LEAGUES.keys())}")
        return
    html = render_page(cfg["url"])
    filename = f"debug_{key}.html"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Guardado en {filename} ({len(html)} caracteres)")


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "--dump-html":
        dump_html_mode(sys.argv[2])
        return

    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "leagues": {}
    }

    for key, cfg in LEAGUES.items():
        data["leagues"][key] = scrape_league(key, cfg)

    os.makedirs("data", exist_ok=True)
    with open("data/afa.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\nListo → data/afa.json")


if __name__ == "__main__":
    main()
