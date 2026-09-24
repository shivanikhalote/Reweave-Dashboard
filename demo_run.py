"""
Demo: Community Working Plot - Lantana/Prosopis Invasive Removal
==================================================================
Simulates a small community-managed plot going through:
  1) BASELINE        survey (invasive-dominated scrub)
  2) DURING_REMOVAL   logged clearing operations
  3) POST_REMOVAL     survey (restored grassland / native regrowth)

Produces:
  - outputs/mrv_data.json          (raw plot + event data)
  - outputs/mrv_impact_report.json (computed MRV summary)
  - outputs/mrv_report.md          (human-readable MRV report)
  - outputs/biomass_by_phase.png   (chart)
  - outputs/carbon_impact.png      (chart)
  - outputs/landuse_change.png     (chart)
"""

import os
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from mrv_core import (
    MRVSystem, Plot, MonitoringEvent, TreeRecord, QuadratRecord,
    MonitoringPhase, LandUseType, compute_biomass_summary,
)

OUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUT_DIR, exist_ok=True)


def build_scenario() -> MRVSystem:
    mrv = MRVSystem()

    plot = Plot(
        plot_id="PLOT-001",
        name="Kondhwa Community Working Plot",
        community_name="Kondhwa Village Forest Committee",
        area_ha=2.5,
        gps_boundary=[(18.4650, 73.8950), (18.4655, 73.8958), (18.4648, 73.8962)],
    )
    plot.set_land_use(date(2025, 1, 10), LandUseType.INVASIVE_DOMINATED)
    mrv.register_plot(plot)

    # -------------------- PHASE 1: BASELINE --------------------------
    baseline = MonitoringEvent(
        plot_id=plot.plot_id,
        phase=MonitoringPhase.BASELINE,
        event_date=date(2025, 1, 15),
        monitor_name="R. Deshmukh (Community Monitor)",
        gps_point=(18.4651, 73.8955),
        photo_evidence=["baseline_photo_01.jpg", "baseline_photo_02.jpg"],
        notes="Dense Lantana camara understory with scattered Prosopis juliflora; "
              "minimal native regeneration visible.",
        tree_records=[
            TreeRecord(species_key="prosopis_juliflora", count=48, mean_dbh_cm=9.5),
            TreeRecord(species_key="native_mixed_tree", count=6, mean_dbh_cm=5.0),
        ],
        quadrat_records=[
            QuadratRecord("lantana_camara", fresh_weight_kg=14.2, quadrat_area_m2=4),
            QuadratRecord("lantana_camara", fresh_weight_kg=16.8, quadrat_area_m2=4),
            QuadratRecord("lantana_camara", fresh_weight_kg=12.1, quadrat_area_m2=4),
            QuadratRecord("native_grass_forb", fresh_weight_kg=1.1, quadrat_area_m2=4),
        ],
    )
    mrv.add_event(baseline)

    # -------------------- PHASE 2: DURING REMOVAL ---------------------
    during1 = MonitoringEvent(
        plot_id=plot.plot_id,
        phase=MonitoringPhase.DURING_REMOVAL,
        event_date=date(2025, 2, 20),
        monitor_name="R. Deshmukh (Community Monitor)",
        gps_point=(18.4651, 73.8955),
        photo_evidence=["clearing_week1.jpg"],
        notes="Manual uprooting of Lantana over 1.0 ha by community labour team (12 members).",
        biomass_removed_kg=5400,
    )
    mrv.add_event(during1)

    during2 = MonitoringEvent(
        plot_id=plot.plot_id,
        phase=MonitoringPhase.DURING_REMOVAL,
        event_date=date(2025, 3, 10),
        monitor_name="R. Deshmukh (Community Monitor)",
        gps_point=(18.4651, 73.8955),
        photo_evidence=["clearing_week4.jpg"],
        notes="Prosopis felling and stump treatment across remaining 1.5 ha.",
        biomass_removed_kg=8200,
    )
    mrv.add_event(during2)

    plot.set_land_use(date(2025, 3, 15), LandUseType.BARE_CLEARED)

    # -------------------- PHASE 3: POST REMOVAL -----------------------
    post = MonitoringEvent(
        plot_id=plot.plot_id,
        phase=MonitoringPhase.POST_REMOVAL,
        event_date=date(2025, 9, 5),
        monitor_name="S. Kale (Forest Dept. Verifier) + R. Deshmukh",
        gps_point=(18.4651, 73.8955),
        photo_evidence=["post_removal_01.jpg", "post_removal_02.jpg", "post_removal_gps.jpg"],
        notes="Community re-seeded native grasses and planted native saplings. "
              "Residual Lantana resprouts spot-treated.",
        tree_records=[
            TreeRecord(species_key="prosopis_juliflora", count=3, mean_dbh_cm=4.0),
            TreeRecord(species_key="native_mixed_tree", count=140, mean_dbh_cm=2.5),
        ],
        quadrat_records=[
            QuadratRecord("lantana_camara", fresh_weight_kg=1.5, quadrat_area_m2=4),
            QuadratRecord("lantana_camara", fresh_weight_kg=0.9, quadrat_area_m2=4),
            QuadratRecord("native_grass_forb", fresh_weight_kg=6.4, quadrat_area_m2=4),
            QuadratRecord("native_grass_forb", fresh_weight_kg=7.1, quadrat_area_m2=4),
        ],
    )
    mrv.add_event(post)
    plot.set_land_use(date(2025, 9, 5), LandUseType.RESTORED_GRASSLAND)

    return mrv


