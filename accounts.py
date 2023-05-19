import firebaseDB


def login(username, password):
    user = firebaseDB.getUser(username)
    if user is None:
        return False
    else:
        if 'password' not in user:
            return "legacy"
        return user['password'] == password


def register(username, password, email):
    return firebaseDB.register(username, password, email)


