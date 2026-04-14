import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Olist Funnel Analytics",
    page_icon=":bar_chart:",
    layout="wide",
)

COLOR_SEQUENCE = [
    "#0068C9", "#29B09D", "#FF8700", "#83C9FF",
    "#FF2B2B", "#FFD16A", "#6D3FC0", "#FF6F61",
]

_LAYOUT = dict(
    font=dict(family="Inter, sans-serif", size=12),
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    colorway=COLOR_SEQUENCE,
    margin=dict(t=48, b=32, l=48, r=24),
)


def _style(fig):
    fig.update_layout(**_LAYOUT)
    return fig


def _download_df(
    df: pd.DataFrame, fmt: dict, filename: str,
    col_rename: dict | None = None,
) -> None:
    formatted = df.copy()
    for col, f in fmt.items():
        if col in formatted.columns:
            formatted[col] = formatted[col].apply(
                lambda x, f=f: f.format(x) if pd.notna(x) else ""
            )
    if col_rename:
        formatted = formatted.rename(columns=col_rename)
    csv = formatted.to_csv(index=False).encode("utf-8")
    st.download_button(
        f"\U0001f4e5 Download {filename}", csv,
        file_name=filename, mime="text/csv",
    )


@st.cache_data(show_spinner=False)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    df_mql = pd.read_csv("dataset/olist_marketing_qualified_leads_dataset.csv")
    df_closed = pd.read_csv("dataset/olist_closed_deals_dataset.csv")

    df_mql["first_contact_date"] = pd.to_datetime(df_mql["first_contact_date"], errors="coerce")
    df_closed["won_date"] = pd.to_datetime(df_closed["won_date"], errors="coerce")

    if "busines_s_segment" in df_closed.columns and "business_segment" not in df_closed.columns:
        df_closed = df_closed.rename(columns={"busines_s_segment": "business_segment"})

    if "declared_monthly_revenue" in df_closed.columns:
        df_closed["declared_monthly_revenue"] = pd.to_numeric(
            df_closed["declared_monthly_revenue"], errors="coerce"
        )

    return df_mql, df_closed


@st.cache_data(show_spinner=False)
def build_funnel(df_mql: pd.DataFrame, df_closed: pd.DataFrame) -> pd.DataFrame:
    df_funnel = df_mql.merge(df_closed, how="left", on="mql_id", suffixes=("_mql", "_deal"))
    df_funnel["is_won"] = df_funnel["won_date"].notna().astype(int)
    df_funnel["days_to_close"] = (
        df_funnel["won_date"] - df_funnel["first_contact_date"]
    ).dt.days
    return df_funnel


def monthly_performance(df_funnel: pd.DataFrame) -> pd.DataFrame:
    mensal = (
        df_funnel.assign(ano_mes=df_funnel["first_contact_date"].dt.to_period("M").astype(str))
        .groupby("ano_mes", dropna=False)
        .agg(
            leads=("mql_id", "count"),
            ganhos=("is_won", "sum"),
            tempo_medio_dias=("days_to_close", "mean"),
        )
        .reset_index()
    )
    mensal = mensal[mensal["ano_mes"] != "2017-06"]
    mensal["taxa_conversao"] = np.where(
        mensal["leads"] > 0, mensal["ganhos"] / mensal["leads"], np.nan
    )
    mensal["taxa_abandono"] = 1 - mensal["taxa_conversao"]
    mensal["tempo_medio_dias"] = mensal["tempo_medio_dias"].round(0)
    return mensal


def origin_performance(df_funnel: pd.DataFrame) -> pd.DataFrame:
    origin_perf = (
        df_funnel.groupby("origin", dropna=False)
        .agg(
            leads=("mql_id", "count"),
            ganhos=("is_won", "sum"),
            receita_total=("declared_monthly_revenue", "sum"),
            tempo_medio_dias=("days_to_close", "mean"),
        )
        .reset_index()
    )
    origin_perf["taxa_conversao"] = np.where(
        origin_perf["leads"] > 0,
        origin_perf["ganhos"] / origin_perf["leads"],
        np.nan,
    )
    origin_perf["taxa_abandono"] = 1 - origin_perf["taxa_conversao"]
    origin_perf["ticket_medio_deal"] = np.where(
        origin_perf["ganhos"] > 0,
        origin_perf["receita_total"] / origin_perf["ganhos"],
        np.nan,
    )
    origin_perf["tempo_medio_dias"] = origin_perf["tempo_medio_dias"].round(0)
    return origin_perf.sort_values(["receita_total", "taxa_conversao"], ascending=False)


