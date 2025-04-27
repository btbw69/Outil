import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Exploitation des données d'éligibilité", layout="wide")
st.title("Exploitation des données d'éligibilité")

uploaded_file = st.file_uploader("Téléversez le fichier d'offres", type=[".xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # Mapping manuel
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

    # Nettoyage
    if 'Already Fiber' in df.columns:
        df = df[~df['Already Fiber'].isin(['AvailableSoon', 'UnderCommercialTerms'])]

    df['Débit'] = df.apply(
        lambda row: '1 gbits' if row['Technologie'] == 'FTTH' and row['Débit'] in ['1000M', '1000/200M'] else row['Débit'],
        axis=1
    )

    onglets = st.tabs([
        "FAS/ABO le moins cher",
        "Site Eligible pour un opérateur",
        "Choix de la techno / opérateur / débit pour chaque site",
        "proginov",
        "Proginov nouvelle zone"
    ])

    # --- 1. FAS/ABO le moins cher ---
    with onglets[0]:
        st.markdown("### FAS/ABO le moins cher")

        required = ['Site', 'Opérateur', 'Technologie', 'Débit', 'Prix mensuel', "Frais d'accès"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            st.error("Colonnes manquantes : " + ", ".join(missing))
        else:
            technos = df['Technologie'].dropna().unique()
            techno_choice = st.selectbox("Technologie", options=technos, key="techno_1")
            engagement = st.slider("Engagement (mois)", 12, 60, 36, 12, key="engagement_1")

            df_filtered = df[df['Technologie'] == techno_choice]
            debits = sorted(df_filtered['Débit'].dropna().unique())
            debit_choice = st.selectbox("Débit", options=debits, key="debit_1")

            df_filtered = df_filtered[df_filtered['Débit'] == debit_choice]

            if df_filtered.empty:
                st.warning("Aucune offre trouvée.")
            else:
                df_filtered["Frais d'accès"] = df_filtered["Frais d'accès"].fillna(0)
                df_filtered['Coût total'] = df_filtered['Prix mensuel'] * engagement + df_filtered["Frais d'accès"]
                best_offers = df_filtered.sort_values('Coût total').groupby('Site').first().reset_index()

                st.markdown(f"### {best_offers['Site'].nunique()} sites éligibles")

                colonnes = ['Site', 'Opérateur', 'Technologie', 'Débit', "Frais d'accès", 'Prix mensuel']
                st.dataframe(best_offers[colonnes], use_container_width=True)

                output = BytesIO()
                best_offers[colonnes].to_excel(output, index=False)
                output.seek(0)
                st.download_button("📥 Télécharger Excel", data=output, file_name="meilleures_offres.xlsx")

    # --- 2. Site Eligible pour un opérateur ---
    with onglets[1]:
        st.markdown("### Site Eligible pour un opérateur")

        technos = df['Technologie'].dropna().unique()
        techno_choice = st.selectbox("Technologie", options=technos, key="techno_2")

        operateurs = df[df['Technologie'] == techno_choice]['Opérateur'].dropna().unique()
        operateur_choice = st.selectbox("Opérateur", options=operateurs, key="operateur_2")

        df_filtered = df[
            (df['Technologie'] == techno_choice) &
            (df['Opérateur'] == operateur_choice)
        ]
        debits = sorted(df_filtered['Débit'].dropna().unique())
        debit_choice = st.selectbox("Débit", options=debits, key="debit_2")

        df_filtered = df_filtered[df_filtered['Débit'] == debit_choice]

        if df_filtered.empty:
            st.warning("Aucune offre trouvée.")
        else:
            colonnes = ['Site', 'Opérateur', 'Technologie', 'Débit', "Frais d'accès", 'Prix mensuel']
            st.dataframe(df_filtered[colonnes], use_container_width=True)

            output = BytesIO()
            df_filtered[colonnes].to_excel(output, index=False)
            output.seek(0)
            st.download_button("📥 Télécharger Excel", data=output, file_name="offres_filtrees.xlsx")

    # --- 3. Choix techno / opérateur / débit par site ---
    with onglets[2]:
        st.markdown("### Choix de la techno / opérateur / débit par site")

        sites = df['Site'].dropna().unique()
        result = pd.DataFrame(columns=['Site', 'Technologie', 'Opérateur', 'Débit', "Frais d'accès", 'Prix mensuel'])

        for site in sites:
            technos = df[df['Site'] == site]['Technologie'].dropna().unique()
            techno_choice = st.selectbox(f"Technologie ({site})", options=technos, key=f"techno_{site}")

            operateurs = df[(df['Site'] == site) & (df['Technologie'] == techno_choice)]['Opérateur'].dropna().unique()
            operateur_choice = st.selectbox(f"Opérateur ({site})", options=operateurs, key=f"operateur_{site}")

            debits = df[
                (df['Site'] == site) &
                (df['Technologie'] == techno_choice) &
                (df['Opérateur'] == operateur_choice)
            ]['Débit'].dropna().unique()
            debit_choice = st.selectbox(f"Débit ({site})", options=debits, key=f"debit_{site}")

            offre = df[
                (df['Site'] == site) &
                (df['Technologie'] == techno_choice) &
                (df['Opérateur'] == operateur_choice) &
                (df['Débit'] == debit_choice)
            ].iloc[0]

            result = pd.concat([result, pd.DataFrame({
                'Site': [site],
                'Technologie': [techno_choice],
                'Opérateur': [operateur_choice],
                'Débit': [debit_choice],
                "Frais d'accès": [offre["Frais d'accès"]],
                "Prix mensuel": [offre["Prix mensuel"]]
            })])

        st.dataframe(result, use_container_width=True)

        output = BytesIO()
        result.to_excel(output, index=False)
        output.seek(0)
        st.download_button("📥 Télécharger Excel", data=output, file_name="resultat_par_site.xlsx")

    # Fonction d'assignation de zone pour Proginov
    def assign_zone(row):
        if row['Technologie'] == 'FTTH':
            ops_site = df[(df['Site'] == row['Site']) & (df['Technologie'] == 'FTTH')]['Opérateur'].unique()
            if 'SFR' in ops_site and 'KOSC' in ops_site:
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

    # --- Quatrième onglet : "proginov" ---
    with onglets[3]:
        st.markdown("### Proginov")

        # Exclure l'opérateur EuroFiber
        df_filtered = df[df['Opérateur'] != 'COMPLETEL']

        technos = df_filtered['Technologie'].dropna().unique()
        techno_choice = st.selectbox("Choisissez une technologie", options=list(technos), key="techno_choice_proginov")

        engagement = st.slider("Durée d'engagement (mois)", min_value=12, max_value=60, step=12, value=36, key="engagement_proginov")

        filtered_df_for_debit = df_filtered[df_filtered['Technologie'] == techno_choice]

        debits = sorted(filtered_df_for_debit['Débit'].dropna().unique())
        debit_options = list(debits)

        debit_choice = st.selectbox("Choisissez un débit (optionnel)", options=debit_options, key="debit_choice_proginov")

        # Application des filtres (sans filtrer par engagement)
        df_filtered = df_filtered[df_filtered['Technologie'] == techno_choice]
        df_filtered = df_filtered[df_filtered['Débit'] == debit_choice]

        # Sélectionner les opérateurs disponibles
        available_operators = df_filtered['Opérateur'].dropna().unique()

        # Création d'un dictionnaire pour stocker les cases à cocher pour chaque opérateur
        operator_filter = {}
        for operator in available_operators:
            operator_filter[operator] = st.checkbox(f"Exclure {operator}", value=False)

        # Exclure les opérateurs sélectionnés
        excluded_operators = [operator for operator, exclude in operator_filter.items() if exclude]
        df_filtered = df_filtered[~df_filtered['Opérateur'].isin(excluded_operators)]

        # Calcul de la zone
        def assign_zone(row):
            if row['Technologie'] == 'FTTH':
                # Vérifier si le site est éligible à SFR et Kosc
                operateurs_du_site = df[(df['Site'] == row['Site']) & (df['Technologie'] == 'FTTH')]['Opérateur'].unique()

                if 'SFR' in operateurs_du_site and 'KOSC' in operateurs_du_site:
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

            best_offers_reduits = best_offers[['Site', 'Technologie', 'Opérateur', 'costArea', 'Débit', 'Frais d\'accès', 'Prix mensuel', 'Zone']]

            st.subheader("Meilleures offres par site")
            st.dataframe(best_offers_reduits, use_container_width=True)

            # Export Excel
            output = BytesIO()
            best_offers_reduits.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            st.download_button(
                label="📥 Télécharger le fichier Excel",
                data=output,
                file_name="meilleures_offres_proginov.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # --- 5. Onglet Proginov nouvelle zone ---
    with onglets[4]:
        st.markdown("### Proginov nouvelle zone")

                # Exclure l'opérateur EuroFiber
        df_filtered = df[df['Opérateur'] != 'COMPLETEL']

        technos = df_filtered['Technologie'].dropna().unique()
        techno_choice = st.selectbox("Choisissez une technologie", options=list(technos), key="techno_choice_proginov")

        engagement = st.slider("Durée d'engagement (mois)", min_value=12, max_value=60, step=12, value=36, key="engagement_proginov")

        filtered_df_for_debit = df_filtered[df_filtered['Technologie'] == techno_choice]

        debits = sorted(filtered_df_for_debit['Débit'].dropna().unique())
        debit_options = list(debits)

        debit_choice = st.selectbox("Choisissez un débit (optionnel)", options=debit_options, key="debit_choice_proginov")

        # Application des filtres (sans filtrer par engagement)
        df_filtered = df_filtered[df_filtered['Technologie'] == techno_choice]
        df_filtered = df_filtered[df_filtered['Débit'] == debit_choice]

        # Sélectionner les opérateurs disponibles
        available_operators = df_filtered['Opérateur'].dropna().unique()

        # Création d'un dictionnaire pour stocker les cases à cocher pour chaque opérateur
        operator_filter = {}
        for operator in available_operators:
            operator_filter[operator] = st.checkbox(f"Exclure {operator}", value=False)

        # Exclure les opérateurs sélectionnés
        excluded_operators = [operator for operator, exclude in operator_filter.items() if exclude]
        df_filtered = df_filtered[~df_filtered['Opérateur'].isin(excluded_operators)]

        # Calcul de la zone
        def assign_zone(row):
            if row['Technologie'] == 'FTTH':
                # Vérifier si le site est éligible à SFR et Kosc
                operateurs_du_site = df[(df['Site'] == row['Site']) & (df['Technologie'] == 'FTTH')]['Opérateur'].unique()

                if 'SFR' in operateurs_du_site and 'KOSC' in operateurs_du_site:
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

            best_offers_reduits = best_offers[['Site', 'Technologie', 'Opérateur', 'costArea', 'Débit', 'Frais d\'accès', 'Prix mensuel', 'Zone']]

            st.subheader("Meilleures offres par site")
            st.dataframe(best_offers_reduits, use_container_width=True)

            # Export Excel
            output = BytesIO()
            best_offers_reduits.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            st.download_button(
                label="📥 Télécharger le fichier Excel",
                data=output,
                file_name="meilleures_offres_proginov.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
