import chromadb

CHROMA_DB_PATH = "./chroma_db"

#Helper: Query Knowledge Base
def query_context(topic):
    """Retrieves relevant context from ChromaDB based on user topic."""
    try:
        client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        collection = client.get_collection("manual_ingest")
        results = collection.query(query_texts=[topic], n_results=5)
        
        if results['documents']:
            context_text = "\n\n".join(results['documents'][0])
            sources = list(set([m['source'] for m in results['metadatas'][0]]))
            return context_text, sources
    except Exception as e:
        return "", []
    return "", []