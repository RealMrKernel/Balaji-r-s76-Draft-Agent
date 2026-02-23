"""
LinkedIn Post Analytics Scraper  v3.0  –  Export Button Edition
----------------------------------------------------------------
Per ogni post nell'Excel di input:
  1. Naviga alla pagina /analytics/post-summary/urn:li:activity:XXX/
  2. Clicca il pulsante "Esporta"
  3. Intercetta il file .xlsx scaricato da LinkedIn
  4. Legge i due fogli: RENDIMENTO + PRINCIPALI DATI DEMOGRAFICI
  5. Estrae anche il testo del post dalla pagina
  6. Consolida tutto in un unico Excel di output

Struttura del file esportato da LinkedIn (osservata sul file reale):
  Foglio RENDIMENTO (coppie label→valore):
    URL post, Data di pubblicazione, Ora di pubblicazione del post,
    Impressioni, Utenti raggiunti, Visitatori del profilo da questo post,
    Follower acquisiti da questo post, Reazioni, Commenti, Diffusioni post,
    Salvataggi, Invii su LinkedIn,
    Qualifica principale (reazioni), Località principale (reazioni), Settore principale (reazioni),
    Qualifica principale (commenti), Località principale (commenti), Settore principale (commenti)

  Foglio PRINCIPALI DATI DEMOGRAFICI (tabella Categoria | Valore | %):
    Dimensioni azienda, Qualifica, Località, Azienda, Settore, Anzianità

UTILIZZO:
  python linkedin_scraper.py --input posts.xlsx --output stats_output.xlsx

REQUISITI:
  pip install playwright openpyxl pandas
  playwright install chromium
"""

import argparse
import sys
import time
import re
import tempfile
from pathlib import Path
from datetime import datetime

import pandas as pd # pyre-ignore

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout # pyre-ignore
except ImportError:
    print("ERRORE: playwright non installato.")
    print("Esegui: pip install playwright && playwright install chromium")
    sys.exit(1)


# ─── utility ──────────────────────────────────────────────────────────────────

def read_input_excel(path: str) -> list:
    df = pd.read_excel(path, dtype=str)
    url_col = None
    for col in df.columns:
        if any(kw in col.lower() for kw in ("url", "link", "post", "href")):
            url_col = col
            break
    if url_col is None:
        url_col = df.columns[0]
    urls = df[url_col].dropna().str.strip().tolist()
    urls = [u for u in urls if u.startswith("http")]
    print(f"  Trovati {len(urls)} URL nella colonna '{url_col}'")
    return urls


def analytics_url(post_url: str) -> str:
    clean = post_url.strip().rstrip("/")
    m = re.search(r"(urn:li:(?:activity|ugcPost):\d+)", clean)
    if m:
        return f"https://www.linkedin.com/analytics/post-summary/{m.group(1)}/"
    m = re.search(r"activity-(\d{10,})", clean)
    if m:
        return f"https://www.linkedin.com/analytics/post-summary/urn:li:activity:{m.group(1)}/"
    return clean


def pct_str(val) -> str:
    """Converte 0.275 → '27.5%'"""
    try:
        return f"{float(val)*100:.1f}%"
    except (ValueError, TypeError):
        return str(val) if val else ""


# ─── parsing del file Excel esportato da LinkedIn ─────────────────────────────

