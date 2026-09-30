"""Le contrat que doit remplir un systeme pour etre mesurable.

`ragscore` ne sait rien du systeme qu'il note : il lui pose une question et recoit une
`Answer`. Tout le reste (base vectorielle, reranker, modele, langue) lui est etranger.

Le point important est `stages` : la recuperation est presque toujours un enchainement
d'etages (recherche large, fusion, reclassement), et une mesure globale ne dit pas OU ca
casse. Si le bon document n'est pas dans le premier etage, aucun reclassement ne l'y fera
apparaitre, et travailler le reranker est une perte de temps. Chaque etage est donc mesure
separement, dans l'ordre ou le systeme les applique.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class RetrievedPassage:
    """Un passage retenu, avec son texte.

    Les etages ne portent que des identifiants, ce qui suffit a mesurer la recuperation et
    ne coute rien a stocker. Le TEXTE, lui, n'est necessaire qu'aux outils qui jugent le
    contenu (ragas et ses semblables) : il est donc facultatif, et un systeme qui ne peut
    pas le fournir reste parfaitement mesurable.
    """

    identifier: str
    text: str


@dataclass(frozen=True)
class RetrievalStage:
    name: str
    # Identifiants des documents retenus par cet etage, du plus pertinent au moins pertinent.
    documentIdentifiers: list[str]


@dataclass
class Answer:
    text: str
    stages: list[RetrievalStage] = field(default_factory=list)
    # Le contenu reellement soumis au generateur, quand le systeme sait le rendre.
    passages: list[RetrievedPassage] = field(default_factory=list)
    # Ce que l'appel a coute, tel que le systeme le rapporte. Une evaluation qui ne dit pas
    # son cout laisse decouvrir la facture apres coup.
    inputTokens: int = 0
    outputTokens: int = 0
    estimatedCostUsd: float = 0.0

    @property
    def finalStage(self) -> RetrievalStage:
        """L'etage qui alimente reellement la generation, donc celui qui porte le rang."""
        if not self.stages:
            return RetrievalStage(name="", documentIdentifiers=[])
        return self.stages[-1]


class MeasurableSystem(Protocol):
    """Le systeme sous mesure. Une seule methode a implementer."""

    def answer(self, question: str) -> Answer: ...
