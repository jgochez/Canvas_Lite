from flask import Flask, request, jsonify, send_file, send_from_directory
from google.cloud import datastore, storage
import requests
import json
import certifi
import ssl
import base64
from six.moves.urllib.request import urlopen
from jose import jwt
import io
import os

app = Flask(__name__)
app.secret_key = 'SECRET_KEY'

# Get from Auth0 webpage
CLIENT_ID = 'B0HoszOAMV7RArFRTf2V8zR4dL05pYOm'
CLIENT_SECRET = '_BFck1nhZo3nBmWrJBvV_vZ_9kyOOsRD0h8kZ17_sMd_E5ziQ4ajnT35uFYB59JK'
DOMAIN = 'portfolio-gochezjo.us.auth0.com'
AUDIENCE = 'https://portfolio-gochezjo.us.auth0.com/api/v2/' 
ALGORITHMS = ["RS256"]

datastore_client = datastore.Client()
storage_client = storage.Client()
bucket_name = 'portfolio_management_tool_gochezjo'  

# Class for error
class AuthError(Exception):
    def __init__(self, error, status_code):
        self.error = error
        self.status_code = status_code

# Handle auth error
@app.errorhandler(AuthError)
def handle_auth_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response

# Get sub from token
def get_sub(jwt_token):
    try:
        base64_url = jwt_token.split('.')[1]
        padding = '=' * (4 - len(base64_url) % 4)
        base64_url += padding
        json_payload = base64.urlsafe_b64decode(base64_url)
        payload = json.loads(json_payload)
        return payload['sub']
    except Exception as e:
        raise ValueError("Invalid JWT token") from e
    
# Verify JWT for authentication
def verify_jwt(request):
    if 'Authorization' in request.headers:
        auth_header = request.headers['Authorization'].split()
        if len(auth_header) < 2:
            raise AuthError({"code": "invalid_header", "description": "Token not found"}, 401)
        token = auth_header[1]
    else:
        raise AuthError({"code": "no_auth_header",
                         "description": "Authorization header is missing"}, 401)
    
    context = ssl.create_default_context(cafile=certifi.where()) # Required for my machine
    jsonurl = urlopen("https://" + DOMAIN + "/.well-known/jwks.json", context=context)
    jwks = json.loads(jsonurl.read())
    try:
        unverified_header = jwt.get_unverified_header(token)
    except jwt.JWTError:
        raise AuthError({"code": "invalid_header",
                         "description": "Invalid header. Use an RS256 signed JWT Access Token"}, 401)
    if unverified_header["alg"] == "HS256":
        raise AuthError({"code": "invalid_header",
                         "description": "Invalid header. Use an RS256 signed JWT Access Token"}, 401)
    rsa_key = {}
    for key in jwks["keys"]:
        if key["kid"] == unverified_header["kid"]:
            rsa_key = {
                "kty": key["kty"],
                "kid": key["kid"],
                "use": key["use"],
                "n": key["n"],
                "e": key["e"]
            }
    if rsa_key:
        try:
            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=ALGORITHMS,
                audience=AUDIENCE,
                issuer="https://" + DOMAIN + "/"
            )
        except jwt.ExpiredSignatureError:
            raise AuthError({"code": "token_expired",
                             "description": "Token is expired"}, 401)
        except jwt.JWTClaimsError:
            raise AuthError({"code": "invalid_claims",
                             "description": "Incorrect claims, please check the audience and issuer"}, 401)
        except Exception:
            raise AuthError({"code": "invalid_header",
                             "description": "Unable to parse authentication token"}, 401)

        return payload
    else:
        raise AuthError({"code": "no_rsa_key",
                         "description": "No RSA key in JWKS"}, 401)

# Serve the HTML file for the front end
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

# Serve static files (CSS, JS)
@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

