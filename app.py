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
        'CostArea': 'CostArea'  # Ajout de la colonne CostArea
    }

    df = df.rename(columns=column_mapping)

    # Exclure les lignes où Already Fiber == 'AvailableSoon' ou 'UnderCommercialTerms'
    if 'Already Fiber' in df.columns:
        df = df[(df['Already Fiber'] != 'AvailableSoon') & (df['Already Fiber'] != 'UnderCommercialTerms')]

    # Remplacer les débits FTTH 1000M et 1000/200M par "1 gbits"
    df['Débit'] = df.apply(
        lambda row: '1 gbits' if row['Technologie'] == 'FTTH' and row['Débit'] in ['1000M', '1000/500M'] else row['Débit'],
        axis=1
    )

    # Initialisation correcte des onglets
    onglets = st.tabs(["FAS/ABO le moins cher", "Site Eligible pour un opérateur", "Choix de la techno / opérateur / débit pour chaque site", "proginov"])

    # --- Premier onglet : "FAS/ABO le moins cher" ---
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

    # --- Deuxième onglet : "Site Eligible pour un opérateur" ---
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

    # --- Troisième onglet : "Choix de la techno / opérateur / débit pour chaque site" ---
    with onglets[2]:
        st.markdown("### Choix de la techno / opérateur / débit pour chaque site")

        # Liste des sites
        sites = df['Site'].dropna().unique()

        # Créer un tableau vide avec les colonnes souhaitées
        result = pd.DataFrame({
            'Site': sites,
            'Technologie': [None] * len(sites),
            'Opérateur': [None] * len(sites),
            'Débit': [None] * len(sites),
            'Frais d\'accès': [None] * len(sites),
            'Prix mensuel': [None] * len(sites)
        })

        # Pour chaque site, créer des sélections pour la techno, opérateur et débit
        for i, site in enumerate(sites):
            # Sélection de la technologie
            technos_disponibles = df[df['Site'] == site]['Technologie'].dropna().unique()
            techno_choice = st.selectbox(f"Choisissez la technologie pour {site}", options=technos_disponibles, key=f"techno_{i}")
            result.loc[i, 'Technologie'] = techno_choice

            # Sélection de l'opérateur en fonction de la technologie choisie
            operateurs_disponibles = df[(df['Site'] == site) & (df['Technologie'] == techno_choice)]['Opérateur'].dropna().unique()
            operateur_choice = st.selectbox(f"Choisissez l'opérateur pour {site} ({techno_choice})", options=operateurs_disponibles, key=f"operateur_{i}")
            result.loc[i, 'Opérateur'] = operateur_choice

            # Sélection du débit en fonction de la techno et opérateur choisis
            debits_disponibles = df[(df['Site'] == site) & (df['Technologie'] == techno_choice) & (df['Opérateur'] == operateur_choice)]['Débit'].dropna().unique()
            debit_choice = st.selectbox(f"Choisissez le débit pour {site} ({operateur_choice})", options=debits_disponibles, key=f"debit_{i}")
            result.loc[i, 'Débit'] = debit_choice

            # Calcul des frais d'accès et du prix mensuel
            frais_acces = df[(df['Site'] == site) & (df['Technologie'] == techno_choice) & (df['Opérateur'] == operateur_choice) & (df['Débit'] == debit_choice)]['Frais d\'accès'].values
            prix_mensuel = df[(df['Site'] == site) & (df['Technologie'] == techno_choice) & (df['Opérateur'] == operateur_choice) & (df['Débit'] == debit_choice)]['Prix mensuel'].values

            result.loc[i, 'Frais d\'accès'] = frais_acces[0] if len(frais_acces) > 0 else 0
            result.loc[i, 'Prix mensuel'] = prix_mensuel[0] if len(prix_mensuel) > 0 else 0

        # Affichage du tableau interactif
        st.dataframe(result, use_container_width=True)

        # Export des résultats en Excel
        output = BytesIO()
        result.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)
        st.download_button(
            label="📥 Télécharger le fichier Excel",
            data=output,
            file_name="resultat_par_site.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

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
