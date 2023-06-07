import firebase_admin
from firebase_admin import credentials
from firebase_admin import auth
import os, json, requests
from firebase_admin import firestore
import firebaseDB


WEB_API = os.environ.get("WEB_API")
rest_api_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"


# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)


def sign_in_with_email_and_password(
    email: str, password: str, return_secure_token: bool = True
):
    """
    The sign_in_with_email_and_password function takes in an email and password,
        then returns a JSON object containing the user's ID token, refresh token, local ID (UID),
        and other information. The function also verifies that the email address is valid.

    :param email: str: Specify the email address of the user to sign in
    :param password: str: Specify the password of the user
    :param return_secure_token: bool: Specify whether or not the user wants to receive a refresh token
    :return: A dictionary
    :doc-author: @Spotlightforbugs
    """
    payload = json.dumps(
        {"email": email, "password": password, "returnSecureToken": return_secure_token}
    )

    r = requests.post(rest_api_url, params={"key": WEB_API}, data=payload)

    return r.json()


def login(email, password):
    """
    The login function takes in an email and password, then signs the user in with those credentials.
    If there is an error signing the user in, it returns False. If not, it returns the email of the signed-in user.

    :param email: Check if the email is in the database
    :param password: Check if the password is correct
    :return: The email of the user if they are logged in
    :doc-author: @Spotlightforbugs
    """
    sign_in = sign_in_with_email_and_password(email, password)
    if "error" in sign_in:
        return False
    for key, value in sign_in.items():
        if key == "email":
            return value


def register(email, password, username):
    """
    The register function takes in an email, password, and username.
        It then creates a user with the given credentials and adds them to the database.
        If there is already a user with that email address it will log them in instead.

    :param email: Check if the user exists in the database
    :param password: Check if the password is correct
    :param username: Add the username to the database
    :return: The user's uid
    :doc-author: @Spotlightforbugs
    """
    try:
        user = auth.create_user(email=email, password=password, display_name=username)
        firebaseDB.add_user_to_db(email, username)
        return user.uid
    except auth.EmailAlreadyExistsError:
        print("Email already exists")
        return login(email, password)


def getUsername(email):
    """
    The getUsername function takes an email address as input and returns the display name of the user if it exists, otherwise it returns the email without the domain.

    :param email: Get the user's email address from the request object
    :return: The username of the user
    :doc-author: @Spotlightforbugs
    """

    # we return the displayname of the user if it exists, otherwise we return the email without the domain
    auth_user = auth.get_user_by_email(email)
    if auth_user.display_name:
        return {"username": auth_user.display_name, "legacy": False}

    db = firebaseDB.getDB()
    users_ref = db.collection("users")
    for doc in users_ref.stream():
        if doc.to_dict()["email"] == email:
            if doc.to_dict().get("username"):
                return {"username": doc.to_dict()["username"], "legacy": True}
    return {"username": email.split("@")[0]}


def is_legacy_user(email):  # checks if the user is a legacy user (has no username)
    """
    The is_legacy_user function checks if the user is a legacy user (has no username)

    :param email: Get the username of the user
    :return: A boolean value (true or false)
    :doc-author: @Spotlightforbugs
    """
    if getUsername(email)["legacy"]:
        return True


def is_legacy(username_or_email):
    return is_legacy_user(email=username_or_email)
