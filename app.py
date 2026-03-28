from flask import Flask, render_template, request, jsonify, session, send_from_directory, redirect, url_for
from flask_cors import CORS
from pymongo import MongoClient
from bson import ObjectId
from bson.errors import InvalidId
import bcrypt

from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from functools import wraps
import uuid
from google.oauth2 import id_token
from google.auth.transport import requests
import jwt


from werkzeug.utils import secure_filename

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Enable CORS
CORS(app, supports_credentials=True)

ADMIN_EMAILS = [
    "shantachaudhari74@gmail.com",
    "ujvalbhavre99@gmail.com",
    "dhruv61222@gmail.com"
]

GOOGLE_CLIENT_ID = "723840503533-iv1ai6u7pc3k8qddehm3dsb83u3q85kq.apps.googleusercontent.com"


def create_jwt(user_id, role):
    payload = {
        "user_id": str(user_id),
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm="HS256")

from functools import wraps

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = users_collection.find_one({'_id': ObjectId(data['user_id'])})
            if not current_user or current_user.get('role') != 'admin':
                return jsonify({'message': 'Admin access required'}), 403
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token is invalid'}), 401
        
        return f(current_user, *args, **kwargs)
    return decorated

@app.route('/api/contact', methods=['POST'])
def submit_contact():
    print("🔥 /api/contact HIT")

    try:
        data = request.get_json()
        print("📩 Received data:", data)

        contact_doc = {
            "name": data.get("name"),
            "email": data.get("email"),
            "subject": data.get("subject"),
            "message": data.get("message"),
            "status": "new",
            "created_at": datetime.utcnow()
        }

        contacts_collection.insert_one(contact_doc)
        print("✅ Inserted into MongoDB")

        return jsonify({"message": "Message sent"}), 201

    except Exception as e:
        print("❌ ERROR:", e)
        return jsonify({"error": str(e)}), 500



@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login.html')
def login_page(): 
    return render_template('login.html')

@app.route("/auth/google")
def google_login():
    # 🔴 TEMPORARY MOCK (since frontend already logs in via Google)
    # In real OAuth, this email comes from Google response
    email = request.args.get("email")

    if not email:
        return "Email not provided", 400

    session["user_email"] = email
    return redirect("/auth/google/callback")

@app.route("/auth/google/callback", methods=["POST"])
def google_auth():
    try:
        # 1️⃣ Read credential from FormData (this matches your login.html)
        credential = request.form.get("credential")

        if not credential:
            return jsonify({"error": "Missing Google credential"}), 400

        # 2️⃣ Verify Google token
        idinfo = id_token.verify_oauth2_token(
            credential,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )

        # 3️⃣ Extract email
        email = idinfo.get("email")
        if not email:
            return jsonify({"error": "Email not found"}), 400

        # 4️⃣ Allow only Silver Oak OR Admin emails
        if not (email.endswith("@silveroakuni.ac.in") or email in ADMIN_EMAILS):
            return jsonify({"error": "Only Silver Oak University emails are allowed"}), 403

        # 5️⃣ Decide role
        role = "admin" if email in ADMIN_EMAILS else "user"

        # 6️⃣ Find or create user
        user = users_collection.find_one({"email": email})

        if user and user.get("status") == "disabled":
           return jsonify({"error": "Your account has been disabled by admin"}), 403


        if not user:
            user_doc = {
                "username": email.split("@")[0],
                "email": email,
                "role": role,
                "status": "active",
                "provider": "google",
                "profile": {
                    "created_at": datetime.utcnow()
                }
            }
            result = users_collection.insert_one(user_doc)
            user_id = result.inserted_id
        else:
            user_id = user["_id"]

            # Force admin role if needed
            if email in ADMIN_EMAILS and user.get("role") != "admin":
                users_collection.update_one(
                    {"_id": user_id},
                    {"$set": {"role": "admin"}}
                )
                role = "admin"
            else:
                role = user.get("role", "user")

        # 7️⃣ Create JWT
        jwt_token = create_jwt(user_id, role)

        # 8️⃣ Send response to frontend
        return jsonify({
            "message": "Login successful",
            "token": jwt_token,
            "email": email,
            "role": role
        }), 200

    except Exception as e:
        print("Google login error:", e)
        return jsonify({"error": "Authentication failed"}), 500





@app.route('/userdesbord.html')
def user_dashboard():
    return render_template('userdesbord.html')

