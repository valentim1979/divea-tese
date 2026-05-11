import chromadb
from chromadb.utils import embedding_functions
import requests
import json
import os
import hashlib

CHROMA_DIR = '/home/valentim/divea/data/chromadb'
CACHE_FILE = '/home/valentim/divea/data/processed/rag_cache.json'

ef = embedding_functions.OllamaEmbeddingFunction(
    url="http://localhost:11434/api/embeddings",
    model_name="nomic-embed-text"
)

client = chromadb.PersistentClient(path=CHROMA_DIR)
collection = client.get_collection(name="artigos_divea", embedding_function=ef)

# Perguntas pre-carregadas
PERGUNTAS_FREQUENTES = [
    "Quais são as melhores práticas para dashboards de vigilância epidemiológica?",
    "Como interpretar o canal endêmico de SRAG?",
    "Quais modelos de machine learning são usados para previsão de surtos?",
    "O que é vigilância sindrômica e como ela complementa a vigilância laboratorial?",
    "Como o TFT se compara ao LSTM para séries temporais epidemiológicas?",
]

def carregar_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}

def salvar_cache(cache):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def hash_pergunta(pergunta):
    return hashlib.md5(pergunta.lower().strip().encode()).hexdigest()

def consultar(pergunta, usar_cache=True):
    cache = carregar_cache()
    chave = hash_pergunta(pergunta)
    
    if usar_cache and chave in cache:
        return cache[chave]['resposta'], cache[chave]['fontes'], True
    
    resultados = collection.query(query_texts=[pergunta], n_results=2)
    contexto = "\n\n".join(resultados['documents'][0])
    fontes = [m['source'] for m in resultados['metadatas'][0]]

    prompt = f"""Voce e especialista em vigilancia epidemiologica e bioestatistica.
Use o contexto abaixo extraido de artigos cientificos para responder a pergunta.
Cite as fontes quando relevante. Responda em portugues de forma objetiva e concisa.

Contexto:
{contexto}

Pergunta: {pergunta}

Resposta:"""

    response = requests.post(
        'http://localhost:11434/api/generate',
        json={"model": "divea-biostats", "prompt": prompt, "stream": False},
        timeout=300
    )
    
    resposta = response.json()['response']
    
    cache[chave] = {'pergunta': pergunta, 'resposta': resposta, 'fontes': fontes}
    salvar_cache(cache)
    
    return resposta, fontes, False

if __name__ == '__main__':
    print("Pre-carregando perguntas frequentes...\n")
    for p in PERGUNTAS_FREQUENTES:
        print(f"Pergunta: {p}")
        resposta, fontes, do_cache = consultar(p)
        status = "CACHE" if do_cache else "GERADO"
        print(f"[{status}] {resposta[:100]}...\n")
    print("Pre-carregamento concluido.")
