from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, session
from flask_login import login_required, current_user
from models import db, Hospital, Ward, Bed, Booking, Notification, User, Department, Doctor, OPDAppointment, MaxPatient
from flask_mail import Message, Mail
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import logging
logging.basicConfig(level=logging.DEBUG)
mail = Mail()
hospital_bp = Blueprint('hospital_bp', __name__)

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@hospital_bp.route('/hospital_dashboard', methods=['GET'])
@login_required
def hospital_dashboard():
    hospital = current_user.hospitals[0]  # Assuming the current user is associated with only one hospital
    wards = Ward.query.filter_by(hospital_id=hospital.id).all()
    return render_template('HOSPITAL/hospital_dashboard.html', hospital=hospital, wards=wards)

@hospital_bp.route('/get_beds/<int:ward_id>', methods=['GET'])
@login_required
def get_beds(ward_id):
    ward = Ward.query.get_or_404(ward_id)
    beds = Bed.query.filter_by(ward_id=ward_id).all()

    bed_counts = {
        "icu_beds": sum(1 for bed in beds if bed.bed_type == "ICU" and bed.status == 'ready'),
        "opd_beds": sum(1 for bed in beds if bed.bed_type == "OPD" and bed.status == 'ready'),
        "general_beds": sum(1 for bed in beds if bed.bed_type == "General" and bed.status == 'ready')
    }

    return jsonify(bed_counts)

@hospital_bp.route('/update_bed_counts', methods=['POST'])
@login_required
def update_bed_counts():
    logging.debug('Received data: %s', request.json)
    data = request.json
    ward_id = data.get('ward_id')

    if ward_id:
        ward = Ward.query.get(ward_id)
        if not ward:
            return jsonify(success=False, message="Ward not found"), 404

        icu_beds = int(data.get('icu_beds') or 0)
        opd_beds = int(data.get('opd_beds') or 0)
        general_beds = int(data.get('general_beds') or 0)

        # Clear old bed data
        Bed.query.filter_by(ward_id=ward_id, bed_type='ICU').delete()
        Bed.query.filter_by(ward_id=ward_id, bed_type='OPD').delete()
        Bed.query.filter_by(ward_id=ward_id, bed_type='General').delete()

        # Add new bed data
        for _ in range(icu_beds):
            new_bed = Bed(ward_id=ward_id, bed_type='ICU', status='ready')
            db.session.add(new_bed)

        for _ in range(opd_beds):
            new_bed = Bed(ward_id=ward_id, bed_type='OPD', status='ready')
            db.session.add(new_bed)

        for _ in range(general_beds):
            new_bed = Bed(ward_id=ward_id, bed_type='General', status='ready')
            db.session.add(new_bed)

        db.session.commit()

        # Update the hospital's vacant bed counts
        update_vacant_beds(ward.hospital_id)

        return jsonify(success=True)

    return jsonify(success=False, message="Invalid ward ID"), 400



@hospital_bp.route('/get_bed_matrix/<int:ward_id>', methods=['GET'])
@login_required
def get_bed_matrix(ward_id):
    beds = Bed.query.filter_by(ward_id=ward_id).all()

    bed_matrix = [{
        'id': bed.id,
        'status': bed.status,
        'bed_type': bed.bed_type
    } for bed in beds]

    return jsonify(bed_matrix)

@hospital_bp.route('/update_bed_status', methods=['POST'])
@login_required
def update_bed_status():
    data = request.json
    bed_id = data.get('bed_id')
    new_status = data.get('status')

    bed = Bed.query.get(bed_id)
    if bed and new_status in ['ready', 'cleaning', 'occupied']:
        bed.status = new_status
        db.session.commit()

        # Update the hospital's vacant bed counts
        update_vacant_beds(bed.ward.hospital_id)

        return jsonify(success=True)
    
    return jsonify(success=False), 400

@hospital_bp.route('/update_info', methods=['GET', 'POST'])
@login_required
def update_info():
    hospital = Hospital.query.filter_by(admin_id=current_user.id).first()
    if not hospital:
        flash('Hospital not found for this admin user.', 'danger')
        return redirect(url_for('signin'))

    if request.method == 'POST':
        hospital.name = request.form.get('name', '')
        hospital.contact_info = request.form.get('contact_info', '')
        hospital.address = request.form.get('address', '')
        hospital.latitude = request.form.get('latitude', '')
        hospital.longitude = request.form.get('longitude', '')

        db.session.commit()

        flash("Hospital information updated successfully.", "success")
        return redirect(url_for('hospital_bp.hospital_dashboard'))

    return render_template('HOSPITAL/update_info.html', hospital=hospital)

