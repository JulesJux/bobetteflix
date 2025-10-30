import numpy as np
import pandas as pd
from itertools import combinations
from collections import Counter
from django.conf import settings
from pathlib import Path


# --------------------------------------------
# 1. Chargement et nettoyage des données
# --------------------------------------------

class ChargementDonnees:
    def __init__(self):
        self.evaluations = None
        self.films = None

    def charger_movielens(self, chemin_donnees="data/ml-latest-small"):
        try:
            self.evaluations = pd.read_csv(Path(settings.BASE_DIR) / 'data' / 'ml-latest-small' / 'ratings.csv')
            self.films = pd.read_csv(Path(settings.BASE_DIR) / 'data' / 'ml-latest-small' / 'movies.csv')
            self._nettoyer_donnees()
        except FileNotFoundError:
            print("Fichiers non trouvés")
            return False
        return True

    def _nettoyer_donnees(self):
        self.evaluations = self.evaluations[self.evaluations['rating'] >= 4.0].copy()
        self.evaluations['id_utilisateur'] = pd.Categorical(self.evaluations['userId']).codes
        self.evaluations['id_film'] = pd.Categorical(self.evaluations['movieId']).codes


chargement = ChargementDonnees()
chargement.charger_movielens()


# --------------------------------------------
# 2. Construction du graphe (optimisé)
# --------------------------------------------

class ConstructionGraphe:
    def __init__(self, evaluations):
        self.evaluations = evaluations
        self.nb_utilisateurs = evaluations['id_utilisateur'].max() + 1
        self.nb_films = evaluations['id_film'].max() + 1
        self.matrice_transition = None

    def construire_matrice_transition(self):
        cooccurrences = Counter()

        for _, group in self.evaluations.groupby('id_utilisateur'):
            films = group['id_film'].values
            for i, j in combinations(films, 2):
                cooccurrences[(i, j)] += 1
                cooccurrences[(j, i)] += 1  # rendre symétrique

        similarite_films = np.zeros((self.nb_films, self.nb_films), dtype=np.float32)
        for (i, j), count in cooccurrences.items():
            similarite_films[i, j] = count

        # Normalisation ligne par ligne
        somme_lignes = similarite_films.sum(axis=1, keepdims=True)
        with np.errstate(divide='ignore', invalid='ignore'):
            self.matrice_transition = np.divide(similarite_films, somme_lignes, where=somme_lignes != 0)
            self.matrice_transition[somme_lignes[:, 0] == 0] = 1.0 / self.nb_films

        return self.matrice_transition


# Construction du graphe
if chargement.evaluations is not None:
    construction = ConstructionGraphe(chargement.evaluations)
    matrice_P = construction.construire_matrice_transition()


# --------------------------------------------
# 3. Recommandation par marche aléatoire (optimisée)
# --------------------------------------------

class RecommandationMarcheAleatoire:
    def __init__(self, matrice_transition):
        self.matrice_transition = matrice_transition
        self.nb_films = matrice_transition.shape[0]

    def marche_aleatoire_naive(self, films_depart, iterations_max=1000):
        scores = np.zeros(self.nb_films)
        for film in films_depart:
            scores[film] = 1 / len(films_depart)

        for iteration in range(iterations_max):
            nouveaux_scores = self.matrice_transition.T @ scores  # Vectorisé
            changement = np.sum(np.abs(nouveaux_scores - scores))
            scores = nouveaux_scores

            if iteration % 100 == 0:
                top_films = np.argsort(scores)[-3:][::-1]

            if changement < 1e-8:
                print(f"✓ Convergence à l'itération {iteration}")
                break

        return scores


# --------------------------------------------
# 4. Métriques d’évaluation (inchangé)
# --------------------------------------------

class MetriquesEvaluation:
    def __init__(self, evaluations):
        self.evaluations = evaluations

    def precision_k(self, films_recommandes, films_reels, k):
        films_recommandes_k = films_recommandes[:k]
        bons_films = len(set(films_recommandes_k) & set(films_reels))
        return bons_films / k if k > 0 else 0
