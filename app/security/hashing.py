from argon2 import PasswordHasher

ph = PasswordHasher()

def hash_password(password):
    return ph.hash(password)

def verify_password(hash, password):
    try:
        return ph.verify(hash, password)
    except:
        return False