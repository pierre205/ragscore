"""Lecture d'un jeu depose : tolerante sur la forme, stricte sur le fond."""

from __future__ import annotations

import pytest

from ragscore.importers import CaseImportError, readCases

CSV = (
    "id,question,relevant_ids,must_include,category\n"
    "un,Quelle duree de garantie ?,GUIDE-01,24 mois,duree\n"
    "deux,Quel taux de TVA ?,,,refus\n"
)


def testCsvDeTableurEstLu():
    cases = readCases(CSV, "jeu.csv")

    assert [case.identifier for case in cases] == ["un", "deux"]
    assert cases[0].relevantIdentifiers == ["GUIDE-01"]
    assert cases[0].mustInclude == ["24 mois"]


def testColonneVideDonneUnCasDeRefus():
    assert readCases(CSV, "jeu.csv")[1].expectsRefusal is True


def testPlusieursDocumentsAttendusSeparesParUneBarre():
    content = "question,relevant_ids\nMa question ?,GUIDE-01|GUIDE-02\n"

    assert readCases(content, "jeu.csv")[0].relevantIdentifiers == ["GUIDE-01", "GUIDE-02"]


def testNomsDeColonnesEnFrancaisAcceptes():
    content = "identifiant,demande,attendu,valeur_attendue\nun,Ma question ?,GUIDE-01,24 mois\n"

    case = readCases(content, "jeu.csv")[0]

    assert case.identifier == "un"
    assert case.question == "Ma question ?"
    assert case.relevantIdentifiers == ["GUIDE-01"]


def testJsonlNatifEtJsonEnListe():
    jsonl = '{"id": "un", "question": "Ma question ?", "relevant_ids": ["A"]}'
    liste = '[{"id": "un", "question": "Ma question ?", "relevant_ids": ["A"]}]'

    assert readCases(jsonl, "jeu.jsonl")[0].relevantIdentifiers == ["A"]
    assert readCases(liste, "jeu.json")[0].relevantIdentifiers == ["A"]


def testIdentifiantAbsentEstRemplaceParSaPosition():
    assert readCases("question\nMa question ?\n", "jeu.csv")[0].identifier == "cas-1"


def testColonneDeQuestionManquanteEstSignaleeAvecLesNomsAcceptes():
    with pytest.raises(CaseImportError, match="question, prompt"):
        readCases("colonne,autre\nvaleur,valeur2\n", "jeu.csv")


def testIdentifiantsEnDoubleSontRefuses():
    content = "id,question\nmeme,Premiere ?\nmeme,Seconde ?\n"

    with pytest.raises(CaseImportError, match="double"):
        readCases(content, "jeu.csv")


def testFichierVideEstSignale():
    with pytest.raises(CaseImportError, match="vide"):
        readCases("   ", "jeu.csv")
