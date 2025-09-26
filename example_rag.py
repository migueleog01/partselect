# server.py
from mcp.server.fastmcp import FastMCP
from typing import List, Dict, Any, Optional
from pathlib import Path
import json, os, hashlib

# --- Minimal FAISS + SentenceTransformers RAG ---
import faiss
from sentence_transformers import SentenceTransformer

mcp = FastMCP("PartSelect MCP Server")

# =========================
# INTERNAL RAG COMPONENTS
# =========================
INDEX_DIR = Path(".rag"); INDEX_DIR.mkdir(exist_ok=True)
INDEX_FILE = INDEX_DIR / "repairs.faiss"
META_FILE  = INDEX_DIR / "repairs.meta.jsonl"
MODEL_NAME = "intfloat/e5-small-v2"  # small/fast/good

_model = None               # SentenceTransformer model
_index = None               # faiss.IndexFlatIP
_meta: List[Dict[str,Any]] = []  # [{id, text, source, appliance_type, extra?...}]

def _load_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model

def _embed(texts: List[str]):
    model = _load_model()
    # (For best results with e5: prefix "query: " for queries, "passage: " for chunks)
    return model.encode(texts, normalize_embeddings=True)

def _hash(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:10]

def _chunk_text(s: str, max_chars=2200, overlap=300) -> List[str]:
    # Char-based chunking (simple + robust). Swap for token-based if you like.
    step = max_chars - overlap
    return [s[i:i+max_chars] for i in range(0, len(s), step)] if s else []

def _appliance_from_filename(path: Path) -> str:
    name = path.stem.lower()
    for key in ("dishwasher","refrigerator","fridge"):
        if key in name:
            return "Refrigerator" if key == "fridge" else key.capitalize()
    return "General"

def _iter_docs_from_json(path: Path):
    """
    Normalize YOUR saved repair JSON into flat text records.
    Adjust fields below to match your schema.
    Expected shapes handled:
      - list of issue objects
      - dict with "items": [...]
      - single dict (wrapped)
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    items = raw if isinstance(raw, list) else raw.get("items", [raw])

    for obj in items:
        # Choose fields to index. Tune to your schema.
        parts = []
        for k in ("issue","title","symptom","description","summary","steps","causes","fix","how_to","notes"):
            v = obj.get(k)
            if isinstance(v, list):
                v = " | ".join(map(str, v))
            if v:
                parts.append(f"{k}: {v}")
        text = "\n".join(parts).strip()
        if text:
            yield {
                "text": text,
                "source": path.name,
                "appliance_type": obj.get("appliance_type") or _appliance_from_filename(path),
                "raw": obj
            }

def _persist_index(vectors, meta):
    global _index, _meta
    dim = vectors.shape[1]
    _index = faiss.IndexFlatIP(dim)  # cosine if vectors are normalized
    _index.add(vectors)
    faiss.write_index(_index, str(INDEX_FILE))
    with META_FILE.open("w", encoding="utf-8") as f:
        for m in meta:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    _meta = meta

def _load_index_from_disk():
    global _index, _meta
    if INDEX_FILE.exists() and META_FILE.exists():
        _index = faiss.read_index(str(INDEX_FILE))
        _meta = [json.loads(line) for line in META_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]

def _build_or_load_index(data_paths: List[str], rebuild: bool = False):
    if (not rebuild) and INDEX_FILE.exists() and META_FILE.exists():
        _load_index_from_disk()
        return {"status":"loaded", "docs": len(_meta)}

    meta: List[Dict[str,Any]] = []
    texts: List[str] = []

    for p in data_paths:
        fp = Path(p)
        for doc in _iter_docs_from_json(fp):
            chunks = _chunk_text(doc["text"])
            for i, ch in enumerate(chunks):
                cid = f"{fp.name}#{_hash(ch)}-{i}"
                meta.append({
                    "id": cid,
                    "text": ch,
                    "source": doc["source"],
                    "appliance_type": doc["appliance_type"]
                })
                texts.append(ch)

    if not texts:
        return {"status":"no_text"}

    vecs = _embed(texts)
    _persist_index(vecs, meta)
    return {"status":"indexed", "docs": len(meta)}

def _ensure_index_loaded():
    if _index is None:
        _load_index_from_disk()

def _retrieve(question: str, k: int = 8, appliance_type: Optional[str] = None):
    _ensure_index_loaded()
    if _index is None:
        return {"error": "RAG index not built yet."}

    qvec = _embed([f"query: {question}"])[0].reshape(1,-1)
    # over-retrieve then filter by appliance_type
    K = max(k*4, 16)
    scores, idxs = _index.search(qvec, K)

    results = []
    for i, score in zip(idxs[0], scores[0]):
        if i == -1:
            continue
        m = _meta[i]
        if appliance_type and m.get("appliance_type","").lower() != appliance_type.lower():
            continue
        results.append({
            "id": m["id"],
            "source": m["source"],
            "appliance_type": m["appliance_type"],
            "score": float(score),
            "text": m["text"]
        })
        if len(results) >= k:
            break

    return {"question": question, "results": results}

# =========================
# PUBLIC MCP TOOL (unchanged name)
# =========================
@mcp.tool()
def get_repair_guides(appliance_type: str = "Dishwasher") -> dict:
    """
    RAG-backed repair guidance for the given appliance type.
    Returns a compact structure the client LLM can turn into prose.
    """
    try:
        q = f"List the most common {appliance_type} problems, symptoms, causes, and typical fixes."
        hits = _retrieve(q, k=12, appliance_type=appliance_type)
        if "error" in hits:
            return hits

        # Light packaging: group by first line as an "issue" title
        buckets: Dict[str, List[Dict[str,Any]]] = {}
        for r in hits["results"]:
            first_line = r["text"].splitlines()[0].strip()[:140]
            key = first_line.lower()
            buckets.setdefault(key, []).append(r)

        issues = []
        for key, group in buckets.items():
            group.sort(key=lambda x: x["score"], reverse=True)
            top = group[0]
            # Short preview for LLM grounding
            preview = "\n".join(top["text"].splitlines()[:6])
            issues.append({
                "issue": top["text"].splitlines()[0].strip(),
                "preview": preview,
                "citations": [{"id": g["id"], "source": g["source"], "score": g["score"]} for g in group[:3]]
            })

        issues.sort(key=lambda x: x["citations"][0]["score"], reverse=True)
        return {
            "appliance_type": appliance_type,
            "query": q,
            "issues": issues[:8],
            "note": "Grounded in local JSON corpus via RAG. Cite with [id] (source)."
        }
    except Exception as e:
        return {"error": f"get_repair_guides failed: {e}"}

# =========================
# (OPTIONAL) your existing scraping tool stays or can be removed
# =========================
# from utils import scrape_partselect_product
# @mcp.tool()
# def get_part_detail(part_select_number: str) -> dict: ...

# =========================
# BOOTSTRAP INDEX ON START
# =========================
if __name__ == "__main__":
    # Point to your saved JSONs (adjust paths)
    DATA = [
        "data/repairs_dishwasher.json",
        "data/repairs_refrigerator.json",
        "data/repairs_washer.json",
        "data/repairs_dryer.json",
    ]
    print(_build_or_load_index(DATA, rebuild=not INDEX_FILE.exists()))
    mcp.run()
