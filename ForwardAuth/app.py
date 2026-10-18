import hashlib
import json
import os
import sys
from hashlib import pbkdf2_hmac
from time import time

import jwt
from flask import Flask, Response, request
from pymongo import MongoClient

# The gateway copies this header from the /auth response onto the request it forwards
# to avalon-spring, which trusts it as the caller's identity.
USERNAME_HEADER = "Avalon-Header-Logged-In-User-Username"

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    sys.exit("JWT_SECRET is not set: refusing to start without a token signing key.")

app = Flask(__name__)


def get_database():
    connection_string = os.getenv("CONNECTION_STRING")
    client = MongoClient(connection_string)
    return client['Archimedes-Rest']


db = get_database()


def get_user(username):
    return db.users.find_one({"username": username})


def json_message(message, status):
    return Response(json.dumps({"message": message}), status=status, mimetype="application/json")


@app.route('/')
def hello():
    return "im running :)"


@app.route('/auth')
def auth():
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return json_message("no token or wrong token", 401)

    try:
        data = jwt.decode(jwt=header[len("Bearer "):], key=JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return json_message("no token or wrong token", 401)

    expire = data.get("expire")
    username = data.get("username")
    if not isinstance(expire, (int, float)) or not isinstance(username, str):
        return json_message("no token or wrong token", 401)
    if expire < time():
        return json_message("token expired", 401)

    return Response(status=200, headers={USERNAME_HEADER: username})


@app.route('/login', methods=["POST"])
def login():
    request_data = request.get_json()
    username = request_data["username"]
    password = request_data["password"]
    user = get_user(username)
    if user is None:
        return json_message("No User found with this username!", 404)

    if hashlib.pbkdf2_hmac('sha256', password=bytes(password, 'utf-8'), salt=user['salt'], iterations=1000) != user["password"]:
        return json_message("Wrong password!", 403)

    data = {
        "username": username,
        "expire": time() + 60*60*24
    }
    token = jwt.encode(data, JWT_SECRET, algorithm="HS256")
    return {"username": username, "token": token}


@app.route('/register', methods=["POST"])
def register():
    request_data = request.get_json()
    username = request_data["username"]
    password = request_data["password"]
    email = request_data.get("email")
    friends = request_data.get("friends")

    if email is None:
        email = ""

    if friends is None:
        friends = []

    if get_user(username) is not None:
        return json_message("Username already in use!", 409)
    salt = os.urandom(16)
    user = {
        "username": username,
        "password": pbkdf2_hmac('sha256', password=bytes(password, 'utf-8'), salt=salt, iterations=1000),
        "salt": salt,
        "email": email,
        "friends": friends
    }

    db.users.insert_one(user)
    return Response(status=200)


if __name__ == '__main__':
    app.run()
