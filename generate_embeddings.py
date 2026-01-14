import pandas as pd
from sentence_transformers import SentenceTransformer

# Charger ton CSV
df = pd.read_csv("csv_fusionne.csv")

# Charger le modèle
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# Calculer les embeddings
embeddings = model.encode(
    df['EventName'].fillna('') + ' ' + df['Description'].fillna(''),
    convert_to_tensor=False  # Numpy array plutôt que tensor pour réduire la mémoire
)

# Sauvegarder embeddings
import numpy as np
np.save("event_embeddings.npy", embeddings)

print("Embeddings générés et sauvegardés.")