# Generate a JWT for a registered user
@app.route('/users/login', methods=['POST'])
def login_user():
    content = request.get_json() 

    if not content or 'username' not in content or 'password' not in content:
        return jsonify({"Error": "The request body is invalid"}), 400

    username = content["username"]
    password = content["password"]

    body = {
        'grant_type': 'password',
        'username': username,
        'password': password,
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'audience': AUDIENCE  
    }
    headers = {'Content-Type': 'application/json'}
    url = f'https://{DOMAIN}/oauth/token'
    response = requests.post(url, json=body, headers=headers)

    if response.status_code == 200: 
        token = response.json().get('access_token')
        return jsonify({"token": token}), 200
    else:
        return jsonify({"Error": "Unauthorized"}), 401

# Get all users
@app.route('/users', methods=['GET'])
def get_all_users():
    try:
        payload = verify_jwt(request)
        
    except AuthError as e:
        return jsonify({"Error": "Unauthorized"}), 401
    ########################################################
    # if payload.get('role') != 'admin':
    #     return jsonify({"Error": "You don't have permission on this resource"}), 403

    query = datastore_client.query(kind='users')
    results = list(query.fetch())
    
    users = []
    for entity in results:
        body = {
            'id': entity.id,
            'role': entity.get('role'),
            'sub': entity.get('sub')
        }
        users.append(body)
    
    return jsonify(users), 200

# Get a user
@app.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    try:
        payload = verify_jwt(request)
    except AuthError as e:
        return jsonify({"Error": "Unauthorized"}), 401

    key = datastore_client.key('users', int(user_id))
    entity = datastore_client.get(key)

    if not entity:
        return jsonify({"Error": "Not found"}), 404

    user = {
        'id': entity.id,
        'role': entity.get('role'),
        'sub': entity.get('sub')
    }

    if 'avatar_url' in entity:
        user['avatar_url'] = entity['avatar_url']

    if user['role'] in ['instructor', 'student']:
        user['courses'] = entity.get('courses', [])

    return jsonify(user), 200

# Create/update a user's avatar
@app.route('/users/<user_id>/avatar', methods=['POST'])
def upload_avatar(user_id):
    try:
        payload = verify_jwt(request)
    except AuthError as e:
        return jsonify({"Error": "Unauthorized"}), 401

    if 'file' not in request.files:
        return jsonify({"Error": "The request body is invalid"}), 400

    file_obj = request.files['file']


    if not file_obj.filename.endswith('.png'):
        return jsonify({"Error": "The request body is invalid"}), 400

    # Upload the file to Google Cloud Storage
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f'avatars/{user_id}.png')
    file_obj.seek(0)
    blob.upload_from_file(file_obj, content_type='image/png')

    avatar_url = blob.public_url

    # Update the user's entity in Datastore
    key = datastore_client.key('users', int(user_id))
    entity = datastore_client.get(key)
    if not entity:
        return jsonify({"Error": "Not found"}), 404

    entity['avatar_url'] = avatar_url
    datastore_client.put(entity)

    return jsonify({"avatar_url": avatar_url}), 200

# Serve an avatar image
@app.route('/users/<user_id>/avatar', methods=['GET'])
def get_avatar(user_id):
    try:
        payload = verify_jwt(request)
    except AuthError as e:
        return jsonify({"Error": "Unauthorized"}), 401

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f'avatars/{user_id}.png')
    
    if not blob.exists():
        return jsonify({"Error": "Not found"}), 404

    file_obj = io.BytesIO()
    blob.download_to_file(file_obj)
    file_obj.seek(0)

    return send_file(file_obj, mimetype='image/png', download_name=f'{user_id}.png')

# Delete a user's avatar
@app.route('/users/<user_id>/avatar', methods=['DELETE'])
def delete_avatar(user_id):
    try:
        payload = verify_jwt(request)
    except AuthError as e:
        return jsonify({"Error": "Unauthorized"}), 401
    
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(f'avatars/{user_id}.png')
    
    if not blob.exists():
        return jsonify({"Error": "Not found"}), 404

    blob.delete()

    key = datastore_client.key('users', int(user_id))
    entity = datastore_client.get(key)
    if entity and 'avatar_url' in entity:
        del entity['avatar_url']
        datastore_client.put(entity)

    return '', 204

