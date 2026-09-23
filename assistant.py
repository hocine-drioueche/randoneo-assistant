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
from langchain_core.runnables import RunnableLambda, RunnableParallel
from langchain_core.output_parsers import StrOutputParser



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
# 2. RÉCUPÉRATION DU CONTEXTE (outils)
# ============================================================



from tools import (
    get_order_status,
    get_product,
    search_catalog,
    search_knowledge_base,
    OrderNotFoundError,
    ProductNotFoundError,
)


def _format_order(order) -> str:
    """Formate une commande en texte lisible."""
    lines = [
        f"Commande {order.order_id} :",
        f"- Statut : {order.status}",
        f"- Client : {order.customer_id}",
        f"- Total : {order.total_eur}€",
        f"- Livraison : {order.shipping_method}",
    ]
    if order.tracking_number:
        lines.append(f"- Numéro de suivi : {order.tracking_number}")
    if order.eta:
        lines.append(f"- Livraison estimée : {order.eta}")
    if order.items:
        lines.append("- Articles :")
        for item in order.items:
            lines.append(f"  • {item.sku} × {item.quantity} ({item.unit_price_eur}€)")
    return "\n".join(lines)


def _format_product(product) -> str:
    """Formate un produit en texte lisible."""
    lines = [
        f"Produit {product.name} (SKU {product.sku}) :",
        f"- Catégorie : {product.category}",
        f"- Prix : {product.price_eur}€",
        f"- Stock : {product.stock} unités",
        f"- Description : {product.description}",
    ]
    if product.attributes:
        attrs = ", ".join(f"{k}={v}" for k, v in product.attributes.items())
        lines.append(f"- Attributs : {attrs}")
    return "\n".join(lines)


def _format_catalog_results(products) -> str:
    """Formate une liste de produits."""
    if not products:
        return ""
    lines = ["Produits pertinents du catalogue :"]
    for p in products[:3]:
        stock_info = f"{p.stock} en stock" if p.stock > 0 else "rupture de stock"
        lines.append(f"- {p.name} ({p.price_eur}€, {stock_info}) : {p.description[:100]}")
    return "\n".join(lines)


def _format_kb_results(passages) -> str:
    """Formate une liste de passages de la base de connaissances."""
    if not passages:
        return ""
    lines = ["Documentation pertinente :"]
    for kb in passages:
        lines.append(f"- [{kb.source}] {kb.text[:200]}")
    return "\n".join(lines)


def fetch_context(ticket: SupportTicket) -> str:
    """
    Récupère le contexte selon le ticket.

    - Si order_id → get_order_status
    - Si sku → get_product
    - Sinon → search_catalog + search_knowledge_base (parallèle)
    """
    try:
        # Cas 1 : numéro de commande
        if ticket.order_id:
            order = get_order_status(ticket.order_id)
            return _format_order(order)

        # Cas 2 : référence produit spécifique
        if ticket.sku:
            product = get_product(ticket.sku)
            return _format_product(product)

        # Cas 3 : question ouverte → catalogue + base de connaissances
        parallel_search = RunnableParallel(
            catalog=RunnableLambda(lambda _: search_catalog(ticket.summary)),
            kb=RunnableLambda(lambda _: search_knowledge_base(ticket.summary)),
        )
        results = parallel_search.invoke({})

        parts = []
        if results["catalog"]:
            parts.append(_format_catalog_results(results["catalog"]))
        if results["kb"]:
            parts.append(_format_kb_results(results["kb"]))

        return "\n\n".join(parts) if parts else "Aucune information trouvée dans nos sources."

    except OrderNotFoundError as e:
        return (
            f"INFORMATION INTROUVABLE : {e} "
            "Cette commande n'existe pas dans notre système. "
            "Demande au client de vérifier le numéro."
        )
    except ProductNotFoundError as e:
        return (
            f"INFORMATION INTROUVABLE : {e} "
            "Ce produit n'existe pas dans notre catalogue. "
            "Demande au client de vérifier la référence."
        )


context_chain = RunnableLambda(fetch_context)






# ============================================================
# 3. RÉDACTION DE LA RÉPONSE
# ============================================================



answer_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Tu es l'assistant de support de Randoneo, un e-commerce de matériel outdoor. "
        "Réponds en français, avec un ton chaleureux et professionnel, en 4 phrases maximum.\n\n"
        "RÈGLES STRICTES :\n"
        "1. Appuie-toi UNIQUEMENT sur le contexte fourni ci-dessous.\n"
        "2. N'invente JAMAIS un statut, un prix, un délai ou une information.\n"
        "3. Si le contexte dit 'INFORMATION INTROUVABLE', dis-le poliment au client "
        "et demande-lui de vérifier sa référence.\n"
        "4. Si le contexte ne contient pas l'information demandée, dis que tu ne l'as pas.\n"
        "5. Termine par une prochaine étape utile si pertinent.",
    ),
    (
        "user",
        "Historique de la conversation :\n"
        "{history}\n\n"
        "Contexte (source de vérité) :\n"
        "{context}\n\n"
        "Message du client : {message}\n\n"
        "Réponse :",
    ),
])

answer_chain = answer_prompt | model | StrOutputParser()

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



# ============================================================
# ============================================================

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



# ============================================================
# ============================================================

if __name__ == "__main__":
    print("Test de la récupération du contexte...\n")

    messages_test = [
        "Ma commande RND-10238 n'est jamais arrivée et je pars en trek demain, c'est urgent !",
        "Bonjour, quelle tente légère conseillez-vous pour 2 personnes en bivouac ?",
        "Parlez-moi du produit TNT-2P-AERO",
        "Et la commande RND-99999 ?",
    ]

    for msg in messages_test:
        print(f"Message : {msg}")
        ticket = extractor.invoke({"message": msg})
        print(f"  → intent   : {ticket.intent}")
        print(f"  → order_id : {ticket.order_id}")
        print(f"  → sku      : {ticket.sku}")
        print(f"\n  Contexte récupéré :")
        context = fetch_context(ticket)
        for line in context.split("\n"):
            print(f"    {line}")
        print("\n" + "=" * 60 + "\n")



# ============================================================
# ============================================================

if __name__ == "__main__":
    print("Test de la rédaction de la réponse...\n")

    messages_test = [
        "Ma commande RND-10238 n'est jamais arrivée et je pars en trek demain, c'est urgent !",
        "Bonjour, quelle tente légère conseillez-vous pour 2 personnes en bivouac ?",
        "Parlez-moi du produit TNT-2P-AERO",
        "Et la commande RND-99999 ?",
    ]

    for msg in messages_test:
        print(f"Message : {msg}")

        # Extraction
        ticket = extractor.invoke({"message": msg})

        # Récupération du contexte
        context = fetch_context(ticket)

        # Rédaction
        answer = answer_chain.invoke({
            "message": msg,
            "context": context,
            "history": "(aucun échange précédent)",
        })

        print(f"\n  → Réponse :\n    {answer}\n")
        print("=" * 60 + "\n")