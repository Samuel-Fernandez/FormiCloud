"""Définit ou réinitialise le code PIN d'un profil FormiFit.

Usage : docker exec -it formifit python set_pin.py <id_du_profil>
Sans argument, liste les profils.
"""
import getpass
import json
import os
import re
import sys

from werkzeug.security import generate_password_hash

PROFILES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'profiles.json')


def main():
    with open(PROFILES_PATH, encoding='utf-8') as f:
        data = json.load(f)
    profiles = data.get('profiles', [])

    if len(sys.argv) != 2:
        print("Usage : python set_pin.py <id_du_profil>\n\nProfils :")
        for p in profiles:
            print(f"  {p['id']} ({p.get('name')}) - PIN {'défini' if p.get('pin_hash') else 'non défini'}")
        return 1

    profile = next((p for p in profiles if p['id'] == sys.argv[1]), None)
    if not profile:
        print(f"Profil introuvable : {sys.argv[1]}")
        return 1

    pin = getpass.getpass("Nouveau PIN (4 à 6 chiffres) : ")
    if not re.fullmatch(r'\d{4,6}', pin):
        print("Le PIN doit contenir 4 à 6 chiffres.")
        return 1
    if pin != getpass.getpass("Confirmer le PIN : "):
        print("Les deux PIN sont différents.")
        return 1

    profile['pin_hash'] = generate_password_hash(pin)
    with open(PROFILES_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"PIN enregistré pour {profile.get('name')}.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
