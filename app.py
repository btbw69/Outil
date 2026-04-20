import streamlit as st
import pandas as pd
from io import BytesIO
import re


def sort_debits(debits):
    """Trie les débits numériquement (ex: 5M, 10M, 100M) plutôt qu'alphabétiquement."""
    def debit_key(d):
        m = re.search(r'\d+', str(d))
        return int(m.group()) if m else 0
    return sorted(debits, key=debit_key)

st.set_page_config(page_title="Exploitation des données d'éligibilité", layout="wide")
st.title("Exploitation des données d'éligibilité")

REQUIRED_COLS = ['Site', 'Opérateur', 'Technologie', 'Débit', 'Prix mensuel', "Frais d'accès"]

COLUMN_MAPPING = {
    'Name': 'Site',
    'OBL': 'Opérateur',
    'Type Physical Link': 'Technologie',
    'bandwidth': 'Débit',
    'FASSellPrice': "Frais d'accès",
    'CRMSellPrice': 'Prix mensuel',
    'CostArea': 'costArea',
}

COLS_TO_HIDE = {'NDI', 'INSEECode', 'rivoli code', 'Available Copper Pair', 'Needed Copper Pair'}


def download_excel(df, filename, label="📥 Télécharger le fichier Excel", key=None):
    buf = BytesIO()
    df.to_excel(buf, index=False, engine='openpyxl')
    buf.seek(0)
    st.download_button(label=label, data=buf, file_name=filename,
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       key=key)


def check_columns(df):
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        st.error("Colonnes manquantes après mapping : " + ", ".join(missing))
        return False
    return True


def precompute_ftth_ops(df):
    """Retourne un dict {site: set(opérateurs FTTH)} pour éviter O(n²) dans apply."""
    return (
        df[df['Technologie'] == 'FTTH']
        .groupby('Site')['Opérateur']
        .apply(set)
        .to_dict()
    )


def zone_classic(row, ftth_ops):
    if row['Technologie'] == 'FTTH':
        ops = ftth_ops.get(row['Site'], set())
        if 'SFR' in ops and 'KOSC' in ops:
            return 'SFR N10 Kosc N11'
        if row['Opérateur'] == 'SFR':
            return 'N10'
        if row['Opérateur'] == 'KOSC':
            return 'N11'
    elif row['Technologie'] == 'FTTO':
        p = row['Prix mensuel']
        if p < 218:
            return 'N1'
        if p < 300:
            return 'N2'
        if p < 325:
            return 'N3'
        if p < 355:
            return 'N4'
        return 'N5'
    return 'Non défini'


def zone_nouvelle(row, ftth_ops):
    if row['Technologie'] == 'FTTH':
        ops = ftth_ops.get(row['Site'], set())
        if 'SFR' in ops and 'KOSC' in ops:
            return 'SFR N10 Kosc N11'
        if row['Opérateur'] == 'SFR':
            return 'N10'
        if row['Opérateur'] == 'KOSC':
            return 'N11'
    elif row['Technologie'] == 'FTTO':
        p = row['Prix mensuel']
        if p <= 175:
            return 'N0'
        if p <= 198:
            return 'N1'
        if p <= 218:
            return 'N2'
        if p <= 248:
            return 'N3'
        if p <= 285:
            return 'N4'
        if p <= 318:
            return 'N5'
        if p <= 368:
            return 'N6'
        return 'HZ'
    return 'Non défini'


