from django.conf import settings
from django.shortcuts import render, redirect
from pathlib import Path
import csv
import os
import requests
from django.db.models import Avg, Count
from django.middleware.csrf import get_token

from .models import Rating
from sadia_site.src.recommendation import ChargementDonnees, ConstructionGraphe

TMDB_API_KEY = os.environ.get("TMDB_API_KEY")
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_TRENDING_URL = "https://api.themoviedb.org/3/trending/movie/day"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
_poster_cache = {}

def about(request):
    return render(request, "html/about.html")

def _clean_title(title):
    """Supprime l’année entre parenthèses à la fin du titre (sans regex)."""
    if not title:
        return title

    pos = title.rfind('(')
    if pos != -1 and title.endswith(')'):
        inside = title[pos+1:-1]
        # Vérifie si c’est bien une année (ex: '1999')
        if len(inside) == 4 and inside.isdigit():
            return title[:pos].strip()
    return title.strip()


def _extract_year(title):
    """Retourne l’année si elle est présente à la fin du titre."""
    if not title:
        return None
    pos = title.rfind('(')
    if pos != -1 and title.endswith(')'):
        inside = title[pos+1:-1]
        if len(inside) == 4 and inside.isdigit():
            return int(inside)
    return None

def _get_poster_from_tmdb(title):
    """Recherche un film par titre sur TMDB et retourne l’URL du poster s’il existe, avec cache."""
    if not TMDB_API_KEY:
        return None

    clean_title = _clean_title(title)
    year = _extract_year(title)
    cache_key = clean_title + (f" ({year})" if year else "")

    # 🔹 Vérifie si on a déjà ce film en cache
    if cache_key in _poster_cache:
        return _poster_cache[cache_key]

    params = {
        "api_key": TMDB_API_KEY,
        "query": clean_title,
        "language": "fr-FR",
    }
    if year:
        params["year"] = year

    try:
        response = requests.get(TMDB_SEARCH_URL, params=params, timeout=5)
        if response.status_code != 200:
            _poster_cache[cache_key] = None
            return None
        data = response.json()
        results = data.get("results") or []
        if not results:
            _poster_cache[cache_key] = None
            return None
        poster_path = results[0].get("poster_path")
        if poster_path:
            poster_url = TMDB_IMAGE_BASE + poster_path
            _poster_cache[cache_key] = poster_url
            return poster_url
        _poster_cache[cache_key] = None
    except Exception as e:
        print("Erreur TMDB pour", title, ":", e)
        _poster_cache[cache_key] = None

    return None


def _dedupe_recommendations_list(recs, keys=('movieId', 'movie_id', 'id_film', 'id')):
    """Déduplique une liste de dictionnaires en préservant l'ordre.
    Cherche l'identifiant du film dans les clés fournies.
    Retourne la liste dédupliquée.
    """
    seen = set()
    deduped = []
    for r in recs:
        if not isinstance(r, dict):
            # si l'élément n'est pas un dict, on l'inclut tel quel
            deduped.append(r)
            continue
        # chercher une clé id utilisable
        film_id = None
        for k in keys:
            if k in r and r[k] is not None:
                film_id = r[k]
                break
        # normaliser les types (numpy types -> int)
        try:
            if film_id is not None:
                film_id = int(film_id)
        except Exception:
            pass
        if film_id is None:
            # pas d'identifiant, inclure une seule fois en se basant sur l'objet dict string
            key = tuple(sorted(r.items()))
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        else:
            if film_id not in seen:
                seen.add(film_id)
                deduped.append(r)
    return deduped

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

    try:
        page_size = int(request.GET.get('page_size', 12))
        if page_size <= 0:
            page_size = 12
    except ValueError:
        page_size = 12

    for i in range (0, page_size):
        films[i]['poster_url'] = _get_poster_from_tmdb(_clean_title(films[i]['title']))

    start = 0
    end = start + page_size

    total = len(films)
    page_films = films[start:end]

    has_more = end < total
    context = {
        'films': page_films,
        'page_size': page_size,
        'has_more': has_more,
        'total_films': total,
    }
    return render(request, 'html/home.html', context)


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
        return redirect('home')

    Rating.objects.create(movie_id=movie_id, title=title, rating=rating_value)
    return redirect('home')

def recommander_films(request):
    # Charger les données
    chargement = ChargementDonnees()
    chemin_donnees = "data/ml-latest-small"
    if not chargement.charger_movielens(chemin_donnees):
        return render(request, 'html/home.html', {'error': 'Impossible de charger les données'})

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

    films_recommandes = _dedupe_recommendations_list(films_recommandes)
    return render(request, 'html/recommendations.html', {'films_recommandes': films_recommandes})
