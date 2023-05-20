import firebase_admin
from firebase_admin import credentials
from firebase_admin import auth
from firebase_admin import firestore


def init():
    
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    if not globals().get("db"):
        globals()["db"] = firestore.client()



def get_leaderboard():
    init()
    leaderboard = []
    for user in db.collection("users").order_by("score", direction=firestore.Query.DESCENDING).stream():
        if user.to_dict()["username"]:
            display_name = user.to_dict()["username"]
        else:
            display_name = user.to_dict()["email"].split("@")[0]
            
        leaderboard.append({"username": display_name, "score": user.to_dict()["score"]})
        
    return leaderboard



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


def getUsers():
    """Get all users from the database"""
    db = getDB()
    users = []
    for user in db.collection('users').get():
        users.append(user.to_dict())
    return users


def getDB():
    init()
    return globals()["db"]

def getScore(username_or_email):
    document = getDocumentFor(username_or_email)
    if document:
        return document.get().to_dict()['score']
    return None


def setScore(username_or_email, score,overwrite=False):
    document = getDocumentFor(username_or_email)
    if document:
        if overwrite:
            document.update({"score": score})
        else:
            document.update({"score": firestore.Increment(score)}) 
        return True
    return False


def add_user_to_db(email):
    db = getDB()
    users = getUsers()
    for user in users:
        if user['email'] == email:
            return False
    db.collection('users').add({'email': email, 'score': 0})
    return True