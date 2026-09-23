"""
Assistant de support Randoneo en ligne de commande.

Ce script :
1. Comprend la demande du client (extraction d'un ticket structuré)
2. Va chercher la bonne information via les outils
3. Rédige une réponse ancrée sur le contexte récupéré
4. Garde le fil de la conversation (mémoire légère)
"""

import os
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import (
    RunnableLambda,
    RunnableParallel,
    RunnablePassthrough,
)

from tools import (
    get_order_status,
    get_product,
    search_catalog,
    search_knowledge_base,
    OrderNotFoundError,
    ProductNotFoundError,
)


# ============================================================
# 0. CONFIGURATION
# ============================================================

load_dotenv()

if not os.getenv("ANTHROPIC_API_KEY"):
    raise ValueError(
        "ANTHROPIC_API_KEY manquante. "
        "Vérifie ton fichier .env à la racine du projet."
    )

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
    """Récupère le contexte selon le ticket."""
    try:
        if ticket.order_id:
            order = get_order_status(ticket.order_id)
            return _format_order(order)

        if ticket.sku:
            product = get_product(ticket.sku)
            return _format_product(product)

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
# 4. ASSEMBLAGE DE LA CHAÎNE
# ============================================================

def build_chain_input(x):
    """Construit le dict complet pour la chaîne."""
    return {
        "message": x["message"],
        "history": x.get("history", "(aucun échange précédent)"),
    }


chain = (
    RunnablePassthrough.assign(ticket=lambda x: extractor.invoke({"message": x["message"]}))
    | RunnablePassthrough.assign(context=lambda x: fetch_context(x["ticket"]))
    | RunnablePassthrough.assign(answer=answer_chain)
)
# ============================================================
# 5. BOUCLE DE CHAT
# ============================================================

def _format_history(history: list[dict]) -> str:
    """Formate l'historique en texte lisible pour le prompt."""
    if not history:
        return "(aucun échange précédent)"
    lines = []
    for msg in history[-6:]:  # Garder les 6 derniers messages
        role = "Client" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role} : {msg['content']}")
    return "\n".join(lines)


def chat():
    """Boucle de chat principale."""
    history: list[dict] = []

    print("=" * 60)
    print("  Assistant de support Randoneo")
    print("  Tapez 'quit' pour quitter.")
    print("=" * 60)
    print()

    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nÀ bientôt !")
            break

        if question.lower() in ("quit", "exit", "q"):
            print("À bientôt !")
            break

        if not question:
            continue

        history_text = _format_history(history)

        print("\nAssistant : ", end="", flush=True)
        full_response = ""

        try:
            for chunk in chain.stream({
                "message": question,
                "history": history_text,
            }):
                if "answer" in chunk:
                    text = chunk["answer"]
                    print(text, end="", flush=True)
                    full_response += text
        except Exception as e:
            print(f"\n[Erreur] {e}")
            continue

        print("\n")

        # Mise à jour de la mémoire (léger)
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": full_response})

        # Limiter la mémoire aux 10 derniers échanges
        if len(history) > 20:
            history = history[-20:]


# ============================================================
# 6. POINT D'ENTRÉE
# ============================================================

if __name__ == "__main__":
    chat()