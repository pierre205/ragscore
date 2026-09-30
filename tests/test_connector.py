"""Brancher un systeme sans ecrire de Python : lecture des reponses et messages d'erreur."""

from __future__ import annotations

import json

import httpx
import pytest

from ragscore.connector import (
    ConnectorError,
    HttpConnector,
    HttpConnectorSystem,
    StageMapping,
    UsageMapping,
    connectorFromDictionary,
    connectorToDictionary,
    extractIdentifiers,
    extractPath,
    fillTemplate,
)

SSE_RESPONSE = (
    'event: candidates\ndata: ["A", "B"]\n\n'
    'event: sources\ndata: [{"code": "A"}]\n\n'
    'event: text\ndata: {"delta": "la reponse"}\n\n'
    'event: done\ndata: {"usage": {"inputTokens": 800, "estimatedCostUsd": 0.004}}\n\n'
)


def clientReturning(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def sseConnector(**overrides) -> HttpConnector:
    defaults = {
        "name": "essai",
        "url": "http://systeme/chat",
        "mode": "sse",
        "textSource": "text",
        "textField": "delta",
        "stages": [
            StageMapping("candidats", "candidates"),
            StageMapping("rerank", "sources", itemField="code"),
        ],
        "usage": UsageMapping(source="done"),
    }
    defaults.update(overrides)
    return HttpConnector(**defaults)


def testFluxLuEtEtagesAssociesAuxEvenements():
    system = HttpConnectorSystem(
        sseConnector(),
        clientReturning(lambda request: httpx.Response(200, text=SSE_RESPONSE)),
    )

    answer = system.answer("ma question")

    assert answer.text == "la reponse"
    assert [stage.name for stage in answer.stages] == ["candidats", "rerank"]
    assert answer.stages[0].documentIdentifiers == ["A", "B"]
    assert answer.finalStage.documentIdentifiers == ["A"]
    assert answer.inputTokens == 800
    assert answer.estimatedCostUsd == 0.004


def testQuestionInsereeDansLeCorpsDeLaRequete():
    envoye = {}

    def handler(request: httpx.Request) -> httpx.Response:
        envoye.update(json.loads(request.content))
        return httpx.Response(200, text=SSE_RESPONSE)

    HttpConnectorSystem(
        sseConnector(body={"question": "{{question}}", "debug": True}),
        clientReturning(handler),
    ).answer("combien de kWh ?")

    assert envoye == {"question": "combien de kWh ?", "debug": True}


def testReponseJsonLueParChemin():
    payload = {"data": {"answer": "42 kWh"}, "sources": [{"id": "A"}, {"id": "B"}]}
    connector = HttpConnector(
        name="essai",
        url="http://systeme/chat",
        mode="json",
        textSource="data.answer",
        stages=[StageMapping("retrieve", "sources", itemField="id")],
    )

    answer = HttpConnectorSystem(
        connector, clientReturning(lambda request: httpx.Response(200, json=payload))
    ).answer("?")

    assert answer.text == "42 kWh"
    assert answer.finalStage.documentIdentifiers == ["A", "B"]


def testEvenementDErreurInterrompLAppelAvecSonMessage():
    stream = 'event: error\ndata: {"message": "quota depasse"}\n\n'
    system = HttpConnectorSystem(
        sseConnector(), clientReturning(lambda request: httpx.Response(200, text=stream))
    )

    with pytest.raises(ConnectorError, match="quota depasse"):
        system.answer("?")


def testCodeHttpEnErreurEstRapporteLisiblement():
    system = HttpConnectorSystem(
        sseConnector(), clientReturning(lambda request: httpx.Response(500, text="boom"))
    )

    with pytest.raises(ConnectorError, match="500"):
        system.answer("?")


def testConnexionPrealableEchoueAvecUnMessageExploitable():
    from ragscore.connector import AuthenticationStep

    system = HttpConnectorSystem(
        sseConnector(authentication=AuthenticationStep(url="http://systeme/login")),
        clientReturning(lambda request: httpx.Response(401)),
    )

    with pytest.raises(ConnectorError, match="identifiants"):
        system.answer("?")


def testVariableDEnvironnementResoluePuisSignaleeSiAbsente(monkeypatch):
    monkeypatch.setenv("JETON_ESSAI", "secret-123")
    assert fillTemplate({"cle": "{{env:JETON_ESSAI}}"}, "") == {"cle": "secret-123"}

    monkeypatch.delenv("JETON_ESSAI")
    with pytest.raises(ConnectorError, match="JETON_ESSAI"):
        fillTemplate({"cle": "{{env:JETON_ESSAI}}"}, "")


def testLeSecretNEstPasEcritDansLeConnecteur():
    """Le connecteur stocke le nom de la variable, jamais sa valeur."""
    connector = sseConnector(body={"question": "{{question}}", "cle": "{{env:JETON}}"})

    stored = json.dumps(connectorToDictionary(connector))

    assert "{{env:JETON}}" in stored
    assert "secret" not in stored


def testAllerRetourDuConnecteurConserveTout():
    connector = sseConnector()

    assert connectorToDictionary(connectorFromDictionary(connectorToDictionary(connector))) == (
        connectorToDictionary(connector)
    )


def testChampInconnuDansUnConnecteurEstSignale():
    with pytest.raises(ConnectorError, match="champs inconnus"):
        connectorFromDictionary({"name": "x", "url": "http://x", "typo": 1})


def testCheminPointeLitListesEtObjets():
    payload = {"a": {"b": [{"c": "trouve"}]}}

    assert extractPath(payload, "a.b.0.c") == "trouve"
    assert extractPath(payload, "a.absent") is None
    assert extractPath(payload, "") == payload


def testIdentifiantsLusQueLApiRendeDesChainesOuDesObjets():
    assert extractIdentifiers({"s": ["A", "B"]}, "s", None) == ["A", "B"]
    assert extractIdentifiers({"s": [{"code": "A"}]}, "s", "code") == ["A"]
    assert extractIdentifiers({}, "absent", None) == []


def testListeAttendueMaisAbsenteEstSignalee():
    with pytest.raises(ConnectorError, match="liste"):
        extractIdentifiers({"s": "pas une liste"}, "s", None)
