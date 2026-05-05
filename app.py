import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
from zoneinfo import ZoneInfo
import re


def debit_key(d):
    m = re.search(r'\d+', str(d))
    return int(m.group()) if m else 0

def sort_debits(debits):
    """Trie les débits numériquement (ex: 5M, 10M, 100M) plutôt qu'alphabétiquement."""
    return sorted(debits, key=debit_key)

ORDRE_TECHNO = {'FTTO': 0, 'FTTH': 1}

def sort_df_by_debit(df, cols_avant_debit):
    """Trie un DataFrame : FTTO avant FTTH, puis débits numériquement."""
    df = df.copy()
    df['_debit_sort'] = df['Débit'].apply(debit_key)
    if 'Technologie' in df.columns:
        df['_techno_sort'] = df['Technologie'].map(ORDRE_TECHNO).fillna(99)
        df = df.sort_values(cols_avant_debit + ['_techno_sort', '_debit_sort']).drop(columns=['_debit_sort', '_techno_sort'])
    else:
        df = df.sort_values(cols_avant_debit + ['_debit_sort']).drop(columns='_debit_sort')
    return df.reset_index(drop=True)

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
        if p <= 371:
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
        "FAS/ABO le moins cher - Multi Techno / Multi Débit",
        "FAS/ABO le moins cher - Multi Techno / Multi Débit (2)",
        "FAS/ABO le moins cher - Multi Débit",
        "Site Eligible pour un opérateur",
        "Choix de la techno / opérateur / débit pour chaque site",
        "Proginov",
        "Proginov - Export Excel"
    ])

    # Onglet 3 : FAS/ABO le moins cher - Multi Débit
    with onglets[2]:
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
                    best_offers = sort_df_by_debit(best_offers, ['Site'])

                    nb_sites = best_offers['Site'].nunique()
                    st.markdown(f"### Nombre de sites éligibles à la {techno_choice} : {nb_sites}")

                    colonnes_a_afficher = ['Site', 'Débit', 'Opérateur', "Frais d'accès", 'Prix mensuel', 'Coût total']
                    st.subheader("Meilleures offres par site et par débit")
                    st.dataframe(best_offers[colonnes_a_afficher], use_container_width=True)
                    download_excel(best_offers[colonnes_a_afficher], "meilleures_offres_multi_debit.xlsx", key="dl_tab_md")

    # Onglet 1 : FAS/ABO le moins cher - Multi Techno / Multi Débit
    with onglets[0]:
        st.markdown("### FAS/ABO le moins cher - Multi Techno / Multi Débit")
        if check_columns(df):
            engagement = st.slider("Durée d'engagement (mois)", min_value=12, max_value=60, step=12, value=36, key="engagement_mtmd")

            ordre_techno = {'FTTO': 0, 'FTTH': 1}
            technos = sorted(df['Technologie'].dropna().unique(), key=lambda t: ordre_techno.get(t, 99))
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
                        best_offers = sort_df_by_debit(best_offers, ['Site', 'Technologie'])
                        st.subheader("Meilleures offres par site, technologie et débit")
                        st.dataframe(best_offers[colonnes_a_afficher], use_container_width=True)
                        download_excel(best_offers[colonnes_a_afficher], "meilleures_offres_multi_techno_debit.xlsx", key="dl_tab_mtmd")

    # Onglet 2 : FAS/ABO le moins cher - Multi Techno / Multi Débit (clone)
    with onglets[1]:
        st.markdown("### FAS/ABO le moins cher - Multi Techno / Multi Débit (2)")
        if check_columns(df):
            engagement = st.slider("Durée d'engagement (mois)", min_value=12, max_value=60, step=12, value=36, key="engagement_mtmd2")

            ordre_techno = {'FTTO': 0, 'FTTH': 1}
            technos = sorted(df['Technologie'].dropna().unique(), key=lambda t: ordre_techno.get(t, 99))
            st.markdown("**Sélectionnez les technologies :**")
            technos_cochees = [t for t in technos if st.checkbox(t, key=f"mtmd2_techno_{t}")]

            if not technos_cochees:
                st.info("Cochez au moins une technologie pour afficher les débits.")
            else:
                st.markdown("**Sélectionnez les débits :**")
                debits_coches = []
                for techno in technos_cochees:
                    st.markdown(f"*{techno}*")
                    debits_techno = sort_debits(df[df['Technologie'] == techno]['Débit'].dropna().unique())
                    for d in debits_techno:
                        if st.checkbox(d, key=f"mtmd2_debit_{techno}_{d}"):
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
                        best_offers = sort_df_by_debit(best_offers, ['Site', 'Technologie'])
                        st.subheader("Meilleures offres par site, technologie et débit")
                        st.dataframe(best_offers[colonnes_a_afficher], use_container_width=True)
                        download_excel(best_offers[colonnes_a_afficher], "meilleures_offres_multi_techno_debit2.xlsx", key="dl_tab_mtmd2")

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

    # Onglet 7 : Proginov - Export Excel
    with onglets[6]:
        st.markdown("### Proginov - Export Excel")
        if check_columns(df):
            ftth_ops = precompute_ftth_ops(df)

            # FTTO : meilleur opérateur et zone par site avec priorité hors SFR/Orange
            df_ftto = df[(df['Opérateur'] != 'COMPLETEL') & (df['Technologie'] == 'FTTO') & (df['Débit'] == '10M')].copy()
            df_ftto["Frais d'accès"] = df_ftto["Frais d'accès"].fillna(0)
            df_ftto['Zone'] = df_ftto.apply(zone_nouvelle, axis=1, ftth_ops=ftth_ops)
            df_ftto['Coût total'] = df_ftto['Prix mensuel'] * 36 + df_ftto["Frais d'accès"]

            def best_ftto_for_site(grp):
                preferred = grp[~grp['Opérateur'].isin(['SFR', 'Orange'])]
                if not preferred.empty:
                    return preferred.sort_values('Coût total').iloc[0]
                sfr = grp[grp['Opérateur'] == 'SFR']
                if not sfr.empty:
                    return sfr.sort_values('Coût total').iloc[0]
                return grp.sort_values('Coût total').iloc[0]

            rows = [best_ftto_for_site(grp) for _, grp in df_ftto.groupby('Site')]
            best_ftto = pd.DataFrame(rows)[['Site', 'Opérateur', 'Zone']].reset_index(drop=True)
            best_ftto.columns = ['Site', 'Opérateur FTTO', 'Zone FTTO']

            # Offres Burst éligibles FTTH Débit Garanti
            OFFRES_BURST = ['FIBRE IELO FTTO BURST', 'Covage FTTO Burst', 'EuroFiber Burst FTTO']

            def get_burst_info(site):
                if 'Eligibility Offer' not in df.columns:
                    return 'Non', ''
                lignes = df[(df['Site'] == site) & (df['Eligibility Offer'].isin(OFFRES_BURST))]
                if lignes.empty:
                    return 'Non', ''
                obls = ' '.join(lignes['Opérateur'].dropna().unique()) + ' N11'
                return 'Oui', obls

            burst_data = best_ftto['Site'].apply(lambda s: pd.Series(get_burst_info(s), index=['Eligible DG', 'Zone DG']))
            best_ftto = pd.concat([best_ftto, burst_data], axis=1)

            # FTTH Sans Garantie : SFR / KOSC
            def get_ftth_sg_info(site):
                ops = ftth_ops.get(site, set())
                sfr = 'SFR' in ops
                kosc = 'KOSC' in ops
                if not sfr and not kosc:
                    return 'Non', ''
                if sfr and kosc:
                    return 'Oui', 'SFR N10 Kosc N11'
                if sfr:
                    return 'Oui', 'SFR N10'
                return 'Oui', 'KOSC N11'

            sg_data = best_ftto['Site'].apply(lambda s: pd.Series(get_ftth_sg_info(s), index=['Eligible SG', 'Zone SG']))
            best_ftto = pd.concat([best_ftto, sg_data], axis=1)

            # Export Excel avec mise en forme template
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill

            buf = BytesIO()
            wb = Workbook()
            ws = wb.active

            # Styles
            red_fill    = PatternFill("solid", fgColor="FF0000")
            gray_fill   = PatternFill("solid", fgColor="BFBFBF")
            yellow_fill = PatternFill("solid", fgColor="FFFF00")
            green_fill  = PatternFill("solid", fgColor="92D050")
            bold   = Font(bold=True)
            center = Alignment(horizontal="center", vertical="center")

            # Ligne 1 : en-têtes groupes
            ws.merge_cells("A1:A2"); ws["A1"] = "Site"
            ws["A1"].fill = gray_fill; ws["A1"].font = bold; ws["A1"].alignment = center

            ws.merge_cells("B1:C1"); ws["B1"] = "FTTO"
            ws["B1"].fill = red_fill; ws["B1"].font = bold; ws["B1"].alignment = center

            ws.merge_cells("D1:E1"); ws["D1"] = "FTTH Débit Garanti"
            ws["D1"].fill = yellow_fill; ws["D1"].font = bold; ws["D1"].alignment = center

            ws.merge_cells("F1:G1"); ws["F1"] = "FTTH Sans Garantie"
            ws["F1"].fill = green_fill; ws["F1"].font = bold; ws["F1"].alignment = center

            # Ligne 2 : sous-en-têtes
            for cell, val, fill in [
                ("B2", "Opérateur FTTO", red_fill),
                ("C2", "Zone FTTO",      red_fill),
                ("D2", "Eligible",       yellow_fill),
                ("E2", "Zone",           yellow_fill),
                ("F2", "Eligible",       green_fill),
                ("G2", "Zone",           green_fill),
            ]:
                ws[cell] = val
                ws[cell].fill = fill
                ws[cell].font = bold
                ws[cell].alignment = center

            # Données à partir de la ligne 3
            for i, row in best_ftto.reset_index(drop=True).iterrows():
                ws.cell(row=i+3, column=1, value=row['Site'])
                ws.cell(row=i+3, column=2, value=row['Opérateur FTTO'])
                ws.cell(row=i+3, column=3, value=row['Zone FTTO'])
                ws.cell(row=i+3, column=4, value=row['Eligible DG'])
                ws.cell(row=i+3, column=5, value=row['Zone DG'])
                ws.cell(row=i+3, column=6, value=row['Eligible SG'])
                ws.cell(row=i+3, column=7, value=row['Zone SG'])

            # Ajustement automatique de la largeur des colonnes
            from openpyxl.utils import get_column_letter
            for i, col in enumerate(ws.columns, 1):
                max_len = max((len(str(cell.value)) if cell.value else 0) for cell in col)
                ws.column_dimensions[get_column_letter(i)].width = max_len + 3

            wb.save(buf)
            buf.seek(0)
            filename = f"Résultat Zones Proginov_{datetime.now(ZoneInfo('Europe/Paris')).strftime('%d-%m-%Y-%Hh%M')}.xlsx"
            st.download_button("📥 Télécharger Zonage Proginov", data=buf,
                               file_name=filename,
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               key="dl_template")
