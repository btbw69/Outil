import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(page_title="Exploitation des données d'éligibilité", layout="wide")
st.title("Exploitation des données d'éligibilité")

uploaded_file = st.file_uploader("Téléversez le fichier d'offres", type=[".xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # Mapping manuel à partir des noms réels
    column_mapping = {
        'Name': 'Site',
        'OBL': 'Opérateur',
        'Type Physical Link': 'Technologie',
        'bandwidth': 'Débit',
        'FASSellPrice': "Frais d'accès",
        'CRMSellPrice': 'Prix mensuel',
        'CostArea': 'costArea'  # attention au c minuscule et A majuscule
    }
    df = df.rename(columns=column_mapping)

    # Exclure certaines lignes
    if 'Already Fiber' in df.columns:
        df = df[(df['Already Fiber'] != 'AvailableSoon') & (df['Already Fiber'] != 'UnderCommercialTerms')]

    # Correction débit FTTH
    df['Débit'] = df.apply(
        lambda row: '1 gbits' if row['Technologie'] == 'FTTH' and row['Débit'] in ['1000M', '1000/200M'] else row['Débit'],
        axis=1
    )

    # Initialisation des onglets
    onglets = st.tabs([
        "FAS/ABO le moins cher",
        "Site Eligible pour un opérateur",
        "Choix de la techno / opérateur / débit pour chaque site",
        "Proginov",
        "Proginov nouvelle zone"
    ])

    # --- Onglet 1 ---
    with onglets[0]:
        st.markdown("### FAS/ABO le moins cher")

        required = ['Site', 'Opérateur', 'Technologie', 'Débit', 'Prix mensuel', "Frais d'accès"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            st.error(f"Colonnes manquantes : {', '.join(missing)}")
        else:
            technos = df['Technologie'].dropna().unique()
            techno_choice = st.selectbox("Technologie", options=technos, key="techno1")
            engagement = st.slider("Engagement (mois)", 12, 60, step=12, value=36, key="engagement1")

            filtered = df[df['Technologie'] == techno_choice]
            debits = sorted(filtered['Débit'].dropna().unique())
            debit_choice = st.selectbox("Débit", options=debits, key="debit1")

            df_filtered = filtered[filtered['Débit'] == debit_choice]

            if df_filtered.empty:
                st.warning("Aucune offre trouvée.")
            else:
                df_filtered["Frais d'accès"] = df_filtered["Frais d'accès"].fillna(0)
                df_filtered['Coût total'] = df_filtered['Prix mensuel'] * engagement + df_filtered["Frais d'accès"]
                best_offers = df_filtered.sort_values('Coût total').groupby('Site').first().reset_index()

                nb_sites = best_offers['Site'].nunique()
                st.write(f"Nombre de sites éligibles : {nb_sites}")

                if 'visible1' not in st.session_state:
                    st.session_state.visible1 = True
                if st.button("Basculer affichage colonnes", key="btn1"):
                    st.session_state.visible1 = not st.session_state.visible1

                if st.session_state.visible1:
                    columns = [col for col in df.columns if col not in ['NDI', 'INSEECode', 'rivoli code', 'Available Copper Pair', 'Needed Coppoer Pair']]
                else:
                    columns = ['Site', "Frais d'accès", 'Prix mensuel']

                st.dataframe(best_offers[columns], use_container_width=True)

                output = BytesIO()
                best_offers[columns].to_excel(output, index=False, engine='openpyxl')
                output.seek(0)
                st.download_button("📥 Télécharger Excel", data=output, file_name="meilleures_offres.xlsx")

    # --- Onglet 2 ---
    with onglets[1]:
        st.markdown("### Site Eligible pour un opérateur")

        technos = df['Technologie'].dropna().unique()
        techno_choice = st.selectbox("Technologie", options=technos, key="techno2")
        operateurs = df[df['Technologie'] == techno_choice]['Opérateur'].dropna().unique()
        operateur_choice = st.selectbox("Opérateur", options=operateurs, key="operateur2")

        filtered = df[(df['Technologie'] == techno_choice) & (df['Opérateur'] == operateur_choice)]
        debits = sorted(filtered['Débit'].dropna().unique())
        debit_choice = st.selectbox("Débit", options=debits, key="debit2", index=debits.index('10M') if '10M' in debits else 0)

        df_filtered = filtered[filtered['Débit'] == debit_choice]

        if df_filtered.empty:
            st.warning("Aucune offre trouvée.")
        else:
            nb_sites = df_filtered['Site'].nunique()
            st.write(f"Nombre de sites éligibles : {nb_sites}")

            colonnes = ['Site', 'Opérateur', 'Technologie', 'Débit', "Frais d'accès", 'Prix mensuel']
            st.dataframe(df_filtered[colonnes], use_container_width=True)

            output = BytesIO()
            df_filtered[colonnes].to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            st.download_button("📥 Télécharger Excel", data=output, file_name="offres_filtrees.xlsx")

    # --- Onglet 3 ---
    with onglets[2]:
        st.markdown("### Choix de la techno / opérateur / débit pour chaque site")

        sites = df['Site'].dropna().unique()
        result = pd.DataFrame({'Site': sites})

        technos_list, operateurs_list, debits_list, frais_list, prix_list = [], [], [], [], []

        for i, site in enumerate(sites):
            technos = df[df['Site'] == site]['Technologie'].dropna().unique()
            techno = st.selectbox(f"Technologie pour {site}", options=technos, key=f"tech_{i}")
            technos_list.append(techno)

            operateurs = df[(df['Site'] == site) & (df['Technologie'] == techno)]['Opérateur'].dropna().unique()
            operateur = st.selectbox(f"Opérateur pour {site}", options=operateurs, key=f"op_{i}")
            operateurs_list.append(operateur)

            debits = df[(df['Site'] == site) & (df['Technologie'] == techno) & (df['Opérateur'] == operateur)]['Débit'].dropna().unique()
            debit = st.selectbox(f"Débit pour {site}", options=debits, key=f"debit_{i}")
            debits_list.append(debit)

            row = df[(df['Site'] == site) & (df['Technologie'] == techno) & (df['Opérateur'] == operateur) & (df['Débit'] == debit)]
            frais = row['Frais d\'accès'].values[0] if not row.empty else 0
            prix = row['Prix mensuel'].values[0] if not row.empty else 0
            frais_list.append(frais)
            prix_list.append(prix)

        result['Technologie'] = technos_list
        result['Opérateur'] = operateurs_list
        result['Débit'] = debits_list
        result['Frais d\'accès'] = frais_list
        result['Prix mensuel'] = prix_list

        st.dataframe(result, use_container_width=True)

        output = BytesIO()
        result.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)
        st.download_button("📥 Télécharger Excel", data=output, file_name="resultat_par_site.xlsx")

    # --- Onglet 4 ---
    with onglets[3]:
        st.markdown("### Proginov")

        df_filtered = df[df['Opérateur'] != 'COMPLETEL']

        techno_choice = st.selectbox("Technologie", options=df_filtered['Technologie'].dropna().unique(), key="techno_proginov")
        engagement = st.slider("Engagement (mois)", 12, 60, step=12, value=36, key="engagement_proginov")
        filtered = df_filtered[df_filtered['Technologie'] == techno_choice]
        debit_choice = st.selectbox("Débit", options=sorted(filtered['Débit'].dropna().unique()), key="debit_proginov")

        df_filtered = filtered[filtered['Débit'] == debit_choice]

        available_operators = df_filtered['Opérateur'].dropna().unique()
        operator_filter = {operator: st.checkbox(f"Exclure {operator}", value=False, key=f"exclure_{operator}_4") for operator in available_operators}
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
            elif row['Technologie'] == 'FTTO':
                if row['Prix mensuel'] < 218:
                    return 'N1'
                elif row['Prix mensuel'] < 300:
                    return 'N2'
                elif row['Prix mensuel'] < 325:
                    return 'N3'
                elif row['Prix mensuel'] < 355:
                    return 'N4'
                else:
                    return 'N5'
            return 'Non défini'

        df_filtered['Zone'] = df_filtered.apply(assign_zone, axis=1)

        if not df_filtered.empty:
            df_filtered["Frais d'accès"] = df_filtered["Frais d'accès"].fillna(0)
            df_filtered['Coût total'] = df_filtered['Prix mensuel'] * engagement + df_filtered["Frais d'accès"]
            best_offers = df_filtered.sort_values('Coût total').groupby('Site').first().reset_index()

            colonnes = ['Site', 'Technologie', 'Opérateur', 'Débit', "Frais d'accès", "Prix mensuel", "Zone"]
            if 'costArea' in best_offers.columns:
                colonnes.insert(3, 'costArea')

            st.dataframe(best_offers[colonnes], use_container_width=True)
            output = BytesIO()
best_offers[colonnes].to_excel(output, index=False, engine='openpyxl')
output.seek(0)
st.download_button(
    label="📥 Télécharger le fichier Excel",
    data=output,
    file_name="meilleures_offres_proginov.xlsx",  # pour l'onglet 4
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

    # --- Onglet 5 ---
    with onglets[4]:
        st.markdown("### Proginov nouvelle zone")

        df_filtered = df[df['Opérateur'] != 'COMPLETEL']

        techno_choice = st.selectbox("Technologie", options=df_filtered['Technologie'].dropna().unique(), key="techno_proginov_new")
        engagement = st.slider("Engagement (mois)", 12, 60, step=12, value=36, key="engagement_proginov_new")
        filtered = df_filtered[df_filtered['Technologie'] == techno_choice]
        debit_choice = st.selectbox("Débit", options=sorted(filtered['Débit'].dropna().unique()), key="debit_proginov_new")

        df_filtered = filtered[filtered['Débit'] == debit_choice]

        available_operators = df_filtered['Opérateur'].dropna().unique()
        operator_filter = {operator: st.checkbox(f"Exclure {operator}", value=False, key=f"exclure_{operator}_5") for operator in available_operators}
        excluded = [op for op, val in operator_filter.items() if val]
        df_filtered = df_filtered[~df_filtered['Opérateur'].isin(excluded)]

        def assign_zone_new(row):
            if row['Technologie'] == 'FTTH':
                ops = df[(df['Site'] == row['Site']) & (df['Technologie'] == 'FTTH')]['Opérateur'].unique()
                if 'SFR' in ops and 'KOSC' in ops:
                    return 'SFR N10 Kosc N11'
                elif row['Opérateur'] == 'SFR':
                    return 'N10'
                elif row['Opérateur'] == 'KOSC':
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

        df_filtered['Zone'] = df_filtered.apply(assign_zone_new, axis=1)

        if not df_filtered.empty:
            df_filtered["Frais d'accès"] = df_filtered["Frais d'accès"].fillna(0)
            df_filtered['Coût total'] = df_filtered['Prix mensuel'] * engagement + df_filtered["Frais d'accès"]
            best_offers = df_filtered.sort_values('Coût total').groupby('Site').first().reset_index()

            colonnes = ['Site', 'Technologie', 'Opérateur', 'Débit', "Frais d'accès", "Prix mensuel", "Zone"]
            if 'costArea' in best_offers.columns:
                colonnes.insert(3, 'costArea')

            st.dataframe(best_offers[colonnes], use_container_width=True)
            output = BytesIO()
best_offers[colonnes].to_excel(output, index=False, engine='openpyxl')
output.seek(0)
st.download_button(
    label="📥 Télécharger le fichier Excel",
    data=output,
    file_name="meilleures_offres_proginov_nouvelle_zone.xlsx",  # pour l'onglet 5
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
