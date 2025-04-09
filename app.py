import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(layout="wide")
st.title("Exploitation dynamique des offres par Site et Techno")

uploaded_file = st.file_uploader("Téléverser votre fichier Excel", type=['xlsx'])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # Renommer colonnes
    df = df.rename(columns={
        'Name': 'Site',
        'OBL': 'Opérateur',
        'Type Physical Link': 'Technologie',
        'bandwidth': 'Débit',
        'FASSellPrice': "Frais d'accès",
        'CRMSellPrice': 'Prix mensuel'
    })

    # Choisir Technologie
    techno = st.selectbox("Sélectionnez la technologie", options=df['Technologie'].unique())

    # Filtrer les sites selon la techno
    df_techno = df[df['Technologie'] == techno]

    # Choisir Site
    site = st.selectbox("Sélectionnez le site", options=df_techno['Site'].unique())

    # Filtrer les opérateurs dispo pour ce site et cette techno
    operateurs_dispo = df_techno[df_techno['Site'] == site]['Opérateur'].unique()

    # Sélectionner opérateur dispo pour ce site précis
    operateur = st.selectbox("Sélectionnez l'opérateur", options=operateurs_dispo)

    # Résultat
    resultat = df_techno[
        (df_techno['Site'] == site) & (df_techno['Opérateur'] == operateur)
    ][['Site', 'Technologie', 'Opérateur', 'Débit', "Frais d'accès", 'Prix mensuel']]

    st.subheader("Récapitulatif sélectionné :")
    st.dataframe(resultat, use_container_width=True)

    # Téléchargement du résultat
    output = BytesIO()
    resultat.to_excel(output, index=False)
    output.seek(0)
    st.download_button("Télécharger le résultat Excel", data=output,
                       file_name="resultat_selection.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
