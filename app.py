from flask import Flask, render_template, redirect, url_for, request, session, flash,jsonify, Response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import json
import re
import io
import logging
import os
from datetime import datetime
from flask_mail import Mail, Message
from flask_bcrypt import Bcrypt
from flask_mysqldb import MySQL
from flask_dance.contrib.google import make_google_blueprint, google
from flask_dance.contrib.facebook import make_facebook_blueprint, facebook
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user, logout_user
from config import Config  # Import the Config class
import requests  # To make API calls
from requests.auth import HTTPBasicAuth
import cv2
import numpy as np
import time
import mediapipe as mp
import math
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
import threading
import schedule
import stream
import datetime
from flask_wtf import FlaskForm
from wtforms import StringField, FileField, SubmitField,TextAreaField
from wtforms.validators import DataRequired
from PIL import Image
from datetime import datetime
from flask_wtf.file import FileAllowed, FileRequired
import hashlib
from wtforms import StringField, SelectField, SubmitField
from models import db, User, Userfg, Hospital, Booking, Rating, Item, Cart, CartItem, Order, Post, Media, Comment, Like, Posts, OPDAppointment


  # Import your models here



with open('config.json', 'r') as c:
    config_params = json.load(c)["params"]

local_server = True


app =Flask(__name__)
app.secret_key = 'soumo-diamond'
app.config['UPLOAD_FOLDER'] = config_params['upload_location']
app.config['SESSION_TYPE'] = 'filesystem'
app.config.from_object(Config)  
app.config['GOOGLE_OAUTH_CLIENT_ID'] = 'your_google_client_id'
app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = 'your_google_client_secret'
app.config['FACEBOOK_OAUTH_CLIENT_ID'] = 'your_facebook_client_id'
app.config['FACEBOOK_OAUTH_CLIENT_SECRET'] = 'your_facebook_client_secret'




app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT='465',
    MAIL_USE_SSL=True,
    MAIL_USERNAME=config_params['gmail-id'],
    MAIL_PASSWORD=config_params['gmail-password'],
    MYSQL_USER=config_params['mysql_user'],
    MYSQL_PASSWORD=config_params['mysql_password'],
    MYSQL_DB=config_params['mysql_db'],
    MYSQL_HOST=config_params['mysql_host']
)
def truncate_words(s, num):
    if not s:
        return ''
    words = re.findall(r'\w+', s)
    if len(words) > num:
        return ' '.join(words[:num]) + '...'
    return s

app.jinja_env.filters['truncate_words'] = truncate_words








def get_access_token():
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }
    response = requests.post(ACCESS_TOKEN_URL, data=data)
    token_info = response.json()
    return token_info['access_token']



def generate_checksum(params, merchant_key):
    params_str = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
    params_str += f'&{merchant_key}'
    return hashlib.sha256(params_str.encode()).hexdigest()

def verify_checksum(params, merchant_key, received_checksum):
    params_str = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
    params_str += f'&{merchant_key}'
    return hashlib.sha256(params_str.encode()).hexdigest() == received_checksum



ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov','csv'}  # Add any other allowed extensions here

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


mail = Mail(app)
mysql = MySQL(app) 
bcrypt = Bcrypt(app)
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])
google_bp = make_google_blueprint(
    client_id=config_params['google_client_id'],
    client_secret=config_params['google_client_secret'],
    redirect_to='google_login'
)
facebook_bp = make_facebook_blueprint(redirect_to='facebook_login')

app.register_blueprint(google_bp, url_prefix='/login')
app.register_blueprint(facebook_bp, url_prefix='/login')

logging.basicConfig()


login_manager = LoginManager(app)
login_manager.login_view = 'signin'  # Redirect to signin page if unauthorized
login_manager.login_message_category = 'danger'

if local_server:
    app.config['SQLALCHEMY_DATABASE_URI'] = config_params['local_uri']
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = config_params['prod_uri']

db.init_app(app)

# Register Blueprints
from routes.user_routes import user_bp
from routes.hospital_routes import hospital_bp


app.register_blueprint(user_bp)
app.register_blueprint(hospital_bp)


class PostForm(FlaskForm):
    content = TextAreaField('Content', validators=[DataRequired()])
    media = FileField('Media', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'mp4', 'mov', 'avi'], 'Images and videos only!')], render_kw={'multiple': True})
    submit = SubmitField('Post')