def segment_win_performance(df_funnel: pd.DataFrame) -> pd.DataFrame:
    won_with_rev = df_funnel[
        df_funnel["is_won"].eq(1)
        & df_funnel["declared_monthly_revenue"].gt(0)
    ]

    seg_type = (
        won_with_rev
        .groupby(["business_segment", "lead_type"], dropna=False)
        .agg(
            deals_fechados=("mql_id", "count"),
            receita_total=("declared_monthly_revenue", "sum"),
            tempo_medio_dias=("days_to_close", "mean"),
        )
        .reset_index()
    )

    total_deals = seg_type["deals_fechados"].sum()
    seg_type["participacao_deals"] = np.where(
        total_deals > 0,
        seg_type["deals_fechados"] / total_deals,
        np.nan,
    )
    seg_type["ticket_medio_deal"] = np.where(
        seg_type["deals_fechados"] > 0,
        seg_type["receita_total"] / seg_type["deals_fechados"],
        np.nan,
    )

    return seg_type.sort_values("receita_total", ascending=False)


def render_funnel_tab(df_funnel: pd.DataFrame) -> None:
    total_mql = len(df_funnel)
    total_won = int(df_funnel["is_won"].sum())
    total_with_revenue = int(
        df_funnel.loc[
            df_funnel["is_won"].eq(1) & df_funnel["declared_monthly_revenue"].gt(0)
        ].shape[0]
    )

    stages = ["MQL (Qualified Lead)", "Closed Deal (Won)", "Won w/ Declared Revenue"]
    values = [total_mql, total_won, total_with_revenue]

    fig = go.Figure(go.Funnel(
        y=stages,
        x=values,
        textinfo="value+percent initial",
        marker=dict(color=COLOR_SEQUENCE[:3]),
    ))
    _style(fig).update_layout(title="Marketing & Sales Funnel")
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        conv_df = pd.DataFrame({
            "Stage": stages,
            "Volume": values,
            "% of MQL": [v / total_mql if total_mql else np.nan for v in values],
        })
        _fmt_funnel = {"Volume": "{:,.0f}", "% of MQL": "{:.2%}"}
        st.dataframe(
            conv_df.style.format(_fmt_funnel),
            use_container_width=True,
        )
        _download_df(conv_df, _fmt_funnel, "funnel_summary.csv")
    with col_b:
        drop = total_mql - total_won
        fig_pie = px.pie(
            names=["Converted", "Not Converted"],
            values=[total_won, drop],
            title="Overall Conversion",
            color_discrete_sequence=[COLOR_SEQUENCE[1], COLOR_SEQUENCE[4]],
            hole=0.45,
        )
        st.plotly_chart(_style(fig_pie), use_container_width=True)


