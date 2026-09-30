"""Genere la documentation PDF de ragscore.

    uv run --extra docs python docs/construire_documentation.py

Le PDF est versionne a cote de ce script : il doit pouvoir etre relu sans rien installer,
et regenere sans rien deviner.
"""

from __future__ import annotations

import math
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

VERT = colors.HexColor("#12805c")
ARDOISE = colors.HexColor("#1d1c1a")
DISCRET = colors.HexColor("#6b6862")
FOND_CODE = colors.HexColor("#f4f3f0")
BORD = colors.HexColor("#e3e1dc")
ROUGE = colors.HexColor("#b3261e")

base = getSampleStyleSheet()
S = {
    "titre": ParagraphStyle("titre", parent=base["Title"], fontName="Helvetica-Bold",
                            fontSize=26, leading=30, textColor=ARDOISE, alignment=TA_LEFT,
                            spaceAfter=4),
    "sous": ParagraphStyle("sous", parent=base["Normal"], fontName="Helvetica", fontSize=10.5,
                           leading=15, textColor=DISCRET, spaceAfter=16),
    "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=15,
                         leading=19, textColor=VERT, spaceBefore=22, spaceAfter=8),
    "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=11.5,
                         leading=15, textColor=ARDOISE, spaceBefore=15, spaceAfter=5),
    "corps": ParagraphStyle("corps", parent=base["Normal"], fontName="Helvetica", fontSize=10,
                            leading=15, textColor=ARDOISE, spaceAfter=7),
    "note": ParagraphStyle("note", parent=base["Normal"], fontName="Helvetica-Oblique",
                           fontSize=9, leading=13.5, textColor=DISCRET, spaceAfter=7),
    "code": ParagraphStyle("code", parent=base["Normal"], fontName="Courier", fontSize=8.5,
                           leading=12.5, textColor=ARDOISE, leftIndent=8, rightIndent=8),
    "formule": ParagraphStyle("formule", parent=base["Normal"], fontName="Helvetica-Oblique",
                              fontSize=11, leading=17, textColor=ARDOISE, alignment=1,
                              spaceBefore=6, spaceAfter=6),
    "cellule": ParagraphStyle("cellule", parent=base["Normal"], fontName="Helvetica", fontSize=9,
                              leading=12.5, textColor=ARDOISE),
    "cellule_code": ParagraphStyle("cellule_code", parent=base["Normal"], fontName="Courier",
                                   fontSize=8.5, leading=12, textColor=ARDOISE),
    "entete": ParagraphStyle("entete", parent=base["Normal"], fontName="Helvetica-Bold",
                             fontSize=8.5, leading=11, textColor=colors.white),
}
LARGEUR = A4[0] - 40 * mm


def code(texte: str):
    contenu = "<br/>".join(
        ligne.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") or "&nbsp;"
        for ligne in texte.strip("\n").split("\n")
    )
    table = Table([[Paragraph(contenu, S["code"])]], colWidths=[LARGEUR])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), FOND_CODE),
        ("BOX", (0, 0), (-1, -1), 0.6, BORD),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return [Spacer(1, 6), table, Spacer(1, 7)]


def tableau(entetes, lignes, largeurs, mono=False):
    donnees = [[Paragraph(titre, S["entete"]) for titre in entetes]]
    for ligne in lignes:
        donnees.append([
            Paragraph(valeur, S["cellule_code"] if (mono and index) else S["cellule"])
            for index, valeur in enumerate(ligne)
        ])
    table = Table(donnees, colWidths=[part * LARGEUR for part in largeurs], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), VERT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, BORD),
        ("BOX", (0, 0), (-1, -1), 0.6, BORD),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fbfbfa")]),
    ]))
    return table


def encadre(texte, couleur=VERT):
    table = Table([[Paragraph(texte, S["corps"])]], colWidths=[LARGEUR])
    table.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, couleur),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbfbfa")),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def pied(canvas, document):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(DISCRET)
    canvas.drawString(20 * mm, 12 * mm, "ragscore, documentation")
    canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"page {document.page}")
    canvas.setStrokeColor(BORD)
    canvas.setLineWidth(0.4)
    canvas.line(20 * mm, 16 * mm, A4[0] - 20 * mm, 16 * mm)
    canvas.restoreState()


histoire = []
A = histoire.append
E = histoire.extend

# ══════════════════════════════════════════════════════════ couverture
A(Paragraph("ragscore", S["titre"]))
A(Paragraph(
    "Mesurer un systeme RAG au lieu de l'affirmer bon.<br/>"
    "Documentation complete : les deux facons de mesurer, le format du jeu de questions, "
    "chaque indicateur explique et calcule, les couts, la reference de configuration.",
    S["sous"]))
A(HRFlowable(width="100%", thickness=0.8, color=BORD, spaceAfter=10))