@hospital_bp.route('/wards', methods=['GET', 'POST'])
@login_required
def manage_wards():
    hospital = current_user.hospitals[0]
    if request.method == 'POST':
        name = request.form.get('name')
        managed_by = request.form.get('managed_by')
        head_wardboy_name = request.form.get('head_wardboy_name')

        ward = Ward(name=name, managed_by=managed_by, head_wardboy_name=head_wardboy_name, hospital_id=hospital.id)

        db.session.add(ward)
        db.session.commit()
        flash('Ward added successfully.', 'success')
        return redirect(url_for('hospital_bp.manage_wards'))

    wards = Ward.query.filter_by(hospital_id=hospital.id).all()
    return render_template('HOSPITAL/manage_wards.html', hospital=hospital, wards=wards)

@hospital_bp.route('/hospital/wards/<int:ward_id>/manage_beds', methods=['GET'])
@login_required
def manage_beds(ward_id):
    ward = Ward.query.get_or_404(ward_id)
    beds = Bed.query.filter_by(ward_id=ward_id).all()
    return render_template('HOSPITAL/hospital_dashboard.html', ward=ward, beds=beds)

@hospital_bp.route('/hospital/manage_staff', methods=['GET', 'POST'])
@login_required
def manage_staff():
    hospital = current_user.hospitals[0]
    staff_members = HealthStaff.query.filter_by(ward_id=hospital.id).all()

    return render_template('HOSPITAL/manage_staff.html', staff_members=staff_members)

def update_vacant_beds(hospital_id):
    icu_beds_ready = Bed.query.join(Ward).filter(
        Bed.bed_type == 'ICU',
        Bed.status == 'ready',
        Ward.hospital_id == hospital_id
    ).count()

    opd_beds_ready = Bed.query.join(Ward).filter(
        Bed.bed_type == 'OPD',
        Bed.status == 'ready',
        Ward.hospital_id == hospital_id
    ).count()

    general_beds_ready = Bed.query.join(Ward).filter(
        Bed.bed_type == 'General',
        Bed.status == 'ready',
        Ward.hospital_id == hospital_id
    ).count()

    hospital = Hospital.query.get(hospital_id)
    if hospital:
        hospital.vacant_icu_beds = icu_beds_ready
        hospital.vacant_opd_beds = opd_beds_ready
        hospital.vacant_general_beds = general_beds_ready

        db.session.commit()

# Display current bookings
@hospital_bp.route('/show_bed_booking')
@login_required
def show_bed_booking():
    # Fetch the current hospital associated with the user
    if not current_user.hospitals:
        # Handle the case where the user has no associated hospitals
        return render_template('HOSPITAL/show_bed_booking.html', bookings=[], wards=[], hospital=None)
    
    hospital = current_user.hospitals[0]  # Assuming one hospital per user
    wards = Ward.query.filter_by(hospital_id=hospital.id).all()
    bookings = Booking.query.filter_by(hospital_id=hospital.id).all()
    
    # Debug: Print booking statuses to the console
    for booking in bookings:
        print(f"Booking ID: {booking.id}, Status: {booking.status}")
    
    return render_template('HOSPITAL/show_bed_booking.html', bookings=bookings, wards=wards, hospital=hospital)

# Verify admission code
@hospital_bp.route('/verify_admission_code/<int:booking_id>', methods=['POST'])
@login_required
def verify_admission_code(booking_id):
    data = request.json
    admission_code = data.get('admission_code')

    booking = Booking.query.get_or_404(booking_id)

    if booking.admission_code == admission_code:
        return jsonify(success=True)
    else:
        return jsonify(success=False)

