# Protocole JSON V2 — première couche série

Base : `d62190e1e4eb97471197c8256312cfc05d7a79ba`.
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
| STOP | `{"v":2,"id":3,"cmd":"STOP"}` | Chauffage coupé et timer manuel annulé avant STOP pompe. |
| CLEAR_ERROR | `{"v":2,"id":4,"cmd":"CLEAR_ERROR"}` | Lecture thermique et conditions de réarmement existantes ; ne démarre aucun équipement. |
| HEATER_SET_TARGET | `{"v":2,"id":5,"cmd":"HEATER_SET_TARGET","target_c":37.5}` | 20 à 60 °C inclus. |
| HEATER_SET_PID | `{"v":2,"id":6,"cmd":"HEATER_SET_PID","kp":8,"ki":0.03,"kd":20}` | Trois nombres >= 0, représentables en float (`FLT_MAX` maximum) ; réinitialisation PID existante. |
| HEATER_SET_PID_LIMIT | `{"v":2,"id":7,"cmd":"HEATER_SET_PID_LIMIT","percent":15}` | Strictement > 0 après conversion float, et <= 100. |
| HEATER_SET_POWER_LIMIT | `{"v":2,"id":8,"cmd":"HEATER_SET_POWER_LIMIT","percent":30}` | 1 à 100 inclus ; limite du mode ON/OFF. |
| HEATER_ENABLE | `{"v":2,"id":9,"cmd":"HEATER_ENABLE","mode":"PID"}` | Mode obligatoire : `PID` ou `ONOFF`. Contrôle thermique frais identique au texte PID_ON / CONTROL_ON. |
| HEATER_DISABLE | `{"v":2,"id":10,"cmd":"HEATER_DISABLE"}` | Désactivation existante du chauffage. |
| PUMP_START | `{"v":2,"id":11,"cmd":"PUMP_START","rpm":3}` | 0 à 100 inclus ; arrondi existant à 0,1 rpm. |
| PUMP_STOP | `{"v":2,"id":12,"cmd":"PUMP_STOP"}` | Séquence WJ STOP / réponse WJ / RJ existante. |
| PUMP_SET_RPM | `{"v":2,"id":13,"cmd":"PUMP_SET_RPM","rpm":5}` | 0 à 100 inclus ; conserve les indicateurs de marche/full-speed mémorisés. |
| PUMP_PRIME | `{"v":2,"id":14,"cmd":"PUMP_PRIME"}` | Prime existant, sans temporisation ajoutée. |
| PUMP_STATUS | `{"v":2,"id":15,"cmd":"PUMP_STATUS"}` | Déclenche un RJ. |
| NEOPIXEL_SET | `{"v":2,"id":16,"cmd":"NEOPIXEL_SET","enabled":true,"brightness":50}` | Deux champs obligatoires ; booléen strict et nombre 0 à 100, arrondi à l'entier comme en legacy. |

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
```

`temp_c=null` si la mesure n'est pas valide. Une valeur flottante non finie provenant du legacy est aussi sérialisée en `null`, jamais en `nan`/`inf`/`ovf`.
`heater_mode` décrit le mode réel du service : IDLE, ONOFF, PID ou MANUAL ; `safety` est séparé (OK/WARNING/ERROR).
`heater_gpio_on` est l'état de sortie commandé, sans retour de mesure électrique.
Température et safety sont mémorisés par la boucle existante ; STATUS ne déclenche aucune lecture capteur/pompe.

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
| NOT_IMPLEMENTED | SYNC et HEARTBEAT réservés. |
| SENSOR_INVALID / OVERTEMP | Conditions thermiques existantes d'activation/réarmement. |
| PUMP_WRITE_FAILED | Échec de construction/écriture de la commande pompe existante. |

Enveloppe/syntaxe non récupérable : `id=0`, `cmd="UNKNOWN"` ; après lecture valide, l'ID et le nom connus sont conservés dans l'erreur.
Les erreurs thermiques verrouillées conservent la sémantique legacy, y compris OVERTEMP lors d'une nouvelle activation refusée sur erreur déjà verrouillée.

## Hors périmètre et validation

SYNC et HEARTBEAT répondent NOT_IMPLEMENTED ; aucun bail, timeout RPi, watchdog applicatif, reconnexion, TCP ou machine d'états système n'est ajouté.
LOG_ON/LOG_OFF et les diagnostics bruts restent sur le même flux série. Pour un client JSON, désactiver les logs legacy et savoir ignorer les diagnostics non JSON.

Les tests Unity `test/test_json_protocol/test_main.cpp` couvrent syntaxe, Unicode/UTF-8, enveloppe, doublons, types et bornes, sans initialiser de service matériel.
Ils restent à compiler/exécuter par Noam ; aucun build ni upload n'a été lancé pendant cette tâche.

Revue bench à effectuer par Noam après compilation :

1. PING/STATUS : vérifier v/id, température null si invalide, absence de RJ pour STATUS.
2. PUMP_STATUS puis STOP : vérifier la qualification `pump_readback_valid` et le chauffage coupé avant la transaction pompe.
3. Entrées invalides : version absente, id chaîne/décimal non entier, rpm hors plage, mode MANUAL, argument PID manquant, NeoPixel enabled numérique. Aucune action sur argument invalide.
4. Framing : PING avec LF puis CRLF ; CR au milieu d'une commande JSON et NUL avant garbage doivent donner MALFORMED_JSON. Après une ligne trop longue, la ligne suivante doit fonctionner.
5. SYNC/HEARTBEAT : NOT_IMPLEMENTED ; puis commandes texte de lecture STATUS/LOG_STATUS/HELP inchangées.