def apply_filters(df_funnel: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filters")

    origins = sorted(df_funnel["origin"].dropna().astype(str).unique().tolist())
    use_all = st.sidebar.checkbox("All", value=True)

    if use_all:
        return df_funnel.copy()

    selected_origins = st.sidebar.multiselect(
        "Select Origins",
        options=origins,
    )

    if not selected_origins:
        return df_funnel.iloc[:0].copy()

    mask = df_funnel["origin"].astype(str).isin(selected_origins)
    return df_funnel.loc[mask].copy()


def render_header(df_funnel: pd.DataFrame) -> None:
    total_leads = len(df_funnel)
    total_wins = int(df_funnel["is_won"].sum())
    conv_rate = total_wins / total_leads if total_leads else np.nan
    avg_days = df_funnel.loc[df_funnel["is_won"].eq(1), "days_to_close"].mean()
    total_revenue = df_funnel["declared_monthly_revenue"].sum(min_count=1)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Leads", f"{total_leads:,}")
    c2.metric("Closed Deals", f"{total_wins:,}")
    c3.metric("Conversion Rate",
              f"{conv_rate:.2%}" if pd.notna(conv_rate) else "-")
    c4.metric("Avg. Time (days)",
              f"{avg_days:,.0f}" if pd.notna(avg_days) else "-")
    c5.metric("Declared Revenue",
              f"R$ {total_revenue:,.2f}" if pd.notna(total_revenue) else "-")


def render_monthly_tab(df_funnel: pd.DataFrame) -> None:
    mensal = monthly_performance(df_funnel)

    col_a, col_b = st.columns(2)
    with col_a:
        fig_vol = px.line(
            mensal,
            x="ano_mes",
            y=["leads", "ganhos"],
            markers=True,
            title="Monthly Trend: Leads vs Closed Deals",
        )
        fig_vol.for_each_trace(
            lambda t: t.update(name={"leads": "Leads", "ganhos": "Won Deals"}.get(t.name, t.name))
        )
        fig_vol.update_layout(xaxis_title="Month", yaxis_title="Count")
        st.plotly_chart(_style(fig_vol), use_container_width=True)

    with col_b:
        fig_conv = px.line(
            mensal,
            x="ano_mes",
            y=["taxa_conversao", "taxa_abandono"],
            markers=True,
            title="Monthly Rates: Conversion vs Drop-off",
        )
        fig_conv.for_each_trace(
            lambda t: t.update(name={"taxa_conversao": "Conversion Rate", "taxa_abandono": "Drop-off Rate"}.get(t.name, t.name))
        )
        fig_conv.update_layout(xaxis_title="Month", yaxis_title="Rate")
        st.plotly_chart(_style(fig_conv), use_container_width=True)

    won = df_funnel.loc[df_funnel["is_won"].eq(1), "days_to_close"].dropna()
    if not won.empty:
        st.subheader("Time-to-Close Distribution (days)")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Median", f"{won.median():,.0f}")
        c2.metric("Mean", f"{won.mean():,.1f}")
        c3.metric("Std. Deviation", f"{won.std():,.1f}")
        c4.metric("P90", f"{won.quantile(0.9):,.0f}")
        st.caption("P90: 90% of deals close within this number of days.")

        fig_hist = px.histogram(
            x=won, nbins=40,
            title="Histogram: Days to Close",
            labels={"x": "Days", "y": "Deal Count"},
            color_discrete_sequence=[COLOR_SEQUENCE[0]],
        )
        fig_hist.update_layout(yaxis_title="Deal Count")
        fig_hist.add_vline(
            x=won.median(), line_dash="dash",
            annotation_text=f"Median: {won.median():.0f}d",
        )
        st.plotly_chart(_style(fig_hist), use_container_width=True)

    _fmt_monthly = {
        "leads": "{:,.0f}",
        "ganhos": "{:,.0f}",
        "tempo_medio_dias": "{:,.0f}",
        "taxa_conversao": "{:.2%}",
        "taxa_abandono": "{:.2%}",
    }
    _rename_monthly = {
        "ano_mes": "month",
        "ganhos": "won_deals",
        "tempo_medio_dias": "avg_days_to_close",
        "taxa_conversao": "conversion_rate",
        "taxa_abandono": "drop_off_rate",
    }
    st.dataframe(
        mensal.style.format(_fmt_monthly),
        use_container_width=True,
    )
    _download_df(mensal, _fmt_monthly, "monthly_performance.csv", _rename_monthly)


def render_origin_tab(df_funnel: pd.DataFrame) -> None:
    origin_perf = origin_performance(df_funnel)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        fig_leads = px.bar(
            origin_perf, x="origin", y="leads",
            title="Leads by Origin", text="leads",
            color_discrete_sequence=[COLOR_SEQUENCE[0]],
        )
        fig_leads.update_traces(textposition="outside")
        st.plotly_chart(_style(fig_leads), use_container_width=True)

    with col_b:
        fig_conv = px.bar(
            origin_perf, x="origin", y="taxa_conversao",
            title="Conversion Rate by Origin", text="taxa_conversao",
            color_discrete_sequence=[COLOR_SEQUENCE[1]],
        )
        fig_conv.update_traces(texttemplate="%{text:.1%}", textposition="outside")
        st.plotly_chart(_style(fig_conv), use_container_width=True)

    with col_c:
        fig_rev = px.bar(
            origin_perf, x="origin", y="receita_total",
            title="Total Revenue by Origin", text="receita_total",
            color_discrete_sequence=[COLOR_SEQUENCE[2]],
        )
        fig_rev.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        st.plotly_chart(_style(fig_rev), use_container_width=True)

    st.subheader("Strategic View: Volume × Conversion × Revenue by Origin")
    bubble_df = origin_perf.dropna(subset=["taxa_conversao", "receita_total"])
    if not bubble_df.empty:
        fig_bubble = px.scatter(
            bubble_df, x="leads", y="taxa_conversao",
            size="receita_total", color="origin",
            hover_data=["ticket_medio_deal", "tempo_medio_dias"],
            title="Bubble: Leads × Conversion",
            labels={"leads": "Lead Volume", "taxa_conversao": "Conversion Rate"},
            color_discrete_sequence=COLOR_SEQUENCE,
        )
        fig_bubble.update_layout(yaxis_tickformat=".0%")
        st.plotly_chart(_style(fig_bubble), use_container_width=True)

    _fmt_origin = {
        "leads": "{:,.0f}",
        "ganhos": "{:,.0f}",
        "receita_total": "R$ {:,.2f}",
        "tempo_medio_dias": "{:,.0f}",
        "taxa_conversao": "{:.2%}",
        "taxa_abandono": "{:.2%}",
        "ticket_medio_deal": "R$ {:,.2f}",
    }
    _rename_origin = {
        "ganhos": "won_deals",
        "receita_total": "total_revenue",
        "tempo_medio_dias": "avg_days_to_close",
        "taxa_conversao": "conversion_rate",
        "taxa_abandono": "drop_off_rate",
        "ticket_medio_deal": "avg_deal_ticket",
    }
    st.dataframe(
        origin_perf.style.format(_fmt_origin),
        use_container_width=True,
    )
    _download_df(origin_perf, _fmt_origin, "origin_performance.csv", _rename_origin)


def render_segment_tab(df_funnel: pd.DataFrame) -> None:
    seg_type = segment_win_performance(df_funnel)

    st.info(
        "Analysis by business_segment and lead_type considers only closed deals "
        "with declared revenue."
    )

    fig_seg = px.bar(
        seg_type.head(20),
        x="business_segment",
        y="receita_total",
        color="lead_type",
        title="Top Segments by Revenue (closed deals w/ revenue)",
        color_discrete_sequence=COLOR_SEQUENCE,
    )
    st.plotly_chart(_style(fig_seg), use_container_width=True)
    _fmt_seg = {
        "deals_fechados": "{:,.0f}",
        "receita_total": "R$ {:,.2f}",
        "tempo_medio_dias": "{:,.0f}",
        "participacao_deals": "{:.2%}",
        "ticket_medio_deal": "R$ {:,.2f}",
    }
    _rename_seg = {
        "deals_fechados": "closed_deals",
        "receita_total": "total_revenue",
        "tempo_medio_dias": "avg_days_to_close",
        "participacao_deals": "deal_share",
        "ticket_medio_deal": "avg_deal_ticket",
    }
    st.dataframe(
        seg_type.style.format(_fmt_seg),
        use_container_width=True,
    )
    _download_df(seg_type, _fmt_seg, "segment_performance.csv", _rename_seg)


def main() -> None:
    st.title("Marketing Funnel Analytics — Olist")
    with st.expander("About This Project", expanded=False):
        st.markdown(
            "This dashboard analyzes the **Olist marketing and sales funnel**, "
            "Brazil's largest department-store marketplace. The dataset contains "
            "approximately **8,000 Marketing Qualified Leads (MQLs)** who requested "
            "contact between Jun/2017 and Jun/2018 to sell their products on the platform.\n\n"
            "Olist connects small businesses across Brazil to sales channels under "
            "a single contract, and sellers ship through logistics partners.\n\n"
            "**What you will find here:**\n"
            "- **Overview Funnel** — MQL → Deal → Revenue conversion view\n"
            "- **Monthly View** — time-series evolution of leads, conversion and closing time\n"
            "- **Origin & Conversion** — performance by acquisition channel\n"
            "- **Segment & Lead Type** — revenue and average ticket by business segment\n\n"
            "*Real, anonymized and sampled data from the original dataset — available on **Kaggle**.*"
        )

    try:
        df_mql, df_closed = load_data()
        df_funnel = build_funnel(df_mql, df_closed)
    except FileNotFoundError:
        st.error("Files not found. Please run the app from the project root folder.")
        st.stop()

    if "business_segment" not in df_funnel.columns or "lead_type" not in df_funnel.columns:
        st.error("Segmentation columns not found in the closed deals dataset.")
        st.stop()

    df_filtered = apply_filters(df_funnel)
    if df_filtered.empty:
        st.warning("No data for the selected filters.")
        st.stop()

    render_header(df_filtered)

    tab1, tab2, tab3, tab4 = st.tabs([
        "Overview Funnel",
        "Monthly View",
        "Origin & Conversion",
        "Segment & Lead Type",
    ])

    with tab1:
        render_funnel_tab(df_filtered)

    with tab2:
        render_monthly_tab(df_filtered)

    with tab3:
        render_origin_tab(df_filtered)

    with tab4:
        render_segment_tab(df_filtered)

    with st.expander("Download Raw Datasets", expanded=False):
        st.markdown("Download the original unprocessed CSV files used in this analysis.")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button(
                "📥 MQL Dataset (CSV)",
                df_mql.to_csv(index=False).encode("utf-8"),
                file_name="olist_marketing_qualified_leads.csv",
                mime="text/csv",
            )
        with col_d2:
            st.download_button(
                "📥 Closed Deals Dataset (CSV)",
                df_closed.to_csv(index=False).encode("utf-8"),
                file_name="olist_closed_deals.csv",
                mime="text/csv",
            )


if __name__ == "__main__":
    main()