# Create a Course
@app.route('/courses', methods=['POST'])
def create_course():
    try:
        payload = verify_jwt(request)
    except AuthError as e:
        return jsonify({"Error": "Unauthorized"}), 401
    ########################################################
    # if payload.get('role') != 'admin':
    #     return jsonify({"Error": "You don't have permission on this resource"}), 403

    content = request.get_json()

    required_fields = ['subject', 'number', 'title', 'term', 'instructor_id']
    if not content or not all(field in content for field in required_fields):
        return jsonify({"Error": "The request body is invalid"}), 400

    subject = content['subject']
    number = content['number']
    title = content['title']
    term = content['term']
    instructor_id = content['instructor_id']

    key = datastore_client.key('users', int(instructor_id))
    instructor = datastore_client.get(key)
    if not instructor or instructor.get('role') != 'instructor':
        return jsonify({"Error": "The request body is invalid"}), 400

    course_key = datastore_client.key('courses')
    course = datastore.Entity(key=course_key)
    course.update({
        'subject': subject,
        'number': number,
        'title': title,
        'term': term,
        'instructor_id': instructor_id
    })

    datastore_client.put(course)

    course_id = course.key.id
    course_url = f"{request.host_url}courses/{course_id}"

    response = {
        'id': course_id,
        'subject': subject,
        'number': number,
        'title': title,
        'term': term,
        'instructor_id': instructor_id,
        'self': course_url
    }

    return jsonify(response), 201

# Get all courses with pagination
@app.route('/courses', methods=['GET'])
def get_all_courses():
    offset = request.args.get('offset', default=0, type=int)
    limit = request.args.get('limit', default=3, type=int)

    query = datastore_client.query(kind='courses')
    query.order = ['subject']
    results = list(query.fetch(offset=offset, limit=limit))
    
    courses = []
    for entity in results:
        courses.append({
            'id': entity.id,
            'subject': entity.get('subject'),
            'number': entity.get('number'),
            'title': entity.get('title'),
            'term': entity.get('term'),
            'instructor_id': entity.get('instructor_id'),
            'self': f"{request.host_url}courses/{entity.id}"
        })
    
    next_url = None
    if len(results) == limit:
        next_offset = offset + limit
        next_url = f"{request.host_url}courses?offset={next_offset}&limit={limit}"

    response = {
        'courses': courses
    }

    if next_url:
        response['next'] = next_url

    return jsonify(response), 200

# Get a course by ID
@app.route('/courses/<course_id>', methods=['GET'])
def get_course(course_id):
    key = datastore_client.key('courses', int(course_id))
    entity = datastore_client.get(key)

    if not entity:
        return jsonify({"Error": "Not found"}), 404

    course = {
        'id': entity.id,
        'subject': entity.get('subject'),
        'number': entity.get('number'),
        'title': entity.get('title'),
        'term': entity.get('term'),
        'instructor_id': entity.get('instructor_id'),
        'self': f"{request.host_url}courses/{entity.id}"
    }

    return jsonify(course), 200

