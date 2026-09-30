"""Le cas d'evaluation : une question, et ce qu'on attend de la reponse.

Un cas dont `relevantIdentifiers` est vide est un **cas de refus** : la question sort du
corpus, et la seule bonne reponse est de dire qu'on ne sait pas. Cette convention remplace
une categorie nommee en dur (« refus ») qui obligeait chaque projet a reprendre le meme mot
francais ; ici, c'est la structure du cas qui porte l'information, pas une chaine.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Case:
    identifier: str
    question: str
    # Les documents qui repondent a la question. Vide = la question doit etre refusee.
    relevantIdentifiers: list[str] = field(default_factory=list)
    # Fragments qui doivent apparaitre dans la reponse (typiquement une valeur chiffree).
    mustInclude: list[str] = field(default_factory=list)
    # Fragments qui ne doivent JAMAIS apparaitre (les pieges d'un cas de refus).
    mustNotInclude: list[str] = field(default_factory=list)
    # Orthographes equivalentes acceptees pour un fragment attendu, declarees une par une.
    # Une variante non declaree n'est pas acceptee : le jeu reste explicite, pas devinatoire.
    mustIncludeVariants: dict[str, list[str]] = field(default_factory=dict)
    # Etiquette libre servant a ventiler le score final (usage, difficulte, secteur...).
    category: str = ""
    referenceAnswer: str | None = None

    @property
    def expectsRefusal(self) -> bool:
        return not self.relevantIdentifiers


# Correspondance entre le format de fichier (serpent, stable) et les attributs (chameau).
FIELD_NAMES = {
    "id": "identifier",
    "question": "question",
    "relevant_ids": "relevantIdentifiers",
    "must_include": "mustInclude",
    "must_not_include": "mustNotInclude",
    "must_include_variants": "mustIncludeVariants",
    "category": "category",
    "reference_answer": "referenceAnswer",
}


def caseFromDictionary(raw: dict) -> Case:
    known = {attribute: raw[key] for key, attribute in FIELD_NAMES.items() if key in raw}
    return Case(**known)


def caseToDictionary(case: Case) -> dict:
    return {key: getattr(case, attribute) for key, attribute in FIELD_NAMES.items()}


def loadCases(path: Path) -> list[Case]:
    """Lit un jeu au format JSON Lines, une ligne par cas.

    Les identifiants en double font echouer le chargement : deux cas de meme identifiant
    s'ecrasent silencieusement a la re-notation, et le jeu perd des cas sans rien dire.
    """
    cases = [
        caseFromDictionary(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    identifiers = [case.identifier for case in cases]
    duplicates = {identifier for identifier in identifiers if identifiers.count(identifier) > 1}
    if duplicates:
        raise ValueError(f"identifiants de cas en double : {', '.join(sorted(duplicates))}")
    return cases


def writeCases(cases: list[Case], path: Path) -> None:
    path.write_text(
        "\n".join(json.dumps(caseToDictionary(case), ensure_ascii=False) for case in cases) + "\n",
        encoding="utf-8",
    )
