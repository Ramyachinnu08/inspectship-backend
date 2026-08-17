"""
Simple RAG (Retrieval Augmented Generation) service.

Stores uploaded documents as text chunks in the database, then for a given
question finds the most relevant chunks (keyword overlap scoring) and feeds
them to Gemini so answers are grounded in YOUR documents.

No external vector DB needed - uses simple but effective keyword scoring.
For larger scale you can later swap in embeddings + a vector store.
"""
import re
import json

# ─── Text chunking ───────────────────────────────────────
def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100):
    """Split text into overlapping chunks by characters (word-boundary aware)."""
    text = re.sub(r'\s+', ' ', text or '').strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        # try to end on a sentence/space boundary
        if end < len(text):
            last_period = chunk.rfind('. ')
            last_space = chunk.rfind(' ')
            cut = last_period if last_period > chunk_size * 0.6 else last_space
            if cut > 0:
                chunk = chunk[:cut + 1]
                end = start + cut + 1
        chunks.append(chunk.strip())
        start = end - overlap
        if start < 0:
            start = 0
    return [c for c in chunks if c]


# ─── Keyword scoring for retrieval ───────────────────────
_STOP = set("a an the is are was were of to in on for and or with at by from as it this that be have has".split())


def _keywords(text: str):
    words = re.findall(r'[a-z0-9]+', (text or '').lower())
    return [w for w in words if w not in _STOP and len(w) > 2]


def score_chunk(chunk: str, query_words) -> int:
    """Count how many query keywords appear in the chunk."""
    chunk_words = set(_keywords(chunk))
    return sum(1 for w in query_words if w in chunk_words)


def retrieve(question: str, chunks: list, top_k: int = 4):
    """Return the top_k most relevant chunks for the question."""
    if not chunks:
        return []
    query_words = _keywords(question)
    if not query_words:
        return chunks[:top_k]
    scored = [(score_chunk(c, query_words), c) for c in chunks]
    scored.sort(key=lambda x: x[0], reverse=True)
    # keep only chunks with at least 1 keyword hit
    relevant = [c for s, c in scored if s > 0][:top_k]
    return relevant if relevant else []


# ─── PDF / text extraction ───────────────────────────────
def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF using pypdf."""
    try:
        from pypdf import PdfReader
        import io
        reader = PdfReader(io.BytesIO(file_bytes))
        text = []
        for page in reader.pages:
            text.append(page.extract_text() or '')
        return '\n'.join(text)
    except Exception as e:
        print(f"[rag] PDF extract failed: {e}")
        return ''


def extract_text(filename: str, file_bytes: bytes) -> str:
    """Extract text from PDF or plain text files."""
    name = (filename or '').lower()
    if name.endswith('.pdf'):
        return extract_text_from_pdf(file_bytes)
    # treat everything else as text
    try:
        return file_bytes.decode('utf-8', errors='ignore')
    except Exception:
        return ''