def resize_image(image_path):
    img = Image.open(image_path)
    img.thumbnail((400, 400))  # Resize to fit within a 400x400 box
    img.save(image_path)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_user():
    return dict(user=current_user)



@app.route('/community', methods=['GET', 'POST'])
@login_required
def community():
    form = PostForm()
    if form.validate_on_submit():
        post = Post(content=form.content.data, user_id=current_user.id)
        db.session.add(post)
        db.session.commit()

        for file in request.files.getlist('media'):
            if file:
                filename = secure_filename(file.filename)
                file_ext = filename.rsplit('.', 1)[1].lower()
                file_type = 'image' if file_ext in ['jpg', 'jpeg', 'png', 'gif'] else 'video'
                media_path = os.path.join('static', 'images', filename)
                file.save(media_path)
                media = Media(file_name=filename, file_type=file_type, post_id=post.id)
                db.session.add(media)
        
        db.session.commit()
        flash('Post created successfully!', 'success')
        return redirect(url_for('community'))

    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template('global-chat.html', form=form, posts=posts)

@app.route('/comment/<int:post_id>', methods=['POST'])
@login_required
def comment(post_id):
    content = request.form.get('content')
    user_id = current_user.id
    new_comment = Comment(post_id=post_id, user_id=user_id, content=content)
    db.session.add(new_comment)
    db.session.commit()

    response = {
        'result': 'success',
        'comment_author_image': url_for('static', filename=current_user.profile_image),
        'comment_author_name': current_user.name,
        'comment_content': new_comment.content
    }

    return jsonify(response)
@app.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like(post_id):
    post = Post.query.get_or_404(post_id)
    user_id = current_user.id
    existing_like = Like.query.filter_by(post_id=post_id, user_id=user_id).first()

    if existing_like:
        db.session.delete(existing_like)
        db.session.commit()
        return jsonify({'result': 'unliked', 'likes_count': len(post.likes)})

    new_like = Like(post_id=post_id, user_id=user_id)
    db.session.add(new_like)
    db.session.commit()
    return jsonify({'result': 'liked', 'likes_count': len(post.likes)})








@app.route('/search-nav', methods=['POST', 'GET'])
@login_required
def search2():
    query = request.form.get('query')
    if not query:
        return redirect(url_for('userdashboard'))

    # Determine which page to redirect to based on the query
    if 'nutrition' in query.lower():
        return redirect(url_for('nutrition'))
    elif 'blog' in query.lower():
        return redirect(url_for('userblogs'))
    elif 'contact' in query.lower():
        return redirect(url_for('usercontact'))
    elif 'marketplace' in query.lower():
        return redirect(url_for('marketplace'))
    elif 'faq' in query.lower():
        return redirect(url_for('faq'))
    elif 'computer vision guide' in query.lower():
        return redirect(url_for('video'))
    else:
        flash('No results found ', 'warning')
        return redirect(url_for('userdashboard'))



@app.route('/request_reset', methods=['GET', 'POST'])
def request_reset():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            token = s.dumps(email, salt='password-reset-salt')
            link = url_for('reset_password', token=token, _external=True)
            send_email(user.email, 'Password Reset Request', f'Click the link to reset your password: {link}')
            flash('An email has been sent with instructions to reset your password.', 'info')
            return redirect(url_for('signin'))
    return render_template('request_reset.html')

def send_email(to, subject, body):
    msg = Message(subject, recipients=[to], body=body, sender=config_params['gmail-id'])
    mail.send(msg)

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=3600)
    except SignatureExpired:
        flash('The reset link is expired.', 'warning')
        return redirect(url_for('request_reset'))
    except BadSignature:
        flash('The reset link is invalid.', 'danger')
        return redirect(url_for('request_reset'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user:
            user.password = bcrypt.generate_password_hash(password).decode('utf-8')
            db.session.commit()
            flash('Your password has been reset.', 'success')
            return redirect(url_for('signin'))
    return render_template('reset_password.html', token=token)

@app.route('/google_login')
def google_login():
    if not google.authorized:
        return redirect(url_for('google.login'))
    resp = google.get('/plus/v1/people/me')
    assert resp.ok, resp.text
    user_info = resp.json()
    email = user_info['emails'][0]['value']
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            name=user_info['displayName'],
            email=email,
            oauth_provider='google',
            oauth_id=user_info['id']
        )
        db.session.add(userfg)
        db.session.commit()
    login_user(user)
    return redirect(url_for('index'))

@app.route('/facebook_login')
def facebook_login():
    if not facebook.authorized:
        return redirect(url_for('facebook.login'))
    resp = facebook.get('/me?fields=id,name,email')
    assert resp.ok, resp.text
    user_info = resp.json()
    email = user_info['email']
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            name=user_info['name'],
            email=email,
            oauth_provider='facebook',
            oauth_id=user_info['id']
        )
        db.session.add(userfg)
        db.session.commit()
    login_user(user)
    return redirect(url_for('index'))




