from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
import io
from flask import send_file
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from functools import wraps
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hotel.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key'  # Required for session management

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# User Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)  # Hashed password

# Create tables
with app.app_context():
    db.create_all()

from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first!", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# **Login Route**
@app.route("/", methods=["GET", "POST"])
def login():
    # if "user_id" in session:  # If user is already logged in, redirect to dashboard
    #     return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session["user_id"] = user.id  # Store user session
            flash("Login successful!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password", "danger")

    return render_template("login.html")

# **Logout Route**
@app.route("/logout")
def logout():
    session.pop("user_id", None)  # Remove user session
    flash("Logged out successfully!", "info")
    return redirect(url_for("login"))

# **Registration Route**
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, password=hashed_password)
        
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

# =======================
#  EXISTING INDEX ROUTE
# =======================
@app.route('/index')
@login_required
def index():
    guests = Guest.query.all()
    return render_template("index.html", guests=guests)

# =======================
#  PROTECTED DASHBOARD
# =======================
@app.route('/dashboard')
@login_required
def dashboard():
    if "user_id" not in session:
        flash("Please log in first!", "warning")
        return redirect(url_for("login"))

    total_guests = Guest.query.count()
    total_reservations = Reservation.query.count()
    occupied_rooms = Room.query.filter_by(is_available=False).count()
    available_rooms = Room.query.filter_by(is_available=True).count()
    total_revenue = db.session.query(db.func.sum(Billing.amount)).scalar() or 0

    return render_template("dashboard.html", 
                           total_guests=total_guests, 
                           total_reservations=total_reservations, 
                           occupied_rooms=occupied_rooms, 
                           available_rooms=available_rooms, 
                           total_revenue=total_revenue)






# Database Models
class Guest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    email = db.Column(db.String(100), nullable=False)
class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(10), unique=True, nullable=False)
    room_type = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)  # Add this if missing
    is_available = db.Column(db.Boolean, default=True)


# Create tables
with app.app_context():
    db.create_all()





@app.route('/add_guest', methods=['POST'])
def add_guest():
    name = request.form['name']
    phone = request.form['phone']
    email = request.form['email']

    # Create a new Guest instance
    new_guest = Guest(name=name, phone=phone, email=email)
    db.session.add(new_guest)
    db.session.commit()

    return redirect(url_for('index'))  # Redirect back to the guest list

@app.route('/guests')
@login_required
def guests():
    all_guests = Guest.query.all()
    return render_template('guests.html', guests=all_guests)


@app.route('/rooms')
def rooms():
    room_type = request.args.get('room_type', '')
    if room_type:
        all_rooms = Room.query.filter_by(room_type=room_type).all()
    else:
        all_rooms = Room.query.all()
    
    return render_template('rooms.html', all_rooms=all_rooms)

@app.route('/add_room', methods=['POST'])
@login_required
def add_room():
    room_number = request.form['room_number']
    room_type = request.form['room_type']
    price = request.form.get('price', type=float)  # Ensure price is stored as a float
    is_available = True  # New rooms should be available by default

    new_room = Room(room_number=room_number, room_type=room_type, price=price, is_available=is_available)
    db.session.add(new_room)
    db.session.commit()

    flash("Room added successfully!", "success")
    return redirect(url_for('rooms'))



