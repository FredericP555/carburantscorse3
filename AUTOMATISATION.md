# Mise à jour et publication de C3

## Composants indépendants

- Worker Cloudflare : **a4c-c3-scheduler**.
- Dépôt ciblé : **FredericP555/carburantscorse3** exclusivement.
- Collecte et calcul : `.github/workflows/update-daily.yml`.
- Publication GitHub Pages : `.github/workflows/static.yml`, dossier `maquette/dist`.

Le Worker existant `a4c-scheduler` et les dépôts C1/C2 ne sont pas modifiés.

## Configuration Cloudflare

Le fichier `cloudflare/wrangler.toml` décrit la configuration de production prévue :

- `C3_ENABLED = "true"`.
- `C3_PARIS_SLOTS = "07:37,10:37,14:37"`.
- Déclencheur `37 * * * *` : appel chaque heure à la minute 37, puis sélection des trois créneaux en heure de Paris par le code, été comme hiver.
- Secret `C3_GH_DISPATCH_TOKEN`, limité au dépôt C3 : Contents en lecture, Actions en lecture/écriture. Ne jamais placer ce secret dans les fichiers.

Une modification du code du dépôt ne redéploie pas automatiquement le Worker créé manuellement dans Cloudflare. **Les corrections du Worker doivent y être déployées explicitement.** Le jeton expire selon la durée choisie lors de sa création ; le renouveler avant cette date.

L’adresse HTTP du Worker donne un état en lecture seule. `enabled=true` décrit sa variable d’activation ; cela ne prouve ni l’exécution d’un cron ni la réussite d’un appel GitHub. La réponse ne révèle pas le jeton.

## Décision de lancement

Avant de collecter, le Worker vérifie la date dans `data/current.json` et les exécutions en attente ou en cours. Il ne demande pas une collecte en double. Un lancement accepté par l’API GitHub peut néanmoins attendre un runner.

Si le dépôt est à jour mais que la version publique manque, diffère ou que la dernière publication a échoué, le Worker corrigé peut demander uniquement `static.yml`. Cette capacité nécessite le redéploiement du code Cloudflare. Une vérification GitHub horaire à la minute 53 sert également de secours de publication ; elle ne collecte aucune donnée et ne republie que si les fichiers publics diffèrent.

## Collecte et enregistrement

Le workflow reçoit une journée attendue et l’option `apply`. Les écritures exigent `apply=true` **et** la variable GitHub `C3_DAILY_ENABLED=true`. La concurrence des écritures est sérialisée.

`daily_refresh.py` travaille dans un dossier temporaire, collecte les archives officielles et UFIP, calcule le candidat puis exécute les contrôles avant d’enregistrer les données visibles. En cas d’échec, les dernières données restent en place. Les nouveaux identifiants nécessitant une identification sont contrôlés dans le registre propre à C3 ; une enseigne actuelle n’est pas attribuée arbitrairement aux journées antérieures.

Les archives annuelles couvrent l’historique nécessaire depuis 2025. L’URL dépend de l’année réelle de collecte, y compris pour une journée du 31 décembre collectée en janvier. Les tests du changement d’année utilisent des sources simulées ; un premier passage réel doit être surveillé.

Les comparaisons Total SP95 masquées ne doivent pas empêcher la publication des séries effectivement affichées. Les effectifs et motifs d’exclusion restent traçables dans les sorties d’audit.

## Publication et vérification publique

Le workflow Pages se déclenche après un changement du site, une mise à jour quotidienne réussie, une demande explicite ou la vérification horaire de secours. Le contrôle de publication compare la dernière date et les empreintes des fichiers au manifeste public `site-manifest.json`. Si aucune différence n’est trouvée, aucun déploiement n’est nécessaire.

Le déploiement utilise le commit inspecté. Les permissions d’écriture Pages et d’identité sont limitées au travail de déploiement ; les autres vérifications restent en lecture. Le manifeste décrit les fichiers de ce déploiement.

Les ressources du site possèdent une URL basée sur leur empreinte pour limiter les anciennes versions conservées par le navigateur. La page affiche la dernière journée réellement disponible ; elle ne prétend pas qu’un traitement en attente a déjà réussi.

## Audit et limites

Chaque exécution conserve les sources, décisions et rapports dans un artefact GitHub **90 jours**. Un archivage durable au-delà de cette durée reste à définir. La présence d’un artefact ne suffit pas : examiner `result.json`, les contrôles et, après publication, le site public.

Les notifications d’échec GitHub dépendent des préférences du compte. Aucun canal d’alerte externe n’est configuré. Cloudflare ne garantit pas l’heure de démarrage d’un runner GitHub. La liaison réelle doit être validée par un événement Cloudflare observé, le workflow correspondant et la date du site ; la seule réponse HTTP du Worker ne suffit pas.

Contrôles disponibles :

```text
python -B test_automation.py
python -B test_regressions.py
python -B test_year_rollover.py
python -B test_pages_health.py
python -B test_collect_current.py
node cloudflare/test_worker.mjs
python -B build_mockup.py
python -B verify_mockup.py
node verify_ui.cjs
```

Les tests couvrent notamment les doublons, erreurs d’API, changements d’heure et d’année simulés, conservation des données en cas d’échec, publication en retard et exports. Les tests DOM simulés ne constituent pas un contrôle visuel navigateur.