@app.route('/lostitem.html')
def lost_item_page():
    return render_template('lostitem.html')

@app.route('/founditem.html')
def found_item_page():
    return render_template('founditem.html')

@app.route('/about.html')
def about_page():
    return render_template('about.html')

@app.route('/contect.html')
def contact_page():
    return render_template('contect.html')


# MongoDB connection
client = MongoClient(os.getenv('MONGODB_URI'))
db = client[os.getenv('DB_NAME')]
users_collection = db.users
items_collection = db.items
contacts_collection = db.contacts

@app.route('/admindesbord.html')
def admin_dashboard():
    return render_template('admindesbord.html')

@app.route('/admin_contacts.html')
def admin_contacts_page():
    return render_template('admin_contacts.html')

@app.route('/adminprofile.html')
def admin_profile():
    return render_template('adminprofile.html')

@app.route('/adminsetting.html')
def admin_setting_page():
    return render_template('adminsetting.html')

@app.route('/changepassadmin.html')
def change_pass_admin():
    return render_template('changepassadmin.html')

@app.route('/faq.html')
def faq_page():
    return render_template('faq.html')


@app.route('/userprofile.html')
def user_profile():
    return render_template('userprofile.html')

@app.route('/reportfound_admin.html')
def report_found_admin_page():
    return render_template('reportfound_admin.html')

@app.route('/reportlost_admin.html')
def report_lost_admin_page():
    return render_template('reportlost_admin.html')