@app.route('/', methods=['POST', 'GET'])
def index():
    posts = Posts.query.order_by(Posts.date.desc()).all()
    return render_template('index.html', params=config_params, posts=posts)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('cf-name')
        phone = request.form.get('cf-phone')
        email = request.form.get('cf-email')
        message = request.form.get('cf-message')

        entry = Query(Name=name, Email=email, Message=message, Phone_number=phone)
        db.session.add(entry)
        db.session.commit()
        flash("Query sent successfully! You will be contacted shortly!", "success")
        mail.send_message('New Query from ' + name,
                          sender=email,
                          recipients=[config_params['gmail-id']],
                          body=message + "\n" + "\n" + phone
                          )
        return redirect('/#contact')
    return render_template('index.html', params=config_params, posts=posts)


@app.route('/user-contact', methods=['GET', 'POST'])
@login_required
def usercontact():
    if request.method == 'POST':
        name = request.form.get('cf-name')
        phone = request.form.get('cf-phone')
        email = request.form.get('cf-email')
        message = request.form.get('cf-message')
        entry = Query(Name=name, Email=email, Message=message, Phone_number=phone)
        db.session.add(entry)
        db.session.commit()
        flash("Query sent successfully! You will be contacted shortly!", "success")
        mail.send_message('New Query from ' + name,
                          sender=email,
                          recipients=[config_params['gmail-id']],
                          body=message + "\n" + "\n" + phone
                          )
        return redirect('/user-contact')
    return render_template('user_dashboard/pages-contact.html', params=config_params,user=current_user)



@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = current_user
    if request.method == 'POST':
          # Handle profile image upload
        if 'upload' in request.files:
            file = request.files['upload']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                current_user.profile_image = os.path.join('images/', filename)
                db.session.commit()
                flash('Profile image updated successfully', 'success')
        current_user.name = request.form.get('name')
        current_user.company = request.form.get('company')
        current_user.job = request.form.get('job')
        current_user.country = request.form.get('country')
        current_user.address = request.form.get('address')
        current_user.phone = request.form.get('phone')
        current_user.twitter = request.form.get('twitter')
        current_user.facebook = request.form.get('facebook')
        current_user.instagram = request.form.get('instagram')
        current_user.linkedin = request.form.get('linkedin')
        db.session.commit()
        flash('Profile updated successfully', 'success')
        return redirect(url_for('profile'))
    return render_template('user_dashboard/users-profile.html', user=current_user, params=config_params)

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS




@app.route("/admin/add_item", methods=['GET', 'POST'])
def add_item():
    if 'user' in session and session['user'] == config_params['admin-user']:
        if request.method == 'POST':
            name = request.form.get('name')
            description = request.form.get('description')
            price = request.form.get('price')
            discount_price = request.form.get('discount_price')
            upload = request.files.get('upload')

            if upload and allowed_file(upload.filename):
                filename = secure_filename(upload.filename)
                upload.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_file = "images/" + filename
            else:
                image_file = None

            if image_file:
                item = Item(name=name, description=description, price=price, discount_price=discount_price, image_file=image_file)
                db.session.add(item)
                db.session.commit()
                flash("Item added successfully!", "success")
                return redirect(url_for('add_item'))
            else:
                flash("Invalid file format. Please upload a valid image.", "danger")
                return redirect(url_for('add_item'))

        return render_template('admin_panel/add_item.html', params=config_params)
    else:
        flash("You are not authorized to access this page.", "danger")
        return redirect(url_for('signin'))








@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        renew_password = request.form['renew_password']

        if not check_password_hash(current_user.password, current_password):
            flash('Current password is incorrect', 'danger')
        elif new_password != renew_password:
            flash('New passwords do not match', 'danger')
        else:
            current_user.password = generate_password_hash(new_password, method='sha256')
            db.session.commit()
            flash('Password changed successfully', 'success')
            return redirect(url_for('profile'))

    return render_template('change_password.html',user=current_user)


