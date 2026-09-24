"""
Digital MRV (Measurement, Reporting, Verification) Prototype
for Community-Based Invasive Species Removal & Biomass Monitoring
==============================================================

Tracks biomass and land use across three monitoring phases for a
community working plot:

    BASELINE        -> before invasive removal
    DURING_REMOVAL  -> progress / biomass removed while clearing
    POST_REMOVAL    -> after removal (regrowth, restoration, land-use change)

Core outputs:
    - Aboveground biomass (AGB) in t/ha, split invasive vs native
    - Carbon stock (tC/ha) and CO2-equivalent (tCO2e/ha)
    - Invasive biomass removed vs native regeneration between phases
    - Land-use change tracking
    - Basic data-quality / verification flags (for the "V" in MRV)

NOTE ON ALLOMETRY:
    The species coefficients below are illustrative placeholders drawn
    from commonly-cited literature ranges for a prototype. For a real
    deployment, replace SPECIES_DB with locally validated allometric
    equations (species- and region-specific) from national biomass
    tables, IPCC default values, or field-calibrated regressions.
"""

from __future__ import annotations

import json
import hashlib
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class LandUseType(str, Enum):
    INVASIVE_DOMINATED = "invasive_dominated_scrub"
    DEGRADED_GRASSLAND = "degraded_grassland"
    NATIVE_FOREST = "native_forest"
    AGROFORESTRY = "agroforestry"
    RESTORED_GRASSLAND = "restored_grassland"
    COMMUNITY_WOODLOT = "community_woodlot"
    CROPLAND = "cropland"
    WETLAND = "wetland"
    BARE_CLEARED = "bare_cleared"


class MonitoringPhase(str, Enum):
    BASELINE = "baseline_before_removal"
    DURING_REMOVAL = "during_removal"
    POST_REMOVAL = "post_removal"
    FOLLOW_UP = "long_term_follow_up"


class SpeciesStatus(str, Enum):
    INVASIVE = "invasive"
    NATIVE = "native"


class MeasurementMethod(str, Enum):
    TREE_CENSUS = "tree_shrub_allometric"   # DBH (+ height) -> allometric eq.
    QUADRAT_HARVEST = "quadrat_harvest"      # cut/weigh biomass in a quadrat


# ---------------------------------------------------------------------------
# Species / allometry database
# ---------------------------------------------------------------------------

@dataclass
class Species:
    key: str
    common_name: str
    status: SpeciesStatus
    method: MeasurementMethod
    # Power-law allometric model: AGB_kg = a * DBH_cm ** b   (tree/shrub)
    a: Optional[float] = None
    b: Optional[float] = None
    # Quadrat method: fraction of fresh-cut weight that is dry matter
    dry_matter_fraction: Optional[float] = None
    # Root:shoot ratio to approximate below-ground biomass (BGB)
    root_shoot_ratio: float = 0.24
    carbon_fraction: float = 0.47  # IPCC default AGB carbon fraction


SPECIES_DB: dict[str, Species] = {
    "prosopis_juliflora": Species(
        key="prosopis_juliflora", common_name="Prosopis juliflora (invasive tree)",
        status=SpeciesStatus.INVASIVE, method=MeasurementMethod.TREE_CENSUS,
        a=0.0754, b=2.556, root_shoot_ratio=0.28,
    ),
    "eucalyptus_invasive": Species(
        key="eucalyptus_invasive", common_name="Eucalyptus sp. (invasive tree)",
        status=SpeciesStatus.INVASIVE, method=MeasurementMethod.TREE_CENSUS,
        a=0.0673, b=2.51, root_shoot_ratio=0.24,
    ),
    "lantana_camara": Species(
        key="lantana_camara", common_name="Lantana camara (invasive shrub)",
        status=SpeciesStatus.INVASIVE, method=MeasurementMethod.QUADRAT_HARVEST,
        dry_matter_fraction=0.35, root_shoot_ratio=0.30,
    ),
    "chromolaena_odorata": Species(
        key="chromolaena_odorata", common_name="Chromolaena odorata (invasive shrub)",
        status=SpeciesStatus.INVASIVE, method=MeasurementMethod.QUADRAT_HARVEST,
        dry_matter_fraction=0.32, root_shoot_ratio=0.30,
    ),
    "native_acacia": Species(
        key="native_acacia", common_name="Native Acacia sp.",
        status=SpeciesStatus.NATIVE, method=MeasurementMethod.TREE_CENSUS,
        a=0.0673, b=2.65, root_shoot_ratio=0.24,
    ),
    "native_mixed_tree": Species(
        key="native_mixed_tree", common_name="Native mixed regenerating trees",
        status=SpeciesStatus.NATIVE, method=MeasurementMethod.TREE_CENSUS,
        a=0.0580, b=2.60, root_shoot_ratio=0.24,
    ),
    "native_grass_forb": Species(
        key="native_grass_forb", common_name="Native grass / forb regrowth",
        status=SpeciesStatus.NATIVE, method=MeasurementMethod.QUADRAT_HARVEST,
        dry_matter_fraction=0.30, root_shoot_ratio=0.50,
    ),
}

