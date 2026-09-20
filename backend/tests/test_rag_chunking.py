"""tests/test_rag_chunking.py — text chunking logic for the RAG pipeline."""

from app.services.text_chunker import chunk_text


def test_chunk_text_produces_overlapping_chunks():
    text = "word " * 100
    chunks = chunk_text(text, chunk_size=20, overlap=5)
    assert len(chunks) > 1
    assert all(len(c.split()) <= 20 for c in chunks)


def test_chunk_text_empty_input():
    assert chunk_text("") == []


def test_chunk_text_short_input_single_chunk():
    chunks = chunk_text("just a few words here", chunk_size=50, overlap=10)
    assert len(chunks) == 1