@app.route("/blogs", methods=['GET'])
def blogs():
    posts = Posts.query.order_by(Posts.date.desc()).all()  # Sort by date in descending order
    return render_template('blogs.html', posts=posts, params=config_params)



@app.route('/my_profile')
@login_required
def myprofile():
    return render_template("user_dashboard/users-profile.html", params=config_params,user=current_user)




@app.route('/marketplace')
@login_required
def marketplace():
    items = Item.query.all()
    return render_template('user_dashboard/marketplace.html', items=items)

@app.route('/add_to_cart/<int:item_id>', methods=['POST'])
@login_required
def add_to_cart(item_id):
    item = Item.query.get_or_404(item_id)
    cart = Cart.query.filter_by(user_id=current_user.id).first()

    if not cart:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.commit()
    
    print(f"Cart ID after commit: {cart.id}")

    cart_item = CartItem.query.filter_by(cart_id=cart.id, item_id=item_id).first()

    if cart_item:
        cart_item.quantity += 1
    else:
        cart_item = CartItem(cart_id=cart.id, item_id=item_id, quantity=1)
        db.session.add(cart_item)

    db.session.commit()
    return jsonify({'success': True, 'message': 'Item added to cart!'})



@app.route('/order_confirmation')
@login_required
def order_confirmation():
    order_id = request.args.get('order_id')
    success = request.args.get('success') == 'true'
    order = Order.query.get(order_id)
    return render_template('user_dashboard/order_confirmation.html', order=order, success=success)



@app.route('/cart')
@login_required
def cart():
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart:
        cart_items = []
    else:
        cart_items = cart.items

    total_amount = sum(item.item.discount_price * item.quantity for item in cart_items)
    return render_template('user_dashboard/cart.html', cart=cart, total_amount=total_amount)


@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart:
        cart_items = []
    else:
        cart_items = cart.items

    total_amount = sum(item.item.discount_price * item.quantity for item in cart_items) * 100  # Convert to paise (integer)

    if total_amount <= 0:
        flash('Your cart is empty. Please add items to your cart before checking out.', 'warning')
        return redirect(url_for('cart'))

    return render_template('user_dashboard/checkout.html', total_amount=total_amount, paytm_merchant_id=app.config['PAYTM_MID'])





def generate_checksum(params, merchant_key):
    # Function to generate checksum
    params_str = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
    params_str += f'&{merchant_key}'
    return hashlib.sha256(params_str.encode()).hexdigest()




@app.route('/update_cart', methods=['POST'])
@login_required
def update_cart():
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart:
        return jsonify({'success': False, 'message': 'No cart found for the user.'})

    print(f"Cart ID for update: {cart.id}")  # Debugging line

    for key in request.form:
        if key.startswith('quantity_'):
            item_id = int(key.split('_')[1])
            quantity = int(request.form[key])
            if quantity > 0:
                cart_item = CartItem.query.filter_by(cart_id=cart.id, item_id=item_id).first()
                if cart_item:
                    cart_item.quantity = quantity
                else:
                    return jsonify({'success': False, 'message': f'Item with ID {item_id} not found in the cart.'})
            else:
                cart_item = CartItem.query.filter_by(cart_id=cart.id, item_id=item_id).first()
                if cart_item:
                    db.session.delete(cart_item)
    
    db.session.commit()
    return jsonify({'success': True, 'message': 'Cart updated successfully!'})



@app.route('/remove_from_cart/<int:item_id>', methods=['GET'])
@login_required
def remove_from_cart(item_id):
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart:
        return jsonify({'success': False, 'message': 'No cart found for the user.'})

    cart_item = CartItem.query.filter_by(cart_id=cart.id, item_id=item_id).first()
    if cart_item:
        db.session.delete(cart_item)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Item removed from cart successfully!'})
    else:
        return jsonify({'success': False, 'message': 'Item not found in cart.'})


