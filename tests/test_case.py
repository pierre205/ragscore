"""Chargement d'un jeu de cas : format de fichier stable, garde-fous a la lecture."""

from __future__ import annotations

import json

import pytest

from ragscore.case import Case, caseToDictionary, loadCases, writeCases


def testIdentifiantsEnDoubleFontEchouerLeChargement(tmp_path):
    path = tmp_path / "jeu.jsonl"
    path.write_text(
        "\n".join(
            json.dumps({"id": "meme", "question": question})
            for question in ["premiere", "seconde"]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="double"):
        loadCases(path)


def testAllerRetourFichierConserveLeCas(tmp_path):
    case = Case(
        identifier="cas",
        question="quelle fiche ?",
        relevantIdentifiers=["BAR-TH-113"],
        mustInclude=["19 800"],
        mustIncludeVariants={"19 800": ["19800"]},
        category="routage",
    )
    path = tmp_path / "jeu.jsonl"

    writeCases([case], path)

    assert loadCases(path) == [case]


def testCasSansDocumentPertinentEstUnCasDeRefus():
    assert Case(identifier="cas", question="?").expectsRefusal is True
    assert Case(identifier="cas", question="?", relevantIdentifiers=["A"]).expectsRefusal is False


def testChampsInconnusDuFichierSontIgnores(tmp_path):
    """Un jeu produit par une version plus recente doit rester lisible."""
    path = tmp_path / "jeu.jsonl"
    path.write_text(json.dumps({"id": "cas", "question": "?", "difficulty": "haute"}), encoding="utf-8")

    assert loadCases(path)[0].identifier == "cas"


def testFormatDeFichierResteEnSerpent():
    keys = set(caseToDictionary(Case(identifier="cas", question="?")))

    assert keys == {
        "id",
        "question",
        "relevant_ids",
        "must_include",
        "must_not_include",
        "must_include_variants",
        "category",
        "reference_answer",
    }
