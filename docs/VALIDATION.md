# Ce qui a été réellement vérifié, et comment

Conformément à la consigne de ne jamais prétendre avoir testé ce qui ne
l'a pas été, voici précisément ce qui a été exécuté pendant la
construction de ce lab, et la limite rencontrée.

## Limite rencontrée : Docker non disponible dans l'environnement de build

L'environnement dans lequel ce lab a été construit ne dispose pas d'un
démon Docker fonctionnel (pas de support des conteneurs imbriqués —
`dockerd` ne démarre pas, `docker compose build` échoue avec *"failed to
connect to the docker API"*). Il n'a donc **pas été possible d'exécuter
`docker compose up` ni de valider le lab dans sa topologie Docker finale**
pendant cette session.

Ce qui a été vérifié malgré cette limite :

- **Validité syntaxique du `docker-compose.yml`** : `docker compose
  config` (qui ne nécessite pas le démon) a été exécuté avec succès et a
  confirmé que le fichier est bien formé, que les réseaux, volumes,
  healthchecks et le mapping de port (`127.0.0.1:5000` uniquement pour
  `helpdesk`, aucun port pour `vault`) sont corrects.

## Ce qui a été réellement testé (code applicatif, en conditions réelles)

Les deux applications Flask (`helpdesk` et `vault`) ont été **exécutées
directement** (sans Docker, via `python3 app.py`), avec un alias réseau
local (`vault` → `127.0.0.1` dans `/etc/hosts`) pour reproduire exactement
le nom d'hôte utilisé dans les payloads SSRF du lab, tel qu'il sera
résolu par Docker DNS en production. Le script `tests/validate_lab.py` a
ensuite été exécuté contre ces services réels et a rejoué, avec de
véritables requêtes HTTP, toute la chaîne d'exploitation :

1. Inscription + connexion d'un compte apprenant — **réussi**
2. IDOR sur `/tickets/1` (lecture d'un ticket d'un autre utilisateur) —
   **réussi**, breadcrumb "vault" bien présent dans la réponse
3. Vue normale d'un ticket contenant un payload XSS : confirmation que le
   HTML est bien échappé — **réussi**
4. Route `/tickets/<id>/raw` : confirmation que le même payload n'est
   **pas** échappé — **réussi**
5. SSRF : création d'un ticket avec une image pointant vers
   `http://vault:5001/internal/status`, et confirmation que la réponse du
   service interne (y compris le jeton) apparaît dans l'aperçu — **réussi**
6. Exfiltration finale : réutilisation du SSRF avec le jeton récupéré
   vers `/internal/export?file=flag.txt&token=...`, et confirmation que le
   flag `LUMEN{...}` est bien récupéré — **réussi**

Vérifications complémentaires manuelles (`curl`) également exécutées et
réussies :
- accès non authentifié à un ticket → redirection propre vers `/login`
- compte non-agent bloqué sur `/agent/queue` → redirection vers
  `/dashboard`
- compte `bob.martin` (agent) → accès à `/agent/queue` confirmé
- appel direct à `vault` avec un mauvais jeton → `403` propre
- image pointant vers une URL injoignable → pas de crash, erreur gérée
  proprement, ticket tout de même créé

## Le seul test qui a échoué, et pourquoi c'est normal

Le script `validate_lab.py` inclut une vérification "`vault` est
injoignable directement depuis l'hôte". Dans ce contexte de validation
sans Docker, `vault` tournait sur `127.0.0.1:5001` (nécessaire pour le
tester directement), donc ce test échoue **dans ce contexte précis**,
comme attendu. Dans la vraie topologie `docker-compose.yml`, `vault` n'a
aucun port mappé vers l'hôte et ce test est censé **passer** — mais cela
n'a pas pu être confirmé avec le démon Docker réel pendant cette session.

## Recommandation avant utilisation en formation

Avant la première session avec des apprenants, il est recommandé
d'exécuter, sur une machine disposant d'un Docker fonctionnel :

```bash
scripts/start.sh
python3 tests/validate_lab.py
curl -m 2 http://127.0.0.1:5001/internal/status   # doit échouer/timeout — confirme le confinement réseau
```

et de confirmer que les 10 vérifications du script passent, y compris la
dernière. L'auteur de ce lab n'a pas pu réaliser cette dernière étape
faute d'environnement Docker disponible, et le signale explicitement ici
plutôt que de l'affirmer.
