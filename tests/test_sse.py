"""Lecture d'un flux SSE, et le piege du dernier bloc."""

from __future__ import annotations

import json

from ragscore.adapters.sse import AnswerDraft, iterateEvents


class FakeResponse:
    """Repond par morceaux arbitraires : une coupure peut tomber au milieu d'un bloc."""

    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks

    def iter_text(self):
        return iter(self.chunks)


def buildStream(events: list[tuple[str, object]]) -> str:
    return "\n\n".join(
        f"event: {name}\ndata: {json.dumps(payload)}" for name, payload in events
    )


def testDernierEvenementDuFluxNEstPasPerdu():
    """Le « done » final porte la consommation : le perdre fait annoncer un cout nul."""
    stream = buildStream([("text", {"delta": "bonjour"}), ("done", {"inputTokens": 1200})])

    events = list(iterateEvents(FakeResponse([stream])))

    assert [name for name, _ in events] == ["text", "done"]
    assert events[-1][1] == {"inputTokens": 1200}


def testBlocCoupeEnDeuxEstRecolle():
    stream = buildStream([("text", {"delta": "bon"}), ("text", {"delta": "jour"})])
    middle = len(stream) // 2

    events = list(iterateEvents(FakeResponse([stream[:middle], stream[middle:]])))

    assert [payload["delta"] for _, payload in events] == ["bon", "jour"]


def testBlocSansEvenementOuSansDonneesEstIgnore():
    stream = "event: ping\n\n" + buildStream([("text", {"delta": "ok"})])

    events = list(iterateEvents(FakeResponse([stream])))

    assert [name for name, _ in events] == ["text"]


def testBrouillonConserveLOrdreDesEtages():
    draft = AnswerDraft()
    draft.setStage("candidats", ["A", "B"])
    draft.setStage("rerank", ["B"])
    draft.addText("texte")

    answer = draft.build()

    assert [stage.name for stage in answer.stages] == ["candidats", "rerank"]
    assert answer.finalStage.documentIdentifiers == ["B"]


def testEtageRedefiniGardeSaPlace():
    """Le produit peut reemettre un etage : il remplace, il ne se dedouble pas."""
    draft = AnswerDraft()
    draft.setStage("candidats", ["A"])
    draft.setStage("rerank", ["A"])
    draft.setStage("candidats", ["A", "B"])

    answer = draft.build()

    assert [stage.name for stage in answer.stages] == ["candidats", "rerank"]
    assert answer.stages[0].documentIdentifiers == ["A", "B"]


def testReponseSansEtageADesEtagesVidesPlutotQuUneErreur():
    assert AnswerDraft().build().finalStage.documentIdentifiers == []