def parse_linkedin_export(xlsx_path: str) -> dict:
    """
    Legge il file xlsx esportato da LinkedIn e restituisce un dict con
    tutti i campi estratti dai fogli RENDIMENTO e PRINCIPALI DATI DEMOGRAFICI.
    """
    result = {}

    try:
        xl = pd.ExcelFile(xlsx_path)
        sheet_names_lower = {s.lower(): s for s in xl.sheet_names}

        # ── Foglio RENDIMENTO ────────────────────────────────────────────────
        rendimento_key = next(
            (v for k, v in sheet_names_lower.items() if "rendimento" in k or "performance" in k),
            xl.sheet_names[0]
        )
        demo_key = next(
            (v for k, v in sheet_names_lower.items() if "demograf" in k or "demographic" in k),
            xl.sheet_names[1] if len(xl.sheet_names) > 1 else None
        )
        # Leggi tutti i fogli necessari mentre il file è aperto, poi chiudi subito
        df_r = pd.read_excel(xlsx_path, sheet_name=rendimento_key, header=None, dtype=str)
        df_d = pd.read_excel(xlsx_path, sheet_name=demo_key, header=0, dtype=str) if demo_key else None
        xl.close()  # chiude il file handle – fondamentale su Windows

        # Costruiamo un dizionario label→valore dalle coppie colonna 0/colonna 1
        kv = {}
        for _, row in df_r.iterrows():
            label = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            value = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
            if label and label != "nan":
                kv[label.lower()] = value

        def get(keys: list) -> str:
            for k in keys:
                for kv_key, val in kv.items():
                    if k.lower() in kv_key:
                        return val if val != "nan" else ""
            return ""

        result["post_url_export"]   = get(["url post", "post url"])
        result["post_date"]         = get(["data di pubblicazione", "publication date"])
        result["post_time"]         = get(["ora di pubblicazione", "publication time"])
        result["impressions"]       = get(["impressioni", "impressions"])
        result["unique_views"]      = get(["utenti raggiunti", "unique viewers", "reach"])
        result["profile_visits"]    = get(["visitatori del profilo", "profile visitors"])
        result["followers_gained"]  = get(["follower acquisiti", "followers gained"])
        result["reactions"]         = get(["reazioni", "reactions"])
        result["comments"]          = get(["commenti", "comments"])
        result["reposts"]           = get(["diffusioni", "reposts", "reshares"])
        result["saves"]             = get(["salvataggi", "saves"])
        result["sends"]             = get(["invii", "sends"])

        # Top reazioni
        # Il foglio ha sezioni separate per reazioni e commenti
        # Individuiamo le righe per sezione usando l'indice
        reaz_section = False
        comm_section = False
        reaz_rows = []
        comm_rows = []
        for _, row in df_r.iterrows():
            label = str(row.iloc[0]).strip().lower() if pd.notna(row.iloc[0]) else ""
            if "reazioni in evidenza" in label:
                reaz_section = True
                comm_section = False
                continue
            if "commenti in evidenza" in label:
                comm_section = True
                reaz_section = False
                continue
            if reaz_section and label:
                reaz_rows.append((str(row.iloc[0]).strip(), str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""))
            if comm_section and label:
                comm_rows.append((str(row.iloc[0]).strip(), str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""))

        def section_val(rows, keyword):
            for label, val in rows:
                if keyword.lower() in label.lower() and val and val != "nan":
                    return val
            return ""

        result["reactions_top_role"]     = section_val(reaz_rows, "qualifica")
        result["reactions_top_location"] = section_val(reaz_rows, "localit")
        result["reactions_top_industry"] = section_val(reaz_rows, "settore")
        result["comments_top_role"]      = section_val(comm_rows, "qualifica")
        result["comments_top_location"]  = section_val(comm_rows, "localit")
        result["comments_top_industry"]  = section_val(comm_rows, "settore")

        # ── Foglio PRINCIPALI DATI DEMOGRAFICI ──────────────────────────────
        if df_d is not None:
            # Colonne: Categoria | Valore | %
            col_cat = df_d.columns[0] # pyre-ignore
            col_val = df_d.columns[1] # pyre-ignore
            col_pct = df_d.columns[2] # pyre-ignore

            def top_demo(category_kw: str, n: int = 3) -> str:
                mask = df_d[col_cat].str.lower().str.contains(category_kw, na=False) # pyre-ignore
                sub = df_d[mask].head(n) # pyre-ignore
                parts = []
                for _, row in sub.iterrows():
                    val = str(row[col_val]).strip()
                    pct = pct_str(row[col_pct])
                    if val and val != "nan":
                        parts.append(f"{val} ({pct})")
                return " | ".join(parts)

            result["demo_seniority"]    = top_demo("anzianit")
            result["demo_role"]         = top_demo("qualifica")
            result["demo_industry"]     = top_demo("settore")
            result["demo_company_size"] = top_demo("dimensioni azienda")
            result["demo_location"]     = top_demo("localit")
            result["demo_company"]      = top_demo("^azienda")

    except Exception as exc:
        result["parse_error"] = str(exc)[:200] # pyre-ignore
        print(f"    ✗ Errore parsing export: {exc}")

    return result


# ─── estrazione testo post dalla pagina ───────────────────────────────────────

