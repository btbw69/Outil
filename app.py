import streamlit as st
import pandas as pd
from io import BytesIO
import json
import os

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
        'CRMSellPrice': 'Prix mensuel'
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
    onglets = st.tabs(["Choix de la techno / opérateur / débit pour chaque site", "Autre Onglet"])

    # --- Troisième onglet : "Choix de la techno / opérateur / débit pour chaque site" ---
    with onglets[0]:
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

        # Sauvegarder le travail en cours dans un fichier JSON
        def save_work():
            state = result.to_dict(orient='records')  # Convertit en dictionnaire
            with open("work_in_progress.json", "w") as f:
                json.dump(state, f)

        # Charger le travail sauvegardé depuis un fichier JSON
        def load_work():
            if os.path.exists("work_in_progress.json"):
                with open("work_in_progress.json", "r") as f:
                    state = json.load(f)
                    result = pd.DataFrame(state)
                    st.dataframe(result)
            else:
                st.warning("Aucun travail sauvegardé trouvé.")

        # Boutons pour sauvegarder et charger le travail
        st.button("Sauvegarder le travail en cours", on_click=save_work)
        st.button("Charger le travail sauvegardé", on_click=load_work)

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
