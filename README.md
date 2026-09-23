# Assistant de support Randoneo

Un assistant de support en ligne de commande pour Randoneo, une boutique
d'équipement outdoor. L'assistant comprend les questions en langage naturel,
consulte les vraies données (catalogue, commandes, documentation) et répond
de manière fiable et contextualisée.

## Fonctionnalités

- **Compréhension** : extraction d'un ticket structuré (intention, n° de commande, SKU)
- **Récupération** : appel des outils selon le ticket (commande, produit, recherche)
- **Rédaction** : réponse ancrée uniquement sur le contexte récupéré
- **Mémoire** : l'assistant garde le fil de la conversation
- **Streaming** : la réponse s'affiche token par token

## Installation

### 1. Cloner le projet

```bash
git clone https://github.com/hocine-drioueche/randoneo-assistant.git
cd randoneo-assistant
```

### 2. Créer un environnement virtuel

```bash
python -m venv .venv

# Linux/Mac
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Configurer la clé API

Crée un fichier `.env` à la racine du projet :

```bash
cp .env.example .env
# Puis édite .env avec ta vraie clé
```

### 5. Vérifier les données

Les fichiers `data/catalog.json`, `data/orders.json` et
`data/knowledge_base.json` doivent être présents.

## Utilisation

```bash
python assistant.py
```

Puis pose tes questions :

```
> Quelle tente légère conseillez-vous pour 2 personnes en bivouac ?
> Et en 3 places ?
> Où en est ma commande RND-10234 ?
> Et la commande RND-99999 ?
> quit
```

## Architecture

```
randoneo-assistant/
├── assistant.py        # Chaîne + boucle de chat
├── tools.py            # Les 4 outils
├── data/               # Les données JSON
│   ├── catalog.json
│   ├── orders.json
│   └── knowledge_base.json
├── requirements.txt
├── .env                # Clé API (non commité)
├── .env.example        # Modèle
└── README.md
```

## Auteur

Hocine Drioueche — [drioueche.hocine@gmail.com](mailto:drioueche.hocine@gmail.com)