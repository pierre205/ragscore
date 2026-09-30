# ragscore

**Documentation complete : [`docs/ragscore.pdf`](docs/ragscore.pdf)** (13 pages) — les deux
facons de mesurer, le format du jeu, chaque indicateur explique et calcule, les couts, la
reference de configuration, le depannage. Regeneree par
`uv run --extra docs python docs/construire_documentation.py`.

Harnais de mesure pour systemes RAG. Il note **la recuperation et la generation separement**,
de facon **deterministe**, et produit un rapport **re-notable sans rappeler le systeme**.

Il ne sait rien du systeme qu'il mesure : ni la base vectorielle, ni le modele, ni la langue,
ni le domaine. On lui donne un jeu de cas et un objet qui repond a une question.

## Pourquoi

Un score unique ne dit pas ou corriger. Si le bon document n'est pas dans le premier etage de
recuperation, aucun reclassement ne l'y fera apparaitre, et travailler le reranker est une
perte de temps. Chaque etage est donc mesure separement, dans l'ordre ou le systeme l'applique.

Et la notation ne passe pas par un modele : une valeur attendue est presente au caractere pres
(a la mise en forme pres) ou elle ne l'est pas. Un juge LLM se justifie pour une reponse
ouverte, jamais pour un chiffre.

## Utilisation

```python
from ragscore import Case, RefusalDetector, loadCases, runEvaluation, writeReport
from ragscore.display import formatSummary

class MonSysteme:
    def answer(self, question: str) -> Answer:
        ...  # interroge votre RAG, renvoie le texte et les etages de recuperation

cases = loadCases(Path("data/testset.jsonl"))
outcomes, summary, observations = runEvaluation(MonSysteme(), cases)
writeReport(Path("data/rapport.json"), outcomes, summary, observations)
print(formatSummary(summary))
```

Re-noter un rapport existant, sans un seul appel facture :

```bash
uv run ragscore rescore --cases data/testset.jsonl --report data/rapport.json
uv run ragscore show --report data/rapport.json
```

## Deux facons de mesurer

Elles ne repondent pas a la meme question, et il faut les deux.

| Sorte | Ce que vous branchez | La question a laquelle elle repond |
| --- | --- | --- |
| `http` | l'API que vous livrez | **votre produit** est-il bon ? |
| `vector` | une base vectorisee et deux cles | **cette approche** est-elle bonne ? |

Brancher l'API reste la mesure qui compte avant de vendre : aucune reimplementation ne la
remplace, parce que deux chemins de requete divergent des qu'on touche a l'un, et
l'evaluation finit par noter autre chose que ce qu'on livre.

Le **moteur integre** repond a l'autre question, celle qu'on se pose en amont : ce
decoupage vaut-il mieux que celui-la, ce reranker sert-il a quelque chose. Il execute la
chaine complete (vectorisation de la question, recherche, reclassement, generation) sans
qu'aucune application n'existe. On lui declare la base, les colonnes et les modeles.

```json
{
  "kind": "vector",
  "name": "mon corpus",
  "databaseUrl": "{{env:DATABASE_URL}}",
  "fromClause": "chunk JOIN document ON document.id = chunk.documentid",
  "identifierColumn": "document.code",
  "textColumn": "chunk.content",
  "embeddingColumn": "chunk.embedding"
}
```

`examples/moteur-assistant-cee.json` est celui qui mesure reellement le corpus CEE.
Installation : `uv sync --extra engine`.

**Un rapport produit par le moteur integre ne doit pas etre presente comme la mesure du
produit.** Il porte le nom du moteur, et son libelle le rappelle.

## L'interface

```bash
uv sync --extra ui
uv run ragscore ui
```

`uv run` lance la commande dans l'environnement du projet sans qu'il soit besoin de
l'activer. Sans lui, `ragscore` reste introuvable : le programme est installe dans
`.venv/bin`, qui n'est pas dans le `PATH` du terminal.

Une page sur `http://127.0.0.1:7654`, servie par ragscore lui-meme : pas de npm, pas d'etape
de construction, pas de second environnement. Elle fait trois choses.

1. **Deposer un jeu de questions** : glissez un `.csv`, un `.jsonl` ou un `.json`. Les noms
   de colonnes usuels sont reconnus, en francais comme en anglais, et un jeu mal forme est
   refuse avec la raison, pas avec une trace d'erreur.
