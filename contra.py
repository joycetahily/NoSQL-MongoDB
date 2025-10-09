from pymongo import MongoClient
import hashlib

# Conexión a MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["AlojaT"]
usuarios = db["usuarios"]

# Recorrer todos los usuarios
for u in usuarios.find():
    if "contraseña" in u:
        plain = u["contraseña"]  # contraseña actual en texto plano
        hashed = hashlib.sha256(plain.encode()).hexdigest()
        usuarios.update_one(
            {"_id": u["_id"]},
            {"$set": {"contraseña": hashed}}
        )
        print(f"Usuario {u['correo']} actualizado.")
print("✅ Todas las contraseñas han sido convertidas a hash SHA256.")