# Create uploads directory if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Allowed file extensions for images
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# JWT token decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = users_collection.find_one({'_id': ObjectId(data['user_id'])})
            if not current_user:
                return jsonify({'message': 'User not found'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token is invalid'}), 401
        
        return f(current_user, *args, **kwargs)
    return decorated


# File Upload Routes

@app.route('/api/upload', methods=['POST'])
@token_required
def upload_file(current_user):
    try:
        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({'message': 'No file provided'}), 400
        
        file = request.files['file']
        
        # Check if file is selected
        if file.filename == '':
            return jsonify({'message': 'No file selected'}), 400
        
        # Check if file type is allowed
        if not allowed_file(file.filename):
            return jsonify({'message': 'File type not allowed. Only PNG, JPG, JPEG, GIF are supported'}), 400
        
        # Generate unique filename
        filename = secure_filename(file.filename)
        file_extension = filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        
        # Save file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        # Return file info
        return jsonify({
            'message': 'File uploaded successfully',
            'filename': unique_filename,
            'file_path': f'/uploads/{unique_filename}',
            'original_filename': filename
        }), 201
        
    except Exception as e:
        return jsonify({'message': 'File upload failed', 'error': str(e)}), 500

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except Exception as e:
        return jsonify({'message': 'File not found', 'error': str(e)}), 404

# User Authentication Routes

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['fullname', 'email', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'message': f'{field} is required'}), 400
        
        username = data['fullname'].strip()
        email = data['email'].strip().lower()
        password = data['password']
        
        # Check if user already exists
        if users_collection.find_one({'$or': [{'username': username}, {'email': email}]}):
            return jsonify({'message': 'Username or email already exists'}), 409
        
        # Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        # Create user document
        user_doc = {
            'username': username,
            'email': email,
            'role': 'user',
            'status': 'active',   # 🔥 ADD THIS
            'profile': {
                'full_name': data.get('full_name', ''),
                'phone': data.get('phone', ''),
                'created_at': datetime.utcnow()
            },
        }
       
        # Insert user
        result = users_collection.insert_one(user_doc)
        
        return jsonify({
            'message': 'User registered successfully',
            'user_id': str(result.inserted_id)
        }), 201
        
    except Exception as e:
        return jsonify({'message': 'Registration failed', 'error': str(e)}), 500



@app.route('/api/logout', methods=['POST'])
@token_required
def logout(current_user):
    # In a stateless JWT system, logout is handled client-side by removing the token
    return jsonify({'message': 'Logout successful'}), 200

@app.route('/api/edit-profile', methods=['PUT'])
@token_required
def edit_profile(current_user):
    try:
        data = request.get_json()
        
        # Prepare update data
        update_data = {}
        
        # Update basic info if provided
        if 'email' in data:
            email = data['email'].strip().lower()
            # Check if email is already taken by another user
            existing_user = users_collection.find_one({
                'email': email,
                '_id': {'$ne': current_user['_id']}
            })
            if existing_user:
                return jsonify({'message': 'Email already exists'}), 409
            update_data['email'] = email
        
        # Update profile fields
        profile_updates = {}
        profile_fields = ['full_name', 'phone']
        for field in profile_fields:
            if field in data:
                profile_updates[f'profile.{field}'] = data[field].strip()
        
        if profile_updates:
            update_data.update(profile_updates)
        
        # Update password if provided
        if 'password' in data and data['password']:
            hashed_password = bcrypt.hashpw(data['password'].encode('utf-8'), bcrypt.gensalt())
            update_data['password'] = hashed_password
        
        if not update_data:
            return jsonify({'message': 'No valid fields to update'}), 400
        
        # Update user
        update_data['profile.updated_at'] = datetime.utcnow()
        users_collection.update_one(
            {'_id': current_user['_id']},
            {'$set': update_data}
        )
        
        # Get updated user
        updated_user = users_collection.find_one({'_id': current_user['_id']})
        
        return jsonify({
            'message': 'Profile updated successfully',
            'user': {
                'id': str(updated_user['_id']),
                'username': updated_user['username'],
                'email': updated_user['email'],
                'role': updated_user['role'],
                'profile': updated_user.get('profile', {})
            }
        }), 200
        
    except Exception as e:
        return jsonify({'message': 'Profile update failed', 'error': str(e)}), 500

@app.route('/api/user/items', methods=['GET'])
@token_required
def get_user_items(current_user):
    try:
        # Get all items submitted by the current user
        user_items = list(items_collection.find({'user_id': str(current_user['_id'])}))
        
        # Convert ObjectId to string for JSON serialization
        for item in user_items:
            item['_id'] = str(item['_id'])
        
        return jsonify({
            'message': 'User items retrieved successfully',
            'items': user_items
        }), 200
        
    except Exception as e:
        return jsonify({'message': 'Failed to retrieve user items', 'error': str(e)}), 500

# Lost & Found Item Routes (Updated with file upload support)
def save_file(field_name):
    if field_name in request.files:
        file = request.files[field_name]
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            ext = filename.rsplit('.', 1)[1].lower()
            unique = f"{uuid.uuid4().hex}.{ext}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique))
            return f"/uploads/{unique}"
    return ""

@app.route('/api/lost', methods=['POST'])
@token_required
def submit_lost_item(current_user):
    try:
        # Handle both JSON and form data (for file uploads)
        if request.content_type and 'multipart/form-data' in request.content_type:
            # Form data with file upload
            data = request.form.to_dict()
            
        item_image = save_file("image")
        id_card_image = save_file("id_card")
        aadhaar_image = save_file("aadhaar_card")
        
        # Validate required fields
        required_fields = ['title', 'description', 'location', 'category']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'message': f'{field} is required'}), 400
        
        item_doc = {
            'title': data['title'].strip(),
            'description': data['description'].strip(),
            'location': data['location'].strip(),
            'date': data.get('date', datetime.utcnow().isoformat()),
            'category': data['category'].strip(),
            'type': 'lost',
            'status': 'pending',
            'user_id': str(current_user['_id']),
            # 🔥 NEW FIELDS
            'phone': data.get('phone'),
            'image': item_image,
            'id_card_image': id_card_image,
            'aadhaar_image': aadhaar_image,

            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }

        
        # Insert item
        result = items_collection.insert_one(item_doc)
        
        return jsonify({
            'message': 'Lost item submitted successfully',
            'item_id': str(result.inserted_id),
            'status': 'pending'
        }), 201
        
    except Exception as e:
        return jsonify({'message': 'Failed to submit lost item', 'error': str(e)}), 500