# Complete check-in process
@hospital_bp.route('/complete_check_in/<int:booking_id>', methods=['POST'])
@login_required
def complete_check_in(booking_id):
    data = request.json
    patient_name = data.get('patient_name')
    ward_id = data.get('ward_id')
    bed_type = data.get('bed_type')

    booking = Booking.query.get_or_404(booking_id)

    # Fetch the next available bed in the selected ward
    bed = Bed.query.filter_by(ward_id=ward_id, bed_type=bed_type, status='ready').order_by(Bed.id).first()
    if not bed:
        return jsonify(success=False, message='No available beds found'), 400

    # Assign the bed and update its status to 'occupied'
    bed.status = 'occupied'
    bed_number = generate_bed_number(bed)
    db.session.commit()

    # Store the assigned bed number in the booking
    booking.status = 'CheckedIn'
    booking.assigned_bed_number = bed_number
    booking.user.name = patient_name
    db.session.commit()

    # Send an email to the user with the bed number
    msg = Message('Admission Details', recipients=[booking.user.email])
    msg.body = f"""
    Dear {booking.user.name},

    Your admission process at {booking.hospital.name} is complete. Below are your details:
    Ward: {Ward.query.get(ward_id).name}
    Bed Type: {bed_type}
    Assigned Bed Number: {bed_number}

    Thank you for choosing our services.

    Best regards,
    Hospital Management System
    Supercharged by HospiTell.
    """
    mail.send(msg)

    return jsonify(success=True, bed_number=bed_number)




# Fetch notifications
@hospital_bp.route('/notifications')
@login_required
def notifications():
    hospital_notifications = Notification.query.filter_by(hospital_id=current_user.hospitals[0].id).order_by(Notification.timestamp.desc()).all()
    return render_template('HOSPITAL/notifications.html', notifications=hospital_notifications)

@hospital_bp.route('/clear_notifications')
@login_required
def clear_notifications():
    notifications = Notification.query.filter_by(hospital_id=current_user.hospitals[0].id).all()
    for notification in notifications:
        db.session.delete(notification)
    db.session.commit()
    return redirect(url_for('hospital_bp.notifications'))

@hospital_bp.route('/get_wards_by_bed_type/<string:bed_type>', methods=['GET'])
@login_required
def get_wards_by_bed_type(bed_type):
    hospital = current_user.hospitals[0]  # Assuming the current user is associated with only one hospital
    wards = Ward.query.filter_by(hospital_id=hospital.id).all()

    ward_list = []
    for ward in wards:
        available_beds = Bed.query.filter_by(ward_id=ward.id, bed_type=bed_type, status='ready').count()
        if available_beds > 0:
            ward_list.append({'id': ward.id, 'name': ward.name, 'available_beds': available_beds})

    return jsonify({'wards': ward_list})

def generate_bed_number(bed):
    bed_type_prefix = {
        'General': 'GB',
        'ICU': 'IB',
        'OPD': 'OB'
    }
    # Count the number of already assigned beds of this type in the ward
    bed_count = Bed.query.filter_by(ward_id=bed.ward_id, bed_type=bed.bed_type).filter(Bed.status != 'ready').count()
    return f"{bed_type_prefix[bed.bed_type]}{bed_count + 1}"


@hospital_bp.route('/manage_opd', methods=['GET', 'POST'])
@login_required
def manage_opd():
    hospital = current_user.hospitals[0]  # Assuming the current user is associated with only one hospital

    if request.method == 'POST':
        name = request.form.get('name')
        expertise = request.form.get('expertise')
        chamber_timings = request.form.get('chamber_timings')
        availability_days = request.form.get('availability_days')
        department_id = request.form.get('department_id')

        doctor = Doctor(name=name, expertise=expertise, chamber_timings=chamber_timings,
                        availability_days=availability_days, department_id=department_id,
                        hospital_id=hospital.id)
        db.session.add(doctor)
        db.session.commit()
        flash('Doctor registered successfully', 'success')

    departments = Department.query.filter_by(hospital_id=hospital.id).all()
    doctors = Doctor.query.filter_by(hospital_id=hospital.id).all()

    return render_template('HOSPITAL/manage_opd.html', doctors=doctors, departments=departments, hospital=hospital)


@hospital_bp.route('/show_opd_bookings', methods=['GET'])
@login_required
def show_opd_bookings():
    hospital = current_user.hospitals[0]

    selected_date = request.args.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
    appointments = OPDAppointment.query.join(Doctor).join(Department).filter(
        Department.hospital_id == hospital.id,
        OPDAppointment.appointment_date == selected_date
    ).all()

    return render_template('HOSPITAL/show_opd_bookings.html', appointments=appointments, hospital=hospital, selected_date=selected_date)



