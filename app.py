import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Exploitation des données d'éligibilité", layout="wide")
st.title("Exploitation des données d'éligibilité")

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
        'CRMSellPrice': 'Prix mensuel',
        'CostArea': 'CostArea'
    }

    df = df.rename(columns=column_mapping)

    # Exclure certaines lignes
    if 'Already Fiber' in df.columns:
        df = df[(df['Already Fiber'] != 'AvailableSoon') & (df['Already Fiber'] != 'UnderCommercialTerms')]

    # Harmonisation du débit
    df['Débit'] = df.apply(
        lambda row: '1 gbits' if row['Technologie'] == 'FTTH' and row['Débit'] in ['1000M', '1000/200M'] else row['Débit'],
        axis=1
    )

    onglets = st.tabs([
        "FAS/ABO le moins cher", 
        "Site Eligible pour un opérateur", 
        "Choix de la techno / opérateur / débit pour chaque site", 
        "proginov",
        "proginov nouvelle zone"
    ])

    # --- Onglet 1 ---
    with onglets[0]:
        st.markdown("### FAS/ABO le moins cher")
        required = ['Site', 'Opérateur', 'Technologie', 'Débit', 'Prix mensuel', "Frais d'accès"]
        missing_columns = [col for col in required if col not in df.columns]
        if missing_columns:
            st.error("Le fichier est invalide. Colonnes manquantes : " + ", ".join(missing_columns))
        else:
            technos = df['Technologie'].dropna().unique()
            techno_choice = st.selectbox("Choisissez une technologie", options=list(technos), key="techno_choice_1")
            engagement = st.slider("Durée d'engagement (mois)", 12, 60, step=12, value=36, key="engagement_1")
            filtered_df_for_debit = df[df['Technologie'] == techno_choice]
            debit_options = sorted(filtered_df_for_debit['Débit'].dropna().unique())
            debit_choice = st.selectbox("Choisissez un débit", options=debit_options, key="debit_choice_1")

            df_filtered = df[(df['Technologie'] == techno_choice) & (df['Débit'] == debit_choice)]

            if df_filtered.empty:
                st.warning("Aucune offre correspondante.")
            else:
                df_filtered["Frais d'accès"] = df_filtered["Frais d'accès"].fillna(0)
                df_filtered['Coût total'] = df_filtered['Prix mensuel'] * engagement + df_filtered["Frais d'accès"]
                best_offers = df_filtered.sort_values('Coût total').groupby('Site').first().reset_index()
                nb_sites = best_offers['Site'].nunique()
                st.markdown(f"### Nombre de sites éligibles : {nb_sites}")

                if 'columns_visible' not in st.session_state:
                    st.session_state.columns_visible = True

                if st.button("Basculer l'affichage des colonnes", key="button_1"):
                    st.session_state.columns_visible = not st.session_state.columns_visible

                colonnes_a_afficher = ([
                    col for col in df.columns if col not in ['NDI', 'INSEECode', 'rivoli code', 'Available Copper Pair', 'Needed Coppoer Pair']
                ] if st.session_state.columns_visible else ['Site', "Frais d'accès", 'Prix mensuel'])

                st.dataframe(best_offers[colonnes_a_afficher], use_container_width=True)

                output = BytesIO()
                best_offers[colonnes_a_afficher].to_excel(output, index=False, engine='openpyxl')
                output.seek(0)
                st.download_button(
                    label="📥 Télécharger Excel",
                    data=output,
                    file_name="meilleures_offres.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    # --- Onglet 2 ---
    with onglets[1]:
        st.markdown("### Site Eligible pour un opérateur")

        techno_choice = st.selectbox("Choisissez une technologie", df['Technologie'].dropna().unique(), key="techno_choice_2")
        operateur_choice = st.selectbox("Choisissez un opérateur", df[df['Technologie'] == techno_choice]['Opérateur'].dropna().unique(), key="operateur_choice_2")
        debit_options = sorted(df[df['Technologie'] == techno_choice]['Débit'].dropna().unique())
        debit_choice = st.selectbox("Choisissez un débit", debit_options, key="debit_choice_2", index=debit_options.index('10M') if '10M' in debit_options else 0)

        df_filtered = df[(df['Technologie'] == techno_choice) & (df['Opérateur'] == operateur_choice) & (df['Débit'] == debit_choice)]

        if df_filtered.empty:
            st.warning("Aucune offre correspondante.")
        else:
            nb_sites_operateur = df_filtered['Site'].nunique()
            st.markdown(f"### Nombre de sites : {nb_sites_operateur}")
            colonnes = ['Site', 'Opérateur', 'Technologie', 'Débit', "Frais d'accès", 'Prix mensuel']
            st.dataframe(df_filtered[colonnes], use_container_width=True)

            output = BytesIO()
            df_filtered[colonnes].to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            st.download_button(
                label="📥 Télécharger Excel",
                data=output,
                file_name="offres_filtrees.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # --- Onglet 3 ---
    with onglets[2]:
        st.markdown("### Choix de la techno / opérateur / débit pour chaque site")
        sites = df['Site'].dropna().unique()
        result = pd.DataFrame({'Site': sites, 'Technologie': None, 'Opérateur': None, 'Débit': None, "Frais d'accès": None, 'Prix mensuel': None})

        for i, site in enumerate(sites):
            technos = df[df['Site'] == site]['Technologie'].dropna().unique()
            techno_choice = st.selectbox(f"{site} - Technologie", technos, key=f"techno_{i}")
            result.loc[i, 'Technologie'] = techno_choice

            operateurs = df[(df['Site'] == site) & (df['Technologie'] == techno_choice)]['Opérateur'].dropna().unique()
            operateur_choice = st.selectbox(f"{site} - Opérateur", operateurs, key=f"operateur_{i}")
            result.loc[i, 'Opérateur'] = operateur_choice

            debits = df[(df['Site'] == site) & (df['Technologie'] == techno_choice) & (df['Opérateur'] == operateur_choice)]['Débit'].dropna().unique()
            debit_choice = st.selectbox(f"{site} - Débit", debits, key=f"debit_{i}")
            result.loc[i, 'Débit'] = debit_choice

            filtre = df[
                (df['Site'] == site) &
                (df['Technologie'] == techno_choice) &
                (df['Opérateur'] == operateur_choice) &
                (df['Débit'] == debit_choice)
            ]
            result.loc[i, "Frais d'accès"] = filtre["Frais d'accès"].values[0] if not filtre.empty else 0
            result.loc[i, "Prix mensuel"] = filtre["Prix mensuel"].values[0] if not filtre.empty else 0

        st.dataframe(result, use_container_width=True)

        output = BytesIO()
        result.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)
        st.download_button(
            label="📥 Télécharger Excel",
            data=output,
            file_name="resultat_par_site.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # --- Onglet 4 : Proginov ---
    with onglets[3]:
        st.markdown("### Proginov")

        df_filtered = df[df['Opérateur'] != 'COMPLETEL']
        techno_choice = st.selectbox("Technologie", df_filtered['Technologie'].dropna().unique(), key="techno_choice_proginov")
        engagement = st.slider("Engagement (mois)", 12, 60, 36, 12, key="engagement_proginov")
        debit_choice = st.selectbox("Débit", sorted(df_filtered[df_filtered['Technologie'] == techno_choice]['Débit'].dropna().unique()), key="debit_choice_proginov")

        df_filtered = df_filtered[(df_filtered['Technologie'] == techno_choice) & (df_filtered['Débit'] == debit_choice)]

        available_operators = df_filtered['Opérateur'].dropna().unique()
        operator_filter = {op: st.checkbox(f"Exclure {op}", value=False) for op in available_operators}
        excluded_operators = [op for op, val in operator_filter.items() if val]
        df_filtered = df_filtered[~df_filtered['Opérateur'].isin(excluded_operators)]

        def assign_zone(row):
            if row['Technologie'] == 'FTTH':
                operateurs_site = df[(df['Site'] == row['Site']) & (df['Technologie'] == 'FTTH')]['Opérateur'].unique()
                if 'SFR' in operateurs_site and 'KOSC' in operateurs_site:
                    return 'SFR N10 Kosc N11'
                if row['Opérateur'] == 'SFR':
                    return 'N10'
                if row['Opérateur'] == 'KOSC':
                    return 'N11'
                if row['Débit'] == '100/20(DG)M':
                    return 'N11'
            elif row['Technologie'] == 'FTTO':
                prix = row['Prix mensuel']
                if prix < 218: return 'N1'
                if prix < 300: return 'N2'
                if prix < 325: return 'N3'
                if prix < 355: return 'N4'
                return 'N5'
            return 'Non défini'

        df_filtered['Zone'] = df_filtered.apply(assign_zone, axis=1)

        if not df_filtered.empty:
            df_filtered["Frais d'accès"] = df_filtered["Frais d'accès"].fillna(0)
            df_filtered['Coût total'] = df_filtered['Prix mensuel'] * engagement + df_filtered["Frais d'accès"]
            best_offers = df_filtered.sort_values('Coût total').groupby('Site').first().reset_index()

            nb_sites = best_offers['Site'].nunique()
            st.markdown(f"### Sites éligibles : {nb_sites}")

            best_offers_reduits = best_offers[['Site', 'Technologie', 'Opérateur', 'CostArea', 'Débit', 'Frais d\'accès', 'Prix mensuel', 'Zone']]
            st.dataframe(best_offers_reduits, use_container_width=True)

            output = BytesIO()
            best_offers_reduits.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            st.download_button(
                label="📥 Télécharger Excel",
                data=output,
                file_name="meilleures_offres_proginov.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    # --- Onglet 5 : Proginov Nouvelle Zone ---
    with onglets[4]:
        st.markdown("### Proginov Nouvelle Zone")

        df_filtered = df[df['Opérateur'] != 'COMPLETEL']
        techno_choice = st.selectbox("Technologie", df_filtered['Technologie'].dropna().unique(), key="techno_choice_proginov_nouvelle")
        engagement = st.slider("Engagement (mois)", 12, 60, 36, 12, key="engagement_proginov_nouvelle")
        debit_choice = st.selectbox("Débit", sorted(df_filtered[df_filtered['Technologie'] == techno_choice]['Débit'].dropna().unique()), key="debit_choice_proginov_nouvelle")

        df_filtered = df_filtered[(df_filtered['Technologie'] == techno_choice) & (df_filtered['Débit'] == debit_choice)]

        available_operators = df_filtered['Opérateur'].dropna().unique()
        operator_filter = {op: st.checkbox(f"Exclure {op}", value=False, key=f"exclude_{op}_nouvelle") for op in available_operators}
        excluded_operators = [op for op, val in operator_filter.items() if val]
        df_filtered = df_filtered[~df_filtered['Opérateur'].isin(excluded_operators)]

        def assign_new_zone(row):
            prix = row['Prix mensuel']
            if prix <= 180: return 'N0'
            if prix <= 190: return 'N1'
            if prix <= 215: return 'N2'
            if prix <= 245: return 'N3'
            if prix <= 280: return 'N4'
            if prix <= 315: return 'N5'
            if prix <= 365: return 'N6'
            return 'N7'

        df_filtered['Zone'] = df_filtered.apply(assign_new_zone, axis=1)

        if not df_filtered.empty:
            df_filtered["Frais d'accès"] = df_filtered["Frais d'accès"].fillna(0)
            df_filtered['Coût total'] = df_filtered['Prix mensuel'] * engagement + df_filtered["Frais d'accès"]
            best_offers = df_filtered.sort_values('Coût total').groupby('Site').first().reset_index()

            nb_sites = best_offers['Site'].nunique()
            st.markdown(f"### Sites éligibles : {nb_sites}")

            best_offers_reduits = best_offers[['Site', 'Technologie', 'Opérateur', 'CostArea', 'Débit', 'Frais d\'accès', 'Prix mensuel', 'Zone']]
            st.dataframe(best_offers_reduits, use_container_width=True)

            output = BytesIO()
            best_offers_reduits.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            st.download_button(
                label="📥 Télécharger Excel",
                data=output,
                file_name="meilleures_offres_proginov_nouvelle_zone.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
