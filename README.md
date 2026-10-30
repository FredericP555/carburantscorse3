# C3 — Suivi quotidien indépendant

Voir [AUTOMATISATION.md](AUTOMATISATION.md) pour le Worker C3 et le workflow quotidien préparés, désactivés et non déployés.

## État au 30 octobre 2026

La maquette locale couvre le **1er–29 octobre 2026**. Les points affichés du 1er au 25 octobre sont conservés ; les 26–29 octobre sont calculés indépendamment dans C3. Aucune publication et aucune automatisation activée.

- `data/history_20261025.json` : amorçage immuable des valeurs précédemment affichées.
- `data/current.json` : série courante, complétée après contrôles sans réécriture de l’historique.
- `engine/profile1` et `engine/profile2` : copies C3 des règles, provenance dans `engine/PROVENANCE.json`. Aucun import depuis les clones de référence pendant le calcul courant.
- `config/` : registres propres à C3 ; identités datées, aucun report rétroactif d’une enseigne actuelle.
- `sources/runs/20261030` : stock annuel officiel récent, snapshots quotidiens 26–29 octobre, UFIP et copies des registres utilisés.
- `outputs/runs/20261030/CONTROLE_ACTUEL.md` : contrôle des résultats, des effectifs et des exclusions Total, avec limites.
- `maquette/C3.html` : page autonome, utilisable sans serveur.

### Recalcul manuel reproductible, hors réseau

```text
python -B c3/run_current.py --run 20261030 --end 2026-10-29
```

Le recalcul utilise les entrées déjà archivées. Il ne réécrit aucun jour déjà présent dans `data/current.json`. Le collecteur accepte les rattrapages jusqu’à décembre 2026. Le passage annuel à 2027 et la résolution automatique complète des nouveaux IDs restent à valider avant activation. Ne pas réutiliser un identifiant de collecte pour des entrées nouvelles.

Contrôles :

```text
python -B c3/test_current.py
python -B c3/verify_mockup.py
node c3/verify_ui.cjs
```

Les écarts territoriaux sont hors TVA (13 % Corse / 20 % continent), sans soustraire l’accise. Autoroutes exclues. Total traditionnel exclut Access et Élan ; ENI est suivi séparément. Le SP95/E10 est une comparaison de carburants différents, explicitement signalée.

Les instantanés quotidiens servent à corroborer les ruptures ; ils ne remplacent pas le stock annuel dans le moteur historique. Le report UFIP après la dernière cotation observée est explicite dans le contrôle. C1 et C2 restent strictement intacts.

---

## Historique des investigations initiales

# C3 — Étape 2 : calculs locaux de contrôle

Une maquette locale autonome est disponible dans [maquette/C3.html](maquette/C3.html), accompagnée de [son aperçu](maquette/apercu.jpg). Elle reprend les historiques publiés de C1/C2 pour les vues communes et distingue les diagnostics Total provisoires. Aucune collecte automatique ni publication n’est activée.

Période de suivi : depuis le 1er octobre 2026. Ce premier contrôle s’arrête au 25 octobre, dernière journée du lot partagé C1 retenu.

## Lire les résultats

Ouvrir `outputs/CONTROLE.md` après l’exécution. Les exports détaillés sont dans `outputs/` ; les sources et leurs empreintes sont dans `sources/manifest.json`.

Ce dossier n’est pas encore un site. Il n’active aucun traitement récurrent et ne publie aucune donnée.

## Protection de C1 et C2

Les répertoires `reference-c1` et `reference-c2` sont des copies de lecture des dépôts publics. Aucun script de promotion, de commit, de push, de résolution d’enseigne écrivant dans ces copies ou de déclenchement GitHub n’est utilisé.

Les scripts C3 désactivent l’écriture des fichiers Python compilés dans ces références. Les fichiers auxiliaires attendus par les moteurs sont placés dans `runtime/`, exclusivement dans C3. Le contrôle final exige que les deux copies Git soient sans modification.

## Reproduction

Utiliser Python 3.12 avec pandas, openpyxl, requests et beautifulsoup4. Les dépendances manquantes de cette session ont été placées dans `dependencies/`, sans modification des références. L’environnement de calcul est relevé dans `outputs/environment.json`.

Depuis la racine de l’espace de travail :

```text
python -B c3/fetch_sources.py
python -B c3/control_c1.py
python -B c3/control_c2.py
python -B c3/assemble_control.py
python -B c3/test_control.py
```

La première commande effectue uniquement des lectures HTTP et des écritures dans `c3/sources`. Les quatre suivantes fonctionnent hors réseau. Chaque rejeu C2 avec un répertoire source distinct dispose de son propre sous-répertoire auxiliaire sous `runtime/`.

Le calendrier de bouclier utilisé pour le contrôle est épinglé au lot partagé C1, commun aux deux profils. C1 est rejoué sur les stocks annuels téléchargés pour C3 ; C2 utilise les déclarations et événements du lot partagé, ce qui permet de vérifier directement son calcul courant. C3 trace les décisions des moteurs sans changer leurs règles.

Pour limiter la mémoire du rejeu C1, toutes les déclarations à partir du 1er octobre sont conservées et seul le dernier état antérieur par station–carburant est gardé. Les prix invalides restent des états explicites. Les événements officiels sont conservés ; la réduction ne change pas leur état ouvert/fermé à l’entrée de la fenêtre. Cette optimisation est propre à C3 et testée sur la conservation des états.

## Ce que ce premier contrôle ne valide pas encore

- Une collecte quotidienne autonome, les rattrapages et la publication.
- La résolution officielle de nouveaux IDs dans un registre propre à C3.
- Une égalité automatique entre tout historique recalculé et les valeurs publiées, protégées en append-only dans C1/C2.
- Un seuil statistique particulier pour les sous-groupes Total. Les effectifs réels sont fournis pour examen.

L’E10 n’est pas présenté comme substitut du SP95. Ses observations sont néanmoins conservées par le moteur C2 lorsqu’elles servent à vérifier l’activité d’une station, conformément à sa méthode.

## Enquête complémentaire

Lire `outputs/ENQUETE.md` : 100/100 écarts C2 reproduits avec leurs entrées de première publication ; 42 différences C1 non attribuées avec certitude ; six IDs avec des périodes d’identité encore incertaines.

`fetch_sources.py --history` archive les lots d’octobre et les 25 instantanés quotidiens officiels. Les registres historiques ont été lus par le connecteur GitHub en référence aux commits indiqués dans `audit_history.py` ; leurs fichiers et les extraits de 31 versions sont conservés dans `sources/history/` et `sources/station_history_evidence.json`.

Pour chaque cas de `audit_history.CASES`, `control_c2.py` accepte `--source-dir`, `--output-dir`, `--registry-file` et `--start` afin de rejouer le lot et le registre correspondants sans toucher au cas principal. `audit_history.py` vérifie ensuite les 100 comparaisons et génère le bilan.

`audit_daily_sources.py` et `replay_daily_c1.py` examinent les instantanés quotidiens comme diagnostics de source ; ils ne remplacent ni le moteur annuel ni les historiques publiés. Les archives annuelles complètes des anciennes exécutions n’ont pas été retrouvées dans les lots partagés et artefacts examinés. Cette limite reste explicite dans les résultats.
