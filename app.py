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

    # Exclure les lignes où Already Fiber == 'AvailableSoon' ou 'UnderCommercialTerms'
    if 'Already Fiber' in df.columns:
        df = df[(df['Already Fiber'] != 'AvailableSoon') & (df['Already Fiber'] != 'UnderCommercialTerms')]

    # Remplacer les débits FTTH 1000M et 1000/200M par "1 gbits"
    df['Débit'] = df.apply(
        lambda row: '1 gbits' if row['Technologie'] == 'FTTH' and row['Débit'] in ['1000M', '1000/200M'] else row['Débit'],
        axis=1
    )

    # Initialisation correcte des onglets
    onglets = st.tabs(["Choisir la techno et le débit souhaités", "Choisir une techno et un opérateur"])

    # --- Premier onglet : "Choisir la techno et le débit souhaités" ---
    with onglets[0]:
        st.markdown("### Choisir la techno et le débit souhaités")

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

            # Application des filtres (sans filtrer par engagement)
            df_filtered = df.copy()
            df_filtered = df_filtered[df_filtered['Technologie'] == techno_choice]
            df_filtered = df_filtered[df_filtered['Débit'] == debit_choice]

            if df_filtered.empty:
                st.warning("Aucune offre ne correspond aux critères sélectionnés.")
            else:
                # Remplissage des valeurs manquantes pour les frais d'accès
                df_filtered["Frais d'accès"] = df_filtered["Frais d'accès"].fillna(0)

                # Calcul du coût total avec la valeur du slider
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

    # --- Deuxième onglet : "Choisir une techno et un opérateur" ---
    with onglets[1]:
        st.markdown("### Vue par choix de techno, opérateur et débit")

        # Choix de la technologie
        technos = df['Technologie'].dropna().unique()
        techno_choice = st.selectbox("Choisissez une technologie", options=list(technos), key="techno_choice_2")

        # Filtrer les opérateurs selon la technologie choisie
        operateurs = df[df['Technologie'] == techno_choice]['Opérateur'].dropna().unique()
        operateur_choice = st.selectbox("Choisissez un opérateur", options=list(operateurs), key="operateur_choice_2")

        # Filtrer les débits selon la technologie choisie
        filtered_df_for_debit = df[df['Technologie'] == techno_choice]
        debits = sorted(filtered_df_for_debit['Débit'].dropna().unique())
        debit_options = list(debits)
        debit_choice = st.selectbox("Choisissez un débit (optionnel)", options=debit_options, key="debit_choice_2")

        # Appliquer les filtres selon techno, opérateur et débit
        df_filtered = df.copy()
        df_filtered = df_filtered[df_filtered['Technologie'] == techno_choice]
        df_filtered = df_filtered[df_filtered['Opérateur'] == operateur_choice]
        df_filtered = df_filtered[df_filtered['Débit'] == debit_choice]

        if df_filtered.empty:
            st.warning("Aucune offre ne correspond aux critères sélectionnés.")
        else:
            # Nombre de sites éligibles pour l'opérateur et la technologie sélectionnés
            nb_sites_operateur = df_filtered['Site'].nunique()
            st.markdown(f"### Nombre de sites éligibles à {operateur_choice} pour la technologie {techno_choice} : {nb_sites_operateur}")

            # Colonnes à afficher
            colonnes_a_afficher = ['Site', 'Opérateur', 'Technologie', 'Débit', 'Prix mensuel', "Frais d'accès"]
            best_offers_reduits = df_filtered[colonnes_a_afficher]

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
