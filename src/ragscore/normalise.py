"""Comparaison de texte tolerante a la mise en forme, intolerante au contenu.

Un fragment attendu ne doit pas etre compte absent parce que le modele l'a mis en gras,
l'a echappe en Markdown ou a double une espace. Il ne doit pas non plus etre compte present
si la valeur differe. La normalisation ne touche donc qu'a la presentation.
"""

from __future__ import annotations

import re
import unicodedata

MARKDOWN_EMPHASIS = re.compile(r"[*_`]+")
MARKDOWN_ESCAPE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|])")
WHITESPACE = re.compile(r"\s+")
# Les espaces insecables encadrent les unites et les milliers en francais : «  1 234 kWh ».
NON_BREAKING_SPACES = dict.fromkeys(map(ord, "    "), " ")


def normaliseForComparison(text: str) -> str:
    """Minuscules, sans accents, sans mise en forme Markdown, espaces reduites."""
    withoutEscapes = MARKDOWN_ESCAPE.sub(r"\1", text)
    withoutEmphasis = MARKDOWN_EMPHASIS.sub("", withoutEscapes)
    withRegularSpaces = withoutEmphasis.translate(NON_BREAKING_SPACES)
    decomposed = unicodedata.normalize("NFD", withRegularSpaces.lower())
    withoutAccents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return WHITESPACE.sub(" ", withoutAccents).strip()
