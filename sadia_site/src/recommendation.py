import numpy as np
import pandas as pd

class ChargementDonnees:
    def __init__(self):
        self.evaluations = None
        self.films = None

    def charger_movielens(self, chemin_donnees="../data/ml-latest-small"):
        try:
            self.evaluations = pd.read_csv(f"{chemin_donnees}/ratings.csv")
            self.films = pd.read_csv(f"{chemin_donnees}/movies.csv")
            self._nettoyer_donnees()
        except FileNotFoundError:
            print("Fichiers non trouvÃ©s")
            return False
        return True

    def _nettoyer_donnees(self):
        self.evaluations = self.evaluations[self.evaluations['rating'] >= 4.0]
        self.evaluations['id_utilisateur'] = pd.Categorical(self.evaluations['userId']).codes
        self.evaluations['id_film'] = pd.Categorical(self.evaluations['movieId']).codes


chargement = ChargementDonnees()
chargement.charger_movielens()


class ConstructionGraphe:
    def __init__(self, evaluations):
        self.evaluations = evaluations
        self.nb_utilisateurs = evaluations['id_utilisateur'].max() + 1
        self.nb_films = evaluations['id_film'].max() + 1
        self.matrice_transition = None

    def construire_matrice_transition(self):
        similarite_films = np.zeros((self.nb_films, self.nb_films))

        for id_utilisateur in range(self.nb_utilisateurs):
            evaluations_utilisateur = self.evaluations[self.evaluations['id_utilisateur'] == id_utilisateur]
            films_aimes = evaluations_utilisateur['id_film'].values

            if len(films_aimes) > 1:
                for i in range(len(films_aimes)):
                    for j in range(len(films_aimes)):
                        if i != j:
                            similarite_films[films_aimes[i], films_aimes[j]] += 1

        self.matrice_transition = np.zeros((self.nb_films, self.nb_films))
        for i in range(self.nb_films):
            somme_ligne = np.sum(similarite_films[i])
            if somme_ligne > 0:
                self.matrice_transition[i] = similarite_films[i] / somme_ligne
            else:
                self.matrice_transition[i] = np.ones(self.nb_films) / self.nb_films

        return self.matrice_transition


if chargement.evaluations is not None:
    construction = ConstructionGraphe(chargement.evaluations)
    matrice_P = construction.construire_matrice_transition()


class RecommandationMarcheAleatoire:
    def __init__(self, matrice_transition):
        self.matrice_transition = matrice_transition
        self.nb_films = matrice_transition.shape[0]

    def marche_aleatoire_naive(self, films_depart, iterations_max=1000):
        scores = np.zeros(self.nb_films)
        for film in films_depart:
            scores[film] = 1 / len(films_depart)
        for iteration in range(iterations_max):
            nouveaux_scores = np.zeros(self.nb_films)
            for i in range(self.nb_films):
                if scores[i] > 0:
                    for j in range(self.nb_films):
                        if self.matrice_transition[i, j] > 0:
                            nouveaux_scores[j] += self.matrice_transition[i, j] * scores[i]
            changement = np.sum(np.abs(nouveaux_scores - scores))
            scores = nouveaux_scores.copy()

            if iteration % 100 == 0:
                top_films = np.argsort(scores)[-3:][::-1]
            if changement < 1e-8:  # Convergence
                print(f"âœ“ Convergence Ã  l'itÃ©ration {iteration}")
                break
        return scores


class MetriquesEvaluation:
    def __init__(self, evaluations):
        self.evaluations = evaluations

    def precision_k(self, films_recommandes, films_reels, k):
        films_recommandes_k = films_recommandes[:k]
        bons_films = len(set(films_recommandes_k) & set(films_reels))
        return bons_films / k if k > 0 else 0