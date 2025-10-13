from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["AlojaT"]
#Código para obtener los atributos de las colecciones de la base de datos
for name in db.list_collection_names():
    sample = db[name].find_one()
    print(f"\nCREATE COLLECTION {name} (")
    for key, value in sample.items():
        print(f"  {key} {type(value).__name__.upper()},")
    print(");")
