# Pistes d'amélioration du lab

Idées pour faire évoluer Lumen Freight Lab au-delà de la version actuelle,
classées par effort estimé.

## Effort faible

- **Mode "difficulté réduite"** : variable d'environnement qui affiche un
  bandeau d'indice directement dans l'UI après N minutes d'inactivité.
- **Timer / scoreboard** : enregistrer dans un fichier le temps mis par
  chaque apprenant entre la connexion et la récupération du flag (ajout
  d'un endpoint `/submit-flag` côté helpdesk).
- **Variante du flag par session** : générer un flag unique par instance
  au démarrage (`scripts/start.sh`) pour éviter le partage de solutions
  entre apprenants d'une même promotion.

## Effort moyen

- **Deuxième chaîne d'exploitation indépendante** : ajouter une faille de
  contrôle d'accès vertical (passer employé → agent) via un paramètre de
  rôle manipulable, pour varier les apprentissages sans toucher à la
  chaîne SSRF existante.
- **Journalisation visible** : exposer en lecture seule un "faux SIEM"
  (fichier de logs HTTP consultable) pour apprendre aux débutants à
  retrouver leurs propres traces d'attaque — utile pour la partie
  "analyse des impacts" du cahier des charges.
- **Durcissement partiel optionnel** : une variante `docker-compose.hardened.yml`
  qui corrige une partie des failles (ex: IDOR corrigé mais pas le SSRF)
  pour un exercice "retrouvez ce qui a été corrigé et ce qui reste".

## Effort élevé

- **Vraie simulation d'agent par navigateur headless** (Playwright) qui
  consulte réellement les tickets et exécute le JavaScript injecté,
  permettant une XSS "vivante" avec vol de cookie de session effectif
  plutôt qu'une confirmation via route de debug. Nécessite un accès
  réseau pour télécharger le binaire du navigateur à l'image Docker (non
  trivial dans des environnements à accès réseau restreint).
- **Extension Active Directory** : ajouter un second scénario inspiré de
  l'idée "fusion d'entreprises" évoquée en amont (domaine AD hérité,
  comptes de service sur-privilégiés) pour un public plus avancé,
  éventuellement comme un lab séparé du même univers narratif Lumen
  Freight.
- **Portail formateur web** : dashboard consultant automatiquement les
  logs de chaque conteneur pour suivre la progression de plusieurs
  apprenants en parallèle (multi-instance via un préfixe de port ou un
  orchestrateur dédié).
