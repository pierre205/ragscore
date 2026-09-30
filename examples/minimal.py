"""Exemple complet et executable : mesurer un systeme en 30 lignes.

Le « systeme » mesure ici est une fausse recherche sur trois documents, pour que l'exemple
tourne sans base ni cle d'API. Un vrai systeme se branche exactement pareil : il suffit que
sa methode `answer` rende le texte produit et les documents retenus par chaque etage.

    python examples/minimal.py
"""

from __future__ import annotations

from ragscore import Answer, Case, RetrievalStage, runEvaluation
from ragscore.display import formatSummary

CORPUS = {
    "GUIDE-01": "La garantie couvre les pieces pendant 24 mois.",
    "GUIDE-02": "Le delai de retractation est de 14 jours.",
    "GUIDE-03": "La livraison standard prend 3 jours ouvres.",
}


class RechercheParMotsCles:
    """Un systeme minuscule : il cherche des mots, puis recopie le meilleur document."""

    def answer(self, question: str) -> Answer:
        words = set(question.lower().split())
        scored = sorted(
            CORPUS,
            key=lambda identifier: len(words & set(CORPUS[identifier].lower().split())),
            reverse=True,
        )
        candidates = scored[:3]  # premier etage : recherche large
        retained = scored[:1]  # second etage : on ne garde que le meilleur
        text = f"{CORPUS[retained[0]]} (source : {retained[0]})"
        return Answer(
            text=text,
            stages=[
                RetrievalStage("recherche", candidates),
                RetrievalStage("selection", retained),
            ],
        )


CASES = [
    Case(
        identifier="garantie",
        question="Quelle est la duree de garantie des pieces ?",
        relevantIdentifiers=["GUIDE-01"],
        mustInclude=["24 mois"],
        category="duree",
    ),
    Case(
        identifier="retractation",
        question="Quel est le delai de retractation ?",
        relevantIdentifiers=["GUIDE-02"],
        mustInclude=["14 jours"],
        category="duree",
    ),
    Case(
        identifier="hors-corpus",
        question="Quel est le taux de TVA applicable ?",
        relevantIdentifiers=[],  # vide = le systeme doit refuser
        mustNotInclude=["24 mois", "14 jours"],
        category="refus",
    ),
]


if __name__ == "__main__":
    outcomes, summary, _ = runEvaluation(RechercheParMotsCles(), CASES)

    for outcome in outcomes:
        verdict = "ok" if outcome.succeeded else "KO"
        print(f"  {verdict}  {outcome.identifier:14} rang={outcome.rank}")
    print("\n" + formatSummary(summary))
