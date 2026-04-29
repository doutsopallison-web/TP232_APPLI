from statistics import covariance
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
import pandas as pd
import os
import uuid
import numpy as np

app=Flask(__name__)
app.secret_key="une clef secrete 123"

# On force l'utilisation du fichier local SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///donnees.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

with app.app_context():
    db.create_all()

# On définit la structure (le modèle) qui remplace ton init_csv()
class Utilisateur(db.Model):
    Id = db.Column(db.String(8), primary_key=True)
    Nom = db.Column(db.String(100))
    Email=db.Column(db.String(60))
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
        email=request.form.get("Email")
        
        deja_connu=Utilisateur.query.filter(
            (Utilisateur.Email==email)
        ).first()
        
        # On recupere les donneesde chaque Utilisateur
        total_actuel= Utilisateur.query.count()
        total_utilisateur=db.session.query(func.count(Utilisateur.Email.distinct())).scalar()
        
        
        if 'edit_id' not in session:
           
            if total_actuel>=1000: 
                flash("Limite d'enregistrements atteinte","danger")
                return redirect (url_for('admin'))
        
            if  not deja_connu and total_utilisateur>=300:
                flash("Limite d'utilisateurs atteinte","danger")
                return redirect (url_for('admin'))
    
        nom=request.form.get("Nom")
        email=request.form.get("Email")
        categorie=request.form.get("Categorie")
        note=int(request.form.get("Note",0))
        nb_articles=int(request.form.get("Nb_Articles",0))
        recommande=request.form.get("Recommandation")
        commentaire=request.form.get("Commentaire")
        
        
        if nb_articles>100:
            flash("La quantite d'articles maximale est de 100","attention")
            nb_articles=100
        
        # Modifier les donnees
        if 'edit_id' in session:
            uid=session['edit_id']
            utilisateur=Utilisateur.query.get(uid)
            if utilisateur:
                utilisateur.Nom=nom
                utilisateur.Email=email
                utilisateur.Categorie=categorie
                utilisateur.Note=note
                utilisateur.Nb_Articles=nb_articles
                utilisateur.Recommandation=recommande
                utilisateur.Commentaire=commentaire
            flash("Modification reussie !","info")
            session.pop('edit_id',None)
            session.pop('edit_data',None)

        else: # Nouvel ajout
            nouveau_id=str(uuid.uuid4())[:8]
            nouveau_utilisateur=Utilisateur(
                Id=nouveau_id,
                Nom=nom,
                Email=email,
                Categorie=categorie,
                Note=note,
                Nb_Articles=nb_articles,
                Recommandation=recommande,
                Commentaire=commentaire
            )
            db.session.add(nouveau_utilisateur)
            
            # On conserve l'id pour les modifications eventuelles
            if 'mes_ids' not in session:
                session['mes_ids']=[]
            session['mes_ids'].append(nouveau_id)
            flash("Utilisateur ajoute a la base SQLAlchemy !", "success")
        
    
        # On valide l'ecriture dans le fichier .db
        db.session.commit()
        return redirect(url_for('admin'))
    
    return render_template("formulaire.html", edit_data=edit_data)
        

@app.route("/analyse")
def analyse():
    # On récupère les données SQL et on les transforme en DataFrame Pandas
    df = pd.read_sql(db.session.query(Utilisateur).statement, db.engine)
    
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
    df=pd.read_sql(db.session.query(Utilisateur).statement, db.engine)
    mes_ids = session.get('mes_ids', [])
    utilisateurs=df.to_dict(orient='records')
    Enr=Utilisateur.query.count()
    u=db.session.query(func.count(Utilisateur.Email.distinct())).scalar()
    return render_template("admin.html", utilisateurs=utilisateurs, mes_ids=mes_ids,Enregistrement=Enr,Utilisateur=u)

@app.route("/charger/<uid>")
def charger(uid):
    df=pd.read_sql(db.session.query(Utilisateur).statement, db.engine)
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
        produit= Utilisateur.query.get(uid)
        if produit:
            db.session.delete(produit)
            db.session.commit()
            
            # retirer la liste en session
            mes_ids.remove(uid)
            session['mes_ids']= mes_ids
            flash("Utilisateur supprime avec succes !","attention")
    else:
        flash("Vous n'avez pas l'autorisation de supprimer ces donnees","danger")
    
    return redirect(url_for('admin'))

if __name__ == "__main__":
    app.run(host='0.0.0.0',port=8000)