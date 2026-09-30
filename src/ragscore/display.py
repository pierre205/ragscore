"""Rendu lisible d'un resume. Le seul endroit ou les metriques portent un nom francais."""

from __future__ import annotations

METRIC_LABELS = {
    "meanReciprocalRank": "MRR (rang moyen inverse)",
    "normalisedDiscountedGain": "nDCG (qualite du classement)",
    "citedRelevant": "document attendu cite dans la reponse",
    "mustIncludeSatisfied": "valeur attendue presente",
    "refusalCorrect": "refus corrects hors corpus",
    "noForbiddenValue": "aucune valeur interdite produite",
}


def formatSummary(summary: dict) -> str:
    lines = ["=" * 68, "RESULTATS", "=" * 68]
    lines.append(
        f"  cas reussis                          : {summary['passed']}/{summary['casesTotal']}"
    )
    for stageName, value in summary["recallByStage"].items():
        lines.append(f"  document attendu apres « {stageName} »".ljust(40) + f": {value:.1%}")
    for key, label in METRIC_LABELS.items():
        value = summary[key]
        rendered = f"{value:.3f}" if key in {"meanReciprocalRank", "normalisedDiscountedGain"} else f"{value:.1%}"
        lines.append(f"  {label}".ljust(40) + f": {rendered}")

    lines.append("\n  par categorie :")
    for category, bucket in sorted(summary["byCategory"].items()):
        lines.append(
            f"    {category or '(sans)':12} {bucket['total']:2d} cas | reussis "
            f"{bucket['passed']}/{bucket['total']} | document trouve "
            f"{bucket['found']}/{bucket['total']} | valeur attendue "
            f"{bucket['mustInclude']}/{bucket['total']}"
        )

    usage = summary.get("usage", {})
    if usage.get("estimatedCostUsd"):
        lines.append(
            f"\n  cout de l'execution : {usage['estimatedCostUsd']:.3f} $"
            f" ({usage['inputTokens']:,} jetons en entree, {usage['outputTokens']:,} en sortie)"
        )
    return "\n".join(lines)