def extract_post_text(page_text: str) -> str:
    """
    Estrae il testo del post dalla pagina analytics (prima di 'Scoperta').
    Usata come fallback se la visita al post originale fallisce.
    """
    parts = re.split(r"\nScoperta\n", page_text, maxsplit=1)
    if len(parts) < 2:
        return ""
    block = parts[0]
    m = re.search(r".+ha pubblicato questo post\s*[•·]\s*\S+\n?", block)
    if m:
        end_idx = int(m.end())
        block = str(block)[end_idx:] # pyre-ignore
    else:
        lines = block.split("\n")
        start = next((i for i, l in enumerate(lines) if len(l.strip()) > 30 and i > 5), 0)
        start_idx = int(start)
        block = "\n".join(lines[start_idx:]) # pyre-ignore
    block = re.sub(r"\nhashtag\n", " ", block)
    block = re.sub(r"[…\.]{3}visualizza altro\s*$", "", block)
    half = len(block) // 2
    if block[:50].strip() and block[half:half+50].strip().startswith(block[:30].strip()): # pyre-ignore
        block = block[:half] # pyre-ignore
    return block.strip()


def extract_post_text_from_post_page(page_text: str) -> str:
    """
    Estrae il testo COMPLETO del post dalla pagina del post originale
    (dopo aver cliccato 'visualizza altro').
    La pagina del post ha struttura diversa da quella analytics:
    il testo si trova tra l'header autore e la sezione commenti/reazioni.
    """
    # Sanity check for "Page not found" or "Questa pagina non esiste" LinkedIn error pages
    if "Questa pagina non esiste" in page_text or "Page not found" in page_text:
        return "[PAGE NOT FOUND]"

    # Rimuovi rumore di navigazione iniziale (barra nav, notifiche, ecc.)
    # Cerca l'inizio del post: di solito dopo "• Xh" o "• Xm" (tempo relativo)
    # oppure dopo una data tipo "17 nov"
    m = re.search(
        r"ha pubblicato questo post\s*[•·][^\n]*\n"   # header autore
        r"(?:[^\n]*\n){0,3}",                           # eventuali righe accessorie
        page_text
    )
    if m:
        end_idx = int(m.end())
        block = str(page_text)[end_idx:] # pyre-ignore
    else:
        # Fallback: salta le prime 15 righe di nav
        lines = page_text.split("\n")
        start = next((i for i, l in enumerate(lines) if len(l.strip()) > 40 and i > 10), 0)
        block = "\n".join(lines[start:]) # pyre-ignore

    # Il testo del post finisce quando cominciano i commenti / reazioni
    # Indicatori di fine post:
    end_markers = [
        r"\nReazioni\n",
        r"\nCommenti\n",
        r"\nAggiungi un commento",
        r"\nRispondi",
        r"\nMi piace\s*\n",
        r"\nCondividi\n",
        r"\nInvia\n",
        r"\nPost correlati",
        r"\nPotrebbe interessarti",
        r"\nAltri post di",
        r"\n\d+ reazioni?\n",
        r"\n\d+ commenti?\n",
    ]
    earliest = len(block)
    for marker in end_markers:
        m2 = re.search(marker, block, re.IGNORECASE)
        if m2 and m2.start() < earliest:
            earliest = m2.start()
    block = block[:earliest] # pyre-ignore

    # Pulizia
    block = re.sub(r"\nhashtag\n", " ", block)
    block = re.sub(r"[…\.]{3}visualizza altro\s*", "", block)
    block = block.strip()

    # Sanity check: se troppo corto, probabilmente qualcosa è andato storto
    if len(block) < 20:
        return ""

    return block


# ─── scraping principale ──────────────────────────────────────────────────────

