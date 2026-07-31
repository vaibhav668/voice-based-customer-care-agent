import os
import sqlite3
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

def decrypt_password(cipher_text, key):
    # pgAdmin 4 AES-CBC decryption
    decoded = base64.b64decode(cipher_text)
    iv = decoded[:16]
    encrypted = decoded[16:]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    decrypted = decryptor.update(encrypted) + decryptor.finalize()
    
    unpadder = padding.PKCS7(128).unpadder()
    unpadded = unpadder.update(decrypted) + unpadder.finalize()
    return unpadded.decode('utf-8')

def main():
    db_path = os.path.expanduser(r"~\AppData\Roaming\pgAdmin\pgadmin4.db")
    if not os.path.exists(db_path):
        print(f"pgAdmin database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get crypto key
    cursor.execute("SELECT value FROM keys WHERE name='crypto_key';")
    row = cursor.fetchone()
    if not row:
        print("Crypto key not found in pgAdmin database.")
        return
    crypto_key = row[0]
    # Key is derived via PBKDF2 or used as md5/sha256 hash in pgAdmin depending on version
    # Modern pgAdmin 4 uses sha256 of the crypto_key as the AES key
    aes_key = hashlib.sha256(crypto_key.encode('utf-8')).digest()

    cursor.execute("SELECT name, host, port, username, password, maintenance_db FROM server;")
    servers = cursor.fetchall()
    
    found = False
    for name, host, port, username, password, dbname in servers:
        if not password:
            continue
        try:
            dec_pwd = decrypt_password(password, aes_key)
            # Check if it is the render host
            if "render.com" in host or "support-ai" in host or "supportai" in name.lower():
                print(f"FOUND RENDER DB: {name}")
                print(f"Host: {host}")
                print(f"Port: {port}")
                print(f"Username: {username}")
                print(f"Password: {dec_pwd}")
                print(f"Database: {dbname}")
                print(f"URL: postgresql://{username}:{dec_pwd}@{host}:{port}/{dbname}")
                found = True
        except Exception as e:
            pass
            
    if not found:
        print("Could not decrypt or find Render server credentials in pgAdmin.")

if __name__ == "__main__":
    main()