@app.route('/api/found', methods=['POST'])
@token_required
def submit_found_item(current_user):
    try:
        # 🔹 Handle multipart form
        if request.content_type and 'multipart/form-data' in request.content_type:
            data = request.form.to_dict()

            print("FOUND FORM DATA:", data)

            item_image = save_file("image")
            id_card_image = save_file("id_card")
            aadhaar_image = save_file("aadhaar_card")

        else:
            data = request.get_json() or {}
            item_image = data.get("image", "")
            id_card_image = ""
            aadhaar_image = ""

        # 🔹 Validate required fields
        required_fields = ['title', 'description', 'location', 'category']
        for field in required_fields:
            if field not in data or not str(data[field]).strip():
                return jsonify({'message': f'{field} is required'}), 400

        # 🔹 Create document
        item_doc = {
            'title': data['title'].strip(),
            'description': data['description'].strip(),
            'location': data['location'].strip(),
            'date': datetime.utcnow().isoformat(),
            'category': data['category'].strip(),
            'type': 'found',
            'status': 'pending',
            'user_id': str(current_user['_id']),

            # 🔥 EXTRA DETAILS
            'phone': data.get('phone'),
            'image': item_image,
            'id_card_image': id_card_image,
            'aadhaar_image': aadhaar_image,

            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }

        items_collection.insert_one(item_doc)

        return jsonify({
            'message': 'Found item submitted successfully',
            'status': 'pending'
        }), 201

    except Exception as e:
        print("FOUND ITEM ERROR:", e)
        return jsonify({'message': 'Failed to submit found item'}), 500


@app.route('/api/items', methods=['GET'])
def get_all_items():
    try:
        # Get query parameters for filtering
        item_type = request.args.get('type')  # lost/found
        category = request.args.get('category')
        search = request.args.get('search')
        
        # Build query - only show approved items to public
        query = {'status': 'approved'}
        
        if item_type:
            query['type'] = item_type
        
        if category:
            query['category'] = category
        
        if search:
            query['$or'] = [
                {'title': {'$regex': search, '$options': 'i'}},
                {'description': {'$regex': search, '$options': 'i'}},
                {'location': {'$regex': search, '$options': 'i'}}
            ]
        
        # Get items sorted by creation date (newest first)
        items = list(items_collection.find(query).sort('created_at', -1))
        
        # Convert ObjectId to string and add user info
        for item in items:
            item['_id'] = str(item['_id'])
            # Get user info for the item
            user = users_collection.find_one({'_id': ObjectId(item['user_id'])})
            if user:
                item['user_info'] = {
                    'username': user['username'],
                    'email': user['email']
                }
        
        return jsonify({
            'message': 'Items retrieved successfully',
            'items': items,
            'count': len(items)
        }), 200
        
    except Exception as e:
        return jsonify({'message': 'Failed to retrieve items', 'error': str(e)}), 500

@app.route('/api/item/<item_id>', methods=['GET'])
def get_single_item(item_id):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(item_id):
            return jsonify({'message': 'Invalid item ID'}), 400
        
        # Get item
        item = items_collection.find_one({'_id': ObjectId(item_id)})
        
        if not item:
            return jsonify({'message': 'Item not found'}), 404
        
        # Convert ObjectId to string
        item['_id'] = str(item['_id'])
        
        # Get user info
        user = users_collection.find_one({'_id': ObjectId(item['user_id'])})
        if user:
            item['user_info'] = {
                'username': user['username'],
                'email': user['email'],
                'profile': user.get('profile', {})
            }
        
        return jsonify({
            'message': 'Item retrieved successfully',
            'item': item
        }), 200
        
    except Exception as e:
        return jsonify({'message': 'Failed to retrieve item', 'error': str(e)}), 500

@app.route('/api/item/<item_id>', methods=['PUT'])
@token_required
def update_item(current_user, item_id):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(item_id):
            return jsonify({'message': 'Invalid item ID'}), 400
        
        # Get item
        item = items_collection.find_one({'_id': ObjectId(item_id)})
        
        if not item:
            return jsonify({'message': 'Item not found'}), 404
        
        # Check if user owns the item or is admin
        if str(item['user_id']) != str(current_user['_id']) and current_user.get('role') != 'admin':
            return jsonify({'message': 'Unauthorized to update this item'}), 403
        
        data = request.get_json()
        
        # Prepare update data
        update_data = {}
        updatable_fields = ['title', 'description', 'location', 'date', 'category', 'image']
        
        for field in updatable_fields:
            if field in data:
                update_data[field] = data[field].strip() if isinstance(data[field], str) else data[field]
        
        if not update_data:
            return jsonify({'message': 'No valid fields to update'}), 400
        
        update_data['updated_at'] = datetime.utcnow()
        
        # Update item
        items_collection.update_one(
            {'_id': ObjectId(item_id)},
            {'$set': update_data}
        )
        
        return jsonify({'message': 'Item updated successfully'}), 200
        
    except Exception as e:
        return jsonify({'message': 'Failed to update item', 'error': str(e)}), 500

