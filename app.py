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
        lambda row: '1 gbits' if row['Technologie'] == 'FTTH' and row['Débit'] in ['1000M', '1000/500M'] else row['Débit'],
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
 # Vérification post-mapping
        required = ['Site', 'Opérateur', 'Technologie', 'Débit', 'Prix mensuel', "Frais d'accès"]
        missing_columns = [col for col in required if col not in df.columns]
        if missing_columns:
            st.error("Le fichier est invalide. Colonnes manquantes après mapping : " + ", ".join(missing_columns))
        else:
            technos = df['Technologie'].dropna().unique()
            techno_choice = st.selectbox("Choisissez une technologie", options=list(technos), key="techno_choice_1")

            engagement = st.slider("Durée d'engagement (mois)", min_value=12, max_value=60, step=12, value=36, key="engagement_1")

            filtered_df_for_debit = df[df['Technologie'] == techno_choice]

            debits = sorted(filtered_df_for_debit['Débit'].dropna().unique())
            debit_options = list(debits)

            debit_choice = st.selectbox("Choisissez un débit (optionnel)", options=debit_options, key="debit_choice_1")

            # Application des filtres (sans filtrer par engagement)
            df_filtered = df.copy()
            df_filtered = df_filtered[df_filtered['Technologie'] == techno_choice]
            df_filtered = df_filtered[df_filtered['Débit'] == debit_choice]

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

                # Initialisation de l'état du bouton
                if 'columns_visible' not in st.session_state:
                    st.session_state.columns_visible = True

                # Bouton pour masquer ou afficher les colonnes
                if st.button("Laisser que colonne prix" if st.session_state.columns_visible else "Afficher toutes les colonnes", key="button_1"):
                    # Met à jour l'état immédiatement après le clic
                    st.session_state.columns_visible = not st.session_state.columns_visible

                # Colonnes à afficher en fonction de l'état du bouton
                if st.session_state.columns_visible:
                    colonnes_a_afficher = [col for col in df.columns if col not in ['NDI', 'INSEECode', 'rivoli code', 'Available Copper Pair', 'Needed Coppoer Pair']]
                else:
                    colonnes_a_afficher = ['Site', "Frais d'accès", 'Prix mensuel']

                best_offers_reduits = best_offers[colonnes_a_afficher]

                st.subheader("Meilleures offres par site")
                st.dataframe(best_offers_reduits, use_container_width=True)

                # Export Excel
                output = BytesIO()
                best_offers_reduits.to_excel(output, index=False, engine='openpyxl')
                output.seek(0)
                st.download_button(
                    label="📥 Télécharger le fichier Excel",
                    data=output,
                    file_name="meilleures_offres.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

    
    # Onglet 2 : Site Eligible pour un opérateur
    with onglets[1]:
        st.markdown("### Site Eligible pour un opérateur")
 # Choix de la technologie
        technos = df['Technologie'].dropna().unique()
        techno_choice = st.selectbox("Choisissez une technologie", options=list(technos), key="techno_choice_2")

        # Filtrer les opérateurs selon la technologie choisie
        operateurs = df[df['Technologie'] == techno_choice]['Opérateur'].dropna().unique()
        operateur_choice = st.selectbox("Choisissez un opérateur", options=list(operateurs), key="operateur_choice_2")

        # Filtrer les débits selon la technologie choisie
        filtered_df_for_debit = df[df['Technologie'] == techno_choice]
        debits = sorted(filtered_df_for_debit['Débit'].dropna().unique())
        debit_options = list(debits)

        # Définir le débit par défaut sur 10M, si disponible
        debit_choice = st.selectbox("Choisissez un débit (optionnel)", options=debit_options, key="debit_choice_2", 
                                    index=debit_options.index('10M') if '10M' in debit_options else 0)

        # Appliquer les filtres selon techno, opérateur et débit
        df_filtered = df.copy()
        df_filtered = df_filtered[df_filtered['Technologie'] == techno_choice]
        df_filtered = df_filtered[df_filtered['Opérateur'] == operateur_choice]
        df_filtered = df_filtered[df_filtered['Débit'] == debit_choice]

        if df_filtered.empty:
            st.warning("Aucune offre ne correspond aux critères sélectionnés.")
        else:
            # Nombre de sites éligibles pour l'opérateur et la technologie sélectionnés
            nb_sites_operateur = df_filtered['Site'].nunique()
            st.markdown(f"### Nombre de sites éligibles à {operateur_choice} pour la technologie {techno_choice} : {nb_sites_operateur}")

            # Colonnes à afficher (modification ici : "Frais d'accès" avant "Prix mensuel")
            colonnes_a_afficher = ['Site', 'Opérateur', 'Technologie', 'Débit', "Frais d'accès", 'Prix mensuel']
            best_offers_reduits = df_filtered[colonnes_a_afficher]

            st.dataframe(best_offers_reduits, use_container_width=True)

            # Export Excel
            output = BytesIO()
            best_offers_reduits.to_excel(output, index=False, engine='openpyxl')
            output.seek(0)
            st.download_button(
                label="📥 Télécharger le fichier Excel",
                data=output,
                file_name="offres_filtrees.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

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
                if row['Prix mensuel'] <= 175:
                    return 'N0'
                elif row['Prix mensuel'] <= 198:
                    return 'N1'
                elif row['Prix mensuel'] <= 218:
                    return 'N2'
                elif row['Prix mensuel'] <= 248:
                    return 'N3'
                elif row['Prix mensuel'] <= 285:
                    return 'N4'
                elif row['Prix mensuel'] <= 318:
                    return 'N5'
                elif row['Prix mensuel'] <= 368:
                    return 'N6'
                else:
                    return 'HZ'
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
