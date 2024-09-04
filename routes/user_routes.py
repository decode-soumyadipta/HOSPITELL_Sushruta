from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import Hospital, Booking, Rating, Bed, Ward, db, Department, Doctor, OPDAppointment
from sqlalchemy.orm import aliased
from geopy.distance import great_circle
import random
import messagebird
from flask_mail import Mail, Message  # Import Message here
import os
from datetime import datetime, timedelta
# Initialize Flask Blueprint
user_bp = Blueprint('user_bp', __name__)
# Initialize Flask-Mail
mail = Mail()
# Your MessageBird API key
MESSAGEBIRD_API_KEY = '8XOUzqZZ0uxGo4GSKYkTMSFQCSvxQW0JoqtB'

# Initialize the MessageBird client
client = messagebird.Client(MESSAGEBIRD_API_KEY)

@user_bp.route('/dashboard')
@login_required
def dashboard():
    
    current_bookings = Booking.query.filter_by(user_id=current_user.id, status='Confirmed').all()
    return render_template('user_dashboard/index.html', current_bookings=current_bookings)

@user_bp.route('/book_bed', methods=['POST'])
@login_required
def book_bed():
    if Booking.query.filter_by(user_id=current_user.id, status='Confirmed').count() > 0:
        return jsonify({'success': False, 'message': 'You already have a confirmed booking. Please cancel it before making a new booking.'}), 400

    data = request.json
    hospital_id = data.get('hospital_id')
    hospital = Hospital.query.get(hospital_id)
    
    if not hospital:
        return jsonify({'success': False, 'message': 'Hospital not found.'}), 404

    if hospital.vacant_general_beds <= 0:
        return jsonify({'success': False, 'message': 'No General beds available.'}), 400

    if not current_user.location or not current_user.address:
        return jsonify({'success': False, 'message': 'User location or address not set. Please update your location.'}), 400

    try:
        user_lat, user_lng = map(float, current_user.location.split(','))
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid user location format.'}), 400

    distance = great_circle((user_lat, user_lng), (hospital.latitude, hospital.longitude)).kilometers
    admission_code = str(random.randint(1000, 9999))
    
    booking = Booking(
        user_id=current_user.id,
        hospital_id=hospital_id,
        bed_type='General',
        distance=distance,
        status='Confirmed',
        admission_code=admission_code
    )
    db.session.add(booking)
    db.session.commit()

    msg = Message('Booking Confirmation',
                  sender=os.environ.get('SENDER_EMAIL'),
                  recipients=[current_user.email])
    msg.body = f"""
    Dear {current_user.name},

    Your booking for a General bed at {hospital.name} has been confirmed. Your admission code is {admission_code}.
    Hospital Address: {hospital.address}
    Distance from you: {distance:.2f} km
    Your Location: {current_user.address}

    Please show this code at the hospital on arrival.

    Best regards,
    Hospital Management System
    """
    mail.send(msg)

    return jsonify({'success': True, 'message': 'Bed booked successfully.'}), 200







@user_bp.route('/rate_service', methods=['POST'])
@login_required
def rate_service():
    rating = Rating(user_id=current_user.id, hospital_id=request.form.get('hospital_id'), driver_id=request.form.get('driver_id'), rating=request.form.get('rating'), feedback=request.form.get('feedback'))
    db.session.add(rating)
    db.session.commit()
    flash("Thank you for your feedback!", "success")
    return redirect(url_for('user_bp.dashboard'))

