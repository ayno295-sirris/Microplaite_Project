# Protocole JSON V2 — première couche série

Base de la supervision : `1c1ac12bcfff54b8babf061be5465fc4deec3612`.
Base du boot failsafe : `acbd9b2ac3b538e44758e995c44da945dd511eb2`.
Transport actuel : `Serial` USB/UART, 115200 8N1. Aucun TCP ni Wi-Fi.

## Framing et validation

- Un objet JSON UTF-8 par ligne, terminé par LF ; un CR immédiatement avant LF est accepté.
- Maximum : 160 octets utiles, hors CRLF. Un dépassement est signalé au LF.
- Les commandes texte bench restent disponibles, avec leurs réponses historiques.
- L'ancien JSON sans version n'est plus accepté : `v` est obligatoire et doit valoir 2.
- `id` : nombre JSON entier signé sur 32 bits, de -2147483648 à 2147483647. Une écriture numérique comme `1.0` est acceptée si sa valeur décodée est entière.
- `cmd` : chaîne non vide, 23 caractères maximum, lettres A-Z, chiffres ou `_` ; sensible à la casse.
- Pas de conversion des chaînes/booléens en nombres. Les arguments numériques doivent être finis et dans les bornes indiquées.
- Les clés dupliquées à la racine sont rejetées. Les champs supplémentaires sont ignorés.
- Les CR intermédiaires, NUL, UTF-8 invalide et échappements Unicode invalides sont rejetés pour les lignes JSON. Les règles texte historiques ne changent pas.
- Une ligne commençant par `{` ne revient jamais au dispatcher texte en cas d'erreur.

## Requêtes

Chaque exemple est une ligne à terminer par LF, sans envoyer le bloc entier.

| Commande | Exemple | Règle / effet |
|---|---|---|
| PING | `{"v":2,"id":1,"cmd":"PING"}` | ACK, aucun effet matériel. |
| STATUS | `{"v":2,"id":2,"cmd":"STATUS"}` | État mémorisé ; aucune transaction RJ. |
| SYNC | `{"v":2,"id":17,"cmd":"SYNC"}` | Ouvre/renouvelle la session, sans activation ni effacement d'erreur. Refusé en FAULT. |
| HEARTBEAT | `{"v":2,"id":18,"cmd":"HEARTBEAT"}` | Rafraîchit une session encore ACTIVE ; ne réactive jamais une session perdue. |
| STOP | `{"v":2,"id":3,"cmd":"STOP"}` | Chauffage coupé et timer manuel annulé avant STOP pompe. |
| CLEAR_ERROR | `{"v":2,"id":4,"cmd":"CLEAR_ERROR"}` | Lecture thermique et conditions de réarmement existantes ; ne démarre aucun équipement. |
| HEATER_SET_TARGET | `{"v":2,"id":5,"cmd":"HEATER_SET_TARGET","target_c":37.5}` | 20 à 60 °C inclus. |
| HEATER_SET_PID | `{"v":2,"id":6,"cmd":"HEATER_SET_PID","kp":8,"ki":0.03,"kd":20}` | Trois nombres >= 0, représentables en float (`FLT_MAX` maximum) ; réinitialisation PID existante. |
| HEATER_SET_PID_LIMIT | `{"v":2,"id":7,"cmd":"HEATER_SET_PID_LIMIT","percent":15}` | Strictement > 0 après conversion float, et <= 100. |
| HEATER_SET_POWER_LIMIT | `{"v":2,"id":8,"cmd":"HEATER_SET_POWER_LIMIT","percent":30}` | 1 à 100 inclus ; limite du mode ON/OFF. |
| HEATER_ENABLE | `{"v":2,"id":9,"cmd":"HEATER_ENABLE","mode":"PID"}` | Session ACTIVE sans FAULT requise. Mode : `PID` ou `ONOFF`. Contrôle thermique frais identique au texte PID_ON / CONTROL_ON. |
| HEATER_DISABLE | `{"v":2,"id":10,"cmd":"HEATER_DISABLE"}` | Désactivation existante du chauffage. |
| PUMP_START | `{"v":2,"id":11,"cmd":"PUMP_START","rpm":3}` | Session ACTIVE sans FAULT requise. 0 à 100 inclus ; arrondi existant à 0,1 rpm. |
| PUMP_STOP | `{"v":2,"id":12,"cmd":"PUMP_STOP"}` | Séquence WJ STOP / réponse WJ / RJ existante. |
| PUMP_SET_RPM | `{"v":2,"id":13,"cmd":"PUMP_SET_RPM","rpm":5}` | Session ACTIVE sans FAULT requise. 0 à 100 inclus ; conserve les indicateurs de marche/full-speed mémorisés. |
| PUMP_PRIME | `{"v":2,"id":14,"cmd":"PUMP_PRIME"}` | Session ACTIVE sans FAULT requise. Prime existant, sans temporisation propre ajoutée. |
| PUMP_STATUS | `{"v":2,"id":15,"cmd":"PUMP_STATUS"}` | Déclenche un RJ. |
| NEOPIXEL_SET | `{"v":2,"id":16,"cmd":"NEOPIXEL_SET","enabled":true,"brightness":50}` | Deux champs obligatoires ; booléen strict et nombre 0 à 100, arrondi à l'entier comme en legacy. `enabled=true` exige une session ACTIVE sans FAULT ; `false` reste autorisé hors session. |

