"""
MarketPulse dashboard.

Reads directly from the dbt marts in Supabase (dbt_dev schema):
  - fct_cpi_trend            -> macro inflation trend
  - fct_bank_rates_latest    -> current interest rates by bank/product
  - fct_bank_products_latest -> product listing/category context

Run locally with: streamlit run streamlit_app/app.py
Deploy on Streamlit Community Cloud (free) — see README for setup.
"""

import os
import pandas as pd
import altair as alt
import streamlit as st
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="MarketPulse", page_icon="📊", layout="wide")

# Consistent colour per bank across every chart in the app — assigned
# once, here, so a bank's colour never changes between tabs or reruns.
BANK_COLORS = {
    "ANZ": "#00A9E0",
    "Westpac": "#DA1710",
    "CBA": "#FFCC00",
    "Suncorp": "#F58220",
}

# Below this many banks, a comparison chart isn't really a "comparison" —
# it's one or two bars with nothing to compare against. Categories under
# this threshold are hidden by default (with an option to show them anyway).
MIN_BANKS_FOR_COMPARISON = 3


@st.cache_resource
def get_engine():
    """Cached across the whole app session. Checks the local .env value
    FIRST and only touches st.secrets if that's empty — st.secrets
    renders its own "No secrets found" warning banner the moment it's
    accessed at all when no secrets.toml exists, regardless of whether
    the resulting exception is caught in Python, so the local-dev path
    needs to avoid touching it entirely rather than just catching errors.
    """
    db_url = os.environ.get("DATABASE_URL")

    if not db_url:
        try:
            db_url = st.secrets.get("DATABASE_URL")
        except Exception:
            pass

    if not db_url:
        st.error(
            "DATABASE_URL not found. For local development, add it to a .env "
            "file in the project root. For a deployed app, set it in the "
            "Streamlit Cloud app's Secrets settings."
        )
        st.stop()

    return create_engine(db_url)


@st.cache_data(ttl=600)
def load_cpi_trend() -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(
            text("select * from dbt_dev.fct_cpi_trend order by time_period"), conn
        )


@st.cache_data(ttl=600)
def load_bank_rates() -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text("select * from dbt_dev.fct_bank_rates_latest"), conn)


@st.cache_data(ttl=600)
def load_bank_products() -> pd.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        return pd.read_sql(text("select * from dbt_dev.fct_bank_products_latest"), conn)


def bank_bar_chart(data: pd.DataFrame, value_col: str, title: str) -> alt.Chart:
    """A bar chart with a FIXED colour per bank, consistent across the
    whole app, using Altair's explicit domain/range mapping rather than
    letting each chart pick its own colours independently.
    """
    return (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X("bank:N", title="Bank", sort="-y"),
            y=alt.Y(f"{value_col}:Q", title=title),
            color=alt.Color(
                "bank:N",
                scale=alt.Scale(
                    domain=list(BANK_COLORS.keys()), range=list(BANK_COLORS.values())
                ),
                legend=None,
            ),
            tooltip=["bank", alt.Tooltip(f"{value_col}:Q", format=".2f")],
        )
        .properties(height=320)
    )


def generate_rate_insight(
    filtered: pd.DataFrame, rate_type: str, component: str
) -> str:
    """Auto-generate a one-line insight comparing the best and worst bank
    for the current filter selection, rather than just showing a bar
    chart and leaving the comparison to the reader.

    "Best" depends on direction: for LENDING, the lowest rate is best
    (cheapest to borrow); for DEPOSIT, the highest rate is best (more
    interest earned). Getting this backwards would produce a factually
    wrong sentence, so the two cases are handled explicitly.
    """
    by_bank = filtered.groupby("bank")["rate_pct"].mean().sort_values()
    if len(by_bank) < 2:
        return ""

    if component == "LENDING":
        best_bank, best_rate = by_bank.index[0], by_bank.iloc[0]
        worst_bank, worst_rate = by_bank.index[-1], by_bank.iloc[-1]
        better_word, verb = "lowest", "charges"
    else:
        best_bank, best_rate = by_bank.index[-1], by_bank.iloc[-1]
        worst_bank, worst_rate = by_bank.index[0], by_bank.iloc[0]
        better_word, verb = "highest", "pays"

    gap = abs(best_rate - worst_rate)

    return (
        f"**{best_bank}** has the {better_word} average {rate_type.lower()} rate "
        f"at **{best_rate:.2f}%**, {gap:.2f} points ahead of "
        f"**{worst_bank}**, which {verb} **{worst_rate:.2f}%**."
    )


