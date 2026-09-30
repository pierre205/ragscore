"""Lecture d'un jeu de questions depose par l'utilisateur.

Trois formats acceptes, parce que personne ne redige cinquante questions en JSON Lines :
le JSONL natif, le CSV (celui que produit un tableur), et un JSON contenant une liste. La
lecture est tolerante sur les noms de colonnes et intolerante sur le reste : un jeu mal
compris donnerait un score faux, ce qui est pire que pas de score du tout.
"""

from __future__ import annotations

import csv
import io
import json

from ragscore.case import Case

# Noms de colonnes acceptes, par champ. Le premier trouve gagne.
COLUMN_ALIASES = {
    "identifier": ["id", "identifier", "identifiant", "cle"],
    "question": ["question", "prompt", "demande", "requete"],
    "relevantIdentifiers": ["relevant_ids", "documents", "document", "attendu", "fiche", "source"],
    "mustInclude": ["must_include", "attendu_dans_reponse", "valeur_attendue", "contient"],
    "mustNotInclude": ["must_not_include", "interdit", "ne_contient_pas"],
    "category": ["category", "categorie", "type"],
    "referenceAnswer": ["reference_answer", "reponse_de_reference", "reponse"],
}
LIST_SEPARATORS = ["|", ";"]


class CaseImportError(ValueError):
    """Erreur de lecture, formulee pour etre affichee telle quelle a l'utilisateur."""


def splitList(value: str) -> list[str]:
    if not value or not value.strip():
        return []
    for separator in LIST_SEPARATORS:
        if separator in value:
            return [piece.strip() for piece in value.split(separator) if piece.strip()]
    return [value.strip()]


def pickColumn(row: dict, fieldName: str) -> str:
    lowered = {str(key).strip().lower(): value for key, value in row.items() if key}
    for alias in COLUMN_ALIASES[fieldName]:
        if alias in lowered and lowered[alias] not in (None, ""):
            value = lowered[alias]
            if isinstance(value, list):
                return LIST_SEPARATORS[0].join(str(item) for item in value)
            return str(value)
    return ""


def caseFromRow(row: dict, position: int) -> Case:
    question = pickColumn(row, "question")
    if not question:
        raise CaseImportError(
            f"ligne {position} : aucune colonne de question reconnue. "
            f"Colonnes acceptees : {', '.join(COLUMN_ALIASES['question'])}"
        )
    return Case(
        identifier=pickColumn(row, "identifier") or f"cas-{position}",
        question=question,
        relevantIdentifiers=splitList(pickColumn(row, "relevantIdentifiers")),
        mustInclude=splitList(pickColumn(row, "mustInclude")),
        mustNotInclude=splitList(pickColumn(row, "mustNotInclude")),
        category=pickColumn(row, "category"),
        referenceAnswer=pickColumn(row, "referenceAnswer") or None,
    )


def readCases(content: str, filename: str) -> list[Case]:
    """Lit un jeu depuis le contenu d'un fichier depose, quel que soit son format."""
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    text = content.strip()
    if not text:
        raise CaseImportError("le fichier est vide")

    if suffix == "csv" or (suffix not in {"jsonl", "json"} and "," in text.splitlines()[0]):
        rows = list(csv.DictReader(io.StringIO(content)))
        if not rows:
            raise CaseImportError("le CSV ne contient aucune ligne de donnees")
        cases = [caseFromRow(row, position) for position, row in enumerate(rows, start=1)]
    elif suffix == "json" or text.startswith("["):
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise CaseImportError("le JSON doit contenir une liste de cas")
        cases = [caseFromRow(row, position) for position, row in enumerate(payload, start=1)]
    else:
        cases = [
            caseFromRow(json.loads(line), position)
            for position, line in enumerate(text.splitlines(), start=1)
            if line.strip()
        ]

    identifiers = [case.identifier for case in cases]
    duplicates = {identifier for identifier in identifiers if identifiers.count(identifier) > 1}
    if duplicates:
        raise CaseImportError(
            f"identifiants en double : {', '.join(sorted(duplicates))}. "
            "Deux cas de meme identifiant s'ecrasent a la re-notation."
        )
    return cases
