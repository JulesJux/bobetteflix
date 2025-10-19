from django.conf import settings
from django.shortcuts import render, redirect
from pathlib import Path
import csv
from django.db.models import Avg, Count
from django.middleware.csrf import get_token

from .models import Rating
from sadia_site.src.recommendation import ChargementDonnees, ConstructionGraphe

def _lire_films():
    movies_path = Path(settings.BASE_DIR) / 'data' / 'ml-latest-small' / 'movies.csv'
    films = []
    if movies_path.exists():
        with movies_path.open(encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # movieId from dataset can be large; we'll keep original id as int
                try:
                    movieId = int(row.get('movieId') or row.get('movieId'))
                except Exception:
                    movieId = None
                films.append({'movieId': movieId, 'title': row.get('title', 'Untitled')})
    else:
        # fallback: quelques films fictifs
        films = [
            {'movieId': 1, 'title': 'The Shawshank Redemption'},
            {'movieId': 2, 'title': 'The Godfather'},
            {'movieId': 3, 'title': 'The Dark Knight'},
        ]
    return films


def home(request):
    films = _lire_films()

    # Ensure CSRF token exists (forces cookie generation)
    get_token(request)

    # Utiliser annotate correctement pour obtenir la moyenne et le nombre de votes par movie_id
    annotated = Rating.objects.values('movie_id').annotate(avg=Avg('rating'), count=Count('rating'))
    stats = {item['movie_id']: {'avg': round(item['avg'], 2) if item['avg'] is not None else None, 'count': item['count']} for item in annotated}

    for f in films:
        mid = f['movieId']
        if mid in stats and stats[mid]['count'] > 0:
            f['avg'] = stats[mid]['avg']
            f['count'] = stats[mid]['count']
        else:
            f['avg'] = None
            f['count'] = 0

    # limit number of films shown for performance (e.g., first 50)
    context = {'films': films[:50]}
    return render(request, 'html/index.html', context)


def rate(request):
    if request.method != 'POST':
        return redirect('home')
    try:
        movie_id = int(request.POST.get('movie_id'))
        title = request.POST.get('title', '')[:200]
        rating_value = int(request.POST.get('rating'))
        if rating_value < 1 or rating_value > 5:
            raise ValueError('rating out of range')
    except Exception:
        # invalid data -> redirect back
        return redirect('home')

    Rating.objects.create(movie_id=movie_id, title=title, rating=rating_value)
    return redirect('home')

def recommander_films(request):
    # Charger les données
    chargement = ChargementDonnees()
    chemin_donnees = "data/ml-latest-small"
    if not chargement.charger_movielens(chemin_donnees):
        return render(request, 'html/index.html', {'error': 'Impossible de charger les données'})

    # Construire la matrice de transition
    graphe = ConstructionGraphe(chargement.evaluations)
    graphe.construire_matrice_transition()

    # Recommander des films basés sur les évaluations existantes
    films_recommandes = []
    for rating in Rating.objects.all():
        id_film = chargement.evaluations[chargement.evaluations['movieId'] == rating.movie_id]['id_film'].values
        if len(id_film) > 0:
            id_film = id_film[0]
            scores = graphe.matrice_transition[id_film]
            indices_recommandes = scores.argsort()[-5:][::-1]  # Top 5 recommandations
            films_recommandes.extend(chargement.films.iloc[indices_recommandes].to_dict('records'))

    return render(request, 'html/recommendations.html', {'films_recommandes': films_recommandes})
