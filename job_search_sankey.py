"""
Sean Kelly                                                              
October 1, 2026                                                                                                        
Job Search Dashboard                                     
This file creates a dashboard in Streamlit to show job search stats and visuals.    
"""


from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


DATA_FILE = Path(__file__).parent / "applications.csv"

REQUIRED_COLUMNS = {
    "sector",
    "referral_status",
    "furthest_stage",
    "final_outcome",
}

REFERRAL_ORDER = ["Referred", "Not referred"]
STAGE_ORDER = ["Applied", "Questionnaire", "Job Task", "Interviews", "Offer"]
OUTCOME_ORDER = [
    "Rejected",
    "Canceled",
    "Withdrew",
    "Proposal",
    "Part-time",
    "Consultancy",
    "Full-time",
]


@st.cache_data
def load_applications(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            "Missing required column(s): " + ", ".join(sorted(missing))
        )

    for column in REQUIRED_COLUMNS:
        df[column] = df[column].astype("string").str.strip()

        if df[column].isna().any() or df[column].eq("").any():
            raise ValueError(f"Column '{column}' contains a blank value.")

    allowed = {
        "referral_status": REFERRAL_ORDER,
        "furthest_stage": STAGE_ORDER,
        "final_outcome": OUTCOME_ORDER,
    }

    for column, valid_values in allowed.items():
        unexpected = sorted(set(df[column]) - set(valid_values))
        if unexpected:
            raise ValueError(
                f"Unexpected value(s) in '{column}': {unexpected}. "
                f"Allowed values: {valid_values}"
            )

    if "application_id" in df.columns:
        if df["application_id"].isna().any():
            raise ValueError("'application_id' contains a blank value.")
        if df["application_id"].duplicated().any():
            raise ValueError(
                "'application_id' must be unique: use one row per application."
            )

    return df


def make_links(applications: pd.DataFrame) -> pd.DataFrame:
    first = (
        applications
        .groupby(
            ["referral_status", "furthest_stage"],
            dropna=False,
        )
        .size()
        .reset_index(name="value")
        .rename(
            columns={
                "referral_status": "source",
                "furthest_stage": "target",
            }
        )
    )

    first["source"] = "referral:" + first["source"].astype(str)
    first["target"] = "stage:" + first["target"].astype(str)

    second = (
        applications
        .groupby(
            ["furthest_stage", "final_outcome"],
            dropna=False,
        )
        .size()
        .reset_index(name="value")
        .rename(
            columns={
                "furthest_stage": "source",
                "final_outcome": "target",
            }
        )
    )

    second["source"] = "stage:" + second["source"].astype(str)
    second["target"] = "outcome:" + second["target"].astype(str)

    return pd.concat([first, second], ignore_index=True)


def check_links(links: pd.DataFrame, application_count: int) -> None:
    first_total = links.loc[
        links["source"].str.startswith("referral:"), "value"
    ].sum()

    second_total = links.loc[
        links["source"].str.startswith("stage:"), "value"
    ].sum()

    if first_total != application_count or second_total != application_count:
        raise ValueError(
            "Link totals do not equal the number of filtered applications."
        )

    for stage in STAGE_ORDER:
        key = f"stage:{stage}"

        incoming = links.loc[links["target"] == key, "value"].sum()
        outgoing = links.loc[links["source"] == key, "value"].sum()

        if incoming != outgoing:
            raise ValueError(
                f"Stage '{stage}' is unbalanced: "
                f"{incoming} incoming, {outgoing} outgoing."
            )


def make_figure(links: pd.DataFrame) -> go.Figure:
    preferred_keys = (
        [f"referral:{x}" for x in REFERRAL_ORDER]
        + [f"stage:{x}" for x in STAGE_ORDER]
        + [f"outcome:{x}" for x in OUTCOME_ORDER]
    )

    active_keys = set(links["source"]) | set(links["target"])
    node_keys = [key for key in preferred_keys if key in active_keys]
    node_index = {
        key: index for index, key in enumerate(node_keys)
    }

    labels = []
    colors = []

    for key in node_keys:
        label = key.split(":", 1)[1]

        if key == "stage:Offer":
            label = "Offer"

        labels.append(label)

        if key.startswith("referral:"):
            colors.append("#00B5E2")
        elif key.startswith("stage:"):
            colors.append("#63666A")
        else:
            colors.append("#041E42")

    link_colors = [
        "rgb(95, 163, 67)"
        if source.startswith("referral:")
        else "rgb(248, 224, 142)"
        for source in links["source"]
    ]

    fig = go.Figure(
        go.Sankey(
            arrangement="snap",
            node=dict(
                label=labels,
                color=colors,
                pad=20,
                thickness=20,
                line=dict(color="rgba(40,40,40,0.35)", width=0.5),
                hovertemplate=(
                    "%{label}<br>%{value} applications<extra></extra>"
                ),
            ),
            link=dict(
                source=links["source"].map(node_index).tolist(),
                target=links["target"].map(node_index).tolist(),
                value=links["value"].tolist(),
                color=link_colors,
                hovertemplate=(
                    "%{source.label} → %{target.label}"
                    "<br>%{value} applications<extra></extra>"
                ),
            ),
        )
    )

    fig.update_layout(
        title="Referral status → furthest stage → outcome",
        height=650,
        font=dict(size=13),
        margin=dict(l=20, r=20, t=65, b=20),
    )

    return fig


st.set_page_config(
    page_title="Job Application Dashboard",
    layout="wide",
)

st.title("Job Application Dashboard")

if not DATA_FILE.exists():
    st.error(
        "Cannot find applications.csv. Place your one-row-per-application "
        "CSV in the same folder as app.py."
    )
    st.stop()

try:
    applications = load_applications(DATA_FILE)
except (ValueError, pd.errors.ParserError) as exc:
    st.error(f"Could not load applications.csv: {exc}")
    st.stop()

sector_options = sorted(applications["sector"].unique().tolist())

selected_sectors = st.multiselect(
    "Filter by sector",
    options=sector_options,
    default=sector_options,
)

if not selected_sectors:
    st.info("Select at least one sector to display the chart and table.")
    st.stop()

filtered = applications.loc[
    applications["sector"].isin(selected_sectors)
].copy()

links = make_links(filtered)

try:
    check_links(links, len(filtered))
except ValueError as exc:
    st.error(str(exc))
    st.stop()

st.metric("Applications shown", len(filtered))

sankey_tab, table_tab = st.tabs(
    ["Sankey", "Application table"]
)

with sankey_tab:
    st.plotly_chart(
        make_figure(links),
        use_container_width=True,
    )
    st.caption(
        "Each application contributes one link from referral status to "
        "furthest stage and one link from furthest stage to outcome."
    )

with table_tab:
    table_columns = [
        "application_id",
        "sector",
        "referral_status",
        "furthest_stage",
        "final_outcome",
    ]

    # Include only columns that exist in your CSV.
    table_columns = [
        column for column in table_columns
        if column in filtered.columns
    ]

    st.dataframe(
        filtered[table_columns],
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("View Sankey link totals"):
        st.dataframe(
            links,
            use_container_width=True,
            hide_index=True,
        )