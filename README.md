# Kit de actualización automática — Ligas argentinas

Esto arma la parte que la página web sola no puede resolver: mantener
actualizadas las 4 ligas del ascenso argentino sin depender de una API
paga ni de que alguien las edite a mano.

## Cómo funciona

```
GitHub Actions (cada 3hs)
        │
        ▼
  scrape_afa.py  →  lee promiedos.com.ar  →  data/afa.json (se commitea solo)
        │
        ▼
raw.githubusercontent.com/TU_USUARIO/TU_REPO/main/data/afa.json
        │
        ▼
  marcador-central.html (fetch automático, con CORS habilitado por GitHub)
```

No necesitás servidor, ni pagar hosting, ni dejar tu computadora prendida.
GitHub Actions lo corre por vos, gratis, en un repo público.

## Paso a paso

1. **Creá un repositorio público en GitHub** (por ejemplo `mi-marcador-afa`).
2. Subí a ese repo:
   - `scrape_afa.py`
   - la carpeta `.github/workflows/update-data.yml`
3. Andá a la pestaña **Actions** del repo y activalo si te lo pide.
4. Corré el workflow una vez a mano: **Actions → Actualizar datos del
   ascenso argentino → Run workflow**. Esto va a crear `data/afa.json`.
5. **Revisá el resultado.** Abrí `data/afa.json` en GitHub. Si ves los
   partidos bien, ¡genial! Si ves arrays vacíos (`"results": []`), el
   scraper no pudo interpretar el HTML del sitio — ver la sección
   "Si no funciona a la primera" más abajo.
6. Una vez que `data/afa.json` tenga datos reales, copiá esta URL
   (reemplazando usuario y repo):

   ```
   https://raw.githubusercontent.com/TU_USUARIO/TU_REPO/main/data/afa.json
   ```

7. Pegala en el panel ⚙ de `marcador-central.html`, en el campo
   "URL de datos del ascenso argentino". A partir de ahí, la página va a
   traer esos datos solos cada vez que se abra (y GitHub Actions los va
   a mantener frescos cada 3 horas).

## Si no funciona a la primera

Es esperable — escribí este scraper sin poder probarlo contra el sitio
en vivo. Para arreglarlo:

1. Corré localmente:
   ```
   pip install requests beautifulsoup4
   python scrape_afa.py
   ```
2. Mirá qué liga quedó vacía en la consola.
3. Abrí esa URL de Promiedos en el navegador, clic derecho → "Inspeccionar"
   sobre un partido, y fijate qué clase o tag envuelve cada partido
   (por ejemplo `<div class="match-card">` o similar).
4. En `scrape_afa.py`, buscá los comentarios `# AJUSTAR ACÁ` y reemplazá
   el selector genérico por el real que encontraste.
5. Volvé a correr el script hasta que `data/afa.json` te cierre.

Si en algún momento preferís que yo mismo revise y ajuste el scraper con
el HTML real, pegame acá el HTML de una de esas páginas (podés copiarlo
con "Ver código fuente" o Inspeccionar → Copiar → Copiar elemento) y te
lo dejo funcionando a medida.

## Alternativa sin scraping

Si en algún momento preferís no mantener un scraper, la alternativa
"cero mantenimiento" es una API paga con cobertura completa del ascenso
argentino, como **FootyStats** (footystats.org/es/api, desde £29.99/mes,
40 ligas incluidas). Con eso alcanza para conectar las 4 ligas
argentinas igual que ya está conectado LaLiga/Premier/Serie A/Champions
en `marcador-central.html`, sin necesidad del scraper.
