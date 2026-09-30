"""Interface locale : deposer un jeu de questions, declarer un systeme, mesurer.

Servie par ragscore lui-meme, en une page sans etape de construction. L'outil reste donc
lancable d'une seule commande, et n'impose pas un second environnement pour etre utilise.

L'interface n'est qu'une facade : tout ce qu'elle fait est faisable en bibliotheque ou en
ligne de commande, et rien n'est stocke dans un format qu'elle serait seule a lire.
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path

from starlette.applications import Starlette
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.routing import Route

from ragscore.case import Case
from ragscore.connector import ConnectorError
from ragscore.importers import CaseImportError, readCases
from ragscore.metrics import scoreCase, summarise
from ragscore.refusal import RefusalDetector
from ragscore.report import readObservations, writeReport
from ragscore.runner import rescore
from ragscore.systems import buildSystem, declarationFromDictionary, declarationToDictionary
from ragscore.workspace import Workspace

UI_DIRECTORY = Path(__file__).parent / "ui"


def serverSentEvent(name: str, payload: object) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def buildApplication(workspace: Workspace) -> Starlette:
    async def page(request: Request) -> FileResponse:
        return FileResponse(UI_DIRECTORY / "index.html")

    async def script(request: Request) -> FileResponse:
        return FileResponse(UI_DIRECTORY / "ui.js", media_type="text/javascript")

    async def state(request: Request) -> JSONResponse:
        return JSONResponse(
            {
                "root": str(workspace.root),
                "caseSets": workspace.listCaseSets(),
                "connectors": [declarationToDictionary(item) for item in workspace.listConnectors()],
                "reports": workspace.listReports(),
            }
        )

    async def importCases(request: Request) -> JSONResponse:
        payload = await request.json()
        try:
            cases = readCases(payload["content"], payload.get("filename", ""))
        except (CaseImportError, json.JSONDecodeError) as readError:
            return JSONResponse({"error": str(readError)}, status_code=400)
        name = payload.get("name") or Path(payload.get("filename", "jeu")).stem
        path = workspace.saveCaseSet(name, cases)
        return JSONResponse(
            {
                "name": path.stem,
                "total": len(cases),
                "refusals": sum(case.expectsRefusal for case in cases),
                "withoutExpectedValue": sum(
                    1 for case in cases if not case.mustInclude and not case.expectsRefusal
                ),
                "preview": [
                    {
                        "identifier": case.identifier,
                        "question": case.question,
                        "relevantIdentifiers": case.relevantIdentifiers,
                        "mustInclude": case.mustInclude,
                        "category": case.category,
                    }
                    for case in cases[:5]
                ],
            }
        )

    async def saveConnector(request: Request) -> JSONResponse:
        payload = await request.json()
        try:
            connector = declarationFromDictionary(payload)
        except (ConnectorError, TypeError) as configurationError:
            return JSONResponse({"error": str(configurationError)}, status_code=400)
        workspace.saveConnector(connector)
        return JSONResponse({"name": connector.name, "describe": connector.describe()})

    async def deleteConnector(request: Request) -> JSONResponse:
        workspace.deleteConnector(request.path_params["name"])
        return JSONResponse({"deleted": True})

    async def testConnector(request: Request) -> JSONResponse:
        """Une seule question, pour verifier le cablage avant de payer cinquante appels."""
        payload = await request.json()
        try:
            connector = declarationFromDictionary(payload["connector"])
            system = buildSystem(connector)
            try:
                result = await run_in_threadpool(system.answer, payload["question"])
            finally:
                system.close()
        except ConnectorError as connectorFailure:
            return JSONResponse({"error": str(connectorFailure)}, status_code=400)
        except Exception as unexpected:  # noqa: BLE001
            return JSONResponse(
                {"error": f"{type(unexpected).__name__} : {unexpected}"}, status_code=400
            )
        return JSONResponse(
            {
                "text": result.text,
                "stages": [
                    {"name": stage.name, "documentIdentifiers": stage.documentIdentifiers}
                    for stage in result.stages
                ],
                "inputTokens": result.inputTokens,
                "outputTokens": result.outputTokens,
                "estimatedCostUsd": result.estimatedCostUsd,
            }
        )

    async def run(request: Request) -> StreamingResponse:
        connectorName = request.query_params["connector"]
        caseSetName = request.query_params["cases"]

        def execute():
            try:
                connector = workspace.loadConnector(connectorName)
                cases = workspace.loadCaseSet(caseSetName)
            except (FileNotFoundError, ValueError) as loadError:
                yield serverSentEvent("error", {"message": str(loadError)})
                return

            detector = RefusalDetector()
            system = buildSystem(connector)
            outcomes, observations = [], {}
            yield serverSentEvent("start", {"total": len(cases), "connector": connector.describe()})
            try:
                for position, case in enumerate(cases, start=1):
                    try:
                        answer = system.answer(case.question)
                    except ConnectorError as callFailure:
                        yield serverSentEvent(
                            "error", {"message": str(callFailure), "case": case.identifier}
                        )
                        return
                    observations[case.identifier] = answer
                    outcome = scoreCase(case, answer, detector)
                    outcomes.append(outcome)
                    yield serverSentEvent(
                        "case",
                        {
                            "position": position,
                            "total": len(cases),
                            "identifier": case.identifier,
                            "question": case.question,
                            "succeeded": outcome.succeeded,
                            "rank": outcome.rank,
                            "costUsd": outcome.estimatedCostUsd,
                        },
                    )
            finally:
                system.close()

            summary = summarise(outcomes)
            path = workspace.reportPath(connectorName, caseSetName)
            writeReport(path, outcomes, summary, observations, label=connector.name)
            yield serverSentEvent("done", {"summary": summary, "report": path.stem})

        def guarded():
            try:
                yield from execute()
            except Exception:  # noqa: BLE001
                yield serverSentEvent(
                    "error", {"message": traceback.format_exc(limit=3).strip().splitlines()[-1]}
                )

        return StreamingResponse(
            iterate_in_threadpool(guarded()),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def rescoreReport(request: Request) -> JSONResponse:
        payload = await request.json()
        reportPath = Path(payload["report"])
        if not reportPath.is_absolute():
            reportPath = workspace.reportsDirectory / f"{payload['report']}.json"
        try:
            cases: list[Case] = workspace.loadCaseSet(payload["cases"])
            observations = readObservations(reportPath)
        except (FileNotFoundError, ValueError) as loadError:
            return JSONResponse({"error": str(loadError)}, status_code=400)

        outcomes, summary = rescore(cases, observations)
        writeReport(reportPath, outcomes, summary, observations, label=payload.get("label", ""))
        return JSONResponse({"summary": summary, "report": reportPath.stem})

    async def readReport(request: Request) -> JSONResponse:
        path = workspace.reportsDirectory / f"{request.path_params['name']}.json"
        if not path.exists():
            return JSONResponse({"error": "rapport introuvable"}, status_code=404)
        return JSONResponse(json.loads(path.read_text(encoding="utf-8")))

    return Starlette(
        routes=[
            Route("/", page),
            Route("/ui.js", script),
            Route("/api/state", state),
            Route("/api/cases", importCases, methods=["POST"]),
            Route("/api/connectors", saveConnector, methods=["POST"]),
            Route("/api/connectors/test", testConnector, methods=["POST"]),
            Route("/api/connectors/{name}", deleteConnector, methods=["DELETE"]),
            Route("/api/run", run),
            Route("/api/rescore", rescoreReport, methods=["POST"]),
            Route("/api/reports/{name}", readReport),
        ]
    )
