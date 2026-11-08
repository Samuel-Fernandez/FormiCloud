from flask import Flask, render_template, redirect, url_for, request, jsonify, session, g
from werkzeug.security import check_password_hash, generate_password_hash
import hashlib
import json
import os
import re
import shutil
import time
import uuid
import datetime
from google import genai
from google.genai import types as genai_types
from groq import Groq

app = Flask(__name__)

# Pas de valeur par défaut : un secret public permettrait de forger une session.
app.secret_key = os.environ["FORMIFIT_SECRET_KEY"]
app.config.update(
    SESSION_COOKIE_NAME='formifit_session',
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    # FormiFit n'est servi qu'en HTTPS derrière Nginx Proxy Manager.
    SESSION_COOKIE_SECURE=os.environ.get("FORMIFIT_INSECURE_COOKIE") != "1",
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=30),
)

# --- IA : essayés dans l'ordre, on passe au suivant en cas d'erreur ou de quota atteint ---
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GEMINI_MODELS = [m.strip() for m in os.environ.get(
    "GEMINI_MODELS", "gemini-3.8-flash,gemini-3.5-flash-lite"
).split(",") if m.strip()]
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
AI_TIMEOUT_SECONDS = 20

gemini_client = genai.Client(
    api_key=GOOGLE_API_KEY,
    http_options=genai_types.HttpOptions(timeout=AI_TIMEOUT_SECONDS * 1000),
) if GOOGLE_API_KEY else None
groq_client = Groq(
    api_key=GROQ_API_KEY, timeout=AI_TIMEOUT_SECONDS, max_retries=0
) if GROQ_API_KEY else None

# --- Nutriments ---
CORE_NUTRIENTS = ['protein', 'carbs', 'fat', 'fiber', 'calcium', 'iron', 'vit_c']
# Absents des aliments enregistrés avant leur ajout : "inconnu" n'est pas "0".
LIPID_NUTRIENTS = ['sat_fat', 'cholesterol']
NUTRIENT_KEYS = ['kcal'] + CORE_NUTRIENTS + LIPID_NUTRIENTS

CHOLESTEROL_LIMIT_MG = 300
SAT_FAT_MAX_ENERGY_PCT = 10
SAT_FAT_LOW_ENERGY_PCT = 7

def empty_intake():
    intake = {key: 0 for key in NUTRIENT_KEYS}
    intake['consumed_items'] = []
    return intake

# Le propriétaire des aliments créés avant la séparation des comptes.
LEGACY_DB_OWNER = os.environ.get("FORMIFIT_LEGACY_OWNER", "samuel").lower()

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

def migrate_legacy_db():
    """Attribue au compte historique les aliments qui n'ont pas encore de propriétaire."""
    if not os.path.exists(get_db_path()) or not os.path.exists(get_profiles_path()):
        return
    db = load_db()
    orphans = [x for key in ('meals', 'workouts') for x in db.get(key, []) if not x.get('owner')]
    if not orphans:
        return
    owner = next((p for p in load_profiles()
                  if LEGACY_DB_OWNER in (str(p.get('id', '')).lower(), str(p.get('name', '')).lower())), None)
    if not owner:
        # Sans propriétaire, ces aliments restent invisibles pour tout le monde.
        app.logger.error("Migration impossible : profil '%s' introuvable.", LEGACY_DB_OWNER)
        return
    backup_path = get_db_path() + '.avant-comptes-prives.bak'
    if not os.path.exists(backup_path):
        shutil.copy2(get_db_path(), backup_path)
    for item in orphans:
        item['owner'] = owner['id']
    save_db(db)

def owned_db(owner_id):
    db = load_db()
    return {key: [x for x in db.get(key, []) if x.get('owner') == owner_id]
            for key in ('meals', 'workouts')}

def clean_item(raw, owner_id):
    """Valide un aliment ou une séance reçu du navigateur ou de l'IA. Lève ValueError/TypeError."""
    item_type = raw.get('type')
    name = str(raw.get('name') or '').strip()
    if item_type not in ('meal', 'workout') or not name:
        raise ValueError('Données invalides')
    cleaned = {
        'id': str(raw.get('id') or uuid.uuid4()),
        'owner': owner_id,
        'name': name[:200],
        'type': item_type,
        'kcal': float(raw.get('kcal') or 0),
    }
    for key in CORE_NUTRIENTS:
        cleaned[key] = float(raw.get(key) or 0)
    if item_type == 'meal':
        for key in LIPID_NUTRIENTS:
            if raw.get(key) not in (None, ''):
                cleaned[key] = float(raw[key])
    return cleaned