@user_bp.route('/nearby_hospitals', methods=['POST'])
@login_required
def nearby_hospitals():
    user_lat = request.json.get('latitude')
    user_lng = request.json.get('longitude')
    bed_type = request.json.get('bed_type')

    if not user_lat or not user_lng:
        return jsonify({'error': 'Missing latitude or longitude'}), 400

    hospitals = Hospital.query.all()
    nearby_hospitals = []
    for hospital in hospitals:
        hospital_location = (hospital.latitude, hospital.longitude)
        user_location = (float(user_lat), float(user_lng))
        distance = great_circle(user_location, hospital_location).kilometers

        if distance <= 5:
            # Sum all ready beds across all wards for this hospital
            icu_beds_ready = Bed.query.join(Ward).filter(
                Bed.bed_type == 'ICU',
                Bed.status == 'ready',
                Ward.hospital_id == hospital.id
            ).count()

            opd_beds_ready = Bed.query.join(Ward).filter(
                Bed.bed_type == 'OPD',
                Bed.status == 'ready',
                Ward.hospital_id == hospital.id
            ).count()

            general_beds_ready = Bed.query.join(Ward).filter(
                Bed.bed_type == 'General',
                Bed.status == 'ready',
                Ward.hospital_id == hospital.id
            ).count()

            nearby_hospitals.append({
                'id': hospital.id,
                'name': hospital.name,
                'address': hospital.address,
                'distance': round(distance, 2),
                'vacant_icu_beds': icu_beds_ready,
                'vacant_opd_beds': opd_beds_ready,
                'vacant_general_beds': general_beds_ready,
                'contact_info': hospital.contact_info,
                'latitude': hospital.latitude,
                'longitude': hospital.longitude,
            })

    return jsonify(nearby_hospitals), 200


@user_bp.route('/save_phone_number', methods=['POST'])
@login_required
def save_phone_number():
    data = request.json
    phone = data.get('phone')

    if phone:
        current_user.phone = phone
        db.session.commit()
        return jsonify({'success': True}), 200
    else:
        return jsonify({'success': False, 'message': 'Phone number is required.'}), 400

def is_whatsapp_number(phone_number):
    try:
        lookup = client.lookup(phone_number, {'type': 'whatsapp'})
        return lookup and lookup.whatsapp
    except messagebird.client.ErrorException as e:
        print(f"Error checking WhatsApp number: {e}")
        return False

def send_whatsapp_message(phone_number, message):
    try:
        msg = client.message_create(
            originator='918240575718',
            recipients=[phone_number],
            body=message,
            messaging_type='whatsapp'
        )
        print(f"WhatsApp message sent successfully: {msg.id}")
        return msg.id
    except messagebird.client.ErrorException as e:
        print(f"Failed to send WhatsApp message: {e}")
        return None


@user_bp.route('/update_whatsapp_number', methods=['POST'])
@login_required
def update_whatsapp_number():
    new_whatsapp_number = request.form.get('whatsapp_number')
    if not new_whatsapp_number:
        return jsonify({'success': False, 'message': 'Please enter a valid WhatsApp number.'}), 400

    if not is_whatsapp_number(new_whatsapp_number):
        return jsonify({'success': False, 'message': 'The entered number is not registered with WhatsApp.'}), 400

    current_user.phone = new_whatsapp_number
    db.session.commit()
    return jsonify({'success': True, 'message': 'WhatsApp number updated successfully.'}), 200


@user_bp.route('/booking_history')
@login_required
def booking_history():
    past_bookings = Booking.query.filter(
        Booking.user_id == current_user.id,
        Booking.created_at < datetime.utcnow() - timedelta(hours=24)
    ).all()
    return render_template('user_dashboard/booking_history.html', bookings=past_bookings)

@user_bp.route('/save_address', methods=['POST'])
@login_required
def save_address():
    data = request.json
    location = data.get('location')
    address = data.get('address')

    if location and address:
        current_user.location = location
        current_user.address = address
        db.session.commit()
        return jsonify({'success': True}), 200
    else:
        return jsonify({'success': False, 'message': 'Invalid data.'}), 400

