import game

_STRINGS = {
    "en": {
        "title": "Hangman",
        "guest": "Guest",
        "change_language": "Change language",
        "language_confirm": "Change the language? This word starts over.",
        "light_mode": "Light mode",
        "dark_mode": "Dark mode",
        "save_score": "Save your score",
        "log_in": "Log in",
        "log_out": "Log out",
        "unsaved_score": "Unsaved score: {n}",
        "no_score": "No score on the board yet",
        "score_line": "Score: {n}",
        "leaderboard": "Leaderboard",
        "username": "Username",
        "score_col": "Score",
        "hangman_alt": "Hangman",
        "win": "You solved it. The word was {word}.",
        "loss": "The drawing is finished. The word was {word}.",
        "worth": "This round is worth {n}. Create an account if you want it on the leaderboard.",
        "create_account": "Create an account",
        "not_now": "Not now",
        "next_word": "Next word",
        "email": "Email",
        "password": "Password",
        "name_label": "Name on the leaderboard",
        "confirm_password": "Confirm password",
        "have_account": "Already have an account?",
        "close": "Close",
        "cap_error": "Confirm you are a person, then try again.",
        "bad_login": "Invalid email or password",
        "session_expired": "Your session has expired. Did you change your password?",
        "email_exists": "Email already exists",
        "password_mismatch": "Those passwords do not match.",
        "save_my_score": "Save my score",
        "try_again": "Something went wrong. Try again.",
        "error_title": "Something went wrong",
        "error_body": "The error was reported. You can head back and try again.",
        "back_to_game": "Back to the game",
    },
    "de": {
        "title": "Galgenmännchen",
        "guest": "Gast",
        "change_language": "Sprache ändern",
        "language_confirm": "Sprache wechseln? Dieses Wort beginnt von vorn.",
        "light_mode": "Heller Modus",
        "dark_mode": "Dunkler Modus",
        "save_score": "Punktzahl speichern",
        "log_in": "Anmelden",
        "log_out": "Abmelden",
        "unsaved_score": "Ungespeicherte Punkte: {n}",
        "no_score": "Noch keine Punkte",
        "score_line": "Punkte: {n}",
        "leaderboard": "Bestenliste",
        "username": "Name",
        "score_col": "Punkte",
        "hangman_alt": "Galgenmännchen",
        "win": "Geschafft. Das Wort war {word}.",
        "loss": "Die Zeichnung ist fertig. Das Wort war {word}.",
        "worth": "Diese Runde ist {n} Punkte wert. Ein Konto setzt sie auf die Bestenliste.",
        "create_account": "Konto erstellen",
        "not_now": "Nicht jetzt",
        "next_word": "Nächstes Wort",
        "email": "E-Mail",
        "password": "Passwort",
        "name_label": "Name auf der Bestenliste",
        "confirm_password": "Passwort bestätigen",
        "have_account": "Schon ein Konto?",
        "close": "Schließen",
        "cap_error": "Bitte bestätige, dass du ein Mensch bist, und versuche es erneut.",
        "bad_login": "E-Mail oder Passwort ist falsch",
        "session_expired": "Die Sitzung ist abgelaufen. Hast du das Passwort geändert?",
        "email_exists": "Diese E-Mail gibt es schon",
        "password_mismatch": "Die Passwörter stimmen nicht überein.",
        "save_my_score": "Punktzahl speichern",
        "try_again": "Etwas ist schiefgelaufen. Versuch es erneut.",
        "error_title": "Etwas ist schiefgelaufen",
        "error_body": "Der Fehler wurde gemeldet. Du kannst zurückgehen und es erneut versuchen.",
        "back_to_game": "Zurück zum Spiel",
    },
    "es": {
        "title": "Ahorcado",
        "guest": "Invitado",
        "change_language": "Cambiar idioma",
        "language_confirm": "¿Cambiar el idioma? Esta palabra empieza de nuevo.",
        "light_mode": "Modo claro",
        "dark_mode": "Modo oscuro",
        "save_score": "Guardar la puntuación",
        "log_in": "Entrar",
        "log_out": "Salir",
        "unsaved_score": "Puntuación sin guardar: {n}",
        "no_score": "Todavía no hay puntuación",
        "score_line": "Puntuación: {n}",
        "leaderboard": "Clasificación",
        "username": "Nombre",
        "score_col": "Puntos",
        "hangman_alt": "Ahorcado",
        "win": "Lo has resuelto. La palabra era {word}.",
        "loss": "El dibujo está completo. La palabra era {word}.",
        "worth": "Esta ronda vale {n}. Crea una cuenta si quieres verla en la clasificación.",
        "create_account": "Crear una cuenta",
        "not_now": "Ahora no",
        "next_word": "Siguiente palabra",
        "email": "Correo",
        "password": "Contraseña",
        "name_label": "Nombre en la clasificación",
        "confirm_password": "Confirmar contraseña",
        "have_account": "¿Ya tienes una cuenta?",
        "close": "Cerrar",
        "cap_error": "Confirma que eres una persona y vuelve a intentarlo.",
        "bad_login": "Correo o contraseña incorrectos",
        "session_expired": "La sesión ha caducado. ¿Has cambiado la contraseña?",
        "email_exists": "Ese correo ya existe",
        "password_mismatch": "Las contraseñas no coinciden.",
        "save_my_score": "Guardar mi puntuación",
        "try_again": "Algo ha salido mal. Inténtalo de nuevo.",
        "error_title": "Algo ha salido mal",
        "error_body": "El error se ha informado. Puedes volver e intentarlo de nuevo.",
        "back_to_game": "Volver al juego",
    },
    "fr": {
        "title": "Pendu",
        "guest": "Invité",
        "change_language": "Changer de langue",
        "language_confirm": "Changer de langue ? Ce mot recommence.",
        "light_mode": "Mode clair",
        "dark_mode": "Mode sombre",
        "save_score": "Enregistrer le score",
        "log_in": "Se connecter",
        "log_out": "Se déconnecter",
        "unsaved_score": "Score non enregistré : {n}",
        "no_score": "Pas encore de score",
        "score_line": "Score : {n}",
        "leaderboard": "Classement",
        "username": "Nom",
        "score_col": "Score",
        "hangman_alt": "Pendu",
        "win": "Trouvé. Le mot était {word}.",
        "loss": "Le dessin est terminé. Le mot était {word}.",
        "worth": "Cette manche vaut {n}. Un compte la place au classement.",
        "create_account": "Créer un compte",
        "not_now": "Pas maintenant",
        "next_word": "Mot suivant",
        "email": "E-mail",
        "password": "Mot de passe",
        "name_label": "Nom au classement",
        "confirm_password": "Confirmer le mot de passe",
        "have_account": "Déjà un compte ?",
        "close": "Fermer",
        "cap_error": "Confirme que tu es une personne, puis réessaie.",
        "bad_login": "E-mail ou mot de passe incorrect",
        "session_expired": "La session a expiré. Le mot de passe a-t-il changé ?",
        "email_exists": "Cet e-mail existe déjà",
        "password_mismatch": "Les mots de passe ne correspondent pas.",
        "save_my_score": "Enregistrer mon score",
        "try_again": "Quelque chose s'est mal passé. Réessaie.",
        "error_title": "Quelque chose s'est mal passé",
        "error_body": "L'erreur a été signalée. Tu peux revenir et réessayer.",
        "back_to_game": "Retour au jeu",
    },
    "it": {
        "title": "Impiccato",
        "guest": "Ospite",
        "change_language": "Cambia lingua",
        "language_confirm": "Cambiare lingua? Questa parola ricomincia.",
        "light_mode": "Modalità chiara",
        "dark_mode": "Modalità scura",
        "save_score": "Salva il punteggio",
        "log_in": "Accedi",
        "log_out": "Esci",
        "unsaved_score": "Punteggio non salvato: {n}",
        "no_score": "Nessun punteggio ancora",
        "score_line": "Punteggio: {n}",
        "leaderboard": "Classifica",
        "username": "Nome",
        "score_col": "Punti",
        "hangman_alt": "Impiccato",
        "win": "Risolto. La parola era {word}.",
        "loss": "Il disegno è finito. La parola era {word}.",
        "worth": "Questo turno vale {n}. Un account lo mette in classifica.",
        "create_account": "Crea un account",
        "not_now": "Non ora",
        "next_word": "Parola successiva",
        "email": "Email",
        "password": "Password",
        "name_label": "Nome in classifica",
        "confirm_password": "Conferma password",
        "have_account": "Hai già un account?",
        "close": "Chiudi",
        "cap_error": "Conferma di essere una persona, poi riprova.",
        "bad_login": "Email o password non validi",
        "session_expired": "La sessione è scaduta. Hai cambiato la password?",
        "email_exists": "Questa email esiste già",
        "password_mismatch": "Le password non coincidono.",
        "save_my_score": "Salva il mio punteggio",
        "try_again": "Qualcosa è andato storto. Riprova.",
        "error_title": "Qualcosa è andato storto",
        "error_body": "L'errore è stato segnalato. Puoi tornare indietro e riprovare.",
        "back_to_game": "Torna al gioco",
    },
    "pt-br": {
        "title": "Forca",
        "guest": "Convidado",
        "change_language": "Mudar o idioma",
        "language_confirm": "Mudar o idioma? Esta palavra recomeça.",
        "light_mode": "Modo claro",
        "dark_mode": "Modo escuro",
        "save_score": "Salvar a pontuação",
        "log_in": "Entrar",
        "log_out": "Sair",
        "unsaved_score": "Pontuação não salva: {n}",
        "no_score": "Ainda sem pontuação",
        "score_line": "Pontuação: {n}",
        "leaderboard": "Ranking",
        "username": "Nome",
        "score_col": "Pontos",
        "hangman_alt": "Forca",
        "win": "Você acertou. A palavra era {word}.",
        "loss": "O desenho terminou. A palavra era {word}.",
        "worth": "Esta rodada vale {n}. Uma conta coloca isso no ranking.",
        "create_account": "Criar uma conta",
        "not_now": "Agora não",
        "next_word": "Próxima palavra",
        "email": "E-mail",
        "password": "Senha",
        "name_label": "Nome no ranking",
        "confirm_password": "Confirmar senha",
        "have_account": "Já tem uma conta?",
        "close": "Fechar",
        "cap_error": "Confirme que você é uma pessoa e tente de novo.",
        "bad_login": "E-mail ou senha inválidos",
        "session_expired": "A sessão expirou. Você mudou a senha?",
        "email_exists": "Esse e-mail já existe",
        "password_mismatch": "As senhas não coincidem.",
        "save_my_score": "Salvar minha pontuação",
        "try_again": "Algo deu errado. Tente de novo.",
        "error_title": "Algo deu errado",
        "error_body": "O erro foi registrado. Você pode voltar e tentar de novo.",
        "back_to_game": "Voltar ao jogo",
    },
    "ro": {
        "title": "Spânzurătoarea",
        "guest": "Oaspete",
        "change_language": "Schimbă limba",
        "language_confirm": "Schimbi limba? Acest cuvânt o ia de la capăt.",
        "light_mode": "Mod luminos",
        "dark_mode": "Mod întunecat",
        "save_score": "Salvează scorul",
        "log_in": "Autentificare",
        "log_out": "Ieșire",
        "unsaved_score": "Scor nesalvat: {n}",
        "no_score": "Încă nu este scor",
        "score_line": "Scor: {n}",
        "leaderboard": "Clasament",
        "username": "Nume",
        "score_col": "Scor",
        "hangman_alt": "Spânzurătoarea",
        "win": "Ai ghicit. Cuvântul era {word}.",
        "loss": "Desenul s-a terminat. Cuvântul era {word}.",
        "worth": "Runda aceasta valorează {n}. Un cont o pune în clasament.",
        "create_account": "Creează un cont",
        "not_now": "Nu acum",
        "next_word": "Cuvântul următor",
        "email": "E-mail",
        "password": "Parolă",
        "name_label": "Nume în clasament",
        "confirm_password": "Confirmă parola",
        "have_account": "Ai deja un cont?",
        "close": "Închide",
        "cap_error": "Confirmă că ești o persoană, apoi încearcă din nou.",
        "bad_login": "E-mail sau parolă incorectă",
        "session_expired": "Sesiunea a expirat. Ai schimbat parola?",
        "email_exists": "Acest e-mail există deja",
        "password_mismatch": "Parolele nu coincid.",
        "save_my_score": "Salvează scorul meu",
        "try_again": "Ceva nu a mers bine. Încearcă din nou.",
        "error_title": "Ceva nu a mers bine",
        "error_body": "Eroarea a fost raportată. Poți reveni și încerca din nou.",
        "back_to_game": "Înapoi la joc",
    },
    "tr": {
        "title": "Adam asmaca",
        "guest": "Misafir",
        "change_language": "Dili değiştir",
        "language_confirm": "Dil değişsin mi? Bu kelime baştan başlar.",
        "light_mode": "Aydınlık mod",
        "dark_mode": "Karanlık mod",
        "save_score": "Puanı kaydet",
        "log_in": "Giriş yap",
        "log_out": "Çıkış yap",
        "unsaved_score": "Kaydedilmemiş puan: {n}",
        "no_score": "Henüz puan yok",
        "score_line": "Puan: {n}",
        "leaderboard": "Sıralama",
        "username": "Ad",
        "score_col": "Puan",
        "hangman_alt": "Adam asmaca",
        "win": "Buldun. Kelime {word} idi.",
        "loss": "Çizim bitti. Kelime {word} idi.",
        "worth": "Bu tur {n} puan. Bir hesap onu sıralamaya yazar.",
        "create_account": "Hesap oluştur",
        "not_now": "Şimdi değil",
        "next_word": "Sonraki kelime",
        "email": "E-posta",
        "password": "Parola",
        "name_label": "Sıralamadaki ad",
        "confirm_password": "Parolayı doğrula",
        "have_account": "Hesabın var mı?",
        "close": "Kapat",
        "cap_error": "Bir kişi olduğunu doğrula, sonra yeniden dene.",
        "bad_login": "E-posta veya parola hatalı",
        "session_expired": "Oturum süresi doldu. Parolayı değiştirdin mi?",
        "email_exists": "Bu e-posta zaten var",
        "password_mismatch": "Parolalar uyuşmuyor.",
        "save_my_score": "Puanımı kaydet",
        "try_again": "Bir şeyler ters gitti. Yeniden dene.",
        "error_title": "Bir şeyler ters gitti",
        "error_body": "Hata bildirildi. Geri dönüp yeniden deneyebilirsin.",
        "back_to_game": "Oyuna dön",
    },
}


