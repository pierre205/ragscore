"""Brancher un systeme HTTP en le DECLARANT, sans ecrire de Python.

Tant qu'il faut coder une classe pour mesurer un systeme, l'outil n'est pas autonome : il
est seulement decouple. Un connecteur decrit en JSON ou JSONL ce qu'il faut envoyer et ou
lire la reponse, ce qui suffit a la quasi-totalite des RAG servis derriere une API.

Deux formes de reponse sont couvertes :

- `json` : une seule reponse, on y lit le texte et les documents par chemin.
- `sse` : une reponse diffusee au fil de l'eau, on associe chaque evenement a son role.

Les secrets ne se stockent pas : ecrivez `{{env:NOM}}` et la valeur est lue dans
l'environnement au moment de l'appel. Un mot de passe ecrit en clair dans un connecteur
finirait dans un fichier, puis dans une sauvegarde, puis dans un depot.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from ragscore.adapters.sse import AnswerDraft, iterateEvents
from ragscore.system import Answer, RetrievalStage

QUESTION_PLACEHOLDER = "{{question}}"
ENVIRONMENT_PLACEHOLDER = re.compile(r"\{\{env:([A-Za-z_][A-Za-z0-9_]*)\}\}")


class ConnectorError(RuntimeError):
    """Probleme de configuration ou de reponse, formule pour etre lisible dans l'interface."""


def resolveEnvironment(value: str) -> str:
    def replace(match: re.Match) -> str:
        name = match.group(1)
        resolved = os.environ.get(name)
        if resolved is None:
            raise ConnectorError(
                f"la variable d'environnement {name} n'est pas definie, et le connecteur "
                f"l'attend"
            )
        return resolved

    return ENVIRONMENT_PLACEHOLDER.sub(replace, value)


def fillTemplate(template: Any, question: str) -> Any:
    """Remplace « {{question}} » et « {{env:NOM}} » partout dans une structure."""
    if isinstance(template, str):
        return resolveEnvironment(template.replace(QUESTION_PLACEHOLDER, question))
    if isinstance(template, dict):
        return {key: fillTemplate(value, question) for key, value in template.items()}
    if isinstance(template, list):
        return [fillTemplate(item, question) for item in template]
    return template


def extractPath(payload: Any, path: str) -> Any:
    """Lit une valeur par chemin pointe : « data.answer », « sources.0.code ».

    Un chemin vide rend la charge utile entiere, ce qui sert quand l'API repond deja la
    liste attendue sans l'envelopper.
    """
    if not path:
        return payload
    current = payload
    for segment in path.split("."):
        if current is None:
            return None
        if isinstance(current, list):
            if not segment.isdigit():
                raise ConnectorError(f"« {segment} » n'est pas un indice valide dans « {path} »")
            index = int(segment)
            current = current[index] if index < len(current) else None
        elif isinstance(current, dict):
            current = current.get(segment)
        else:
            return None
    return current


def extractIdentifiers(payload: Any, path: str, itemField: str | None) -> list[str]:
    """Liste d'identifiants de documents, que l'API renvoie des chaines ou des objets."""
    value = extractPath(payload, path)
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConnectorError(f"« {path or 'la reponse'} » ne contient pas une liste")
    if itemField:
        return [str(item.get(itemField)) for item in value if isinstance(item, dict)]
    return [item if isinstance(item, str) else str(item) for item in value]


@dataclass
class StageMapping:
    name: str
    # Mode json : chemin dans la reponse. Mode sse : nom de l'evenement.
    source: str
    # Champ a lire dans chaque element, si l'API renvoie des objets plutot que des chaines.
    itemField: str | None = None
    # Mode sse uniquement : chemin a l'interieur de la charge utile de l'evenement.
    payloadPath: str = ""


@dataclass
class UsageMapping:
    source: str = ""
    inputTokensPath: str = "inputTokens"
    outputTokensPath: str = "outputTokens"
    costPath: str = "estimatedCostUsd"


@dataclass
class AuthenticationStep:
    """Un appel prealable dont on garde les cookies. Couvre la connexion par formulaire."""

    url: str
    method: str = "POST"
    body: dict = field(default_factory=dict)
    headers: dict = field(default_factory=dict)


@dataclass
class HttpConnector:
    name: str
    url: str
    mode: str = "sse"  # « sse » ou « json »
    method: str = "POST"
    headers: dict = field(default_factory=dict)
    body: dict = field(default_factory=lambda: {"question": QUESTION_PLACEHOLDER})
    # Mode json : chemin du texte. Mode sse : nom de l'evenement qui porte le texte.
    textSource: str = "text"
    # Mode sse uniquement : champ de l'evenement de texte contenant le fragment.
    textField: str = "delta"
    stages: list[StageMapping] = field(default_factory=list)
    usage: UsageMapping = field(default_factory=UsageMapping)
    authentication: AuthenticationStep | None = None
    timeoutSeconds: int = 180
    # Nom de l'evenement (mode sse) qui signale une erreur cote serveur.
    errorSource: str = "error"
    errorMessagePath: str = "message"

    def describe(self) -> str:
        stages = ", ".join(stage.name for stage in self.stages) or "aucun etage declare"
        return f"{self.method} {self.url} [{self.mode}] | etages : {stages}"


def connectorFromDictionary(raw: dict) -> HttpConnector:
    known = dict(raw)
    known.pop("createdAt", None)
    stages = [StageMapping(**stage) for stage in known.pop("stages", [])]
    usage = UsageMapping(**known.pop("usage", {}) or {})
    authenticationRaw = known.pop("authentication", None)
    authentication = AuthenticationStep(**authenticationRaw) if authenticationRaw else None
    unexpected = set(known) - {
        "name", "url", "mode", "method", "headers", "body", "textSource", "textField",
        "timeoutSeconds", "errorSource", "errorMessagePath",
    }
    if unexpected:
        raise ConnectorError(f"champs inconnus dans le connecteur : {', '.join(sorted(unexpected))}")
    return HttpConnector(
        stages=stages, usage=usage, authentication=authentication, **known
    )