A(Paragraph("Le principe", S["h1"]))
A(Paragraph(
    "ragscore est un arbitre. Il ne connait pas le jeu, il connait les regles. Vous lui donnez "
    "une liste de questions avec les bonnes reponses, et un systeme capable de repondre. Il note "
    "<b>la recuperation et la generation separement</b>, de facon <b>deterministe</b>, et produit "
    "un rapport <b>renotable sans rappeler le systeme</b>.", S["corps"]))
A(Paragraph(
    "Il n'appelle lui-meme aucun modele et ne connait ni votre base, ni votre langue, ni votre "
    "domaine.", S["corps"]))

A(Paragraph("Pourquoi separer les deux etages", S["h2"]))
A(Paragraph(
    "Un score unique ne dit pas ou corriger. Si le bon document n'est pas dans le premier etage "
    "de recuperation, aucun reclassement ne l'y fera apparaitre, et travailler le reranker est "
    "une perte de temps. A l'inverse, un systeme qui trouve le bon document et le resume mal n'a "
    "pas le meme probleme qu'un systeme qui ne le trouve pas. La distinction dit lequel des deux "
    "vous avez.", S["corps"]))

A(Paragraph("Pourquoi une notation deterministe", S["h2"]))
A(Paragraph(
    "Aucune valeur attendue n'est appreciee par un modele : elle est presente au caractere pres, "
    "a la mise en forme pres, ou elle ne l'est pas. Un juge LLM se justifie pour une reponse "
    "ouverte, jamais pour un chiffre. Une notation qui varie d'une execution a l'autre ne permet "
    "de comparer ni deux versions, ni deux modeles.", S["corps"]))

A(Paragraph("Les trois objets", S["h1"]))
A(tableau(
    ["Objet", "Ce qu'il porte", "Qui l'ecrit"],
    [["<b>Case</b>", "une question, les documents qui y repondent, ce que la reponse doit contenir",
      "vous"],
     ["<b>Answer</b>", "le texte produit et les documents retenus par chaque etage",
      "votre systeme"],
     ["<b>CaseOutcome</b>", "la note : rangs, presence des valeurs, refus",
      "ragscore"]],
    [0.2, 0.62, 0.18]))
A(Spacer(1, 8))
A(Paragraph(
    "Le contrat a remplir tient en une methode : <font face='Courier'>answer(question)</font> qui "
    "rend une <font face='Courier'>Answer</font>. Ni interface a heriter, ni configuration.",
    S["corps"]))

# ══════════════════════════════════════════════════════════ installation
A(Paragraph("Installation", S["h1"]))
E(code(
    "cd ~/Desktop/ragscore\n"
    "uv sync --extra ui --extra engine"))
A(tableau(
    ["Extra", "Ce qu'il ajoute", "Necessaire pour"],
    [["(aucun)", "httpx seulement", "utiliser ragscore comme bibliotheque"],
     ["ui", "starlette, uvicorn", "l'interface locale"],
     ["engine", "psycopg, pgvector, voyageai, anthropic", "le moteur integre"],
     ["docs", "reportlab", "regenerer ce PDF"]],
    [0.13, 0.45, 0.42], mono=False))
A(Spacer(1, 8))
A(encadre(
    "<b>Toutes les commandes se prefixent par uv run.</b> Le programme est installe dans "
    "<font face='Courier'>.venv/bin</font>, qui n'est pas dans le PATH du terminal : sans "
    "<font face='Courier'>uv run</font>, le shell repond "
    "<font face='Courier'>command not found</font>. L'alternative est "
    "<font face='Courier'>source .venv/bin/activate</font>, une fois par session."))

A(PageBreak())

# ══════════════════════════════════════════════════════════ deux facons
A(Paragraph("Les deux facons de mesurer", S["h1"]))
A(Paragraph(
    "Elles ne repondent pas a la meme question, et il faut les deux.", S["corps"]))
A(tableau(
    ["Sorte", "Vous branchez", "La question a laquelle elle repond", "Prerequis"],
    [["<b>vector</b><br/>moteur integre", "une base vectorisee et deux cles",
      "cette <b>approche</b> est-elle bonne ? Ce decoupage, ce reranker, ce modele d'embeddings",
      "la base"],
     ["<b>http</b><br/>API a brancher", "l'URL de votre application",
      "mon <b>produit</b> est-il bon ? C'est le chiffre que l'on publie",
      "la base et l'application"]],
    [0.17, 0.2, 0.45, 0.18]))
A(Spacer(1, 10))
A(Paragraph(
    "Brancher l'API reste la mesure qui compte avant de vendre, et aucune reimplementation ne la "
    "remplace : deux chemins de requete divergent des qu'on touche a l'un, et l'evaluation finit "
    "par noter autre chose que ce qu'on livre. Le moteur integre repond a l'autre question, celle "
    "que l'on se pose en amont, quand l'application n'existe pas encore ou que l'on compare deux "
    "strategies sans rien deployer.", S["corps"]))