@hospital_bp.route('/manage_virtual_queue', methods=['GET', 'POST'])
@login_required
def manage_virtual_queue():
    hospital = current_user.hospitals[0]
    selected_date = request.args.get('date', datetime.utcnow().strftime('%Y-%m-%d'))
    doctor_id = request.args.get('doctor_id')
    time_slot = request.args.get('time_slot')
    
    doctors = Doctor.query.filter_by(hospital_id=hospital.id).all()
    
    if doctor_id:
        selected_doctor = Doctor.query.get(doctor_id)
        time_slots = selected_doctor.chamber_timings.split(',')
    else:
        selected_doctor = None
        time_slots = []

    if request.method == 'POST':
        max_patients = request.form.get('max_patients')
        if doctor_id and time_slot and max_patients.isdigit():
            max_patients = int(max_patients)
            max_patient_entry = MaxPatient.query.filter_by(doctor_id=doctor_id, time_slot=time_slot).first()
            if max_patient_entry:
                max_patient_entry.max_patients = max_patients
            else:
                max_patient_entry = MaxPatient(doctor_id=doctor_id, time_slot=time_slot, max_patients=max_patients)
                db.session.add(max_patient_entry)
            db.session.commit()
            return jsonify(success=True)
        else:
            return jsonify(success=False)

    patients = []
    total_patients = 0
    total_checked_in = 0
    if doctor_id and time_slot:
        patients = OPDAppointment.query.filter_by(
            hospital_id=hospital.id,
            appointment_date=selected_date,
            doctor_id=doctor_id,
            time_slot=time_slot,
            status='CheckedIn'
        ).order_by(OPDAppointment.queue_number).all()
        total_patients = OPDAppointment.query.filter_by(
            hospital_id=hospital.id,
            appointment_date=selected_date,
            doctor_id=doctor_id,
            time_slot=time_slot
        ).count()
        total_checked_in = len(patients)

    return render_template('HOSPITAL/manage_virtual_queue.html', 
                           patients=patients, 
                           hospital=hospital, 
                           doctors=doctors,
                           selected_date=selected_date,
                           selected_doctor=doctor_id,
                           time_slots=time_slots,
                           selected_time_slot=time_slot,
                           total_patients=total_patients,
                           total_checked_in=total_checked_in)

@hospital_bp.route('/create_opd_queue', methods=['POST'])
@login_required
def create_opd_queue():
    selected_date = request.args.get('date')
    doctor_id = request.args.get('doctor_id')
    time_slot = request.args.get('time_slot')
    hospital = current_user.hospitals[0]

    if not doctor_id:
        return jsonify(success=False, error="Doctor ID is required."), 400

    try:
        patients = OPDAppointment.query.filter_by(
            hospital_id=hospital.id,
            appointment_date=selected_date,
            doctor_id=doctor_id,
            time_slot=time_slot,
            status='CheckedIn'
        ).all()

        if not patients:
            return jsonify(success=False, error="No patients found to create the queue.")

        sorted_patients = sorted(patients, key=lambda x: (
            not x.is_emergency,  
            x.user.age < 60, 
            x.id
        ))

        for index, patient in enumerate(sorted_patients, start=1):
            patient.queue_number = index
            db.session.commit()

            # Send email to all patients in the queue with their queue number
            msg = Message('Your OPD Queue Number', recipients=[patient.user.email])
            msg.body = f"""
            Dear {patient.user.name},

            You have been assigned queue number {patient.queue_number} for your OPD appointment with Dr. {patient.doctor.name} on {patient.appointment_date} at {patient.time_slot}.

            Please be prepared to meet the doctor.

            Best regards,
            Hospital Management System
            """
            mail.send(msg)

            # Notify patient when 5 people are ahead in the queue
            if index == len(sorted_patients) - 5:
                msg = Message('Queue Update: 5 People Ahead', recipients=[patient.user.email])
                msg.body = f"""
                Dear {patient.user.name},

                There are 5 people ahead of you in the queue for your OPD appointment with Dr. {patient.doctor.name} on {patient.appointment_date} at {patient.time_slot}.

                Please be prepared to meet the doctor shortly.

                Best regards,
                Hospital Management System
                """
                mail.send(msg)

        return jsonify(success=True), 200

    except Exception as e:
        return jsonify(success=False, error=str(e)), 500