def make_charts(mrv: MRVSystem, plot_id: str):
    comp = mrv.phase_comparison(plot_id)
    phase_order = [MonitoringPhase.BASELINE.value, MonitoringPhase.POST_REMOVAL.value]
    labels = ["Baseline\n(before removal)", "Post-removal\n(after restoration)"]

    invasive_vals = [comp[p].invasive_agb_t_ha for p in phase_order]
    native_vals = [comp[p].native_agb_t_ha for p in phase_order]

    # --- Chart 1: biomass by phase (stacked bar, invasive vs native) ---
    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.bar(labels, invasive_vals, label="Invasive species AGB", color="#c0392b")
    ax.bar(labels, native_vals, bottom=invasive_vals, label="Native species AGB", color="#27ae60")
    ax.set_ylabel("Aboveground biomass (t/ha)")
    ax.set_title("Biomass Composition: Before vs After Invasive Removal")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "biomass_by_phase.png"), dpi=150)
    plt.close(fig)

    # --- Chart 2: carbon / CO2e impact ---
    carbon_vals = [comp[p].carbon_stock_tC_ha for p in phase_order]
    co2e_vals = [comp[p].co2e_t_ha for p in phase_order]
    x = range(len(labels))
    width = 0.35
    fig, ax = plt.subplots(figsize=(6, 4.5))
    ax.bar([i - width / 2 for i in x], carbon_vals, width, label="Carbon stock (tC/ha)", color="#34495e")
    ax.bar([i + width / 2 for i in x], co2e_vals, width, label="CO2e (t/ha)", color="#2980b9")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_title("Carbon Stock & CO2e: Before vs After")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "carbon_impact.png"), dpi=150)
    plt.close(fig)

    # --- Chart 3: land-use change timeline ---
    plot = mrv.plots[plot_id]
    fig, ax = plt.subplots(figsize=(7, 2.5))
    dates = [d for d, _ in plot.land_use_history]
    uses = [u.value.replace("_", " ") for _, u in plot.land_use_history]
    ax.plot(dates, [0] * len(dates), "o-", color="#7f8c8d", markersize=10)
    for i, (d, u) in enumerate(zip(dates, uses)):
        ax.annotate(f"{d}\n{u}", (d, 0), textcoords="offset points",
                     xytext=(0, 15 if i % 2 == 0 else -30), ha="center", fontsize=8)
    ax.set_yticks([])
    ax.set_title("Land-Use Change Timeline")
    ax.set_xlabel("")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "landuse_change.png"), dpi=150)
    plt.close(fig)