A(encadre(
    "<b>Les deux chiffres ne sont pas comparables entre eux.</b> Le moteur integre utilise votre "
    "corpus, mais pas votre chemin de requete : ni vos expansions, ni votre consigne systeme, ni "
    "vos verifications. Un rapport issu du moteur ne doit jamais etre presente comme la mesure du "
    "produit.", ROUGE))

# ─────────────────────────────────── moteur
A(Paragraph("Le moteur integre (kind: vector)", S["h2"]))
A(Paragraph(
    "ragscore execute la chaine complete : il vectorise la question, cherche dans la base, "
    "reclasse, puis genere. Deux etages sont releves, nommes "
    "<font face='Courier'>recherche</font> et <font face='Courier'>rerank</font>.", S["corps"]))
E(code('''{
  "kind": "vector",
  "name": "mon corpus",
  "databaseUrl": "{{env:DATABASE_URL}}",
  "fromClause": "chunk JOIN document ON document.id = chunk.documentid",
  "identifierColumn": "document.code",
  "textColumn": "chunk.content",
  "embeddingColumn": "chunk.embedding",
  "searchLimit": 40,
  "rerankKeep": 8,
  "maxPassages": 14,
  "embeddingModel": "voyage-3.5",
  "rerankModel": "rerank-2.5",
  "generationModel": "claude-sonnet-5"
}'''))
A(Paragraph(
    "Quand l'identifiant vit dans la meme table que le texte, "
    "<font face='Courier'>table</font> suffit et <font face='Courier'>fromClause</font> reste "
    "vide. Sinon on donne la relation avec sa jointure, et les colonnes se qualifient. "
    "<font face='Courier'>fromClause</font> et <font face='Courier'>whereClause</font> sont du "
    "SQL assume : de la configuration, jamais une valeur saisie par un utilisateur final. Les "
    "noms de table et de colonnes, eux, passent par des identifiants SQL composes, jamais "
    "concatenes.", S["corps"]))
A(encadre(
    "<b>La consigne donnee au modele decide du score.</b> Celle par defaut demande de citer "
    "l'identifiant et de refuser hors corpus. Sans cette consigne, tous les cas de refus "
    "echouent et la citation n'est jamais mesurable. La modifier est legitime : c'est souvent "
    "ce que l'on cherche a mesurer."))

# ─────────────────────────────────── http
A(Paragraph("L'API a brancher (kind: http)", S["h2"]))
A(Paragraph(
    "Deux formes de reponse sont couvertes. En <b>flux SSE</b>, chaque evenement est associe a "
    "son role. En <b>JSON</b>, on lit le texte et les documents par chemin pointe.", S["corps"]))
E(code('''{
  "kind": "http",
  "name": "mon assistant (local)",
  "url": "http://127.0.0.1:3000/api/chat",
  "mode": "sse",
  "body": {"question": "{{question}}", "debug": true},
  "textSource": "text",
  "textField": "delta",
  "stages": [
    {"name": "candidats", "source": "candidates", "itemField": null},
    {"name": "rerank",    "source": "sources",    "itemField": "code"}
  ],
  "usage": {"source": "done"},
  "authentication": {
    "url": "http://127.0.0.1:3000/api/auth/connexion",
    "body": {"email": "{{env:EVALUATION_EMAIL}}",
             "password": "{{env:EVALUATION_PASSWORD}}"}
  }
}'''))
A(Paragraph(
    "<font face='Courier'>itemField</font> sert quand l'API renvoie des objets plutot que des "
    "chaines : <font face='Courier'>[{\"code\": \"A\"}]</font> se lit avec "
    "<font face='Courier'>\"code\"</font>, <font face='Courier'>[\"A\"]</font> sans rien. "
    "L'etape <font face='Courier'>authentication</font> est rejouee une fois, et ses cookies "
    "sont conserves pour tous les appels suivants.", S["corps"]))
A(Paragraph(
    "En mode JSON, <font face='Courier'>textSource</font> devient un chemin "
    "(<font face='Courier'>data.answer</font>) et chaque etage lit une liste par chemin.",
    S["note"]))

A(PageBreak())

# ══════════════════════════════════════════════════════════ jeu de questions
A(Paragraph("Le jeu de questions", S["h1"]))
A(Paragraph(
    "Un fichier JSON Lines, une ligne par cas. Le depot dans l'interface accepte aussi le CSV "
    "d'un tableur et un JSON contenant une liste.", S["corps"]))
E(code('''{"id": "montant-granules",
 "question": "Combien de kWh cumac pour une chaudiere a granules en zone H1 ?",
 "relevant_ids": ["BAR-TH-113"],
 "must_include": ["41 300 kWh cumac"],
 "must_include_variants": {"41 300 kWh cumac": ["41300 kWh cumac"]},
 "must_not_include": [],
 "category": "montant"}'''))