V2 ne permet pas d'activer MANUAL. Un test MANUAL lancé en texte reste visible dans STATUS.
Les commandes de réglage n'activent pas le chauffage.

## Réponses

Les réponses sont des objets JSON sur une ligne terminée par CRLF.

```json
{"v":2,"id":1,"type":"OK","cmd":"PING"}
{"v":2,"id":9,"type":"ERR","cmd":"HEATER_ENABLE","error":"BAD_MODE"}
```

Toutes les réponses pompe et STOP dont le `cmd` a pu être validé ajoutent les quatre champs pompe, y compris les erreurs :

```json
{"v":2,"id":12,"type":"OK","cmd":"PUMP_STOP","pump_running":false,"pump_rpm":0.1,"pump_full_speed":false,"pump_readback_valid":true}
```

Ces valeurs sont illustratives. `pump_readback_valid=false` signifie que les valeurs ne confirment pas l'état du contrôleur.
Un RJ valide confirme l'état rapporté par le contrôleur, pas une mesure de rotation physique.

- START / SET_RPM / PRIME : écriture WJ existante, readback invalidé, pas de RJ ajouté.
- STOP : chauffage arrêté en premier pour le STOP global ; aucune temporisation RS485 modifiée.
- Un échec d'écriture retourne `PUMP_WRITE_FAILED` avec les champs pompe.
- Un timeout/échec de readback après écriture, ou pendant PUMP_STATUS, reste `OK` avec `pump_readback_valid=false`.
- Une réponse RJ RUNNING après STOP est publiée telle quelle : running=true, readback_valid=true.
- Le readback n'expire pas automatiquement et aucun âge n'est ajouté.

## STATUS

Champs émis :

```text
v, id, type="STATUS", cmd="STATUS", uptime_ms
temp_c, temperature_available, temperature_valid, temperature_fault
heater_mode, heater_gpio_on, heater_target_c, heater_output_percent
thermal_test_mode, max_target_c, warning_temp_c, emergency_cutoff_c
power_limit_percent, pid_kp, pid_ki, pid_kd, pid_output_limit_percent, pid_integral
safety, last_error, error_latched
pump_running, pump_rpm, pump_full_speed, pump_readback_valid
neopixel_enabled, neopixel_brightness
system_state, comm_state, session_active, heartbeat_age_ms
```

