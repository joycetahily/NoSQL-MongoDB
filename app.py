import io
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
            # Guardamos la información del usuario en la sesión
            session["usuario_id"] = str(user["_id"])
            session["usuario_nombre"] = user["nombre"]
            session["usuario_rol"] = user.get("rol", [])  # <-- guardamos la lista completa de roles

            flash("Inicio de sesión exitoso", "success")
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


# ---------------- VER PROPIEDADES ----------------
@app.route("/propiedades")
def ver_propiedades():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    data = list(propiedades.find())
    return render_template("propiedades.html", propiedades=data, usuario=session["usuario_nombre"])

# ---------------- CREAR NUEVA PROPIEDAD ----------------
@app.route("/crear_propiedad", methods=["GET", "POST"])
def crear_propiedad():
    if "usuario_id" not in session or "anfitrion" not in session.get("usuario_rol", []):
        flash("No tienes permisos para crear propiedades.", "danger")
        return redirect(url_for("ver_propiedades"))

    if request.method == "POST":
        fotos = [f.strip() for f in request.form.get("fotos", "").split(",") if f.strip()]
        servicios_raw = request.form.get("servicios", "")
        servicios = [s.strip() for s in servicios_raw.split(",") if s.strip()]


        nueva_propiedad = {
            "anfitrion_id": ObjectId(session["usuario_id"]),
            "titulo": request.form["titulo"],
            "fotos": fotos,
            "precio_por_dia": Decimal128(Decimal(str(request.form["precio_por_dia"]))),
            "ubicacion": {
             "ciudad": request.form["ciudad"],
               "colonia": request.form["colonia"],
              "calle_numero": request.form["calle_numero"]
            },
            "tipo": request.form["tipo"],
            "descripcion": request.form.get("descripcion", ""),
            "servicios": servicios, 
            "reglas": request.form.get("reglas", "")
            }

        propiedades.insert_one(nueva_propiedad)
        flash("Propiedad creada correctamente.", "success")
        return redirect(url_for("ver_propiedades"))

    return render_template("crear_propiedad.html")

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

    # Traer reseñas y agregar nombre del usuario
    resenas_cursor = reseñas.find({"propiedad_id": ObjectId(id)})
    resenas = []
    for r in resenas_cursor:
        usuario_resena = usuarios.find_one({"_id": r["huesped_id"]})
        r["usuario"] = usuario_resena["nombre"] if usuario_resena else "Desconocido"
        r["fecha"] = r["fecha_creacion"].strftime("%d/%m/%Y")
        resenas.append(r)

    return render_template("propiedad.html", propiedad=propiedad, resenas=resenas)


# ---------------- AGREGAR RESEÑA ----------------
@app.route("/agregar_resena/<id>", methods=["POST"])
def agregar_resena(id):
    if "usuario_id" not in session:
        flash("Debes iniciar sesión para dejar una reseña.", "warning")
        return redirect(url_for("login"))

    comentario = request.form["comentario"]
    calificacion = int(request.form["calificacion"])
    huesped_id = ObjectId(session["usuario_id"])

    nueva_resena = {
        "reserva_id": None,
        "propiedad_id": ObjectId(id),
        "huesped_id": huesped_id,
        "calificacion": calificacion,
        "comentario": comentario,
        "fecha_creacion": datetime.utcnow()
    }

    reseñas.insert_one(nueva_resena)
    flash("Reseña agregada correctamente.", "success")
    return redirect(url_for("ver_propiedad", id=id))

@app.route("/reservar/<id>", methods=["POST"])
def reservar(id):
    propiedad = db.propiedades.find_one({"_id": ObjectId(id)})
    if not propiedad:
        return "Propiedad no encontrada", 404

    # Datos del formulario
    fecha_inicio = datetime.strptime(request.form["fecha_inicio"], "%Y-%m-%d")
    fecha_fin = datetime.strptime(request.form["fecha_fin"], "%Y-%m-%d")
    numero_huespedes = int(request.form["numero_huespedes"])
    numero_noches = (fecha_fin - fecha_inicio).days

    # Conversión a Decimal128
    precio_por_noche = Decimal128(Decimal(str(propiedad.get("precio_por_dia", 0))))
    subtotal = Decimal128(Decimal(str(precio_por_noche.to_decimal() * numero_noches)))
    comision_servicio = Decimal128(Decimal(str(subtotal.to_decimal() * Decimal("0.10"))))  # 10% de ejemplo
    total = Decimal128(Decimal(str(subtotal.to_decimal() + comision_servicio.to_decimal())))

    # Crear documento de reserva
    reserva = {
        "propiedad_id": propiedad["_id"],
        "huesped_id": ObjectId(session["usuario_id"]),
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "numero_huespedes": numero_huespedes,
        "estado": "completada",
        "fecha_reserva": datetime.now(),
        "desglose_precio": {
            "precio_por_noche": precio_por_noche,
            "numero_noches": numero_noches,
            "subtotal": subtotal,
            "comision_servicio": comision_servicio,
            "total": total
        }
    }

    # Insertar reserva en MongoDB
    reserva_id = db.reservas.insert_one(reserva).inserted_id

    # Crear documento de pago
    pago = {
        "reserva_id": reserva_id,
        "huesped_id": ObjectId(session["usuario_id"]),
        "monto": total,
        "estado": "pago_confirmado",
        "fecha_creacion": datetime.now(),
        "fecha_confirmacion": datetime.now()
    }
    pago_id = db.pagos.insert_one(pago).inserted_id

    # Generar PDF del ticket
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

    # Obtener clabe bancaria del anfitrión si existe
    anfitrion = db.usuarios.find_one({"_id": propiedad["anfitrion_id"]})
    clabe = anfitrion.get("clabe_bancaria", "No disponible")
    pdf.cell(0, 8, f"CLABE bancaria del anfitrión: {clabe}", ln=True)

    # Enviar PDF al navegador
    pdf_output = io.BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)
    return send_file(pdf_output, download_name="ticket_reserva.pdf", as_attachment=True)

# ---------------- EJECUTAR APP ----------------
if __name__ == "__main__":
    app.run(debug=True)

