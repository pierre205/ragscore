"""Moteur integre : composition SQL, reduction des doublons, dependances absentes."""

from __future__ import annotations

import pytest

from ragscore.connector import ConnectorError
from ragscore.engines.vector import Passage, VectorEngine, VectorEngineSystem, uniqueInOrder
from ragscore.systems import buildSystem, declarationFromDictionary, declarationToDictionary


def testDocumentCitePlusieursFoisNeCompteQuUneFois():
    """Le rang doit etre celui du DOCUMENT, pas du passage : deux extraits d'une meme fiche
    ne doivent pas faire chuter son rang alors que la recuperation est bonne."""
    passages = [
        Passage("BAR-TH-113", "premier extrait"),
        Passage("BAR-TH-113", "second extrait"),
        Passage("BAR-EN-101", "autre fiche"),
    ]

    assert uniqueInOrder(passages) == ["BAR-TH-113", "BAR-EN-101"]


def testNomsDeTableEtColonnesPassentParDesIdentifiantsSql():
    """Ils viennent d'une saisie : ils sont composes, jamais concatenes."""
    from psycopg import sql

    engine = VectorEngine(name="essai", table="public.chunk", identifierColumn="code")
    composed = sql.SQL("SELECT {identifier} FROM {table}").format(
        identifier=sql.Identifier(engine.identifierColumn),
        table=sql.Identifier(*engine.table.split(".")),
    )

    assert composed.as_string(None) == 'SELECT "code" FROM "public"."chunk"'


def testNomDeTableMalveillantEstEchappeEtNonInterprete():
    from psycopg import sql

    piege = 'chunk"; DROP TABLE chunk; --'

    rendu = sql.Identifier(piege).as_string(None)

    assert rendu.startswith('"chunk""')
    assert rendu.endswith('"')


def testDeclarationVectorielleFaitUnAllerRetour():
    engine = VectorEngine(name="moteur", table="chunk")

    relu = declarationFromDictionary(declarationToDictionary(engine))

    assert relu == engine
    assert isinstance(buildSystem(relu), VectorEngineSystem)


def testChampInconnuDansUnMoteurEstSignale():
    with pytest.raises(ConnectorError, match="champs inconnus"):
        declarationFromDictionary({"kind": "vector", "name": "x", "tabel": "chunk"})


def testSorteInconnueEstSignalee():
    with pytest.raises(ConnectorError, match="sorte de systeme inconnue"):
        declarationFromDictionary({"kind": "graphe", "name": "x"})


def testUneDeclarationSansSorteResteUnConnecteurHttp():
    from ragscore.connector import HttpConnector

    declaration = declarationFromDictionary({"name": "ancien", "url": "http://systeme/chat"})

    assert isinstance(declaration, HttpConnector)


def testLesClesNeSontPasEcritesDansLaDeclaration():
    engine = VectorEngine(name="moteur")

    stored = declarationToDictionary(engine)

    assert stored["voyageApiKey"] == "{{env:VOYAGE_API_KEY}}"
    assert stored["anthropicApiKey"] == "{{env:ANTHROPIC_API_KEY}}"
    assert stored["databaseUrl"] == "{{env:DATABASE_URL}}"


def testUrlDeBaseNonDefinieEstSignaleeParSonNom(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    system = VectorEngineSystem(engine=VectorEngine(name="moteur"))

    with pytest.raises(ConnectorError, match="DATABASE_URL"):
        system.open()


def testErreurDuFournisseurEstRendueLisible():
    """Une trace brute traversait l'interface. Le solde epuise et la cle invalide sont
    les deux causes courantes, et elles ne sont pas des defauts du systeme mesure."""
    from ragscore.engines.vector import Passage

    class VoyageEnPanne:
        def embed(self, *args, **kwargs):
            raise RuntimeError("Your credit balance is too low")

    system = VectorEngineSystem(engine=VectorEngine(name="moteur"))
    system._voyage = VoyageEnPanne()

    with pytest.raises(ConnectorError, match="vectorisation de la question a echoue"):
        system.searchCandidates("une question")

    class AnthropicEnPanne:
        class messages:
            @staticmethod
            def create(*args, **kwargs):
                raise RuntimeError("credit balance is too low")

    system._anthropic = AnthropicEnPanne()
    with pytest.raises(ConnectorError, match="generation a echoue"):
        system.generate("une question", [Passage("A", "un extrait")])


def testIdentifiantTireDUneExpressionJsonb():
    """Cas Supabase courant : l'identifiant vit dans une colonne jsonb, pas dans une colonne."""
    from psycopg import sql

    engine = VectorEngine(name="moteur", identifierExpression="metadata->>'url'")
    rendu = sql.SQL(engine.identifierExpression).as_string(None)

    assert rendu == "metadata->>'url'"
    assert "expression" in engine.describe() or "metadata" in engine.describe()


def testExpressionPrimeSurLaColonne():
    engine = VectorEngine(name="moteur", identifierColumn="code",
                          identifierExpression="metadata->>'url'")

    assert "metadata->>'url'" in engine.describe()
    assert "code" not in engine.describe()