`temp_c=null` si la mesure n'est pas valide. Une valeur flottante non finie provenant du legacy est aussi sérialisée en `null`, jamais en `nan`/`inf`/`ovf`.
`heater_mode` décrit le mode réel du service : IDLE, ONOFF, PID ou MANUAL ; `safety` est séparé (OK/WARNING/ERROR).
`heater_gpio_on` est l'état de sortie commandé, sans retour de mesure électrique.
Température et safety sont mémorisés par la boucle existante ; STATUS ne déclenche aucune lecture capteur/pompe.

## Session et états système

- États système : BOOT, IDLE, READY, RUNNING, FAULT.
- États communication : NO_SESSION, ACTIVE, LOST. `session_active` vaut true uniquement en ACTIVE.
- Après initialisation : NO_SESSION ; IDLE si aucune faute locale ni activité mémorisée. Le STOP pompe du boot conserve son readback réel : si RJ rapporte RUNNING, l'état reste RUNNING, sauf FAULT prioritaire.
- Un échec d'initialisation MAX31856 bloque le système en FAULT jusqu'à une nouvelle initialisation au redémarrage. Il ne modifie ni SafetyService ni les erreurs thermiques existantes.
- Une erreur thermique verrouillée ou `safety=ERROR` impose FAULT devant tout autre état. SYNC retourne SYSTEM_FAULT sans effacer l'erreur ni ouvrir/renouveler la session.
- Sinon, un mode chauffage ONOFF/PID/MANUAL ou `pumpRunning=true` impose RUNNING, même sans session ou sans readback pompe. NeoPixel ne participe pas à cette définition.
- Sans actionneur actif : READY si session ACTIVE, IDLE sinon.
- SYNC initialise `lastHeartbeatMs` et passe la communication ACTIVE. Il ne démarre rien ; un actionneur déjà actif en legacy reste observé comme RUNNING.
- HEARTBEAT n'est accepté qu'en session ACTIVE. Il maintient la communication même en FAULT, sans effacer ni masquer cette faute.
- RPi nominal : heartbeat toutes les 500 ms. À plus de 1000 ms, l'âge est informatif seulement : aucune transition ni coupure. Le client peut afficher le retard depuis `heartbeat_age_ms`.
- Timeout strict : soustraction non signée `now - lastHeartbeatMs > 3000`. Exactement 3000 ms n'expire pas la session. Le calcul couvre le débordement de millis().
- À expiration : LOST avant toute attente pompe. Si un actionneur est actif, appel au STOP global existant, chauffage d'abord puis pompe. Sans actionneur actif, aucune transaction pompe supplémentaire.
- Après arrêt : IDLE, sauf FAULT prioritaire ou pompe toujours indiquée RUNNING. Un STOP non confirmé ne doit pas masquer une indication de marche conservée après échec d'écriture ou RJ RUNNING.
- L'arrêt sur timeout est tenté une seule fois. Aucun redémarrage ni nouvelle tentative automatique. STOP explicite reste disponible.
- Un heartbeat tardif retourne NO_SESSION. Un nouveau SYNC est nécessaire, puis une commande explicite pour redémarrer. Les lectures/configurations/arrêts restent disponibles hors session ; HEATER_ENABLE, PUMP_START, PUMP_PRIME, PUMP_SET_RPM et NEOPIXEL_SET avec enabled=true sont verrouillés.
- `heartbeat_age_ms` est un entier en session ACTIVE, sinon null, y compris en LOST.
- STOP texte ou JSON reste accessible en FAULT et sans session ; il ne clear aucune erreur et ne renouvelle pas le heartbeat. Après arrêt, READY si ACTIVE, IDLE sans session, avec FAULT toujours prioritaire.
- Les commandes texte bench restent utilisables sans SYNC. Si une session a été ouverte, son timeout surveille aussi les actionneurs activés en texte ; après perte de session, une nouvelle activation texte reste un geste bench explicite.

Extrait de STATUS :

```json
{"system_state":"READY","comm_state":"ACTIVE","session_active":true,"heartbeat_age_ms":215}
```