@user_bp.route('/cancel_booking/<int:booking_id>', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    booking = Booking.query.get(booking_id)
    if not booking or booking.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Booking not found or access denied.'}), 404
    
    booking.status = 'Cancelled'
    db.session.commit()
    
    return jsonify({'success': True}), 200


@user_bp.route('/book_opd', methods=['GET', 'POST'])
@login_required
def book_opd():
    if request.method == 'POST':
        appointment_date = request.form.get('appointment_date')
        doctor_id = request.form.get('doctor_id')
        time_slot = request.form.get('time_slot')
        hospital_id = request.form.get('hospital_id')  # Capture the hospital_id from the form
        appointment_code = str(random.randint(1000, 9999))

        # Ensure the current user hasn't already booked this slot
        existing_appointment = OPDAppointment.query.filter_by(
            user_id=current_user.id,
            doctor_id=doctor_id,
            appointment_date=appointment_date,
            time_slot=time_slot
        ).first()

        if existing_appointment:
            flash('You have already booked this time slot.', 'warning')
            return redirect(url_for('user_bp.view_appointments'))

        # Update user details if provided
        current_user.phone = request.form.get('phone') or current_user.phone
        current_user.age = request.form.get('age') or current_user.age
        current_user.address = request.form.get('address') or current_user.address

        # Create the OPDAppointment with the hospital_id
        appointment = OPDAppointment(
            user_id=current_user.id,
            doctor_id=doctor_id,
            hospital_id=hospital_id,  # Ensure hospital_id is saved
            appointment_date=appointment_date,
            time_slot=time_slot,
            appointment_code=appointment_code
        )
        db.session.add(appointment)
        db.session.commit()

        # Send confirmation email
        doctor = Doctor.query.get(doctor_id)
        hospital = Hospital.query.get(hospital_id)
        msg = Message('Your OPD Appointment Details', recipients=[current_user.email])
        msg.body = f"""
        Dear {current_user.name},

        Your appointment is confirmed with Dr. {doctor.name} at {hospital.name} on {appointment_date} at {time_slot}.
        Appointment Code: {appointment_code}

        Thank you for choosing our hospital.
        """
        mail.send(msg)

        flash('Appointment booked successfully', 'success')
        return redirect(url_for('user_bp.view_appointments'))

    hospitals = Hospital.query.all()
    return render_template('user_dashboard/book_opd.html', hospitals=hospitals)



@user_bp.route('/view_appointments', methods=['GET'])
@login_required
def view_appointments():
    today = datetime.today().date()
    end_date = today + timedelta(days=10)
    appointments = OPDAppointment.query.filter(
        OPDAppointment.user_id == current_user.id,
        OPDAppointment.appointment_date.between(today, end_date)
    ).all()
    return render_template('user_dashboard/view_appointments.html', appointments=appointments)



@user_bp.route('/get_doctors/<int:department_id>', methods=['GET'])
def get_doctors(department_id):
    appointment_date = request.args.get('date')
    
    if not appointment_date:
        return jsonify({'doctors': []})

    date_obj = datetime.strptime(appointment_date, '%Y-%m-%d')
    weekday_name = date_obj.strftime('%A')

    doctors = Doctor.query.filter_by(department_id=department_id).all()
    available_doctors = []

    for doctor in doctors:
        availability_days = [day.strip().capitalize() for day in doctor.availability_days.split(',')]
        if weekday_name in availability_days:
            available_doctors.append({
                'id': doctor.id,
                'name': doctor.name
            })

    return jsonify({'doctors': available_doctors})

@user_bp.route('/get_time_slots/<int:doctor_id>/<string:appointment_date>', methods=['GET'])
@login_required
def get_time_slots(doctor_id, appointment_date):
    appointment_date = datetime.strptime(appointment_date, '%Y-%m-%d').date()

    # Fetch all appointments for the selected doctor and date
    existing_appointments = OPDAppointment.query.filter_by(
        doctor_id=doctor_id, 
        appointment_date=appointment_date
    ).all()

    occupied_slots = set(appointment.time_slot for appointment in existing_appointments if appointment.user_id == current_user.id)
    
    all_slots = Doctor.query.get(doctor_id).chamber_timings.split(',')
    available_slots = [slot for slot in all_slots if slot not in occupied_slots]

    return jsonify({'time_slots': available_slots})



@user_bp.route('/get_departments/<int:hospital_id>', methods=['GET'])
def get_departments(hospital_id):
    departments = Department.query.filter_by(hospital_id=hospital_id).all()
    return jsonify({'departments': [{'id': dept.id, 'name': dept.name} for dept in departments]})

@user_bp.route('/doctor_details/<int:doctor_id>', methods=['GET'])
@login_required
def doctor_details(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    return render_template('user_dashboard/doctor_details.html', doctor=doctor)