def build_leaderboard(
    rates_df: pd.DataFrame, min_banks: int = MIN_BANKS_FOR_COMPARISON
):
    """For every rate category with at least min_banks reporting, find
    the winning bank (lowest rate for LENDING, highest for DEPOSIT) and
    the margin over the runner-up. Returns a DataFrame with one row per
    category: component, rate_type, winner, winner_rate, runner_up,
    runner_up_rate, margin, banks_compared.

    This is the core logic behind the Key Insights tab — rather than
    just showing charts, it directly answers "who's winning, and by how
    much" for every category with enough data to make the comparison
    meaningful.
    """
    rows = []
    working = rates_df.copy()
    working["rate_pct"] = working["rate"] * 100

    for component, group in working.groupby("rate_component"):
        counts = group.groupby("rate_type")["bank"].nunique()
        covered = counts[counts >= min_banks].index

        for rate_type in covered:
            by_bank = (
                group[group["rate_type"] == rate_type]
                .groupby("bank")["rate_pct"]
                .mean()
                .sort_values()
            )

            if component == "LENDING":
                winner, winner_rate = by_bank.index[0], by_bank.iloc[0]
                runner_up, runner_up_rate = by_bank.index[1], by_bank.iloc[1]
            else:
                winner, winner_rate = by_bank.index[-1], by_bank.iloc[-1]
                runner_up, runner_up_rate = by_bank.index[-2], by_bank.iloc[-2]

            rows.append(
                {
                    "component": component,
                    "rate_type": rate_type,
                    "winner": winner,
                    "winner_rate": winner_rate,
                    "runner_up": runner_up,
                    "runner_up_rate": runner_up_rate,
                    "margin": abs(winner_rate - runner_up_rate),
                    "banks_compared": len(by_bank),
                }
            )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("📊 MarketPulse")
st.caption(
    "Australian inflation trends and live bank product rates, pulled from the "
    "ABS Data API and banks' public CDR Open Banking APIs. "
    "Personal portfolio project — not financial advice."
)

tab_overview, tab_insights, tab_rates, tab_products, tab_cpi = st.tabs(
    ["Overview", "Key Insights", "Rate Comparison", "Product Browser", "CPI Trend"]
)

# ---------------------------------------------------------------------------
# Overview tab
# ---------------------------------------------------------------------------
with tab_overview:
    cpi_df = load_cpi_trend()
    rates_df = load_bank_rates()

    col1, col2, col3 = st.columns(3)

    if not cpi_df.empty:
        latest_cpi = cpi_df.iloc[-1]
        col1.metric(
            "Latest CPI (YoY)",
            f"{latest_cpi['cpi_pct_change_yoy']:.1f}%",
            delta=(
                f"{latest_cpi['month_over_month_shift']:.1f} pts"
                if pd.notna(latest_cpi["month_over_month_shift"])
                else None
            ),
        )
    else:
        col1.metric("Latest CPI (YoY)", "No data")

    avg_lending, avg_deposit = None, None
    if not rates_df.empty:
        avg_lending = rates_df[rates_df["rate_component"] == "LENDING"]["rate"].mean()
        avg_deposit = rates_df[rates_df["rate_component"] == "DEPOSIT"]["rate"].mean()
        col2.metric(
            "Avg lending rate",
            f"{avg_lending * 100:.2f}%" if pd.notna(avg_lending) else "No data",
        )
        col3.metric(
            "Avg deposit rate",
            f"{avg_deposit * 100:.2f}%" if pd.notna(avg_deposit) else "No data",
        )

    st.divider()

    if not cpi_df.empty and pd.notna(avg_lending):
        latest_shift = latest_cpi["month_over_month_shift"]
        direction = (
            "rising" if pd.notna(latest_shift) and latest_shift > 0 else "easing"
        )
        st.markdown(
            f"**Insight:** headline CPI is currently {direction} "
            f"(latest reading {latest_cpi['cpi_pct_change_yoy']:.1f}% year-on-year), "
            f"while the average advertised lending rate across tracked banks sits at "
            f"**{avg_lending * 100:.2f}%** — a spread of "
            f"**{(avg_lending * 100) - latest_cpi['cpi_pct_change_yoy']:.1f} points** "
            "above current inflation."
        )

    st.subheader("CPI trend")
    if not cpi_df.empty:
        st.line_chart(
            cpi_df.set_index("time_period")[["cpi_pct_change_yoy"]],
            height=320,
        )
    st.caption(
        "Headline CPI (year-on-year % change), Australian Bureau of Statistics. "
        "See the Rate Comparison tab for how individual banks currently price "
        "against this backdrop."
    )

