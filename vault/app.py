"""
Lumen Vault — service d'archivage interne (fictif)
====================================================
Ce service ne doit JAMAIS être joignable depuis l'extérieur du réseau
Docker interne : dans docker-compose.yml il n'a PAS de "ports:" mappé vers
l'hôte, il n'est connecté qu'au réseau "internal_net" partagé avec le
helpdesk.

VULNERABILITE INTENTIONNELLE (confiance réseau interne, CWE-306 /
"missing authentication for critical function") : les endpoints ne
vérifient pas d'authentification forte — seul un jeton statique, visible
dès le premier appel à /internal/status, est requis pour /internal/export.
C'est un schéma réaliste : "c'est interne, donc c'est sûr" est une erreur
de conception fréquente en entreprise.

Ce service n'est accessible par un apprenant QUE via le SSRF du helpdesk
(fonctionnalité d'aperçu d'image), ce qui est l'objectif pédagogique du
lab : montrer qu'une confiance réseau mal placée devient exploitable dès
qu'un service frontal peut être détourné en proxy.
"""

from flask import Flask, request, jsonify, abort

app = Flask(__name__)

SERVICE_TOKEN = "VLT-7f3a9c2e-SERVICE-TOKEN"

# Jeu de données fictif stocké "dans le vault"
ARCHIVE = {
    "status.json": None,  # géré séparément par /internal/status
    "customer_manifest_sample.csv": (
        "shipment_id,client,destination,value_eur\n"
        "LFS-88213,Nordic Retail Group,Rotterdam,48250\n"
        "LFS-88214,Atlas Pharma Supply,Marseille,91200\n"
        "LFS-88215,Kappa Electronics,Hambourg,15300\n"
    ),
    "flag.txt": "LUMEN{ssrf_vers_service_interne_non_authentifie_8f2c91}",
}


@app.route("/")
def index():
    return {"service": "lumen-vault", "note": "internal use only"}


@app.route("/internal/status")
def status():
    """
    Endpoint de supervision basique. Volontairement, il renvoie le jeton
    de service dans sa réponse (habitude de debug non retirée en prod) :
    c'est le premier secret que la chaîne SSRF permet de récupérer.
    """
    return jsonify(
        {
            "service": "lumen-vault",
            "status": "ok",
            "version": "2.3.1",
            "token": SERVICE_TOKEN,
            "hint": "token requis pour /internal/export?file=...&token=...",
        }
    )


@app.route("/internal/export")
def export():
    file_name = request.args.get("file", "")
    token = request.args.get("token", "")

    if token != SERVICE_TOKEN:
        abort(403, description="Forbidden - service token required")

    if file_name not in ARCHIVE or ARCHIVE[file_name] is None:
        abort(404, description="Unknown archive file")

    return ARCHIVE[file_name], 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/healthz")
def healthz():
    return {"status": "ok", "service": "lumen-vault"}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
