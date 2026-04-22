from datetime import datetime

from mongo_client import users_collection
from auth_utils import hash_password, verify_password


def create_user(username: str, password: str):
    username = username.strip()

    if not username or not password:
        return False, "Nom d'utilisateur et mot de passe obligatoires."

    existing = users_collection.find_one({"username": username})
    if existing:
        return False, "Ce nom d'utilisateur existe déjà."

    users_collection.insert_one(
        {
            "username": username,
            "password_hash": hash_password(password),
            "created_at": datetime.utcnow(),
        }
    )
    return True, "Compte créé avec succès."


def authenticate_user(username: str, password: str) -> bool:
    user = users_collection.find_one({"username": username.strip()})
    if not user:
        return False

    return verify_password(password, user["password_hash"])