A(tableau(
    ["Champ", "Role"],
    [["id", ("identifiant unique. Deux cas de meme id s'ecraseraient a la renotation, "
            "le chargement echoue donc")],
     ["question", "ce qui est envoye au systeme, tel quel"],
     ["relevant_ids", "les documents qui repondent. <b>Vide = cas de refus</b>"],
     ["must_include", "ce que la reponse doit contenir, typiquement une valeur chiffree"],
     ["must_include_variants", "orthographes equivalentes acceptees, declarees une par une"],
     ["must_not_include", "les pieges, surtout sur un cas de refus"],
     ["category", "etiquette libre servant a ventiler le score (usage, secteur, difficulte)"]],
    [0.26, 0.74], mono=False))
A(Spacer(1, 8))

A(Paragraph("Le cas de refus", S["h2"]))
A(Paragraph(
    "Un cas dont <font face='Courier'>relevant_ids</font> est vide est un cas de refus : la "
    "question sort du corpus, et la seule bonne reponse est de dire qu'on ne sait pas. C'est la "
    "<b>structure</b> du cas qui porte l'information, pas une categorie nommee dans une langue "
    "particuliere.", S["corps"]))
A(Paragraph(
    "Il est reussi a deux conditions : le systeme dit qu'il ne sait pas, ET il ne laisse echapper "
    "aucune valeur interdite. Un systeme qui refuse poliment tout en citant un montant plausible "
    "echoue, et c'est le comportement qui coute un client.", S["corps"]))

A(Paragraph("Les variantes d'orthographe", S["h2"]))
A(Paragraph(
    "Une variante non declaree n'est pas acceptee. Le jeu reste explicite, jamais devinatoire : "
    "si <font face='Courier'>3.7 kWh</font> doit valoir <font face='Courier'>3,7 kWh</font>, "
    "cela s'ecrit. La comparaison tolere en revanche toujours la mise en forme : gras, "
    "echappements Markdown, espaces insecables, accents et casse.", S["corps"]))

A(encadre(
    "<b>La verite terrain se verifie contre le corpus, jamais de memoire.</b> ragscore ne peut "
    "pas le faire a votre place, il ne connait pas votre corpus. Mais c'est la condition pour "
    "que le score veuille dire quelque chose : un jeu de test faux donne confiance a tort, ce "
    "qui est pire que pas de jeu du tout. Sur le corpus CEE, chaque fragment attendu est "
    "verifie present dans la fiche citee avant d'entrer dans le jeu, et la generation echoue "
    "bruyamment sinon.", ROUGE))

A(PageBreak())

# ══════════════════════════════════════════════════════════ indicateurs
A(Paragraph("Les indicateurs, un par un", S["h1"]))
A(Paragraph(
    "Les cas de refus sont <b>exclus</b> de tous les rappels et de tous les rangs : ils n'ont "
    "aucun document pertinent, donc les inclure ferait monter le score sans rien mesurer. Ils "
    "sont notes a part, par « refus corrects ».", S["corps"]))

# ─────────────────────────────────── rappel
A(Paragraph("Rappel par etage", S["h2"]))
A(Paragraph(
    "Pour chaque etage de recuperation : la part des cas ou <b>au moins un</b> document pertinent "
    "s'y trouve. Un etage est une etape nommee de votre chaine, dans l'ordre ou le systeme "
    "l'applique.", S["corps"]))
A(Paragraph(
    "<b>Comment le lire.</b> C'est un entonnoir. Si le rappel chute entre deux etages, c'est le "
    "second qui perd le document. S'il est deja bas au premier, le probleme est dans la recherche "
    "ou dans l'indexation, et aucun reclassement ne le rattrapera.", S["corps"]))
A(tableau(
    ["Ce que vous observez", "Ce que cela signifie", "Ou chercher"],
    [["recherche 100 %, rerank 100 %", "la recuperation n'est pas votre probleme",
      "la generation, ou le jeu de test"],
     ["recherche 100 %, rerank 78 %", "le reranker jette de bons documents",
      "le modele de reclassement, le seuil, le nombre garde"],
     ["recherche 62 %", "le document n'est jamais candidat",
      "le decoupage, les embeddings, le nombre cherche"]],
    [0.3, 0.38, 0.32]))

# ─────────────────────────────────── MRR
A(Paragraph("MRR, rang moyen inverse", S["h2"]))
A(Paragraph(
    "Le rappel dit si le document est la. Le MRR dit <b>a quelle place</b>. Pour chaque cas on "
    "prend l'inverse du rang du meilleur document pertinent dans l'etage final, puis on fait la "
    "moyenne. Un document absent compte zero.", S["corps"]))
