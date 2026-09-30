"""Le rapport doit permettre de re-noter sans rappeler le systeme."""

from __future__ import annotations

import json

import pytest

from ragscore.case import Case
from ragscore.metrics import scoreCase, summarise
from ragscore.refusal import RefusalDetector
from ragscore.report import readObservations, writeReport
from ragscore.runner import rescore
from ragscore.system import Answer, RetrievalStage

DETECTOR = RefusalDetector()


def buildObservation() -> Answer:
    return Answer(
        text="La fiche BAR-TH-113 donne 19 800 kWh cumac.",
        stages=[
            RetrievalStage("candidats", ["BAR-TH-113", "BAR-TH-104"]),
            RetrievalStage("rerank", ["BAR-TH-113"]),
        ],
        inputTokens=1200,
        outputTokens=300,
        estimatedCostUsd=0.016,
    )


def testRenotationRedonneExactementLesMemesNotes(tmp_path):
    case = Case(
        identifier="cas",
        question="?",
        relevantIdentifiers=["BAR-TH-113"],
        mustInclude=["19 800 kWh cumac"],
    )
    observations = {"cas": buildObservation()}
    outcomes = [scoreCase(case, observations["cas"], DETECTOR)]
    path = tmp_path / "rapport.json"
    writeReport(path, outcomes, summarise(outcomes), observations)

    relu, resume = rescore([case], readObservations(path), DETECTOR)

    assert relu == outcomes
    assert resume == summarise(outcomes)


def testRenotationPrendEnCompteUneVarianteAjouteeApresCoup(tmp_path):
    """Le cas d'usage du mode : la reponse etait bonne, c'est le harnais qui etait trop strict."""
    strict = Case(
        identifier="cas", question="?", relevantIdentifiers=["BAR-TH-113"], mustInclude=["19800"]
    )
    tolerant = Case(
        identifier="cas",
        question="?",
        relevantIdentifiers=["BAR-TH-113"],
        mustInclude=["19800"],
        mustIncludeVariants={"19800": ["19 800"]},
    )
    observations = {"cas": buildObservation()}
    path = tmp_path / "rapport.json"
    outcomes = [scoreCase(strict, observations["cas"], DETECTOR)]
    writeReport(path, outcomes, summarise(outcomes), observations)

    assert outcomes[0].mustIncludeSatisfied is False

    relu, _ = rescore([tolerant], readObservations(path), DETECTOR)

    assert relu[0].mustIncludeSatisfied is True


def testCasAbsentDesObservationsEstIgnoreEtNonInvente(tmp_path):
    ancien = Case(identifier="ancien", question="?", relevantIdentifiers=["BAR-TH-113"])
    nouveau = Case(identifier="nouveau", question="?", relevantIdentifiers=["BAR-EN-101"])
    observations = {"ancien": buildObservation()}

    outcomes, resume = rescore([ancien, nouveau], observations, DETECTOR)

    assert [outcome.identifier for outcome in outcomes] == ["ancien"]
    assert resume["casesTotal"] == 1


def testRapportSansObservationsEstRefuseAvecUnMessageClair(tmp_path):
    path = tmp_path / "ancien-rapport.json"
    path.write_text(json.dumps({"summary": {}, "cases": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="format anterieur"):
        readObservations(path)


def testConsommationEstAgregeeDansLeResume():
    case = Case(identifier="cas", question="?", relevantIdentifiers=["BAR-TH-113"])
    outcome = scoreCase(case, buildObservation(), DETECTOR)

    usage = summarise([outcome, outcome])["usage"]

    assert usage["inputTokens"] == 2400
    assert usage["estimatedCostUsd"] == 0.032