def write_markdown_report(report: dict, path: str):
    lines = []
    lines.append(f"# Digital MRV Report — {report['plot_name']}\n")
    lines.append(f"**Community:** {report['community']}  ")
    lines.append(f"**Plot ID:** {report['plot_id']}  ")
    lines.append(f"**Plot area:** {report['area_ha']} ha\n")

    lines.append("## Land-Use History\n")
    for d, u in report["land_use_history"]:
        lines.append(f"- {d}: {u.replace('_', ' ') if isinstance(u, str) else u}")
    lines.append("")

    lines.append("## Phase Summaries (per hectare)\n")
    lines.append("| Phase | Date | Invasive AGB (t/ha) | Native AGB (t/ha) | Total AGB (t/ha) | Carbon (tC/ha) | CO2e (t/ha) |")
    lines.append("|---|---|---|---|---|---|---|")
    for phase, s in report["phase_summaries"].items():
        lines.append(
            f"| {phase.replace('_', ' ')} | {s['event_date']} | {s['invasive_agb_t_ha']} | "
            f"{s['native_agb_t_ha']} | {s['total_agb_t_ha']} | {s['carbon_stock_tC_ha']} | {s['co2e_t_ha']} |"
        )
    lines.append("")

    lines.append("## Removal & Restoration Impact\n")
    lines.append(f"- **Invasive biomass physically removed during operations:** "
                  f"{report['invasive_biomass_removed_during_ops_kg']:,} kg "
                  f"({report['invasive_biomass_removed_during_ops_kg']/1000:.2f} t)")
    if "invasive_pct_reduction" in report and report["invasive_pct_reduction"] is not None:
        lines.append(f"- **Standing invasive biomass reduction (baseline → post):** "
                      f"{report['invasive_pct_reduction']}%")
    if "net_carbon_change_tC_ha" in report:
        lines.append(f"- **Net carbon stock change:** {report['net_carbon_change_tC_ha']} tC/ha")
        lines.append(f"- **Net CO2e change:** {report['net_co2e_change_t_ha']} t/ha")
        lines.append(f"- **Native biomass gain:** {report['native_agb_change_t_ha']} t/ha")
    lines.append("")

    lines.append("## Verification Flags\n")
    any_flags = False
    for event_id, flags in report["verification_flags"].items():
        if flags:
            any_flags = True
            lines.append(f"- Event `{event_id}`:")
            for f in flags:
                lines.append(f"  - ⚠️ {f}")
    if not any_flags:
        lines.append("- ✅ No data-quality issues flagged across all monitoring events.")
    lines.append("")

    lines.append("## Charts\n")
    lines.append("![Biomass by phase](biomass_by_phase.png)\n")
    lines.append("![Carbon impact](carbon_impact.png)\n")
    lines.append("![Land use change](landuse_change.png)\n")

    with open(path, "w") as f:
        f.write("\n".join(lines))


def main():
    mrv = build_scenario()
    plot_id = "PLOT-001"

    report = mrv.impact_report(plot_id)

    mrv.to_json(os.path.join(OUT_DIR, "mrv_data.json"))
    import json
    with open(os.path.join(OUT_DIR, "mrv_impact_report.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)

    make_charts(mrv, plot_id)
    write_markdown_report(report, os.path.join(OUT_DIR, "mrv_report.md"))

    # Console summary
    print("=" * 70)
    print(f"MRV RUN COMPLETE: {report['plot_name']} ({report['area_ha']} ha)")
    print("=" * 70)
    for phase, s in report["phase_summaries"].items():
        print(f"[{phase}] invasive={s['invasive_agb_t_ha']} t/ha  "
              f"native={s['native_agb_t_ha']} t/ha  "
              f"carbon={s['carbon_stock_tC_ha']} tC/ha  co2e={s['co2e_t_ha']} t/ha")
    print(f"\nInvasive biomass removed (logged): "
          f"{report['invasive_biomass_removed_during_ops_kg']} kg")
    if "invasive_pct_reduction" in report:
        print(f"Invasive standing-biomass reduction: {report['invasive_pct_reduction']}%")
        print(f"Net carbon change: {report['net_carbon_change_tC_ha']} tC/ha "
              f"({report['net_co2e_change_t_ha']} t CO2e/ha)")
    print(f"\nOutputs written to: {OUT_DIR}")


if __name__ == "__main__":
    main()
