"""Choisir le systeme a mesurer d'apres sa declaration.

Deux sortes coexistent, distinguees par le champ « kind » :

- « http »   : on branche l'API reellement livree. Mesure LE PRODUIT.
- « vector » : on execute la chaine ici meme, a partir d'une base vectorisee et de deux
               cles. Mesure UNE APPROCHE, sans application a deployer.

Les deux rendent le meme contrat, donc le harnais ne fait aucune difference entre elles.
"""

from __future__ import annotations

from ragscore.connector import (
    ConnectorError,
    HttpConnector,
    HttpConnectorSystem,
    connectorFromDictionary,
    connectorToDictionary,
)
from ragscore.engines.vector import VectorEngine, VectorEngineSystem

HTTP = "http"
VECTOR = "vector"


def declarationFromDictionary(raw: dict) -> HttpConnector | VectorEngine:
    kind = raw.get("kind", HTTP)
    if kind == VECTOR:
        known = dict(raw)
        expected = set(VectorEngine.__dataclass_fields__)
        unexpected = set(known) - expected
        if unexpected:
            raise ConnectorError(
                f"champs inconnus dans le moteur : {', '.join(sorted(unexpected))}"
            )
        return VectorEngine(**known)
    if kind != HTTP:
        raise ConnectorError(f"sorte de systeme inconnue : « {kind} »")
    return connectorFromDictionary({key: value for key, value in raw.items() if key != "kind"})


def declarationToDictionary(declaration: HttpConnector | VectorEngine) -> dict:
    if isinstance(declaration, VectorEngine):
        return {
            field: getattr(declaration, field)
            for field in VectorEngine.__dataclass_fields__
        }
    return {"kind": HTTP, **connectorToDictionary(declaration)}


def buildSystem(declaration: HttpConnector | VectorEngine):
    if isinstance(declaration, VectorEngine):
        return VectorEngineSystem(engine=declaration)
    return HttpConnectorSystem(declaration)