La boucle traite la sécurité locale avant la supervision puis les commandes. La réception rend la main après une ligne ou 162 octets, même si le flux est continu. Le timeout reste coopératif : une lecture capteur ou transaction pompe déjà bloquante peut retarder sa détection. Dès détection, le chauffage est coupé avant l'attente RS485 ; les délais et trames Longer existants ne changent pas.

## Boot failsafe

- Première opération de `App::begin()` : `HeaterService::begin()` place le GPIO chauffage OFF, le mode IDLE, réinitialise le PID et annule le timer MANUAL. Aucun mode ni état antérieur n'est restauré.
- Ensuite, NeoPixel est initialisé OFF : état false, luminosité 0, buffer effacé puis transmis. En texte bench, un ON seul conserve cette luminosité nulle ; régler explicitement la luminosité pour éclairer.
- Après `PumpService::begin()`, un unique `PumpService::stop(_state)` est exécuté avant l'initialisation du service de commandes et de la session. Aucun START, PRIME ou rappel de vitesse.
- La séquence validée reste WJ STOP, attente de réponse WJ valide, puis RJ. Le budget d'attente existant partagé WJ/RJ est de 200 ms ; les écritures/flush UART et autres initialisations s'y ajoutent. Aucun retry ni délai supplémentaire n'est ajouté.
- Pompe absente : aucune réponse WJ, donc aucun RJ envoyé ; le budget expire et le boot continue, avec `pump_readback_valid=false`. Un échec d'écriture ou un RJ invalide/absent laisse également ce drapeau false. Aucun acquittement applicatif STOP réussi n'est émis au boot.
- Sans readback valide, `pump_running=false` représente uniquement la valeur initiale ou la consigne STOP : l'état du contrôleur est inconnu. Un état système IDLE ne constitue pas une confirmation d'arrêt physique. Aucune nouvelle faute pompe n'est inventée ; SYNC reste possible si les conditions locales existantes l'autorisent.
- Le boot finit sans session ; SYNC et une commande d'activation explicite sont nécessaires. SYNC seul ne rallume aucun équipement. Le timeout heartbeat >3000 ms et sa séquence heater.stop()/pump.stop() sont inchangés.
- Limite matérielle : aucune action logicielle pendant une absence d'alimentation ESP32, ni garantie GPIO avant l'exécution de l'initialisation. Le STOP au boot agit au redémarrage seulement. La sécurité pendant une déconnexion USB exige que la plateforme maintienne l'alimentation ESP32 indépendamment du lien USB de communication.

## Erreurs

| Code | Condition |
|---|---|
| MALFORMED_JSON | Syntaxe, encodage, échappement, CR intermédiaire ou NUL invalide. |
| LINE_TOO_LONG | Dépassement de 160 octets utiles. |
| DUPLICATE_FIELD | Clé répétée à la racine. |
| MISSING_ID / BAD_ID | ID absent ou type/valeur invalide. |
| MISSING_CMD / BAD_CMD | Commande absente ou nom/type invalide. |
| MISSING_VERSION / BAD_VERSION / UNSUPPORTED_VERSION | Version absente, type non entier, ou autre entier que 2. |
| MISSING_ARGUMENT / BAD_ARGUMENT_TYPE / OUT_OF_RANGE | Argument requis absent, mauvais type, ou valeur hors bornes/non finie. |
| BAD_MODE | Mode autre que PID/ONOFF. |
| UNKNOWN_COMMAND | Nom valide mais non implémenté. |
| NO_SESSION | HEARTBEAT ou commande d'activation sans session ACTIVE ; refaire SYNC. |
| SYSTEM_FAULT | SYNC ou commande d'activation refusée par une faute locale critique. |
| SYSTEM_NOT_READY | SYNC ou activation demandée avant la fin de l'initialisation. |
| SENSOR_INVALID / OVERTEMP | Conditions thermiques existantes d'activation/réarmement. |
| PUMP_WRITE_FAILED | Échec de construction/écriture de la commande pompe existante. |