@app.route('/api/item/<item_id>', methods=['DELETE'])
@token_required
def delete_item(current_user, item_id):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(item_id):
            return jsonify({'message': 'Invalid item ID'}), 400
        
        # Get item
        item = items_collection.find_one({'_id': ObjectId(item_id)})
        
        if not item:
            return jsonify({'message': 'Item not found'}), 404
        
        # Check if user owns the item or is admin
        if str(item['user_id']) != str(current_user['_id']) and current_user.get('role') != 'admin':
            return jsonify({'message': 'Unauthorized to delete this item'}), 403
        
        # Delete associated image file if exists
        if item.get('image') and item['image'].startswith('/uploads/'):
            image_filename = item['image'].replace('/uploads/', '')
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
            if os.path.exists(image_path):
                os.remove(image_path)
        
        # Delete item
        items_collection.delete_one({'_id': ObjectId(item_id)})
        
        return jsonify({'message': 'Item deleted successfully'}), 200
        
    except Exception as e:
        return jsonify({'message': 'Failed to delete item', 'error': str(e)}), 500

# Admin Routes

@app.route('/api/admin/items', methods=['GET'])
@admin_required
def get_all_admin_items(current_user):
    try:
        # Get query parameters for filtering
        status = request.args.get('status')  # pending/approved/rejected
        item_type = request.args.get('type')  # lost/found
        
        # Build query
        query = {}
        
        if status:
            query['status'] = status
        
        if item_type:
            query['type'] = item_type
        
        # Get all items (including pending ones) sorted by creation date
        items = list(items_collection.find(query).sort('created_at', -1))
        
        # Convert ObjectId to string and add user info
        for item in items:
            item['_id'] = str(item['_id'])
            # Get user info for the item
            user = users_collection.find_one({'_id': ObjectId(item['user_id'])})
            if user:
                item['user_info'] = {
                    'username': user['username'],
                    'email': user['email'],
                    'profile': user.get('profile', {})
                }
        
        return jsonify({
            'message': 'Admin items retrieved successfully',
            'items': items,
            'count': len(items)
        }), 200
        
    except Exception as e:
        return jsonify({'message': 'Failed to retrieve admin items', 'error': str(e)}), 500

@app.route('/api/admin/approve/<item_id>', methods=['PUT'])
@admin_required
def approve_reject_item(current_user, item_id):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(item_id):
            return jsonify({'message': 'Invalid item ID'}), 400
        
        data = request.get_json()
        action = data.get('action')  # 'approve' or 'reject'
        admin_notes = data.get('admin_notes', '')
        
        if action not in ['approve', 'reject']:
            return jsonify({'message': 'Action must be either "approve" or "reject"'}), 400
        
        # Get item
        item = items_collection.find_one({'_id': ObjectId(item_id)})
        
        if not item:
            return jsonify({'message': 'Item not found'}), 404
        
        # Update item status
        new_status = 'approved' if action == 'approve' else 'rejected'
        
        update_data = {
            'status': new_status,
            'admin_notes': admin_notes,
            'reviewed_by': str(current_user['_id']),
            'reviewed_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        items_collection.update_one(
            {'_id': ObjectId(item_id)},
            {'$set': update_data}
        )
        
        return jsonify({
            'message': f'Item {action}d successfully',
            'item_id': item_id,
            'new_status': new_status
        }), 200
        
    except Exception as e:
        return jsonify({'message': f'Failed to {action} item', 'error': str(e)}), 500
    
    
@app.route('/admin_users.html')
def admin_users_page():
    return render_template('admin_users.html')

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def get_all_users(current_user):
    users = list(users_collection.find())

    for user in users:
        user['_id'] = str(user['_id'])

        # Count items posted by this user
        item_count = items_collection.count_documents({
            'user_id': user['_id']
        })
        user['item_count'] = item_count

    return jsonify({'users': users}), 200

@app.route('/api/admin/user/status/<user_id>', methods=['PUT'])
@admin_required
def update_user_status(current_user, user_id):
    if not ObjectId.is_valid(user_id):
        return jsonify({"message": "Invalid user ID"}), 400

    data = request.get_json()
    status = data.get("status")

    if status not in ["active", "disabled"]:
        return jsonify({"message": "Invalid status"}), 400

    users_collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"status": status}}
    )

    return jsonify({"message": "User status updated"})