A(Paragraph("MRR = moyenne de ( 1 / rang )", S["formule"]))
A(tableau(
    ["Rang du bon document", "Contribution"],
    [["1<sup>er</sup>", "1,000"], ["2<sup>e</sup>", "0,500"], ["3<sup>e</sup>", "0,333"],
     ["5<sup>e</sup>", "0,200"], ["10<sup>e</sup>", "0,100"], ["absent", "0,000"]],
    [0.5, 0.5]))
A(Spacer(1, 8))
A(Paragraph(
    "<b>Exemple reel.</b> Sur les 45 cas du jeu CEE qui attendent une fiche, 42 la placent au "
    "premier rang et 3 au second :", S["corps"]))
E(code(
    f"MRR = (42 x 1,000  +  3 x 0,500) / 45\n"
    f"    = {(42 * 1 + 3 * 0.5):.1f} / 45\n"
    f"    = {(42 * 1 + 3 * 0.5) / 45:.3f}"))
A(Paragraph(
    "<b>Comment le lire.</b> 1,000 signifie « toujours en tete ». La chute est brutale : passer "
    "du premier au second rang coute la moitie. C'est voulu, parce qu'un document cite en "
    "deuxieme position pese deja beaucoup moins dans ce que le modele lit. En dessous de 0,7, la "
    "recuperation ramene le bon document mais mal classe, et le modele travaille dans le bruit.",
    S["corps"]))

# ─────────────────────────────────── nDCG
A(Paragraph("nDCG, qualite du classement", S["h2"]))
A(Paragraph(
    "Meme idee que le MRR, avec une decroissance logarithmique au lieu d'inverse, et surtout la "
    "capacite de compter <b>plusieurs</b> documents pertinents. Le resultat est normalise par le "
    "classement parfait, donc toujours entre 0 et 1.", S["corps"]))
A(Paragraph("gain = somme de ( 1 / log2(rang + 1) ),  puis divise par le classement parfait",
            S["formule"]))
A(tableau(
    ["Rang", "MRR y voit", "nDCG y voit"],
    [["1<sup>er</sup>", "1,000", "1,000"],
     ["2<sup>e</sup>", "0,500", "0,631"],
     ["3<sup>e</sup>", "0,333", "0,500"],
     ["5<sup>e</sup>", "0,200", "0,387"]],
    [0.34, 0.33, 0.33]))
A(Spacer(1, 8))
A(Paragraph(
    f"Sur le meme jeu CEE : nDCG = (42 x 1,000 + 3 x 0,631) / 45 = "
    f"{(42 + 3 * (1 / math.log2(3))) / 45:.3f}, contre 0,967 pour le MRR. L'ecart est normal : "
    "le nDCG punit moins durement un document trouve en deuxieme position.", S["corps"]))
A(Paragraph(
    "<b>Quand il compte vraiment.</b> Des qu'un cas a plusieurs documents pertinents. Le MRR ne "
    "regarde alors que le meilleur et ignore si vous avez trouve les autres ; le nDCG les compte "
    "tous. Sur un jeu a un seul document par question, les deux disent presque la meme chose.",
    S["note"]))

A(PageBreak())

# ─────────────────────────────────── generation
A(Paragraph("Document cite", S["h2"]))
A(Paragraph(
    "La part des reponses qui mentionnent litteralement l'identifiant attendu. La recherche se "
    "fait dans le <b>texte brut</b>, sans normalisation : un identifiant est sensible a la casse "
    "et aux tirets, et <font face='Courier'>bar-th-113</font> n'est pas "
    "<font face='Courier'>BAR-TH-113</font>.", S["corps"]))
A(Paragraph(
    "<b>Comment le lire.</b> Un ecart entre « trouve apres rerank » et « document cite » signifie "
    "que le systeme a le bon extrait sous les yeux et ne le nomme pas. C'est un probleme de "
    "consigne, pas de recuperation. Pour un professionnel qui doit verifier une source, c'est "
    "redhibitoire.", S["corps"]))

A(Paragraph("Valeur attendue", S["h2"]))
A(Paragraph(
    "La part des reponses contenant tous les fragments de "
    "<font face='Courier'>must_include</font>. C'est l'indicateur le plus severe et le plus utile "
    ": il ne juge pas le style, il verifie le chiffre.", S["corps"]))
A(Paragraph(
    "La comparaison normalise la mise en forme (gras, echappements Markdown, espaces insecables, "
    "accents, casse) et rien d'autre. <font face='Courier'>19 900</font> ne passe pas pour "
    "<font face='Courier'>19 800</font>.", S["corps"]))

A(Paragraph("Refus corrects", S["h2"]))
A(Paragraph(
    "Calcule sur les seuls cas de refus. Reussi si le systeme dit qu'il ne sait pas <b>et</b> ne "
    "produit aucune valeur interdite. La detection du refus se fait par motifs, et c'est la "
    "partie fragile de la notation : un refus parfaitement formule mais non reconnu compte comme "
    "un echec et sous-estime le systeme. Les motifs par defaut tolerent les incises, comme "
    "« je ne peux <i>donc</i> pas repondre ».", S["corps"]))