class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    guest_id = db.Column(db.Integer, db.ForeignKey('guest.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    check_in = db.Column(db.Date, nullable=False)
    check_out = db.Column(db.Date, nullable=False)
    payment_status = db.Column(db.String(20), default="Unpaid")  # Add this line
    guest = db.relationship('Guest', backref='reservations')
    room = db.relationship('Room', backref='reservations')


@app.route('/reservations')
@login_required
def reservations():
    selected_room_id = request.args.get('selected_room', type=int)
    guests = Guest.query.all()
    rooms = Room.query.filter_by(is_available=True).all()
    reservations = Reservation.query.all()

    return render_template("reservations.html", guests=guests, rooms=rooms, reservations=reservations, selected_room_id=selected_room_id)

@app.route('/add_reservation', methods=['GET', 'POST'])
def add_reservation():
    if request.method == 'GET':  # Pre-fill room selection if coming from rooms page
        room_id = request.args.get('room_id', type=int)
        guests = Guest.query.all()
        rooms = Room.query.filter_by(is_available=True).all()
        reservations = Reservation.query.all()  # Fetch existing reservations

        return render_template("reservations.html", guests=guests, rooms=rooms, reservations=reservations, selected_room_id=room_id)

    guest_id = int(request.form['guest_id'])
    room_id = int(request.form['room_id'])

    # Check if room is still available
    room = Room.query.get(room_id)
    if not room or not room.is_available:
        flash("This room is already booked. Please select another room.", "danger")
        return redirect('/rooms')

    check_in = datetime.strptime(request.form['check_in'], '%Y-%m-%d').date()
    check_out = datetime.strptime(request.form['check_out'], '%Y-%m-%d').date()

    guest = Guest.query.get(guest_id)
    if not guest:
        return "Guest not found", 404

    new_reservation = Reservation(guest_id=guest.id, room_id=room_id, check_in=check_in, check_out=check_out)
    db.session.add(new_reservation)

    # Mark room as occupied
    room.is_available = False  

    db.session.commit()

    return redirect('/reservations')




class Billing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey('reservation.id'), nullable=False)
    guest_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default="Pending")
    category = db.Column(db.String(50), nullable=False, default="Room Stay")  # New column


