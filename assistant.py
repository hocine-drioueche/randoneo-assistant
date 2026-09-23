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
from typing import Literal, Optional
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate



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
# 1. EXTRACTION DU TICKET (sortie structurée)
# ============================================================




Intent = Literal[
    "order_tracking",
    "return_refund",
    "payment_issue",
    "product_question",
    "product_advice",
    "account",
    "other",
]


class SupportTicket(BaseModel):
    """Ticket structuré extrait d'un message client."""

    intent: Intent = Field(description="Intention principale du message")
    order_id: Optional[str] = Field(
        default=None,
        description="Numéro de commande si mentionné, ex. RND-10234",
    )
    sku: Optional[str] = Field(
        default=None,
        description="Référence produit si mentionnée, ex. TNT-2P-AERO",
    )
    summary: str = Field(description="Résumé du problème en une phrase")


extract_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Tu extrais un ticket de support structuré du message client Randoneo "
        "(e-commerce outdoor). Analyse le message et identifie :\n"
        "- l'intention principale\n"
        "- le numéro de commande s'il est mentionné (format RND-XXXXX)\n"
        "- la référence produit si elle est mentionnée (format XXX-XX-XXXX)\n"
        "- un résumé court du problème",
    ),
    ("user", "{message}"),
])

extractor = extract_prompt | model.with_structured_output(SupportTicket)





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




if __name__ == "__main__":
    print("Test de l'extraction du ticket...\n")

    messages_test = [
        "Ma commande RND-10238 n'est jamais arrivée et je pars en trek demain, c'est urgent !",
        "Bonjour, quelle tente légère conseillez-vous pour 2 personnes en bivouac ?",
        "Je veux renvoyer ma tente, elle est trop petite. Commande RND-10240.",
        "Vous recrutez des saisonniers ?",
    ]

    for msg in messages_test:
        print(f"Message : {msg}")
        ticket = extractor.invoke({"message": msg})
        print(f"  → intent   : {ticket.intent}")
        print(f"  → order_id : {ticket.order_id}")
        print(f"  → sku      : {ticket.sku}")
        print(f"  → summary  : {ticket.summary}")
        print()