@hospital_bp.route('/register_department', methods=['POST'])
@login_required
def register_department():
    name = request.form.get('name')

    department = Department(name=name)
    db.session.add(department)
    db.session.commit()
    flash('Department registered successfully', 'success')
    return redirect(url_for('hospital_bp.manage_opd'))

@hospital_bp.route('/update_patient_status/<int:appointment_id>', methods=['POST'])
@login_required
def update_patient_status(appointment_id):
    appointment = OPDAppointment.query.get_or_404(appointment_id)
    completed_queue_number = appointment.queue_number

    if completed_queue_number is None:
        return jsonify(success=False, error="Queue number is not set for this appointment."), 400

    appointment.status = 'Done'
    db.session.commit()

    # Send a final confirmation email to the patient
    msg = Message('OPD Appointment Completed', recipients=[appointment.user.email])
    msg.body = f"""
    Dear {appointment.user.name},

    Your OPD appointment with Dr. {appointment.doctor.name} on {appointment.appointment_date} at {appointment.time_slot} is completed.
    Thank you for using our services.

    Best regards,
    Hospital Management System
    """
    mail.send(msg)

    # Notify all remaining patients in the queue
    remaining_patients = OPDAppointment.query.filter(
        OPDAppointment.hospital_id == appointment.hospital_id,
        OPDAppointment.appointment_date == appointment.appointment_date,
        OPDAppointment.status == 'CheckedIn',
        OPDAppointment.queue_number.isnot(None),  # Ensure queue_number is not None
        OPDAppointment.queue_number > completed_queue_number
    ).order_by(OPDAppointment.queue_number).all()

    for patient in remaining_patients:
        send_queue_update_email(patient.queue_number, patient)
    
    flash('Patient status updated successfully', 'success')
    return jsonify(success=True)

def send_queue_update_email(queue_number, patient):
    msg = Message('Queue Update: Your Position', recipients=[patient.user.email])
    msg.body = f"""
    Dear {patient.user.name},

    Your queue number is now {queue_number}.

    Please be prepared to meet the doctor shortly.

    Best regards,
    Hospital Management System
    """
    mail.send(msg)


@hospital_bp.route('/get_departments/<int:hospital_id>', methods=['GET'])
@login_required
def get_departments(hospital_id):
    departments = Department.query.filter_by(hospital_id=hospital_id).all()
    return jsonify({'departments': [{'id': dept.id, 'name': dept.name, 'image': dept.image} for dept in departments]})



@hospital_bp.route('/manage_opd_landing')
@login_required
def manage_opd_landing():
    hospital = current_user.hospitals[0]
    return render_template('HOSPITAL/manage_opd_landing.html', hospital=hospital)


@hospital_bp.route('/manage_departments', methods=['GET', 'POST'])
@login_required
def manage_departments():
    hospital = current_user.hospitals[0]

    if request.method == 'POST':
        department_name = request.form.get('department_name')

        # Handle department image upload
        if 'department_image' in request.files:
            file = request.files['department_image']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(current_app.config['UPLOAD_LOCATION'], filename)
                file.save(filepath)
                image_path = os.path.join('images/', filename)
            else:
                image_path = None
        else:
            image_path = None

        department = Department(name=department_name, image=image_path, hospital_id=hospital.id)
        db.session.add(department)
        db.session.commit()
        flash('Department added successfully', 'success')

    departments = Department.query.filter_by(hospital_id=hospital.id).all()

    return render_template('HOSPITAL/manage_departments.html', departments=departments, hospital=hospital)


@hospital_bp.route('/manage_doctors', methods=['GET', 'POST'])
@login_required
def manage_doctors():
    hospital = current_user.hospitals[0]

    if request.method == 'POST':
        name = request.form.get('name')
        expertise = request.form.get('expertise')
        chamber_timings = request.form.get('chamber_timings')
        availability_days = request.form.get('availability_days')
        department_id = request.form.get('department_id')

        doctor = Doctor(name=name, expertise=expertise, chamber_timings=chamber_timings,
                        availability_days=availability_days, department_id=department_id,
                        hospital_id=hospital.id)
        db.session.add(doctor)
        db.session.commit()
        flash('Doctor registered successfully', 'success')

    departments = Department.query.filter_by(hospital_id=hospital.id).all()
    doctors = Doctor.query.filter_by(hospital_id=hospital.id).all()
    return render_template('HOSPITAL/manage_doctors.html', doctors=doctors, departments=departments, hospital=hospital)


