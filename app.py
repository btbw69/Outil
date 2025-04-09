import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(layout="wide")
st.title("Exploitation des données d'éligibilité")

uploaded_file = st.file_uploader("Téléversez le fichier d'offres", type=[".xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # Renommer les colonnes
    column_mapping = {
        'Name': 'Site',
        'OBL': 'Opérateur',
        'Type Physical Link': 'Technologie',
        'bandwidth': 'Débit',
        'FASSellPrice': "Frais d'accès",
        'CRMSellPrice': 'Prix mensuel'
    }
    df = df.rename(columns=column_mapping)

    # --- Onglet 3 - "Construire son résultat par site" ---
    with st.expander("Construire son résultat par site"):
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

        # Alternance de couleurs pour chaque site
        result_html = ""
        colors = ["#f2f2f2", "#ffffff"]  # Couleurs alternées

        for i, row in result.iterrows():
            color = colors[i % 2]  # Alterner la couleur
            result_html += f'<tr style="background-color:{color}">'
            for col in result.columns:
                result_html += f'<td>{row[col]}</td>'
            result_html += '</tr>'

        # Table HTML avec couleurs alternées
        st.markdown(f"""
            <table style="width:100%; border-collapse: collapse; text-align:left;">
                <thead>
                    <tr style="background-color:#e0e0e0;">
                        <th>Site</th>
                        <th>Technologie</th>
                        <th>Opérateur</th>
                        <th>Débit</th>
                        <th>Frais d'accès</th>
                        <th>Prix mensuel</th>
                    </tr>
                </thead>
                <tbody>
                    {result_html}
                </tbody>
            </table>
        """, unsafe_allow_html=True)

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
