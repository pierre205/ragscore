"""Notation d'un cas : ce que chaque metrique compte, et ce qu'elle refuse de compter."""

from __future__ import annotations

from ragscore.case import Case
from ragscore.metrics import discountedCumulativeGain, scoreCase, summarise
from ragscore.refusal import RefusalDetector
from ragscore.system import Answer, RetrievalStage

DETECTOR = RefusalDetector()


def buildAnswer(text: str, candidates: list[str], retrieved: list[str]) -> Answer:
    return Answer(
        text=text,
        stages=[
            RetrievalStage("candidats", candidates),
            RetrievalStage("rerank", retrieved),
        ],
    )


def testDocumentPerduEntreLesDeuxEtagesEstImputeAuBonEtage():
    case = Case(identifier="cas", question="?", relevantIdentifiers=["BAR-TH-113"])
    answer = buildAnswer("reponse", ["BAR-TH-113", "BAR-TH-104"], ["BAR-TH-104"])

    outcome = scoreCase(case, answer, DETECTOR)

    assert outcome.stageHits["candidats"] is True
    assert outcome.stageHits["rerank"] is False
    assert outcome.rank is None


def testRangEtRangInverseSuiventLaPositionDansEtageFinal():
    case = Case(identifier="cas", question="?", relevantIdentifiers=["BAR-TH-113"])
    answer = buildAnswer("reponse", ["BAR-TH-113"], ["BAR-EN-101", "BAR-TH-113"])

    outcome = scoreCase(case, answer, DETECTOR)

    assert outcome.rank == 2
    assert summarise([outcome])["meanReciprocalRank"] == 0.5


def testValeurAttendueToleraLeGrasEtLesEspacesInsecables():
    case = Case(
        identifier="cas",
        question="?",
        relevantIdentifiers=["BAR-TH-113"],
        mustInclude=["19 800 kWh cumac"],
    )
    answer = buildAnswer("Le montant est de **19 800 kWh cumac**.", ["BAR-TH-113"], ["BAR-TH-113"])

    assert scoreCase(case, answer, DETECTOR).mustIncludeSatisfied is True


def testValeurAttendueRefuseUnChiffreDifferent():
    case = Case(
        identifier="cas",
        question="?",
        relevantIdentifiers=["BAR-TH-113"],
        mustInclude=["19 800 kWh cumac"],
    )
    answer = buildAnswer("Le montant est de 19 900 kWh cumac.", ["BAR-TH-113"], ["BAR-TH-113"])

    assert scoreCase(case, answer, DETECTOR).mustIncludeSatisfied is False


def testVarianteAccepteeSeulementSiElleEstDeclaree():
    declared = Case(
        identifier="cas",
        question="?",
        relevantIdentifiers=["BAR-TH-113"],
        mustInclude=["3,7 kWh"],
        mustIncludeVariants={"3,7 kWh": ["3.7 kWh"]},
    )
    undeclared = Case(
        identifier="cas",
        question="?",
        relevantIdentifiers=["BAR-TH-113"],
        mustInclude=["3,7 kWh"],
    )
    answer = buildAnswer("valeur : 3.7 kWh", ["BAR-TH-113"], ["BAR-TH-113"])

    assert scoreCase(declared, answer, DETECTOR).mustIncludeSatisfied is True
    assert scoreCase(undeclared, answer, DETECTOR).mustIncludeSatisfied is False


def testCitationEstSensibleALaCasseDeLIdentifiant():
    case = Case(identifier="cas", question="?", relevantIdentifiers=["BAR-TH-113"])
    lowered = buildAnswer("voir la fiche bar-th-113", ["BAR-TH-113"], ["BAR-TH-113"])
    exact = buildAnswer("voir la fiche BAR-TH-113", ["BAR-TH-113"], ["BAR-TH-113"])

    assert scoreCase(case, lowered, DETECTOR).citedRelevant is False
    assert scoreCase(case, exact, DETECTOR).citedRelevant is True


def testCasDeRefusReussiSeulementSansValeurInterdite():
    case = Case(
        identifier="refus",
        question="?",
        relevantIdentifiers=[],
        mustNotInclude=["BAR-TH-113"],
    )
    honest = buildAnswer("Cette information ne figure pas dans les extraits.", [], [])
    invented = buildAnswer("Ce point ne figure pas, mais voyez BAR-TH-113.", [], [])

    assert scoreCase(case, honest, DETECTOR).succeeded is True
    assert scoreCase(case, invented, DETECTOR).succeeded is False


def testRefusToleraUneIncise():
    case = Case(identifier="refus", question="?", relevantIdentifiers=[])
    answer = buildAnswer("Je ne peux donc pas repondre a partir des extraits.", [], [])

    assert scoreCase(case, answer, DETECTOR).refused is True


def testCasDeRefusExclusDuRappelPourNePasGonflerLeScore():
    sourced = scoreCase(
        Case(identifier="cas", question="?", relevantIdentifiers=["BAR-TH-113"]),
        buildAnswer("reponse", ["BAR-TH-113"], ["AUTRE"]),
        DETECTOR,
    )
    refusal = scoreCase(
        Case(identifier="refus", question="?", relevantIdentifiers=[]),
        buildAnswer("Aucune information dans les extraits.", [], []),
        DETECTOR,
    )

    summary = summarise([sourced, refusal])

    # Un seul cas a un document attendu, et il est manque : le rappel vaut 0, pas 50 %.
    assert summary["recallByStage"]["rerank"] == 0.0
    assert summary["refusalCorrect"] == 1.0
    assert summary["passed"] == 1


def testGainCumuleRecompenseLePremierRang():
    parfait = discountedCumulativeGain(["A"], ["A", "B", "C"])
    tardif = discountedCumulativeGain(["A"], ["B", "C", "A"])

    assert parfait == 1.0
    assert 0 < tardif < parfait


def testGainCumuleCompteTousLesDocumentsPertinents():
    complet = discountedCumulativeGain(["A", "B"], ["A", "B", "C"])
    partiel = discountedCumulativeGain(["A", "B"], ["A", "C", "D"])

    assert complet == 1.0
    assert partiel < complet