def upsert_item(item):
    """Enregistre un élément du compte. Renvoie False si l'id appartient à un autre compte."""
    db = load_db()
    existing = next((x for key in ('meals', 'workouts') for x in db.get(key, [])
                     if x.get('id') == item['id']), None)
    if existing and existing.get('owner') != item['owner']:
        return False
    for key in ('meals', 'workouts'):
        db[key] = [x for x in db.get(key, []) if x.get('id') != item['id']]
    db['meals' if item['type'] == 'meal' else 'workouts'].append(item)
    save_db(db)
    return True

def ldl_indicator(days):
    """Repère LDL déduit des repas, jamais une mesure : seule une prise de sang donne le LDL.

    Seuls les aliments dont les graisses saturées sont connues comptent, pour ne pas
    afficher "favorable" à cause d'aliments anciens sans cette donnée.
    """
    sat_fat = energy = cholesterol = 0.0
    tracked_days = 0
    for day in days:
        day_tracked = False
        for consumed in day.get('consumed_items') or []:
            item = consumed.get('item') or {}
            if item.get('type') == 'workout' or item.get('sat_fat') is None:
                continue
            factor = float(consumed.get('percentage', 100)) / 100
            sat_fat += float(item['sat_fat']) * factor
            cholesterol += float(item.get('cholesterol') or 0) * factor
            # Depuis les macros : les kcal nettes seraient faussées par le sport.
            energy += (float(item.get('protein') or 0) * 4 + float(item.get('carbs') or 0) * 4
                       + float(item.get('fat') or 0) * 9) * factor
            day_tracked = True
        tracked_days += day_tracked

    if energy <= 0:
        return {'level': 'unknown', 'label': 'Pas assez de données',
                'detail': "Ajoutez des aliments dont les graisses saturées sont renseignées."}

    pct_energy = sat_fat * 9 / energy * 100
    avg_cholesterol = cholesterol / tracked_days
    if pct_energy > SAT_FAT_MAX_ENERGY_PCT:
        level, label = 'watch', 'À surveiller'
    elif pct_energy > SAT_FAT_LOW_ENERGY_PCT or avg_cholesterol > CHOLESTEROL_LIMIT_MG:
        level, label = 'moderate', 'Modéré'
    else:
        level, label = 'favorable', 'Favorable'
    return {'level': level, 'label': label,
            'detail': f"Graisses saturées : {pct_energy:.1f} % des calories des repas suivis "
                      f"· cholestérol : {round(avg_cholesterol)} mg/jour"}

# --- Comptes (code PIN par profil) ---
PIN_PATTERN = re.compile(r'\d{4,6}')
MAX_PIN_FAILURES = 5
PIN_LOCK_SECONDS = 15 * 60
# En mémoire : Gunicorn tourne avec un seul worker (voir Dockerfile).
pin_failures = {}  # id du profil -> (nombre d'échecs, fin du blocage)

def find_profile(profiles, profile_id):
    return next((p for p in profiles if p.get('id') == profile_id), None)

def pin_fingerprint(profile):
    # Changer un PIN invalide les sessions ouvertes avec l'ancien.
    return hashlib.sha256(profile['pin_hash'].encode()).hexdigest()[:16]

def pin_lock_remaining(profile_id):
    count, locked_until = pin_failures.get(profile_id, (0, 0))
    if locked_until <= time.time():
        if count >= MAX_PIN_FAILURES or locked_until:
            pin_failures.pop(profile_id, None)
        return 0
    return locked_until - time.time() if count >= MAX_PIN_FAILURES else 0

def verify_pin(profile, pin):
    if check_password_hash(profile['pin_hash'], pin or ''):
        pin_failures.pop(profile['id'], None)
        return True
    count, _ = pin_failures.get(profile['id'], (0, 0))
    pin_failures[profile['id']] = (count + 1, time.time() + PIN_LOCK_SECONDS)
    return False

@app.before_request
def require_profile():
    if request.endpoint is None or request.endpoint in ('index', 'login', 'static'):
        return None

    is_api = request.path.startswith('/api/')
    profile = find_profile(load_profiles(), session.get('profile_id'))
    if not profile or not profile.get('pin_hash') or session.get('pin_fp') != pin_fingerprint(profile):
        session.clear()
        return (jsonify({'error': 'Session expirée'}), 401) if is_api else redirect(url_for('index'))

    g.profile_id = profile['id']

    # Une page restée ouverte sur un autre profil ne doit pas écrire dans le compte courant.
    claimed = (request.view_args or {}).get('username')
    if claimed is None and request.is_json:
        body = request.get_json(silent=True)
        if isinstance(body, dict):
            claimed = body.get('username')
    if claimed is not None and claimed != g.profile_id:
        return (jsonify({'error': 'Accès refusé'}), 403) if is_api else redirect(url_for('index'))
    return None