def scrape_post(page, post_url: str, download_dir: Path) -> dict:
    result = {
        "post_url":              post_url,
        "analytics_url":         "",
        "post_text":             "",
        "post_date":             "",
        "post_time":             "",
        "impressions":           "",
        "unique_views":          "",
        "profile_visits":        "",
        "followers_gained":      "",
        "reactions":             "",
        "comments":              "",
        "reposts":               "",
        "saves":                 "",
        "sends":                 "",
        "reactions_top_role":    "",
        "reactions_top_location":"",
        "reactions_top_industry":"",
        "comments_top_role":     "",
        "comments_top_location": "",
        "comments_top_industry": "",
        "demo_seniority":        "",
        "demo_role":             "",
        "demo_industry":         "",
        "demo_company_size":     "",
        "demo_location":         "",
        "demo_company":          "",
        "scraped_at":            datetime.now().strftime("%Y-%m-%d %H:%M"),
        "error":                 "",
    }

    try:
        a_url = None
        
        # ── 1. Visita prima il post originale per estrarre il testo e l'URL Analytics corretto ──────────
        try:
            page.goto(post_url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)

            # Controllo redirect login
            if any(x in page.url for x in ("authwall", "/login", "checkpoint", "uas/authenticate")):
                result["error"] = "Redirect al login – sessione scaduta"
                print("    ✗ Redirect login")
                return result

            # Estrai l'URL Analytics corretto dalla pagina o dalla navigazione
            try:
                # 1. Cerca il link del pulsante "Visualizza analisi" (se presente)
                analytics_link = page.query_selector("a[href*='/analytics/post-summary/']")
                if analytics_link:
                    href = analytics_link.get_attribute("href")
                    if href:
                        a_url = href if href.startswith("http") else f"https://www.linkedin.com{href}"
            except Exception:
                pass
                
            if not a_url:
                # 2. Se l'URL finale della pagina è cambiato in activity-...
                if "activity-" in page.url:
                    m = re.search(r"activity-(\d{10,})", page.url)
                    if m:
                        a_url = f"https://www.linkedin.com/analytics/post-summary/urn:li:activity:{m.group(1)}/"
            
            if not a_url:
                # 3. Cerca l'URN dell'attività direttamente nel codice HTML (meta tags)
                html = page.content()
                m = re.search(r"urn:li:activity:\d{10,}", html)
                if m:
                    a_url = f"https://www.linkedin.com/analytics/post-summary/{m.group(0)}/"
            
            # 4. Fallback (vecchio metodo regex stringa)
            if not a_url:
                a_url = analytics_url(post_url)

            # Clicca tutti i pulsanti "visualizza altro" / "see more" presenti per leggere il testo
            for see_more_sel in [
                "button.feed-shared-inline-show-more-text__see-more-less-toggle",
                "button:has-text('visualizza altro')",
                "button:has-text('…visualizza altro')",
                "button:has-text('see more')",
                "[aria-label*='visualizza altro']",
            ]:
                try:
                    btns = page.query_selector_all(see_more_sel)
                    for btn in btns:
                        if btn.is_visible():
                            btn.click()
                            time.sleep(0.5)
                except Exception:
                    pass

            time.sleep(1)
            post_page_text = page.inner_text("body")
            
            # Check for dead page before extracting
            if "Questa pagina non esiste" in post_page_text or "Page not found" in post_page_text:
                result["error"] = "Post non trovato o eliminato"
                print("    ✗ Post non trovato")
                return result
                
            result["post_text"] = extract_post_text_from_post_page(post_page_text)
        except Exception as e_txt:
            print(f"    ⚠ Impossibile leggere testo dal post originale: {e_txt}")
            result["post_text"] = ""
            if not a_url:
                a_url = analytics_url(post_url)

        result["analytics_url"] = a_url or ""
        print(f"    → Analytics: {a_url}")

        # ── 2. Naviga alla pagina analytics, trovata dinamicamente ─────────────
        page.goto(a_url, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_selector(
                "button:has-text('Esporta'), button:has-text('Export'), "
                "[aria-label*='Esporta'], [aria-label*='Export']",
                timeout=15000
            )
        except PlaywrightTimeout:
            pass
        time.sleep(3)

        page_text = page.inner_text("body")  # usato nel fallback stats

        # ── 4. Clicca "Esporta" e intercetta il download ──────────────────
        export_btn = None
        for selector in [
            "button:has-text('Esporta')",
            "button:has-text('Export')",
            "[aria-label*='Esporta']",
            "[aria-label*='Export']",
            "text=Esporta",
            "text=Export",
        ]:
            try:
                btn = page.query_selector(selector)
                if btn and btn.is_visible():
                    export_btn = btn
                    break
            except Exception:
                pass

        if not export_btn:
            result["error"] = "Pulsante Esporta non trovato"
            print("    ✗ Pulsante Esporta non trovato")
            # Fallback: prova a estrarre le stats dal testo della pagina
            _fill_stats_from_text(result, page_text)
            return result

        # Intercetta il download
        with page.expect_download(timeout=30000) as download_info:
            export_btn.click() # pyre-ignore

        download = download_info.value

        # Salva il file nella cartella temporanea
        file_name = download.suggested_filename or f"export_{int(time.time())}.xlsx"
        save_path = download_dir / file_name
        download.save_as(str(save_path))
        print(f"    ↓ Download: {file_name}")

        # ── 5. Parsa il file scaricato ─────────────────────────────────────
        export_data = parse_linkedin_export(str(save_path))
        result.update(export_data)

        # L'URL nel file export può differire (ugcPost vs activity); teniamo l'originale
        result["post_url"] = post_url

        # Pulizia file temporaneo
        try:
            save_path.unlink()
        except Exception:
            pass

        print(
            f"    ✓  impr={result['impressions'] or '—':>6}  "
            f"reach={result['unique_views'] or '—':>6}  "
            f"react={result['reactions'] or '—':>4}  "
            f"comm={result['comments'] or '—':>3}  "
            f"testo={len(result['post_text'])}ch"
        )

    except PlaywrightTimeout:
        result["error"] = "Timeout"
        print("    ✗ Timeout")
    except Exception as exc:
        result["error"] = str(exc)[:150] # pyre-ignore
        print(f"    ✗ Errore: {exc}")

    return result


def _fill_stats_from_text(result: dict, text: str):
    """Fallback: estrae statistiche dal testo della pagina se il download fallisce."""
    def after(label):
        m = re.search(rf"^{re.escape(label)}\n+([\d\.,]+)", text, re.MULTILINE)
        return re.sub(r"[.,](?=\d{{3}}(?!\d))", "", m.group(1)) if m else ""

    m = re.search(r"Scoperta\n+([\d\.,]+)", text)
    if m: result["impressions"] = re.sub(r"[.,](?=\d{3}(?!\d))", "", m.group(1))
    m = re.search(r"Impressioni\n+([\d\.,]+)", text)
    if m: result["unique_views"] = re.sub(r"[.,](?=\d{3}(?!\d))", "", m.group(1))
    result["reactions"] = after("Reazioni")
    result["comments"]  = after("Commenti")
    result["reposts"]   = after("Diffusioni post")
    result["saves"]     = after("Salvataggi")
    result["sends"]     = after("Invii su LinkedIn")


class LinkedInScraper:
    """Class wrapper for the LinkedIn scraper to integrate with the agent"""
    def __init__(self, headless: bool = False, delay: float = 4.0):
        self.headless = headless
        self.delay = delay
        self.auth_file = Path(__file__).parent.parent / "data" / "auth.json"

    def scrape_urls(self, urls: list[str]) -> list[dict]:
        """Scrape a list of LinkedIn post URLs and return extracted data dicts."""
        records = []
        tmp_dir_obj = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        tmp_dir = tmp_dir_obj.name
        
        try:
            download_dir = Path(tmp_dir)

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=self.headless,
                    args=["--start-maximized"],
                    downloads_path=str(download_dir),
                )
                # If auth file exists, load it
                context_args = {
                    "viewport": {"width": 1400, "height": 900},
                    "accept_downloads": True,
                    "user_agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                }
                
                if self.auth_file.exists():
                    print("🔄 Caricamento sessione salvata...")
                    context_args["storage_state"] = str(self.auth_file)
                    
                context = browser.new_context(**context_args)
                page = context.new_page()

                print("\n🔐 Apro LinkedIn ...")
                page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
                
                # Check if we are logged in by looking for global nav
                is_logged_in = False
                try:
                    page.wait_for_selector(
                        ".search-global-typeahead, .global-nav__me-photo, "
                        "[data-test-global-nav-search], #global-nav-search",
                        timeout=5000
                    )
                    is_logged_in = True
                    print("   ✅  Login attivo rilevato – avvio scraping …\n")
                except PlaywrightTimeout:
                    is_logged_in = False

                # If headless is True but we aren't logged in, fail fast rather than stalling
                if not is_logged_in and self.headless:
                    print("   ❌ Errore: Sessione inesistente o scaduta.")
                    print("      Disattiva 'Run in Background' e lancia lo scraping per effettuare il login!")
                    return [{"post_url": u, "error": "Login required. Run without headless mode first."} for u in urls]
                
                # If visible and not logged in, give the user time to do it manually
                if not is_logged_in and not self.headless:
                    print("   👀 Attendo fino a 3 minuti per permetterti di fare il login manualmente...")
                    page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
                    try:
                        page.wait_for_selector(
                            ".search-global-typeahead, .global-nav__me-photo, "
                            "[data-test-global-nav-search], #global-nav-search",
                            timeout=180000
                        )
                        print("   ✅  Login manuale rilevato!")
                        # Save the state for future headless runs!
                        self.auth_file.parent.mkdir(exist_ok=True)
                        context.storage_state(path=str(self.auth_file))
                        print("   💾 Sessione salvata con successo per i futuri avvii in background!")
                    except PlaywrightTimeout:
                        print("   ⚠️  Timeout login, procedo comunque (potrebbe fallire o richiedere authwall) …\n")

                for i, url in enumerate(urls, start=1):
                    print(f"[{i:>3}/{len(urls)}] {url[:90]}")
                    record = scrape_post(page, url, download_dir)
                    records.append(record)

                    if i < len(urls):
                        time.sleep(self.delay)

                browser.close()

        finally:
            try:
                tmp_dir_obj.cleanup()
            except Exception:
                pass
                
        return records

def clean_scraped_post_data(post_data: dict) -> dict:
    """
    Takes the raw text from the scraper, processes hashtags, cleans boilerplate 
    profiles and footers, and normalizes the newlines into spaces.
    Returns the updated post_data dictionary.
    """
    import re
    
    original_title = post_data.get("title", "")
    original_body = post_data.get("body", "")

    # Clean the body (remove header)
    lines = original_body.split("\n")
    start_index = 0
    for i, line in enumerate(lines):
        if "Visibile a tutti su LinkedIn e altrove" in line:
            start_index = i + 1
            break
            
    # Clean the body (remove footer)
    end_index = len(lines)
    for i in range(start_index, len(lines)):
        line = lines[i].strip()
        if line == "Attiva per visualizzare un’immagine più grande," or line == "Il documento è stato caricato" or " altre persone" in line:
            end_index = i
            # Step back if the previous line is a number (e.g. "114" people liked)
            if end_index > 0 and lines[end_index - 1].strip().isdigit():
                end_index -= 1
            break
            
    # Also trim trailing empty lines before the footer
    while end_index > start_index and not lines[end_index - 1].strip():
        end_index -= 1

    cleaned_body_lines = lines[start_index:end_index]
    
    # Extract Tags
    tags = []
    
    # Walk backwards from the end of the cleaned body to find the line with tags
    for i in range(len(cleaned_body_lines) - 1, -1, -1):
        line = cleaned_body_lines[i]
        
        if "#" in line:
            extracted_tags = re.findall(r'#\w+', line)
            if extracted_tags:
                for tag in extracted_tags:
                    if tag not in tags:
                        tags.append(tag)
                        
                for tag in extracted_tags:
                    line = re.sub(rf'{tag}(?!\w)', '', line)
                
                cleaned_body_lines[i] = line.strip()
                
                if not cleaned_body_lines[i]:
                    cleaned_body_lines.pop(i)
                break
            
    # Replace any formatting \n (or stray \r) with spaces to form a single line of text
    cleaned_body_lines = [l.replace('\r', '').replace('\n', ' ').strip() for l in cleaned_body_lines]
            
    # Re-join on space
    cleaned_body_text = " ".join(l for l in cleaned_body_lines if l).strip()
    # collapse multiple spaces into one space
    cleaned_body_text = re.sub(r'\s+', ' ', cleaned_body_text).strip()
    
    # Extract new title (first sentence or up to 150 chars)
    new_title = ""
    if cleaned_body_text:
        if len(cleaned_body_text) > 150:
            first_sentence = cleaned_body_text.split('.')[0] + "."
            new_title = first_sentence if len(first_sentence) < 150 else cleaned_body_text[:147] + "..."
        else:
            new_title = cleaned_body_text

    post_data["title"] = new_title
    post_data["body"] = cleaned_body_text
    post_data["tags"] = tags
    
    return post_data

def get_post_id_from_url(analytics_url: str, post_url: str, fallback_idx: int) -> str:
    """
    Extracts the URN ID from the analytics/post URL to use as file ID.
    If none is found, relies on a fallback with timestamp.
    """
    import re
    from datetime import datetime
    
    url_to_parse = analytics_url if analytics_url else post_url
    
    m = re.search(r"urn:li:activity:(\d{10,})", url_to_parse)
    if m:
        return f"urn_li_activity_{m.group(1)}"
        
    m2 = re.search(r"activity-(\d{10,})", url_to_parse)
    if m2:
        return f"urn_li_activity_{m2.group(1)}"
        
    return f"scraped_{datetime.now().strftime('%Y%m%d%H%M%S')}_{fallback_idx}"
