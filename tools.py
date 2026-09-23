"""
Outils de l'assistant Randoneo.

Chaque outil lit les données JSON et expose une fonction simple.
Les fonctions renvoient des objets Pydantic validés.
"""

import json
import re
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# MODÈLES PYDANTIC
# ============================================================

class OrderItem(BaseModel):
    """Un article dans une commande."""
    sku: str = Field(description="Référence produit")
    quantity: int = Field(description="Quantité commandée")
    unit_price_eur: float = Field(description="Prix unitaire en euros")


class OrderStatus(BaseModel):
    """Une commande client."""
    order_id: str = Field(description="Numéro de commande")
    customer_id: str = Field(description="Identifiant du client")
    status: str = Field(description="Statut de la commande")
    items: list[OrderItem] = Field(description="Articles commandés")
    total_eur: float = Field(description="Total en euros")
    shipping_method: str = Field(description="Mode de livraison")
    tracking_number: Optional[str] = Field(
        default=None,
        description="Numéro de suivi (optionnel)",
    )
    eta: Optional[str] = Field(
        default=None,
        description="Date de livraison estimée (optionnel)",
    )
    created_at: str = Field(description="Date de création de la commande")


class Product(BaseModel):
    """Un produit du catalogue."""
    sku: str = Field(description="Référence produit")
    name: str = Field(description="Nom du produit")
    category: str = Field(description="Catégorie")
    price_eur: float = Field(description="Prix en euros")
    stock: int = Field(description="Stock disponible")
    attributes: dict = Field(
        default_factory=dict,
        description="Attributs libres (places, poids, etc.)",
    )
    description: str = Field(description="Description du produit")


class KnowledgePassage(BaseModel):
    """Un passage de la base de connaissances."""
    source: str = Field(description="Document d'origine")
    text: str = Field(description="Contenu du passage")


# ============================================================
# EXCEPTIONS
# ============================================================

class OrderNotFoundError(ValueError):
    """Aucune commande ne correspond à l'identifiant fourni."""


class ProductNotFoundError(ValueError):
    """Aucun produit ne correspond au SKU fourni."""


# ============================================================
# CHARGEMENT DES DONNÉES
# ============================================================

DATA_DIR = Path(__file__).parent / "data"


def _load_json(filename: str) -> list:
    """Charge un fichier JSON depuis le dossier data/."""
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Fichier de données introuvable : {path}")
    return json.loads(path.read_text(encoding="utf-8"))


# ============================================================
# OUTIL 1 : get_order_status
# ============================================================

def get_order_status(order_id: str) -> OrderStatus:
    """
    Renvoie la commande correspondant à l'identifiant.

    Args:
        order_id: Identifiant de commande, ex. "RND-10234"

    Returns:
        Un objet OrderStatus validé

    Raises:
        OrderNotFoundError: Si l'identifiant est inconnu
    """
    orders = _load_json("orders.json")
    normalized = order_id.strip().upper()

    for order in orders:
        if order["order_id"].upper() == normalized:
            return OrderStatus(**order)

    raise OrderNotFoundError(f"Aucune commande trouvée pour {order_id!r}.")


# ============================================================
# OUTIL 2 : get_product
# ============================================================

def get_product(sku: str) -> Product:
    """
    Renvoie le produit correspondant au SKU.

    Args:
        sku: Référence produit, ex. "TNT-2P-AERO"

    Returns:
        Un objet Product validé

    Raises:
        ProductNotFoundError: Si le SKU est inconnu
    """
    catalog = _load_json("catalog.json")
    normalized = sku.strip().upper()

    for product in catalog:
        if product["sku"].upper() == normalized:
            return Product(**product)

    raise ProductNotFoundError(f"Aucun produit trouvé pour le SKU {sku!r}.")


# ============================================================
# OUTIL 3 : search_catalog
# ============================================================

def search_catalog(query: str, category: Optional[str] = None) -> list[Product]:
    """
    Recherche des produits par mots-clés (nom, description, catégorie).

    Args:
        query: Termes de recherche, ex. "tente légère"
        category: Filtre optionnel de catégorie, ex. "Tentes"

    Returns:
        Liste d'objets Product triés par pertinence
    """
    catalog = _load_json("catalog.json")

    terms = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 1]

    results = []
    for item in catalog:
        if category and item["category"].lower() != category.lower():
            continue

        haystack = f"{item['name']} {item['description']} {item['category']}".lower()
        score = sum(haystack.count(term) for term in terms)

        if score > 0 or not terms:
            results.append((score, item))

    results.sort(key=lambda pair: pair[0], reverse=True)

    return [Product(**item) for _, item in results]


# ============================================================
# OUTIL 4 : search_knowledge_base
# ============================================================

def search_knowledge_base(query: str, k: int = 3) -> list[KnowledgePassage]:
    """
    Renvoie les k passages les plus pertinents de la base de connaissances.

    Args:
        query: Termes de recherche
        k: Nombre de passages à renvoyer (défaut : 3)

    Returns:
        Liste d'objets KnowledgePassage triés par pertinence
    """
    kb = _load_json("knowledge_base.json")

    terms = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 1]

    results = []
    for item in kb:
        haystack = item["text"].lower()
        score = sum(haystack.count(term) for term in terms)
        if score > 0 or not terms:
            results.append((score, item))

    results.sort(key=lambda pair: pair[0], reverse=True)

    return [KnowledgePassage(**item) for _, item in results[:k]]


# ============================================================
# TEST MANUEL
# ============================================================

if __name__ == "__main__":
    print("=== Test des outils ===\n")

    print("1. get_order_status('RND-10234')")
    try:
        order = get_order_status("RND-10234")
        print(f"   Type : {type(order).__name__}")
        print(f"   ID : {order.order_id}")
        print(f"   Statut : {order.status}")
        print(f"   Suivi : {order.tracking_number}")
        print(f"   ETA : {order.eta}")
        print(f"   Articles : {len(order.items)}")
        for item in order.items:
            print(f"     - {item.sku} × {item.quantity} ({item.unit_price_eur}€)")
    except OrderNotFoundError as e:
        print(f"   Erreur : {e}")

    print("\n2. get_product('TNT-2P-AERO')")
    try:
        product = get_product("TNT-2P-AERO")
        print(f"   Type : {type(product).__name__}")
        print(f"   Nom : {product.name}")
        print(f"   Prix : {product.price_eur}€")
        print(f"   Stock : {product.stock}")
        print(f"   Attributs : {product.attributes}")
    except ProductNotFoundError as e:
        print(f"   Erreur : {e}")

    print("\n3. search_catalog('tente légère 2 personnes')")
    for p in search_catalog("tente légère 2 personnes")[:3]:
        print(f"   - {p.name} ({p.price_eur}€, stock {p.stock})")

    print("\n4. search_knowledge_base('tente légère')")
    results = search_knowledge_base("tente légère")
    if results:
        for kb in results:
            print(f"   - [{kb.source}] {kb.text[:70]}...")
    else:
        print("   Aucun résultat (le mot n'existe pas dans la base)")
        

    print("\n5. get_order_status('RND-99999') → doit lever une erreur")
    try:
        get_order_status("RND-99999")
    except OrderNotFoundError as e:
        print(f"   Erreur attendue : {e}")

    print("\n6. get_product('SKU-INEXISTANT') → doit lever une erreur")
    try:
        get_product("SKU-INEXISTANT")
    except ProductNotFoundError as e:
        print(f"   Erreur attendue : {e}")