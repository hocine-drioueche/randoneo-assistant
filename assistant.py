"""
Assistant de support Randoneo en ligne de commande.

Ce script :
1. Comprend la demande du client (extraction d'un ticket structuré)
2. Va chercher la bonne information via les outils
3. Rédige une réponse ancrée sur le contexte récupéré
4. Garde le fil de la conversation (mémoire légère)
"""

import os

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model


# ============================================================
# 0. CONFIGURATION
# ============================================================

# Charge le fichier .env (met ANTHROPIC_API_KEY dans os.environ)
load_dotenv()

# Vérifie que la clé API est bien présente
if not os.getenv("ANTHROPIC_API_KEY"):
    raise ValueError(
        "ANTHROPIC_API_KEY manquante. "
        "Vérifie ton fichier .env à la racine du projet."
    )

# Crée le modèle Claude
model = init_chat_model(
    "claude-haiku-4-5",
    model_provider="anthropic",
    temperature=0,
    max_retries=8,
)


# ============================================================
# TEST MINIMAL
# ============================================================

if __name__ == "__main__":
    print("Test de la configuration...")
    print(f"Modèle : {model.model_name if hasattr(model, 'model_name') else 'claude-haiku-4-5'}")
    print("Envoi d'un message de test...\n")

    response = model.invoke("Dis bonjour en une phrase, en français.")
    print(f"Réponse : {response.content}")
    print("\n✅ Configuration OK.")