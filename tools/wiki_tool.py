import os
import frontmatter
import base64
import fitz  # PyMuPDF
import io
import json
from PIL import Image
from langchain_core.tools import tool
from datetime import datetime

WIKI_DIR = "persona/wiki"
ENTRIES_DIR = os.path.join(WIKI_DIR, "entries")
INDEX_PATH = os.path.join(WIKI_DIR, "index.md")
RAW_DIR = os.path.join(WIKI_DIR, "raw")

def ensure_dirs():
    os.makedirs(ENTRIES_DIR, exist_ok=True)
    os.makedirs(RAW_DIR, exist_ok=True)
    if not os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "w") as f:
            f.write("# LLM Wiki Index\n\nBenvenuto nell'archivio di conoscenza di Absalom.\n\n## Voci\n")

def _optimize_image(img_bytes, max_size=2000):
    """Ridimensiona e ottimizza l'immagine prima di inviarla all'LLM."""
    try:
        img = Image.open(io.BytesIO(img_bytes))
        # Converte in RGB per compatibilità JPEG
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception as e:
        print(f"Errore ottimizzazione immagine: {e}")
        return img_bytes

@tool
def wiki_ingest_raw():
    """Ingerisce TUTTI i file presenti nella cartella 'raw' della Wiki.
    Supporta .txt, .md, .pdf, .jpg, .png.
    I PDF vengono convertiti in immagini. Le immagini vengono ottimizzate.
    Tutti i file vengono eliminati dopo la lettura.
    """
    ensure_dirs()
    files = [f for f in os.listdir(RAW_DIR) if not f.startswith(".")]
    if not files:
        return "La cartella 'raw' è vuota. Nessun file da ingerire."
    
    # Risultato cumulativo per tutti i file
    final_result = {
        "type": "media_list",
        "media": [],
        "text_blocks": [],
        "text_info": f"Ho trovato {len(files)} file da elaborare."
    }
    
    processed_count = 0
    errors = []

    for filename in files:
        filepath = os.path.join(RAW_DIR, filename)
        ext = os.path.splitext(filename)[1].lower()
        
        try:
            if ext in [".txt", ".md", ".log"]:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                final_result["text_blocks"].append({
                    "filename": filename,
                    "content": content
                })
                
            elif ext == ".pdf":
                doc = fitz.open(filepath)
                # Limite di 5 pagine per file se ci sono più file, altrimenti 10
                max_p = 5 if len(files) > 1 else 10
                num_pages = min(len(doc), max_p)
                for i in range(num_pages):
                    page = doc.load_page(i)
                    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)) # Ridotto leggermente lo zoom per velocità
                    img_data = pix.tobytes("jpeg")
                    optimized_data = _optimize_image(img_data)
                    final_result["media"].append({
                        "mime": "image/jpeg",
                        "data": base64.b64encode(optimized_data).decode("utf-8"),
                        "name": f"{filename}_pag_{i+1}.jpg"
                    })
                doc.close()
                
            elif ext in [".jpg", ".jpeg", ".png"]:
                with open(filepath, "rb") as f:
                    img_data = f.read()
                optimized_data = _optimize_image(img_data)
                final_result["media"].append({
                    "mime": "image/jpeg",
                    "data": base64.b64encode(optimized_data).decode("utf-8"),
                    "name": filename
                })
            else:
                errors.append(f"Formato '{ext}' non supportato per {filename}")
                continue
                
            # Elimina il file dopo l'acquisizione riuscita
            os.remove(filepath)
            processed_count += 1
            
        except Exception as e:
            errors.append(f"Errore su {filename}: {str(e)}")

    final_result["text_info"] = f"Elaborati {processed_count} file con successo. "
    if errors:
        final_result["text_info"] += "Note: " + "; ".join(errors)
        
    return f"__INGEST_DATA__:{json.dumps(final_result)}"

@tool
def wiki_list_entries():
    """Elenca tutti i titoli delle voci presenti nella Wiki (l'archivio di conoscenza).
    Usa questo tool per avere una panoramica completa di tutto ciò che Absalom ha memorizzato o archiviato.
    """
    ensure_dirs()
    entries = [f for f in os.listdir(ENTRIES_DIR) if f.endswith(".md")]
    if not entries:
        return "La Wiki è attualmente vuota."
    
    titles = [f[:-3].replace("_", " ") for f in entries]
    return "Voci presenti nella Wiki:\n- " + "\n- ".join(titles)

