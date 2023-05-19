"""Cloud Firestore Database"""
import os
from typing import Any

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

globals()['db'] = None


def init():
    if globals()['db'] is None:
        """Initialize connection to the database"""
        if not os.path.exists(os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json')):
            with open(os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json'), 'w') as f:
                f.write(os.environ['GOOGLE_APPLICATION_CREDENTIALS'])
        cred = credentials.Certificate(os.path.join(os.path.dirname(__file__), 'serviceAccountKey.json'))
        firebase_admin.initialize_app(cred)
        globals()['db'] = firestore.client()
        # check if the database is connected
        if globals()['db'] is not None:
            print("Database connected")
        else:
            print("Database not connected, please check your credentials")
    else:
        print("Database already connected")


def getDB():
    """Get the database"""
    if globals()['db'] is None:
        init()
    return globals()['db']


def getUsers():
    """Get all users from the database"""
    db = getDB()
    users = []
    for user in db.collection('users').get():
        users.append(user.to_dict())
    return users


def get_leaderboard():
    users = getUsers()  # Assuming you have a function named getUsers() that returns the user data

    # Create the leaderboard with username and score
    leaderboard: list[dict[str, Any]] = []
    for user in users:
        email = user['email']
        if 'username' in user and user['username'] != '':
            username = user['username']
        else:
            username = email.split('@')[0]
        leaderboard.append({'username': username, 'score': user['score']})

    # Sort the leaderboard based on the scores in descending order
    leaderboard = sorted(leaderboard, key=lambda x: x['score'], reverse=True)

    # set negative scores to 0
    for user in leaderboard:
        if user['score'] < 0:
            user['score'] = 0

    return leaderboard


def register(username, password, email):
    db = getDB()
    users = getUsers()
    for user in users:
        if user['username'] == username:
            return False
    db.collection('users').add({'username': username, 'password': password, 'email': email, 'score': 0})
    return True


def getUser(username) -> str | None:
    # the username can be the username or the email.
    # There might be no username field, but there will always be an email field
    users = getUsers()
    for user in users:
        if user['username'] == username:
            return user
        elif user['email'] == username:
            # check if the user has a username field in the database and it is not empty
            if 'username' in user and user['username'] != '':
                return user
            else:
                # edit the user's username field to be the email without the @ and the domain
                db = getDB()
                db.collection('users').document(user['email']).update({'username': user['email'].split('@')[0]})
                return getUser(username)
    return None


def getDocumentFor(username_or_email):
    db = getDB()
    users = getUsers()
    for user in users:
        if user['username'] == username_or_email or user['email'] == username_or_email:
            for document in db.collection('users').get():
                if document.to_dict()['username'] == user['username']:
                    return document.reference

    return None


def getDocumentDFor(username_or_email):
    db = getDB()
    users = getUsers()
    for user in users:
        if user['username'] == username_or_email or user['email'] == username_or_email:
            for document in db.collection('users').get():
                if document.to_dict()['username'] == user['username']:
                    return document

    return None


def add_points(username, points):
    getDB()
    user = getUser(username)
    if user is None:
        return False
    else:
        document = getDocumentDFor(username)
        if document.to_dict()['score'] + points < 0:
            document = getDocumentFor(username)
            document.update({'score': 0})

        document = getDocumentFor(username)
        document.update({'score': user['score'] + points})
        return True
