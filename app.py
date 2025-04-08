import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Exploitation des données d'éligibité", layout="wide")
st.title("Exploitation des données d'éligibité")

uploaded_file = st.file_uploader("Téléversez le fichier d'offres", type=[".xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

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

    # Exclure les lignes où Already Fiber == 'AvailableSoon'
    if 'Already Fiber' in df.columns:
        df = df[df['Already Fiber'] != 'AvailableSoon']

    # Remplacer les débits FTTH 1000M et 1000/200M par "1 gbits"
    df['Débit'] = df.apply(
        lambda row: '1 gbits' if row['Technologie'] == 'FTTH' and row['Débit'] in ['1000M', '1000/200M'] else row['Débit'],
        axis=1
    )

    onglets = st.tabs(["Par choix de techno et débit", "Par choix techno et opérateur"])

    # --- Premier onglet ---
    with onglets[0]:
        st.markdown("### Vue par choix de techno et débit")

        # Vérification post-mapping
        required = ['Site', 'Opérateur', 'Technologie', 'Débit', 'Prix mensuel', "Frais d'accès"]
        missing_columns = [col for col in required if col not in df.columns]
        if missing_columns:
            st.error("Le fichier est invalide. Colonnes manquantes après mapping : " + ", ".join(missing_columns))
        else:
            technos = df['Technologie'].dropna().unique()
            techno_choice = st.selectbox("Choisissez une technologie", options=list(technos))

            engagement = st.slider("Durée d'engagement (mois)", min_value=12, max_value=60, step=12, value=36)

            filtered_df_for_debit = df[df['Technologie'] == techno_choice]

            debits = sorted(filtered_df_for_debit['Débit'].dropna().unique())
            debit_options = list(debits)

            debit_choice = st.selectbox("Choisissez un débit (optionnel)", options=debit_options)

            # Appliquer les filtres selon techno, opérateur et débit
            df_filtered = df.copy()
            df_filtered = df_filtered[df_filtered['Technologie'] == techno_choice]
            df_filtered = df_filtered[df_filtered['Débit'] == debit_choice]

            if df_filtered.empty:
                st.warning("Aucune offre ne correspond aux critères sélectionnés.")
            else:
                # Colonnes à afficher (mêmes que pour le 1er onglet)
                colonnes_a_afficher = ['Site', 'Opérateur', 'Technologie', 'Débit', 'Prix mensuel', "Frais d'accès"]
                best_offers_reduits = df_filtered[colonnes_a_afficher]

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

    # --- Deuxième onglet ---
    with onglets[1]:
        st.markdown("### Vue par choix de techno, opérateur et débit")

        # Choix de la technologie, opérateur et débit
        technos = df['Technologie'].dropna().unique()
        techno_choice = st.selectbox("Choisissez une technologie", options=list(technos))

        operateurs = df['Opérateur'].dropna().unique()
        operateur_choice = st.selectbox("Choisissez un opérateur", options=list(operateurs))

        filtered_df_for_debit = df[df['Technologie'] == techno_choice]
        debits = sorted(filtered_df_for_debit['Débit'].dropna().unique())
        debit_options = list(debits)
        debit_choice = st.selectbox("Choisissez un débit (optionnel)", options=debit_options)

        # Appliquer les filtres selon techno, opérateur et débit
        df_filtered = df.copy()
        df_filtered = df_filtered[df_filtered['Technologie'] == techno_choice]
        df_filtered = df_filtered[df_filtered['Opérateur'] == operateur_choice]
        df_filtered = df_filtered[df_filtered['Débit'] == debit_choice]

        if df_filtered.empty:
            st.warning("Aucune offre ne correspond aux critères sélectionnés.")
        else:
            # Colonnes à afficher (mêmes que pour le 1er onglet)
            colonnes_a_afficher = ['Site', 'Opérateur', 'Technologie', 'Débit', 'Prix mensuel', "Frais d'accès"]
            best_offers_reduits = df_filtered[colonnes_a_afficher]

            st.subheader("Offres correspondant à vos critères")
            st.dataframe(best_offers_reduits, use_container_width=True)

            # Export Excel
            output = BytesIO()
            best_offers_reduits.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            st.download_button(
                label="📥 Télécharger le fichier Excel",
                data=output,
                file_name="offres_filtrees.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