def connectorToDictionary(connector: HttpConnector) -> dict:
    return {
        "name": connector.name,
        "url": connector.url,
        "mode": connector.mode,
        "method": connector.method,
        "headers": connector.headers,
        "body": connector.body,
        "textSource": connector.textSource,
        "textField": connector.textField,
        "stages": [
            {
                "name": stage.name,
                "source": stage.source,
                "itemField": stage.itemField,
                "payloadPath": stage.payloadPath,
            }
            for stage in connector.stages
        ],
        "usage": {
            "source": connector.usage.source,
            "inputTokensPath": connector.usage.inputTokensPath,
            "outputTokensPath": connector.usage.outputTokensPath,
            "costPath": connector.usage.costPath,
        },
        "authentication": (
            {
                "url": connector.authentication.url,
                "method": connector.authentication.method,
                "body": connector.authentication.body,
                "headers": connector.authentication.headers,
            }
            if connector.authentication
            else None
        ),
        "timeoutSeconds": connector.timeoutSeconds,
        "errorSource": connector.errorSource,
        "errorMessagePath": connector.errorMessagePath,
    }


class HttpConnectorSystem:
    """Le systeme mesurable obtenu a partir d'un connecteur declare."""

    def __init__(self, connector: HttpConnector, client: httpx.Client | None = None) -> None:
        self.connector = connector
        self.client = client or httpx.Client(timeout=connector.timeoutSeconds)
        self.authenticated = False

    def close(self) -> None:
        self.client.close()

    def authenticate(self) -> None:
        """Rejoue l'etape de connexion et conserve les cookies pour les appels suivants."""
        step = self.connector.authentication
        if step is None or self.authenticated:
            return
        response = self.client.request(
            step.method,
            resolveEnvironment(step.url),
            json=fillTemplate(step.body, ""),
            headers=fillTemplate(step.headers, ""),
        )
        if response.status_code >= 400:
            raise ConnectorError(
                f"la connexion a echoue ({response.status_code}) sur {step.url}. "
                "Verifiez les identifiants du connecteur."
            )
        self.authenticated = True

    def answer(self, question: str) -> Answer:
        self.authenticate()
        connector = self.connector
        body = fillTemplate(connector.body, question)
        headers = fillTemplate(connector.headers, question)
        url = resolveEnvironment(connector.url)

        if connector.mode == "json":
            return self._answerFromJson(url, body, headers)
        return self._answerFromEventStream(url, body, headers)

    def _answerFromJson(self, url: str, body: dict, headers: dict) -> Answer:
        response = self.client.request(self.connector.method, url, json=body, headers=headers)
        if response.status_code >= 400:
            raise ConnectorError(f"le systeme a repondu {response.status_code} : {response.text[:200]}")
        payload = response.json()
        text = extractPath(payload, self.connector.textSource)
        if text is None:
            raise ConnectorError(
                f"aucun texte trouve au chemin « {self.connector.textSource} ». "
                f"Cles disponibles : {', '.join(map(str, payload))[:200]}"
                if isinstance(payload, dict)
                else f"aucun texte trouve au chemin « {self.connector.textSource} »"
            )
        usage = extractPath(payload, self.connector.usage.source) or {}
        return Answer(
            text=str(text),
            stages=[
                RetrievalStage(
                    stage.name, extractIdentifiers(payload, stage.source, stage.itemField)
                )
                for stage in self.connector.stages
            ],
            inputTokens=int(extractPath(usage, self.connector.usage.inputTokensPath) or 0),
            outputTokens=int(extractPath(usage, self.connector.usage.outputTokensPath) or 0),
            estimatedCostUsd=float(extractPath(usage, self.connector.usage.costPath) or 0.0),
        )

    def _answerFromEventStream(self, url: str, body: dict, headers: dict) -> Answer:
        connector = self.connector
        stagesBySource = {stage.source: stage for stage in connector.stages}
        draft = AnswerDraft()

        with self.client.stream(
            connector.method, url, json=body, headers=headers
        ) as response:
            if response.status_code >= 400:
                response.read()
                raise ConnectorError(
                    f"le systeme a repondu {response.status_code} : {response.text[:200]}"
                )
            for eventName, payload in iterateEvents(response):
                if eventName == connector.errorSource:
                    message = extractPath(payload, connector.errorMessagePath) or payload
                    raise ConnectorError(f"le systeme a signale une erreur : {message}")
                if eventName == connector.textSource:
                    fragment = (
                        extractPath(payload, connector.textField)
                        if connector.textField
                        else payload
                    )
                    draft.addText(str(fragment or ""))
                elif eventName in stagesBySource:
                    stage = stagesBySource[eventName]
                    draft.setStage(
                        stage.name,
                        extractIdentifiers(payload, stage.payloadPath, stage.itemField),
                    )
                elif connector.usage.source and eventName == connector.usage.source:
                    usage = extractPath(payload, "usage")
                    usage = usage if isinstance(usage, dict) else payload
                    draft.setUsage(
                        inputTokens=int(extractPath(usage, connector.usage.inputTokensPath) or 0),
                        outputTokens=int(extractPath(usage, connector.usage.outputTokensPath) or 0),
                        costUsd=float(extractPath(usage, connector.usage.costPath) or 0.0),
                    )

        return draft.build()