@tool
def wiki_read(topic: str):
    """Legge il contenuto di una specifica voce della Wiki.
    
    Parametri:
    - topic: Il titolo della voce da leggere (es. 'Integrazione Telegram').
    """
    ensure_dirs()
    filename = topic.strip().replace(" ", "_") + ".md"
    filepath = os.path.join(ENTRIES_DIR, filename)
    
    if not os.path.exists(filepath):
        return f"Voce '{topic}' non trovata nella Wiki."
    
    post = frontmatter.load(filepath)
    content = post.content
    metadata = post.metadata
    
    res = f"--- TITOLO: {topic} ---\n"
    res += f"Ultimo aggiornamento: {metadata.get('updated_at', 'Sconosciuto')}\n"
    res += f"Categoria: {metadata.get('category', 'Generale')}\n\n"
    res += content
    return res

@tool
def wiki_write(topic: str, content: str, category: str = "Generale"):
    """Crea o aggiorna una voce nella Wiki.
    
    Parametri:
    - topic: Il titolo della voce (es. 'Integrazione Telegram').
    - content: Il contenuto in formato Markdown.
    - category: Una categoria opzionale per organizzare la voce.
    """
    ensure_dirs()
    filename = topic.strip().replace(" ", "_") + ".md"
    filepath = os.path.join(ENTRIES_DIR, filename)
    
    post = frontmatter.Post(content)
    post['updated_at'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    post['category'] = category
    
    with open(filepath, "wb") as f:
        frontmatter.dump(post, f)
    
    # Aggiorna l'indice
    _update_index()
    
    return f"Ho aggiornato la voce '{topic}' nella Wiki."

@tool
def wiki_search(query: str):
    """Cerca nell'archivio di conoscenza (Wiki) di Absalom. 
    Usa questo tool quando l'utente chiede informazioni su argomenti specifici "memorizzati" o "archiviati" (es. geografia, storia, note).
    Analizza titoli, contenuti e categorie delle voci.
    """
    ensure_dirs()
    query = query.lower().strip()
    
    # Lista di stop-words comuni da ignorare nella ricerca per keywords
    stop_words = {"il", "lo", "la", "i", "gli", "le", "di", "a", "da", "in", "con", "su", "per", "tra", "fra", "che", "degli", "delle", "parlami"}
    keywords = [w for w in query.split() if w not in stop_words and len(w) > 2]
    
    if not keywords:
        keywords = [query] # Se non restano keyword, usa la query originale

    matches = {} # Usiamo un dizionario per pesare i risultati

    for filename in os.listdir(ENTRIES_DIR):
        if filename.endswith(".md"):
            filepath = os.path.join(ENTRIES_DIR, filename)
            post = frontmatter.load(filepath)
            content = post.content.lower()
            title = filename[:-3].replace("_", " ").lower()
            category = str(post.metadata.get("category", "")).lower()
            
            score = 0
            for kw in keywords:
                # Priorità al titolo
                if kw in title:
                    score += 10
                # Categoria
                if kw in category:
                    score += 5
                # Contenuto
                if kw in content:
                    score += 1
            
            if score > 0:
                matches[filename[:-3].replace("_", " ")] = score
    
    if not matches:
        return f"Nessun risultato trovato per '{query}'."
    
    # Ordina per score decrescente
    sorted_matches = sorted(matches.items(), key=lambda x: x[1], reverse=True)
    
    res = f"Risultati della ricerca per '{query}':\n"
    for title, score in sorted_matches:
        res += f"- {title}\n"
    
    return res
    
def _update_index():
    entries = [f for f in os.listdir(ENTRIES_DIR) if f.endswith(".md")]
    with open(INDEX_PATH, "w") as f:
        f.write("# LLM Wiki Index\n\n")
        f.write(f"Ultimo aggiornamento indice: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("## Voci Archiviate\n")
        for e in sorted(entries):
            title = e[:-3].replace("_", " ")
            f.write(f"- [[{title}]]\n")
