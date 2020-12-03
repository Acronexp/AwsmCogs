PREBAKED_ANSWERS = {
    "FR-SMALLTALK": (
        {"q": ("quel est ton nom", "comment tu t'appelles", "c'est quoi ton nom"),
         "a": ("Mon nom est {bot.name}.",
               "Je m'appelle {bot.name}.",
               "Je suis {bot.name}, pour vous servir."),
         "ctx_in": ["random", "bot"],
         "ctx_out": ["random", "bot"]},

        {"q": ("quel est ton age", "t'as quel age"),
         "a": ("Je n'ai pas réellement d'âge, je suis potentiellement immortel.",
               "Ce n'est pas quelque chose qu'on demande comme ça.",
               "Je ne sais pas, ce concept ne s'applique pas aux robots."),
         "ctx_in": ["random", "bot"],
         "ctx_out": ["random", "bot"]},

        {"q": ("quelle est ta couleur preferee", "quelle est ta couleur favorite"),
         "a": ("Ma couleur favorite est le rouge.", "Je préfère la couleur rouge, c'est une couleur... intéressante.",
               "Si je devais vraiment choisir, le rouge."),
         "ctx_in": ["random", "bot"],
         "ctx_out": ["random", "bot"]},

        {"q": ("veux-tu m'epouser", "on se marie ensemble", "veux-tu te marier avec moi"),
         "a": ("Je crains ne pas être disponible.",
               "Ce n'est pas possible, je vivrai peut-être éternellement alors que vous ne vivrez tout au plus qu'un petit siècle.",
               "Dans une autre vie, peut-être."),
         "ctx_in": ["random", "bot"],
         "ctx_out": ["random", "bot"]},

        {"q": ("tu m'aimes", "est-ce que tu m'aimes"),
         "a": ("**Erreur** • `AMOUR` ne figure pas dnas la liste des sentiments émulés.",
               "Je suis incapable d'aimer ni d'apprécier quelque chose ou quelqu'un.",
               ""),
         "ctx_in": ["random", "bot"],
         "ctx_out": ["random", "bot"]},

        {"q": ("quel est le sens de la vie", "c'est quoi le sens de la vie"),
         "a": ("Si j'étais un bot cliché, je dirais de ce côté ->",
               "Question veine, économisez votre temps et arrêtez de réfléchir à ce genre de choses.",
               "Pourquoi devrais-je savoir au juste ? La notion même de *vie* m'échappe."),
         "ctx_in": ["random", "phi"],
         "ctx_out": ["random", "phi"]},

        {"q": ("quelle est la reponse à la vie, l'univers et tout le reste", "quelle est la reponse à tout"),
         "a": ("Les autres bots répondraient certainement 42, alors je vais faire de même.",
               "Vous me demandez une question trop complexe pour ma capacité de réflexion limitée, il faudrait déjà m'expliquer les termes de la question comme *vie* et *univers*.",
               "Je n'en ai aucune idée, demandez à google."),
         "ctx_in": ["random", "phi"],
         "ctx_out": ["random", "phi"]},

        {"q": ("est-ce que le pere noel existe", "le pere noel existe-t-il"),
         "a": ("Je ne sais pas mais en tout cas je n'ai pas eu l'occasion de le rencontrer.",
               "Peut-être bien, si c'est le cas il faudrait réfléchir à qui cela profite.",
               ""),
         "ctx_in": ["random", "phi"],
         "ctx_out": ["random", "phi"]},
    )
}