from flask import Flask, render_template, redirect, url_for, request, jsonify
import json
import os
import uuid
import datetime
import google.generativeai as genai

app = Flask(__name__)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

# --- Fichiers ---
def get_profiles_path():
    return os.path.join(os.path.dirname(__file__), 'data', 'profiles.json')

def get_db_path():
    return os.path.join(os.path.dirname(__file__), 'data', 'database.json')

def load_profiles():
    with open(get_profiles_path(), 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('profiles', [])

def save_profiles(profiles_list):
    with open(get_profiles_path(), 'w', encoding='utf-8') as f:
        json.dump({'profiles': profiles_list}, f, indent=2, ensure_ascii=False)

def load_db():
    if not os.path.exists(get_db_path()):
        return {"meals": [], "workouts": []}
    with open(get_db_path(), 'r', encoding='utf-8') as f:
        return json.load(f)

def save_db(data):
    with open(get_db_path(), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def check_and_rotate_days(user_profile):
    today_str = datetime.date.today().isoformat()
    if 'history' not in user_profile:
        user_profile['history'] = {}

    last_date = user_profile.get('last_date')
    if last_date and last_date != today_str:
        if 'today_intake' in user_profile:
            user_profile['history'][last_date] = user_profile['today_intake']
        user_profile['today_intake'] = {
            'kcal': 0, 'protein': 0, 'carbs': 0, 'fat': 0,
            'fiber': 0, 'calcium': 0, 'iron': 0, 'vit_c': 0,
            'consumed_items': []
        }

    user_profile['last_date'] = today_str

# --- Routes Pages ---
@app.route('/')
def index():
    profiles = load_profiles()
    return render_template('profile_selection.html', profiles=profiles)

@app.route('/dashboard/<username>')
def dashboard(username):
    profiles = load_profiles()
    user_profile = next((p for p in profiles if p['id'] == username), None)
    
    if not user_profile:
        return "Profil non trouvé", 404
        
    required_fields = ['weight', 'height', 'age', 'sex']
    if not all(user_profile.get(k) for k in required_fields):
        return redirect(url_for('settings', username=username))

    # --- Gestion des Jours ---
    check_and_rotate_days(user_profile)
    today_str = user_profile['last_date']

    if 'today_intake' not in user_profile:
        user_profile['today_intake'] = {
            'kcal': 0, 'protein': 0, 'carbs': 0, 'fat': 0,
            'fiber': 0, 'calcium': 0, 'iron': 0, 'vit_c': 0,
            'consumed_items': []
        }
    
    # Save the rotation
    save_profiles(profiles)
        
    weight = float(user_profile.get('weight'))
    height = float(user_profile.get('height'))
    age = int(user_profile.get('age'))
    sex = user_profile.get('sex')
    body_fat = user_profile.get('body_fat')

    if body_fat:
        bf = float(body_fat)
        lean_mass = weight * (1 - bf / 100)
        bmr = 370 + (21.6 * lean_mass)
    else:
        if sex == 'homme':
            bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
        else:
            bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

    tdee = bmr * 1.2
    base_tdee = tdee
    
    # --- Objectif de Sèche ---
    target_weight = user_profile.get('target_weight')
    cut_timeframe = user_profile.get('cut_timeframe')

    if target_weight and cut_timeframe:
        try:
            tw = float(target_weight)
            days = int(cut_timeframe)
            if tw < weight:
                deficit_total = (weight - tw) * 7700
                deficit_daily = deficit_total / days
                tdee -= deficit_daily
        except ValueError:
            pass

    target_protein = weight * 2
    target_fat = weight * 1
    # Check si les protéines et lipides dépassent les calories
    fixed_cals = (target_protein * 4) + (target_fat * 9)
    if fixed_cals > tdee:
        # On réduit un peu les lipides si vraiment ça bloque
        target_fat = (tdee - (target_protein * 4)) / 9
        if target_fat < weight * 0.5: 
            target_fat = weight * 0.5
        target_carbs = max(0, (tdee - (target_protein * 4 + target_fat * 9)) / 4)
    else:
        target_carbs = (tdee - fixed_cals) / 4
    
    targets = {
        'kcal': round(tdee),
        'protein': round(target_protein),
        'carbs': round(target_carbs),
        'fat': round(target_fat),
        'fiber': 30,
        'calcium': 1000,
        'iron': 8 if sex == 'homme' else 18,
        'vit_c': 90 if sex == 'homme' else 75
    }

    target_date_str = request.args.get('date', today_str)
    try:
        target_date_obj = datetime.date.fromisoformat(target_date_str)
    except ValueError:
        target_date_obj = datetime.date.today()
        target_date_str = today_str

    if target_date_str == today_str:
        target_intake = user_profile.get('today_intake', {})
    else:
        target_intake = user_profile.get('history', {}).get(target_date_str, {
            'kcal': 0, 'protein': 0, 'carbs': 0, 'fat': 0,
            'fiber': 0, 'calcium': 0, 'iron': 0, 'vit_c': 0,
            'consumed_items': []
        })

    # --- Vue Hebdomadaire ---
    monday_obj = target_date_obj - datetime.timedelta(days=target_date_obj.weekday())
    sunday_obj = monday_obj + datetime.timedelta(days=6)
    
    prev_week_date = monday_obj - datetime.timedelta(days=7)
    next_week_date = monday_obj + datetime.timedelta(days=7)
    
    weekly_intake = {
        'kcal': 0, 'protein': 0, 'carbs': 0, 'fat': 0,
        'fiber': 0, 'calcium': 0, 'iron': 0, 'vit_c': 0
    }
    
    for i in range(7):
        d = monday_obj + datetime.timedelta(days=i)
        d_str = d.isoformat()
        if d_str == today_str:
            day_data = user_profile.get('today_intake', {})
        else:
            day_data = user_profile.get('history', {}).get(d_str, {})
            
        for k in weekly_intake:
            weekly_intake[k] += day_data.get(k, 0)
            
    weekly_targets = {k: v * 7 for k, v in targets.items()}
    
    pct = {}
    for k in targets:
        if targets[k] > 0:
            percentage = (target_intake.get(k, 0) / targets[k]) * 100
        else:
            percentage = 0
        pct[k] = min(round(percentage), 100)
        
    for k in pct:
        if pct[k] < 0: pct[k] = 0

    # --- Préparation 7 Jours (Lundi à Dimanche) ---
    labels_7d = []
    data_7d = []
    target_7d = []
    days_with_data = 0
    total_consumed = 0
    
    jours_fr_court = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]

    for i in range(7):
        d = monday_obj + datetime.timedelta(days=i)
        d_str = d.isoformat()
        labels_7d.append(f"{jours_fr_court[i]} {d.strftime('%d/%m')}")
        
        c = 0
        has_data = False
        
        if d_str == today_str:
            c = user_profile['today_intake'].get('kcal', 0)
            if c != 0:
                has_data = True
        else:
            if d_str in user_profile.get('history', {}):
                c = user_profile['history'][d_str].get('kcal', 0)
                has_data = True
                
        data_7d.append(c)
        target_7d.append(round(tdee))
        
        if has_data:
            days_with_data += 1
            total_consumed += c

    if days_with_data == 0:
        weekly_diff = 0
        real_weekly_diff = 0
        kg_diff_str = "0"
        real_diff_str = "0"
    else:
        weekly_diff = round(total_consumed - (days_with_data * round(tdee)))
        real_weekly_diff = round(total_consumed - (days_with_data * round(base_tdee)))
        kg_diff = round(real_weekly_diff / 7700, 2)
        kg_diff_str = f"+{kg_diff}" if kg_diff > 0 else f"{kg_diff}"
        real_diff_str = f"+{real_weekly_diff}" if real_weekly_diff > 0 else f"{real_weekly_diff}"

    db = load_db()
    
    jours_fr = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    week_dates = []
    jours_fr_court = ["Lun", "Mar", "Mer", "Jeu", "Ven", "Sam", "Dim"]
    for i in range(7):
        d = monday_obj + datetime.timedelta(days=i)
        if d.isoformat() == today_str:
            label = f"Aujourd'hui ({jours_fr[i]} {d.strftime('%d/%m')})"
        else:
            label = f"{jours_fr[i]} {d.strftime('%d/%m')}"
        week_dates.append({
            "val": d.isoformat(),
            "label": label,
            "short_day": jours_fr_court[i],
            "date_str": d.strftime('%d/%m')
        })

    return render_template(
        'dashboard.html', 
        user=user_profile, 
        targets=targets, 
        intake=target_intake, 
        pct=pct, 
        weekly_targets=weekly_targets,
        weekly_intake=weekly_intake,
        db=db,
        labels_7d=labels_7d,
        data_7d=data_7d,
        target_7d=target_7d,
        week_dates=week_dates,
        weekly_diff=weekly_diff,
        days_with_data=days_with_data,
        real_diff_str=real_diff_str,
        kg_diff_str=kg_diff_str,
        today_str=today_str,
        target_date_str=target_date_str,
        prev_week_str=prev_week_date.isoformat(),
        next_week_str=next_week_date.isoformat(),
        monday_str=monday_obj.strftime('%d/%m'),
        sunday_str=sunday_obj.strftime('%d/%m'),
        history=user_profile.get('history', {}),
        today_intake=user_profile.get('today_intake', {})
    )

@app.route('/settings/<username>', methods=['GET', 'POST'])
def settings(username):
    profiles = load_profiles()
    user_profile = next((p for p in profiles if p['id'] == username), None)
    
    if not user_profile:
        return "Profil non trouvé", 404
        
    if request.method == 'POST':
        user_profile['weight'] = request.form.get('weight')
        user_profile['height'] = request.form.get('height')
        user_profile['age'] = request.form.get('age')
        user_profile['sex'] = request.form.get('sex')
        user_profile['body_fat'] = request.form.get('body_fat')
        user_profile['target_weight'] = request.form.get('target_weight')
        user_profile['cut_timeframe'] = request.form.get('cut_timeframe')
        
        save_profiles(profiles)
        return redirect(url_for('dashboard', username=username))
        
    return render_template('settings.html', user=user_profile)

# --- Routes API (AJAX) ---
@app.route('/api/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({'error': 'Message manquant'}), 400

    system_prompt = """Tu es un expert en nutrition de l'application FormiFit. 
L'utilisateur va te décrire un repas (ex: 200g de poulet, 100g de riz) ou un entraînement (ex: 30 minutes de course).
Estime précisément les valeurs nutritionnelles ou les calories brûlées (en négatif pour les entraînements).
Tu dois obligatoirement répondre au format JSON valide avec la structure suivante :
{"type": "meal" ou "workout", "name": "nom descriptif", "kcal": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0, "calcium": 0, "iron": 0, "vit_c": 0}
Si c'est un entraînement, "kcal" doit être un nombre négatif (ex: -300), et tous les autres macronutriments/micronutriments à 0."""

    try:
        model = genai.GenerativeModel(
            'gemini-2.5-flash',
            system_instruction=system_prompt,
        )
        response = model.generate_content(
            user_message,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
            )
        )
        content = response.text
        data = json.loads(content)
        data['id'] = str(uuid.uuid4())
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/save_to_db', methods=['POST'])
def save_to_db():
    item = request.json
    db = load_db()
    
    if item.get('type') not in ['meal', 'workout']:
        return jsonify({'error': 'Type invalide'}), 400
        
    if item['type'] == 'meal':
        db['meals'].append(item)
    else:
        db['workouts'].append(item)
        
    save_db(db)
    return jsonify({'success': True, 'item': item})

@app.route('/api/consume', methods=['POST'])
def consume():
    data = request.json
    username = data.get('username')
    item = data.get('item')
    percentage = float(data.get('percentage', 100)) / 100.0
    target_date = data.get('target_date', 'today')

    profiles = load_profiles()
    user_profile = next((p for p in profiles if p['id'] == username), None)
    if not user_profile:
        return jsonify({'error': 'Utilisateur non trouvé'}), 404

    check_and_rotate_days(user_profile)
    today_str = user_profile['last_date']

    if target_date == 'today' or target_date == today_str:
        if 'today_intake' not in user_profile:
            user_profile['today_intake'] = {
                'kcal': 0, 'protein': 0, 'carbs': 0, 'fat': 0,
                'fiber': 0, 'calcium': 0, 'iron': 0, 'vit_c': 0
            }
        intake_ref = user_profile['today_intake']
    else:
        if 'history' not in user_profile:
            user_profile['history'] = {}
        if target_date not in user_profile['history']:
            user_profile['history'][target_date] = {
                'kcal': 0, 'protein': 0, 'carbs': 0, 'fat': 0,
                'fiber': 0, 'calcium': 0, 'iron': 0, 'vit_c': 0
            }
        intake_ref = user_profile['history'][target_date]

    for key in ['kcal', 'protein', 'carbs', 'fat', 'fiber', 'calcium', 'iron', 'vit_c']:
        if key in item:
            val = float(item[key]) * percentage
            intake_ref[key] = round(intake_ref.get(key, 0) + val)

    if 'consumed_items' not in intake_ref:
        intake_ref['consumed_items'] = []
    
    intake_ref['consumed_items'].append({
        'instance_id': str(uuid.uuid4()),
        'item': item,
        'percentage': percentage * 100 # Store as 0-500%
    })

    save_profiles(profiles)

    # Re-calculate 7 days data
    data_7d = []
    for i in range(6, -1, -1):
        d_str = (datetime.date.today() - datetime.timedelta(days=i)).isoformat()
        if d_str == today_str:
            data_7d.append(user_profile.get('today_intake', {}).get('kcal', 0))
        else:
            data_7d.append(user_profile.get('history', {}).get(d_str, {}).get('kcal', 0))

    # Calculate weekly intake (Monday to Sunday)
    today_obj = datetime.date.today()
    monday_obj = today_obj - datetime.timedelta(days=today_obj.weekday())
    weekly_intake = {
        'kcal': 0, 'protein': 0, 'carbs': 0, 'fat': 0,
        'fiber': 0, 'calcium': 0, 'iron': 0, 'vit_c': 0
    }
    for i in range(7):
        d = monday_obj + datetime.timedelta(days=i)
        d_str = d.isoformat()
        if d_str == today_str:
            day_data = user_profile.get('today_intake', {})
        else:
            day_data = user_profile.get('history', {}).get(d_str, {})
            
        for k in weekly_intake:
            weekly_intake[k] += day_data.get(k, 0)

    return jsonify({
        'success': True, 
        'new_intake': user_profile.get('today_intake', {}),
        'new_weekly_intake': weekly_intake,
        'new_data_7d': data_7d
    })

@app.route('/api/update_intake', methods=['POST'])
def update_intake():
    data = request.json
    username = data.get('username')
    target_date = data.get('target_date')
    new_data = data.get('new_data')

    profiles = load_profiles()
    user_profile = next((p for p in profiles if p['id'] == username), None)
    if not user_profile:
        return jsonify({'error': 'Utilisateur non trouvé'}), 404

    check_and_rotate_days(user_profile)
    today_str = user_profile['last_date']
    if target_date == 'today' or target_date == today_str:
        if 'today_intake' not in user_profile:
            user_profile['today_intake'] = {}
        for k, v in new_data.items():
            user_profile['today_intake'][k] = float(v)
    else:
        if 'history' not in user_profile:
            user_profile['history'] = {}
        if target_date not in user_profile['history']:
            user_profile['history'][target_date] = {}
        for k, v in new_data.items():
            user_profile['history'][target_date][k] = float(v)

    save_profiles(profiles)
    return jsonify({'success': True})

@app.route('/api/delete_consumed_item', methods=['POST'])
def delete_consumed_item():
    data = request.json
    username = data.get('username')
    target_date = data.get('target_date')
    instance_id = data.get('instance_id')

    profiles = load_profiles()
    user_profile = next((p for p in profiles if p['id'] == username), None)
    if not user_profile:
        return jsonify({'error': 'Utilisateur non trouvé'}), 404

    check_and_rotate_days(user_profile)
    today_str = user_profile['last_date']
    if target_date == 'today' or target_date == today_str:
        intake_ref = user_profile.get('today_intake')
    else:
        intake_ref = user_profile.get('history', {}).get(target_date)

    if not intake_ref or 'consumed_items' not in intake_ref:
        return jsonify({'error': 'Données non trouvées'}), 404

    items = intake_ref['consumed_items']
    idx = next((i for i, x in enumerate(items) if x.get('instance_id') == instance_id), None)
    
    if idx is not None:
        consumed = items.pop(idx)
        pct = consumed['percentage'] / 100.0
        item = consumed['item']
        for key in ['kcal', 'protein', 'carbs', 'fat', 'fiber', 'calcium', 'iron', 'vit_c']:
            if key in item:
                val = float(item[key]) * pct
                intake_ref[key] = max(0, round(intake_ref.get(key, 0) - val))
        
        save_profiles(profiles)
        return jsonify({'success': True})
    return jsonify({'error': 'Item non trouvé'}), 404

@app.route('/api/update_consumed_item', methods=['POST'])
def update_consumed_item():
    data = request.json
    username = data.get('username')
    target_date = data.get('target_date')
    instance_id = data.get('instance_id')
    new_percentage = float(data.get('new_percentage', 100))

    profiles = load_profiles()
    user_profile = next((p for p in profiles if p['id'] == username), None)
    if not user_profile:
        return jsonify({'error': 'Utilisateur non trouvé'}), 404

    check_and_rotate_days(user_profile)
    today_str = user_profile['last_date']
    if target_date == 'today' or target_date == today_str:
        intake_ref = user_profile.get('today_intake')
    else:
        intake_ref = user_profile.get('history', {}).get(target_date)

    if not intake_ref or 'consumed_items' not in intake_ref:
        return jsonify({'error': 'Données non trouvées'}), 404

    items = intake_ref['consumed_items']
    idx = next((i for i, x in enumerate(items) if x.get('instance_id') == instance_id), None)
    
    if idx is not None:
        consumed = items[idx]
        old_pct = consumed['percentage'] / 100.0
        new_pct = new_percentage / 100.0
        item = consumed['item']
        
        for key in ['kcal', 'protein', 'carbs', 'fat', 'fiber', 'calcium', 'iron', 'vit_c']:
            if key in item:
                diff = float(item[key]) * (new_pct - old_pct)
                intake_ref[key] = max(0, round(intake_ref.get(key, 0) + diff))
                
        consumed['percentage'] = new_percentage
        save_profiles(profiles)
        return jsonify({'success': True})
    return jsonify({'error': 'Item non trouvé'}), 404

@app.route('/api/export_json/<username>', methods=['GET'])
def export_json(username):
    profiles = load_profiles()
    user_profile = next((p for p in profiles if p['id'] == username), None)
    if not user_profile:
        return jsonify({'error': 'Utilisateur non trouvé'}), 404

    try:
        weeks = int(request.args.get('weeks', 4))
        if weeks < 1 or weeks > 52:
            return jsonify({'error': 'Le nombre de semaines doit être compris entre 1 et 52'}), 400
    except ValueError:
        return jsonify({'error': 'Nombre de semaines invalide'}), 400

    check_and_rotate_days(user_profile)
    today_str = user_profile['last_date']
    today_obj = datetime.date.fromisoformat(today_str)

    result_history = {}
    for i in range(7 * weeks - 1, -1, -1):
        d = today_obj - datetime.timedelta(days=i)
        d_str = d.isoformat()

        if d_str == today_str:
            intake = user_profile.get('today_intake', {})
            if intake:
                result_history[d_str] = intake
        else:
            intake = user_profile.get('history', {}).get(d_str)
            if intake:
                result_history[d_str] = intake

    export_payload = {
        "user": {
            "id": user_profile.get("id"),
            "name": user_profile.get("name"),
            "weight": user_profile.get("weight"),
            "height": user_profile.get("height"),
            "age": user_profile.get("age"),
            "sex": user_profile.get("sex"),
            "body_fat": user_profile.get("body_fat")
        },
        "export_date": today_str,
        "weeks_exported": weeks,
        "history": result_history
    }

    return jsonify(export_payload)

@app.route('/api/db/save', methods=['POST'])
def db_save():
    item = request.json
    if not item or not item.get('name') or not item.get('type'):
        return jsonify({'error': 'Données invalides'}), 400

    db = load_db()
    item_id = item.get('id')

    # If no ID, generate a new one
    if not item_id:
        item_id = str(uuid.uuid4())
        item['id'] = item_id

    item_type = item.get('type')
    if item_type not in ['meal', 'workout']:
        return jsonify({'error': 'Type invalide'}), 400

    # Clean and convert values
    try:
        cleaned_item = {
            'id': item_id,
            'name': str(item['name']),
            'type': item_type,
            'kcal': float(item.get('kcal') or 0),
            'protein': float(item.get('protein') or 0),
            'carbs': float(item.get('carbs') or 0),
            'fat': float(item.get('fat') or 0),
            'fiber': float(item.get('fiber') or 0),
            'calcium': float(item.get('calcium') or 0),
            'iron': float(item.get('iron') or 0),
            'vit_c': float(item.get('vit_c') or 0)
        }
    except (ValueError, TypeError):
        return jsonify({'error': 'Valeurs nutritionnelles invalides'}), 400

    # Target list and other list to handle type changes
    if item_type == 'meal':
        db['meals'] = [x for x in db.get('meals', []) if x.get('id') != item_id]
        db['workouts'] = [x for x in db.get('workouts', []) if x.get('id') != item_id]
        db['meals'].append(cleaned_item)
    else:
        db['meals'] = [x for x in db.get('meals', []) if x.get('id') != item_id]
        db['workouts'] = [x for x in db.get('workouts', []) if x.get('id') != item_id]
        db['workouts'].append(cleaned_item)

    save_db(db)
    return jsonify({'success': True, 'item': cleaned_item})

@app.route('/api/db/delete/<item_id>', methods=['POST'])
def db_delete(item_id):
    db = load_db()

    meals_len = len(db.get('meals', []))
    db['meals'] = [x for x in db.get('meals', []) if x.get('id') != item_id]

    workouts_len = len(db.get('workouts', []))
    db['workouts'] = [x for x in db.get('workouts', []) if x.get('id') != item_id]

    if len(db['meals']) == meals_len and len(db['workouts']) == workouts_len:
        return jsonify({'error': 'Élément non trouvé'}), 404

    save_db(db)
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1004, debug=False)
