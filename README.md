# C3 — Suivi quotidien des carburants en Corse

C3 suit les prix depuis le **1er octobre 2026**. Le site présente le gazole et le SP95 en Corse, le classement quotidien des 13 régions et les écarts avec les Bouches-du-Rhône.

- Comparaisons territoriales du même carburant, toutes stations et réseau traditionnel.
- Gazole à enseigne comparable : Total et Eni, hors autoroutes, grandes surfaces et low-cost.
- Comparaison complémentaire SP95 Corse / SP95-E10 Bouches-du-Rhône : deux carburants différents, indiqués explicitement.

Les prix moyens sont TTC. Les écarts neutralisent la TVA : **Corse ÷ 1,13 ; Bouches-du-Rhône ÷ 1,20**, sans soustraire l’accise. Un écart négatif signifie que la Corse est moins chère.

## Données et site

`data/current.json` indique la dernière journée effectivement disponible dans `end`. Les points déjà enregistrés sont conservés. L’amorçage du 1er au 25 octobre 2026 est dans `data/history_20261025.json` ; les journées suivantes sont calculées dans C3.

Les critères et moteurs copiés dans `engine/` appartiennent à C3 ; leur provenance est documentée dans `engine/PROVENANCE.json`. Les registres propres à C3 sont dans `config/`. Aucun traitement C3 n’écrit dans C1 ou C2 ni n’y déclenche un workflow.

Les sources et les décisions d’une exécution sont conservées dans son artefact d’audit, avec une rétention GitHub de 90 jours. Elles ne sont pas toutes versionnées dans ce dépôt. Il faut conserver ces artefacts plus longtemps pour pouvoir reproduire les calculs à long terme.

Le site publié correspond au dossier `maquette/dist/`. `index.html` utilise des URL de ressources versionnées par empreinte ; `C3.html` embarque les styles, scripts et données dans un seul fichier. L’interface ne contient aucun lien vers les dépôts techniques.

## Mise à jour quotidienne

Voir [AUTOMATISATION.md](AUTOMATISATION.md). Cloudflare demande la mise à jour à **7 h 37**, avec rattrapages à **10 h 37 et 14 h 37**, heure de Paris. Les écritures exigent les activations côté Worker et côté GitHub. Un lancement ou une publication peut rester en attente côté GitHub ; la dernière journée disponible doit être contrôlée sur le site.

Le workflow de publication vérifie le contenu public. Une vérification horaire de secours concerne seulement la publication : elle ne remplace pas Cloudflare pour la collecte.

Les archives annuelles sont sélectionnées selon leur année et le jour réel de collecte. Le passage d’année est couvert par des tests simulés ; il ne constitue pas une validation d’archives 2027 qui n’existent pas encore à la date de préparation.

## Commandes depuis la racine du dépôt

Installer Python 3.12, Node.js et les dépendances :

```text
python -m pip install -r requirements.lock.txt
```

Essai isolé jusqu’à la veille à Paris, sans écriture des données visibles :

```text
python -B daily_refresh.py --run essai20261031 --target 2026-10-30
```

Chaque identifiant `--run` doit être nouveau. Un essai sur une date déjà présente après le 25 octobre rejoue cette journée dans une copie temporaire. L’option `--apply` enregistre un candidat uniquement après validation ; en automatisation, la variable GitHub doit également autoriser l’écriture.

Contrôles indépendants de téléchargements :

```text
python -B test_automation.py
python -B test_regressions.py
python -B test_year_rollover.py
python -B test_pages_health.py
node cloudflare/test_worker.mjs
python -B build_mockup.py
python -B verify_mockup.py
node verify_ui.cjs
```

`test_current.py` s’exécute après un calcul et utilise ses sources et sorties d’audit ; il ne peut pas reproduire ces contrôles à partir du seul dépôt neuf. `verify_ui.cjs` contrôle les branchements, les séries et les exports avec un DOM simulé. Il ne remplace pas une vérification visuelle dans un navigateur.
