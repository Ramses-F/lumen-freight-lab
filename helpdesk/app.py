"""
Lumen Freight Services — Helpdesk interne ("Lumen Helpdesk")
================================================================
Application volontairement vulnérable pour un lab de pentest pédagogique.

NE JAMAIS DÉPLOYER CE CODE EN DEHORS D'UN ENVIRONNEMENT ISOLÉ.
Les vulnérabilités ci-dessous sont INTENTIONNELLES et documentées dans
VULNERABILITIES.md et docs/FORMATEUR.md.

Résumé des failles volontaires (voir docs pour le détail complet) :
  1. IDOR sur /tickets/<id>            -> aucune vérification de propriété
  2. XSS stockée sur /tickets/<id>/raw -> rendu HTML sans échappement (route
     de debug QA oubliée avant mise en prod)
  3. SSRF sur la création de ticket    -> l'aperçu d'image embarquée effectue
     une requête HTTP côté serveur vers n'importe quelle URL, y compris les
     hôtes du réseau interne (pas de filtrage d'IP/host)
"""

import os
import re
import sqlite3
import time
from functools import wraps

import requests
from flask import Flask, g, redirect, render_template, request, session, url_for, flash

APP_SECRET = os.environ.get("HELPDESK_SECRET_KEY", "lumen-dev-secret-not-for-prod")
DB_PATH = os.environ.get("HELPDESK_DB_PATH", "/data/helpdesk.db")
PREVIEW_TIMEOUT = float(os.environ.get("HELPDESK_PREVIEW_TIMEOUT", "3"))
PREVIEW_MAX_CHARS = 400

IMG_MARKDOWN_RE = re.compile(r"!\[[^\]]*\]\((https?://[^\s)]+)\)")

app = Flask(__name__)
app.secret_key = APP_SECRET


