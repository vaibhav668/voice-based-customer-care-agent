import os
import sqlite3
import base64
import hashlib
import psycopg2
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

def try_connect(pwd):
    try:
        conn = psycopg2.connect(
            host="dpg-d96cbe5ckfvc73f9dda0-a.oregon-postgres.render.com",
            port=5432,
            user="dbuser",
            password=pwd,
            dbname="supportai_9q4b",
            connect_timeout=2
        )
        conn.close()
        return True
    except Exception:
        return False

def decrypt_cfb(ciphertext, key, iv):
    try:
        cipher = Cipher(algorithms.AES(key), modes.CFB(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    except Exception:
        return None

def decrypt_cbc(ciphertext, key, iv):
    try:
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted = decryptor.update(ciphertext) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        return unpadder.update(decrypted) + unpadder.finalize()
    except Exception:
        return None

def main():
    # Read variables from pgadmin4.db
    db_path = os.path.expanduser(r"~\AppData\Roaming\pgAdmin\pgadmin4.db")
    if not os.path.exists(db_path):
        print("pgAdmin DB not found")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT password FROM server WHERE name='support-ai-db';")
    enc_pwd_hex = cursor.fetchone()[0]
    
    cursor.execute("SELECT value FROM keys WHERE name='SECRET_KEY';")
    secret_key = cursor.fetchone()[0]
    
    cursor.execute("SELECT value FROM keys WHERE name='SECURITY_PASSWORD_SALT';")
    salt = cursor.fetchone()[0]
    
    conn.close()

    # The password stores '32' (version 2) + base64 encoded ciphertext
    if enc_pwd_hex.startswith('32') or enc_pwd_hex.startswith('31'):
        enc_pwd_hex = enc_pwd_hex[2:] # Strip version prefix
    
    # Or maybe the entire string is just hex string that represents ASCII version prefix + base64?
    # Let's decode hex first
    try:
        enc_bytes = bytes.fromhex(enc_pwd_hex)
        ascii_str = enc_bytes.decode('utf-8')
        if ascii_str.startswith('32') or ascii_str.startswith('31') or ascii_str.startswith('2') or ascii_str.startswith('1'):
            # It starts with version prefix
            # Remove prefix (e.g. '32' or '2')
            if ascii_str.startswith('32'):
                ascii_str = ascii_str[2:]
            elif ascii_str.startswith('2'):
                ascii_str = ascii_str[1:]
        ciphertext = base64.b64decode(ascii_str)
    except Exception:
        # Fallback to direct base64 decode if not hex
        try:
            ciphertext = base64.b64decode(enc_pwd_hex)
        except Exception:
            print("Failed to decode ciphertext")
            return

    print(f"Ciphertext length: {len(ciphertext)} bytes")
    iv = ciphertext[:16]
    encrypted_data = ciphertext[16:]

    # Key derivation candidates
    # pgAdmin uses PBKDF2 to derive the key from the master password/SECRET_KEY and user email
    # or SHA256 of the SECRET_KEY.
    # Let's try different key derivation options
    key_candidates = []

    # 1. Secret Key directly as SHA256
    key_candidates.append(hashlib.sha256(secret_key.encode('utf-8')).digest())
    key_candidates.append(hashlib.sha256(secret_key.encode('utf-8')).digest()[:16])
    
    # 2. Salt + Secret Key
    key_candidates.append(hashlib.sha256((secret_key + salt).encode('utf-8')).digest())

    # 3. PBKDF2 of Secret Key using salt as salt, iterations 1000
    for s in [salt, "salt", "pgadmin4", ""]:
        for iterations in [1000, 10000, 25000]:
            try:
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=s.encode('utf-8') if isinstance(s, str) else s,
                    iterations=iterations,
                    backend=default_backend()
                )
                key_candidates.append(kdf.derive(secret_key.encode('utf-8')))
            except Exception:
                pass

    # 4. Try pgadmin4@pgadmin.org + secret_key PBKDF2
    for user_email in ["pgadmin4@pgadmin.org", "pgadmin"]:
        for s in [salt, "salt", "pgadmin4", ""]:
            try:
                kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=s.encode('utf-8') if isinstance(s, str) else s,
                    iterations=1000,
                    backend=default_backend()
                )
                key_candidates.append(kdf.derive(user_email.encode('utf-8')))
            except Exception:
                pass

    print(f"Testing {len(key_candidates)} key candidates...")
    
    found = False
    for i, key in enumerate(key_candidates):
        for mode_name, decrypt_func in [("CFB", decrypt_cfb), ("CBC", decrypt_cbc)]:
            res = decrypt_func(encrypted_data, key, iv)
            if res:
                try:
                    dec_str = res.decode('utf-8')
                    if dec_str and len(dec_str) > 0 and all(32 <= ord(c) < 127 for c in dec_str):
                        # Verify against postgres
                        if try_connect(dec_str):
                            print(f"SUCCESS! Key index: {i}, Mode: {mode_name}")
                            print(f"Decrypted Password: {dec_str}")
                            found = True
                            break
                except Exception:
                    pass
        if found:
            break
            
    if not found:
        print("Failed to decrypt password using all key candidates.")

if __name__ == "__main__":
    main()
