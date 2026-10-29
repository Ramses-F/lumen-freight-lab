# Mission — Lumen Freight Services

*Document destiné aux apprenants. Le corrigé complet se trouve dans
`FORMATEUR.md`, réservé au formateur.*

## Contexte

**Lumen Freight Services** est une entreprise de transport et logistique
de taille moyenne. Son service IT a ouvert il y a quelques mois un portail
de support interne, **Lumen Helpdesk**, pour que les employés puissent
signaler des incidents (matériel, logiciel, accès...).

Le prestataire qui a développé ce portail a été pressé par le planning.
Le responsable sécurité de Lumen vous a mandaté pour réaliser un **test
d'intrusion en boîte grise** sur ce portail : vous avez le droit de créer
un compte employé classique, comme n'importe quel nouvel arrivant, mais
aucun accès privilégié ne vous a été donné au départ.

## Périmètre autorisé

- Le portail Lumen Helpdesk et tout ce qui est atteignable **depuis** lui
  (réseau du lab uniquement).
- Interdiction formelle de sortir du lab : n'attaquez jamais de systèmes
  réels sur Internet.

## Objectifs de la mission

1. **Reconnaissance** — comprendre le fonctionnement du portail, créer un
   compte, explorer les fonctionnalités disponibles.
2. **Énumération** — identifier comment les tickets sont référencés et ce
   qu'un utilisateur authentifié peut consulter.
3. **Collecte d'indices** — certains anciens tickets, visibles si vous
   trouvez comment y accéder, contiennent des informations laissées par
   inadvertance par l'équipe IT.
4. **Identification d'une vulnérabilité applicative** — une fonctionnalité
   de diagnostic, qui n'aurait jamais dû rester accessible en production,
   traite les données d'un ticket d'une manière risquée.
5. **Pivot réseau** — le portail dispose d'une fonctionnalité d'aperçu de
   pièce jointe qui effectue elle-même des requêtes. Jusqu'où peut-elle
   vous emmener ?
6. **Objectif final** — récupérer la preuve (un fichier `flag.txt`) stockée
   sur un service qui n'est normalement accessible à personne de
   l'extérieur, et documenter comment vous y êtes parvenu.
7. **Livrable** — un rapport précisant : la chaîne d'exploitation complète,
   l'impact métier de chaque étape, et une recommandation de correction.

## Indices progressifs (à n'ouvrir qu'en cas de blocage)

<details>
<summary>Indice 1 — Reconnaissance</summary>

Une fois connecté, regardez attentivement comment les tickets sont
numérotés et référencés dans l'URL. Que se passe-t-il si vous changez
simplement le numéro ?
</details>

<details>
<summary>Indice 2 — Après avoir lu d'autres tickets</summary>

Deux tickets plus anciens contiennent des informations internes
intéressantes : l'un évoque une fonctionnalité de test jamais retirée,
l'autre évoque l'architecture d'un service d'archivage interne. Lisez-les
attentivement, ils donnent presque toute la suite du chemin.
</details>

<details>
<summary>Indice 3 — Vulnérabilité applicative</summary>

Si un ticket mentionne une URL de la forme <code>/tickets/&lt;id&gt;/raw</code>,
qu'est-ce que cela pourrait signifier pour la façon dont le contenu est
affiché ? Essayez de créer un ticket avec un contenu qui serait dangereux
s'il n'était pas échappé, puis comparez son affichage sur la vue normale
et sur cette route.
</details>

<details>
<summary>Indice 4 — Pivot réseau</summary>

La création de ticket mentionne qu'on peut joindre une image avec la
syntaxe <code>![alt](url)</code>. Qui va chercher cette image, et depuis
où ? Un des tickets lus plus tôt donne le nom d'hôte et le port d'un
service interne...
</details>

<details>
<summary>Indice 5 — Objectif final</summary>

Le service interne répond à <code>/internal/status</code> avec une
information qui ressemble à un jeton d'authentification. Un autre
endpoint, <code>/internal/export</code>, pourrait bien l'attendre en
paramètre.
</details>

## Rappel de sécurité

Ce lab est isolé : le service interne n'est accessible que depuis le
portail lui-même, jamais directement depuis votre machine. Si une requête
directe vers lui échoue, c'est normal et voulu — c'est tout l'intérêt du
pivot à trouver.
