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
        "FAS/ABO le moins cher - 1 ligne par site",
        "FAS/ABO le moins cher - 1 ligne par débit",
        "FAS/ABO le moins cher - Différentes Marges",
        "Configurateur d'offre client",
        "Site Eligible pour un opérateur",
        "Proginov",
        "Proginov - Export Excel"
    ])

    # Onglet 1 : FAS/ABO le moins cher - Multi Techno / Multi Débit
    with onglets[0]:
        st.markdown("### FAS/ABO le moins cher - 1 ligne par site")
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
                    pivot = None
                    for techno, debit in debits_coches:
                        df_td = df[(df['Technologie'] == techno) & (df['Débit'] == debit)].copy()
                        df_td["Frais d'accès"] = df_td["Frais d'accès"].fillna(0)
                        df_td['Coût total'] = df_td['Prix mensuel'] * engagement + df_td["Frais d'accès"]
                        best = df_td.sort_values('Coût total').groupby('Site').first().reset_index()[['Site', 'Opérateur', "Frais d'accès", 'Prix mensuel']]
                        col_prefix = f"{techno} {debit}"
                        best = best.rename(columns={'Opérateur': f"{col_prefix} - Opérateur", "Frais d'accès": f"{col_prefix} - FAS", 'Prix mensuel': f"{col_prefix} - Abo"})
                        pivot = best if pivot is None else pivot.merge(best, on='Site', how='outer')

                    if pivot is None or pivot.empty:
                        st.warning("Aucune offre ne correspond aux critères sélectionnés.")
                    else:
                        nb_sites = pivot['Site'].nunique()
                        st.markdown(f"### Nombre de sites éligibles : {nb_sites}")
                        st.subheader("Meilleures offres par site")
                        st.dataframe(pivot, use_container_width=True)
                        download_excel(pivot, "meilleures_offres_multi_techno_debit.xlsx", key="dl_tab_mtmd")

    # Onglet 2 : FAS/ABO le moins cher - Multi Techno / Multi Débit (clone)
    with onglets[1]:
        st.markdown("### FAS/ABO le moins cher - 1 ligne par débit")
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

    # Onglet 3 : FAS/ABO le moins cher - Différentes Marges
    with onglets[2]:
        st.markdown("### FAS/ABO le moins cher - Différentes Marges")
        st.markdown("""
        <style>
        div[data-testid="stHorizontalBlock"] div[data-testid="column"] .stButton button {
            padding: 0.25rem 0.6rem;
            min-width: unset;
        }
        </style>
        """, unsafe_allow_html=True)
        if check_columns(df):
            engagement = st.slider("Durée d'engagement (mois)", min_value=12, max_value=60, step=12, value=36, key="engagement_dm")

            # Détection automatique de la marge (uniquement sur 36 mois)
            FAS_COUT_ACHAT_ORANGE = 400
            marge_actuelle = None

            if engagement == 36:
                df_orange = df[(df['Technologie'] == 'FTTO') & (df['Opérateur'] == 'Orange')].copy()
                df_orange["Frais d'accès"] = df_orange["Frais d'accès"].fillna(0)
                fas_vals = df_orange["Frais d'accès"][df_orange["Frais d'accès"] > 0]

                if not fas_vals.empty:
                    fas_orange = fas_vals.iloc[0]
                    marge_detectee = round((1 - FAS_COUT_ACHAT_ORANGE / fas_orange) * 100, 2)
                    st.markdown(f"**Marge Actuelle détectée : {marge_detectee}%**")
                else:
                    marge_detectee = None
                    st.warning("Impossible de détecter la marge (aucun FAS Orange FTTO trouvé)")

                col_ma, _ = st.columns([1, 3])
                with col_ma:
                    manuelle_str = st.text_input("Marge Actuelle Manuelle Si Détectée Fausse (%)", value="", key="dm_marge_manuelle")

                if manuelle_str.strip():
                    try:
                        marge_actuelle = float(manuelle_str.replace(',', '.'))
                    except ValueError:
                        st.error("Valeur invalide pour la marge manuelle")
                        marge_actuelle = marge_detectee
                else:
                    marge_actuelle = marge_detectee
            else:
                st.warning("Engagement différent de 36 mois, merci de rentrer la marge actuelle manuellement.")
                col_ma, _ = st.columns([1, 3])
                with col_ma:
                    marge_actuelle = st.number_input("Marge Actuelle (%)", min_value=0.0, max_value=99.9, value=25.0, step=0.1, key="dm_marge_manuelle_autre")

            # Marges cibles dynamiques avec IDs stables
            if 'dm_marges' not in st.session_state:
                st.session_state.dm_marges = [{'id': 0, 'val': 20.0}]
                st.session_state.dm_marge_counter = 1

            def dm_add_marge():
                st.session_state.dm_marges.append({'id': st.session_state.dm_marge_counter, 'val': 20.0})
                st.session_state.dm_marge_counter += 1

            def dm_del_marge(mid):
                st.session_state.dm_marges = [m for m in st.session_state.dm_marges if m['id'] != mid]

            def dm_move_up(idx):
                if idx > 0:
                    m = st.session_state.dm_marges
                    m[idx], m[idx - 1] = m[idx - 1], m[idx]

            def dm_move_down(idx):
                m = st.session_state.dm_marges
                if idx < len(m) - 1:
                    m[idx], m[idx + 1] = m[idx + 1], m[idx]

            st.markdown("**Marges cibles :**")
            for idx, marge in enumerate(st.session_state.dm_marges):
                mid = marge['id']
                n = len(st.session_state.dm_marges)
                col_val, col_up, col_down, col_del, col_space = st.columns([1.5, 0.35, 0.35, 1.2, 4], gap="small")
                with col_val:
                    st.session_state.dm_marges[idx]['val'] = st.number_input(
                        f"Marge {idx+1} (%)", min_value=0.0, max_value=99.9,
                        value=marge['val'], step=0.1, key=f"dm_marge_{mid}"
                    )
                with col_up:
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.button("↑", key=f"dm_up_{mid}", on_click=dm_move_up, args=(idx,), disabled=(idx == 0))
                with col_down:
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.button("↓", key=f"dm_down_{mid}", on_click=dm_move_down, args=(idx,), disabled=(idx == n - 1))
                with col_del:
                    if n > 1:
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.button("－ Supprimer", key=f"dm_del_marge_{mid}", on_click=dm_del_marge, args=(mid,))

            st.button("＋ Ajouter une marge", key="dm_add_marge", on_click=dm_add_marge)

            ordre_techno = {'FTTO': 0, 'FTTH': 1}
            technos = sorted(df['Technologie'].dropna().unique(), key=lambda t: ordre_techno.get(t, 99))
            st.markdown("**Sélectionnez les technologies :**")
            technos_cochees = [t for t in technos if st.checkbox(t, key=f"dm_techno_{t}")]

            if not technos_cochees:
                st.info("Cochez au moins une technologie pour afficher les débits.")
            else:
                st.markdown("**Sélectionnez les débits :**")
                debits_coches = []
                for techno in technos_cochees:
                    st.markdown(f"*{techno}*")
                    debits_techno = sort_debits(df[df['Technologie'] == techno]['Débit'].dropna().unique())
                    for d in debits_techno:
                        if st.checkbox(d, key=f"dm_debit_{techno}_{d}"):
                            debits_coches.append((techno, d))

                if not debits_coches:
                    st.info("Cochez au moins un débit pour afficher les résultats.")
                elif marge_actuelle is None:
                    st.warning("Marge actuelle non disponible, veuillez la saisir manuellement.")
                else:
                    taux_actuel = marge_actuelle / 100

                    pivot = None
                    for techno, debit in debits_coches:
                        df_td = df[(df['Technologie'] == techno) & (df['Débit'] == debit)].copy()
                        df_td["Frais d'accès"] = df_td["Frais d'accès"].fillna(0)
                        # Coût de revient = prix affiché × (1 - marge actuelle)
                        df_td['cout_fas'] = df_td["Frais d'accès"] * (1 - taux_actuel)
                        df_td['cout_abo'] = df_td['Prix mensuel'] * (1 - taux_actuel)
                        df_td['Coût total'] = df_td['Prix mensuel'] * engagement + df_td["Frais d'accès"]
                        best = df_td.sort_values('Coût total').groupby('Site').first().reset_index()

                        bloc = best[['Site', 'Opérateur']].copy()
                        col_prefix = f"{techno} {debit}"
                        bloc = bloc.rename(columns={'Opérateur': f"{col_prefix} - Opérateur"})

                        for marge in st.session_state.dm_marges:
                            marge_val = st.session_state.get(f"dm_marge_{marge['id']}", marge['val'])
                            taux = marge_val / 100
                            label = f"{int(marge_val)}%" if marge_val == int(marge_val) else f"{marge_val}%"
                            # Prix de vente à la nouvelle marge = coût / (1 - nouvelle marge)
                            bloc[f"{col_prefix} {label} - FAS"] = (best['cout_fas'] / (1 - taux)).round(2)
                            bloc[f"{col_prefix} {label} - Abo"] = (best['cout_abo'] / (1 - taux)).round(2)

                        pivot = bloc if pivot is None else pivot.merge(bloc, on='Site', how='outer')

                    if pivot is None or pivot.empty:
                        st.warning("Aucune offre ne correspond aux critères sélectionnés.")
                    else:
                        nb_sites = pivot['Site'].nunique()
                        st.markdown(f"### Nombre de sites éligibles : {nb_sites}")
                        st.subheader("Meilleures offres par site avec différentes marges")
                        st.dataframe(pivot, use_container_width=True)
                        download_excel(pivot, "meilleures_offres_differentes_marges.xlsx", key="dl_tab_dm")

    # Onglet 4 : Configurateur d'offre client
    with onglets[3]:
        st.markdown("### Configurateur d'offre client")
        if check_columns(df):
            engagement = st.slider("Durée d'engagement (mois)", min_value=12, max_value=60, step=12, value=36, key="engagement_conf")

            # Détection automatique de la marge
            FAS_COUT_ACHAT_ORANGE = 400
            marge_conf = None

            if engagement == 36:
                df_orange = df[(df['Technologie'] == 'FTTO') & (df['Opérateur'] == 'Orange')].copy()
                df_orange["Frais d'accès"] = df_orange["Frais d'accès"].fillna(0)
                fas_vals = df_orange["Frais d'accès"][df_orange["Frais d'accès"] > 0]
                if not fas_vals.empty:
                    marge_detectee = round((1 - FAS_COUT_ACHAT_ORANGE / fas_vals.iloc[0]) * 100, 2)
                    st.markdown(f"**Marge Actuelle détectée : {marge_detectee}%**")
                else:
                    marge_detectee = None
                    st.warning("Impossible de détecter la marge (aucun FAS Orange FTTO trouvé)")

                col_ma, _ = st.columns([1, 3])
                with col_ma:
                    manuelle_str = st.text_input("Marge Actuelle Manuelle Si Détectée Fausse (%)", value="", key="conf_marge_manuelle")
                if manuelle_str.strip():
                    try:
                        marge_conf = float(manuelle_str.replace(',', '.'))
                    except ValueError:
                        st.error("Valeur invalide pour la marge manuelle")
                        marge_conf = marge_detectee
                else:
                    marge_conf = marge_detectee
            else:
                st.warning("Engagement différent de 36 mois, merci de rentrer la marge actuelle manuellement.")
                col_ma, _ = st.columns([1, 3])
                with col_ma:
                    marge_conf = st.number_input("Marge Actuelle (%)", min_value=0.0, max_value=99.9, value=25.0, step=0.1, key="conf_marge_manuelle_autre")

            def appliquer_nouvelle_marge():
                val_str = st.session_state.get("conf_nouvelle_marge", "")
                if val_str.strip():
                    try:
                        val = float(val_str.replace(',', '.'))
                        for key in list(st.session_state.keys()):
                            if key.startswith("conf_marge_site_"):
                                st.session_state[key] = val
                    except ValueError:
                        pass

            col_nm, _ = st.columns([1, 3])
            with col_nm:
                nouvelle_marge_str = st.text_input("Nouvelle Marge (%)", value="", key="conf_nouvelle_marge", on_change=appliquer_nouvelle_marge)

            # Valeur par défaut de la marge par site (première fois)
            if nouvelle_marge_str.strip():
                try:
                    default_marge_site = float(nouvelle_marge_str.replace(',', '.'))
                except ValueError:
                    default_marge_site = marge_conf or 25.0
            else:
                default_marge_site = marge_conf or 25.0

            st.divider()

            sites = df['Site'].dropna().unique()
            ordre_techno = {'FTTO': 0, 'FTTH': 1}

            # En-têtes
            h = st.columns([2, 1.2, 1.2, 1.5, 1.5, 1, 1, 1])
            for col, label in zip(h, ["Site", "Technologie", "Débit", "Forcer opérateur ?", "Opérateur", "Marge %", "FAS", "Abo"]):
                col.markdown(f"**{label}**")
            st.divider()

            result_rows = []
            for i, site in enumerate(sites):
                df_site = df[df['Site'] == site]
                cols = st.columns([2, 1.2, 1.2, 1.5, 1.5, 1, 1, 1])

                with cols[0]:
                    st.markdown(f"{site}")

                with cols[1]:
                    technos = sorted(df_site['Technologie'].dropna().unique(), key=lambda t: ordre_techno.get(t, 99))
                    techno = st.selectbox("T", options=technos, key=f"conf_techno_{i}", label_visibility="collapsed")

                with cols[2]:
                    df_site_tech = df_site[df_site['Technologie'] == techno]
                    debits = sort_debits(df_site_tech['Débit'].dropna().unique())
                    debit = st.selectbox("D", options=debits, key=f"conf_debit_{i}", label_visibility="collapsed")

                with cols[3]:
                    st.markdown("<br>", unsafe_allow_html=True)
                    force = st.checkbox("Forcer", key=f"conf_force_{i}", label_visibility="collapsed")

                df_td = df_site_tech[df_site_tech['Débit'] == debit].copy()
                df_td["Frais d'accès"] = df_td["Frais d'accès"].fillna(0)
                df_td['Coût total'] = df_td['Prix mensuel'] * engagement + df_td["Frais d'accès"]

                if force:
                    with cols[4]:
                        ops = df_td.sort_values('Coût total')['Opérateur'].dropna().unique()
                        op = st.selectbox("Op", options=list(ops), key=f"conf_op_{i}", label_visibility="collapsed")
                    ligne = df_td[df_td['Opérateur'] == op]
                else:
                    ligne = df_td.sort_values('Coût total').iloc[:1]
                    op = ligne['Opérateur'].values[0] if not ligne.empty else ''
                    with cols[4]:
                        st.markdown(op)

                fas_brut = ligne["Frais d'accès"].values[0] if not ligne.empty else 0
                abo_brut = ligne['Prix mensuel'].values[0] if not ligne.empty else 0

                with cols[5]:
                    marge_site = st.number_input("M", min_value=0.0, max_value=99.9,
                                                  value=float(default_marge_site), step=0.1,
                                                  key=f"conf_marge_site_{i}", label_visibility="collapsed")

                # Recalcul : ôter marge actuelle puis appliquer marge site
                if marge_conf is not None and marge_site < 100:
                    taux_actuel = marge_conf / 100
                    taux_site = marge_site / 100
                    fas = round(fas_brut * (1 - taux_actuel) / (1 - taux_site), 2)
                    abo = round(abo_brut * (1 - taux_actuel) / (1 - taux_site), 2)
                else:
                    fas, abo = fas_brut, abo_brut

                with cols[6]:
                    st.markdown(f"{fas:.2f} €")

                with cols[7]:
                    st.markdown(f"{abo:.2f} €")

                result_rows.append({
                    'Site': site, 'Technologie': techno, 'Débit': debit,
                    'Opérateur': op, 'Marge %': marge_site, "Frais d'accès": fas, 'Prix mensuel': abo
                })

            st.divider()
            result_df = pd.DataFrame(result_rows)
            download_excel(result_df, "configuration_offre_client.xlsx", key="dl_conf")

    # Onglet 5 : Site Eligible pour un opérateur
    with onglets[4]:
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

    # Onglet 5 : Proginov
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
