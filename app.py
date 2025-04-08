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

    with onglets[0]:
    # --- Vue par techno et débit ---
        # Vérification post-mapping
        required = ['Site', 'Opérateur', 'Technologie', 'Débit', 'Prix mensuel', "Frais d'accès"]
        missing_columns = [col for col in required if col not in df.columns]
        if missing_columns:
            st.error("Le fichier est invalide. Colonnes manquantes après mapping : " + ", ".join(missing_columns))
        else:
            technos = df['Technologie'].dropna().unique()
            techno_choice = st.selectbox("Choisissez une technologie", options=["Toutes"] + list(technos))

            engagement = st.slider("Durée d'engagement (mois)", min_value=12, max_value=60, step=12, value=36)

            if techno_choice != "Toutes":
                filtered_df_for_debit = df[df['Technologie'] == techno_choice]
            else:
                filtered_df_for_debit = df

            debits = sorted(filtered_df_for_debit['Débit'].dropna().unique())
            debit_options = ["Tous"] + list(debits)

            # Fix pour éviter erreur si "1 gbits" non trouvé
            if techno_choice == "FTTH" and "1 gbits" in debit_options:
                debit_index = debit_options.index("1 gbits")
            else:
                debit_index = 0

            debit_choice = st.selectbox("Choisissez un débit (optionnel)", options=debit_options, index=debit_index)

            # Application des filtres (sans filtrer par engagement)
            df_filtered = df.copy()
            if techno_choice != "Toutes":
                df_filtered = df_filtered[df_filtered['Technologie'] == techno_choice]
            if debit_choice != "Tous":
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
                st.download_button(
                    label="📥 Télécharger le fichier Excel",
                    data=output,
                    file_name="meilleures_offres.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    with onglets[1]:
        st.info("🚧 Cette vue sera bientôt disponible.")