CO2_PER_C = 44.0 / 12.0  # conversion factor: tCO2e per tC


# ---------------------------------------------------------------------------
# Measurement records
# ---------------------------------------------------------------------------

@dataclass
class TreeRecord:
    """One tree/shrub-census entry: n individuals of a species with mean DBH."""
    species_key: str
    count: int
    mean_dbh_cm: float
    mean_height_m: Optional[float] = None

    def agb_kg_total(self) -> float:
        sp = SPECIES_DB[self.species_key]
        if sp.a is None:
            raise ValueError(f"{self.species_key} has no tree allometric coefficients")
        per_tree_kg = sp.a * (self.mean_dbh_cm ** sp.b)
        return per_tree_kg * self.count


@dataclass
class QuadratRecord:
    """One quadrat-harvest entry: fresh-cut weight of a species in a known area."""
    species_key: str
    fresh_weight_kg: float
    quadrat_area_m2: float

    def dry_kg_per_m2(self) -> float:
        sp = SPECIES_DB[self.species_key]
        if sp.dry_matter_fraction is None:
            raise ValueError(f"{self.species_key} has no dry matter fraction")
        dry_kg = self.fresh_weight_kg * sp.dry_matter_fraction
        return dry_kg / self.quadrat_area_m2


# ---------------------------------------------------------------------------
# Plot & community working area
# ---------------------------------------------------------------------------

@dataclass
class Plot:
    plot_id: str
    name: str
    community_name: str
    area_ha: float
    land_use_history: list[tuple[str, LandUseType]] = field(default_factory=list)  # (date_iso, land_use)
    gps_boundary: Optional[list[tuple[float, float]]] = None  # [(lat, lon), ...]

    def set_land_use(self, on_date: date, land_use: LandUseType) -> None:
        self.land_use_history.append((on_date.isoformat(), land_use))

    @property
    def current_land_use(self) -> Optional[LandUseType]:
        if not self.land_use_history:
            return None
        return LandUseType(self.land_use_history[-1][1])


# ---------------------------------------------------------------------------
# Monitoring event (one field visit / survey)
# ---------------------------------------------------------------------------

@dataclass
class MonitoringEvent:
    plot_id: str
    phase: MonitoringPhase
    event_date: date
    monitor_name: str
    tree_records: list[TreeRecord] = field(default_factory=list)
    quadrat_records: list[QuadratRecord] = field(default_factory=list)
    gps_point: Optional[tuple[float, float]] = None
    photo_evidence: list[str] = field(default_factory=list)  # file paths / URLs
    notes: str = ""
    biomass_removed_kg: Optional[float] = None  # only meaningful for DURING_REMOVAL
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])

    def evidence_hash(self) -> str:
        """Simple integrity fingerprint for the event record (for audit trail)."""
        payload = json.dumps(
            {
                "plot_id": self.plot_id,
                "phase": self.phase.value,
                "date": self.event_date.isoformat(),
                "monitor": self.monitor_name,
                "trees": [asdict(t) for t in self.tree_records],
                "quadrats": [asdict(q) for q in self.quadrat_records],
            },
            sort_keys=True,
        ).encode()
        return hashlib.sha256(payload).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Biomass / carbon computation
# ---------------------------------------------------------------------------

@dataclass
class BiomassSummary:
    event_id: str
    phase: MonitoringPhase
    event_date: str
    invasive_agb_t_ha: float
    native_agb_t_ha: float
    total_agb_t_ha: float
    total_biomass_incl_bgb_t_ha: float  # AGB + estimated below-ground biomass
    carbon_stock_tC_ha: float
    co2e_t_ha: float
    total_agb_tonnes: float  # scaled to full plot area


def _quadrat_records_to_density(records: list[QuadratRecord]) -> dict[str, float]:
    """Average kg/m2 per species across all quadrats of that species -> kg/ha."""
    by_species: dict[str, list[float]] = {}
    for r in records:
        by_species.setdefault(r.species_key, []).append(r.dry_kg_per_m2())
    return {sp: (sum(vals) / len(vals)) * 10_000 for sp, vals in by_species.items()}


