"""Exporter une mesure vers ragas, pour confronter deux protocoles.

ragas et ragscore ne notent pas la meme chose, et c'est precisement l'interet de les faire
tourner cote a cote.

ragscore note de facon DETERMINISTE contre une verite terrain : la valeur attendue est
presente au caractere pres ou elle ne l'est pas. ragas note surtout par un LLM JUGE, et
plusieurs de ses metriques se passent de verite terrain (« la reponse est-elle fidele aux
extraits ? »). Sur un corpus reglementaire, la premiere approche tranche ce que la seconde
ne peut qu'apprecier ; en revanche ragas voit des choses qu'un fragment attendu ne voit
pas, comme une reponse exacte mais mal etayee.

Ce module ne fait qu'une chose : traduire. Il n'appelle aucun modele et n'installe rien.
"""

from __future__ import annotations

from dataclasses import dataclass

from ragscore.case import Case
from ragscore.system import Answer

# Metriques ragas utilisables SANS reponse de reference, donc immediatement.
METRICS_WITHOUT_REFERENCE = ["Faithfulness", "ResponseRelevancy", "LLMContextPrecisionWithoutReference"]
# Metriques qui exigent une reponse de reference redigee cas par cas.
METRICS_NEEDING_REFERENCE = ["ContextRecall", "AnswerCorrectness", "LLMContextPrecisionWithReference"]


@dataclass
class ExportReadiness:
    """Ce qui manque avant que l'export soit exploitable, dit avant de payer un juge."""

    total: int
    withPassages: int
    withReference: int
    refusalCases: int

    @property
    def usable(self) -> int:
        return self.withPassages

    def summary(self) -> str:
        lines = [
            f"{self.total} cas au total",
            f"  {self.withPassages} portent le texte de leurs passages (indispensable a ragas)",
            f"  {self.withReference} portent une reponse de reference",
            f"  {self.refusalCases} sont des cas de refus",
        ]
        if self.withPassages < self.total:
            lines.append(
                f"  ATTENTION : {self.total - self.withPassages} cas sans texte de passage "
                "seront ignores. Le systeme mesure doit rendre ses passages."
            )
        if self.withReference < self.total - self.refusalCases:
            lines.append(
                "  Sans reponse de reference, seules les metriques sans reference sont "
                f"calculables : {', '.join(METRICS_WITHOUT_REFERENCE)}."
            )
        return "\n".join(lines)


def assessReadiness(cases: list[Case], observations: dict[str, Answer]) -> ExportReadiness:
    present = [case for case in cases if case.identifier in observations]
    return ExportReadiness(
        total=len(present),
        withPassages=sum(1 for case in present if observations[case.identifier].passages),
        withReference=sum(1 for case in present if case.referenceAnswer),
        refusalCases=sum(1 for case in present if case.expectsRefusal),
    )


def toRagasRecords(
    cases: list[Case],
    observations: dict[str, Answer],
    includeRefusals: bool = False,
) -> list[dict]:
    """Traduit en enregistrements au format attendu par `SingleTurnSample`.

    Les cas de refus sont exclus par defaut. ragas juge la fidelite d'une reponse a ses
    extraits ; un refus n'a pas d'extraits pertinents, et le noter ainsi melangerait deux
    comportements qui n'ont rien a voir. ragscore, lui, les note correctement a part.
    """
    records = []
    for case in cases:
        answer = observations.get(case.identifier)
        if answer is None or not answer.passages:
            continue
        if case.expectsRefusal and not includeRefusals:
            continue
        record = {
            "user_input": case.question,
            "retrieved_contexts": [passage.text for passage in answer.passages],
            "response": answer.text,
        }
        if case.referenceAnswer:
            record["reference"] = case.referenceAnswer
        records.append(record)
    return records


def buildEvaluationDataset(cases: list[Case], observations: dict[str, Answer], **options):
    """Construit directement un `EvaluationDataset` ragas, si ragas est installe."""
    try:
        from ragas import EvaluationDataset
        from ragas.dataset_schema import SingleTurnSample
    except ModuleNotFoundError as missing:
        raise RuntimeError(
            "ragas n'est pas installe :\n    uv pip install ragas\n"
            "Vous pouvez aussi utiliser toRagasRecords() et construire le jeu vous-meme."
        ) from missing

    return EvaluationDataset(
        samples=[SingleTurnSample(**record) for record in toRagasRecords(cases, observations, **options)]
    )
