from statistics import covariance
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
import pandas as pd
import os
import uuid
import numpy as np

app=Flask(__name__)
app.secret_key="une clef secrete 123"

if os.environ.get('postgresql://base_de_donnees_t31q_user:Lit2Kmi0ijUOToGHKDS3Ud1dbH8izTle@dpg-d7o50r3bc2fs7396o3s0-a.frankfurt-postgres.render.com/base_de_donnees_t31q'):
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('postgresql://base_de_donnees_t31q_user:Lit2Kmi0ijUOToGHKDS3Ud1dbH8izTle@dpg-d7o50r3bc2fs7396o3s0-a.frankfurt-postgres.render.com/base_de_donnees_t31q')
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///donnees.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# On définit la structure (le modèle) qui remplace ton init_csv()
class Produit(db.Model):
    Id = db.Column(db.String(8), primary_key=True)
    Nom = db.Column(db.String(100))
    Categorie = db.Column(db.String(50))
    Note = db.Column(db.Integer)
    Nb_Articles = db.Column(db.Integer)
    Recommandation = db.Column(db.String(5))
    Commentaire = db.Column(db.Text)

# Pour créer la base de données la première fois
with app.app_context():
    db.create_all()

@app.route("/")
def home():
    # La page d'accueil affiche uniquement la documentation
    return render_template("accueil.html")

@app.route("/formulaire", methods=["GET", "POST"])
def formulaire():
    edit_data = session.get('edit_data')
    
    if request.method == "POST":
        # On recupere les donneesde chaque produit
        nom=request.form.get("Nom")
        categorie=request.form.get("Categorie")
        note=int(request.form.get("Note",0))
        nb_articles=int(request.form.get("Nb_Articles",0))
        recommande=request.form.get("Recommandation")
        commentaire=request.form.get("Commentaire")
        
        # Modifier les donnees
        if 'edit_id' in session:
            uid=session['edit_id']
            produit=Produit.query.get(uid)
            if produit:
                produit.Nom=nom
                produit.Categorie=categorie
                produit.Note=note
                produit.Nb_Articles=nb_articles
                produit.Recommandation=recommande
                produit.Commentaire=commentaire
            flash("Modification reussie !","info")
            session.pop('edit_id',None)
            session.pop('edit_data',None)

        else: # Nouvel ajout
            nouveau_id=str(uuid.uuid4())[:8]
            nouveau_produit=Produit(
                Id=nouveau_id,
                Nom=nom,
                Categorie=categorie,
                Note=note,
                Nb_Articles=nb_articles,
                Recommandation=recommande,
                Commentaire=commentaire
            )
            db.session.add(nouveau_produit)
            
            # On conserve l'id pour les modifications eventuelles
            if 'mes_ids' not in session:
                session['mes_ids']=[]
            session['mes_ids'].append(nouveau_id)
            flash("Produit ajoute a la base SQL !", "success")
            
        # On valide l'ecriture dans le fichier .db
        db.session.commit()
        return redirect(url_for('admin'))
    
    return render_template("formulaire.html", edit_data=edit_data)
        

@app.route("/analyse")
def analyse():
    # On récupère les données SQL et on les transforme en DataFrame Pandas
    df = pd.read_sql(db.session.query(Produit).statement, db.engine)
    
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
    


    # --- 1. Statistiques Descriptives ---
    # Moyennes
    mean_x = df['Nb_Articles'].mean()
    mean_y = df['Note'].mean()

    # Variances (dispersion des données par rapport à la moyenne)
    var_x = df['Nb_Articles'].var()
    var_y = df['Note'].var()

    # Écarts-types (racine carrée de la variance, même unité que la variable)
    std_x = df['Nb_Articles'].std()
    std_y = df['Note'].std()

    # --- 2. Corrélation (Force du lien entre X et Y) ---
    # Comprise entre -1 et 1. Proche de 1 = lien fort positif.
    correlation = df['Nb_Articles'].corr(df['Note'])

    # --- 3. Régression Linéaire (y = ax + b) ---
    # Calcul de la covariance pour la pente
    covariance = np.cov(df['Nb_Articles'], df['Note'])[0][1]

    # Pente (a)
    a = covariance / var_x
    # Ordonnée à l'origine (b)
    b = mean_y - (a * mean_x)

    stats = {
        'moyenne': round(df['Note'].mean(), 1),
        'total': len(df),
        'reco': round((len(df[df['Recommandation'] == 'Oui']) / len(df)) * 100, 1) if len(df) > 0 else 0,
        'mean_x': mean_x,
        'mean_y': mean_y,
        'var_x': var_x,
        'var_y': var_y,
        'std_x': std_x,
        'std_y': std_y,
        'correlation': correlation,
        'a': a,
        'b': b,
        'labels_cat': cat_counts.index.tolist(),
        'values_cat': cat_counts.values.tolist(),
        'dist_notes': dist_notes,
        'labels_art': [str(k) for k in dist_art.keys()],
        'values_art': list(dist_art.values())
    }

    return render_template("analyse.html", stats=stats)

@app.route("/admin")
def admin():
    df=pd.read_sql(db.session.query(Produit).statement, db.engine)
    mes_ids = session.get('mes_ids', [])
    produits=df.to_dict(orient='records')
    return render_template("admin.html", produits=produits, mes_ids=mes_ids)

@app.route("/charger/<uid>")
def charger(uid):
    df=pd.read_sql(db.session.query(Produit).statement, db.engine)
    if uid in session.get('mes_ids', []):
        l = df[df['Id'] == uid].iloc[0]
        session['edit_id'] = uid
        session['edit_data'] = l.to_dict()
    return redirect(url_for('formulaire'))

@app.route("/supprimer/<uid>")
def supprimer(uid):
    # verifie sil'id est dans la session actuelle
    mes_ids= session.get('mes_ids',[])
    if uid in mes_ids:
        produit= Produit.query.get(uid)
        if produit:
            db.session.delete(produit)
            db.session.commit()
            
            # retirer la liste en session
            mes_ids.remove(uid)
            session['mes_ids']= mes_ids
            flash("Produit supprime avec succes !","danger")
    else:
        flash("Vous n'avez pas l'autorisation de supprimer ces donnees","danger")
    
    return redirect(url_for('admin'))

if __name__ == "__main__":
    app.run(host='0.0.0.0',port=10000)