def html_lang(language):
    if language == "pt-br":
        return "pt-BR"
    if language in _STRINGS:
        return language
    return "en"


def catalog(language):
    return dict(_STRINGS.get(language) or _STRINGS["en"])


def text(language, key, **values):
    template = catalog(language).get(key) or _STRINGS["en"][key]
    return template.format(**values) if values else template


def match_accept_language(header):
    """Pick a supported language from an Accept-Language header."""
    if not header:
        return "en"
    supported = set(game.getLanguages())
    ranked = []
    for index, part in enumerate(header.split(",")):
        piece = part.strip()
        if not piece:
            continue
        tag, _, params = piece.partition(";")
        quality = 1.0
        for param in params.split(";"):
            param = param.strip()
            if param.startswith("q="):
                try:
                    quality = float(param[2:])
                except ValueError:
                    quality = 0.0
        ranked.append((quality, -index, tag.strip().lower().replace("_", "-")))
    ranked.sort(reverse=True)
    for _, _, tag in ranked:
        if tag in supported:
            return tag
        primary = tag.split("-")[0]
        if primary == "pt":
            return "pt-br"
        if primary in supported:
            return primary
    return "en"


def client_state(language, word, letters, wrong_guesses, result=None, pending=0):
    """Board data the page can apply without loading a new document."""
    language = language if language in _STRINGS else "en"
    letters = [ch.lower() for ch in letters or []]
    wrong_guesses = int(wrong_guesses or 0)
    if result:
        status = "won" if result.get("success") else "lost"
    else:
        status = game.round_status(word, letters, wrong_guesses)
    names = game.language_names()
    state = {
        "language": language,
        "html_lang": html_lang(language),
        "flag": game.language_flag(language),
        "flag_name": names.get(language, names["en"]),
        "status": status,
        "tiles": game.reveal(word, letters, status),
        "letter_states": game.letter_states(letters, word),
        "drawing": game.drawing_for(wrong_guesses, status),
        "copy": catalog(language),
        "title": text(language, "title"),
        "result": None,
    }
    if result:
        shown = (result.get("word") or word or "").capitalize()
        offer = bool(result.get("offer"))
        state["result"] = {
            "success": bool(result.get("success")),
            "offer": offer,
            "message": text(
                language, "win" if result.get("success") else "loss", word=shown
            ),
            "worth": (
                text(language, "worth", n=result.get("points", pending))
                if offer
                else ""
            ),
        }
    return state