Enveloppe/syntaxe non récupérable : `id=0`, `cmd="UNKNOWN"` ; après lecture valide, l'ID et le nom connus sont conservés dans l'erreur.
Les commandes texte conservent la sémantique thermique legacy, y compris OVERTEMP lors d'une nouvelle activation refusée sur erreur déjà verrouillée. En JSON V2, le verrou système prioritaire retourne SYSTEM_FAULT avant toute tentative d'activation si cette erreur est déjà présente.

## Hors périmètre et validation

La session RPi et son timeout sont gérés localement. Aucun token de session, mécanisme de reconnexion, TCP, Wi-Fi ni watchdog applicatif supplémentaire n'est ajouté.
LOG_ON/LOG_OFF et les diagnostics bruts restent sur le même flux série. Pour un client JSON, désactiver les logs legacy et savoir ignorer les diagnostics non JSON.

Les tests Unity `test/test_json_protocol/test_main.cpp` couvrent syntaxe, Unicode/UTF-8, enveloppe, doublons, types et bornes, sans initialiser de service matériel.
Ils restent à compiler/exécuter par Noam ; aucun build ni upload n'a été lancé pendant cette tâche.

Les tests Unity `test/test_supervision/test_main.cpp` exercent le vrai service avec une horloge passée explicitement et des doublures chauffage/pompe sans accès GPIO/RS485 : BOOT/IDLE, SYNC/READY, chaque source RUNNING, STOP/READY ou IDLE, heartbeat, seuils 1000/3000/3001, perte de session, ordre de coupure, absence de reprise, priorité FAULT, panne d'initialisation, STOP pompe échoué et débordement millis(). Ils ne sont pas exécutés pendant cette tâche. Garder `test_build_src=false` (configuration existante) : ce test inclut le service sous test et remplace uniquement ses dépendances matérielles à l'édition des liens.

Les six tests statiques `python -B test/test_boot_contract.py` vérifient le câblage des appels dans les sources : chauffage OFF en premier, STOP pompe avant les commandes, NeoPixel OFF, NO_SESSION/sans reprise, verrou V2 NeoPixel et séquence heartbeat conservée. Ils s'exécutent sans compilation ni accès matériel ; ils ne remplacent ni les tests C++ ni la validation au banc.

Revue bench à effectuer par Noam après compilation :

1. PING/STATUS : vérifier v/id, température null si invalide, absence de RJ pour STATUS.
2. PUMP_STATUS puis STOP : vérifier la qualification `pump_readback_valid` et le chauffage coupé avant la transaction pompe.
3. Entrées invalides : version absente, id chaîne/décimal non entier, rpm hors plage, mode MANUAL, argument PID manquant, NeoPixel enabled numérique. Aucune action sur argument invalide.
4. Framing : PING avec LF puis CRLF ; CR au milieu d'une commande JSON et NUL avant garbage doivent donner MALFORMED_JSON. Après une ligne trop longue, la ligne suivante doit fonctionner.
5. Avant SYNC, HEATER_ENABLE/PUMP_START/PUMP_PRIME/PUMP_SET_RPM et NEOPIXEL_SET avec enabled=true doivent retourner NO_SESSION. Après SYNC, vérifier READY puis RUNNING lors d'une activation chauffage/pompe et READY après STOP.
6. Envoyer HEARTBEAT toutes les 500 ms ; suspendre à plus de 1000 ms sans arrêt anticipé, puis dépasser 3000 ms pour vérifier LOST et l'arrêt. Un heartbeat seul ne réarme pas ; SYNC puis une activation explicite sont nécessaires.
7. Avec une faute locale présente, vérifier que SYNC ne clear rien et que HEARTBEAT/STOP/timeout ne masquent jamais FAULT. Vérifier STATUS/LOG_STATUS/HELP texte inchangés.
8. Au reboot, vérifier chauffage OFF, NeoPixel OFF/0, demande STOP pompe et NO_SESSION. Sans pompe, le boot doit continuer et STATUS afficher pump_readback_valid=false, sans prétendre confirmer l'arrêt. Une reconnexion/SYNC seule ne doit rien réactiver.
