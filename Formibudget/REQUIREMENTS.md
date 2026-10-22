# Formibudget

## Introduction
Actuellement, un fichier Excel est utilisé pour calculer le budget futur, les dépenses hebdomadaires, etc. L'objectif est de remplacer ce fichier par une application web dédiée à la gestion de mon budget personnel, déployée sur un VPS via Docker.

## Contexte actuel (fichier Excel)
Le fichier Excel dispose de quelques éléments avec une valeur en CHF prédéfinie : ce sont les dépenses régulières. Le budget restant est calculé à chaque fin de semaine, et il est possible de visualiser sur le long terme ce qu'il reste comme argent par semaine.

Aucune migration des données existantes n'est prévue : l'application démarrera avec une base vide.

## Fonctionnalités

### Gestion des dépenses régulières
- Ajouter des dépenses régulières récurrentes sur *n* semaines ou *n* mois.
- Une dépense récurrente peut avoir une fin définie par une **date de fin précise** (ex. "jusqu'au 31.12.2026).
- Le montant d'une dépense récurrente peut varier d'une occurrence à l'autre ; modifier le montant ne s'applique **qu'à l'occurrence en cours**, sans affecter les occurrences passées ou futures.
- Supprimer une dépense récurrente ne supprime que les occurrences **futures** ; l'historique des occurrences passées est conservé.
- Les dépenses et revenus récurrents affectent directement le budget dès leur échéance (pas besoin de validation manuelle pour qu'ils soient pris en compte).
- Ajouter des entrées (revenus) et des sorties (dépenses) au niveau hebdomadaire ou mensuel.

### Catégories et limites budgétaires
- Les catégories sont **entièrement personnalisables** : créer, modifier, supprimer ses propres catégories librement (pas de liste prédéfinie imposée).
- Possibilité de fixer une limite de budget par catégorie, à ne pas dépasser. La limite est **hebdomadaire** (remise à zéro chaque semaine, du lundi au dimanche).
- En cas de dépassement d'une limite de catégorie, l'application l'affiche **visuellement** (couleur/icône d'alerte) mais n'empêche pas d'ajouter la dépense.

### Calendrier et affichage
- Affichage sous forme de calendrier par semaine (semaine du **lundi** au dimanche), avec le détail des dépenses par jour concerné.
- Correction manuelle du budget final en fin de semaine, en cas d'incohérence ou d'oubli.
- Si le solde d'une semaine devient négatif, un **avertissement visuel** (bandeau/icône) est affiché sur la semaine concernée, sans bloquer la saisie.
- L'historique des semaines passées est conservé **indéfiniment** (pas de purge automatique).

### Projection budgétaire
- Projection du budget disponible sur plusieurs mois, voire plusieurs années, à partir des dépenses/revenus récurrents et ponctuels.
- La projection est affichée **sur la même page que le calendrier** (ex. graphique/résumé visible en permanence à côté ou au-dessus de la vue calendrier), et non sur une page séparée.
- Horizon par défaut : **6 mois**.
- Forme : **graphique en courbe** montrant l'évolution du solde dans le temps.

### Export des données
- Export possible au format **JSON** et/ou via copier/coller (pas d'export CSV ni PDF prévu).

## Utilisateurs
Application mono-utilisateur (usage personnel), sans gestion multi-comptes.

## Devise
Devise fixe : CHF (codée en dur, pas de configuration multi-devises).

## Contraintes techniques

### Hébergement
- Déploiement en conteneur Docker sur un VPS aux ressources limitées.
- Un reverse proxy est déjà configuré sur le VPS (gestion du nom de domaine et du HTTPS en amont) : le conteneur doit simplement exposer un port HTTP interne.
- Aucune authentification applicative n'est requise dans un premier temps ; la sécurité d'accès est gérée en dehors de l'application (réseau, VPN, whitelist IP, etc.).

### Stack technique
- **Backend** : Python (FastAPI).
- **Frontend** : rendu serveur avec HTMX (pas de build JS complexe, empreinte légère).
- **Base de données** : SQLite, stockée dans un fichier sur un volume Docker persistant.
- **Port du conteneur** : fixe, codé en dur (**8010**).

### Sauvegardes
Pas de mécanisme de sauvegarde automatisé prévu pour le moment. À réévaluer plus tard si besoin (ex. cron de copie du fichier SQLite).

### Tests automatisés
Pas de suite de tests requise dans un premier temps ; priorité au fonctionnel. À reconsidérer une fois l'application stable.

## Interface utilisateur

### Thème
Thème **clair uniquement** (pas de mode sombre pour l'instant).

### Responsive / mobile
L'interface doit être **responsive** : l'application sera aussi consultée depuis un téléphone.

### Format des nombres et dates
Format **suisse/européen** :
- Montants : `1'234.50 CHF`
- Dates : `DD.MM.YYYY`

## Hors périmètre (pour l'instant)
- Authentification / gestion de comptes multiples.
- Import/migration depuis le fichier Excel.
- Sauvegardes automatisées.
- Export CSV / PDF.
- Tests automatisés.
- Mode sombre.
