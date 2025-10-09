from flask import Flask, render_template, request, redirect, url_for, session, flash
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
import hashlib

app = Flask(__name__)
app.secret_key = "clave"  


# Conexión a MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["AlojaT"]
usuarios = db["usuarios"]
propiedades = db["propiedades"] 

# Función para encriptar contraseña
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.route("/")
def inicio():
    if "usuario_id" in session:
        return redirect(url_for("ver_propiedades"))  # ya logueado → propiedades
    return redirect(url_for("login"))  # no logueado → login

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form["correo"]
        contraseña = hash_password(request.form["contraseña"])
        user = usuarios.find_one({"correo": correo, "contraseña": contraseña})

        if user:
            session["usuario_id"] = str(user["_id"])
            session["usuario_nombre"] = user["nombre"]
            flash("Inicio de sesión exitoso", "success")
            return redirect(url_for("ver_propiedades"))  # redirige a propiedades
        else:
            flash("Correo o contraseña incorrectos", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada correctamente", "info")
    return redirect(url_for("login"))

# ---------------- REGISTRO ----------------
@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        roles = request.form.getlist("rol")
        if not roles:
            flash("Debes seleccionar al menos un rol.", "danger")
            return redirect(url_for("registro"))

        es_anfitrion = "anfitrion" in roles
        clabe_bancaria = None

        if es_anfitrion:
            clabe_bancaria = request.form.get("clabe_bancaria", "").replace(" ", "")
            if not clabe_bancaria or len(clabe_bancaria) != 18 or not clabe_bancaria.isdigit():
                flash("Debes ingresar una CLABE válida de 18 dígitos.", "danger")
                return redirect(url_for("registro"))

        documentos = [d.strip() for d in request.form["documento_identidad"].split(",") if d.strip()]
        if len(documentos) < 2:
            flash("Debes ingresar al menos 2 documentos de identidad.", "danger")
            return redirect(url_for("registro"))

        data = {
            "nombre": request.form["nombre"],
            "apellido": request.form["apellido"],
            "correo": request.form["correo"],
            "contraseña": hash_password(request.form["contraseña"]),
            "fecha_nacimiento": datetime.strptime(request.form["fecha_nacimiento"], "%Y-%m-%d"),
            "direccion_postal": request.form["direccion_postal"],
            "documento_identidad": documentos,
            "rol": roles,
            "es_anfitrion": es_anfitrion,
            "clabe_bancaria": clabe_bancaria,
            "fecha_registro": datetime.utcnow()
        }

        if usuarios.find_one({"correo": data["correo"]}):
            flash("Ya existe un usuario con ese correo", "warning")
            return redirect(url_for("registro"))

        usuarios.insert_one(data)
        flash("Usuario registrado correctamente. Ahora puedes iniciar sesión.", "success")
        return redirect(url_for("login"))

    return render_template("registro.html")

# ---------------- PROPIEDADES ----------------
@app.route("/propiedades")
def ver_propiedades():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    data = propiedades.find()
    return render_template("propiedades.html", propiedades=data, usuario=session["usuario_nombre"])

# ---------------- CRUD USUARIOS (opcional) ----------------
@app.route("/nuevo", methods=["GET", "POST"])
def nuevo():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        roles = request.form.getlist("rol")
        if not roles:
            flash("Debes seleccionar al menos un rol.", "danger")
            return redirect(url_for("nuevo"))

        es_anfitrion = "anfitrion" in roles
        clabe_bancaria = None
        if es_anfitrion:
            clabe_bancaria = request.form.get("clabe_bancaria", "").replace(" ", "")
            if not clabe_bancaria or len(clabe_bancaria) != 18 or not clabe_bancaria.isdigit():
                flash("Debes ingresar una CLABE válida de 18 dígitos.", "danger")
                return redirect(url_for("nuevo"))

        documentos = [d.strip() for d in request.form["documento_identidad"].split(",") if d.strip()]
        if len(documentos) < 2:
            flash("Debes ingresar al menos 2 documentos de identidad.", "danger")
            return redirect(url_for("nuevo"))

        usuario = {
            "nombre": request.form["nombre"],
            "apellido": request.form["apellido"],
            "correo": request.form["correo"],
            "contraseña": hash_password(request.form["contraseña"]),
            "fecha_nacimiento": datetime.strptime(request.form["fecha_nacimiento"], "%Y-%m-%d"),
            "direccion_postal": request.form["direccion_postal"],
            "documento_identidad": documentos,
            "rol": roles,
            "es_anfitrion": es_anfitrion,
            "clabe_bancaria": clabe_bancaria,
            "fecha_registro": datetime.utcnow()
        }
        usuarios.insert_one(usuario)
        flash("Usuario agregado correctamente", "success")
        return redirect(url_for("ver_propiedades"))
    return render_template("nuevo.html")

# ---------------- EDITAR Y ELIMINAR USUARIO (opcional) ----------------
@app.route("/editar/<id>", methods=["GET", "POST"])
def editar(id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    usuario = usuarios.find_one({"_id": ObjectId(id)})

    if request.method == "POST":
        roles = request.form.getlist("rol")
        if not roles:
            flash("Debes seleccionar al menos un rol.", "danger")
            return redirect(url_for("editar", id=id))

        es_anfitrion = "anfitrion" in roles
        clabe_bancaria = None
        if es_anfitrion:
            clabe_bancaria = request.form.get("clabe_bancaria", "").replace(" ", "")
            if not clabe_bancaria or len(clabe_bancaria) != 18 or not clabe_bancaria.isdigit():
                flash("Debes ingresar una CLABE válida de 18 dígitos.", "danger")
                return redirect(url_for("editar", id=id))

        documentos = [d.strip() for d in request.form["documento_identidad"].split(",") if d.strip()]
        if len(documentos) < 2:
            flash("Debes ingresar al menos 2 documentos de identidad.", "danger")
            return redirect(url_for("editar", id=id))

        data = {
            "nombre": request.form["nombre"],
            "apellido": request.form["apellido"],
            "correo": request.form["correo"],
            "fecha_nacimiento": datetime.strptime(request.form["fecha_nacimiento"], "%Y-%m-%d"),
            "direccion_postal": request.form["direccion_postal"],
            "documento_identidad": documentos,
            "rol": roles,
            "es_anfitrion": es_anfitrion,
            "clabe_bancaria": clabe_bancaria
        }
        usuarios.update_one({"_id": ObjectId(id)}, {"$set": data})
        flash("Usuario actualizado correctamente", "success")
        return redirect(url_for("ver_propiedades"))

    return render_template("editar.html", usuario=usuario)

@app.route("/eliminar/<id>")
def eliminar(id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    usuarios.delete_one({"_id": ObjectId(id)})
    flash("Usuario eliminado", "info")
    return redirect(url_for("ver_propiedades"))

# ---------------- EJECUTAR APP ----------------
if __name__ == "__main__":
    app.run(debug=True)