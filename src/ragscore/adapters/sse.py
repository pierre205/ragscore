"""Adaptateur pour un systeme servi en HTTP avec reponse en flux (Server-Sent Events).

C'est la forme la plus courante d'un RAG en production : l'API diffuse la reponse au fil
de l'eau. Mesurer l'API reellement livree, plutot qu'une copie du chemin de requete ecrite
pour l'occasion, est le seul moyen de mesurer le produit : deux implementations divergent
des que l'on touche a l'une, et l'evaluation se met alors a noter autre chose.

Le decoupage du flux est ici, une fois pour toutes, avec le piege qui va avec : le dernier
bloc d'un flux SSE n'est pas suivi d'une ligne vide, donc une boucle qui met toujours de
cote le bloc final le perd. C'est presque toujours celui qui porte la consommation.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator

import httpx

from ragscore.system import Answer, RetrievalStage

EVENT_NAME = re.compile(r"^event: (.+)$", re.MULTILINE)
EVENT_DATA = re.compile(r"^data: (.+)$", re.MULTILINE)


class AnswerDraft:
    """Reponse en cours de construction, alimentee au fil des evenements du flux."""

    def __init__(self) -> None:
        self.textParts: list[str] = []
        self.stages: dict[str, list[str]] = {}
        self.inputTokens = 0
        self.outputTokens = 0
        self.estimatedCostUsd = 0.0

    def addText(self, fragment: str) -> None:
        self.textParts.append(fragment)

    def setStage(self, name: str, documentIdentifiers: list[str]) -> None:
        """Ordre d'insertion = ordre des etages. Un etage redefini garde sa place."""
        self.stages[name] = list(documentIdentifiers)

    def setUsage(self, inputTokens: int = 0, outputTokens: int = 0, costUsd: float = 0.0) -> None:
        self.inputTokens = inputTokens
        self.outputTokens = outputTokens
        self.estimatedCostUsd = costUsd

    def build(self) -> Answer:
        return Answer(
            text="".join(self.textParts),
            stages=[
                RetrievalStage(name=name, documentIdentifiers=identifiers)
                for name, identifiers in self.stages.items()
            ],
            inputTokens=self.inputTokens,
            outputTokens=self.outputTokens,
            estimatedCostUsd=self.estimatedCostUsd,
        )


def parseEventBlock(block: str) -> tuple[str, object] | None:
    eventName = EVENT_NAME.search(block)
    rawData = EVENT_DATA.search(block)
    if not eventName or not rawData:
        return None
    return eventName.group(1), json.loads(rawData.group(1))


def iterateEvents(response: httpx.Response) -> Iterator[tuple[str, object]]:
    buffer = ""
    for chunk in response.iter_text():
        buffer += chunk
        blocks = buffer.split("\n\n")
        buffer = blocks.pop()
        for block in blocks:
            parsed = parseEventBlock(block)
            if parsed:
                yield parsed
    # Le bloc final n'est pas suivi d'une ligne vide : sans ce traitement il est perdu.
    if buffer.strip():
        parsed = parseEventBlock(buffer)
        if parsed:
            yield parsed


class ServerSentEventsSystem:
    """Interroge une API en flux et reconstitue une `Answer`.

    `handleEvent` traduit un evenement propre au produit en appel sur le brouillon. Tout ce
    qui est specifique a un projet (noms des evenements, forme des charges utiles) vit la,
    et nulle part dans le harnais.
    """

    def __init__(
        self,
        url: str,
        buildRequestBody: Callable[[str], dict],
        handleEvent: Callable[[str, object, AnswerDraft], None],
        client: httpx.Client,
    ) -> None:
        self.url = url
        self.buildRequestBody = buildRequestBody
        self.handleEvent = handleEvent
        self.client = client

    def answer(self, question: str) -> Answer:
        draft = AnswerDraft()
        with self.client.stream("POST", self.url, json=self.buildRequestBody(question)) as response:
            response.raise_for_status()
            for eventName, payload in iterateEvents(response):
                self.handleEvent(eventName, payload, draft)
        return draft.build()
