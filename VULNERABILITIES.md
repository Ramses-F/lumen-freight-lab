# Vulnérabilités du lab — liste, impact, remédiation

Toutes les vulnérabilités ci-dessous sont **intentionnelles**, documentées
et confinées à l'environnement du lab (voir `docker-compose.yml` pour le
confinement réseau). Aucune donnée réelle n'est utilisée.

---

## V1 — IDOR sur la consultation de ticket (CWE-639)

- **Composant** : `helpdesk/app.py`, route `GET /tickets/<id>`
- **Description** : aucun contrôle que l'utilisateur authentifié est bien
  l'auteur du ticket (ni agent/admin). Tout utilisateur connecté peut lire
  n'importe quel ticket en changeant l'ID dans l'URL.
- **Impact** : divulgation d'informations internes (ici, des notes
  d'architecture et des indices opérationnels), potentiellement des
  données personnelles ou sensibles dans un système réel (fuite de
  confidentialité horizontale).
- **Reproductibilité** : systématique, aucune condition particulière.
- **Remédiation** :
  - Vérifier `ticket.author_id == current_user.id` ou un rôle autorisé
    (agent/admin) avant de servir la ressource.
  - Préférer des identifiants non séquentiels (UUID) pour réduire
    l'énumération, **en complément** du contrôle d'accès — jamais en
    remplacement.

---

## V2 — XSS stockée via route de debug oubliée (CWE-79)

- **Composant** : `helpdesk/app.py`, route `GET /tickets/<id>/raw`
- **Description** : route de QA jamais retirée avant la mise en
  production ; elle construit la réponse HTML par concaténation de
  chaînes (sans passer par le moteur de templates Jinja2, qui échappe par
  défaut), rendant la description du ticket telle quelle.
- **Impact** : dans un système réel, un attaquant pourrait voler la
  session d'un agent/admin consultant cette route, effectuer des actions
  en son nom, ou mener des attaques de phishing internes (défacement de
  l'interface vue par la victime).
- **Reproductibilité** : systématique dès qu'un payload HTML/JS est
  injecté dans la description d'un ticket et que la route `/raw` est
  consultée.
- **Remédiation** :
  - Supprimer purement et simplement la route avant toute mise en
    production (revue de code / checklist de recette).
  - Si un rendu "source" est réellement nécessaire, utiliser le moteur de
    templates avec auto-escaping actif plutôt qu'une concaténation
    manuelle.
  - Mettre en place une Content-Security-Policy stricte en défense en
    profondeur.

---

## V3 — SSRF via l'aperçu d'image des tickets (CWE-918)

- **Composant** : `helpdesk/app.py`, fonction `fetch_preview()` appelée à
  la création d'un ticket.
- **Description** : toute URL au format markdown image
  (`![alt](url)`) trouvée dans la description déclenche une requête HTTP
  **côté serveur**, sans aucune restriction de schéma, d'hôte ou d'IP
  cible (y compris les plages privées/loopback/réseau interne Docker).
- **Impact** : pivot réseau permettant d'atteindre des services internes
  normalement inaccessibles depuis l'extérieur (ici `vault`), avec
  réponse renvoyée à l'attaquant (SSRF non aveugle) — dans un contexte
  réel, cela peut aussi exposer des endpoints de métadonnées cloud
  (AWS/GCP/Azure instance metadata), bases de données internes, ou API
  d'administration.
- **Reproductibilité** : systématique, aucune condition particulière.
- **Remédiation** :
  - Mettre en place une allow-list stricte de domaines/schémas autorisés
    pour les requêtes sortantes (https uniquement, domaines connus).
  - Résoudre le DNS puis vérifier explicitement que l'IP résolue
    n'appartient pas à une plage privée, loopback ou link-local
    (`127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`,
    `169.254.0.0/16`) avant d'effectuer la requête — et revérifier après
    toute redirection HTTP.
  - Faire transiter ces requêtes par un proxy sortant dédié, isolé
    réseau, avec allow-list centralisée.
  - Limiter strictement la taille de réponse lue et le timeout (déjà fait
    partiellement ici à titre d'exemple, insuffisant seul).

---

## V4 — Absence d'authentification forte sur un service interne (CWE-306)

- **Composant** : `vault/app.py`
- **Description** : le service d'archivage interne considère que
  l'isolation réseau suffit ("c'est interne, donc c'est sûr") et ne
  protège son endpoint sensible que par un jeton statique révélé par un
  autre endpoint non protégé.
- **Impact** : une fois le réseau interne atteint (ici via le SSRF V3),
  aucune barrière sérieuse n'empêche l'accès aux données archivées.
  Mouvement latéral facilité, perte de "defense in depth".
- **Reproductibilité** : systématique une fois le jeton obtenu.
- **Remédiation** :
  - Authentification forte entre services (mTLS, jetons à courte durée de
    vie et rotation, identités de service plutôt que secret statique
    partagé).
  - Ne jamais exposer un secret de service dans une réponse non protégée,
    même "interne".
  - Principe de moindre privilège : `vault` ne devrait répondre qu'au
    service `helpdesk` identifié, pas à quiconque atteint le réseau.

---

## Mesures de confinement appliquées au lab

- `vault` n'a **aucun port mappé vers l'hôte** dans `docker-compose.yml`
  — il n'est joignable que depuis le réseau Docker interne.
- Le réseau `internal_net` est déclaré `internal: true` : pas de route
  sortante vers Internet depuis ce réseau.
- `helpdesk` n'est exposé que sur `127.0.0.1:5000`, jamais sur `0.0.0.0`.
- Toutes les données (comptes, tickets, secrets, flag) sont fictives.
- `scripts/reset.sh` permet de repartir d'un état propre à tout moment.
