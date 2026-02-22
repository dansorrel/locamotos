from werkzeug.security import generate_password_hash, check_password_hash
import re

def hash_password(password):
    """Hashes a password for storing in the database."""
    return generate_password_hash(password)

def verify_password(stored_password_hash, provided_password):
    """Verifies a provided password against a stored hash."""
    return check_password_hash(stored_password_hash, provided_password)

def is_strong_password(password):
    """
    Validates that a password meets strength requirements:
    - At least 8 characters
    - At least 1 uppercase letter
    - At least 1 lowercase letter
    - At least 1 number
    """
    if len(password) < 8:
        return False, "A senha deve ter pelo menos 8 caracteres."
    if not re.search(r"[A-Z]", password):
        return False, "A senha deve conter pelo menos uma letra maiúscula."
    if not re.search(r"[a-z]", password):
        return False, "A senha deve conter pelo menos uma letra minúscula."
    if not re.search(r"[0-9]", password):
        return False, "A senha deve conter pelo menos um número."
        
    return True, "Senha válida."
