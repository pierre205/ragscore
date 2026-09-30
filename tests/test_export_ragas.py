"""Export vers ragas : ce qui est traduit, ce qui est ecarte, et ce qu'on annonce avant."""

from __future__ import annotations

from ragscore.case import Case
from ragscore.exports.ragas import assessReadiness, toRagasRecords
from ragscore.system import Answer, RetrievedPassage


def answerWithPassages(text: str = "une reponse") -> Answer:
    return Answer(
        text=text,
        passages=[
            RetrievedPassage("BAR-TH-113", "La chaudiere biomasse ouvre droit a 41 300 kWh cumac."),
            RetrievedPassage("BAR-TH-171", "La pompe a chaleur air-eau est traitee ailleurs."),
        ],
    )


def testEnregistrementPorteLesTroisChampsAttendus():
    case = Case(identifier="cas", question="Combien de kWh ?", relevantIdentifiers=["BAR-TH-113"])

    record = toRagasRecords([case], {"cas": answerWithPassages()})[0]

    assert record["user_input"] == "Combien de kWh ?"
    assert record["response"] == "une reponse"
    assert len(record["retrieved_contexts"]) == 2
    assert "41 300" in record["retrieved_contexts"][0]


def testLaReferenceN_estPresenteQueSiElleExiste():
    sans = Case(identifier="a", question="?", relevantIdentifiers=["X"])
    avec = Case(identifier="b", question="?", relevantIdentifiers=["X"],
                referenceAnswer="41 300 kWh cumac")
    observations = {"a": answerWithPassages(), "b": answerWithPassages()}

    records = toRagasRecords([sans, avec], observations)

    assert "reference" not in records[0]
    assert records[1]["reference"] == "41 300 kWh cumac"


def testCasSansTexteDePassageEstIgnore():
    """Un systeme qui ne rend que des identifiants ne peut pas etre juge sur le contenu."""
    case = Case(identifier="cas", question="?", relevantIdentifiers=["X"])

    assert toRagasRecords([case], {"cas": Answer(text="une reponse")}) == []


def testCasDeRefusEcarteParDefaut():
    """Un refus n'a pas d'extrait pertinent : le noter en fidelite melangerait deux choses."""
    refus = Case(identifier="refus", question="?", relevantIdentifiers=[])
    observations = {"refus": answerWithPassages("Cette information ne figure pas.")}

    assert toRagasRecords([refus], observations) == []
    assert len(toRagasRecords([refus], observations, includeRefusals=True)) == 1


def testEtatDePreparationCompteCeQuiManque():
    cases = [
        Case(identifier="a", question="?", relevantIdentifiers=["X"], referenceAnswer="oui"),
        Case(identifier="b", question="?", relevantIdentifiers=["X"]),
        Case(identifier="refus", question="?", relevantIdentifiers=[]),
    ]
    observations = {
        "a": answerWithPassages(),
        "b": Answer(text="sans passage"),
        "refus": answerWithPassages(),
    }

    etat = assessReadiness(cases, observations)

    assert (etat.total, etat.withPassages, etat.withReference, etat.refusalCases) == (3, 2, 1, 1)
    assert "seront ignores" in etat.summary()
    assert "sans reference" in etat.summary()


def testRienN_estAnnonceQuandToutEstComplet():
    cases = [Case(identifier="a", question="?", relevantIdentifiers=["X"], referenceAnswer="oui")]

    etat = assessReadiness(cases, {"a": answerWithPassages()})

    assert "ATTENTION" not in etat.summary()
