import os
from typing import Dict, List

import streamlit as st
import altair as alt
import pandas as pd
import re
import math
from streamlit import column_config as cc

from app.notion_repo import NotionRepository, NotionAPIError
from app.scoring import ScoringEngine
from app.models import Vendor, Part, VendorAnalysis, ScoringWeights
try:
    from app.kraljic import KraljicEngine
    KRALJIC_AVAILABLE = True
except Exception:
    KraljicEngine = None
    KRALJIC_AVAILABLE = False
import numpy as np

# Optional Plotly support (fallback to Altair if unavailable)
try:
    import plotly.express as px
    PLOTLY_AVAILABLE = True
except Exception:
    PLOTLY_AVAILABLE = False

def safe_plotly_bar(df, x, y, title):
    if PLOTLY_AVAILABLE:
        fig = px.bar(df, x=x, y=y, title=title)
        st.plotly_chart(fig, use_container_width=True)
    else:
        chart = alt.Chart(df).mark_bar().encode(x=x, y=y).properties(title=title)
        st.altair_chart(chart, use_container_width=True)

def nobreak_vs(text: str) -> str:
    pattern = r"(\$?\d+(?:\.\d+)?)\s*vs\s*(\$?\d+(?:\.\d+)?)"
    return re.sub(pattern, lambda m: f"{m.group(1)}\u00A0vs\u00A0{m.group(2)}", text)

# Reuse existing app logic


def _bootstrap_env_from_streamlit_secrets():
    try:
        secrets_obj = st.secrets  # triggers load
    except FileNotFoundError:
        return

    for key in [
        "NOTION_API_KEY",
        "VENDORS_DB_ID",
        "PARTS_DB_ID",
        "SCORES_DB_ID",
        "SECRET_KEY",
    ]:
        if key in st.secrets and st.secrets.get(key):
            os.environ[key] = str(st.secrets.get(key))


_bootstrap_env_from_streamlit_secrets()

st.set_page_config(page_title="Vendor Database", layout="wide")

# Top navigation as a horizontal radio (clickable titles)
current_page = st.radio(
    "",
    ["Vendors", "Components", "Kraljic Matrix", "TCO Analysis", "Compliance", "Analytics", "Settings", "About"],
    horizontal=True,
    index=["Vendors", "Components", "Kraljic Matrix", "TCO Analysis", "Compliance", "Analytics", "Settings", "About"].index(
        st.session_state.get("page", "Vendors")
    ),
)
st.session_state["page"] = current_page