@app.route('/payment_status', methods=['POST'])
@login_required
def payment_status():
    cart = Cart.query.filter_by(user_id=current_user.id).first()
    if not cart:
        return jsonify({'success': False, 'message': 'No cart found for the user.'})

    # Debugging to ensure cart_id is valid
    print(f"Cart ID: {cart.id}")

    # Process cart items
    for item in cart.items:
        print(f"Cart Item ID: {item.id}, Cart ID: {item.cart_id}")  # Debugging line
        # Ensure cart_id is set
        if item.cart_id is None:
            item.cart_id = cart.id

    # Create and add the order
    order = Order(
        user_id=current_user.id,
        name=request.form['name'],
        address=request.form['address'],
        mobile=request.form['mobile'],
        total_amount=int(float(request.form['total_amount'])),  # Convert to integer
        payment_status='Pending',
        payment_method=request.form['payment_method']
    )
    db.session.add(order)

    try:
        db.session.commit()
        # Redirect to order confirmation page with success parameter
        return redirect(url_for('order_confirmation', success='true', order_id=order.id))
    except Exception as e:
        db.session.rollback()
        print(f"Exception: {str(e)}")  # Debugging line
        return jsonify({'success': False, 'message': 'An error occurred while processing the payment.'})

@app.route('/my_orders')
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=current_user.id).all()
    return render_template('user_dashboard/my_orders.html', orders=orders)

@app.route('/edit_order/<int:order_id>', methods=['GET', 'POST'])
@login_required
def edit_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        abort(403)
    
    if request.method == 'POST':
        order.name = request.form['name']
        order.address = request.form['address']
        order.mobile = request.form['mobile']
        db.session.commit()
        flash('Your order has been updated!', 'success')
        return redirect(url_for('my_orders'))
    
    return render_template('user_dashboard/edit_order.html', order=order)

@app.route('/cancel_order/<int:order_id>', methods=['POST'])
@login_required
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        db.session.delete(order)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Your order has been canceled.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'An error occurred while canceling the order.'})



def verify_checksum(params, merchant_key, received_checksum):
    # Function to verify checksum
    params_str = '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
    params_str += f'&{merchant_key}'
    return hashlib.sha256(params_str.encode()).hexdigest() == received_checksum

#@app.route('/admin/orders')
#@login_required
#def admin_orders():
#    if current_user.is_admin:
#        orders = Order.query.all()
#        return render_template('admin_panel/orders.html', orders=orders)
#    else:
#        flash('You are not authorized to access this page.', 'danger')
#        return redirect(url_for('signin'))


#@app.route('/index')
#@login_required
#def index2():
#    return render_template("user_dashboard/index.html", params=config_params,user=current_user)

@app.route("/user-blogs", methods=['GET'])
@login_required
def userblogs():
    posts = Posts.query.order_by(Posts.date.desc()).all()  # Sort by date in descending order
    return render_template('user_dashboard/user-blog.html', posts=posts,params=config_params,user=current_user)

@app.route('/faq')
@login_required
def faq():
    return render_template("user_dashboard/pages-faq.html", params=config_params,user=current_user)



@app.route("/new_post", methods=['GET', 'POST'])
def new_post():
    if 'user' in session and session['user'] == config_params['admin-user']:
        if request.method == 'POST':
            title = request.form.get('title')
            id = request.form.get('id')
            content = request.form.get('content')
            upload = request.files.get('upload')
            date = datetime.now()

            if upload:
                filename = secure_filename(upload.filename)
                upload.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                img_file = "images/" + filename
            else:
                img_file = None

            post = Posts(title=title, id=id, content=content, img_file=img_file, date=date)
            db.session.add(post)
            db.session.commit()
            flash("File uploaded successfully!", "success")
            return redirect('/edit/' + str(post.sno))

        return render_template('admin_panel/edit.html', posts=Posts, params=config_params, post=None, user=current_user)

@app.route("/edit/<string:sno>", methods=['GET', 'POST'])
def edit(sno):
    if 'user' in session and session['user'] == config_params['admin-user']:
        post = Posts.query.filter_by(sno=sno).first()
        if request.method == 'POST':
            title = request.form.get('title')
            id = request.form.get('id')
            content = request.form.get('content')
            upload = request.files.get('upload')
            date = datetime.now()

            if upload:
                filename = secure_filename(upload.filename)
                upload.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                img_file = "images/" + filename
                post.img_file = img_file

            post.title = title
            post.id = id
            post.content = content
            post.date = date
            db.session.commit()
            flash("File uploaded successfully!", "success")
            return redirect('/edit/' + sno)

        return render_template('admin_panel/edit.html', posts=Posts, params=config_params, post=post)
