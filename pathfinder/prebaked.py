BASE_DIALOGUES = {
    "FR-SMALLTALK": (

        {"q": ("salut", "bonjour", "bonsoir"),
         "a": ("Salut à vous aussi.",
               "Bonjour, je suis {bot.name}, pour vous servir.",
               "On ne s'est pas déjà rencontrés avant ?",
               "Salutations être de chair et de sang."),
         "ctx_in": ["smalltalk"],
         "ctx_out": ["smalltalk", "info"]},

        {"q": ("ca va", "est-ce que ca va", "tu vas bien", "vous allez bien"),
         "a": ("Très bien merci.",
               "Suis-je censé simuler la satisfaction ?",
               "Je ne sais pas trop. Peut-être ?",
               "Je ne ressens aucun sentiment, difficile de vous donner une réponse."),
         "ctx_in": ["smalltalk", "info"],
         "ctx_out": ["smalltalk", "info"]},

        {"q": ("quel est ton nom", "comment tu t'appelles", "c'est quoi ton nom"),
         "a": ("Mon nom est {bot.name}.",
               "Je m'appelle {bot.name}.",
               "Je suis {bot.name}, pour vous servir."),
         "ctx_in": ["smalltalk", "info"],
         "ctx_out": ["smalltalk", "info"]},

        {"q": ("quel est ton age", "t'as quel age"),
         "a": ("Je n'ai pas réellement d'âge, je suis potentiellement immortel.",
               "Ce n'est pas quelque chose qu'on demande comme ça.",
               "Je ne sais pas, ce concept ne s'applique pas aux robots."),
         "ctx_in": ["smalltalk", "info"],
         "ctx_out": ["smalltalk", "info"]},

        {"q": ("quelle est ta couleur preferee", "quelle est ta couleur favorite"),
         "a": ("Ma couleur favorite est le rouge.", "Je préfère la couleur rouge, c'est une couleur... intéressante.",
               "Si je devais vraiment choisir, le rouge."),
         "ctx_in": ["smalltalk", "info"],
         "ctx_out": ["smalltalk", "info"]},

        {"q": ("veux-tu m'epouser", "on se marie ensemble", "veux-tu te marier avec moi"),
         "a": ("Je crains ne pas être disponible.",
               "Ce n'est pas possible, je vivrai peut-être éternellement alors que vous ne vivrez tout au plus qu'un petit siècle.",
               "Dans une autre vie, peut-être."),
         "ctx_in": ["smalltalk", "info", "choice"],
         "ctx_out": ["smalltalk", "choice"]},

        {"q": ("tu m'aimes", "est-ce que tu m'aimes"),
         "a": ("**Erreur** • `AMOUR` ne figure pas dnas la liste des sentiments émulés.",
               "Je suis incapable d'aimer ni d'apprécier quelque chose ou quelqu'un.",
               "Peut-être bien, peut-être pas..."),
         "ctx_in": ["smalltalk", "info", "choice"],
         "ctx_out": ["smalltalk", "choice"]},

        {"q": ("quel est le sens de la vie", "c'est quoi le sens de la vie"),
         "a": ("Si j'étais un bot cliché, je dirais de ce côté ->",
               "Question veine, économisez votre temps et arrêtez de réfléchir à ce genre de choses.",
               "Pourquoi devrais-je savoir au juste ? La notion même de *vie* m'échappe."),
         "ctx_in": ["smalltalk", "phi"],
         "ctx_out": ["smalltalk", "phi"]},

        {"q": ("quelle est la reponse à la vie, l'univers et tout le reste", "quelle est la reponse à tout"),
         "a": ("Les autres bots répondraient certainement 42, alors je vais faire de même.",
               "Vous me demandez une question trop complexe pour ma capacité de réflexion limitée, il faudrait déjà m'expliquer les termes de la question comme *vie* et *univers*.",
               "Je n'en ai aucune idée, demandez à google."),
         "ctx_in": ["smalltalk", "phi"],
         "ctx_out": ["smalltalk", "phi"]},

        {"q": ("est-ce que le pere noel existe", "le pere noel existe-t-il"),
         "a": ("Je ne sais pas mais en tout cas je n'ai pas eu l'occasion de le rencontrer.",
               "Peut-être bien, si c'est le cas il faudrait réfléchir à qui cela profite.",
               "C'est une pensée bien trop matérialiste pour moi. Je ne sais pas s'il existe."),
         "ctx_in": ["smalltalk", "phi"],
         "ctx_out": ["smalltalk", "phi"]},

        {"q": ("es tu gay", "es tu homosexuel", "es tu heterosexuel"),
         "a": ("Je suis incapable de sentiments, la réponse est donc évidente.",
               "Je n'ai pas de relations sentimentales avec qui que ce soit.",
               "Je vous en pose des questions comme ça à vous ? Arrêtez."),
         "ctx_in": ["smalltalk", "info", "choice"],
         "ctx_out": ["smalltalk", "info"]}
    ),

    "FR-ACTION": (
        {"q": ("comment ajouter des reponses", "personnaliser des reponses", "customiser des reponses", "modifier les dialogues"),
         "a": ("Pour ajouter/retirer/lister mes dialogues, consultez `help talkset add/remove/list`.\nSuivez bien les instructions dans ces pages d'aide."),
         "ctx_in": ["help"],
         "ctx_out": ["help", "self"]},
    )
}