def compute_biomass_summary(event: MonitoringEvent, plot: Plot) -> BiomassSummary:
    """Compute AGB (t/ha), carbon stock and CO2e for one monitoring event."""
    invasive_kg_ha = 0.0
    native_kg_ha = 0.0
    invasive_bgb_kg_ha = 0.0
    native_bgb_kg_ha = 0.0

    # --- Tree/shrub census records: assume full census over the plot area ---
    for t in event.tree_records:
        sp = SPECIES_DB[t.species_key]
        agb_total_kg = t.agb_kg_total()
        agb_kg_ha = agb_total_kg / plot.area_ha
        bgb_kg_ha = agb_kg_ha * sp.root_shoot_ratio
        if sp.status == SpeciesStatus.INVASIVE:
            invasive_kg_ha += agb_kg_ha
            invasive_bgb_kg_ha += bgb_kg_ha
        else:
            native_kg_ha += agb_kg_ha
            native_bgb_kg_ha += bgb_kg_ha

    # --- Quadrat records: density (kg/ha) averaged across sampled quadrats ---
    densities = _quadrat_records_to_density(event.quadrat_records)
    for sp_key, kg_ha in densities.items():
        sp = SPECIES_DB[sp_key]
        bgb_kg_ha = kg_ha * sp.root_shoot_ratio
        if sp.status == SpeciesStatus.INVASIVE:
            invasive_kg_ha += kg_ha
            invasive_bgb_kg_ha += bgb_kg_ha
        else:
            native_kg_ha += kg_ha
            native_bgb_kg_ha += bgb_kg_ha

    invasive_t_ha = invasive_kg_ha / 1000
    native_t_ha = native_kg_ha / 1000
    total_agb_t_ha = invasive_t_ha + native_t_ha
    total_bgb_t_ha = (invasive_bgb_kg_ha + native_bgb_kg_ha) / 1000
    total_biomass_t_ha = total_agb_t_ha + total_bgb_t_ha

    # Weighted average carbon fraction across the species present (default 0.47)
    carbon_fraction = 0.47
    carbon_stock_tC_ha = total_biomass_t_ha * carbon_fraction
    co2e_t_ha = carbon_stock_tC_ha * CO2_PER_C

    return BiomassSummary(
        event_id=event.event_id,
        phase=event.phase,
        event_date=event.event_date.isoformat(),
        invasive_agb_t_ha=round(invasive_t_ha, 3),
        native_agb_t_ha=round(native_t_ha, 3),
        total_agb_t_ha=round(total_agb_t_ha, 3),
        total_biomass_incl_bgb_t_ha=round(total_biomass_t_ha, 3),
        carbon_stock_tC_ha=round(carbon_stock_tC_ha, 3),
        co2e_t_ha=round(co2e_t_ha, 3),
        total_agb_tonnes=round(total_agb_t_ha * plot.area_ha, 3),
    )


# ---------------------------------------------------------------------------
# Verification: simple automated data-quality flags
# ---------------------------------------------------------------------------

def verify_event(event: MonitoringEvent) -> list[str]:
    """Return a list of data-quality / verification warnings for an event."""
    flags = []
    if not event.gps_point:
        flags.append("Missing GPS point for this monitoring event.")
    if not event.photo_evidence:
        flags.append("No photo evidence attached.")
    if not event.tree_records and not event.quadrat_records:
        flags.append("No biomass measurements recorded for this event.")
    for t in event.tree_records:
        if t.mean_dbh_cm <= 0 or t.count <= 0:
            flags.append(f"Invalid tree record for {t.species_key} (dbh/count <= 0).")
    for q in event.quadrat_records:
        if q.fresh_weight_kg < 0 or q.quadrat_area_m2 <= 0:
            flags.append(f"Invalid quadrat record for {q.species_key}.")
    if event.phase == MonitoringPhase.DURING_REMOVAL and event.biomass_removed_kg is None:
        flags.append("DURING_REMOVAL event missing logged biomass_removed_kg.")
    return flags


# ---------------------------------------------------------------------------
# MRV System: orchestrates plots + events + reporting
# ---------------------------------------------------------------------------

