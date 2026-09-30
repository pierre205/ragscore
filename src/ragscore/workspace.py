"""Ou vivent les connecteurs, les jeux de questions et les rapports.

Un espace de travail est un simple dossier, par defaut `.ragscore` dans le repertoire
courant. Tout y est en clair et relisible a la main : aucun format proprietaire, aucun
index a reconstruire. On peut le versionner, sauf les connecteurs, qui peuvent porter des
identifiants et sont donc ecrits en acces restreint.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ragscore.case import Case, loadCases, writeCases
from ragscore.connector import HttpConnector
from ragscore.engines.vector import VectorEngine
from ragscore.systems import declarationFromDictionary, declarationToDictionary

WORKSPACE_DIRECTORY_NAME = ".ragscore"
OWNER_ONLY = 0o600


def slugify(name: str) -> str:
    kept = [character if character.isalnum() else "-" for character in name.lower()]
    slug = "".join(kept).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "sans-nom"


@dataclass
class Workspace:
    root: Path

    @classmethod
    def open(cls, root: Path | None = None) -> Workspace:
        base = Path(root) if root else Path.cwd() / WORKSPACE_DIRECTORY_NAME
        workspace = cls(root=base)
        for directory in [base, workspace.connectorsDirectory, workspace.casesDirectory,
                          workspace.reportsDirectory]:
            directory.mkdir(parents=True, exist_ok=True)
        gitignore = base / ".gitignore"
        if not gitignore.exists():
            # Les connecteurs peuvent contenir une URL interne ou un identifiant : ils ne
            # partent pas dans un depot par accident.
            gitignore.write_text("connectors/\n", encoding="utf-8")
        return workspace

    @property
    def connectorsDirectory(self) -> Path:
        return self.root / "connectors"

    @property
    def casesDirectory(self) -> Path:
        return self.root / "cases"

    @property
    def reportsDirectory(self) -> Path:
        return self.root / "reports"

    # ------------------------------------------------------------------ connecteurs
    def listConnectors(self) -> list[HttpConnector | VectorEngine]:
        connectors = []
        for path in sorted(self.connectorsDirectory.glob("*.json")):
            connectors.append(declarationFromDictionary(json.loads(path.read_text(encoding="utf-8"))))
        return connectors

    def connectorPath(self, name: str) -> Path:
        return self.connectorsDirectory / f"{slugify(name)}.json"

    def saveConnector(self, connector: HttpConnector | VectorEngine) -> Path:
        path = self.connectorPath(connector.name)
        path.write_text(
            json.dumps(declarationToDictionary(connector), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # Un connecteur peut porter un identifiant de service : lisible par son seul
        # proprietaire, comme un fichier d'environnement.
        os.chmod(path, OWNER_ONLY)
        return path

    def loadConnector(self, name: str) -> HttpConnector | VectorEngine:
        path = self.connectorPath(name)
        if not path.exists():
            raise FileNotFoundError(f"aucun connecteur nomme « {name} »")
        return declarationFromDictionary(json.loads(path.read_text(encoding="utf-8")))

    def deleteConnector(self, name: str) -> None:
        self.connectorPath(name).unlink(missing_ok=True)

    # ------------------------------------------------------------------ jeux de cas
    def listCaseSets(self) -> list[dict]:
        sets = []
        for path in sorted(self.casesDirectory.glob("*.jsonl")):
            cases = loadCases(path)
            sets.append(
                {
                    "name": path.stem,
                    "path": str(path),
                    "total": len(cases),
                    "refusals": sum(case.expectsRefusal for case in cases),
                    "categories": sorted({case.category for case in cases if case.category}),
                }
            )
        return sets

    def saveCaseSet(self, name: str, cases: list[Case]) -> Path:
        path = self.casesDirectory / f"{slugify(name)}.jsonl"
        writeCases(cases, path)
        return path

    def loadCaseSet(self, name: str) -> list[Case]:
        path = self.casesDirectory / f"{slugify(name)}.jsonl"
        if not path.exists():
            raise FileNotFoundError(f"aucun jeu de questions nomme « {name} »")
        return loadCases(path)

    # ------------------------------------------------------------------ rapports
    def reportPath(self, connectorName: str, caseSetName: str, stamped: bool = True) -> Path:
        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        pieces = [slugify(connectorName), slugify(caseSetName)]
        if stamped:
            pieces.append(stamp)
        return self.reportsDirectory / f"{'--'.join(pieces)}.json"

    def listReports(self) -> list[dict]:
        reports = []
        for path in sorted(self.reportsDirectory.glob("*.json"), reverse=True):
            payload = json.loads(path.read_text(encoding="utf-8"))
            summary = payload.get("summary", {})
            reports.append(
                {
                    "name": path.stem,
                    "path": str(path),
                    "generatedAt": payload.get("generatedAt", ""),
                    "label": payload.get("label", ""),
                    "passed": summary.get("passed"),
                    "total": summary.get("casesTotal"),
                    "summary": summary,
                }
            )
        return reports
