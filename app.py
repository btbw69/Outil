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
        'CostArea': 'costArea'  # important c minuscule
    }
    df = df.rename(columns=column_mapping)

    # Exclusion des lignes Already Fiber
    if 'Already Fiber' in df.columns:
        df = df[(df['Already Fiber'] != 'AvailableSoon') & (df['Already Fiber'] != 'UnderCommercialTerms')]

    # Remplacement débit FTTH
    df['Débit'] = df.apply(
        lambda row: '1 gbits' if row['Technologie'] == 'FTTH' and row['Débit'] in ['1000M', '1000/200M'] else row['Débit'],
        axis=1
    )

    # Création des onglets
    onglets = st.tabs([
        "FAS/ABO le moins cher",
        "Site Eligible pour un opérateur",
        "Choix de la techno / opérateur / débit pour chaque site",
        "Proginov",
        "Proginov nouvelle zone"
    ])

    # Onglet 1 : FAS/ABO le moins cher
    with onglets[0]:
        st.markdown("### FAS/ABO le moins cher")
        required = ['Site', 'Opérateur', 'Technologie', 'Débit', 'Prix mensuel', "Frais d'accès"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            st.error(f"Colonnes manquantes : {', '.join(missing)}")
        else:
            technos = df['Technologie'].dropna().unique()
            techno_choice = st.selectbox("Technologie", options=technos, key="techno1")
            engagement = st.slider("Durée d'engagement", 12, 60, step=12, value=36, key="engagement1")
            df_filtered = df[df['Technologie'] == techno_choice]
            debits = sorted(df_filtered['Débit'].dropna().unique())
            debit_choice = st.selectbox("Débit", options=debits, key="debit1")
            df_filtered = df_filtered[df_filtered['Débit'] == debit_choice]
            if df_filtered.empty:
                st.warning("Aucune offre disponible.")
            else:
                df_filtered["Frais d'accès"] = df_filtered["Frais d'accès"].fillna(0)
                df_filtered["Coût total"] = df_filtered["Prix mensuel"] * engagement + df_filtered["Frais d'accès"]
                best = df_filtered.sort_values('Coût total').groupby('Site').first().reset_index()
                st.dataframe(best, use_container_width=True)
                output = BytesIO()
                best.to_excel(output, index=False, engine='openpyxl')
                output.seek(0)
                st.download_button("📥 Télécharger Excel", data=output, file_name="meilleures_offres.xlsx")

    # Onglet 2 : Site Eligible pour un opérateur
    with onglets[1]:
        st.markdown("### Site Eligible pour un opérateur")
        technos = df['Technologie'].dropna().unique()
        techno_choice = st.selectbox("Technologie", options=technos, key="techno2")
        operateurs = df[df['Technologie'] == techno_choice]['Opérateur'].dropna().unique()
        operateur_choice = st.selectbox("Opérateur", options=operateurs, key="operateur2")
        filtered = df[(df['Technologie'] == techno_choice) & (df['Opérateur'] == operateur_choice)]
        debits = sorted(filtered['Débit'].dropna().unique())
        debit_choice = st.selectbox("Débit", options=debits, key="debit2", index=debits.index('10M') if '10M' in debits else 0)
        filtered = filtered[filtered['Débit'] == debit_choice]
        if filtered.empty:
            st.warning("Aucune offre.")
        else:
            st.dataframe(filtered, use_container_width=True)
            output = BytesIO()
            filtered.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            st.download_button("📥 Télécharger Excel", data=output, file_name="offres_filtrees.xlsx")

    # Onglet 3 : Choix par site
    with onglets[2]:
        st.markdown("### Choix de la techno / opérateur / débit pour chaque site")
        sites = df['Site'].dropna().unique()
        result = pd.DataFrame({'Site': sites})
        techno_list, operateur_list, debit_list, frais_list, prix_list = [], [], [], [], []
        for i, site in enumerate(sites):
            technos = df[df['Site'] == site]['Technologie'].dropna().unique()
            techno = st.selectbox(f"Technologie {site}", options=technos, key=f"tech_{i}")
            operateurs = df[(df['Site'] == site) & (df['Technologie'] == techno)]['Opérateur'].dropna().unique()
            operateur = st.selectbox(f"Opérateur {site}", options=operateurs, key=f"op_{i}")
            debits = df[(df['Site'] == site) & (df['Technologie'] == techno) & (df['Opérateur'] == operateur)]['Débit'].dropna().unique()
            debit = st.selectbox(f"Débit {site}", options=debits, key=f"debit_{i}")
            ligne = df[(df['Site'] == site) & (df['Technologie'] == techno) & (df['Opérateur'] == operateur) & (df['Débit'] == debit)]
            frais = ligne["Frais d'accès"].values[0] if not ligne.empty else 0
            prix = ligne["Prix mensuel"].values[0] if not ligne.empty else 0
            techno_list.append(techno)
            operateur_list.append(operateur)
            debit_list.append(debit)
            frais_list.append(frais)
            prix_list.append(prix)
        result['Technologie'] = techno_list
        result['Opérateur'] = operateur_list
        result['Débit'] = debit_list
        result["Frais d'accès"] = frais_list
        result["Prix mensuel"] = prix_list
        st.dataframe(result, use_container_width=True)
        output = BytesIO()
        result.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)
        st.download_button("📥 Télécharger Excel", data=output, file_name="choix_site.xlsx")

    # Onglet 4 : Proginov (ancienne zone)
    with onglets[3]:
        st.markdown("### Proginov")
        df_filtered = df[df['Opérateur'] != 'COMPLETEL']
        techno_choice = st.selectbox("Technologie", options=df_filtered['Technologie'].dropna().unique(), key="techno4")
        engagement = st.slider("Engagement", 12, 60, step=12, value=36, key="engagement4")
        debit_choice = st.selectbox("Débit", options=sorted(df_filtered[df_filtered['Technologie'] == techno_choice]['Débit'].dropna().unique()), key="debit4")
        df_filtered = df_filtered[(df_filtered['Technologie'] == techno_choice) & (df_filtered['Débit'] == debit_choice)]
        available_operators = df_filtered['Opérateur'].dropna().unique()
        excluded_ops = [op for op in available_operators if st.checkbox(f"Exclure {op}", key=f"exc4_{op}")]
        df_filtered = df_filtered[~df_filtered['Opérateur'].isin(excluded_ops)]

        def zone_classic(row):
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

        df_filtered['Zone'] = df_filtered.apply(zone_classic, axis=1)
        df_filtered["Frais d'accès"] = df_filtered["Frais d'accès"].fillna(0)
        df_filtered['Coût total'] = df_filtered['Prix mensuel'] * engagement + df_filtered["Frais d'accès"]
        best = df_filtered.sort_values('Coût total').groupby('Site').first().reset_index()
        colonnes = ['Site', 'Technologie', 'Opérateur', 'Débit', "Frais d'accès", 'Prix mensuel', 'Zone']
        if 'costArea' in best.columns:
            colonnes.insert(3, 'costArea')
        st.dataframe(best[colonnes], use_container_width=True)
        output = BytesIO()
        best[colonnes].to_excel(output, index=False, engine='openpyxl')
        output.seek(0)
        st.download_button("📥 Télécharger Excel", data=output, file_name="proginov.xlsx")

    # Onglet 5 : Proginov nouvelle zone
    with onglets[4]:
        st.markdown("### Proginov nouvelle zone")
        df_filtered = df[df['Opérateur'] != 'COMPLETEL']
        techno_choice = st.selectbox("Technologie", options=df_filtered['Technologie'].dropna().unique(), key="techno5")
        engagement = st.slider("Engagement", 12, 60, step=12, value=36, key="engagement5")
        debit_choice = st.selectbox("Débit", options=sorted(df_filtered[df_filtered['Technologie'] == techno_choice]['Débit'].dropna().unique()), key="debit5")
        df_filtered = df_filtered[(df_filtered['Technologie'] == techno_choice) & (df_filtered['Débit'] == debit_choice)]
        available_operators = df_filtered['Opérateur'].dropna().unique()
        excluded_ops = [op for op in available_operators if st.checkbox(f"Exclure {op}", key=f"exc5_{op}")]
        df_filtered = df_filtered[~df_filtered['Opérateur'].isin(excluded_ops)]

        def zone_nouvelle(row):
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

        df_filtered['Zone'] = df_filtered.apply(zone_nouvelle, axis=1)
        df_filtered["Frais d'accès"] = df_filtered["Frais d'accès"].fillna(0)
        df_filtered['Coût total'] = df_filtered['Prix mensuel'] * engagement + df_filtered["Frais d'accès"]
        best = df_filtered.sort_values('Coût total').groupby('Site').first().reset_index()
        colonnes = ['Site', 'Technologie', 'Opérateur', 'Débit', "Frais d'accès", 'Prix mensuel', 'Zone']
        if 'costArea' in best.columns:
            colonnes.insert(3, 'costArea')
        st.dataframe(best[colonnes], use_container_width=True)
        output = BytesIO()
        best[colonnes].to_excel(output, index=False, engine='openpyxl')
        output.seek(0)
        st.download_button("📥 Télécharger Excel", data=output, file_name="proginov_nouvelle_zone.xlsx")