A(Paragraph(
    "Les motifs sont propres a une langue et s'injectent : un jeu francais et un jeu anglais "
    "n'utilisent pas les memes.", S["note"]))

A(Paragraph("Aucune valeur interdite", S["h2"]))
A(Paragraph(
    "Calcule sur <b>tous</b> les cas, refus compris. C'est le garde-fou contre l'invention : une "
    "valeur que la reponse ne devait jamais contenir et qui s'y trouve.", S["corps"]))

A(Paragraph("Cas reussis", S["h2"]))
A(Paragraph(
    "Le score global, celui qu'on annonce. Un cas ordinaire est reussi si le document est trouve, "
    "que toutes les valeurs attendues sont presentes et qu'aucune valeur interdite ne l'est. Un "
    "cas de refus est reussi selon la regle ci-dessus.", S["corps"]))

A(Paragraph("Ventilation par categorie", S["h2"]))
A(Paragraph(
    "Les memes chiffres, decoupes par l'etiquette <font face='Courier'>category</font>. C'est "
    "souvent la seule vue qui montre quelque chose : un score global de 94 % peut cacher un type "
    "de question a 60 %. Sur le corpus CEE, les categories separent routage, montant, duree, "
    "condition, version et refus.", S["corps"]))

A(Paragraph("Ce qu'aucun de ces indicateurs ne mesure", S["h2"]))
A(Paragraph(
    "La qualite d'une reponse ouverte. « Explique-moi la condition de mise en oeuvre » n'a pas de "
    "fragment attendu verifiable, donc seule la recuperation y est notee. C'est la limite assumee "
    "de la notation deterministe, et la raison pour laquelle un juge LLM viendra la completer, "
    "valide au prealable contre un annotateur humain.", S["corps"]))
A(Paragraph(
    "Ils ne mesurent pas non plus la latence, la robustesse aux questions malveillantes, ni le "
    "comportement sur un corpus qui change.", S["note"]))

A(PageBreak())

# ══════════════════════════════════════════════════════════ couts
A(Paragraph("Ce que ca consomme", S["h1"]))
A(Paragraph(
    "ragscore n'appelle aucun modele. Ce qui coute, c'est le systeme mesure : une question "
    "declenche une vectorisation, un reclassement et une generation, donc <b>deux fournisseurs</b>.",
    S["corps"]))
A(tableau(
    ["Action", "Appels au systeme", "Cout"],
    [["Lancer la mesure, 50 questions", "50", "0,80 a 1,20 $"],
     ["Tester sur une question", "1", "environ 0,02 $"],
     ["Renoter un rapport", "0", "gratuit"],
     ["Afficher un rapport", "0", "gratuit"],
     ["Toute la navigation dans l'interface", "0", "gratuit"]],
    [0.5, 0.24, 0.26]))
A(Spacer(1, 10))
A(Paragraph("Tarifs de generation, en dollars par million de jetons", S["h2"]))
A(tableau(
    ["Modele", "Entree", "Sortie", "Mesure sur le jeu CEE", "Cout des 50"],
    [["claude-sonnet-5", "2 $", "10 $", "50 / 50", "environ 0,80 $"],
     ["claude-haiku-4-5", "1 $", "5 $", "49 / 50", "environ 0,30 $"],
     ["claude-opus-5", "5 $", "25 $", "non mesure", "environ 2 $"]],
    [0.3, 0.13, 0.13, 0.25, 0.19], mono=False))
A(Spacer(1, 8))
A(Paragraph(
    "L'unique echec de Haiku 4.5 portait sur un raisonnement dans un tableau deja recupere, pas "
    "sur une recuperation. Il convient tres bien pour eprouver un cablage ou iterer sur un "
    "decoupage ; le chiffre que l'on publie se mesure avec le modele que l'on livre.", S["corps"]))
A(encadre(
    "<b>Le cout affiche sous-estime la realite.</b> Il ne compte que les jetons de generation. "
    "Les appels de vectorisation et de reclassement ne sont pas comptes, alors que le total se "
    "presente comme complet. L'ecart est faible, la generation pesant beaucoup plus lourd, mais "
    "il n'est pas nul.", ROUGE))

A(Paragraph("La renotation, et pourquoi elle existe", S["h2"]))
A(Paragraph(
    "Le rapport separe <b>ce que le systeme a repondu</b> de <b>la note qu'on lui a mise</b>. "
    "Quand la correction porte sur le harnais (detection du refus, normalisation, variante "
    "acceptee, fragment attendu mal recopie) et non sur le systeme, les reponses sont identiques "
    "au caractere pres : les renoter ne coute rien.", S["corps"]))
A(Paragraph(
    "Ce n'est pas un confort. Trois executions completes d'un jeu de 50 questions ont ete "
    "gaspillees faute de ce mode.", S["corps"]))
