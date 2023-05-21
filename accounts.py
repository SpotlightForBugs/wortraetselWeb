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



def sign_in_with_email_and_password(email: str, password: str, return_secure_token: bool = True):
    payload = json.dumps({
        "email": email,
        "password": password,
        "returnSecureToken": return_secure_token
    })

    r = requests.post(rest_api_url,
                      params={"key": WEB_API},
                      data=payload)

    return r.json()


def login(email, password):
    sign_in = sign_in_with_email_and_password(email, password)
    if "error" in sign_in:
        return False
    for key, value in sign_in.items():
        if key == "email":
            return value
    
    
    
def register(email, password, username):
    try:
        user = auth.create_user(email=email, password=password)
        return user.uid
        firebaseDB.add_user_to_db(email,username)
    except auth.EmailAlreadyExistsError:
        print("Email already exists")
        return login(email, password)


def getUsername(email):
    
    # we return the displayname of the user if it exists, otherwise we return the email without the domain
    auth_user = auth.get_user_by_email(email)
    if auth_user.display_name:
        return {"username": auth_user.display_name}
    return {"username": email.split("@")[0]}