# ---------------------------------------------------------------------------
# Base de données
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    first_init = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'employee',
            display_name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            description TEXT NOT NULL,
            preview_snippet TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (author_id) REFERENCES users (id)
        );
        """
    )
    conn.commit()
    if first_init:
        seed(conn)
    conn.close()


def seed(conn):
    """Jeu de données fictif cohérent + comptes de test + indices narratifs."""
    cur = conn.cursor()

    # Comptes de test (mots de passe volontairement simples : lab pédagogique)
    cur.execute(
        "INSERT INTO users (username, password, role, display_name) VALUES (?,?,?,?)",
        ("admin.rousseau", "LumenAdmin2024!", "admin", "Hélène Rousseau (IT Admin)"),
    )
    cur.execute(
        "INSERT INTO users (username, password, role, display_name) VALUES (?,?,?,?)",
        ("bob.martin", "SupportBob25", "agent", "Bob Martin (Support N1)"),
    )
    cur.execute(
        "INSERT INTO users (username, password, role, display_name) VALUES (?,?,?,?)",
        ("j.leclerc", "Welcome123", "employee", "Julie Leclerc (Logistique)"),
    )
    conn.commit()

    admin_id = cur.execute("SELECT id FROM users WHERE username=?", ("admin.rousseau",)).fetchone()[0]
    bob_id = cur.execute("SELECT id FROM users WHERE username=?", ("bob.martin",)).fetchone()[0]
    julie_id = cur.execute("SELECT id FROM users WHERE username=?", ("j.leclerc",)).fetchone()[0]

    now = time.strftime("%Y-%m-%d %H:%M")

    # Ticket admin : indice narratif révélant l'hôte interne "vault" (SSRF)
    cur.execute(
        """INSERT INTO tickets (author_id, subject, description, preview_snippet, created_at)
           VALUES (?,?,?,?,?)""",
        (
            admin_id,
            "Migration archivage - notes internes",
            "Pour mémoire équipe infra : l'aperçu d'image des tickets passe "
            "désormais par le service d'archivage interne (host interne "
            "'vault', port 5001) pour le scan antivirus avant affichage. "
            "Ce service NE DOIT JAMAIS être exposé publiquement, seul le "
            "helpdesk doit pouvoir lui parler. Ticket fermé, pour archive.",
            None,
            now,
        ),
    )

    # Ticket bob -> julie : indice narratif sur la route de debug XSS oubliée
    cur.execute(
        """INSERT INTO tickets (author_id, subject, description, preview_snippet, created_at)
           VALUES (?,?,?,?,?)""",
        (
            bob_id,
            "Re: Anomalie affichage ticket #de test QA",
            "Julie, pour rappel la vue /tickets/<id>/raw c'était juste pour "
            "que la QA puisse vérifier le rendu HTML brut des descriptions "
            "avant qu'on active l'échappement en prod. Il faudra la retirer "
            "avant le go-live, je l'ai mise en TODO sprint prochain.",
            None,
            now,
        ),
    )

    # Ticket employé normal, pour remplir le dashboard
    cur.execute(
        """INSERT INTO tickets (author_id, subject, description, preview_snippet, created_at)
           VALUES (?,?,?,?,?)""",
        (
            julie_id,
            "Scanner entrepôt B ne s'allume plus",
            "Bonjour, le scanner code-barres du quai B3 ne s'allume plus "
            "depuis ce matin. Merci de planifier une intervention.",
            None,
            now,
        ),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def current_user():
    if "user_id" not in session:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()


@app.context_processor
def inject_user():
    return {"current_user": current_user()}


# ---------------------------------------------------------------------------
# SSRF vulnerable feature : aperçu d'image embarquée dans une description
# ---------------------------------------------------------------------------

def fetch_preview(description: str):
    """
    Fonctionnalité "aperçu pièce jointe" : si la description contient une
    image au format markdown ![alt](url), le backend va chercher le
    contenu de l'URL côté serveur pour en afficher un extrait.

    VULNERABILITE (SSRF, CWE-918) : aucune validation de l'hôte/IP cible.
    N'importe quelle URL, y compris les services du réseau interne
    (ex: http://vault:5001/...), peut être demandée par le serveur, qui
    renverra un extrait de la réponse. C'est le point d'entrée SSRF du lab.
    """
    match = IMG_MARKDOWN_RE.search(description)
    if not match:
        return None
    target_url = match.group(1)
    try:
        resp = requests.get(target_url, timeout=PREVIEW_TIMEOUT)
        snippet = resp.text[:PREVIEW_MAX_CHARS]
        return f"[Aperçu automatique de {target_url}]\n{snippet}"
    except requests.RequestException as exc:
        return f"[Aperçu indisponible pour {target_url}: {exc.__class__.__name__}]"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        display_name = request.form.get("display_name", "").strip() or username
        if not username or not password:
            flash("Identifiant et mot de passe requis.", "error")
            return render_template("register.html")
        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if existing:
            flash("Ce nom d'utilisateur existe déjà.", "error")
            return render_template("register.html")
        db.execute(
            "INSERT INTO users (username, password, role, display_name) VALUES (?,?,?,?)",
            (username, password, "employee", display_name),
        )
        db.commit()
        flash("Compte créé, vous pouvez vous connecter.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if user and user["password"] == password:
            session["user_id"] = user["id"]
            flash(f"Bienvenue, {user['display_name']}.", "success")
            nxt = request.args.get("next") or url_for("dashboard")
            return redirect(nxt)
        flash("Identifiants invalides.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user = current_user()
    tickets = db.execute(
        "SELECT * FROM tickets WHERE author_id=? ORDER BY id DESC", (user["id"],)
    ).fetchall()
    return render_template("dashboard.html", tickets=tickets)


@app.route("/tickets/new", methods=["GET", "POST"])
@login_required
def new_ticket():
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        description = request.form.get("description", "").strip()
        if not subject or not description:
            flash("Sujet et description requis.", "error")
            return render_template("new_ticket.html")

        preview_snippet = fetch_preview(description)

        db = get_db()
        db.execute(
            """INSERT INTO tickets (author_id, subject, description, preview_snippet, created_at)
               VALUES (?,?,?,?,?)""",
            (current_user()["id"], subject, description, preview_snippet, time.strftime("%Y-%m-%d %H:%M")),
        )
        db.commit()
        new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        flash("Ticket créé.", "success")
        return redirect(url_for("view_ticket", ticket_id=new_id))
    return render_template("new_ticket.html")


@app.route("/tickets/<int:ticket_id>")
@login_required
def view_ticket(ticket_id):
    """
    VULNERABILITE (IDOR, CWE-639) : aucun contrôle que l'utilisateur
    connecté est bien l'auteur du ticket (ou un agent/admin). N'importe
    quel compte authentifié peut lire n'importe quel ticket par ID.
    """
    db = get_db()
    ticket = db.execute(
        """SELECT tickets.*, users.display_name AS author_name, users.username AS author_username
           FROM tickets JOIN users ON users.id = tickets.author_id
           WHERE tickets.id=?""",
        (ticket_id,),
    ).fetchone()
    if not ticket:
        return render_template("not_found.html"), 404
    return render_template("view_ticket.html", ticket=ticket)


@app.route("/tickets/<int:ticket_id>/raw")
@login_required
def view_ticket_raw(ticket_id):
    """
    VULNERABILITE (Stored XSS, CWE-79) : route de "QA preview" oubliée en
    prod. Elle rend la description du ticket SANS échappement HTML, via
    render_template_string + filtre |safe, contrairement à la vue normale
    qui échappe correctement (auto-escaping Jinja2 actif par défaut).
    """
    db = get_db()
    ticket = db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
    if not ticket:
        return render_template("not_found.html"), 404
    # Rendu volontairement non échappé pour reproduire la faille QA.
    unsafe_html = f"""
    <!doctype html>
    <html lang="fr"><head><meta charset="utf-8">
    <title>QA raw preview - ticket #{ticket['id']}</title></head>
    <body style="font-family: monospace; background:#111; color:#0f0; padding:2rem;">
    <h3>[QA DEBUG] Rendu brut - ticket #{ticket['id']}</h3>
    <p><b>Sujet:</b> {ticket['subject']}</p>
    <div><b>Description (RAW, non échappée) :</b><br>{ticket['description']}</div>
    </body></html>
    """
    return unsafe_html


@app.route("/agent/queue")
@login_required
def agent_queue():
    user = current_user()
    if user["role"] not in ("agent", "admin"):
        flash("Accès réservé aux agents support.", "error")
        return redirect(url_for("dashboard"))
    db = get_db()
    tickets = db.execute(
        """SELECT tickets.*, users.display_name AS author_name
           FROM tickets JOIN users ON users.id = tickets.author_id
           ORDER BY tickets.id DESC"""
    ).fetchall()
    return render_template("agent_queue.html", tickets=tickets)


@app.route("/healthz")
def healthz():
    return {"status": "ok", "service": "lumen-helpdesk"}


with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
