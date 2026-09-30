"""Notation d'un cas, puis agregation en resume.

Deux principes tiennent tout le module :

1. **La recuperation et la generation se notent separement.** Un systeme qui trouve le bon
   document et le resume mal n'a pas le meme probleme qu'un systeme qui ne le trouve pas.
   Un score unique melange les deux et ne dit ou corriger ni l'un ni l'autre.
2. **La notation est deterministe.** Aucune valeur attendue n'est appreciee par un modele :
   elle est presente au caractere pres (a la mise en forme pres) ou elle ne l'est pas. Un
   juge LLM se justifie pour une reponse ouverte, jamais pour un chiffre.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ragscore.case import Case
from ragscore.normalise import normaliseForComparison
from ragscore.refusal import RefusalDetector
from ragscore.system import Answer


@dataclass
class CaseOutcome:
    identifier: str
    category: str
    question: str
    relevantIdentifiers: list[str]
    # Par etage de recuperation : le bon document y est-il ? Ordre = ordre des etages.
    stageHits: dict[str, bool] = field(default_factory=dict)
    # Rang du meilleur document pertinent dans l'etage final, 1 = premier. None = absent.
    rank: int | None = None
    normalisedDiscountedGain: float = 0.0
    citedRelevant: bool = False
    mustIncludeSatisfied: bool = True
    mustNotIncludeRespected: bool = True
    refused: bool = False
    answer: str = ""
    retrievedIdentifiers: list[str] = field(default_factory=list)
    inputTokens: int = 0
    outputTokens: int = 0
    estimatedCostUsd: float = 0.0

    @property
    def expectsRefusal(self) -> bool:
        return not self.relevantIdentifiers

    @property
    def succeeded(self) -> bool:
        """Reussite du cas, au sens ou on le compterait dans « n sur 50 »."""
        if self.expectsRefusal:
            return self.refused and self.mustNotIncludeRespected
        return (
            self.rank is not None and self.mustIncludeSatisfied and self.mustNotIncludeRespected
        )


def fragmentIsPresent(fragment: str, case: Case, comparableAnswer: str) -> bool:
    """Le fragment attendu, ou l'une de ses orthographes equivalentes declarees."""
    spellings = [fragment, *case.mustIncludeVariants.get(fragment, [])]
    return any(normaliseForComparison(spelling) in comparableAnswer for spelling in spellings)


def bestRank(relevantIdentifiers: list[str], retrieved: list[str]) -> int | None:
    """Rang (1 = premier) du premier document pertinent rencontre."""
    ranks = [
        retrieved.index(identifier) + 1
        for identifier in relevantIdentifiers
        if identifier in retrieved
    ]
    return min(ranks) if ranks else None


def discountedCumulativeGain(relevantIdentifiers: list[str], retrieved: list[str]) -> float:
    """nDCG a pertinence binaire, normalise par le classement parfait.

    Sur un cas a un seul document pertinent, nDCG vaut 1/log2(rang+1) : il recompense un
    document trouve au premier rang plus qu'au dixieme, la ou un simple taux de presence
    les compte pareil. Sur plusieurs documents pertinents, il mesure aussi combien on en a.
    """
    if not relevantIdentifiers:
        return 0.0
    relevantSet = set(relevantIdentifiers)
    gain = sum(
        1 / math.log2(position + 1)
        for position, identifier in enumerate(retrieved, start=1)
        if identifier in relevantSet
    )
    perfect = sum(
        1 / math.log2(position + 1)
        for position in range(1, min(len(relevantIdentifiers), len(retrieved)) + 1)
    )
    return gain / perfect if perfect else 0.0


