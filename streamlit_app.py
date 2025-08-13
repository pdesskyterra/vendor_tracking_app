import os
from typing import Dict, List

import streamlit as st
import altair as alt
import pandas as pd
import re
import math
from streamlit import column_config as cc

def nobreak_vs(text: str) -> str:
    pattern = r"(\$?\d+(?:\.\d+)?)\s*vs\s*(\$?\d+(?:\.\d+)?)"
    return re.sub(pattern, lambda m: f"{m.group(1)}\u00A0vs\u00A0{m.group(2)}", text)

# Reuse existing app logic
from app.notion_repo import NotionRepository, NotionAPIError
from app.scoring import ScoringEngine
from app.models import Vendor, Part, VendorAnalysis, ScoringWeights


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

st.set_page_config(page_title="Synseer Vendor Database", layout="wide")

# Top navigation as a horizontal radio (clickable titles)
current_page = st.radio(
    "",
    ["Vendors", "Components", "Analytics", "Settings"],
    horizontal=True,
    index=["Vendors", "Components", "Analytics", "Settings"].index(
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
    st.title("Synseer Vendor DB")
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
        m2.metric("High Risk Vendors", f"{high_risk_count}")
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
                    "Parts": len(a.parts),
                    "Risks": risks,
                    "Status": "Stale" if a.vendor.is_stale() else "Fresh",
                }
            )
        df = pd.DataFrame(df_rows)
        st.dataframe(
            df,
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
            },
            height=420,
        )

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
elif current_page == "Analytics":
    st.header("Analytics")
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    chart_data = []
    for a in analyses[:3]:
        base = a.current_score.final_score
        for i, m in enumerate(months):
            variation = 0.02 * (i - 2.5)
            score = max(0.1, min(0.95, base + variation))
            chart_data.append({"Vendor": a.vendor.name, "Month": m, "Final Score %": score * 100})

    c = (
        alt.Chart(alt.Data(values=chart_data))
        .mark_line(point=True)
        .encode(x="Month:N", y=alt.Y("Final Score %:Q", scale=alt.Scale(domain=[0, 100])), color="Vendor:N")
        .properties(height=320, title="Vendor Final Score Trend (Mock)")
    )
    st.altair_chart(c, use_container_width=True)
elif current_page == "Settings":
    st.header("Settings")
    st.subheader("Scoring Weights")
    st.write("Adjust sliders in the sidebar. The model auto-recomputes. Use 'Update Score' to note a refresh.")
    if st.session_state.get("last_updated"):
        st.info("Scores updated just now.") 