"""Execution du jeu : interroge le systeme, note chaque cas, agrege."""

from __future__ import annotations

from collections.abc import Callable

from ragscore.case import Case
from ragscore.metrics import CaseOutcome, scoreCase, summarise
from ragscore.refusal import RefusalDetector
from ragscore.system import Answer, MeasurableSystem


def runEvaluation(
    system: MeasurableSystem,
    cases: list[Case],
    refusalDetector: RefusalDetector | None = None,
    onCaseScored: Callable[[int, int, CaseOutcome], None] | None = None,
) -> tuple[list[CaseOutcome], dict, dict[str, Answer]]:
    """Retourne (notes, resume, observations). Les observations permettent la re-notation."""
    detector = refusalDetector or RefusalDetector()
    outcomes: list[CaseOutcome] = []
    observations: dict[str, Answer] = {}

    for position, case in enumerate(cases, start=1):
        answer = system.answer(case.question)
        observations[case.identifier] = answer
        outcome = scoreCase(case, answer, detector)
        outcomes.append(outcome)
        if onCaseScored:
            onCaseScored(position, len(cases), outcome)

    return outcomes, summarise(outcomes), observations


def rescore(
    cases: list[Case],
    observations: dict[str, Answer],
    refusalDetector: RefusalDetector | None = None,
) -> tuple[list[CaseOutcome], dict]:
    """Re-note des reponses deja obtenues. Aucun appel au systeme, donc aucun cout.

    Un cas present dans le jeu mais absent des observations est ignore, pas invente : un
    jeu qui grandit se re-note sur ce qui existe, et la prochaine execution complete
    ramassera les nouveaux cas.
    """
    detector = refusalDetector or RefusalDetector()
    outcomes = [
        scoreCase(case, observations[case.identifier], detector)
        for case in cases
        if case.identifier in observations
    ]
    return outcomes, summarise(outcomes)