@hospital_bp.route('/get_doctors/<int:department_id>', methods=['GET'])
@login_required
def get_doctors(department_id):
    # Fetch all doctors in the selected department
    doctors = Doctor.query.filter_by(department_id=department_id).all()
    
    doctor_list = [{'id': doctor.id, 'name': doctor.name} for doctor in doctors]
    
    return jsonify({'doctors': doctor_list})

@hospital_bp.route('/get_time_slots/<int:doctor_id>', methods=['GET'])
@login_required
def get_time_slots(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    time_slots = doctor.chamber_timings.split(',')  # Assuming chamber_timings is stored as a comma-separated string
    
    return jsonify({'time_slots': time_slots})



@hospital_bp.route('/verify_appointment_code/<int:appointment_id>', methods=['POST'])
@login_required
def verify_appointment_code(appointment_id):
    data = request.json
    appointment_code = data.get('appointment_code')

    # Fetch the appointment
    appointment = OPDAppointment.query.get_or_404(appointment_id)

    # Verify the appointment code
    if appointment.appointment_code == appointment_code:
        return jsonify(success=True)
    else:
        return jsonify(success=False)


@hospital_bp.route('/complete_opd_check_in/<int:appointment_id>', methods=['POST'])
@login_required
def complete_opd_check_in(appointment_id):
    data = request.json
    appointment = OPDAppointment.query.get_or_404(appointment_id)

    # Update the appointment status
    appointment.status = 'CheckedIn'
    if data.get('age'):
        appointment.user.age = data.get('age')
    
    # Update emergency status if provided
    appointment.is_emergency = bool(data.get('is_emergency'))  # Ensure it's saved as a boolean
    
    db.session.commit()

    # Send a notification email to the patient
    msg = Message('OPD Appointment Check-In Confirmation', recipients=[appointment.user.email])
    msg.body = f"""
    Dear {appointment.user.name},

    You have successfully checked in for your OPD appointment with Dr. {appointment.doctor.name} on {appointment.appointment_date}.
    You are in the queue. We will notify you with the current queue status.

    Best regards,
    Hospital Management System
    """
    mail.send(msg)

    return jsonify(success=True)





@hospital_bp.route('/on_spot_registration', methods=['POST'])
@login_required
def on_spot_registration():
    name = request.form.get('name')
    email = request.form.get('email')
    age = request.form.get('age')
    is_emergency = request.form.get('is_emergency') == 'true'

    selected_date = request.args.get('date')
    doctor_id = request.args.get('doctor_id')
    time_slot = request.args.get('time_slot')
    hospital = current_user.hospitals[0]

    if not doctor_id or not time_slot:
        return jsonify(success=False, message='Doctor and Time Slot must be selected for registration.')

    if age is not None and age.isdigit():
        age = int(age)
    else:
        return jsonify(success=False, message='Invalid age entered.')

    temp_user = User(
        name=name,
        email=email,
        password='',
        role='patient',
        age=age
    )
    db.session.add(temp_user)
    db.session.commit()

    total_patients_in_queue = OPDAppointment.query.filter_by(
        hospital_id=hospital.id,
        doctor_id=doctor_id,
        appointment_date=selected_date,
        time_slot=time_slot,
        status='CheckedIn'
    ).count()

    max_patients = MaxPatient.query.filter_by(doctor_id=doctor_id, time_slot=time_slot).first()

    if max_patients and total_patients_in_queue < max_patients.max_patients:
        patient = OPDAppointment(
            user_id=temp_user.id,
            doctor_id=doctor_id,
            appointment_date=datetime.today(),
            time_slot=time_slot,
            hospital_id=hospital.id,
            is_emergency=is_emergency,
            status='CheckedIn'
        )
        db.session.add(patient)
        db.session.commit()
        return jsonify(success=True, message='Patient successfully registered.')
    else:
        return jsonify(success=False, message='Doctor is fully booked for this time slot.')


@hospital_bp.route('/set_max_patients', methods=['POST'])
@login_required
def set_max_patients():
    max_patients = request.form.get('max_patients')

    if max_patients is not None and max_patients.isdigit():
        max_patients = int(max_patients)
        session['max_patients'] = max_patients
        return jsonify(success=True)
    else:
        return jsonify(success=False), 400


