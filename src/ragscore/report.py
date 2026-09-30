"""Ecriture et relecture du rapport d'execution.

Le rapport separe **ce que le systeme a repondu** (l'observation) de **la note qu'on lui a
mise** (le score). C'est ce qui rend la re-notation possible : quand la correction porte sur
le harnais (detection du refus, normalisation, variante d'orthographe acceptee) et non sur le
systeme, les reponses sont identiques au caractere pres et les re-noter ne coute rien. Sans
ce mode, chaque correction de harnais se paie une execution complete du jeu.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from ragscore.metrics import CaseOutcome
from ragscore.system import Answer, RetrievalStage, RetrievedPassage

REPORT_FORMAT_VERSION = 1


def writeReport(
    path: Path,
    outcomes: list[CaseOutcome],
    summary: dict,
    observations: dict[str, Answer],
    label: str = "",
) -> None:
    payload = {
        "formatVersion": REPORT_FORMAT_VERSION,
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
        "label": label,
        "summary": summary,
        "observations": [
            {
                "identifier": identifier,
                "answer": answer.text,
                "stages": [
                    {"name": stage.name, "documentIdentifiers": stage.documentIdentifiers}
                    for stage in answer.stages
                ],
                "passages": [
                    {"identifier": passage.identifier, "text": passage.text}
                    for passage in answer.passages
                ],
                "inputTokens": answer.inputTokens,
                "outputTokens": answer.outputTokens,
                "estimatedCostUsd": answer.estimatedCostUsd,
            }
            for identifier, answer in observations.items()
        ],
        "scores": [asdict(outcome) for outcome in outcomes],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def readObservations(path: Path) -> dict[str, Answer]:
    """Relit les reponses stockees pour les re-noter, sans toucher au systeme."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "observations" not in payload:
        raise ValueError(
            f"{path.name} ne contient pas d'observations : il vient d'un format anterieur "
            "et ne peut pas etre re-note. Relancez une execution complete."
        )
    return {
        entry["identifier"]: Answer(
            text=entry["answer"],
            stages=[
                RetrievalStage(name=stage["name"], documentIdentifiers=stage["documentIdentifiers"])
                for stage in entry.get("stages", [])
            ],
            passages=[
                RetrievedPassage(identifier=passage["identifier"], text=passage["text"])
                for passage in entry.get("passages", [])
            ],
            inputTokens=entry.get("inputTokens", 0),
            outputTokens=entry.get("outputTokens", 0),
            estimatedCostUsd=entry.get("estimatedCostUsd", 0.0),
        )
        for entry in payload["observations"]
    }
