import streamlit as st
import pandas as pd
import plotly.express as px

# Configure the page
st.set_page_config(page_title="Projeto Clínica de estética", layout="wide")

# Add title
st.title("Dashboard - Análise de Procedimentos Clínicos")

# Load data
@st.cache_data
def load_data():
    df = pd.read_excel('Docs/Clinica_Prospct.xlsx')
    # Calculate average margins
    df['Margem_Media'] = df[['Margem de Lucro  (Tatuapé / Paulista)', 'Margem de Lucro  (Perdizes)']].mean(axis=1)
    df['Margem_%_Media'] = df[['Margem %  (Tatuapé / Paulista)', 'Margem %  (Perdizes)']].mean(axis=1) * 100
    df['Custo_Unit_Médio'] = df[['Custo_Unit_Sessões (Tatuapé / Paulista)', 'Custo_Unit_Sessões (Perdizes)']].mean(axis=1)
    return df

df = load_data()

# Create two columns for the visualizations
col1, col2 = st.columns(2)  

with col1:
    st.subheader("Análise de Produtos por Procedimento")
    
    # Add filters
    selected_procedures = st.multiselect(
        "Selecione os Procedimentos:",
        options=df['Procedimento'].unique(),
        default=df['Procedimento'].unique()
    )
    
    # Add metric selection
    metric_choice = st.selectbox(
        "Selecione a métrica para análise:",
        ["Valor / Margem", "Margem por Produto", "Valor / Custo"]
    )
    
    # Add grouping selection
    group_by = st.selectbox(
        "Agrupar por:",
        ["Procedimento", "Produto / Ativo"]
    )
    
    # Filter data
    filtered_df = df[df['Procedimento'].isin(selected_procedures)]
    
    # Create dynamic bar chart based on selection
    if metric_choice == "Valor / Margem":
        fig1 = px.bar(filtered_df,
                      x=group_by,
                      y=['Valor_Cobrado p/ Sessões à Vista_Cash', 'Margem_Media'],
                      title=f'Valor e Margens de Lucro por {group_by}',
                      barmode='group',
                      height=700,
                      color_discrete_sequence=['#000080', '#f5365c'], 
                      labels={
                          'Valor_Cobrado p/ Sessões à Vista_Cash': 'Valor Cobrado',
                          'Margem_Media': 'Margem Média',
                          'value': 'Valor (R$)',
                          'variable': 'Métrica'
                      })
    elif metric_choice == "Margem por Produto":
        fig1 = px.bar(filtered_df,
                      x=group_by,
                      y='Margem_Media',
                      title=f'Margem Média por {group_by}',
                      height=700,
                      color_discrete_sequence=['#000080'], 
                      labels={
                          'Margem_Media': 'Margem Média (R$)',
                          'value': 'Margem (R$)',
                          'variable': 'Métrica'
                      })
    else:  # Custo por Produto
        fig1 = px.bar(filtered_df,
                      x=group_by,
                      y=['Valor_Cobrado p/ Sessões à Vista_Cash', 'Custo_Unit_Médio'],
                      title=f'Valor e Custo Unitário Médio por {group_by}',
                      barmode='group',
                      height=700,
                      color_discrete_sequence=['#000080', '#f5365c'],
                      labels={
                          'Custo_Unit_Médio': 'Custo Unitário Médio (R$)',
                          'value': 'Valor (R$)',
                          'variable': 'Métrica'
                      })

    # Update layout to remove unwanted labels
    fig1.update_layout(
        xaxis_title=group_by,
        yaxis_title="Valor (R$)"
    )
    
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.subheader("Distribuição de Margem de Lucro")
    
    # Create sunburst chart
    fig2 = px.sunburst(
        filtered_df,
        path=['Procedimento', 'Produto / Ativo'],
        values='Margem_%_Media',
        title='Margem de Lucro por Produto (%)',
        height=850
    )
    
    # Customize templates
    templates = []
    for i, label in enumerate(fig2.data[0].labels):
        if fig2.data[0].parents[i] == '':
            templates.append('%{label}')
        else:
            templates.append('%{label}<br>%{value:.2f}%')
    
    fig2.data[0].texttemplate = templates
    fig2.data[0].textinfo = 'text'
    fig2.update_layout(showlegend=True)
    
    st.plotly_chart(fig2, use_container_width=True)
    
# Add some metrics
st.subheader("Principais Métricas")
metric_cols = st.columns(4)

with metric_cols[0]:
    max_row = filtered_df.loc[filtered_df['Valor_Cobrado p/ Sessões à Vista_Cash'].idxmax()]
    max_value = max_row['Valor_Cobrado p/ Sessões à Vista_Cash']
    max_procedure = max_row['Procedimento']
    st.metric(f"Procedimento mais caro: {max_procedure}", f"R$ {max_value:,.2f}")

with metric_cols[1]:
    min_row = filtered_df.loc[filtered_df['Custo_Unit_Médio'].idxmin()]
    min_value = min_row['Custo_Unit_Médio']
    min_procedure = min_row['Procedimento']
    st.metric(f"Menor custo únitário: {min_procedure}", f"R$ {min_value:,.2f}")

with metric_cols[2]:    
    max_row = filtered_df.loc[filtered_df['Margem_Media'].idxmax()]
    max_value = max_row['Margem_Media']
    max_procedure = max_row['Procedimento']
    st.metric(f"Maior margem: {max_procedure}", f"R$ {max_value:,.2f}")
    
with metric_cols[3]:    
    max_row = filtered_df.loc[filtered_df['Margem_%_Media'].idxmax()]
    max_value = max_row['Margem_%_Media']
    max_procedure = max_row['Procedimento']
    st.metric(f"Maior margem %: {max_procedure}", f"{max_value:.2f}%")    

# Add data table with filters
st.subheader("Dados Detalhados")
st.dataframe(filtered_df)

