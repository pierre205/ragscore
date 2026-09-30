"""Ligne de commande : re-noter et afficher un rapport, sans toucher au systeme.

Executer le jeu demande un systeme, donc du code propre au projet mesure ; c'est au projet
de fournir son script. Re-noter, non : le rapport contient deja les reponses. Ces deux
operations la n'ont besoin de rien d'autre et meritent une commande.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ragscore.case import loadCases
from ragscore.display import formatSummary
from ragscore.report import readObservations, writeReport
from ragscore.runner import rescore


def serveUserInterface(port: int, workspaceRoot: Path | None) -> int:
    """L'interface n'est installee que si on l'a demandee : le harnais s'utilise sans elle."""
    try:
        import uvicorn

        from ragscore.server import buildApplication
    except ModuleNotFoundError:
        print(
            "l'interface a besoin de dependances supplementaires :\n"
            "    uv pip install 'ragscore[ui]'",
            file=sys.stderr,
        )
        return 1

    from ragscore.workspace import Workspace

    workspace = Workspace.open(workspaceRoot)
    print(f"espace de travail : {workspace.root}", flush=True)
    print(f"interface : http://127.0.0.1:{port}", flush=True)
    # Ecoute sur la boucle locale seulement : l'outil manipule des connecteurs qui peuvent
    # porter des identifiants, il n'a rien a faire sur le reseau.
    uvicorn.run(buildApplication(workspace), host="127.0.0.1", port=port, log_level="warning")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ragscore", description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    rescoreCommand = subcommands.add_parser(
        "rescore", help="re-noter les reponses d'un rapport, sans un seul appel facture"
    )
    rescoreCommand.add_argument("--cases", type=Path, required=True)
    rescoreCommand.add_argument("--report", type=Path, required=True)
    rescoreCommand.add_argument("--out", type=Path, help="par defaut : ecrase le rapport lu")

    showCommand = subcommands.add_parser("show", help="afficher le resume d'un rapport")
    showCommand.add_argument("--report", type=Path, required=True)

    uiCommand = subcommands.add_parser(
        "ui", help="ouvrir l'interface locale : deposer un jeu, declarer un systeme, mesurer"
    )
    uiCommand.add_argument("--port", type=int, default=7654)
    uiCommand.add_argument(
        "--workspace", type=Path, help="dossier de travail (defaut : .ragscore ici)"
    )

    arguments = parser.parse_args(argv)

    if arguments.command == "ui":
        return serveUserInterface(arguments.port, arguments.workspace)

    if arguments.command == "show":
        import json

        payload = json.loads(arguments.report.read_text(encoding="utf-8"))
        print(formatSummary(payload["summary"]))
        return 0

    cases = loadCases(arguments.cases)
    observations = readObservations(arguments.report)
    outcomes, summary = rescore(cases, observations)
    writeReport(arguments.out or arguments.report, outcomes, summary, observations)
    print(formatSummary(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