def check_and_rotate_days(user_profile):
    today_str = datetime.date.today().isoformat()
    if 'history' not in user_profile:
        user_profile['history'] = {}

    last_date = user_profile.get('last_date')
    if last_date and last_date != today_str:
        if 'today_intake' in user_profile:
            user_profile['history'][last_date] = user_profile['today_intake']
        user_profile['today_intake'] = empty_intake()

    user_profile['last_date'] = today_str

# --- Routes Pages ---
@app.route('/')
def index():
    profiles = [{'id': p['id'], 'name': p.get('name'), 'avatar': p.get('avatar')} for p in load_profiles()]
    return render_template('profile_selection.html', profiles=profiles)

@app.route('/login/<profile_id>', methods=['GET', 'POST'])
def login(profile_id):
    profile = find_profile(load_profiles(), profile_id)
    if not profile:
        return "Profil non trouvé", 404

    public_profile = {'id': profile['id'], 'name': profile.get('name'), 'avatar': profile.get('avatar')}
    if not profile.get('pin_hash'):
        return render_template('login.html', profile=public_profile, no_pin=True)

    if session.get('profile_id') == profile['id'] and session.get('pin_fp') == pin_fingerprint(profile):
        return redirect(url_for('dashboard', username=profile['id']))

    error = None
    if request.method == 'POST':
        remaining = pin_lock_remaining(profile['id'])
        if remaining > 0:
            error = f"Trop d'essais. Réessayez dans {int(remaining // 60) + 1} min."
        elif verify_pin(profile, request.form.get('pin')):
            session.clear()
            session.permanent = True
            session['profile_id'] = profile['id']
            session['pin_fp'] = pin_fingerprint(profile)
            return redirect(url_for('dashboard', username=profile['id']))
        else:
            error = "Code PIN incorrect."
    return render_template('login.html', profile=public_profile, error=error), (401 if error else 200)

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('index'))

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
        user_profile['today_intake'] = empty_intake()

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
        'vit_c': 90 if sex == 'homme' else 75,
        # Plafonds à ne pas dépasser, contrairement aux objectifs ci-dessus
        'sat_fat': round(tdee * SAT_FAT_MAX_ENERGY_PCT / 100 / 9),
        'cholesterol': CHOLESTEROL_LIMIT_MG
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
        target_intake = user_profile.get('history', {}).get(target_date_str, empty_intake())

    # Les journées enregistrées avant l'ajout d'un nutriment n'ont pas sa clé.
    target_intake = {**empty_intake(), **target_intake}

    # --- Vue Hebdomadaire ---
    monday_obj = target_date_obj - datetime.timedelta(days=target_date_obj.weekday())
    sunday_obj = monday_obj + datetime.timedelta(days=6)
    
    prev_week_date = monday_obj - datetime.timedelta(days=7)
    next_week_date = monday_obj + datetime.timedelta(days=7)
    
    weekly_intake = {key: 0 for key in NUTRIENT_KEYS}
    week_days = []

    for i in range(7):
        d = monday_obj + datetime.timedelta(days=i)
        d_str = d.isoformat()
        if d_str == today_str:
            day_data = user_profile.get('today_intake', {})
        else:
            day_data = user_profile.get('history', {}).get(d_str, {})
        week_days.append(day_data)

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

    db = owned_db(user_profile['id'])

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
        ldl_daily=ldl_indicator([target_intake]),
        ldl_weekly=ldl_indicator(week_days),
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
        
    return render_template('settings.html', user=user_profile, pin_status=request.args.get('pin'))

@app.route('/settings/<username>/pin', methods=['POST'])
def change_pin(username):
    profiles = load_profiles()
    profile = find_profile(profiles, g.profile_id)

    if pin_lock_remaining(profile['id']) > 0:
        status = 'locked'
    elif not verify_pin(profile, request.form.get('current_pin')):
        status = 'wrong'
    else:
        new_pin = request.form.get('new_pin') or ''
        if not PIN_PATTERN.fullmatch(new_pin):
            status = 'invalid'
        elif new_pin != request.form.get('confirm_pin'):
            status = 'mismatch'
        else:
            profile['pin_hash'] = generate_password_hash(new_pin)
            save_profiles(profiles)
            session['pin_fp'] = pin_fingerprint(profile)
            status = 'ok'
    return redirect(url_for('settings', username=username, pin=status) + '#pin')

# --- IA ---
AI_SYSTEM_PROMPT = """Tu es un expert en nutrition de l'application FormiFit.
L'utilisateur va te décrire un repas (ex: 200g de poulet, 100g de riz) ou un entraînement (ex: 30 minutes de course).
Estime précisément les valeurs nutritionnelles ou les calories brûlées (en négatif pour les entraînements).
Tu dois obligatoirement répondre au format JSON valide avec la structure suivante :
{"type": "meal" ou "workout", "name": "nom descriptif", "kcal": 0, "protein": 0, "carbs": 0, "fat": 0, "sat_fat": 0, "cholesterol": 0, "fiber": 0, "calcium": 0, "iron": 0, "vit_c": 0}
Unités : kcal en kcal ; protein, carbs, fat, sat_fat (acides gras saturés, inclus dans fat) et fiber en grammes ; cholesterol, calcium, iron et vit_c en milligrammes.
Si c'est un entraînement, "kcal" doit être un nombre négatif (ex: -300), et tous les autres macronutriments/micronutriments à 0."""

