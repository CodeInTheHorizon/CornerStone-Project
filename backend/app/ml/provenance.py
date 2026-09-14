"""Which provenance classes a model may be trained on.

Training never combines provenance silently. The caller names the source types
it accepts, and the dataset may contain only those. Filtering rows after the
fact is not enough: market features (category medians, listing density,
competition) are computed across every row in a dataset, so a LIVE row built
alongside DEMO rows already carries DEMO information. The dataset has to be
rebuilt with only the accepted source types.

Allowed selections:

* ``demo``               -- development model on synthetic data
* ``imported``           -- model on an operator-supplied historical dataset
* ``live``               -- model on genuinely collected history
* ``imported`` + ``live`` -- allowed when both are selected explicitly
* ``demo`` with anything -- rejected, unless a development override is set in a
  development environment; such a model is never more than experimental
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.enums import SourceType

PROFILES = {
    frozenset({"demo"}): "development_demo",
    frozenset({"imported"}): "imported_history",
    frozenset({"live"}): "live_history",
    frozenset({"imported", "live"}): "imported_and_live",
}


class ProvenanceError(ValueError):
    """The requested training provenance is not permitted."""


@dataclass(frozen=True)
class ProvenancePolicy:
    selected: list[str]
    dataset_source_types: list[str]
    profile: str
    development_override: bool

    @property
    def uses_demo(self) -> bool:
        return "demo" in self.dataset_source_types or "demo" in self.selected

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_source_types": self.selected,
            "dataset_source_types": self.dataset_source_types,
            "profile": self.profile,
            "development_override": self.development_override,
            "uses_demo": self.uses_demo,
        }


def resolve(
    selected: list[str] | None,
    dataset_source_types: list[str],
    *,
    development_override: bool = False,
    is_development: bool = False,
) -> ProvenancePolicy:
    """Validate the requested source types against the dataset. Raises ProvenanceError."""
    valid = {source.value for source in SourceType}
    chosen = sorted({str(value).lower() for value in (selected or [])})
    if not chosen:
        raise ProvenanceError(
            "Select the source types this model may be trained on (demo, imported, live). "
            "Training never picks them implicitly."
        )
    unknown = sorted(set(chosen) - valid)
    if unknown:
        raise ProvenanceError(f"Unknown source type(s): {', '.join(unknown)}.")

    present = sorted({str(value).lower() for value in dataset_source_types})
    if not present:
        raise ProvenanceError("The dataset does not record its source types; rebuild it before training.")
    unselected = sorted(set(present) - set(chosen))
    if unselected:
        raise ProvenanceError(
            f"The dataset contains {', '.join(s.upper() for s in unselected)} rows that were not selected. "
            "Market features are computed across all rows, so filtering is not enough: rebuild the dataset "
            f"with only {', '.join(s.upper() for s in chosen)}."
        )

    key = frozenset(chosen)
    if key in PROFILES:
        return ProvenancePolicy(chosen, present, PROFILES[key], False)

    # Only remaining combinations mix DEMO with real provenance.
    if development_override and is_development:
        return ProvenancePolicy(chosen, present, "development_mixed", True)
    if development_override:
        raise ProvenanceError("The DEMO mixing override is only available when ENVIRONMENT=development.")
    raise ProvenanceError(
        "DEMO data cannot be combined with IMPORTED or LIVE data: synthetic rows would contaminate a "
        "real-data model. Train on DEMO alone, or on IMPORTED and/or LIVE without DEMO. A development "
        "override exists for local experiments only."
    )
