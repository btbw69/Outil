import streamlit as st
import pandas as pd
from io import BytesIO
from st_aggrid import AgGrid, GridOptionsBuilder

# Paramètres de la page Streamlit
st.set_page_config(page_title="Exploitation des données d'éligibilité", layout="wide")
st.title("Exploitation des données d'éligibilité")

# Uploader le fichier Excel
uploaded_file = st.file_uploader("Téléversez le fichier d'offres", type=[".xlsx"])

if uploaded_file:
    # Lire les données depuis le fichier Excel
    df = pd.read_excel(uploaded_file)

    # Mapping des colonnes
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

    # Onglets
    onglets = st.tabs(["Choisir la techno et le débit souhaités", "Choisir une techno et un opérateur", "Construire son résultat par site"])

    # --- Troisième onglet : "Construire son résultat par site" ---
    with onglets[2]:
        st.markdown("### Construire son résultat par site")

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

        # Configuration des options de la grille Ag-Grid
        gb = GridOptionsBuilder.from_dataframe(result)
        
        # Ajout de listes déroulantes dans les cellules
        gb.configure_column('Technologie', editable=True, cellEditor='agSelectCellEditor', 
                            cellEditorParams={'values': ['FTTH', 'ADSL', 'VDSL', 'Fibre']})
        gb.configure_column('Opérateur', editable=True, cellEditor='agSelectCellEditor', 
                            cellEditorParams={'values': df['Opérateur'].dropna().unique()})
        gb.configure_column('Débit', editable=True, cellEditor='agSelectCellEditor', 
                            cellEditorParams={'values': df['Débit'].dropna().unique()})

        grid_options = gb.build()

        # Affichage du tableau interactif Ag-Grid
        grid_response = AgGrid(result, gridOptions=grid_options, enable_enterprise_modules=True, update_mode='MODEL_CHANGED')

        # Récupérer les données modifiées après interaction
        updated_result = grid_response['data']

        # Afficher le tableau mis à jour
        st.write("Tableau mis à jour avec les sélections :")
        st.dataframe(updated_result)

        # Export des résultats en Excel
        output = BytesIO()
        updated_result.to_excel(output, index=False, engine='openpyxl')
        output.seek(0)
        st.download_button(
            label="📥 Télécharger le fichier Excel",
            data=output,
            file_name="resultat_par_site.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