def render_proginov_tab(df, zone_fn, key_prefix, filename):
    if not check_columns(df):
        return

    ftth_ops = precompute_ftth_ops(df)

    df_base = df[df['Opérateur'] != 'COMPLETEL'].copy()
    techno_choice = st.selectbox("Technologie",
                                 options=df_base['Technologie'].dropna().unique(),
                                 key=f"techno_{key_prefix}")
    debit_auto = '1 gbits' if techno_choice == 'FTTH' else '10M'

    df_filtered = df_base[
        (df_base['Technologie'] == techno_choice) &
        (df_base['Débit'] == debit_auto)
    ].copy()

    available_operators = df_filtered['Opérateur'].dropna().unique()
    excluded_ops = [op for op in available_operators if st.checkbox(f"Exclure {op}", key=f"exc_{key_prefix}_{op}")]
    df_filtered = df_filtered[~df_filtered['Opérateur'].isin(excluded_ops)].copy()

    if df_filtered.empty:
        st.warning("Aucune offre ne correspond aux critères sélectionnés.")
        return

    df_filtered["Frais d'accès"] = df_filtered["Frais d'accès"].fillna(0)
    df_filtered['Zone'] = df_filtered.apply(zone_fn, axis=1, ftth_ops=ftth_ops)
    df_filtered['Coût total'] = df_filtered['Prix mensuel'] * 36 + df_filtered["Frais d'accès"]

    best = df_filtered.sort_values('Coût total').groupby('Site').first().reset_index()
    colonnes = ['Site', 'Technologie', 'Opérateur', 'Prix mensuel', 'Zone']

    st.dataframe(best[colonnes], use_container_width=True)
    download_excel(best[colonnes], filename, key=f"dl_{key_prefix}")