@app.route("/signin", methods=['GET', 'POST'])  # SIGN IN
def signin():
    logging.debug(f'Session state: {session}')
    if 'user' in session and session['user'] == config_params['admin-user']:
        logging.debug('Admin user already logged in.')  
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        logging.debug(f'Attempting login with email: {email}')

        if email == config_params['admin-user'] and password == config_params['admin-password']:
            session['user'] = email
            logging.debug('Admin login successful.')
            return redirect(url_for('admin_dashboard'))

        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully.', 'success')
            if user.role == 'hospital_admin':
                return redirect(url_for('hospital_bp.hospital_dashboard'))  # Redirect based on role
            elif user.role == 'ambulance_driver':
                return redirect(url_for('ambulance_bp.ambulance_dashboard'))
            else:
                return redirect(url_for('user_bp.dashboard'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('signup.html', params=config_params)





@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']  # Get the role from the form
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        # Create a new user
        user = User(name=name, email=email, password=hashed_password, role=role)
        db.session.add(user)
        db.session.commit()

        # Check the role and create related records
        if role == 'hospital_admin':
            hospital_name = request.form.get('hospital_name')  # Ensure you have this field in your signup form
            hospital = Hospital(name=hospital_name, admin_id=user.id)
            db.session.add(hospital)
            db.session.commit()
            flash('Hospital account created successfully!', 'success')
            return redirect(url_for('hospital_bp.hospital_dashboard'))
        
        elif role == 'ambulance_driver':
            driver_name = request.form.get('driver_name')  # Ensure you have this field in your signup form
            driver = AmbulanceDriver(name=driver_name, user_id=user.id)
            db.session.add(driver)
            db.session.commit()
            flash('Ambulance driver account created successfully!', 'success')
            return redirect(url_for('ambulance_bp.ambulance_dashboard'))
        
        else:
            flash('User account created successfully! Please log in.', 'success')
            return redirect(url_for('signin'))

    return render_template('signup.html', params=config_params)



@app.route("/logout")
def logout():
    session.pop('user')
    return redirect('/signin')

@app.route("/signout")
@login_required
def signout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('signin'))

@app.route("/delete/<string:sno>", methods=['GET', 'POST'])
def delete(sno):
    if 'user' in session and session['user'] == config_params['admin-user']:
        post = Posts.query.filter_by(sno=sno).first()
        db.session.delete(post)
        db.session.commit()
    return redirect('/signin')




@app.route("/admin/dashboard")
def admin_dashboard():
    if 'user' in session and session['user'] == config_params['admin-user']:
        items = Item.query.all()
        posts = Posts.query.order_by(Posts.date.desc()).all()
        return render_template('admin_panel/dashboard.html', items=items, posts=posts)
    else:
        flash("You are not authorized to access this page.", "danger")
        return redirect(url_for('signin'))

@app.route("/admin/edit_item/<int:item_id>", methods=['GET', 'POST'])
def edit_item(item_id):
    if 'user' in session and session['user'] == config_params['admin-user']:
        item = Item.query.get_or_404(item_id)
        if request.method == 'POST':
            item.name = request.form.get('name')
            item.description = request.form.get('description')
            item.price = float(request.form.get('price'))
            item.discount_price = float(request.form.get('discount_price')) if request.form.get('discount_price') else None
            upload = request.files.get('upload')

            if upload and allowed_file(upload.filename):
                filename = secure_filename(upload.filename)
                upload.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                item.image_file = "images/" + filename

            db.session.commit()
            flash("Item updated successfully!", "success")
            return redirect(url_for('admin_dashboard'))

        return render_template('admin_panel/edit_item.html', item=item, params=config_params)
    else:
        flash("You are not authorized to access this page.", "danger")
        return redirect(url_for('signin'))

@app.route("/admin/delete_item/<int:item_id>")
def delete_item(item_id):
    if 'user' in session and session['user'] == config_params['admin-user']:
        item = Item.query.get_or_404(item_id)
        db.session.delete(item)
        db.session.commit()
        flash("Item deleted successfully!", "success")
        return redirect(url_for('admin_dashboard'))
    else:
        flash("You are not authorized to access this page.", "danger")
        return redirect(url_for('signin'))





#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
#SIH 2024
#----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------




if __name__ == "__main__":
    with app.app_context():
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        db.create_all() 
        app.run(debug=True, port=7777)
