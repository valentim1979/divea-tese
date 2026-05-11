import os
import chromadb
from chromadb.utils import embedding_functions
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

ARTIGOS_DIR = '/home/valentim/divea/data/artigos/Bibliografias'
CHROMA_DIR = '/home/valentim/divea/data/chromadb'

# Embedding com nomic via Ollama
ef = embedding_functions.OllamaEmbeddingFunction(
    url="http://localhost:11434/api/embeddings",
    model_name="nomic-embed-text"
)

client = chromadb.PersistentClient(path=CHROMA_DIR)
collection = client.get_or_create_collection(
    name="artigos_divea",
    embedding_function=ef
)

splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

pdfs = [f for f in os.listdir(ARTIGOS_DIR) if f.endswith('.pdf')]
print(f"Indexando {len(pdfs)} artigos...")

for i, pdf in enumerate(pdfs):
    path = os.path.join(ARTIGOS_DIR, pdf)
    try:
        loader = PyPDFLoader(path)
        pages = loader.load()
        chunks = splitter.split_documents(pages)
        
        ids = [f"{pdf}_{j}" for j in range(len(chunks))]
        texts = [c.page_content for c in chunks]
        metas = [{"source": pdf, "page": c.metadata.get("page", 0)} for c in chunks]
        
        collection.add(documents=texts, ids=ids, metadatas=metas)
        print(f"[{i+1}/{len(pdfs)}] {pdf} — {len(chunks)} chunks")
    except Exception as e:
        print(f"[ERRO] {pdf}: {e}")

print(f"\nIndexacao concluida. Total: {collection.count()} chunks.")