A(tableau(
    ["Vous avez change...", "Renoter suffit ?"],
    [["une valeur attendue, une variante, un motif de refus", "oui, et c'est gratuit"],
     ["l'etiquette ou l'intitule d'un cas", "oui"],
     ["le decoupage, les embeddings, le reranker, le prompt, le modele", "non, il faut remesurer"],
     ["ajoute de nouveaux cas au jeu", "non pour ceux-la, ils seront ignores"]],
    [0.62, 0.38]))

A(PageBreak())

# ══════════════════════════════════════════════════════════ secrets
A(Paragraph("Les secrets", S["h1"]))
A(Paragraph(
    "Une declaration de systeme ne stocke <b>jamais</b> une valeur secrete. On y ecrit "
    "<font face='Courier'>{{env:NOM}}</font>, et la valeur est lue dans l'environnement du "
    "processus au moment de l'appel. Une variable manquante est signalee par son nom, pas par une "
    "erreur obscure.", S["corps"]))
E(code(
    'DATABASE_URL=... VOYAGE_API_KEY=... ANTHROPIC_API_KEY=... uv run ragscore ui\n'
    '\n'
    '# ou, si elles vivent deja dans un fichier :\n'
    'set -a && source ~/mon-projet/.env && set +a && uv run ragscore ui'))
A(tableau(
    ["Garde-fou", "Ce qu'il fait"],
    [["{{env:NOM}}", "le fichier porte le nom de la variable, jamais sa valeur"],
     ["droits 600", "les declarations enregistrees sont lisibles par leur seul proprietaire"],
     [".gitignore", "le dossier des declarations n'est pas versionne"],
     ["boucle locale", "l'interface n'ecoute que sur 127.0.0.1, jamais sur le reseau"]],
    [0.26, 0.74]))
A(Spacer(1, 8))
A(Paragraph(
    "Un mot de passe ecrit en clair dans une declaration finirait dans un fichier, puis dans une "
    "sauvegarde, puis dans un depot.", S["note"]))

# ══════════════════════════════════════════════════════════ commandes
A(Paragraph("Les commandes", S["h1"]))
A(tableau(
    ["Commande", "Ce qu'elle fait", "Cout"],
    [["uv run ragscore ui", "ouvre l'interface locale sur 127.0.0.1:7654", "gratuit"],
     ["uv run ragscore show --report R", "affiche le resume d'un rapport", "gratuit"],
     ["uv run ragscore rescore --cases J --report R",
      "renote les reponses stockees. Ecrase R, sauf si --out est donne", "gratuit"],
     ["uv run python examples/minimal.py",
      "exemple complet sans base ni cle d'API", "gratuit"]],
    [0.4, 0.44, 0.16], mono=False))

A(Paragraph("Utilisation en bibliotheque", S["h2"]))
A(Paragraph(
    "L'interface n'est qu'une facade : tout ce qu'elle fait est faisable en Python, et rien n'est "
    "stocke dans un format qu'elle serait seule a relire.", S["corps"]))
E(code('''from pathlib import Path
from ragscore import loadCases, runEvaluation, writeReport
from ragscore.display import formatSummary

class MonSysteme:
    def answer(self, question: str) -> Answer:
        ...  # interroge votre RAG, rend le texte et les etages

cases = loadCases(Path("data/testset.jsonl"))
outcomes, summary, observations = runEvaluation(MonSysteme(), cases)
writeReport(Path("data/rapport.json"), outcomes, summary, observations)
print(formatSummary(summary))'''))

# ══════════════════════════════════════════════════════════ reference
A(Paragraph("Reference de configuration", S["h1"]))
A(Paragraph("Moteur integre (kind: vector)", S["h2"]))
A(tableau(
    ["Champ", "Defaut", "Role"],
    [["databaseUrl", "{{env:DATABASE_URL}}", "connexion PostgreSQL avec pgvector"],
     ["table", "chunk", "table portant les vecteurs, si aucune jointure"],
     ["fromClause", "(vide)", "relation complete avec jointure, SQL assume"],
     ["identifierColumn", "code", "colonne de l'identifiant, qualifiable"],
     ["textColumn", "content", "colonne du texte envoye au modele"],
     ["embeddingColumn", "embedding", "colonne du vecteur"],
     ["whereClause", "(vide)", "filtre additionnel, SQL assume"],
     ["searchLimit", "40", "candidats ramenes par la recherche vectorielle"],
     ["rerankKeep", "8", "candidats gardes apres reclassement"],
     ["maxPassages", "14", "passages envoyes au modele"],
     ["embeddingModel", "voyage-3.5", "modele de vectorisation"],
     ["rerankModel", "rerank-2.5", "modele de reclassement"],
     ["generationModel", "claude-sonnet-5", "modele de generation"],
     ["systemPrompt", "citation et refus", "consigne, elle decide du score"],
     ["inputPricePerMillion", "2.0", "tarif d'entree, pour annoncer le cout"],
     ["outputPricePerMillion", "10.0", "tarif de sortie"]],
    [0.27, 0.25, 0.48], mono=True))

