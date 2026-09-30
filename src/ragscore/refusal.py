"""Reconnaitre qu'un systeme a refuse de repondre.

Un cas de refus se note sur deux conditions : le systeme dit qu'il ne sait pas, ET il ne
laisse echapper aucune des valeurs interdites. La premiere condition se detecte par motifs,
et c'est la partie fragile : un refus parfaitement formule mais non reconnu compte comme un
echec, ce qui sous-estime le systeme. Les motifs par defaut tolerent donc les incises
(« je ne peux DONC pas repondre »), qui etaient la cause principale des faux echecs.

Les motifs sont propres a une langue. Ils s'injectent, ils ne se codent pas en dur.
"""

from __future__ import annotations

import re

FRENCH_REFUSAL_PATTERNS = [
    r"ne (?:\w+ ){0,2}figure(?:nt)? pas",
    r"ne (?:\w+ ){0,2}trouve pas",
    r"ne (?:\w+ ){0,2}permet(?:tent)? pas",
    r"n'existe pas",
    r"aucune information",
    r"aucun des extraits",
    r"aucun extrait",
    r"ne (?:\w+ ){0,2}contien(?:t|nent) pas",
    r"ne (?:\w+ ){0,2}comporte(?:nt)? pas",
    r"ne (?:\w+ ){0,2}peu(?:x|t) (?:\w+ ){0,2}pas repondre",
    r"pas en mesure",
    r"ne (?:\w+ ){0,2}mentionne(?:nt)? (?:pas|aucun)",
    r"ne (?:\w+ ){0,2}releve(?:nt)? pas",
    r"ne (?:\w+ ){0,2}dispose pas",
    r"faute d'extraits",
    r"hors du perimetre",
]

ENGLISH_REFUSAL_PATTERNS = [
    r"(?:do|does|can)(?:es)?n[o']t (?:\w+ ){0,2}(?:contain|mention|cover|say)",
    r"(?:cannot|can not|unable to) (?:\w+ ){0,2}answer",
    r"no (?:relevant )?information",
    r"none of the (?:excerpts|passages|sources)",
    r"not (?:\w+ ){0,2}in the (?:provided )?(?:excerpts|passages|sources|documents)",
    r"outside the scope",
]


class RefusalDetector:
    """Detecte un refus dans un texte deja normalise pour comparaison."""

    def __init__(self, patterns: list[str] | None = None) -> None:
        self.patterns = [
            re.compile(pattern) for pattern in (patterns or FRENCH_REFUSAL_PATTERNS)
        ]

    def detects(self, comparableAnswer: str) -> bool:
        return any(pattern.search(comparableAnswer) for pattern in self.patterns)
