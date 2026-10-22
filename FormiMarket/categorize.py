import json

fruits_legumes = [
    'Brocolis', 'Brocoli', 'Carotte', 'Champignons de paris', 'Oignon', 'Tomate cerise', 
    'Concombre', 'Avocat', 'Maïs', 'Poivron', 'Courgette', 'Haricots vert', 
    'Ratatouille', 'Butternut', 'Salade', 'Tomate', 'Céleri', 'Poireau'
]

viandes_poissons = [
    'Blanc de poulet', 'Crevettes', 'Cabillaud', 'Thon', 'Poulet', 'Lard', 
    'Saumon', 'Poisson frit', 'Viande hachée', 'Jambon'
]

produits_laitiers = [
    'Crème', 'Gruyère', 'Mozarella', 'Oeufs', 'Lait', 'Fromage aux herbes', 
    'Séré', 'Fromage carré', 'Beurre', 'Crème de Soja'
]

epicerie = [
    'Pâtes', 'Persil', 'Ail', 'Cumin', 'Riz', 'Vermicelles', 'Sauce soja', 
    'Tomate conserve', 'Thym', 'Farine', 'Pizza industrielle', 'Tabasco', 'Olive', 
    'Lentilles', 'Guacamole', 'Sauce Salsa', 'Tortillas', 'Pain', 'Curry', 'Miel', 
    'Pain mbudget', 'Moutarde', 'Mayonnaise', 'Purée', 'Sauce tomate', 'Pain burger', 
    'Ketchup', 'Pois chiches', 'Spaghetti', 'Bouillon de légume', 'Coriandre', 
    'Pâte feuilletée', 'Feuille de brick', 'Sauce Salade', 'Tortellinis', 
    'Salade russe', 'Pain toast complet'
]

def get_category(name):
    if name in fruits_legumes: return "Fruits & Légumes"
    if name in viandes_poissons: return "Viandes & Poissons"
    if name in produits_laitiers: return "Produits Laitiers & Oeufs"
    if name in epicerie: return "Épicerie"
    return "Autres"

with open('data/ingredients.json', 'r') as f:
    ingredients = json.load(f)

for ing in ingredients:
    if ing['category'] == 'Autres' or ing['category'] == 'Légumes':
        # Re-categorize everything we know
        cat = get_category(ing['name'])
        if cat != "Autres":
            ing['category'] = cat
        elif ing['category'] == 'Légumes':
            ing['category'] = "Fruits & Légumes"

with open('data/ingredients.json', 'w') as f:
    json.dump(ingredients, f, indent=4, ensure_ascii=False)

print("Categorization complete.")
