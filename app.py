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

    # Créer un tableau de base avec Ag-Grid
    st.subheader("Tableau avec listes déroulantes pour Technologie et Opérateur")

    # Configuration de base d'Ag-Grid avec la liste déroulante pour Technologie
    gb = GridOptionsBuilder.from_dataframe(df)

    # Liste déroulante pour la colonne "Technologie"
    gb.configure_column('Technologie', editable=True, cellEditor='agSelectCellEditor', 
                        cellEditorParams={'values': ['FTTO', 'FTTH']})
    
    # Afficher Ag-Grid avec la liste déroulante pour Technologie
    grid_options = gb.build()
    grid_response = AgGrid(df, gridOptions=grid_options, update_mode='MODEL_CHANGED')

    # Récupérer les données modifiées après interaction
    updated_result = grid_response['data']

    # Vérifier si une technologie a été sélectionnée
    if updated_result:
        selected_techno = updated_result[0]['Technologie']  # Prendre la première ligne pour la technologie choisie

        # Filtrer les opérateurs disponibles pour la technologie sélectionnée
        filtered_operators = df[df['Technologie'] == selected_techno]['Opérateur'].dropna().unique()

        # Maintenant, ajouter la liste déroulante pour la colonne "Opérateur"
        gb.configure_column('Opérateur', editable=True, cellEditor='agSelectCellEditor', 
                            cellEditorParams={'values': filtered_operators})

        # Recharger la grille avec la nouvelle configuration (Opérateur filtré)
        grid_options = gb.build()
        grid_response = AgGrid(df, gridOptions=grid_options, update_mode='MODEL_CHANGED')

        # Récupérer les données mises à jour
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