# ---------------------------------------------------------------------------
# Key Insights tab
# ---------------------------------------------------------------------------
with tab_insights:
    rates_df = load_bank_rates()

    if rates_df.empty:
        st.warning("No rate data available.")
    else:
        leaderboard = build_leaderboard(rates_df)

        if leaderboard.empty:
            st.info(
                f"No category currently has {MIN_BANKS_FOR_COMPARISON}+ banks "
                "reporting — not enough data for a meaningful leaderboard yet."
            )
        else:
            st.subheader("Most competitive bank overall")

            win_counts = leaderboard["winner"].value_counts()
            total_categories = len(leaderboard)

            top_bank = win_counts.index[0]
            top_wins = win_counts.iloc[0]

            st.markdown(
                f"### 🏆 **{top_bank}** — best rate in **{top_wins} of "
                f"{total_categories}** compared categories"
            )

            win_chart_data = win_counts.rename_axis("bank").reset_index(name="wins")
            st.altair_chart(
                bank_bar_chart(win_chart_data, "wins", "Categories won"),
                use_container_width=True,
            )

            st.divider()
            st.subheader("Category leaders")
            st.caption(
                "The best-rated bank in each product category with enough banks "
                "to compare fairly, and how far ahead of the runner-up they are."
            )

            cols = st.columns(3)
            sorted_leaderboard = leaderboard.sort_values("margin", ascending=False)
            for i, (_, row) in enumerate(sorted_leaderboard.iterrows()):
                col = cols[i % 3]
                bank_color = BANK_COLORS.get(row["winner"], "#888888")
                label = row["rate_type"].replace("_", " ").title()
                sublabel = row["component"].title()

                with col:
                    st.markdown(
                        f"""
                        <div style="border-left: 4px solid {bank_color};
                                    padding: 10px 14px; margin-bottom: 12px;
                                    background-color: rgba(255,255,255,0.03);
                                    border-radius: 4px;">
                            <div style="font-size: 0.8em; opacity: 0.7;">
                                {sublabel} · {label}
                            </div>
                            <div style="font-size: 1.3em; font-weight: 600;
                                        color: {bank_color};">
                                {row['winner']}
                            </div>
                            <div style="font-size: 1.1em;">
                                {row['winner_rate']:.2f}%
                            </div>
                            <div style="font-size: 0.8em; opacity: 0.6;">
                                {row['margin']:.2f} pts ahead of {row['runner_up']}
                                ({row['banks_compared']} banks compared)
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            st.divider()
            st.subheader("Full comparison table")
            display_table = leaderboard[
                [
                    "component",
                    "rate_type",
                    "winner",
                    "winner_rate",
                    "runner_up",
                    "runner_up_rate",
                    "margin",
                    "banks_compared",
                ]
            ].sort_values(["component", "margin"], ascending=[True, False])
            st.dataframe(display_table, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Rate comparison tab
# ---------------------------------------------------------------------------
with tab_rates:
    rates_df = load_bank_rates()

    if rates_df.empty:
        st.warning("No rate data available.")
    else:
        st.subheader("Compare current rates across banks")

        component = st.radio("Rate type", ["LENDING", "DEPOSIT"], horizontal=True)
        component_df = rates_df[rates_df["rate_component"] == component].copy()
        component_df["rate_pct"] = component_df["rate"] * 100

        bank_counts = component_df.groupby("rate_type")["bank"].nunique()
        well_covered = bank_counts[
            bank_counts >= MIN_BANKS_FOR_COMPARISON
        ].index.tolist()
        thin_covered = bank_counts[
            bank_counts < MIN_BANKS_FOR_COMPARISON
        ].index.tolist()

        show_thin = st.checkbox(
            f"Also show categories with fewer than {MIN_BANKS_FOR_COMPARISON} banks "
            f"reporting ({len(thin_covered)} hidden by default)",
            value=False,
        )

        rate_types = (
            sorted(well_covered) if not show_thin else sorted(bank_counts.index)
        )

        if not rate_types:
            st.info("No rate categories meet the comparison threshold.")
        else:
            selected_type = st.selectbox("Rate category", rate_types)
            filtered = component_df[component_df["rate_type"] == selected_type]

            n_banks = filtered["bank"].nunique()
            if n_banks < len(BANK_COLORS):
                missing = set(BANK_COLORS.keys()) - set(filtered["bank"].unique())
                st.caption(
                    f"⚠️ {n_banks} of {len(BANK_COLORS)} banks report this rate type. "
                    f"Not shown: {', '.join(sorted(missing))} — likely means that "
                    "bank doesn't currently offer a matching product, not missing data."
                )

            chart_data = filtered.groupby("bank", as_index=False)["rate_pct"].mean()
            st.altair_chart(
                bank_bar_chart(chart_data, "rate_pct", f"{selected_type} rate (%)"),
                use_container_width=True,
            )

            insight = generate_rate_insight(filtered, selected_type, component)
            if insight:
                st.markdown(f"💡 {insight}")

            with st.expander("See underlying products"):
                display_cols = [
                    "bank",
                    "product_name",
                    "product_category",
                    "rate_pct",
                    "comparison_rate",
                ]
                st.dataframe(
                    filtered[display_cols].sort_values("rate_pct"),
                    use_container_width=True,
                )

# ---------------------------------------------------------------------------
# Product browser tab
# ---------------------------------------------------------------------------
with tab_products:
    products_df = load_bank_products()

    if products_df.empty:
        st.warning("No product data available.")
    else:
        st.subheader("Browse current bank products")

        banks = st.multiselect(
            "Filter by bank",
            options=sorted(products_df["bank"].unique()),
            default=sorted(products_df["bank"].unique()),
        )
        categories = st.multiselect(
            "Filter by category",
            options=sorted(products_df["product_category"].dropna().unique()),
        )

        filtered = products_df[products_df["bank"].isin(banks)]
        if categories:
            filtered = filtered[filtered["product_category"].isin(categories)]

        st.write(f"{len(filtered)} products")

        product_counts = filtered.groupby("bank", as_index=False).size()
        product_counts.columns = ["bank", "count"]
        st.altair_chart(
            bank_bar_chart(product_counts, "count", "Product count"),
            use_container_width=True,
        )

        st.dataframe(
            filtered[["bank", "product_name", "product_category", "description"]],
            use_container_width=True,
        )

# ---------------------------------------------------------------------------
# CPI trend tab (detailed)
# ---------------------------------------------------------------------------
with tab_cpi:
    cpi_df = load_cpi_trend()

    if cpi_df.empty:
        st.warning("No CPI data available.")
    else:
        st.subheader("Australian CPI — year-on-year % change")
        st.line_chart(
            cpi_df.set_index("time_period")[["cpi_pct_change_yoy"]], height=380
        )

        st.subheader("Month-over-month shift")
        st.bar_chart(
            cpi_df.set_index("time_period")[["month_over_month_shift"]], height=280
        )

        with st.expander("See raw data"):
            st.dataframe(cpi_df, use_container_width=True)

st.divider()
st.caption(
    "Data sources: Australian Bureau of Statistics (ABS) Data API, and the "
    "Consumer Data Right (CDR) Product Reference APIs of ANZ, Westpac, CBA, "
    "and Suncorp. AMP is excluded due to a persistent API version negotiation "
    "issue on their end. Not every bank offers every product/rate category — "
    "charts note when fewer than all four banks report a given category. "
    "See README for full details and known limitations."
)
