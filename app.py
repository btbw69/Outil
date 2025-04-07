import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Optimiseur d'offres Internet", layout="wide")
st.title("Optimiseur d'offres Internet par site client")

uploaded_file = st.file_uploader("Téléversez le fichier d'offres", type=[".xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # Mapping des colonnes réelles vers les noms attendus
    df = df.rename(columns={
        'name': 'Site',
        'OBL': 'Opérateur',
        'type physical link': 'Technologie',
        'bandwidth': 'Débit',
        'FASSellPrice': "Frais d'accès",
        'CRMSellPrice': 'Prix mensuel'
    })

    # Ajout d'une colonne factice pour l'engagement (à ajuster si elle existe ailleurs)
    if 'Engagement (mois)' not in df.columns:
        df['Engagement (mois)'] = 36  # valeur par défaut, modifiable plus tard

    # Vérification des colonnes nécessaires
    required_columns = ['Site', 'Opérateur', 'Technologie', 'Débit', 'Prix mensuel', "Frais d'accès", 'Engagement (mois)']
    if not all(col in df.columns for col in required_columns):
        st.error("Le fichier ne contient pas toutes les colonnes requises : " + ", ".join(required_columns))
    else:
        technos = df['Technologie'].unique()
        techno_choice = st.selectbox("Choisissez une technologie", options=technos)

        engagement = st.slider("Durée d'engagement (mois)", min_value=12, max_value=60, step=12)

        debits = df['Débit'].unique()
        debit_choice = st.selectbox("Choisissez un débit (optionnel)", options=["Tous"] + list(debits))

        # Application des filtres
        df_filtered = df[
            (df['Technologie'] == techno_choice) &
            (df['Engagement (mois)'] == engagement)
        ]
        if debit_choice != "Tous":
            df_filtered = df_filtered[df_filtered['Débit'] == debit_choice]

        # Calcul du coût total
        df_filtered['Coût total'] = df_filtered['Prix mensuel'] * engagement + df_filtered["Frais d'accès"]

        # Sélection de l'offre la moins chère par site
        best_offers = df_filtered.sort_values('Coût total').groupby('Site').first().reset_index()

        st.subheader("Meilleures offres par site")
        st.dataframe(best_offers, use_container_width=True)

        # Export Excel
        output = BytesIO()
        best_offers.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)

        st.download_button(
            label="📥 Télécharger le fichier Excel",
            data=output,
            file_name="meilleures_offres.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