@app.route('/api/admin/user/<user_id>', methods=['PUT'])
@admin_required
def update_user_role(current_user, user_id):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(user_id):
            return jsonify({'message': 'Invalid user ID'}), 400
        
        data = request.get_json()
        new_role = data.get('role')
        
        if new_role not in ['user', 'admin']:
            return jsonify({'message': 'Role must be either "user" or "admin"'}), 400
        
        # Prevent admin from demoting themselves
        if str(current_user['_id']) == user_id and new_role != 'admin':
            return jsonify({'message': 'Cannot change your own admin role'}), 400
        
        # Get user
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        # Update user role
        users_collection.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {
                'role': new_role,
                'profile.updated_at': datetime.utcnow()
            }}
        )
        
        return jsonify({
            'message': f'User role updated to {new_role} successfully',
            'user_id': user_id,
            'new_role': new_role
        }), 200
        
    except Exception as e:
        return jsonify({'message': 'Failed to update user role', 'error': str(e)}), 500

@app.route('/api/admin/user/<user_id>', methods=['DELETE'])
@admin_required
def delete_user(current_user, user_id):
    try:
        # Validate ObjectId
        if not ObjectId.is_valid(user_id):
            return jsonify({'message': 'Invalid user ID'}), 400
        
        # Prevent admin from deleting themselves
        if str(current_user['_id']) == user_id:
            return jsonify({'message': 'Cannot delete your own account'}), 400
        
        # Get user
        user = users_collection.find_one({'_id': ObjectId(user_id)})
        
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        # Delete user's items and associated images
        user_items = items_collection.find({'user_id': user_id})
        for item in user_items:
            if item.get('image') and item['image'].startswith('/uploads/'):
                image_filename = item['image'].replace('/uploads/', '')
                image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
                if os.path.exists(image_path):
                    os.remove(image_path)
        
        # Delete user's items
        items_collection.delete_many({'user_id': user_id})
        
        # Delete user
        users_collection.delete_one({'_id': ObjectId(user_id)})
        
        return jsonify({
            'message': 'User and associated items deleted successfully',
            'user_id': user_id
        }), 200
        
    except Exception as e:
        return jsonify({'message': 'Failed to delete user', 'error': str(e)}), 500
    
@app.route("/api/admin/contacts", methods=["GET"])
@admin_required
def admin_get_contacts(current_user):
    messages = list(
        contacts_collection.find().sort("created_at", -1)
    )

    for msg in messages:
        msg["_id"] = str(msg["_id"])

    return jsonify({
        "messages": messages
    })

@app.route("/api/admin/contacts/<contact_id>/read", methods=["PUT"])
@admin_required
def admin_mark_contact_read(current_user, contact_id):
    contacts_collection.update_one(
        {"_id": ObjectId(contact_id)},
        {"$set": {"status": "read"}}
    )

    return jsonify({"message": "Marked as read"})

@app.route('/admin_items.html')
def admin_items_page():
    return render_template('admin_items.html')

@app.route('/api/admin/stats', methods=['GET'])
@admin_required
def get_admin_stats(current_user):
    try:
        # Get various statistics
        total_users = users_collection.count_documents({})
        total_items = items_collection.count_documents({})
        new_messages = contacts_collection.count_documents({"status": "new"})
        pending_items = items_collection.count_documents({'status': 'pending'})
        approved_items = items_collection.count_documents({'status': 'approved'})
        rejected_items = items_collection.count_documents({'status': 'rejected'})
        lost_items = items_collection.count_documents({'type': 'lost', 'status': 'approved'})
        found_items = items_collection.count_documents({'type': 'found', 'status': 'approved'})
        
        # Get recent activity (last 10 items)
        recent_items = list(items_collection.find({}).sort('created_at', -1).limit(10))
        for item in recent_items:
            item['_id'] = str(item['_id'])
            # Get user info
            user = users_collection.find_one({'_id': ObjectId(item['user_id'])})
            if user:
                item['user_info'] = {'username': user['username']}
        
        stats = {
            'total_users': total_users,
            'total_items': total_items,
            'pending_items': pending_items,
            'approved_items': approved_items,
            'rejected_items': rejected_items,
            'lost_items': lost_items,
            'found_items': found_items,
            'new_messages': new_messages,
            'recent_items': recent_items
        }
        
        return jsonify({
            'message': 'Admin statistics retrieved successfully',
            'stats': stats
        }), 200
        
    except Exception as e:
        return jsonify({'message': 'Failed to retrieve admin statistics', 'error': str(e)}), 500
import os

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)