def ask_gemini(model, message):
    response = gemini_client.models.generate_content(
        model=model,
        contents=message,
        config=genai_types.GenerateContentConfig(
            system_instruction=AI_SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    return response.text

def ask_groq(message):
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": AI_SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    return response.choices[0].message.content

def ai_providers():
    providers = []
    if gemini_client:
        providers += [(f"gemini:{m}", lambda msg, model=m: ask_gemini(model, msg)) for m in GEMINI_MODELS]
    if groq_client:
        providers.append((f"groq:{GROQ_MODEL}", ask_groq))
    return providers

# --- Routes API (AJAX) ---
@app.route('/api/chat', methods=['POST'])
def chat():
    body = request.get_json(silent=True) or {}
    user_message = body.get('message')
    if not user_message or not isinstance(user_message, str):
        return jsonify({'error': 'Message manquant'}), 400
    user_message = user_message[:2000]

    for provider_name, ask in ai_providers():
        try:
            data = json.loads(ask(user_message))
            data.pop('id', None)
            return jsonify(clean_item(data, g.profile_id))
        except Exception as e:
            app.logger.warning("IA %s indisponible : %s", provider_name, e)

    return jsonify({'error': "Aucune IA n'est disponible pour le moment. Réessayez plus tard."}), 503

@app.route('/api/save_to_db', methods=['POST'])
def save_to_db():
    try:
        item = clean_item(request.get_json(silent=True) or {}, g.profile_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'Données invalides'}), 400

    if not upsert_item(item):
        return jsonify({'error': 'Élément non trouvé'}), 404
    return jsonify({'success': True, 'item': item})

@app.route('/api/consume', methods=['POST'])
def consume():
    data = request.json
    username = g.profile_id
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
            user_profile['today_intake'] = empty_intake()
        intake_ref = user_profile['today_intake']
    else:
        if 'history' not in user_profile:
            user_profile['history'] = {}
        if target_date not in user_profile['history']:
            user_profile['history'][target_date] = empty_intake()
        intake_ref = user_profile['history'][target_date]

    for key in NUTRIENT_KEYS:
        if item.get(key) is not None:
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
    weekly_intake = {key: 0 for key in NUTRIENT_KEYS}
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
    username = g.profile_id
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
            if k in NUTRIENT_KEYS:
                user_profile['today_intake'][k] = float(v)
    else:
        if 'history' not in user_profile:
            user_profile['history'] = {}
        if target_date not in user_profile['history']:
            user_profile['history'][target_date] = {}
        for k, v in new_data.items():
            if k in NUTRIENT_KEYS:
                user_profile['history'][target_date][k] = float(v)

    save_profiles(profiles)
    return jsonify({'success': True})

@app.route('/api/delete_consumed_item', methods=['POST'])
def delete_consumed_item():
    data = request.json
    username = g.profile_id
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
        for key in NUTRIENT_KEYS:
            if item.get(key) is not None:
                val = float(item[key]) * pct
                intake_ref[key] = max(0, round(intake_ref.get(key, 0) - val))
        
        save_profiles(profiles)
        return jsonify({'success': True})
    return jsonify({'error': 'Item non trouvé'}), 404

@app.route('/api/update_consumed_item', methods=['POST'])
def update_consumed_item():
    data = request.json
    username = g.profile_id
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
        
        for key in NUTRIENT_KEYS:
            if item.get(key) is not None:
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
    try:
        cleaned_item = clean_item(request.get_json(silent=True) or {}, g.profile_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'Données invalides'}), 400

    if not upsert_item(cleaned_item):
        return jsonify({'error': 'Élément non trouvé'}), 404
    return jsonify({'success': True, 'item': cleaned_item})

@app.route('/api/db/delete/<item_id>', methods=['POST'])
def db_delete(item_id):
    db = load_db()

    def is_target(x):
        return x.get('id') == item_id and x.get('owner') == g.profile_id

    if not any(is_target(x) for key in ('meals', 'workouts') for x in db.get(key, [])):
        return jsonify({'error': 'Élément non trouvé'}), 404

    for key in ('meals', 'workouts'):
        db[key] = [x for x in db.get(key, []) if not is_target(x)]

    save_db(db)
    return jsonify({'success': True})

migrate_legacy_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1004, debug=False)