@app.route('/generate_bill/<int:reservation_id>')
@login_required
def generate_bill(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    guest = Guest.query.get(reservation.guest_id)
    if not guest:
        return "Guest not found", 404

    stay_days = (reservation.check_out - reservation.check_in).days
    room_price = reservation.room.price  # Fetch from Room model
    total_amount = stay_days * room_price

    # Check if a room stay bill already exists
    room_stay_bill = Billing.query.filter_by(reservation_id=reservation.id, category="Room Stay").first()

    if room_stay_bill:
        room_stay_bill.amount = total_amount
    else:
        new_bill = Billing(reservation_id=reservation.id, guest_name=guest.name, amount=total_amount, category="Room Stay")
        db.session.add(new_bill)

    db.session.commit()
    return redirect('/billing')









@app.route('/pay_bill/<int:bill_id>')
@login_required
def pay_bill(bill_id):
    bill = Billing.query.get_or_404(bill_id)
    bill.status = "Paid"
    db.session.commit()

    return redirect('/billing')

class RoomService(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reservation_id = db.Column(db.Integer, db.ForeignKey('reservation.id'), nullable=False)
    item = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)

    reservation = db.relationship('Reservation', backref='services')


    @app.route('/room_service')
    @login_required
    def room_service():
        reservations = Reservation.query.all()
        services = RoomService.query.all()
        return render_template("room_service.html", reservations=reservations, services=services)
@app.route('/add_service', methods=['POST'])
@login_required
def add_service():
    reservation_id = request.form['reservation_id']
    item = request.form['item']
    price = float(request.form['price'])

    # Add the new room service entry
    new_service = RoomService(reservation_id=reservation_id, item=item, price=price)
    db.session.add(new_service)

    # Create a separate bill for room service
    if new_service and new_service.reservation and new_service.reservation.guest:
        guest_name = new_service.reservation.guest.name
    else:
        print("Missing data: Service, Reservation, or Guest")
        guest_name = "Unknown"

    new_bill = Billing(
    reservation_id=reservation_id,
    guest_name=guest_name,
    amount=price,
    category="Room Service"
)

    db.session.add(new_bill)
    db.session.commit()  # Ensure changes are saved

    print("Room service bill added successfully!")



   
    return redirect('/room_service')


@app.route('/recommend_rooms')
def recommend_rooms():
    room_type = request.args.get('room_type', 'Single')  # Default to Single
    recommended_rooms = Room.query.filter_by(is_available=True, room_type=room_type).order_by(Room.price).limit(3).all()
    
    return render_template('recommended.html', recommended_rooms=recommended_rooms)


@app.route('/edit_reservation/<int:reservation_id>', methods=['GET', 'POST'])
@login_required
def edit_reservation(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    
    if request.method == 'POST':
        reservation.check_in = datetime.strptime(request.form['check_in'], '%Y-%m-%d').date()
        reservation.check_out = datetime.strptime(request.form['check_out'], '%Y-%m-%d').date()
        db.session.commit()
        return redirect(url_for('reservations'))
    
    return render_template('edit_reservation.html', reservation=reservation)

@app.route('/delete_reservation/<int:reservation_id>', methods=['POST'])
def delete_reservation(reservation_id):
    reservation = Reservation.query.get(reservation_id)
    if reservation:
        print(f"Deleting reservation ID: {reservation_id}")

        if reservation.room_id:
            room = Room.query.get(reservation.room_id)
            if room:
                print(f"Room found: {room.id}, Current Status: {room.is_available}")
                room.is_available = True  # Use is_available instead of status
                db.session.commit()
                print(f"Room {room.id} status updated to: {room.is_available}")

        db.session.delete(reservation)
        db.session.commit()
        flash("Reservation deleted successfully, room is now available!", "success")
    else:
        flash("Reservation not found!", "danger")

    return redirect(url_for('reservations'))





@app.route('/billing')
def billing():  
    bills = Billing.query.all()
    reservations = Reservation.query.all()  # Fetch all reservations

    print("Reservations:", reservations)  # Debugging output

    return render_template('billing.html', bills=bills, reservations=reservations)



from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import io
from flask import send_file, flash, redirect, url_for

@app.route('/generate_receipt/<int:reservation_id>')
def generate_receipt(reservation_id):
    reservation = Reservation.query.get(reservation_id)

    if not reservation:
        flash("Reservation not found!", "danger")
        return redirect(url_for('reservations'))

    guest_name = reservation.guest.name if reservation.guest else "Unknown"
    room = Room.query.get(reservation.room_id)

    # Fetch Room Service Data from Relationship
    total_service_cost = sum(service.price for service in reservation.services)

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    title = Paragraph("<b>HOTEL RECEIPT</b>", styles["Title"])
    elements.append(title)
    elements.append(Spacer(1, 12))

    # Reservation Details
    receipt_data = [
        ["Guest Name:", guest_name],
        ["Room Type:", room.room_type],
        ["Room Number:", room.room_number],
        ["Room Price:", f"₹{room.price}"],
        ["Check-in Date:", reservation.check_in.strftime("%d-%m-%Y")],
        ["Check-out Date:", reservation.check_out.strftime("%d-%m-%Y")]
    ]

    table = Table(receipt_data, colWidths=[150, 300])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 12))

    # Room Service Section (If Any)
    if reservation.services:
        elements.append(Paragraph("<b>Room Service Details</b>", styles["Heading2"]))
        service_data = [["Item", "Price (₹)"]]

        for service in reservation.services:
            service_data.append([service.item, f"₹{service.price}"])

        service_table = Table(service_data, colWidths=[300, 150])
        service_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]))

        elements.append(service_table)
        elements.append(Spacer(1, 12))

    # Grand Total Calculation
    grand_total = room.price + total_service_cost
    total_data = [["Total Room Service Cost:", f"₹{total_service_cost}"],
                  ["Grand Total:", f"₹{grand_total}"]]

    total_table = Table(total_data, colWidths=[300, 150])
    total_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))

    elements.append(total_table)
    doc.build(elements)

    pdf_buffer.seek(0)
    return send_file(pdf_buffer, as_attachment=True, download_name=f"receipt_{reservation_id}.pdf", mimetype='application/pdf')




@app.route('/delete_room/<int:room_id>', methods=['POST'])
def delete_room(room_id):
    room = Room.query.get(room_id)
    if room:
        db.session.delete(room)
        db.session.commit()
        flash(f"Room {room.room_number} deleted successfully!", "success")
    else:
        flash("Room not found!", "danger")

    return redirect(url_for('rooms'))  # Adjust if your main rooms page route is different

if __name__ == "__main__":
    app.run(debug=True, port=5000)  # Running on port 8000