# Center main content and inject minimal CSS for score bars and badges
st.markdown(
    """
    <style>
    .block-container {max-width: 1400px; padding-top: 1rem; padding-bottom: 3rem; margin: 0 auto;}
    .score-bar {height: 8px; background:#e5e7eb; border-radius: 6px; overflow: hidden;}
    .score-fill {height: 100%;}
    .fill-excellent {background:#10b981;}
    .fill-good {background:#3b82f6;}
    .fill-fair {background:#f59e0b;}
    .fill-poor {background:#ef4444;}
    .risk-badge {display:inline-block; padding:2px 6px; border-radius:8px; font-size:12px; margin-right:4px;}
    .risk-high {background:#fee2e2; color:#991b1b;}
    .risk-medium {background:#ffedd5; color:#9a3412;}
    .risk-low {background:#e0f2fe; color:#075985;}
    .status-ind {display:inline-flex; align-items:center; gap:6px; font-size:12px;}
    .status-stale {color:#b45309;}
    .status-fresh {color:#047857;}
    .panel {border:1px solid #e5e7eb; border-radius:10px; padding:14px; background:#fff;}
    .summary {font-size:14px;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=300)
def fetch_vendors_and_parts() -> tuple[List[Vendor], Dict[str, List[Part]]]:
    repo = NotionRepository()
    vendors = repo.list_vendors()
    parts_by_vendor: Dict[str, List[Part]] = {}
    for v in vendors:
        parts = repo.list_parts_by_vendor(v.id)
        if parts:
            parts_by_vendor[v.id] = parts
    return vendors, parts_by_vendor


def compute_analyses(
    vendors: List[Vendor],
    parts_by_vendor: Dict[str, List[Part]],
    weights: ScoringWeights,
) -> List[VendorAnalysis]:
    engine = ScoringEngine(weights)
    # Apply runtime threshold overrides from Settings
    try:
        engine.staleness_threshold_days = int(st.session_state.get("risk_staleness_days", engine.staleness_threshold_days))
        engine.capacity_shortfall_threshold = int(st.session_state.get("risk_capacity_high", engine.capacity_shortfall_threshold))
        engine.cost_spike_threshold = float(st.session_state.get("risk_cost_spike_high_pct", 25)) / 100.0
        engine.ocean_delay_high_days = int(st.session_state.get("risk_ocean_high_days", getattr(engine, 'ocean_delay_high_days', 35)))
        engine.air_delay_high_days = int(st.session_state.get("risk_air_high_days", getattr(engine, 'air_delay_high_days', 14)))
    except Exception:
        pass
    return engine.score_vendors(vendors, parts_by_vendor)


def score_fill_class(pct: int) -> str:
    if pct >= 80:
        return "fill-excellent"
    if pct >= 60:
        return "fill-good"
    if pct >= 40:
        return "fill-fair"
    return "fill-poor"


def render_score_bar(p: float) -> str:
    pct = max(0, min(100, int(round(p * 100))))
    return f'<div class="score-bar"><div class="score-fill {score_fill_class(pct)}" style="width:{pct}%"></div></div>'


def render_risk_badges(analysis: VendorAnalysis) -> str:
    if not analysis.risk_flags:
        return ""
    html = []
    for f in analysis.risk_flags:
        sev = f.severity or "low"
        html.append(f'<span class="risk-badge risk-{sev}">{f.type.replace("_", " ")}</span>')
    return "".join(html)


# Sidebar - global filters and weights
with st.sidebar:
    st.title("Vendor Database")
    st.caption("Component Vendor Scoring & Analytics")

    st.subheader("Filters")
    region = st.selectbox("Region", ["", "US", "CN", "KR", "EU", "VN", "MX", "IN"], index=0)
    component_query = st.text_input("Component name contains", value="")
    st.caption("Filters vendors whose parts include components matching this text.")
    sort_display = st.selectbox("Sort by", ["Final Score", "Total Cost", "Total Time", "Vendor Maturity", "Capacity"], index=0)
    sort_map = {
        "Final Score": "final_score",
        "Total Cost": "total_cost",
        "Total Time": "total_time",
        "Vendor Maturity": "reliability",
        "Capacity": "capacity",
    }
    sort_by = sort_map.get(sort_display, "final_score")

    st.subheader("Scoring Weights")
    # Initialize once, then let widgets read/write session_state
    if "w_cost" not in st.session_state:
        st.session_state["w_cost"] = 40
    if "w_time" not in st.session_state:
        st.session_state["w_time"] = 30
    if "w_rel" not in st.session_state:
        st.session_state["w_rel"] = 20
    if "w_cap" not in st.session_state:
        st.session_state["w_cap"] = 10

    cost_w = st.slider("Total Cost", 0, 100, key="w_cost")
    time_w = st.slider("Total Time", 0, 100, key="w_time")
    rel_w = st.slider("Vendor Maturity", 0, 100, key="w_rel")
    cap_w = st.slider("Capacity", 0, 100, key="w_cap")
    total = cost_w + time_w + rel_w + cap_w
    enforce_norm = st.checkbox("Enforce 100% (auto-normalize for scoring)", value=True)

    def _scale_weights():
        vals = [
            int(st.session_state.get("w_cost", 0)),
            int(st.session_state.get("w_time", 0)),
            int(st.session_state.get("w_rel", 0)),
            int(st.session_state.get("w_cap", 0)),
        ]
        s = sum(vals)
        if s <= 0:
            scaled = [40, 30, 20, 10]
        else:
            raw = [v * 100.0 / s for v in vals]
            floors = [int(math.floor(x)) for x in raw]
            remainder = 100 - sum(floors)
            fracs = [(i, raw[i] - floors[i]) for i in range(len(vals))]
            fracs.sort(key=lambda t: t[1], reverse=True)
            for i in range(remainder):
                floors[fracs[i % len(floors)][0]] += 1
            scaled = floors
        st.session_state["w_cost"], st.session_state["w_time"], st.session_state["w_rel"], st.session_state["w_cap"] = scaled
    st.button("Scale sliders to 100%", on_click=_scale_weights)

    # Build weights for scoring (normalized if requested or total is zero)
    if total == 0:
        weights_scoring = ScoringWeights()
    else:
        if enforce_norm or total != 100:
            weights_scoring = ScoringWeights(
                total_cost=cost_w / total,
                total_time=time_w / total,
                reliability=rel_w / total,
                capacity=cap_w / total,
            )
        else:
            weights_scoring = ScoringWeights(
                total_cost=cost_w / 100,
                total_time=time_w / 100,
                reliability=rel_w / 100,
                capacity=cap_w / 100,
            )

    if total == 100 and not enforce_norm:
        st.success("Weights sum to 100%.")
    else:
        st.info("Weights are normalized to 100% for scoring.")

    if st.button("Update Score", type="primary"):
        st.session_state["last_updated"] = True

# Data load
error_container = st.empty()
try:
    vendors, parts_by_vendor = fetch_vendors_and_parts()
except Exception as e:
    error_container.error(
        "Failed to load data from Notion. Ensure secrets are configured (NOTION_API_KEY, VENDORS_DB_ID, PARTS_DB_ID, SCORES_DB_ID).\n" + str(e)
    )
    st.stop()

# Apply filters
if region:
    vendors = [v for v in vendors if v.region.lower() == region.lower()]
if component_query:
    filtered_ids = set()
    q = component_query.lower()
    for vid, parts in parts_by_vendor.items():
        for p in parts:
            if q in p.component_name.lower():
                filtered_ids.add(vid)
    vendors = [v for v in vendors if v.id in filtered_ids]

# Compute analyses with scoring weights
analyses = compute_analyses(vendors, parts_by_vendor, weights_scoring)

# Sorting
if sort_by == "total_cost":
    analyses.sort(key=lambda a: a.avg_landed_cost)
elif sort_by == "total_time":
    analyses.sort(key=lambda a: a.avg_total_time)
elif sort_by == "reliability":
    analyses.sort(key=lambda a: a.current_score.reliability_score, reverse=True)
elif sort_by == "capacity":
    analyses.sort(key=lambda a: a.total_monthly_capacity, reverse=True)
else:
    analyses.sort(key=lambda a: a.current_score.final_score, reverse=True)

if current_page == "Vendors":
    st.header("Vendors")
    # Guides moved to About page
    # Executive summary
    engine_for_summary = ScoringEngine(weights_scoring)
    summary = engine_for_summary.generate_executive_summary(analyses)
    bullets = [b.strip() for b in summary.get("summary", "").split("•") if b.strip()]
    st.subheader("Executive Summary")
    if bullets:
        for b in bullets:
            clean = " ".join(b.replace("\n", " ").split())
            # normalize 'vs' spacing and prevent awkward breaks
            clean = re.sub(r"v\s*s", "vs", clean, flags=re.IGNORECASE)
            clean = nobreak_vs(clean)
            st.markdown(f"- {clean}")
    else:
        st.write("No insights available.")
    st.subheader("Recommendation")
    rec = " ".join(summary.get("recommendation", "").replace("\n", " ").split())
    rec = nobreak_vs(rec)
    st.markdown(rec)

    # KPI metrics row
    if analyses:
        total_vendors = len(analyses)
        high_risk_count = sum(1 for a in analyses if any(f.severity == "high" for f in a.risk_flags))
        avg_score = sum(a.current_score.final_score for a in analyses) / total_vendors
        total_capacity = sum(a.total_monthly_capacity for a in analyses)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Vendors", f"{total_vendors}")
        m2.metric("Operational High Risk Vendors", f"{high_risk_count}")
        m3.metric("Avg Final Score", f"{avg_score*100:.1f}%")
        m4.metric("Total Capacity", f"{total_capacity:,}")

    st.divider()

    # Vendors table using native dataframe with column configs
    if not analyses:
        st.info("No vendors to display with current filters.")
    else:
        df_rows: List[Dict] = []
        for idx, a in enumerate(analyses, start=1):
            # Risk summary counts
            high = sum(1 for f in a.risk_flags if f.severity == "high")
            med = sum(1 for f in a.risk_flags if f.severity == "medium")
            low = sum(1 for f in a.risk_flags if f.severity == "low")
            risks = f"H:{high} M:{med} L:{low}" if (high or med or low) else "None"
            # Composite risk index (0-100)
            risk_index = min(100, high*30 + med*15 + low*5 + (30 if a.vendor.is_stale() else 0) + (10 if a.total_monthly_capacity < 10000 else 0))
            df_rows.append(
                {
                    "Rank": idx,
                    "Vendor": a.vendor.name,
                    "Region": a.vendor.region,
                    # Percentages now numeric for compact width
                    "Final Score (%)": round(a.current_score.final_score * 100, 1),
                    "Cost (%)": round(a.current_score.total_cost_score * 100, 1),
                    "Time (%)": round(a.current_score.total_time_score * 100, 1),
                    "Vendor Maturity (%)": round(a.current_score.reliability_score * 100, 1),
                    "Capacity (%)": round(a.current_score.capacity_score * 100, 1),
                    "Avg. Landed Cost": round(a.avg_landed_cost, 2),
                    "Avg. Total Time (days)": round(a.avg_total_time, 1),
                    "Total Capacity": a.total_monthly_capacity,
                    "Risk Index": risk_index,
                    "Parts": len(a.parts),
                    "Risks": risks,
                    "Status": "Stale" if a.vendor.is_stale() else "Fresh",
                }
            )
        df = pd.DataFrame(df_rows)
        # Add percentile ranks and z-scores for cost/time
        if not df.empty:
            for col in ["Avg. Landed Cost", "Avg. Total Time (days)"]:
                pct_col = f"{col} Pctl"
                z_col = f"{col} Z"
                df[pct_col] = (df[col].rank(pct=True) * 100).round(1)
                if df[col].std(ddof=0) > 0:
                    df[z_col] = ((df[col] - df[col].mean()) / df[col].std(ddof=0)).round(2)
                else:
                    df[z_col] = 0.0
        show_adv = st.checkbox("Show advanced metrics (percentiles, z-scores, risk index)", value=False)
        display_df = df if show_adv else df.drop(columns=[c for c in df.columns if c.endswith(" Pctl") or c.endswith(" Z") or c == "Risk Index"], errors="ignore")
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Final Score (%)": cc.NumberColumn(format="%.1f%%"),
                "Cost (%)": cc.NumberColumn(format="%.1f%%"),
                "Time (%)": cc.NumberColumn(format="%.1f%%"),
                "Vendor Maturity (%)": cc.NumberColumn(format="%.1f%%"),
                "Capacity (%)": cc.NumberColumn(format="%.1f%%"),
                "Avg. Landed Cost": cc.NumberColumn(format="$%.2f"),
                "Avg. Total Time (days)": cc.NumberColumn(format="%.1f"),
                "Total Capacity": cc.NumberColumn(format="%d"),
                "Risk Index": cc.NumberColumn(format="%d"),
            },
            height=420,
        )

    # Vendor Comparison
    if analyses:
        with st.expander("Compare vendors (pillar scores)", expanded=False):
            col_a, col_b = st.columns(2)
            names = [a.vendor.name for a in analyses]
            with col_a:
                v1 = st.selectbox("Vendor A", names, index=0, key="cmp_a")
            with col_b:
                v2 = st.selectbox("Vendor B", names, index=min(1, len(names)-1), key="cmp_b")
            if v1 and v2 and v1 != v2:
                a1 = next(a for a in analyses if a.vendor.name == v1)
                a2 = next(a for a in analyses if a.vendor.name == v2)
                comp_df = pd.DataFrame([
                    {"Pillar": "Cost", "Vendor": v1, "Score": a1.current_score.total_cost_score*100},
                    {"Pillar": "Time", "Vendor": v1, "Score": a1.current_score.total_time_score*100},
                    {"Pillar": "Vendor Maturity", "Vendor": v1, "Score": a1.current_score.reliability_score*100},
                    {"Pillar": "Capacity", "Vendor": v1, "Score": a1.current_score.capacity_score*100},
                    {"Pillar": "Cost", "Vendor": v2, "Score": a2.current_score.total_cost_score*100},
                    {"Pillar": "Time", "Vendor": v2, "Score": a2.current_score.total_time_score*100},
                    {"Pillar": "Vendor Maturity", "Vendor": v2, "Score": a2.current_score.reliability_score*100},
                    {"Pillar": "Capacity", "Vendor": v2, "Score": a2.current_score.capacity_score*100},
                ])
                bar = alt.Chart(comp_df).mark_bar().encode(
                    x=alt.X('Pillar:N', title='Pillar', sort=["Cost","Time","Vendor Maturity","Capacity"]),
                    xOffset='Vendor:N',
                    y=alt.Y('Score:Q', title='Score (%)', scale=alt.Scale(domain=[0,100])),
                    color=alt.Color('Vendor:N'),
                    tooltip=['Vendor','Pillar','Score']
                ).properties(height=260)
                st.altair_chart(bar, use_container_width=True)

    # Vendor Detail panel
    if analyses:
        st.divider()
        st.subheader("Vendor Detail")
        vendor_names = [a.vendor.name for a in analyses]
        selected_name = st.selectbox("Select a vendor", vendor_names)
        selected = next(a for a in analyses if a.vendor.name == selected_name)

        left, right = st.columns([1, 1])
        with left:
            st.markdown("#### Vendor Info")
            st.write(
                {
                    "Region": selected.vendor.region,
                    "Contact": selected.vendor.contact_email,
                    "Last Verified": str(selected.vendor.last_verified) if selected.vendor.last_verified else None,
                    "Stale": selected.vendor.is_stale(),
                }
            )

            st.markdown("#### Scores")
            st.write(
                {
                    "Final": round(selected.current_score.final_score * 100, 1),
                    "Cost": round(selected.current_score.total_cost_score * 100, 1),
                    "Time": round(selected.current_score.total_time_score * 100, 1),
                    "Vendor Maturity": round(selected.current_score.reliability_score * 100, 1),
                    "Capacity": round(selected.current_score.capacity_score * 100, 1),
                }
            )

            st.markdown("#### Risk Flags")
            if selected.risk_flags:
                for f in selected.risk_flags:
                    st.warning(f"{f.severity.upper()}: {f.description}")
            else:
                st.success("No risk flags detected")

        with right:
            st.markdown("#### Components")
            parts_rows = [
                {
                    "Component": p.component_name,
                    "Unit Price": p.unit_price,
                    "Landed Cost": p.total_landed_cost,
                    "Lead (wks)": p.lead_time_weeks,
                    "Transit (days)": p.transit_days,
                    "Mode": p.shipping_mode,
                    "Capacity": p.monthly_capacity,
                }
                for p in selected.parts
            ]
            st.dataframe(parts_rows, use_container_width=True, height=320)
elif current_page == "Components":
    st.header("Components")
    if not st.session_state.get("SHOW_GUIDES", True):
        st.markdown(
            """
            ### What this page shows
            - All components across filtered vendors with cost/time/capacity metrics.
            
            ### How it works
            - Landed Cost = Unit Price + Freight + Tariff; Total Time = Lead×7 + Transit; Capacity = monthly capacity.
            
            ### Why it matters
            - Identifies cost/time hotspots and capacity constraints at part level.
            
            ### Metrics Reference
            - Per part inputs: `component_name`, `vendor`, `odm_destination`, `odm_region`, `unit_price`, `freight_cost`, `tariff_rate_pct`, `lead_time_weeks`, `transit_days`, `shipping_mode`, `monthly_capacity`, `last_verified`
            - Derived per part: `total_landed_cost`, `total_time_days`
            - Filters: `component_name` contains filter narrows parts and vendors.
            """
        )
    # Flatten all parts across the (filtered) vendors
    parts_all: List[Dict] = []
    for v in vendors:
        for p in parts_by_vendor.get(v.id, []):
            # Apply component filter (already applied at vendors, but ensure here)
            if component_query and component_query.lower() not in p.component_name.lower():
                continue
            parts_all.append(
                {
                    "Component": p.component_name,
                    "Vendor": v.name,
                    "Region": v.region,
                    "Unit Price": p.unit_price,
                    "Landed Cost": p.total_landed_cost,
                    "Lead (wks)": p.lead_time_weeks,
                    "Transit (days)": p.transit_days,
                    "Total Time (days)": p.total_time_days,
                    "Mode": p.shipping_mode,
                    "Capacity": p.monthly_capacity,
                }
            )
    if not parts_all:
        st.info("No components match the current filters.")
    else:
        parts_df = pd.DataFrame(parts_all)
        st.dataframe(
            parts_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Unit Price": cc.NumberColumn(format="$%.2f"),
                "Landed Cost": cc.NumberColumn(format="$%.2f"),
                "Lead (wks)": cc.NumberColumn(format="%d"),
                "Transit (days)": cc.NumberColumn(format="%d"),
                "Total Time (days)": cc.NumberColumn(format="%d"),
                "Capacity": cc.NumberColumn(format="%d"),
            },
            height=420,
        )
elif current_page == "Kraljic Matrix":
    st.header("Kraljic Matrix Analysis")
    # Guides moved to About page
    engine = KraljicEngine() if KRALJIC_AVAILABLE else None
    rows = []
    for a in analyses:
        v = a.vendor
        v_parts = parts_by_vendor.get(v.id, [])
        spend = getattr(v, "annual_spend_usd", 0) or 0
        if spend == 0 and v_parts:
            spend = sum((getattr(p, "annual_demand_forecast", 0) or p.monthly_capacity * 12 * 0.5) * p.total_landed_cost for p in v_parts)
        supply_risk = getattr(v, "supply_risk_score", 0) or 0
        if supply_risk == 0:
            # fallback simple risk: longer time and low maturity increase risk
            time_norm = a.avg_total_time / max(1, max(x.avg_total_time for x in analyses))
            maturity_norm = 1 - a.current_score.reliability_score
            supply_risk = min(1.0, 0.6 * time_norm + 0.4 * maturity_norm)
        if engine:
            category = getattr(v, "kraljic_category", None) or engine.categorize_vendor(v, v_parts)
            category_value = category.value if category else "Unknown"
        else:
            # Fallback categorization based on thresholds
            risk_pct = supply_risk * 100
            if spend >= 100000 and risk_pct >= 60:
                category_value = "Strategic"
            elif spend >= 100000 and risk_pct < 60:
                category_value = "Leverage"
            elif spend < 100000 and risk_pct >= 60:
                category_value = "Bottleneck"
            else:
                category_value = "Routine"
        rows.append({
            "Vendor": v.name,
            "Region": v.region,
            "Annual Spend ($)": spend,
            "Supply Risk (%)": supply_risk * 100,
            "Category": category_value,
        })
    if not rows:
        st.info("No vendor data available for Kraljic analysis.")
    else:
        dfk = pd.DataFrame(rows)
        # Summary metrics
        c1, c2, c3, c4 = st.columns(4)
        counts = dfk["Category"].value_counts()
        c1.metric("Strategic", int(counts.get("Strategic", 0)))
        c2.metric("Leverage", int(counts.get("Leverage", 0)))
        c3.metric("Bottleneck", int(counts.get("Bottleneck", 0)))
        c4.metric("Routine", int(counts.get("Routine", 0)))
        st.divider()
        # Scatter plot (Altair fallback)
        chart = alt.Chart(dfk).mark_circle(size=120).encode(
            x=alt.X("Annual Spend ($):Q", title="Annual Spend ($)"),
            y=alt.Y("Supply Risk (%):Q", title="Supply Risk (%)"),
            color=alt.Color("Category:N"),
            tooltip=["Vendor", "Annual Spend ($)", "Supply Risk (%)", "Category"],
        ).properties(height=380, title="Supplier Portfolio (Kraljic)")
        st.altair_chart(chart, use_container_width=True)
        st.dataframe(dfk.sort_values("Annual Spend ($)", ascending=False), use_container_width=True, hide_index=True, height=360)
elif current_page == "TCO Analysis":
    st.header("Total Cost of Ownership (TCO) Analysis")
    # Guides moved to About page
    tco_rows = []
    for a in analyses:
        parts = a.parts
        if not parts:
            continue
        total_tco = 0.0
        for p in parts:
            # 3-year TCO proxy if method not available
            annual_vol = getattr(p, "annual_demand_forecast", 0) or (p.monthly_capacity * 12 * 0.5)
            total_tco += annual_vol * p.total_landed_cost * 3
        tco_rows.append({
            "Vendor": a.vendor.name,
            "Region": a.vendor.region,
            "Parts": len(parts),
            "Total 3-Year TCO": total_tco,
            "Avg TCO per Part": total_tco / len(parts),
        })
    if not tco_rows:
        st.info("No data available for TCO analysis.")
    else:
        df_tco = pd.DataFrame(tco_rows)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Portfolio TCO", f"${df_tco['Total 3-Year TCO'].sum():,.0f}")
        col2.metric("Avg TCO/Vendor", f"${df_tco['Total 3-Year TCO'].mean():,.0f}")
        col3.metric("Vendors", len(df_tco))
        col4.metric("Avg Parts/Vendor", f"{df_tco['Parts'].mean():.1f}")
        st.divider()
        safe_plotly_bar(df_tco.sort_values('Total 3-Year TCO', ascending=True), x='Total 3-Year TCO', y='Vendor', title='3-Year TCO by Vendor')
        st.dataframe(
            df_tco.sort_values('Total 3-Year TCO', ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Total 3-Year TCO": cc.NumberColumn(format="$%.0f"),
                "Avg TCO per Part": cc.NumberColumn(format="$%.0f"),
            },
            height=400,
        )
elif current_page == "Compliance":
    st.header("Compliance & Certifications")
    # Guides moved to About page
    comp_rows = []
    for a in analyses:
        v = a.vendor
        parts = a.parts
        uflpa = getattr(v, "uflpa_compliant", False)
        conflict = getattr(v, "conflict_minerals_compliant", False)
        rohs = any(getattr(p, "rohs_compliant", False) for p in parts)
        reach = any(getattr(p, "reach_compliant", False) for p in parts)
        last_audit = getattr(v, "last_audit_date", None)
        certs = len(getattr(v, "iso_certifications", []) or [])
        score = (sum([uflpa, conflict, rohs, reach, bool(last_audit)]) / 5) * 100
        risk = "Low" if score >= 80 else ("Medium" if score >= 60 else "High")
        comp_rows.append({
            "Vendor": v.name,
            "Region": v.region,
            "Compliance Score": score,
            "Risk Level": risk,
            "UFLPA": "✅" if uflpa else "❌",
            "Conflict Minerals": "✅" if conflict else "❌",
            "RoHS": "✅" if rohs else "❌",
            "REACH": "✅" if reach else "❌",
            "Last Audit": str(last_audit) if last_audit else "Never",
            "Certifications": certs,
        })
    if not comp_rows:
        st.info("No compliance data available.")
    else:
        dfc = pd.DataFrame(comp_rows)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Avg Compliance", f"{dfc['Compliance Score'].mean():.1f}%")
        c2.metric("Compliance High Risk Vendors", int((dfc['Risk Level'] == 'High').sum()))
        c3.metric("Medium Risk Vendors", int((dfc['Risk Level'] == 'Medium').sum()))
        c4.metric("Low Risk Vendors", int((dfc['Risk Level'] == 'Low').sum()))
        st.divider()
        st.dataframe(
            dfc,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Compliance Score": cc.NumberColumn(format="%.1f%%"),
                "Certifications": cc.NumberColumn(format="%d"),
            },
            height=420,
        )
elif current_page == "Analytics":
    st.header("Analytics")
    # Guides moved to About page
    # Select vendors and metric to plot in trend
    all_names = [a.vendor.name for a in analyses]
    selected_names = st.multiselect("Vendors to plot", options=all_names, default=all_names)
    metric_display = st.selectbox("Metric to plot", ["Final Score", "Cost", "Time", "Vendor Maturity", "Capacity"], index=0)
    metric_map = {
        "Final Score": (lambda a: a.current_score.final_score, "Final Score (%)"),
        "Cost": (lambda a: a.current_score.total_cost_score, "Cost Score (%)"),
        "Time": (lambda a: a.current_score.total_time_score, "Time Score (%)"),
        "Vendor Maturity": (lambda a: a.current_score.reliability_score, "Vendor Maturity (%)"),
        "Capacity": (lambda a: a.current_score.capacity_score, "Capacity Score (%)"),
    }
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    chart_data = []
    base_fn, y_label = metric_map.get(metric_display, (lambda a: a.current_score.final_score, "Final Score (%)"))
    for a in analyses:
        if a.vendor.name not in selected_names:
            continue
        base = base_fn(a)
        for i, m in enumerate(months):
            variation = 0.02 * (i - 2.5)
            score = max(0.1, min(0.95, base + variation))
            chart_data.append({"Vendor": a.vendor.name, "Month": m, y_label: score * 100})

    c = (
        alt.Chart(alt.Data(values=chart_data))
        .mark_line(point=True)
        .encode(x="Month:N", y=alt.Y(f"{y_label}:Q", scale=alt.Scale(domain=[0, 100])), color="Vendor:N")
        .properties(height=320, title=f"{metric_display} Trend")
    )
    st.altair_chart(c, use_container_width=True)

    # Cost vs Time scatter with capacity size and maturity color
    if analyses:
        scat_rows = []
        for a in analyses:
            scat_rows.append({
                "Vendor": a.vendor.name,
                "Avg Cost": a.avg_landed_cost,
                "Avg Time": a.avg_total_time,
                "Capacity": a.total_monthly_capacity,
                "Maturity": a.current_score.reliability_score*100,
            })
        scat_df = pd.DataFrame(scat_rows)
        scat = alt.Chart(scat_df).mark_circle().encode(
            x=alt.X('Avg Cost:Q', title='Avg Landed Cost ($)'),
            y=alt.Y('Avg Time:Q', title='Avg Total Time (days)'),
            size=alt.Size('Capacity:Q', title='Capacity'),
            color=alt.Color('Maturity:Q', title='Vendor Maturity (%)', scale=alt.Scale(scheme='blues')),
            tooltip=['Vendor','Avg Cost','Avg Time','Capacity','Maturity']
        ).properties(height=360, title='Cost vs Time (bubble = capacity, color = maturity)')
        st.altair_chart(scat, use_container_width=True)

elif current_page == "Settings":
    st.header("Settings")
    # Guides moved to About page

    st.divider()
    st.subheader("Kraljic Settings")
    c1, c2, c3 = st.columns(3)
    spend_threshold = c1.number_input("Spend threshold ($)", min_value=0, value=100000, step=10000)
    risk_threshold_pct = c2.slider("Risk threshold (%)", 0, 100, 60, step=5)
    utilization_factor = c3.slider("Utilization factor (capacity%)", 0, 100, 50, step=5)
    percentile_split = st.checkbox("Use percentile split (median) instead of fixed thresholds", value=False)

    st.divider()
    st.subheader("Risk Thresholds")
    c1, c2 = st.columns(2)
    staleness_days = c1.slider("Staleness flag at ≥ days", 30, 365, 120, step=10)
    capacity_high = c2.number_input("High risk if capacity <", min_value=0, value=2000, step=500)
    c3, c4 = st.columns(2)
    ocean_high = c3.number_input("Ocean high-risk if transit days >", min_value=0, value=35, step=1)
    air_high = c4.number_input("Air high-risk if transit days >", min_value=0, value=14, step=1)
    cost_spike_high = st.slider("Cost spike high if MoM > %", 0, 100, 25, step=1)

    st.divider()
    st.subheader("Normalization")
    norm_method = st.radio("Normalization method", ["Min-Max", "Z-Score"], index=0, horizontal=True)

    # Persist in session for use elsewhere
    st.session_state["kraljic_spend_threshold"] = spend_threshold
    st.session_state["kraljic_risk_threshold_pct"] = risk_threshold_pct
    st.session_state["kraljic_utilization_pct"] = utilization_factor
    st.session_state["kraljic_percentile_split"] = percentile_split
    st.session_state["risk_staleness_days"] = staleness_days
    st.session_state["risk_capacity_high"] = capacity_high
    st.session_state["risk_ocean_high_days"] = ocean_high
    st.session_state["risk_air_high_days"] = air_high
    st.session_state["risk_cost_spike_high_pct"] = cost_spike_high
    st.session_state["norm_method"] = norm_method

    st.divider()
    st.subheader("Save / Export Scores")
    dest = st.radio("Destination", ["Notion Scores DB", "CSV", "XLSX"], index=0, horizontal=True)
    filename = st.text_input("Filename (for CSV/XLSX)", value="vendor_scores")
    save_btn = st.button("Save Scores", type="primary")

    if save_btn:
        # Recompute scores with current weights
        vendors, parts_by_vendor = fetch_vendors_and_parts()
        weights_scoring = ScoringWeights(
            total_cost=st.session_state.get("weights_total_cost", 0.4),
            total_time=st.session_state.get("weights_total_time", 0.3),
            reliability=st.session_state.get("weights_reliability", 0.2),
            capacity=st.session_state.get("weights_capacity", 0.1),
        )
        analyses = compute_analyses(vendors, parts_by_vendor, weights_scoring)
        # Build dataframe of scores
        rows = []
        for a in analyses:
            rows.append({
                "Vendor ID": a.vendor.id,
                "Vendor": a.vendor.name,
                "Total Cost Score": round(a.current_score.total_cost_score, 4),
                "Total Time Score": round(a.current_score.total_time_score, 4),
                "Reliability Score": round(a.current_score.reliability_score, 4),
                "Capacity Score": round(a.current_score.capacity_score, 4),
                "Final Score": round(a.current_score.final_score, 4),
            })
        df_scores = pd.DataFrame(rows)

        if dest == "Notion Scores DB":
            try:
                repo = NotionRepository()
                saved = 0
                from datetime import datetime
                snapnow = datetime.now()
                for a in analyses:
                    vs = a.current_score
                    # ensure metadata fields are populated
                    vs.weights = {
                        "total_cost": weights_scoring.total_cost,
                        "total_time": weights_scoring.total_time,
                        "reliability": weights_scoring.reliability,
                        "capacity": weights_scoring.capacity,
                    }
                    vs.inputs = {
                        "avg_landed_cost": a.avg_landed_cost,
                        "avg_total_time": a.avg_total_time,
                        "total_monthly_capacity": a.total_monthly_capacity,
                    }
                    repo.create_vendor_score(a.vendor.id, vs, vendor_name=a.vendor.name, snapshot_dt=snapnow)
                    saved += 1
                st.success(f"Saved {saved} score snapshots to Notion Scores DB")
            except Exception as e:
                st.error(f"Failed to save to Notion: {e}")
        elif dest == "CSV":
            out = df_scores.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", out, file_name=f"{filename}.csv", mime="text/csv")
        else:
            try:
                from io import BytesIO
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                    df_scores.to_excel(writer, index=False, sheet_name="Scores")
                st.download_button("Download XLSX", buffer.getvalue(), file_name=f"{filename}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception as e:
                st.error(f"Failed to generate XLSX: {e}") 

elif current_page == "About":
    st.header("About")
    st.markdown("Centralized methodology and reference for all pages.")

    tabs = st.tabs([
        "Scoring & Weights",
        "Risk & Alerts",
        "Kraljic Matrix",
        "Components & Data",
        "TCO Methodology",
        "Compliance",
        "Analytics",
        "Settings & Export",
    ])

    with tabs[0]:
        st.subheader("Scoring pillars, weights, and formulas")
        st.markdown(
            """
            #### Final score
            `Final Score = (Cost Score × Cost Weight) + (Time Score × Time Weight) + (Vendor Maturity Score × Maturity Weight) + (Capacity Score × Capacity Weight)`

            - Default weights: Cost 40%, Time 30%, Vendor Maturity 20%, Capacity 10% (Settings can change; weights normalize to 100%).
            - Scores are 0–100% in UI (internally 0–1).
            - Normalization: winsorize outliers then min‑max scale across the vendor portfolio (lower is better for cost/time; higher is better for maturity/capacity).

            #### Pillars and inputs
            - **Total Cost Score (lower is better)**
              - Input: average landed cost across vendor parts.
              - Landed cost per part: `unit_price + freight_cost + unit_price × (tariff_rate_pct/100)`
              - Scaled with min‑max (inverted) across all vendors.
            - **Total Time Score (lower is better)**
              - Input: average total time across vendor parts.
              - Total time per part: `lead_time_weeks × 7 + transit_days`
              - Scaled with min‑max (inverted).
            - **Vendor Maturity Score (higher is better)**
              - Enhanced mode (preferred): uses comprehensive maturity provided in data (`Vendor Maturity Score`).
              - Proxy mode (fallback): based on region reputation, geopolitics alignment, data freshness, shipping risk.
              - Enhanced subcomponents (used for transparency and/or internal computation):
                - Operational Excellence (35%): OTIF%, Lead‑Time Consistency, Quality Score
                - Financial Maturity (25%): Financial Stability, Debt Management
                - Innovation & Technology (20%): Digital Transformation, TRL, Patent Strength
                - Business Maturity (15%): Company Age factor, Company Size factor
                - Partnership & Communication (5%): Communication Quality, Continuous Improvement
            - **Capacity Score (higher is better)**
              - Input: total monthly capacity aggregated for vendor parts.
              - Scaled with min‑max.

            #### Sub-metric formulas
            - Quality Score: `1 − min(PPM_defects/1000, 1)`
            - Debt Management: `min(1, max(0, (4 − debt_to_equity)/4))`
            - Company Age Factor: `min(1, age_years/25)`
            """
        )

    with tabs[1]:
        st.subheader("Risk flags and thresholds")
        st.markdown(
            """
            - **Compliance (high priority):**
              - UFLPA non‑compliance → High
              - Conflict minerals non‑compliance → High
              - Audit status: None (Medium), >18 months (Low), >2 years (Medium), >3 years (High)
              - ISO certification deficiency by size (Enterprise 5+, Large 4+, Medium 2+, Small 1+): 0 → Medium; below expected (>0) → Low
            - **Operational:**
              - Data staleness: Medium 120–180 days, High >180 days
              - Capacity: High <2K units/month, Medium <5K units/month
              - Low maturity: High <25%, Medium <40%
            - **Supply chain:**
              - Delays: Ocean >21 days (High >35 days); Air >10 days (High >14 days)
              - Cost spikes: High >25% MoM, Medium >15% MoM
              - Part compliance: RoHS High <80% (Medium <90%); REACH High <70% (Medium <80%)

            Notes: thresholds are adjustable in Settings for staleness, capacity, delays, and cost spikes; flags are additive and visible per vendor.
            """
        )

    with tabs[2]:
        st.subheader("Kraljic Matrix")
        st.markdown(
            """
            - **Axes:** Annual Spend (impact on profit) vs Supply Risk.
            - **Thresholds (fallback mode):** Spend ≥ $100k; Risk ≥ 60% (both configurable). 4 quadrants:
              - Strategic (high spend, high risk)
              - Leverage (high spend, low risk)
              - Bottleneck (low spend, high risk)
              - Routine (low spend, low risk)
            - **Risk proxy (fallback):** `min(1, 0.6 × time_norm + 0.4 × (1 − maturity))` when explicit risk not available.
            - **Strategies:** Strategic: partner/dual source; Leverage: competition/volume; Bottleneck: continuity/safety stock; Routine: streamline/automate.
            """
        )

    with tabs[3]:
        st.subheader("Components & data inputs")
        st.markdown(
            """
            - Per part inputs: `component_name`, `vendor`, `odm_destination`, `odm_region`, `unit_price`, `freight_cost`, `tariff_rate_pct`, `lead_time_weeks`, `transit_days`, `shipping_mode`, `monthly_capacity`, `last_verified`.
            - Derived per part: `total_landed_cost`, `total_time_days`.
            - Vendor‑level aggregates: average landed cost, average total time, total monthly capacity; maturity data when available.
            """
        )

    with tabs[4]:
        st.subheader("TCO methodology")
        st.markdown(
            """
            - 3‑Year TCO (prototype): `Σ(annual_volume × total_landed_cost × 3)` across vendor parts.
            - Annual volume uses forecast when present; else a utilization factor of capacity (see Settings).
            - Outputs: total portfolio TCO, average per vendor; sortable/exportable table.
            """
        )

    with tabs[5]:
        st.subheader("Compliance scoring")
        st.markdown(
            """
            - **Compliance Score:** 5 equally weighted checks (UFLPA, Conflict Minerals, RoHS, REACH, Audit presence); score = (# passed ÷ 5) × 100.
            - **Risk levels:** High <60%, Medium 60–79%, Low ≥80%.
            - **Part‑level:** RoHS/REACH flags roll up to vendor view; thresholds as listed in Risk flags.
            """
        )

    with tabs[6]:
        st.subheader("Settings, normalization, and export")
        st.markdown(
            """
            - **Weights & normalization:** adjust weights (min‑max normalized). Z‑score option is planned placeholder.
            - **Kraljic thresholds:** spend, risk, utilization factor.
            - **Risk thresholds:** staleness days, capacity cutoffs, ocean/air delay thresholds, cost spike %.
            - **Save/Export:**
              - Notion: one snapshot per vendor per save; Title "{Vendor} – {YYYY‑MM‑DD HH:MM:SS}"; Snapshot (date‑time).
              - CSV/XLSX: immediate download of current score table.
            - **Notion Scores DB schema:**
              - Title (any name) – auto‑filled; Vendor (Relation to Vendors DB)
              - Total Cost/Time/Vendor Maturity/Capacity/Final Score: Number (Percent)
              - Snapshot: Date (time enabled); Weights JSON, Inputs JSON: Rich text
            """
        ) 