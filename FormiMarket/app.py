from flask import Flask, render_template, request, redirect, url_for, jsonify
import json
import os

app = Flask(__name__)

import uuid

# Data file path
DATA_FILE = os.path.join('data', 'ingredients.json')
DATA_DISHES_FILE = os.path.join('data', 'dishes.json')
DATA_SCHEDULE_FILE = os.path.join('data', 'schedule.json')

def load_ingredients():
    """Charge la liste des ingrédients depuis le fichier JSON."""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def save_ingredients(ingredients):
    """Sauvegarde la liste des ingrédients dans le fichier JSON."""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(ingredients, f, indent=4, ensure_ascii=False)

def load_dishes():
    """Charge la liste des plats depuis le fichier JSON."""
    if not os.path.exists(DATA_DISHES_FILE):
        return []
    try:
        with open(DATA_DISHES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []

def save_dishes(dishes):
    """Sauvegarde la liste des plats dans le fichier JSON."""
    with open(DATA_DISHES_FILE, 'w', encoding='utf-8') as f:
        json.dump(dishes, f, indent=4, ensure_ascii=False)

def load_schedule():
    """Charge le planning de la semaine, crée des jours vides par défaut si innexistant."""
    if not os.path.exists(DATA_SCHEDULE_FILE):
        return {day: [] for day in ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']}
    try:
        with open(DATA_SCHEDULE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {day: [] for day in ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']}

def save_schedule(schedule):
    """Sauvegarde le planning de la semaine dans le fichier JSON."""
    with open(DATA_SCHEDULE_FILE, 'w', encoding='utf-8') as f:
        json.dump(schedule, f, indent=4, ensure_ascii=False)

@app.route('/')
def index():
    """Route principale affichant le dashboard (planning de la semaine)."""
    dishes = load_dishes()
    schedule = load_schedule()
    return render_template('index.html', dishes=dishes, schedule=schedule)

@app.route('/api/planner/add', methods=['POST'])
def add_planner_dish():
    """Ajoute un plat au planning pour un jour donné et check les ingrédients à acheter."""
    data = request.json
    dish_name = data.get('dish_name')
    day = data.get('day')
    
    if not dish_name or not day:
        return jsonify({'success': False, 'message': 'Missing data'})

    dishes = load_dishes()
    # verify dish exists
    selected_dish = next((d for d in dishes if d['name'] == dish_name), None)
    if not selected_dish:
         return jsonify({'success': False, 'message': 'Plat non trouvé'})

    schedule = load_schedule()
    if day not in schedule:
         return jsonify({'success': False, 'message': 'Jour invalide'})
    
    # Use a unique ID for the schedule item to allow multiples and exact moving
    item = {
        'id': str(uuid.uuid4()),
        'name': dish_name
    }
    schedule[day].append(item)
    save_schedule(schedule)

    # Update ingredients logic (existing check)
    ingredients = load_ingredients()
    dish_ingredients = selected_dish.get('ingredients', [])
    updated_ing = False
    existing_ing_map = {ing['name'].lower(): ing for ing in ingredients}
    
    for d_ing in dish_ingredients:
        lower = d_ing.lower()
        if lower in existing_ing_map:
            if not existing_ing_map[lower]['checked']:
                existing_ing_map[lower]['checked'] = True
                updated_ing = True
    
    if updated_ing:
        save_ingredients(ingredients)

    return jsonify({'success': True, 'item': item})

@app.route('/api/planner/move', methods=['POST'])
def move_planner_dish():
    """Déplace un plat programmé d'un jour à un autre dans le planning."""
    data = request.json
    item_id = data.get('item_id')
    to_day = data.get('to_day')
    
    schedule = load_schedule()
    
    # Find item
    found_day = None
    found_item = None
    for day, items in schedule.items():
        for item in items:
            if item.get('id') == item_id:
                found_day = day
                found_item = item
                break
        if found_day:
            break
            
    if not found_item:
        return jsonify({'success': False, 'message': 'Item not found'})
        
    if found_day == to_day:
        return jsonify({'success': True}) # No change
        
    # Remove from old
    schedule[found_day] = [i for i in schedule[found_day] if i['id'] != item_id]
    # Add to new
    schedule[to_day].append(found_item)
    
    save_schedule(schedule)
    return jsonify({'success': True})

@app.route('/api/planner/remove', methods=['POST'])
def remove_planner_dish():
    """Supprime un plat du planning de la semaine."""
    data = request.json
    item_id = data.get('item_id')
    
    schedule = load_schedule()
    
    found = False
    for day in schedule:
        original_len = len(schedule[day])
        schedule[day] = [i for i in schedule[day] if i.get('id') != item_id]
        if len(schedule[day]) < original_len:
            found = True
            break
            
    if found:
        save_schedule(schedule)
        return jsonify({'success': True})
        
    return jsonify({'success': False, 'message': 'Item not found'})

@app.route('/formibase')
def formibase():
    """Affiche la page de base de données gérant les plats et ingrédients existants."""
    dishes = load_dishes()
    ingredients = load_ingredients()
    # Sort dishes alphabetically
    dishes.sort(key=lambda x: x['name'].lower())
    return render_template('formibase.html', dishes=dishes, available_ingredients=ingredients)

@app.route('/shopping-list', methods=['GET', 'POST'])
def shopping_list():
    """Affiche et gère la liste de courses. Permet l'ajout manuel d'un ingrédient."""
    ingredients = load_ingredients()
    
    if request.method == 'POST':
        name = request.form.get('name')
        category = request.form.get('category').strip()
        price = request.form.get('price')
        
        if name and category:
            # Check if exists
            exists = False
            for ing in ingredients:
                if ing['name'].lower() == name.lower():
                    exists = True
                    break
            
            if not exists:
                new_ingredient = {
                    'name': name,
                    'category': category, 
                    'price': float(price) if price else None,
                    'checked': False
                }
                ingredients.append(new_ingredient)
                save_ingredients(ingredients)
            return redirect(url_for('shopping_list'))

    # Group by category
    grouped_ingredients = {}
    for ingredient in ingredients:
        cat = ingredient['category']
        if cat not in grouped_ingredients:
            grouped_ingredients[cat] = []
        grouped_ingredients[cat].append(ingredient)

    # Sort categories alphabetically
    sorted_categories = sorted(grouped_ingredients.keys())
    
    return render_template('shopping_list.html', grouped_ingredients=grouped_ingredients, sorted_categories=sorted_categories)

@app.route('/api/toggle', methods=['POST'])
def toggle_ingredient():
    """Coche ou décoche un ingrédient dans la liste de courses."""
    data = request.json
    name = data.get('name')
    ingredients = load_ingredients()
    
    for ing in ingredients:
        if ing['name'] == name:
            ing['checked'] = not ing['checked']
            break
            
    save_ingredients(ingredients)
    return jsonify({'success': True})

@app.route('/api/update', methods=['POST'])
def update_ingredient():
    """Met à jour les informations (nom, prix, catégorie) d'un ingrédient existant."""
    data = request.json
    original_name = data.get('original_name')
    new_name = data.get('new_name')
    category = data.get('category').strip()
    price = data.get('price')
    
    ingredients = load_ingredients()
    
    # Check if new name exists (if name changed)
    if original_name != new_name:
        for ing in ingredients:
            if ing['name'].lower() == new_name.lower():
                return jsonify({'success': False, 'message': 'Cet ingrédient existe déjà.'})
    
    updated = False
    for ing in ingredients:
        if ing['name'] == original_name:
            ing['name'] = new_name
            ing['category'] = category
            ing['price'] = float(price) if price else None
            updated = True
            break
            
    if updated:
        save_ingredients(ingredients)
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': 'Ingrédient non trouvé.'})

@app.route('/api/delete', methods=['POST'])
def delete_ingredient():
    """Supprime un ingrédient de la base de données de manière permanente."""
    data = request.json
    name = data.get('name')
    ingredients = load_ingredients()
    
    ingredients = [ing for ing in ingredients if ing['name'] != name]
    
    save_ingredients(ingredients)
    return jsonify({'success': True})

# Formibase API Routes
@app.route('/api/dishes/add', methods=['POST'])
def add_dish():
    """Ajoute un nouveau plat et ses ingrédients dans la base de données."""
    data = request.json
    name = data.get('name')
    dish_ingredients = data.get('ingredients', [])
    new_ingredients_details = data.get('new_ingredients_details', {})
    
    if not name:
        return jsonify({'success': False, 'message': 'Le nom du plat est requis.'})
        
    dishes = load_dishes()
    new_dish = {
        'id': str(uuid.uuid4()),
        'name': name,
        'ingredients': dish_ingredients
    }
    
    dishes.append(new_dish)
    save_dishes(dishes)
    
    # Check for new ingredients and add them to ingredients.json if they don't exist
    all_ingredients = load_ingredients()
    existing_names = set(ing['name'].lower() for ing in all_ingredients)
    added_new_ingredient = False
    
    for ing_name in dish_ingredients:
        if ing_name.lower() not in existing_names:
            details = new_ingredients_details.get(ing_name, {})
            category = details.get('category', 'Autres').strip()
            if not category:
                category = 'Autres'
            price_val = details.get('price')
            
            all_ingredients.append({
                'name': ing_name,
                'category': category,
                'price': float(price_val) if price_val else None,
                'checked': False
            })
            existing_names.add(ing_name.lower())
            added_new_ingredient = True
            
    if added_new_ingredient:
        save_ingredients(all_ingredients)
    
    return jsonify({'success': True, 'dish': new_dish})

@app.route('/api/dishes/update', methods=['POST'])
def update_dish():
    """Met à jour un plat existant et rajoute les nouveaux ingrédients détectés."""
    data = request.json
    dish_id = data.get('id')
    name = data.get('name')
    dish_ingredients = data.get('ingredients', [])
    new_ingredients_details = data.get('new_ingredients_details', {})
    
    dishes = load_dishes()
    updated = False
    
    for dish in dishes:
        if dish['id'] == dish_id:
            dish['name'] = name
            dish['ingredients'] = dish_ingredients
            updated = True
            break
            
    if updated:
        save_dishes(dishes)
        
        # Check for new ingredients
        all_ingredients = load_ingredients()
        existing_names = set(ing['name'].lower() for ing in all_ingredients)
        added_new_ingredient = False
        
        for ing_name in dish_ingredients:
            if ing_name.lower() not in existing_names:
                details = new_ingredients_details.get(ing_name, {})
                category = details.get('category', 'Autres').strip()
                if not category:
                    category = 'Autres'
                price_val = details.get('price')
                
                all_ingredients.append({
                    'name': ing_name,
                    'category': category,
                    'price': float(price_val) if price_val else None,
                    'checked': False
                })
                existing_names.add(ing_name.lower())
                added_new_ingredient = True
                
        if added_new_ingredient:
            save_ingredients(all_ingredients)
            
        return jsonify({'success': True})
        
    return jsonify({'success': False, 'message': 'Plat non trouvé.'})

@app.route('/api/dishes/delete', methods=['POST'])
def delete_dish():
    """Supprime un plat de la base de données."""
    data = request.json
    dish_id = data.get('id')
    
    dishes = load_dishes()
    dishes = [d for d in dishes if d['id'] != dish_id]
    
    save_dishes(dishes)
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1000, debug=False)
