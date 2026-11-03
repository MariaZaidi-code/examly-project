"""Embedders. Default is an offline hashed lexical embedding (1024-d, L2-normalised); a remote
OpenAI-compatible /embeddings endpoint is used when AGENT_EMBED_URL is set."""
import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from . import config

class HashingEmbedder:
    name = "hashing-1024-unigram+bigram"
    dim = 1024
    def __init__(self):
        self.v = HashingVectorizer(n_features=self.dim, ngram_range=(1, 2), alternate_sign=False, norm="l2", stop_words="english")
    def embed(self, texts):
        return self.v.transform(texts).toarray().astype("float32")

class RemoteEmbedder:
    def __init__(self):
        self.name, self.dim = config.EMBED_MODEL, None
    def embed(self, texts):
        import requests
        r = requests.post(config.EMBED_URL.rstrip("/") + "/embeddings", headers={"Authorization": "Bearer " + (config.LLM_KEY or "")},
                          json={"model": config.EMBED_MODEL, "input": texts}, timeout=60)
        r.raise_for_status()
        m = np.array([d["embedding"] for d in r.json()["data"]], dtype="float32")
        return m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-9)

def get_embedder():
    return RemoteEmbedder() if config.EMBED_URL else HashingEmbedder()
