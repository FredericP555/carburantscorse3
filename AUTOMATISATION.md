# Préparation de la mise à jour quotidienne C3

État : **fichiers préparés localement, aucun dépôt créé, aucun Worker déployé, aucun déclencheur activé**. Le Worker `a4c-scheduler` existant et les projets C1/C2 ne sont pas modifiés.

## Architecture proposée

Un Worker indépendant `a4c-c3-scheduler` appelle uniquement `FredericP555/carburantscorse3`, workflow `update-daily.yml`. Ce nom de dépôt est une proposition et doit être confirmé à sa création. Le contenu de ce dossier C3 devient la racine du futur dépôt, sans les dossiers de référence ni les téléchargements locaux.

Horaires proposés : tous les jours à **07:37**, avec rattrapages **10:37 et 14:37**, heure de Paris. Ils ne sont pas activés et peuvent être ajustés. Un futur cron Cloudflare `37 * * * *` appelle le Worker chaque heure ; le code ne sélectionne que ces trois créneaux par conversion Europe/Paris, été et hiver. Pas de planification native GitHub.

Avant chaque demande, le Worker lit la dernière date C3 et les exécutions GitHub : rien si la veille est déjà intégrée ou si un traitement attend/est en cours. Le workflow sérialise les écritures et relit les données du dépôt ; une demande répétée devient une opération sans effet. Le Worker ne garantit pas le démarrage immédiat d'un runner GitHub.

L'ouverture HTTP du Worker affiche un état et ne déclenche rien. Le champ enabled décrit la variable du programme, sans prétendre inspecter la configuration réelle des crons.

## Vérification avant enregistrement

`daily_refresh.py` travaille dans un dossier temporaire sous C3. Il collecte, calcule et contrôle le candidat avant de modifier les données visibles. Une collecte incomplète, un échec R2 ou une station BdR admissible non classée bloque l'ajout. Un nouvel identifiant requérant une identification doit être vérifié dans le registre C3 ; sa résolution automatique complète reste à préparer. Aucune omission silencieuse n'est autorisée.

Le mode par défaut ne fait qu'un essai. Les écritures nécessitent à la fois `apply=true` au workflow et la variable GitHub `C3_DAILY_ENABLED=true`. Côté Cloudflare, `C3_ENABLED=false` et `crons=[]` sont fournis par défaut. Le token secret futur `C3_GH_DISPATCH_TOKEN` doit être limité au seul dépôt C3, avec lecture des contenus et lecture/écriture des Actions. Ne pas copier le secret du Worker C1/C2 dans les fichiers.

La collecte prend en charge les jours d'octobre, novembre et décembre 2026 et les rattrapages entre mois. Le passage annuel à 2027 est volontairement bloqué tant que les règles et archives annuelles n'ont pas été validées. Les contrôles de fraîcheur vérifient la présence de déclarations jusqu'à la journée demandée pour chacun des carburants et territoires nécessaires.

Les données déjà enregistrées sont conservées. Les sources et décisions de la nouvelle exécution sont proposées en artefacts GitHub avec rétention de **90 jours** ; un archivage plus long devra être choisi avant la production durable. L'échec garde la dernière page avec sa date précédente. GitHub signale l'échec ; les notifications externes ne sont pas configurées.

## Vérifications effectuées localement

```text
node cloudflare/test_worker.mjs
python -B test_automation.py
python -B test_current.py
node verify_ui.cjs
```

Ces tests couvrent les changements d'heure, le passage octobre/novembre, les demandes répétées, une file GitHub occupée, une erreur d'API et la conservation des données sur échec de collecte. Ce sont des simulations : aucun appel réel de dispatch, aucun essai de bout en bout Cloudflare/GitHub n'a été effectué.

Avant activation : créer le dépôt C3 dédié, faire un essai distant sans enregistrement, examiner son rapport, puis configurer le Worker dédié et ses secrets/crons. L'hébergement public du site et sa liaison au dépôt restent une étape distincte ; ce workflow prépare les fichiers statiques mais n'active aucun hébergement.

Références officielles : [Cloudflare Cron Triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/), [Scheduled handler](https://developers.cloudflare.com/workers/runtime-apis/handlers/scheduled/), [GitHub workflow dispatch et concurrence](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax).
