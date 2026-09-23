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





# ============================================================
# ============================================================


if __name__ == "__main__":
    print("Test de la chaîne complète...\n")

    messages_test = [
        "Ma commande RND-10238 n'est jamais arrivée et je pars en trek demain, c'est urgent !",
        "Bonjour, quelle tente légère conseillez-vous pour 2 personnes en bivouac ?",
        "Et la commande RND-99999 ?",
    ]

    for msg in messages_test:
        print(f"Message : {msg}")

        result = chain.invoke({
            "message": msg,
            "history": "(aucun échange précédent)",
        })

        print(f"\n  → Ticket :")
        print(f"    intent   : {result['ticket'].intent}")
        print(f"    order_id : {result['ticket'].order_id}")
        print(f"    sku      : {result['ticket'].sku}")
        print(f"\n  → Réponse :\n    {result['answer']}\n")
        print("=" * 60 + "\n")