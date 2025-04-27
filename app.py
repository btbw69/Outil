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

    # --- 4. Onglet Proginov ---
    with onglets[3]:
        st.markdown("### Proginov")

        from_zone = df[df['Opérateur'] != 'COMPLETEL']

        def assign_zone(row):
            if row['Technologie'] == 'FTTH':
                ops = df[(df['Site'] == row['Site']) & (df['Technologie'] == 'FTTH')]['Opérateur'].unique()
                if 'SFR' in ops and 'KOSC' in ops:
                    return 'SFR N10 Kosc N11'
                elif row['Opérateur'] == 'SFR':
                    return 'N10'
                elif row['Opérateur'] == 'KOSC':
                    return 'N11'
            if row['Technologie'] == 'FTTO':
                prix = row['Prix mensuel']
                if prix < 218:
                    return 'N1'
                elif prix < 300:
                    return 'N2'
                elif prix < 325:
                    return 'N3'
                elif prix < 355:
                    return 'N4'
                else:
                    return 'N5'
            return 'Non défini'

        from_zone['Zone'] = from_zone.apply(assign_zone, axis=1)

        st.dataframe(from_zone[['Site', 'Technologie', 'Opérateur', 'Débit', 'Prix mensuel', 'Zone']], use_container_width=True)

    # --- 5. Onglet Proginov nouvelle zone ---
    with onglets[4]:
        st.markdown("### Proginov nouvelle zone")

        # Ici tu pourras plus tard mettre ta nouvelle règle de zone spéciale

        from_zone = df[df['Opérateur'] != 'COMPLETEL']
        from_zone['Zone'] = from_zone.apply(assign_zone, axis=1)

        st.dataframe(from_zone[['Site', 'Technologie', 'Opérateur', 'Débit', 'Prix mensuel', 'Zone']], use_container_width=True)

