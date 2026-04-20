from flask import Flask, render_template, request, redirect, url_for, flash, session
import pandas as pd
import os
import uuid

app = Flask(__name__)
app.secret_key = "une_cle_tres_secrete_123"
CSV_FILE = 'donnees_ecommerce_v2.csv'

def init_csv():
    # Ajout de 'Nb_Articles' dans la structure
    colonnes = ['ID', 'Nom', 'Categorie', 'Note', 'Nb_Articles', 'Recommandation', 'Commentaire']
    if not os.path.exists(CSV_FILE) or os.stat(CSV_FILE).st_size < 10:
        df = pd.DataFrame(columns=colonnes)
        df.to_csv(CSV_FILE, index=False)

@app.route("/")
def home():
    # La page d'accueil affiche uniquement la documentation
    return render_template("accueil.html")

@app.route("/formulaire", methods=["GET", "POST"])
def formulaire():
    init_csv()
    edit_data = session.get('edit_data')
    
    if request.method == "POST":
        # Récupération de TOUS les champs
        nom = request.form.get("nom").upper()
        categorie = request.form.get("categorie")
        note = request.form.get("note")
        nb_articles = request.form.get("nb_articles")
        recommande = request.form.get("recommande")
        commentaire = request.form.get("commentaire")

        df = pd.read_csv(CSV_FILE, dtype=str)
        cols = ['Nom', 'Categorie', 'Note', 'Nb_Articles', 'Recommandation', 'Commentaire']
        vals = [nom, categorie, note, nb_articles, recommande, commentaire]

        if 'edit_id' in session:
            uid = str(session['edit_id'])
            df.loc[df['ID'] == uid, cols] = vals
            flash("Modification enregistrée !", "info")
            session.pop('edit_id', None)
            session.pop('edit_data', None)
        else:
            nouveau_id = str(uuid.uuid4())[:8]
            nouvelle_ligne = pd.DataFrame([[nouveau_id] + vals], columns=['ID'] + cols)
            df = pd.concat([df, nouvelle_ligne], ignore_index=True)
            
            if 'mes_ids' not in session:
                session['mes_ids'] = []
            session['mes_ids'].append(nouveau_id)
            flash("Données ajoutées à la base !", "success")

        df.to_csv(CSV_FILE, index=False)
        return redirect(url_for('admin'))

    return render_template("formulaire.html", edit_data=edit_data)

@app.route("/analyse")
def analyse():
    init_csv()
    df = pd.read_csv(CSV_FILE)
    
    # Sécurité si le fichier est vide
    if df.empty:
        return render_template("analyse.html", stats=None)

    # Conversion forcée pour les calculs numériques
    df['Note'] = pd.to_numeric(df['Note'], errors='coerce').fillna(0)
    df['Nb_Articles'] = pd.to_numeric(df['Nb_Articles'], errors='coerce').fillna(0)

    # 1. QUALITATIF NOMINAL (Catégories -> Camembert)
    cat_counts = df['Categorie'].value_counts()
    
    # 2. QUALITATIF ORDINAL (Notes -> Histogramme)
    # On compte les occurrences de chaque note de 1 à 5
    dist_notes = df['Note'].astype(int).value_counts().to_dict()

    # 3. QUANTITATIF DISCRET (Nb Articles -> Barres de fréquence)
    dist_art = df['Nb_Articles'].astype(int).value_counts().sort_index().to_dict()

    stats = {
        'moyenne': round(df['Note'].mean(), 1),
        'total': len(df),
        'reco': round((len(df[df['Recommandation'] == 'Oui']) / len(df)) * 100, 1) if len(df) > 0 else 0,
        'labels_cat': cat_counts.index.tolist(),
        'values_cat': cat_counts.values.tolist(),
        'dist_notes': dist_notes,
        'labels_art': [str(k) for k in dist_art.keys()],
        'values_art': list(dist_art.values())
    }
    return render_template("analyse.html", stats=stats)

@app.route("/admin")
def admin():
    df = pd.read_csv(CSV_FILE, dtype=str)
    mes_ids = session.get('mes_ids', [])
    def btn(row):
        if str(row['ID']) in mes_ids:
            return f'<a href="/charger/{row["ID"]}" class="btn btn-sm btn-primary">Modifier</a>'
        return '<span class="badge bg-secondary opacity-50">Lecture seule</span>'
    df['Actions'] = df.apply(btn, axis=1)
    return render_template("admin.html", tableau=df.drop(columns=['ID']).to_html(classes='table text-center', index=False, escape=False))

@app.route("/charger/<uid>")
def charger(uid):
    df = pd.read_csv(CSV_FILE, dtype=str)
    if uid in session.get('mes_ids', []):
        l = df[df['ID'] == uid].iloc[0]
        session['edit_id'] = uid
        session['edit_data'] = l.to_dict()
    return redirect(url_for('home'))

if  __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)