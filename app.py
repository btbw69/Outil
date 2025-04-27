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

    # Exclure les lignes où Already Fiber == 'AvailableSoon' ou 'UnderCommercialTerms'
    if 'Already Fiber' in df.columns:
        df = df[(df['Already Fiber'] != 'AvailableSoon') & (df['Already Fiber'] != 'UnderCommercialTerms')]

    # Remplacer les débits FTTH 1000M et 1000/200M par "1 gbits"
    df['Débit'] = df.apply(
        lambda row: '1 gbits' if row['Technologie'] == 'FTTH' and row['Débit'] in ['1000M', '1000/200M'] else row['Débit'],
        axis=1
    )

    # Initialisation des onglets
    onglets = st.tabs(["FAS/ABO le moins cher", "Site Eligible pour un opérateur", "Choix de la techno / opérateur / débit pour chaque site", "Proginov", "Proginov nouvelle zone"])

    # --- Premier onglet : "FAS/ABO le moins cher" ---
    with onglets[0]:
        st.markdown("### FAS/ABO le moins cher")

        required = ['Site', 'Opérateur', 'Technologie', 'Débit', 'Prix mensuel', "Frais d'accès"]
        missing_columns = [col for col in required if col not in df.columns]
        if missing_columns:
            st.error("Le fichier est invalide. Colonnes manquantes : " + ", ".join(missing_columns))
        else:
            technos = df['Technologie'].dropna().unique()
            techno_choice = st.selectbox("Choisissez une technologie", options=list(technos), key="techno_choice_1")

            engagement = st.slider("Durée d'engagement (mois)", 12, 60, 36, 12, key="engagement_1")

            filtered_df_for_debit = df[df['Technologie'] == techno_choice]
            debits = sorted(filtered_df_for_debit['Débit'].dropna().unique())
            debit_choice = st.selectbox("Choisissez un débit", options=debits, key="debit_choice_1")

            df_filtered = df[(df['Technologie'] == techno_choice) & (df['Débit'] == debit_choice)]

            if df_filtered.empty:
                st.warning("Aucune offre ne correspond aux critères.")
            else:
                df_filtered["Frais d'accès"] = df_filtered["Frais d'accès"].fillna(0)
                df_filtered['Coût total'] = df_filtered['Prix mensuel'] * engagement + df_filtered["Frais d'accès"]

                best_offers = df_filtered.sort_values('Coût total').groupby('Site').first().reset_index()
                nb_sites = best_offers['Site'].nunique()
                st.markdown(f"### Nombre de sites : {nb_sites}")

                if 'columns_visible' not in st.session_state:
                    st.session_state.columns_visible = True

                if st.button("Afficher/Masquer colonnes", key="button_1"):
                    st.session_state.columns_visible = not st.session_state.columns_visible

                colonnes_a_afficher = [col for col in df.columns if col not in ['NDI', 'INSEECode', 'rivoli code', 'Available Copper Pair', 'Needed Coppoer Pair']] if st.session_state.columns_visible else ['Site', "Frais d'accès", 'Prix mensuel']

                st.dataframe(best_offers[colonnes_a_afficher], use_container_width=True)

                output = BytesIO()
                best_offers[colonnes_a_afficher].to_excel(output, index=False, engine='openpyxl')
                output.seek(0)
                st.download_button("📥 Télécharger Excel", data=output, file_name="meilleures_offres.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # --- Deuxième onglet : "Site Eligible pour un opérateur" ---
    with onglets[1]:
        st.markdown("### Site Eligible pour un opérateur")

        technos = df['Technologie'].dropna().unique()
        techno_choice = st.selectbox("Technologie", options=list(technos), key="techno_choice_2")

        operateurs = df[df['Technologie'] == techno_choice]['Opérateur'].dropna().unique()
        operateur_choice = st.selectbox("Opérateur", options=list(operateurs), key="operateur_choice_2")

        filtered_df_for_debit = df[df['Technologie'] == techno_choice]
        debits = sorted(filtered_df_for_debit['Débit'].dropna().unique())
        debit_choice = st.selectbox("Débit", options=debits, key="debit_choice_2", index=debits.index('10M') if '10M' in debits else 0)

        df_filtered = df[(df['Technologie'] == techno_choice) & (df['Opérateur'] == operateur_choice) & (df['Débit'] == debit_choice)]

        if df_filtered.empty:
            st.warning("Aucune offre.")
        else:
            nb_sites_operateur = df_filtered['Site'].nunique()
            st.markdown(f"### Sites : {nb_sites_operateur}")

            colonnes = ['Site', 'Opérateur', 'Technologie', 'Débit', "Frais d'accès", 'Prix mensuel']
            st.dataframe(df_filtered[colonnes], use_container_width=True)

            output = BytesIO()
            df_filtered[colonnes].to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            st.download_button("📥 Télécharger Excel", data=output, file_name="offres_filtrees.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # --- Troisième onglet : "Choix de la techno / opérateur / débit pour chaque site" ---
    with onglets[2]:
        st.markdown("### Choix de la techno / opérateur / débit pour chaque site")

        sites = df['Site'].dropna().unique()
        result = pd.DataFrame({
            'Site': sites,
            'Technologie': [None] * len(sites),
            'Opérateur': [None] * len(sites),
            'Débit': [None] * len(sites),
            "Frais d'accès": [None] * len(sites),
            'Prix mensuel': [None] * len(sites)
        })

        for i, site in enumerate(sites):
            technos_disponibles = df[df['Site'] == site]['Technologie'].dropna().unique()
            techno_choice = st.selectbox(f"Technologie pour {site}", options=technos_disponibles, key=f"techno_{i}")
            result.loc[i, 'Technologie'] = techno_choice

            operateurs_dispo = df[(df['Site'] == site) & (df['Technologie'] == techno_choice)]['Opérateur'].dropna().unique()
            operateur_choice = st.selectbox(f"Opérateur pour {site}", options=operateurs_dispo, key=f"operateur_{i}")
            result.loc[i, 'Opérateur'] = operateur_choice

            debits_dispo = df[(df['Site'] == site) & (df['Technologie'] == techno_choice) & (df['Opérateur'] == operateur_choice)]['Débit'].dropna().unique()
            debit_choice = st.selectbox(f"Débit pour {site}", options=debits_dispo, key=f"debit_{i}")
            result.loc[i, 'Débit'] = debit_choice

            frais = df[(df['Site'] == site) & (df['Technologie'] == techno_choice) & (df['Opérateur'] == operateur_choice) & (df['Débit'] == debit_choice)]["Frais d'accès"].values
            prix = df[(df['Site'] == site) & (df['Technologie'] == techno_choice) & (df['Opérateur'] == operateur_choice) & (df['Débit'] == debit_choice)]['Prix mensuel'].values

            result.loc[i, "Frais d'accès"] = frais[0] if len(frais) > 0 else 0
            result.loc[i, 'Prix mensuel'] = prix[0] if len(prix) > 0 else 0

        st.dataframe(result, use_container_width=True)

        output = BytesIO()
        result.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)
        st.download_button("📥 Télécharger Excel", data=output, file_name="resultat_par_site.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # --- Quatrième et Cinquième onglets : "Proginov" + "Proginov nouvelle zone" ---
    def onglet_proginov(df_filtered, key_prefix, file_name, titre):
        st.markdown(f"### {titre}")

        df_filtered = df_filtered[df_filtered['Opérateur'] != 'COMPLETEL']

        technos = df_filtered['Technologie'].dropna().unique()
        techno_choice = st.selectbox("Technologie", options=list(technos), key=f"techno_choice_{key_prefix}")

        engagement = st.slider("Durée d'engagement (mois)", 12, 60, 36, 12, key=f"engagement_{key_prefix}")

        filtered_df_for_debit = df_filtered[df_filtered['Technologie'] == techno_choice]
        debits = sorted(filtered_df_for_debit['Débit'].dropna().unique())
        debit_choice = st.selectbox("Débit", options=debits, key=f"debit_choice_{key_prefix}")

        df_filtered = df_filtered[(df_filtered['Technologie'] == techno_choice) & (df_filtered['Débit'] == debit_choice)]

        available_operators = df_filtered['Opérateur'].dropna().unique()
        operator_filter = {op: st.checkbox(f"Exclure {op}", False, key=f"exclude_{op}_{key_prefix}") for op in available_operators}
        excluded = [op for op, val in operator_filter.items() if val]
        df_filtered = df_filtered[~df_filtered['Opérateur'].isin(excluded)]

        def assign_zone(row):
            if row['Technologie'] == 'FTTH':
                ops = df[(df['Site'] == row['Site']) & (df['Technologie'] == 'FTTH')]['Opérateur'].unique()
                if 'SFR' in ops and 'KOSC' in ops:
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
            st.warning("Aucune offre disponible.")
        else:
            df_filtered["Frais d'accès"] = df_filtered["Frais d'accès"].fillna(0)
            df_filtered['Coût total'] = df_filtered['Prix mensuel'] * engagement + df_filtered["Frais d'accès"]

            best_offers = df_filtered.sort_values('Coût total').groupby('Site').first().reset_index()

            nb_sites = best_offers['Site'].nunique()
            st.markdown(f"### Nombre de sites : {nb_sites}")

            colonnes = ['Site', 'Technologie', 'Opérateur', 'costArea', 'Débit', "Frais d'accès", 'Prix mensuel', 'Zone']
            st.dataframe(best_offers[colonnes], use_container_width=True)

            output = BytesIO()
            best_offers[colonnes].to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            st.download_button("📥 Télécharger Excel", data=output, file_name=file_name, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with onglets[3]:
        onglet_proginov(df.copy(), "proginov", "meilleures_offres_proginov.xlsx", "Proginov")

    with onglets[4]:
        onglet_proginov(df.copy(), "proginov_new", "meilleures_offres_proginov_nouvelle_zone.xlsx", "Proginov nouvelle zone")
