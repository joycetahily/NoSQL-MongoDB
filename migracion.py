from pymongo import MongoClient
from bson import ObjectId

# --- Conexión a MongoDB ---
client = MongoClient("mongodb://localhost:27017/")
db = client["AlojaT"]
propiedades = db["propiedades"]
reseñas = db["reseñas"]

print("Conectado a la base de datos AlojaT.")

# 1. Obtenemos IDs de todas las propiedades
lista_propiedades = list(propiedades.find({}, {"_id": 1}))
ids_propiedades = [p["_id"] for p in lista_propiedades]

print(f"Se encontraron {len(ids_propiedades)} propiedades.")

# 2. Preparamos el pipeline de agregación para calcular el promedio de TODAS
pipeline = [
    {
        "$match": {
            "propiedad_id": {"$in": ids_propiedades}
        }
    },
    {
        "$group": {
            "_id": "$propiedad_id",
            "avg_rating": {"$avg": "$calificacion"}
        }
    }
]

# 3. Ejecutamos la agregación
resultados_avg = list(reseñas.aggregate(pipeline))

print(f"Se calcularon {len(resultados_avg)} promedios de calificación.")

contador_actualizadas = 0

# 4. Actualizamos cada propiedad con su promedio
for res in resultados_avg:
    prop_id = res["_id"]
    calif_promedio = round(res['avg_rating'], 1)
    
    propiedades.update_one(
        {"_id": prop_id},
        {"$set": {"calificacion_promedio": calif_promedio}}
    )
    contador_actualizadas += 1

print(f"--- ¡LISTO! ---")
print(f"Se actualizaron {contador_actualizadas} propiedades con su calificación promedio.")