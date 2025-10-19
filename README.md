# sadia

Projet Django initialisé.

Prerequis
- Python 3.8+
- Virtualenv (optionnel mais recommandé)

Quickstart

```bash
# depuis le répertoire /home/jules/Documents/sadia
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Fichiers importants
- `manage.py` - utilitaire Django pour lancer le serveur et les commandes
- `sadia_site/` - package du projet (settings, urls, wsgi, asgi)

Prochaine étape suggérée : créer une app via `python manage.py startapp <nom>` et l'ajouter à `INSTALLED_APPS`.
# bobetteflix