uploaded_file = st.file_uploader("Téléversez le fichier d'offres", type=[".xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    df = df.rename(columns=COLUMN_MAPPING)

    if 'Already Fiber' in df.columns:
        df = df[~df['Already Fiber'].isin(['AvailableSoon', 'UnderCommercialTerms'])]

    df['Débit'] = df.apply(
        lambda row: '1 gbits' if row['Technologie'] == 'FTTH' and row['Débit'] in ['1000M', '1000/500M'] else row['Débit'],
        axis=1
    )

    onglets = st.tabs([
        "FAS/ABO le moins cher",
        "FAS/ABO le moins cher - Multi Débit",
        "FAS/ABO le moins cher - Multi Techno / Multi Débit",
        "Site Eligible pour un opérateur",
        "Choix de la techno / opérateur / débit pour chaque site",
        "Proginov"
    ])

    # Onglet 1 : FAS/ABO le moins cher
    with onglets[0]:
        st.markdown("### FAS/ABO le moins cher")
        if check_columns(df):
            technos = df['Technologie'].dropna().unique()
            techno_choice = st.selectbox("Choisissez une technologie", options=list(technos), key="techno_choice_1")
            engagement = st.slider("Durée d'engagement (mois)", min_value=12, max_value=60, step=12, value=36, key="engagement_1")

            debits = sort_debits(df[df['Technologie'] == techno_choice]['Débit'].dropna().unique())
            debit_choice = st.selectbox("Choisissez un débit", options=debits, key="debit_choice_1")

            df_filtered = df[(df['Technologie'] == techno_choice) & (df['Débit'] == debit_choice)].copy()

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

                if st.button(
                    "Laisser que colonne prix" if st.session_state.columns_visible else "Afficher toutes les colonnes",
                    key="button_1"
                ):
                    st.session_state.columns_visible = not st.session_state.columns_visible

                if st.session_state.columns_visible:
                    colonnes_a_afficher = [c for c in best_offers.columns if c not in COLS_TO_HIDE]
                else:
                    colonnes_a_afficher = ['Site', "Frais d'accès", 'Prix mensuel']

                st.subheader("Meilleures offres par site")
                st.dataframe(best_offers[colonnes_a_afficher], use_container_width=True)
                download_excel(best_offers[colonnes_a_afficher], "meilleures_offres.xlsx", key="dl_tab1")

    # Onglet 2 : FAS/ABO le moins cher - Multi Débit
    with onglets[1]:
        st.markdown("### FAS/ABO le moins cher - Multi Débit")
        if check_columns(df):
            technos = df['Technologie'].dropna().unique()
            techno_choice = st.selectbox("Choisissez une technologie", options=list(technos), key="techno_choice_md")
            engagement = st.slider("Durée d'engagement (mois)", min_value=12, max_value=60, step=12, value=36, key="engagement_md")

            debits = sort_debits(df[df['Technologie'] == techno_choice]['Débit'].dropna().unique())
            st.markdown("**Sélectionnez les débits :**")
            debits_coches = [d for d in debits if st.checkbox(d, key=f"md_debit_{d}")]

            if not debits_coches:
                st.info("Cochez au moins un débit pour afficher les résultats.")
            else:
                df_filtered = df[(df['Technologie'] == techno_choice) & (df['Débit'].isin(debits_coches))].copy()

                if df_filtered.empty:
                    st.warning("Aucune offre ne correspond aux critères sélectionnés.")
                else:
                    df_filtered["Frais d'accès"] = df_filtered["Frais d'accès"].fillna(0)
                    df_filtered['Coût total'] = df_filtered['Prix mensuel'] * engagement + df_filtered["Frais d'accès"]
                    best_offers = df_filtered.sort_values('Coût total').groupby(['Site', 'Débit']).first().reset_index()
                    best_offers = best_offers.sort_values(['Site', 'Débit'])

                    nb_sites = best_offers['Site'].nunique()
                    st.markdown(f"### Nombre de sites éligibles à la {techno_choice} : {nb_sites}")

                    colonnes_a_afficher = ['Site', 'Débit', 'Opérateur', "Frais d'accès", 'Prix mensuel', 'Coût total']
                    st.subheader("Meilleures offres par site et par débit")
                    st.dataframe(best_offers[colonnes_a_afficher], use_container_width=True)
                    download_excel(best_offers[colonnes_a_afficher], "meilleures_offres_multi_debit.xlsx", key="dl_tab_md")

    # Onglet 3 : FAS/ABO le moins cher - Multi Techno / Multi Débit
    with onglets[2]:
        st.markdown("### FAS/ABO le moins cher - Multi Techno / Multi Débit")
        if check_columns(df):
            engagement = st.slider("Durée d'engagement (mois)", min_value=12, max_value=60, step=12, value=36, key="engagement_mtmd")

            technos = sorted(df['Technologie'].dropna().unique())
            st.markdown("**Sélectionnez les technologies :**")
            technos_cochees = [t for t in technos if st.checkbox(t, key=f"mtmd_techno_{t}")]

            if not technos_cochees:
                st.info("Cochez au moins une technologie pour afficher les débits.")
            else:
                st.markdown("**Sélectionnez les débits :**")
                debits_coches = []
                for techno in technos_cochees:
                    st.markdown(f"*{techno}*")
                    debits_techno = sort_debits(df[df['Technologie'] == techno]['Débit'].dropna().unique())
                    for d in debits_techno:
                        if st.checkbox(d, key=f"mtmd_debit_{techno}_{d}"):
                            debits_coches.append((techno, d))

                if not debits_coches:
                    st.info("Cochez au moins un débit pour afficher les résultats.")
                else:
                    mask = pd.Series([False] * len(df), index=df.index)
                    for techno, debit in debits_coches:
                        mask |= (df['Technologie'] == techno) & (df['Débit'] == debit)
                    df_filtered = df[mask].copy()

                    if df_filtered.empty:
                        st.warning("Aucune offre ne correspond aux critères sélectionnés.")
                    else:
                        df_filtered["Frais d'accès"] = df_filtered["Frais d'accès"].fillna(0)
                        df_filtered['Coût total'] = df_filtered['Prix mensuel'] * engagement + df_filtered["Frais d'accès"]
                        best_offers = df_filtered.sort_values('Coût total').groupby(['Site', 'Technologie', 'Débit']).first().reset_index()

                        nb_sites = best_offers['Site'].nunique()
                        st.markdown(f"### Nombre de sites éligibles : {nb_sites}")

                        colonnes_a_afficher = ['Site', 'Technologie', 'Débit', 'Opérateur', "Frais d'accès", 'Prix mensuel', 'Coût total']
                        best_offers = best_offers.sort_values(['Site', 'Technologie', 'Débit'])
                        st.subheader("Meilleures offres par site, technologie et débit")
                        st.dataframe(best_offers[colonnes_a_afficher], use_container_width=True)
                        download_excel(best_offers[colonnes_a_afficher], "meilleures_offres_multi_techno_debit.xlsx", key="dl_tab_mtmd")

    # Onglet 4 : Site Eligible pour un opérateur
    with onglets[3]:
        st.markdown("### Site Eligible pour un opérateur")
        if check_columns(df):
            technos = df['Technologie'].dropna().unique()
            techno_choice = st.selectbox("Choisissez une technologie", options=list(technos), key="techno_choice_2")

            operateurs = df[df['Technologie'] == techno_choice]['Opérateur'].dropna().unique()
            operateur_choice = st.selectbox("Choisissez un opérateur", options=list(operateurs), key="operateur_choice_2")

            debits = sort_debits(df[df['Technologie'] == techno_choice]['Débit'].dropna().unique())
            debit_choice = st.selectbox("Choisissez un débit", options=debits, key="debit_choice_2",
                                        index=debits.index('10M') if '10M' in debits else 0)

            df_filtered = df[
                (df['Technologie'] == techno_choice) &
                (df['Opérateur'] == operateur_choice) &
                (df['Débit'] == debit_choice)
            ]

            if df_filtered.empty:
                st.warning("Aucune offre ne correspond aux critères sélectionnés.")
            else:
                nb_sites = df_filtered['Site'].nunique()
                st.markdown(f"### Nombre de sites éligibles à {operateur_choice} pour la technologie {techno_choice} : {nb_sites}")

                colonnes_a_afficher = ['Site', 'Opérateur', 'Technologie', 'Débit', "Frais d'accès", 'Prix mensuel']
                st.dataframe(df_filtered[colonnes_a_afficher], use_container_width=True)
                download_excel(df_filtered[colonnes_a_afficher], "offres_filtrees.xlsx", key="dl_tab2")

    # Onglet 5 : Choix par site
    with onglets[4]:
        st.markdown("### Choix de la techno / opérateur / débit pour chaque site")
        if check_columns(df):
            sites = df['Site'].dropna().unique()
            techno_list, operateur_list, debit_list, frais_list, prix_list = [], [], [], [], []

            for i, site in enumerate(sites):
                df_site = df[df['Site'] == site]
                technos = df_site['Technologie'].dropna().unique()
                techno = st.selectbox(f"Technologie {site}", options=technos, key=f"s3_tech_{i}")

                df_site_tech = df_site[df_site['Technologie'] == techno]
                operateurs = df_site_tech['Opérateur'].dropna().unique()
                operateur = st.selectbox(f"Opérateur {site}", options=operateurs, key=f"s3_op_{i}")

                df_site_op = df_site_tech[df_site_tech['Opérateur'] == operateur]
                debits = df_site_op['Débit'].dropna().unique()
                debit = st.selectbox(f"Débit {site}", options=debits, key=f"s3_debit_{i}")

                ligne = df_site_op[df_site_op['Débit'] == debit]
                frais = ligne["Frais d'accès"].values[0] if not ligne.empty else 0
                prix = ligne["Prix mensuel"].values[0] if not ligne.empty else 0

                techno_list.append(techno)
                operateur_list.append(operateur)
                debit_list.append(debit)
                frais_list.append(frais)
                prix_list.append(prix)

            result = pd.DataFrame({
                'Site': sites,
                'Technologie': techno_list,
                'Opérateur': operateur_list,
                'Débit': debit_list,
                "Frais d'accès": frais_list,
                'Prix mensuel': prix_list,
            })
            st.dataframe(result, use_container_width=True)
            download_excel(result, "choix_site.xlsx", label="📥 Télécharger Excel", key="dl_tab3")

    # Onglet 6 : Proginov
    with onglets[5]:
        st.markdown("### Proginov")
        render_proginov_tab(df, zone_nouvelle, key_prefix="5", filename="proginov_nouvelle_zone.xlsx")