# Update a course
@app.route('/courses/<course_id>', methods=['PATCH'])
def update_course(course_id):
    try:
        payload = verify_jwt(request)
    except AuthError as e:
        return jsonify({"Error": "Unauthorized"}), 401

    ########################################################
    # if payload.get('role') != 'admin':
    #     return jsonify({"Error": "You don't have permission on this resource"}), 403

    content = request.get_json()
    if not content:
        return jsonify({"Error": "The request body is invalid"}), 400

    key = datastore_client.key('courses', int(course_id))
    course = datastore_client.get(key)
    if not course:
        return jsonify({"Error": "Not found"}), 403

    if 'instructor_id' in content:
        instructor_key = datastore_client.key('users', int(content['instructor_id']))
        instructor = datastore_client.get(instructor_key)
        if not instructor or instructor.get('role') != 'instructor':
            return jsonify({"Error": "Instructor not found"}), 400

    # Update key-values
    updates = {}

    if 'subject' in content:
        updates['subject'] = content['subject']
    if 'number' in content:
        updates['number'] = content['number']
    if 'title' in content:
        updates['title'] = content['title']
    if 'term' in content:
        updates['term'] = content['term']
    if 'instructor_id' in content:
        updates['instructor_id'] = content['instructor_id']

    course.update(updates)
    datastore_client.put(course)

    course_url = f"{request.host_url}/courses/{course_id}"
    response = {
        'id': course.id,
        'subject': course.get('subject'),
        'number': course.get('number'),
        'title': course.get('title'),
        'term': course.get('term'),
        'instructor_id': course.get('instructor_id'),
        'self': course_url
    }

    return jsonify(response), 200

# Delete a course
@app.route('/courses/<course_id>', methods=['DELETE'])
def delete_course(course_id):
    try:
        payload = verify_jwt(request)
    except AuthError as e:
        return jsonify({"Error": "Unauthorized"}), 401

    ########################################################
    # if payload.get('role') != 'admin':
    #     return jsonify({"Error": "You don't have permission on this resource"}), 403

    key = datastore_client.key('courses', int(course_id))
    course = datastore_client.get(key)
    if not course:
        return jsonify({"Error": "Not found"}), 404

    datastore_client.delete(key)
    return '', 204

# Update enrollment in a course
@app.route('/courses/<course_id>/students', methods=['PATCH'])
def update_course_enrollment(course_id):
    try:
        payload = verify_jwt(request)
    except AuthError as e:
        return jsonify({"Error": "Unauthorized"}), 401

     ########################################################
    # if payload.get('role') != 'admin':
    #     return jsonify({"Error": "You don't have permission on this resource"}), 403
    key = datastore_client.key('courses', int(course_id))
    course = datastore_client.get(key)
    if not course:
        return jsonify({"Error": "Not found"}), 404

    ########################################################
    # if payload.get('sub') != course.get('instructor_id'):
    #     return jsonify({"Error": "You don't have permission on this resource"}), 403

    content = request.get_json()
    if not content or not ('add' in content or 'remove' in content):
        return jsonify({"Error": "The request body is invalid"}), 400

    add_students = content.get('add', [])
    remove_students = content.get('remove', [])

    if any(student_id in add_students for student_id in remove_students):
        return jsonify({"Error": "Enrollment data is invalid"}), 409

    existing_students = course.get('students', [])
    for student_id in add_students:
        student_key = datastore_client.key('users', int(student_id))
        student = datastore_client.get(student_key)
        if not student or student.get('role') != 'student':
            return jsonify({"Error": "Enrollment data is invalid"}), 409
        if student_id not in existing_students:
            existing_students.append(student_id)

    for student_id in remove_students:
        if student_id in existing_students:
            existing_students.remove(student_id)

    course['students'] = existing_students
    datastore_client.put(course)

    return '', 200

# Get enrollment for a course
@app.route('/courses/<course_id>/students', methods=['GET'])
def get_course_enrollment(course_id):
    try:
        payload = verify_jwt(request)
    except AuthError as e:
        return jsonify({"Error": "Unauthorized"}), 401

    key = datastore_client.key('courses', int(course_id))
    course = datastore_client.get(key)
    if not course:
        return jsonify({"Error": "Not found"}), 404

    ########################################################
    # if payload.get('role') != 'admin' and payload.get('sub') != course.get('instructor_id'):
    #     return jsonify({"Error": "You don't have permission on this resource"}), 403

    students = course.get('students', [])

    return jsonify(students), 200


if __name__ == '__main__':
    # newman run assignment6.postman_collection.json -e assignment6.postman_environment.json
    app.run(host='127.0.0.1', port=8000, debug=True)
