import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Optimiseur d'offres Internet", layout="wide")
st.title("Optimiseur d'offres Internet par site client")

uploaded_file = st.file_uploader("Téléversez le fichier d'offres", type=[".xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # Affichage des colonnes réelles du fichier pour débogage
    st.write("Colonnes détectées dans le fichier :", list(df.columns))

    # Mapping manuel à partir des noms réels (corrigé avec majuscules)
    column_mapping = {
        'Name': 'Site',
        'OBL': 'Opérateur',
        'Type Physical Link': 'Technologie',
        'bandwidth': 'Débit',
        'FASSellPrice': "Frais d'accès",
        'CRMSellPrice': 'Prix mensuel'
    }

    df = df.rename(columns=column_mapping)

    # Vérification post-mapping
    required = ['Site', 'Opérateur', 'Technologie', 'Débit', 'Prix mensuel', "Frais d'accès"]
    missing_columns = [col for col in required if col not in df.columns]
    if missing_columns:
        st.error("Le fichier est invalide. Colonnes manquantes après mapping : " + ", ".join(missing_columns))
    else:
        # Ajout d'une colonne par défaut pour l'engagement si elle n'existe pas
        if 'Engagement (mois)' not in df.columns:
            df['Engagement (mois)'] = 36  # valeur par défaut

        technos = df['Technologie'].dropna().unique()
        techno_choice = st.selectbox("Choisissez une technologie", options=["Toutes"] + list(technos))

        engagement = st.slider("Durée d'engagement (mois)", min_value=12, max_value=60, step=12)

        if techno_choice != "Toutes":
            debits = df[df['Technologie'] == techno_choice]['Débit'].dropna().unique()
        else:
            debits = df['Débit'].dropna().unique()

        debit_choice = st.selectbox("Choisissez un débit (optionnel)", options=["Tous"] + list(debits))

        # Application des filtres
        df_filtered = df[df['Engagement (mois)'] == engagement]
        if techno_choice != "Toutes":
            df_filtered = df_filtered[df_filtered['Technologie'] == techno_choice]
        if debit_choice != "Tous":
            df_filtered = df_filtered[df_filtered['Débit'] == debit_choice]

        if df_filtered.empty:
            st.warning("Aucune offre ne correspond aux critères sélectionnés.")
        else:
            # Remplissage des valeurs manquantes pour les frais d'accès
            df_filtered["Frais d'accès"] = df_filtered["Frais d'accès"].fillna(0)

            # Calcul du coût total
            df_filtered['Coût total'] = df_filtered['Prix mensuel'] * engagement + df_filtered["Frais d'accès"]

            # Sélection de l'offre la moins chère par site
            best_offers = df_filtered.sort_values('Coût total').groupby('Site').first().reset_index()

            # Affichage du nombre de sites éligibles
            nb_sites = best_offers['Site'].nunique()
            st.markdown(f"### Nombre de sites éligibles à la {techno_choice} : {nb_sites}")

            # Colonnes à exclure
            colonnes_a_exclure = ['NDI', 'INSEECode', 'rivoli code', 'Available Copper Pair', 'Needed Coppoer Pair']
            colonnes_finales = [col for col in best_offers.columns if col not in colonnes_a_exclure]

            best_offers_reduits = best_offers[colonnes_finales]

            st.subheader("Meilleures offres par site")
            st.dataframe(best_offers_reduits, use_container_width=True)

            # Export Excel
            output = BytesIO()
            best_offers_reduits.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)

            st.download_button(
                label="📥 Télécharger le fichier Excel",
                data=output,
                file_name="meilleures_offres.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