def scoreCase(case: Case, answer: Answer, refusalDetector: RefusalDetector) -> CaseOutcome:
    comparableAnswer = normaliseForComparison(answer.text)
    retrieved = answer.finalStage.documentIdentifiers

    return CaseOutcome(
        identifier=case.identifier,
        category=case.category,
        question=case.question,
        relevantIdentifiers=list(case.relevantIdentifiers),
        stageHits={
            stage.name: any(
                identifier in stage.documentIdentifiers
                for identifier in case.relevantIdentifiers
            )
            for stage in answer.stages
        },
        rank=bestRank(case.relevantIdentifiers, retrieved),
        normalisedDiscountedGain=discountedCumulativeGain(case.relevantIdentifiers, retrieved),
        # La citation se cherche dans le texte BRUT : un identifiant est sensible a la casse
        # et aux tirets, que la normalisation ne doit pas avoir le droit d'assouplir.
        citedRelevant=any(identifier in answer.text for identifier in case.relevantIdentifiers),
        mustIncludeSatisfied=all(
            fragmentIsPresent(fragment, case, comparableAnswer) for fragment in case.mustInclude
        ),
        mustNotIncludeRespected=all(
            normaliseForComparison(fragment) not in comparableAnswer
            for fragment in case.mustNotInclude
        ),
        refused=refusalDetector.detects(comparableAnswer),
        answer=answer.text,
        retrievedIdentifiers=list(retrieved),
        inputTokens=answer.inputTokens,
        outputTokens=answer.outputTokens,
        estimatedCostUsd=answer.estimatedCostUsd,
    )


def ratio(matching: int, total: int) -> float:
    return round(matching / total, 3) if total else 0.0


def summarise(outcomes: list[CaseOutcome]) -> dict:
    """Resume chiffre. Les cas de refus sont comptes a part : ils n'ont pas de document
    pertinent, donc les inclure dans un rappel ferait monter le score sans rien mesurer."""
    sourced = [outcome for outcome in outcomes if not outcome.expectsRefusal]
    refusals = [outcome for outcome in outcomes if outcome.expectsRefusal]

    stageNames: list[str] = []
    for outcome in sourced:
        for name in outcome.stageHits:
            if name not in stageNames:
                stageNames.append(name)

    reciprocalRanks = [1 / outcome.rank for outcome in sourced if outcome.rank]
    byCategory: dict[str, dict] = {}
    for outcome in outcomes:
        bucket = byCategory.setdefault(
            outcome.category, {"total": 0, "found": 0, "cited": 0, "mustInclude": 0, "passed": 0}
        )
        bucket["total"] += 1
        bucket["found"] += int(outcome.rank is not None or outcome.expectsRefusal)
        bucket["cited"] += int(outcome.citedRelevant or outcome.expectsRefusal)
        bucket["mustInclude"] += int(outcome.mustIncludeSatisfied)
        bucket["passed"] += int(outcome.succeeded)

    return {
        "casesTotal": len(outcomes),
        "passed": sum(outcome.succeeded for outcome in outcomes),
        "recallByStage": {
            name: ratio(sum(outcome.stageHits.get(name, False) for outcome in sourced), len(sourced))
            for name in stageNames
        },
        "meanReciprocalRank": round(sum(reciprocalRanks) / len(sourced), 3) if sourced else 0.0,
        "normalisedDiscountedGain": round(
            sum(outcome.normalisedDiscountedGain for outcome in sourced) / len(sourced), 3
        )
        if sourced
        else 0.0,
        "citedRelevant": ratio(sum(outcome.citedRelevant for outcome in sourced), len(sourced)),
        "mustIncludeSatisfied": ratio(
            sum(outcome.mustIncludeSatisfied for outcome in sourced), len(sourced)
        ),
        "refusalCorrect": ratio(
            sum(outcome.refused and outcome.mustNotIncludeRespected for outcome in refusals),
            len(refusals),
        ),
        "noForbiddenValue": ratio(
            sum(outcome.mustNotIncludeRespected for outcome in outcomes), len(outcomes)
        ),
        "byCategory": byCategory,
        "usage": {
            "inputTokens": sum(outcome.inputTokens for outcome in outcomes),
            "outputTokens": sum(outcome.outputTokens for outcome in outcomes),
            "estimatedCostUsd": round(
                sum(outcome.estimatedCostUsd for outcome in outcomes), 4
            ),
        },
    }
