import numpy as np
import math
from datetime import datetime

def cosine_similarity(v1, v2):
    if v1 is None or v2 is None: return 0
    # Vectorized similarity for single pair
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def batch_cosine_similarity(query_v, vectors_v):
    """
    Experimental vectorized similarity for a batch of vectors.
    vectors_v should be a 2D numpy array.
    """
    if query_v is None or vectors_v.size == 0:
        return np.array([])
    dot_product = np.dot(vectors_v, query_v)
    norms = np.linalg.norm(vectors_v, axis=1) * np.linalg.norm(query_v)
    return np.divide(dot_product, norms, out=np.zeros_like(dot_product), where=norms!=0)

def calculate_importance(access_count, last_accessed_str):
    try:
        last_accessed = datetime.strptime(last_accessed_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        # Fallback to now if timestamp is corrupted or missing
        last_accessed = datetime.now()
    
    # Decay Factor (lambda = 0.0001 per minute ~ roughly half in 5 days)
    delta_minutes = (datetime.now() - last_accessed).total_seconds() / 60
    decay = math.exp(-0.0001 * delta_minutes)
    return (access_count + 1) * decay