class MRVSystem:
    def __init__(self):
        self.plots: dict[str, Plot] = {}
        self.events: list[MonitoringEvent] = []

    # -- registration -------------------------------------------------
    def register_plot(self, plot: Plot) -> None:
        self.plots[plot.plot_id] = plot

    def add_event(self, event: MonitoringEvent) -> BiomassSummary:
        plot = self.plots[event.plot_id]
        self.events.append(event)
        return compute_biomass_summary(event, plot)

    def events_for_plot(self, plot_id: str) -> list[MonitoringEvent]:
        return [e for e in self.events if e.plot_id == plot_id]

    # -- reporting ------------------------------------------------------
    def phase_comparison(self, plot_id: str) -> dict[str, BiomassSummary]:
        """Latest summary per phase for a plot, keyed by phase value."""
        plot = self.plots[plot_id]
        result: dict[str, BiomassSummary] = {}
        for e in self.events_for_plot(plot_id):
            result[e.phase.value] = compute_biomass_summary(e, plot)
        return result

    def impact_report(self, plot_id: str) -> dict:
        """
        Headline MRV outputs: invasive biomass removed, native regeneration,
        net carbon impact, and land-use change, comparing baseline -> post-removal.
        """
        comp = self.phase_comparison(plot_id)
        plot = self.plots[plot_id]
        baseline = comp.get(MonitoringPhase.BASELINE.value)
        post = comp.get(MonitoringPhase.POST_REMOVAL.value)

        during_events = [e for e in self.events_for_plot(plot_id)
                          if e.phase == MonitoringPhase.DURING_REMOVAL]
        total_removed_kg = sum(e.biomass_removed_kg or 0 for e in during_events)

        report = {
            "plot_id": plot_id,
            "plot_name": plot.name,
            "community": plot.community_name,
            "area_ha": plot.area_ha,
            "land_use_history": plot.land_use_history,
            "phase_summaries": {k: asdict(v) for k, v in comp.items()},
            "invasive_biomass_removed_during_ops_kg": round(total_removed_kg, 1),
        }

        if baseline and post:
            report["invasive_agb_change_t_ha"] = round(
                post.invasive_agb_t_ha - baseline.invasive_agb_t_ha, 3
            )
            report["native_agb_change_t_ha"] = round(
                post.native_agb_t_ha - baseline.native_agb_t_ha, 3
            )
            report["net_carbon_change_tC_ha"] = round(
                post.carbon_stock_tC_ha - baseline.carbon_stock_tC_ha, 3
            )
            report["net_co2e_change_t_ha"] = round(
                post.co2e_t_ha - baseline.co2e_t_ha, 3
            )
            invasive_pct_reduction = None
            if baseline.invasive_agb_t_ha > 0:
                invasive_pct_reduction = round(
                    100 * (baseline.invasive_agb_t_ha - post.invasive_agb_t_ha)
                    / baseline.invasive_agb_t_ha, 1
                )
            report["invasive_pct_reduction"] = invasive_pct_reduction

        # verification flags across all events for this plot
        report["verification_flags"] = {
            e.event_id: verify_event(e) for e in self.events_for_plot(plot_id)
        }
        return report

    # -- persistence ------------------------------------------------------
    @classmethod
    def from_json(cls, path: str) -> "MRVSystem":
        with open(path) as f:
            data = json.load(f)
        mrv = cls()
        for pid, pdata in data.get("plots", {}).items():
            plot = Plot(
                plot_id=pdata["plot_id"],
                name=pdata["name"],
                community_name=pdata["community_name"],
                area_ha=pdata["area_ha"],
                land_use_history=[(d, LandUseType(u)) for d, u in pdata.get("land_use_history", [])],
                gps_boundary=[tuple(pt) for pt in pdata["gps_boundary"]] if pdata.get("gps_boundary") else None,
            )
            mrv.plots[pid] = plot
        for edata in data.get("events", []):
            event = MonitoringEvent(
                plot_id=edata["plot_id"],
                phase=MonitoringPhase(edata["phase"]),
                event_date=date.fromisoformat(edata["event_date"]),
                monitor_name=edata["monitor_name"],
                tree_records=[TreeRecord(**t) for t in edata.get("tree_records", [])],
                quadrat_records=[QuadratRecord(**q) for q in edata.get("quadrat_records", [])],
                gps_point=tuple(edata["gps_point"]) if edata.get("gps_point") else None,
                photo_evidence=edata.get("photo_evidence", []),
                notes=edata.get("notes", ""),
                biomass_removed_kg=edata.get("biomass_removed_kg"),
                event_id=edata.get("event_id", uuid.uuid4().hex[:10]),
            )
            mrv.events.append(event)
        return mrv

    def to_json(self, path: str) -> None:
        data = {
            "plots": {
                pid: {**asdict(p), "land_use_history": p.land_use_history}
                for pid, p in self.plots.items()
            },
            "events": [
                {
                    **asdict(e),
                    "phase": e.phase.value,
                    "event_date": e.event_date.isoformat(),
                }
                for e in self.events
            ],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
