"""ragscore : mesurer un systeme RAG au lieu de l'affirmer bon.

Le harnais ne sait rien du systeme qu'il note. On lui donne un jeu de cas et un objet qui
repond a une question ; il rend des chiffres separes pour la recuperation et pour la
generation, et un rapport re-notable sans rappeler le systeme.
"""

from ragscore.case import Case, loadCases, writeCases
from ragscore.metrics import CaseOutcome, scoreCase, summarise
from ragscore.refusal import RefusalDetector
from ragscore.report import readObservations, writeReport
from ragscore.runner import rescore, runEvaluation
from ragscore.system import Answer, MeasurableSystem, RetrievalStage, RetrievedPassage

__all__ = [
    "Answer",
    "Case",
    "CaseOutcome",
    "MeasurableSystem",
    "RefusalDetector",
    "RetrievalStage",
    "RetrievedPassage",
    "loadCases",
    "readObservations",
    "rescore",
    "runEvaluation",
    "scoreCase",
    "summarise",
    "writeCases",
    "writeReport",
]
