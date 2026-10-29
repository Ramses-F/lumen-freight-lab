# Lumen Freight Lab — Lab de pentest pédagogique

Lab de pentest web **volontairement vulnérable**, construit autour d'une
chaîne réaliste : **IDOR → XSS stockée (route de debug oubliée) → SSRF vers
un service interne → secret exposé → exfiltration de données**.

Scénario, parcours apprenant et corrigé formateur : voir `docs/`.

> ⚠️ **Usage strictement pédagogique et autorisé.** Ne jamais exposer ce
> lab sur un réseau public ni y faire tourner des données réelles. Voir
> `VULNERABILITIES.md` pour le détail des failles et leur confinement.

## Pré-requis

- Docker + Docker Compose v2 (`docker compose version`)
- Un terminal (`curl` recommandé pour les tests manuels)

Aucun autre outil n'est nécessaire pour faire tourner le lab. Les outils
d'attaque (navigateur, `curl`, proxy d'interception, etc.) sont à la charge
de l'apprenant, comme dans une vraie mission.

## Démarrage

```bash
git clone <ce dossier> lumen-freight-lab   # ou simplement décompressez l'archive
cd lumen-freight-lab
scripts/start.sh
```

Le script construit les images, démarre les services et attend que le
portail soit prêt. Portail apprenant : **http://127.0.0.1:5000**

Le service interne `vault` n'est **volontairement pas exposé** à l'hôte :
c'est le réseau Docker interne (`internal_net`, `internal: true`) qui
l'isole. Seul le service `helpdesk` peut lui parler. Voir
`docker-compose.yml` pour le détail du confinement réseau.

## Arrêt / réinitialisation

```bash
scripts/stop.sh     # arrête les conteneurs, conserve les données
scripts/reset.sh     # arrêt complet + suppression du volume + réinjection du jeu de données initial
```

## Validation automatisée

Un script rejoue réellement toute la chaîne d'exploitation (pas une simple
vérification "le port répond") et vérifie que chaque vulnérabilité prévue
est bien présente et exploitable :

```bash
pip install requests   # si nécessaire
python3 tests/validate_lab.py
```

Résultat attendu : toutes les vérifications passent, y compris la preuve
que `vault` est injoignable directement depuis l'hôte (confinement
réseau). Voir `docs/VALIDATION.md` pour le détail de ce qui a été vérifié
et dans quelles conditions.

## Arborescence

```
lumen-freight-lab/
├── docker-compose.yml        # orchestration + confinement réseau
├── helpdesk/                 # application vulnérable principale (Flask)
│   ├── app.py
│   ├── templates/
│   └── Dockerfile
├── vault/                    # service interne non authentifié (Flask)
│   ├── app.py
│   └── Dockerfile
├── scripts/                  # start / stop / reset
├── tests/
│   └── validate_lab.py       # validation end-to-end de la chaîne d'exploitation
├── docs/
│   ├── MISSION.md             # brief apprenant
│   ├── FORMATEUR.md           # guide confidentiel (solutions, corrections)
│   ├── VALIDATION.md          # ce qui a été réellement testé, et comment
│   └── AMELIORATIONS.md       # pistes d'évolution du lab
├── VULNERABILITIES.md        # liste des failles, impact, remédiation
└── README.md                  # ce fichier
```

## Comptes de test pré-créés

| Compte | Mot de passe | Rôle |
|---|---|---|
| `j.leclerc` | `Welcome123` | employé (point d'entrée apprenant recommandé) |
| `bob.martin` | `SupportBob25` | agent support |
| `admin.rousseau` | `LumenAdmin2024!` | admin IT |

L'apprenant peut aussi créer son propre compte via `/register` — c'est le
parcours recommandé pour commencer la mission à froid, comme un vrai
nouvel employé.
# lumen-freight-lab
