import io
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from datetime import timedelta
import hashlib
from fpdf import FPDF
from bson.decimal128 import Decimal128
from flask import send_file
from bson import ObjectId
from decimal import Decimal
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = "clave_secreta"

# --- Conexión a MongoDB ---
client = MongoClient("mongodb://localhost:27017/")
db = client["AlojaT"]
usuarios = db["usuarios"]
propiedades = db["propiedades"]
reseñas = db["reseñas"]
reservas = db["reservas"]    
pagos = db["pagos"]    

# --- Función para encriptar contraseña ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Carpetas de subida
UPLOAD_FOLDER = 'static/documentos'
UPLOAD_FOLDER_PROP = 'static/imagenes_propiedades'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['UPLOAD_FOLDER_PROP'] = UPLOAD_FOLDER_PROP

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------- PÁGINA PRINCIPAL ----------------
@app.route("/")
def inicio():
    if "usuario_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

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
            session["usuario_rol"] = user.get("rol", []) 
            return redirect(url_for("dashboard"))
        else:
            flash("Correo o contraseña incorrectos", "danger")
    return render_template("login.html")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", rol=session.get("usuario_rol"))

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

        archivos = request.files.getlist("documento_identidad")
        if len(archivos) < 2:
            flash("Debes subir al menos 2 documentos de identidad.", "danger")
            return redirect(url_for("registro"))

        documentos_guardados = []
        for archivo in archivos:
            if archivo and allowed_file(archivo.filename):
                filename = secure_filename(archivo.filename)
                ruta = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                archivo.save(ruta)
                documentos_guardados.append(filename)
            else:
                flash("Solo se permiten archivos: png, jpg, jpeg, pdf.", "danger")
                return redirect(url_for("registro"))

        data = {
            "nombre": request.form["nombre"],
            "apellido": request.form["apellido"],
            "correo": request.form["correo"],
            "contraseña": hash_password(request.form["contraseña"]),
            "fecha_nacimiento": datetime.strptime(request.form["fecha_nacimiento"], "%Y-%m-%d"),
            "direccion_postal": request.form.get("direccion_postal"),
            "documento_identidad": documentos_guardados,
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


# ---------------- VER PROPIEDADES (CORREGIDO Y FUSIONADO) ----------------
@app.route("/propiedades", methods=["GET"])
def ver_propiedades():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    
    # --- (LÓGICA DE FILTROS DEL ARCHIVO "NUEVO") ---
    tipo = request.args.get("tipo", "")
    min_precio = request.args.get("min_precio", 0, type=float)
    max_precio = request.args.get("max_precio", 999999, type=float)
    servicios = request.args.getlist("servicios")
    calificacion_minima = request.args.get("calificacion_minima", 0, type=float) 

    # --- Construir el filtro de MongoDB ---
    filtro = {}
    filtro["precio_por_dia"] = {"$gte": min_precio, "$lte": max_precio}

    if tipo:
        filtro["tipo"] = tipo.lower()
    if servicios:
        filtro["servicios"] = {"$all": servicios}
    if calificacion_minima > 0: 
        filtro["calificacion_promedio"] = {"$gte": calificacion_minima} 

    # --- (LÓGICA DE PROPIEDADES DEL ARCHIVO "ANTERIOR", PERO APLICANDO EL FILTRO) ---
    usuario_id = session["usuario_id"]
    rol = session.get("usuario_rol", [])

    # Buscamos en la DB aplicando el FILTRO
    data = list(propiedades.find(filtro)) 

    # --- (LÓGICA DE "prop.propia" DEL ARCHIVO "ANTERIOR") ---
    # Marcar cuáles propiedades son del anfitrión logueado
    for prop in data:
        prop["propia"] = (str(prop.get("anfitrion_id")) == usuario_id)
        # (Estas líneas son buenas prácticas de tu archivo "nuevo")
        prop["_id"] = str(prop["_id"])
        prop["fotos"] = prop.get("fotos", [])
        prop["ubicacion"] = prop.get("ubicacion", {})
         
    return render_template(
        "propiedades.html", 
        propiedades=data, 
        rol=rol, 
        session=session, # Pasamos la sesión completa
        # (Pasamos las variables del filtro para que se queden seleccionadas)
        tipo=tipo,
        min_precio=int(min_precio),
        max_precio=int(max_precio),
        servicios=servicios,
        calificacion_minima=calificacion_minima
    )


@app.route("/logout")
def logout():
    session.clear()  # Elimina toda la información de sesión
    return redirect(url_for("login"))  # Redirige al login

# ---------------- CREAR NUEVA PROPIEDAD ----------------
@app.route("/crear_propiedad", methods=["GET", "POST"])
def crear_propiedad():
    if request.method == "POST":
        titulo = request.form["titulo"]
        precio_por_dia = Decimal128(str(request.form["precio_por_dia"]))
        tipo = request.form["tipo"]
        descripcion = request.form["descripcion"]
        reglas = request.form["reglas"]
        servicios = request.form.getlist("servicios")
        ciudad = request.form["ciudad"]
        colonia = request.form["colonia"]
        calle_numero = request.form["calle_numero"]

        if len(titulo.strip()) < 10:
            flash("El título debe tener al menos 10 caracteres.", "error")
            return redirect(url_for("crear_propiedad"))
        if len(descripcion.strip()) < 50:
            flash("La descripción debe tener al menos 50 caracteres.", "error")
            return redirect(url_for("crear_propiedad"))
        if not servicios:
            flash("Debes seleccionar al menos un servicio.", "error")
            return redirect(url_for("crear_propiedad"))

        archivos = request.files.getlist('fotos')
        nombres_guardados = []

        if not os.path.exists(app.config['UPLOAD_FOLDER_PROP']):
            os.makedirs(app.config['UPLOAD_FOLDER_PROP'])

        for archivo in archivos:
            if archivo and allowed_file(archivo.filename):
                filename = secure_filename(archivo.filename)
                archivo.save(os.path.join(app.config['UPLOAD_FOLDER_PROP'], filename))
                nombres_guardados.append(filename)

        if len(nombres_guardados) == 0:
            flash("Debes subir al menos una imagen de la propiedad.", "error")
            return redirect(url_for("crear_propiedad"))

        anfitrion_id = ObjectId(session.get("usuario_id"))

        propiedad = {
            "titulo": titulo,
            "precio_por_dia": precio_por_dia,
            "tipo": tipo,
            "descripcion": descripcion,
            "reglas": reglas,
            "servicios": servicios,
            "ubicacion": {
                "ciudad": ciudad,
                "colonia": colonia,
                "calle_numero": calle_numero
            },
            "fotos": nombres_guardados,
            "anfitrion_id": anfitrion_id
        }

        propiedades.insert_one(propiedad)
        return redirect(url_for("ver_propiedades"))

    return render_template("crear_propiedad.html")
    
    
# ---------------- EDITAR PROPIEDAD ----------------
@app.route("/editar_propiedad/<id>", methods=["GET", "POST"])
def editar_propiedad(id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    propiedad = propiedades.find_one({"_id": ObjectId(id)})

    if not propiedad:
        flash("Propiedad no encontrada", "danger")
        return redirect(url_for("ver_propiedades"))

    if propiedad["anfitrion_id"] != ObjectId(session["usuario_id"]):
        flash("No tienes permiso para editar esta propiedad", "danger")
        return redirect(url_for("ver_propiedades"))

    if request.method == "POST":
        titulo = request.form["titulo"]
        precio_por_dia = Decimal128(str(request.form["precio_por_dia"]))
        tipo = request.form["tipo"]
        descripcion = request.form["descripcion"]
        reglas = request.form["reglas"]
        servicios = request.form.getlist("servicios")
        ciudad = request.form["ciudad"]
        colonia = request.form["colonia"]
        calle_numero = request.form["calle_numero"]

        propiedades.update_one(
            {"_id": ObjectId(id)},
            {"$set": {
                "titulo": titulo,
                "precio_por_dia": precio_por_dia,
                "tipo": tipo,
                "descripcion": descripcion,
                "reglas": reglas,
                "servicios": servicios,
                "ubicacion": {
                    "ciudad": ciudad,
                    "colonia": colonia,
                    "calle_numero": calle_numero
                }
            }}
        )
        flash("Propiedad actualizada correctamente", "success")
        return redirect(url_for("ver_propiedades"))

    return render_template("editar_propiedad.html", propiedad=propiedad)


# ---------------- ELIMINAR PROPIEDAD ----------------
@app.route("/eliminar_propiedad/<id>", methods=["POST"])
def eliminar_propiedad(id):
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    propiedad = propiedades.find_one({"_id": ObjectId(id)})

    if not propiedad:
        flash("Propiedad no encontrada", "danger")
        return redirect(url_for("ver_propiedades"))

    if propiedad["anfitrion_id"] != ObjectId(session["usuario_id"]):
        flash("No tienes permiso para eliminar esta propiedad", "danger")
        return redirect(url_for("ver_propiedades"))

    propiedades.delete_one({"_id": ObjectId(id)})
    flash("Propiedad eliminada correctamente", "success")
    return redirect(url_for("ver_propiedades"))


# ---------------- VER PROPIEDAD Y RESEÑAS ----------------
@app.route("/propiedades/<id>")
def ver_propiedad(id):
    try:
        propiedad = propiedades.find_one({"_id": ObjectId(id)})
    except:
        flash("ID de propiedad inválido", "danger")
        return redirect(url_for("ver_propiedades"))

    if not propiedad:
        flash("Propiedad no encontrada", "danger")
        return redirect(url_for("ver_propiedades"))

    resenas_cursor = reseñas.find({"propiedad_id": ObjectId(id)})
    resenas = []
    for r in resenas_cursor:
        usuario_resena = usuarios.find_one({"_id": r["huesped_id"]})
        r["usuario"] = usuario_resena["nombre"] if usuario_resena else "Desconocido"
        r["fecha"] = r["fecha_creacion"].strftime("%d/%m/%Y")
        resenas.append(r)

    reservas_usuario = []
    if "usuario_id" in session:
        usuario_id = ObjectId(session["usuario_id"])
        reservas_cursor = reservas.find({
            "huesped_id": usuario_id,
            "propiedad_id": ObjectId(id),
        })
        reservas_usuario = [r["_id"] for r in reservas_cursor]

    reservas_completadas = reservas.find({"propiedad_id": ObjectId(id)})
    fechas_ocupadas = []
    for r in reservas_completadas:
        fecha = r["fecha_inicio"]
        while fecha <= r["fecha_fin"]:
            fechas_ocupadas.append(fecha.strftime("%Y-%m-%d"))
            fecha += timedelta(days=1)

    return render_template(
        "propiedad.html",
        propiedad=propiedad,
        resenas=resenas,
        reservas_usuario=reservas_usuario,
        fechas_ocupadas=fechas_ocupadas
    )

# ---------------- AGREGAR RESEÑA (CON LÓGICA DE CALIFICACIÓN) ----------------
@app.route("/agregar_resena/<id>", methods=["POST"])
def agregar_resena(id):
    if "usuario_id" not in session:
        flash("Debes iniciar sesión para dejar una reseña.", "warning")
        return redirect(url_for("login"))

    usuario_id = ObjectId(session["usuario_id"])

    reserva = reservas.find_one({
        "huesped_id": usuario_id,
        "propiedad_id": ObjectId(id),
    })

    if not reserva:
        flash("Debes completar una reserva para poder dejar una reseña.", "warning")
        return redirect(url_for("ver_propiedad", id=id))

    comentario = request.form["comentario"]
    calificacion = int(request.form["calificacion"])

    nueva_resena = {
        "reserva_id": reserva["_id"],
        "propiedad_id": ObjectId(id),
        "huesped_id": usuario_id,
        "calificacion": calificacion,
        "comentario": comentario,
        "fecha_creacion": datetime.utcnow()
    }

    reseñas.insert_one(nueva_resena)
    flash("Reseña agregada correctamente.", "success")
    
    # --- (LÓGICA DE CÁLCULO DE PROMEDIO DEL ARCHIVO "NUEVO") ---
    try:
        pipeline = [
            {"$match": {"propiedad_id": ObjectId(id)}},
            {"$group": {
                "_id": "$propiedad_id",
                "avg_rating": {"$avg": "$calificacion"}
            }}
        ]
        resultado_avg = list(reseñas.aggregate(pipeline))
        
        if resultado_avg:
            calif_promedio = round(resultado_avg[0]['avg_rating'], 1) 
            propiedades.update_one(
                {"_id": ObjectId(id)},
                {"$set": {"calificacion_promedio": calif_promedio}}
            )
    except Exception as e:
        print(f"Error al actualizar calificación promedio: {e}")
    
    return redirect(url_for("ver_propiedad", id=id))


@app.route("/reservar/<id>", methods=["POST"])
def reservar(id):
    propiedad = db.propiedades.find_one({"_id": ObjectId(id)})
    if not propiedad:
        flash("Propiedad no encontrada.", "danger")
        return redirect(url_for("ver_propiedades"))

    fecha_inicio = datetime.strptime(request.form["fecha_inicio"], "%Y-%m-%d")
    fecha_fin = datetime.strptime(request.form["fecha_fin"], "%Y-%m-%d")
    numero_huespedes = int(request.form["numero_huespedes"])
    numero_noches = (fecha_fin - fecha_inicio).days

    conflicto = reservas.find_one({
        "propiedad_id": propiedad["_id"],
        "fecha_inicio": {"$lt": fecha_fin},
        "fecha_fin": {"$gt": fecha_inicio}
    })

    if conflicto:
        flash("Lo sentimos, la propiedad ya está reservada para esas fechas.", "danger")
        return redirect(url_for("ver_propiedad", id=id))

    precio_por_noche = Decimal128(Decimal(str(propiedad.get("precio_por_dia", 0))))
    subtotal = Decimal128(Decimal(str(precio_por_noche.to_decimal() * numero_noches)))
    comision_servicio = Decimal128(Decimal(str(subtotal.to_decimal() * Decimal("0.10"))))
    total = Decimal128(Decimal(str(subtotal.to_decimal() + comision_servicio.to_decimal())))

    reserva = {
        "propiedad_id": propiedad["_id"],
        "huesped_id": ObjectId(session["usuario_id"]),
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "numero_huespedes": numero_huespedes,
        "fecha_reserva": datetime.now(),
        "desglose_precio": {
            "precio_por_noche": precio_por_noche,
            "numero_noches": numero_noches,
            "subtotal": subtotal,
            "comision_servicio": comision_servicio,
            "total": total
        }
    }

    reserva_id = db.reservas.insert_one(reserva).inserted_id

    pago = {
        "reserva_id": reserva_id,
        "huesped_id": ObjectId(session["usuario_id"]),
        "monto": total,
        "fecha_creacion": datetime.now(),
    }
    db.pagos.insert_one(pago)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Ticket de Reserva", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 8, f"Reserva ID: {reserva_id}", ln=True)
    pdf.cell(0, 8, f"Propiedad: {propiedad['titulo']}", ln=True)
    pdf.cell(0, 8, f"Huésped: {session['usuario_nombre']}", ln=True)
    pdf.cell(0, 8, f"Fecha inicio: {fecha_inicio.strftime('%Y-%m-%d')}", ln=True)
    pdf.cell(0, 8, f"Fecha fin: {fecha_fin.strftime('%Y-%m-%d')}", ln=True)
    pdf.cell(0, 8, f"No. huéspedes: {numero_huespedes}", ln=True)
    pdf.ln(5)
    pdf.cell(0, 8, "Desglose de precio:", ln=True)
    pdf.cell(0, 8, f"  Precio por noche: ${precio_por_noche.to_decimal()}", ln=True)
    pdf.cell(0, 8, f"  Número de noches: {numero_noches}", ln=True)
    pdf.cell(0, 8, f"  Subtotal: ${subtotal.to_decimal()}", ln=True)
    pdf.cell(0, 8, f"  Comisión servicio: ${comision_servicio.to_decimal()}", ln=True)
    pdf.cell(0, 8, f"  Total: ${total.to_decimal()}", ln=True)
    pdf.ln(5)

    anfitrion = db.usuarios.find_one({"_id": propiedad["anfitrion_id"]})
    clabe = anfitrion.get("clabe_bancaria", "No disponible")
    pdf.cell(0, 8, f"CLABE bancaria del anfitrión: {clabe}", ln=True)

    pdf_output = io.BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)
    return send_file(pdf_output, download_name="ticket_reserva.pdf", as_attachment=True)

# ---------------- EJECUTAR APP ----------------
if __name__ == "__main__":
    app.run(debug=True)