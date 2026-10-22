# Projet FormiFit - Suivi Nutritionnel

## Description Générale
Application web responsive (adaptée pour Smartphone et Ordinateur) permettant de calculer, suivre et gérer les apports nutritionnels et les besoins caloriques journaliers et hebdomadaires.

## Fonctionnalités Clés
- **Gestion Multi-profils** : Possibilité de créer et de gérer plusieurs profils d'utilisateurs.
- **Base de Données Commune** : Une base de données partagée contenant les aliments, ingrédients et repas.
- **Recherche et Ajout** : Recherche intuitive dans la base de données pour ajouter des éléments consommés dans la journée.
- **Assistant IA (Génération d'Aliments)** : Interface de discussion avec une IA permettant de décrire un nouveau repas ou ingrédient. L'IA générera automatiquement les valeurs nutritionnelles et les l'ajoutera à la base de données (via un retour de données au format JSON).

## Architecture de l'Application

### 1. Page de Profil
- Sélection du profil utilisateur lors du lancement de l'application pour charger les données et les paramètres correspondants.

### 2. Page d'Accueil (Tableau de Bord)
- Visualisation graphique (sous forme de barres de progression).
- Affichage en pourcentages et en grammages des nutriments, kilocalories (kcal), etc.
- Comparaison entre l'accumulation journalière/hebdomadaire et les objectifs réels (besoins nutritionnels) de l'utilisateur.

### 3. Page d'Édition de la Base de Données
- Interface dédiée pour modifier, corriger ou enrichir manuellement les informations d'un repas ou d'un ingrédient existant.

### 4. Page de Réglages et Objectifs
- **Paramètres Métaboliques** : Saisie des données personnelles (poids, taille, sexe, pourcentage de masse graisseuse).
- **Calculs Automatiques** : Évaluation du métabolisme de base et des besoins caloriques journaliers en fonction des paramètres de l'utilisateur.
- **Limites Personnalisées** : Possibilité de définir une limite stricte de calories quotidiennes.
- **Planification d'Objectif de Poids** :
  - Saisie d'un poids cible.
  - Calcul automatique par l'application du nombre maximal de calories autorisées quotidiennement pour atteindre cet objectif selon différentes échéances temporelles :
    - 6 mois
    - 3 mois
    - 1 mois
    - 2 semaines
    - 1 semaine

## 5. Suggestions d'Évolutions (Optionnelles)
- **Dépenses Énergétiques** : Possibilité d'ajouter des séances de sport pour déduire les calories brûlées de la journée. (Base de donnée à part, ajout des séances de sport avec l'IA)



# PROMPT TO USE
Niquel. Si poids, masse graisseuse, taille, âge, sexe, tout ce qui sert à calculer le métabolisme (kcal, micro/macronutriments9 n'a pas été renseigné l'utilisateur est redirigé vers la page réglage pour remplir ceci.

secret key : (voir .env, GOOGLE_API_KEY)