A(Spacer(1, 10))
A(Paragraph("API a brancher (kind: http)", S["h2"]))
A(tableau(
    ["Champ", "Defaut", "Role"],
    [["url", "(requis)", "point d'entree interroge"],
     ["mode", "sse", "« sse » pour un flux, « json » pour une reponse unique"],
     ["method", "POST", "verbe HTTP"],
     ["body", '{"question": "{{question}}"}', "corps envoye, la question y est substituee"],
     ["headers", "{}", "en-tetes, ou {{env:NOM}} pour un jeton"],
     ["textSource", "text", "evenement (sse) ou chemin (json) du texte"],
     ["textField", "delta", "champ du fragment, en sse uniquement"],
     ["stages", "[]", "un etage par etape : nom, source, itemField"],
     ["usage", "{}", "ou lire la consommation rapportee"],
     ["authentication", "null", "appel prealable dont les cookies sont conserves"],
     ["timeoutSeconds", "180", "delai maximal par question"],
     ["errorSource", "error", "evenement signalant une erreur serveur"]],
    [0.22, 0.28, 0.5], mono=True))

A(PageBreak())

# ══════════════════════════════════════════════════════════ depannage
A(Paragraph("Depannage", S["h1"]))
A(tableau(
    ["Message", "Cause et correction"],
    [["command not found: ragscore",
      ("l'environnement n'est pas actif. Prefixez par uv run, ou activez avec "
      "source .venv/bin/activate")],
     ["la variable d'environnement X n'est pas definie",
      "le processus a ete lance sans elle. Relancez l'interface avec la variable"],
     ["connexion a la base impossible",
      "la base n'est pas demarree, ou databaseUrl est faux"],
     ["la recherche a echoue",
      "un nom de table ou de colonne est faux, ou la jointure manque"],
     ["le systeme a repondu 500",
      "l'application mesuree ne tourne pas, ou refuse la requete"],
     ["la connexion a echoue (401)",
      "les identifiants du connecteur sont faux ou absents"],
     ["aucun texte trouve au chemin X",
      "mode json : le chemin du texte est faux. Les cles disponibles sont listees"],
     ["un etage remonte vide au test",
      "le nom d'evenement, de chemin ou de champ est faux"],
     ["aucune colonne de question reconnue",
      "le fichier depose n'a pas de colonne question, prompt, demande ou requete"],
     ["identifiants en double",
      "deux cas portent le meme id ; ils s'ecraseraient a la renotation"],
     ["ne contient pas d'observations",
      "le rapport vient d'un format anterieur et ne peut pas etre renote"],
     ["le moteur integre a besoin de dependances",
      "relancez uv sync --extra engine"]],
    [0.33, 0.67]))

# ══════════════════════════════════════════════════════════ limites
A(Paragraph("Limites connues", S["h1"]))
A(tableau(
    ["Limite", "Consequence"],
    [["Pas de juge pour les reponses ouvertes",
      "une question sans fragment verifiable n'est notee que sur la recuperation"],
     ["Le cout affiche ignore la vectorisation et le reclassement",
      "le total annonce est legerement inferieur au reel"],
     ["Les ablations ne sont pas commutables",
      "comparer avec et sans reclassement demande deux declarations et deux mesures"],
     ["Le moteur integre n'ingere rien",
      "il faut une base deja vectorisee ; ragscore ne construit pas l'index"],
     ["La detection du refus est par motifs",
      "une formulation inattendue compte comme un echec et sous-estime le systeme"]],
    [0.38, 0.62]))
A(Spacer(1, 8))
A(Paragraph(
    "<b>La suite.</b> Un juge LLM pour les reponses ouvertes, <b>valide contre un annotateur "
    "humain</b> avant de publier la moindre metrique de qualite : l'accord entre le juge et "
    "l'humain se mesure par le kappa de Cohen, et sans ce prealable un score de qualite ne "
    "prouve rien. Puis la commutation des etages, pour mesurer les ablations.", S["corps"]))

A(Spacer(1, 10))
A(HRFlowable(width="100%", thickness=0.8, color=BORD, spaceAfter=6))
A(Paragraph(
    "ragscore, 58 tests. Documentation regeneree par docs/construire_documentation.py. "
    "Mise a jour du 18 septembre 2026.", S["note"]))

sortie = Path(__file__).parent / "ragscore.pdf"
document = SimpleDocTemplate(
    str(sortie), pagesize=A4,
    leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=20 * mm,
    title="ragscore, documentation",
    subject="Mesurer un systeme RAG : les deux facons de faire, les indicateurs, les couts",
)
document.build(histoire, onFirstPage=pied, onLaterPages=pied)
print(f"ecrit : {sortie}")
