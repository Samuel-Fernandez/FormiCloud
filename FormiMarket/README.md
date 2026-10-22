# FormiMarket

FormiMarket est une application web simple développée en Python avec le framework Flask. Elle permet de gérer vos plats, vos ingrédients, de planifier vos repas de la semaine et de générer une liste de courses automatique.

## Prérequis

- Python 3.x
- Flask

## Installation

1. Clonez ce dépôt sur votre machine locale.
2. (Optionnel) Créez et activez un environnement virtuel :
   ```bash
   python -m venv venv
   # Sur Windows : venv\Scripts\activate
   # Sur Mac/Linux : source venv/bin/activate
   ```
3. Installez Flask (si ce n'est pas déjà fait) :
   ```bash
   pip install flask
   ```

## Démarrage rapide

Pour lancer l'application, exécutez le fichier principal depuis la racine du projet :

```bash
python app.py
```

Ensuite, ouvrez votre navigateur et accédez à l'adresse suivante : [http://localhost:1000](http://localhost:1000).

## Structure du projet

- `app.py` : Fichier principal contenant la logique du serveur Flask et les routes API.
- `templates/` : Contient les fichiers HTML pour l'interface utilisateur.
- `static/` : Contient les fichiers CSS, JavaScript et autres ressources statiques.
- `data/` : Contient les fichiers JSON de sauvegarde (`dishes.json`, `ingredients.json`, `schedule.json`). *(Ces fichiers sont ignorés par Git pour ne pas exposer vos données personnelles)*.


Ce projet a été réalisé avec l'aide d'antigravity.