2. **Declarer le systeme a mesurer** : une URL, la forme de la requete, et pour chaque etage
   de recuperation l'evenement ou le chemin qui porte les identifiants. Le bouton
   « Tester sur une question » verifie le cablage avant de payer cinquante appels.
3. **Mesurer** : progression cas par cas, resultats, et un bouton qui renote sans rappeler
   le systeme.

**Aucune ligne de Python n'est necessaire** pour mesurer un systeme servi en HTTP. Ecrire une
classe reste possible, et reste la seule voie pour un systeme qui n'est pas derriere une API.

### Les secrets

Un connecteur ne stocke jamais un mot de passe : ecrivez `{{env:NOM}}` et la valeur est lue
dans l'environnement du processus au moment de l'appel. Lancez donc l'interface avec les
variables dont vos connecteurs ont besoin :

```bash
EVALUATION_EMAIL=... EVALUATION_PASSWORD=... uv run ragscore ui
```

Les connecteurs enregistres sont ecrits en `600` et ignores par git, parce qu'ils peuvent
porter une URL interne. L'interface n'ecoute que sur la boucle locale.

### Exemple de connecteur

`examples/connecteur-assistant-cee.json` branche un assistant servi en SSE avec connexion
prealable, deux etages de recuperation et releve de consommation. C'est celui qui mesure
reellement `assistant-cee`.

## Le jeu de cas

Un fichier JSON Lines, une ligne par cas.

```json
{"id": "montant-granules", "question": "Combien de kWh cumac pour une chaudiere a granules en zone H1 ?",
 "relevant_ids": ["BAR-TH-113"], "must_include": ["41 300 kWh cumac"],
 "must_include_variants": {"41 300 kWh cumac": ["41300 kWh cumac"]}, "category": "montant"}
```

- `relevant_ids` **vide** = cas de refus : la question sort du corpus, et la seule bonne
  reponse est de dire qu'on ne sait pas. C'est la structure du cas qui porte l'information,
  pas une categorie nommee en dur dans une langue.
- `must_include` : ce que la reponse doit contenir, typiquement une valeur chiffree.
- `must_include_variants` : orthographes equivalentes acceptees, **declarees une par une**.
  Une variante non declaree n'est pas acceptee : le jeu reste explicite, pas devinatoire.
- `must_not_include` : les pieges, surtout sur un cas de refus.

**La vérité terrain se vérifie contre le corpus, pas de memoire.** ragscore ne peut pas le
faire a votre place (il ne connait pas votre corpus), mais c'est la condition pour que le
score veuille dire quelque chose : un jeu de test faux donne confiance a tort.

## Metriques

| Metrique | Ce qu'elle mesure |
| --- | --- |
| `recallByStage` | le bon document survit-il a chaque etage de recuperation |
| `meanReciprocalRank` | a quel rang, en moyenne, dans l'etage final |
| `normalisedDiscountedGain` | qualite du classement (nDCG a pertinence binaire) |
| `citedRelevant` | le systeme cite-t-il le document attendu |
| `mustIncludeSatisfied` | la valeur attendue est-elle dans la reponse |
| `refusalCorrect` | refuse-t-il bien hors corpus, sans lacher de valeur interdite |
| `noForbiddenValue` | aucune valeur interdite produite, tous cas confondus |

Les cas de refus sont exclus des rappels : ils n'ont pas de document pertinent, donc les
inclure ferait monter le score sans rien mesurer.

## La re-notation

Le rapport separe **ce que le systeme a repondu** de **la note qu'on lui a mise**. Quand la
correction porte sur le harnais (detection du refus, normalisation, variante acceptee) et non
sur le systeme, les reponses sont identiques au caractere pres et les re-noter ne coute rien.

Ce n'est pas un confort : trois executions completes d'un jeu de 50 questions ont ete
gaspillees faute de ce mode.

## Etat

Mesure deterministe, interface locale et moteur integre : faits, 58 tests. Premier
consommateur : `assistant-cee` (50 cas), mesure par son API, par le moteur integre, et
par code.

Reste a faire : juge LLM pour les reponses ouvertes, **valide contre un annotateur humain**
(accord juge / humain, Cohen's kappa) avant de publier la moindre metrique de qualite ; et
commutation des etages pour mesurer les ablations (avec et sans reclassement, dense contre
hybride).

## Licence

MIT, voir [`LICENSE`](LICENSE).
