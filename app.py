import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Exploitation des données d'éligibilité", layout="wide")
st.title("Exploitation des données d'éligibilité")

uploaded_file = st.file_uploader("Téléversez le fichier d'offres", type=[".xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # Mapping manuel des colonnes
    column_mapping = {
        'Name': 'Site',
        'OBL': 'Opérateur',
        'Type Physical Link': 'Technologie',
        'bandwidth': 'Débit',
        'FASSellPrice': "Frais d'accès",
        'CRMSellPrice': 'Prix mensuel',
        'CostArea': 'CostArea'
    }
    df = df.rename(columns=column_mapping)

    # Exclure certaines lignes Already Fiber
    if 'Already Fiber' in df.columns:
        df = df[(df['Already Fiber'] != 'AvailableSoon') & (df['Already Fiber'] != 'UnderCommercialTerms')]

    # Correction débit FTTH
    df['Débit'] = df.apply(
        lambda row: '1 gbits' if row['Technologie'] == 'FTTH' and row['Débit'] in ['1000M', '1000/200M'] else row['Débit'],
        axis=1
    )

    # Définir les onglets
    onglets = st.tabs([
        "FAS/ABO le moins cher",
        "Site Eligible pour un opérateur",
        "Choix de la techno / opérateur / débit pour chaque site",
        "Proginov",
        "Proginov nouvelle zone"
    ])

    # --- Onglet 1 : FAS/ABO le moins cher ---
    with onglets[0]:
        st.markdown("### FAS/ABO le moins cher")

        required = ['Site', 'Opérateur', 'Technologie', 'Débit', 'Prix mensuel', "Frais d'accès"]
        missing_columns = [col for col in required if col not in df.columns]
        if missing_columns:
            st.error("Le fichier est invalide. Colonnes manquantes après mapping : " + ", ".join(missing_columns))
        else:
            technos = df['Technologie'].dropna().unique()
            techno_choice = st.selectbox("Choisissez une technologie", options=list(technos), key="techno_choice_1")
            engagement = st.slider("Durée d'engagement (mois)", 12, 60, step=12, value=36, key="engagement_1")

            filtered_df = df[df['Technologie'] == techno_choice]
            debits = sorted(filtered_df['Débit'].dropna().unique())
            debit_choice = st.selectbox("Choisissez un débit (optionnel)", options=debits, key="debit_choice_1")

            df_filtered = filtered_df[filtered_df['Débit'] == debit_choice]
            if df_filtered.empty:
                st.warning("Aucune offre ne correspond aux critères sélectionnés.")
            else:
                df_filtered["Frais d'accès"] = df_filtered["Frais d'accès"].fillna(0)
                df_filtered['Coût total'] = df_filtered['Prix mensuel'] * engagement + df_filtered["Frais d'accès"]
                best_offers = df_filtered.sort_values('Coût total').groupby('Site').first().reset_index()

                nb_sites = best_offers['Site'].nunique()
                st.markdown(f"### Nombre de sites éligibles à la {techno_choice} : {nb_sites}")

                if 'columns_visible' not in st.session_state:
                    st.session_state.columns_visible = True
                if st.button("Laisser que colonne prix" if st.session_state.columns_visible else "Afficher toutes les colonnes", key="button_1"):
                    st.session_state.columns_visible = not st.session_state.columns_visible

                if st.session_state.columns_visible:
                    colonnes_a_afficher = [col for col in df.columns if col not in ['NDI', 'INSEECode', 'rivoli code', 'Available Copper Pair', 'Needed Coppoer Pair']]
                else:
                    colonnes_a_afficher = ['Site', "Frais d'accès", 'Prix mensuel']

                best_offers_reduits = best_offers[colonnes_a_afficher]
                st.dataframe(best_offers_reduits, use_container_width=True)

                output = BytesIO()
                best_offers_reduits.to_excel(output, index=False, engine='openpyxl')
                output.seek(0)
                st.download_button("📥 Télécharger le fichier Excel", data=output, file_name="meilleures_offres.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # --- Onglet 2 : Site Eligible pour un opérateur ---
    with onglets[1]:
        st.markdown("### Site Eligible pour un opérateur")

        technos = df['Technologie'].dropna().unique()
        techno_choice = st.selectbox("Choisissez une technologie", options=list(technos), key="techno_choice_2")
        operateurs = df[df['Technologie'] == techno_choice]['Opérateur'].dropna().unique()
        operateur_choice = st.selectbox("Choisissez un opérateur", options=list(operateurs), key="operateur_choice_2")

        filtered_df = df[(df['Technologie'] == techno_choice) & (df['Opérateur'] == operateur_choice)]
        debits = sorted(filtered_df['Débit'].dropna().unique())
        debit_choice = st.selectbox("Choisissez un débit (optionnel)", options=debits, key="debit_choice_2", index=debits.index('10M') if '10M' in debits else 0)

        df_filtered = filtered_df[filtered_df['Débit'] == debit_choice]
        if df_filtered.empty:
            st.warning("Aucune offre ne correspond aux critères sélectionnés.")
        else:
            nb_sites = df_filtered['Site'].nunique()
            st.markdown(f"### Nombre de sites éligibles à {operateur_choice} pour la techno {techno_choice} : {nb_sites}")

            colonnes = ['Site', 'Opérateur', 'Technologie', 'Débit', "Frais d'accès", 'Prix mensuel']
            st.dataframe(df_filtered[colonnes], use_container_width=True)

            output = BytesIO()
            df_filtered[colonnes].to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            st.download_button("📥 Télécharger le fichier Excel", data=output, file_name="offres_filtrees.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # --- Onglet 3 : Choix de la techno / opérateur / débit pour chaque site ---
    with onglets[2]:
        st.markdown("### Choix de la techno / opérateur / débit pour chaque site")

        sites = df['Site'].dropna().unique()
        result = pd.DataFrame({
            'Site': sites,
            'Technologie': [None] * len(sites),
            'Opérateur': [None] * len(sites),
            'Débit': [None] * len(sites),
            'Frais d\'accès': [None] * len(sites),
            'Prix mensuel': [None] * len(sites)
        })

        for i, site in enumerate(sites):
            technos = df[df['Site'] == site]['Technologie'].dropna().unique()
            techno_choice = st.selectbox(f"Technologie pour {site}", options=technos, key=f"techno_{i}")
            result.loc[i, 'Technologie'] = techno_choice

            operateurs = df[(df['Site'] == site) & (df['Technologie'] == techno_choice)]['Opérateur'].dropna().unique()
            operateur_choice = st.selectbox(f"Opérateur pour {site} ({techno_choice})", options=operateurs, key=f"operateur_{i}")
            result.loc[i, 'Opérateur'] = operateur_choice

            debits = df[(df['Site'] == site) & (df['Technologie'] == techno_choice) & (df['Opérateur'] == operateur_choice)]['Débit'].dropna().unique()
            debit_choice = st.selectbox(f"Débit pour {site} ({operateur_choice})", options=debits, key=f"debit_{i}")
            result.loc[i, 'Débit'] = debit_choice

            frais = df[(df['Site'] == site) & (df['Technologie'] == techno_choice) & (df['Opérateur'] == operateur_choice) & (df['Débit'] == debit_choice)]['Frais d\'accès'].values
            prix = df[(df['Site'] == site) & (df['Technologie'] == techno_choice) & (df['Opérateur'] == operateur_choice) & (df['Débit'] == debit_choice)]['Prix mensuel'].values

            result.loc[i, 'Frais d\'accès'] = frais[0] if len(frais) > 0 else 0
            result.loc[i, 'Prix mensuel'] = prix[0] if len(prix) > 0 else 0

        st.dataframe(result, use_container_width=True)

        output = BytesIO()
        result.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)
        st.download_button("📥 Télécharger le fichier Excel", data=output, file_name="resultat_par_site.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # --- Onglet 4 : Proginov ---
    with onglets[3]:
        st.markdown("### Proginov")

        df_filtered = df[df['Opérateur'] != 'COMPLETEL']

        technos = df_filtered['Technologie'].dropna().unique()
        techno_choice = st.selectbox("Choisissez une technologie", options=list(technos), key="techno_choice_proginov")

        engagement = st.slider("Durée d'engagement (mois)", 12, 60, step=12, value=36, key="engagement_proginov")

        filtered_df = df_filtered[df_filtered['Technologie'] == techno_choice]
        debits = sorted(filtered_df['Débit'].dropna().unique())
        debit_choice = st.selectbox("Choisissez un débit (optionnel)", options=debits, key="debit_choice_proginov")

        df_filtered = df_filtered[df_filtered['Débit'] == debit_choice]

        available_operators = df_filtered['Opérateur'].dropna().unique()
        operator_filter = {}
        for operator in available_operators:
            operator_filter[operator] = st.checkbox(f"Exclure {operator}", value=False, key=f"exclude_{operator}_proginov")

        excluded_operators = [operator for operator, exclude in operator_filter.items() if exclude]
        df_filtered = df_filtered[~df_filtered['Opérateur'].isin(excluded_operators)]

        # Fonction zone "ancienne"
        def assign_zone(row):
            if row['Technologie'] == 'FTTH':
                operateurs_site = df[(df['Site'] == row['Site']) & (df['Technologie'] == 'FTTH')]['Opérateur'].unique()
                if 'SFR' in operateurs_site and 'KOSC' in operateurs_site:
                    return 'SFR N10 Kosc N11'
                elif row['Opérateur'] == 'SFR':
                    return 'N10'
                elif row['Opérateur'] == 'KOSC':
                    return 'N11'
                elif row['Débit'] == '100/20(DG)M':
                    return 'N11'
            elif row['Technologie'] == 'FTTO':
                if row['Prix mensuel'] < 218:
                    return 'N1'
                elif 218 <= row['Prix mensuel'] < 300:
                    return 'N2'
                elif 300 <= row['Prix mensuel'] < 325:
                    return 'N3'
                elif 325 <= row['Prix mensuel'] < 355:
                    return 'N4'
                elif row['Prix mensuel'] >= 355:
                    return 'N5'
            return 'Non défini'

        df_filtered['Zone'] = df_filtered.apply(assign_zone, axis=1)

        if not df_filtered.empty:
            df_filtered['Frais d\'accès'] = df_filtered['Frais d\'accès'].fillna(0)
            df_filtered['Coût total'] = df_filtered['Prix mensuel'] * engagement + df_filtered['Frais d\'accès']
            best_offers = df_filtered.sort_values('Coût total').groupby('Site').first().reset_index()

            best_offers = best_offers[['Site', 'Technologie', 'Opérateur', 'CostArea', 'Débit', 'Frais d\'accès', 'Prix mensuel', 'Zone']]
            st.dataframe(best_offers, use_container_width=True)

    # --- Onglet 5 : Proginov nouvelle zone ---
    with onglets[4]:
        st.markdown("### Proginov nouvelle zone")

        # Même base que Proginov mais avec la nouvelle règle zone FTTO
        df_filtered = df[df['Opérateur'] != 'COMPLETEL']

        technos = df_filtered['Technologie'].dropna().unique()
        techno_choice = st.selectbox("Choisissez une technologie", options=list(technos), key="techno_choice_proginov_nouvelle")

        engagement = st.slider("Durée d'engagement (mois)", 12, 60, step=12, value=36, key="engagement_proginov_nouvelle")

        filtered_df = df_filtered[df_filtered['Technologie'] == techno_choice]
        debits = sorted(filtered_df['Débit'].dropna().unique())
        debit_choice = st.selectbox("Choisissez un débit (optionnel)", options=debits, key="debit_choice_proginov_nouvelle")

        df_filtered = df_filtered[df_filtered['Débit'] == debit_choice]

        available_operators = df_filtered['Opérateur'].dropna().unique()
        operator_filter = {}
        for operator in available_operators:
            operator_filter[operator] = st.checkbox(f"Exclure {operator}", value=False, key=f"exclude_{operator}_proginov_nouvelle")

        excluded_operators = [operator for operator, exclude in operator_filter.items() if exclude]
        df_filtered = df_filtered[~df_filtered['Opérateur'].isin(excluded_operators)]

        # Fonction zone nouvelle
        def assign_zone_nouvelle(row):
            if row['Technologie'] == 'FTTH':
                operateurs_site = df[(df['Site'] == row['Site']) & (df['Technologie'] == 'FTTH')]['Opérateur'].unique()
                if 'SFR' in operateurs_site and 'KOSC' in operateurs_site:
                    return 'SFR N10 Kosc N11'
                elif row['Opérateur'] == 'SFR':
                    return 'N10'
                elif row['Opérateur'] == 'KOSC':
                    return 'N11'
                elif row['Débit'] == '100/20(DG)M':
                    return 'N11'
            elif row['Technologie'] == 'FTTO':
                if row['Prix mensuel'] <= 180:
                    return 'N0'
                elif row['Prix mensuel'] <= 190:
                    return 'N1'
                elif row['Prix mensuel'] <= 215:
                    return 'N2'
                elif row['Prix mensuel'] <= 245:
                    return 'N3'
                elif row['Prix mensuel'] <= 280:
                    return 'N4'
                elif row['Prix mensuel'] <= 315:
                    return 'N5'
                elif row['Prix mensuel'] <= 365:
                    return 'N6'
                else:
                    return 'N7'
            return 'Non défini'

        df_filtered['Zone'] = df_filtered.apply(assign_zone_nouvelle, axis=1)

        if not df_filtered.empty:
            df_filtered['Frais d\'accès'] = df_filtered['Frais d\'accès'].fillna(0)
            df_filtered['Coût total'] = df_filtered['Prix mensuel'] * engagement + df_filtered['Frais d\'accès']
            best_offers = df_filtered.sort_values('Coût total').groupby('Site').first().reset_index()

            best_offers = best_offers[['Site', 'Technologie', 'Opérateur', 'CostArea', 'Débit', 'Frais d\'accès', 'Prix mensuel', 'Zone']]
            st.dataframe(best_offers, use_container_width=True)
