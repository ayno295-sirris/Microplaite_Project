# Guide d'utilisation MICROPLAITE

Ce guide décrit l'application Raspberry Pi candidate à la livraison. L'ESP32
reste l'autorité pour le contrôle temps réel, le PID et la mise en sécurité.

## Démarrage et connexion

L'application démarre automatiquement en plein écran après l'ouverture de la
session graphique du Raspberry Pi. Le lancement manuel utilise le même lanceur :

```bash
/home/nayo/dev/Microplaite_project/rpi5/raspberrypi5/scripts/launch_microplaite_ui.sh --fullscreen
```

L'application détecte d'abord les ports USB ESP32, puis utilise `/dev/serial0`
en dernier recours. Si l'ESP32 n'est pas disponible, l'interface reste ouverte
et affiche `DISCONNECTED` ou `LOST`.

Après avoir connecté ou reconnecté le câble USB, appuyer sur `RECONNECT`. Cette
action ouvre une nouvelle session, exécute PING, STATUS et SYNC, puis démarre le
heartbeat. Elle ne redémarre ni la pompe, ni le chauffage, ni une recette. Il
n'existe pas de reconnexion ou de reprise automatique.

## Arrêt global et fermeture

Le bouton rouge `STOP` interrompt la recette et demande un arrêt global à
l'ESP32. En cas de perte USB, la mise en sécurité est assurée par la supervision
de l'ESP32; le Raspberry Pi ne peut plus transmettre de commande sur un câble
débranché.

Pour quitter proprement, maintenir le titre `MICROPLAITE CONTROL` pendant environ
3 secondes, puis choisir `QUIT APPLICATION`. La fermeture arrête le time-lapse et
le Live, ferme le fichier CSV actif, annule les changements de pompe en attente et
libère le port série. Elle ne provoque pas un redémarrage immédiat de
l'application.

## Température et chauffage

- La température et la courbe proviennent des STATUS V2 de l'ESP32.
- Régler la consigne, puis utiliser `START` pour activer le PID.
- La consigne UI est limitée de 0 à 60 °C.
- Les paramètres utilisés par cette version sont `Kp=8.0`, `Ki=0.03`, `Kd=20.0`.
- La limite de sortie PID demandée par l'UI est 15 %.
- Utiliser `STOP PID` ou le `STOP` global avant toute intervention.

Ne jamais considérer l'affichage Raspberry Pi comme un remplacement des sécurités
thermiques et défauts de sonde de l'ESP32.

## Pompe bidirectionnelle

La consigne signée va de -100,0 à +100,0 RPM :

- une valeur positive demande le sens CW;
- une valeur négative demande le sens CCW;
- zéro demande l'arrêt;
- `START` démarre explicitement la pompe avec la consigne préparée;
- `STOP PUMP` arrête la pompe;
- `PRIME` utilise la commande de priming existante.

Quand la pompe tourne, le curseur et le champ RPM mettent à jour la consigne sans
bloquer l'interface. Lors d'un changement de sens, l'application arrête d'abord la
pompe, exige un readback récent confirmant l'arrêt, puis redémarre dans le nouveau
sens. Un STOP opérateur, LOST, FAULT ou la fermeture annule tout redémarrage en
attente. Sur un ancien firmware sans capability bidirectionnelle, une consigne
négative est refusée.

Les champs `Requested direction`, `Reported direction` et le readback permettent
de distinguer la demande de l'état réellement confirmé.

## Caméra et Live

`START LIVE` ouvre l'unique service caméra existant. Le tableau de bord affiche
uniquement une image Live actuelle, une image de la session time-lapse en cours,
ou le message `No active preview`; il ne réutilise pas une ancienne capture comme
si elle était active.

L'enregistrement vidéo est optionnel. Activer `Record video`, choisir le stockage,
puis démarrer et arrêter le Live. `STOP LIVE` arrête la vidéo et éteint
immédiatement le NeoPixel.

## NeoPixel

- `LED ON` et `LED OFF` fonctionnent avec ou sans Live.
- `START LIVE` allume automatiquement le NeoPixel avec la luminosité choisie.
- `STOP LIVE` l'éteint immédiatement.
- Une luminosité de 0 % peut être rapportée comme `enabled=true`, sans lumière
  visible.
- Le firmware compatible éteint automatiquement le NeoPixel après 120 secondes
  d'éclairage continu.
- `Keep NeoPixel On` désactive volontairement cette limite. La case est décochée
  par défaut et n'est activable que si l'ESP32 annonce
  `neopixel_auto_off_supported=true`.
- Cocher `Keep NeoPixel On` lorsque les LED sont éteintes mémorise seulement le
  prochain mode Live; cela n'allume pas les LED.
- Un ancien firmware conserve ON/OFF, mais la case Keep On reste désactivée et
  l'application ne prétend pas fournir l'extinction automatique.

Il n'existe aucun second timer NeoPixel dans le Raspberry Pi. L'état STATUS de
l'ESP32 est autoritaire. Les captures time-lapse conservent toujours leur séquence
indépendante ON, stabilisation, capture, OFF.

## Time-lapse

Choisir le stockage, l'intervalle, la luminosité, la stabilisation et la durée,
puis appuyer sur `START TIMELAPSE`.

- La stabilisation LED vaut 2 500 ms par défaut et se règle en millisecondes.
- L'intervalle doit être strictement supérieur à la stabilisation.
- Les échéances restent espacées selon l'intervalle nominal : le délai de
  stabilisation ne s'ajoute pas à chaque cycle.
- Une échéance dépassée est ignorée; aucune capture concurrente de rattrapage
  n'est lancée.
- `STOP TIMELAPSE` interrompt la session et éteint le NeoPixel.

Le stockage interne est `~/Microplaite/timelapse/`. Les vidéos sont placées dans
`~/Microplaite/video/`. En mode externe, les données vont dans un dossier
`Microplaite` du premier volume inscriptible détecté sous `/media` ou `/mnt`.
L'application exige au moins 50 Mio libres.

## Logging CSV

Le bouton de logging crée un fichier UTF-8 directement exploitable par Excel,
LibreOffice ou pandas dans :

```text
~/MicroplaiteData/logs/microplaite_YYYY-MM-DD_HHMMSS.csv
```

Une ligne est écrite pour chaque STATUS V2 déjà reçu; aucune seconde boucle STATUS
n'est créée. Arrêter le logging avant de retirer un support. LOST et la fermeture
flushent et ferment le fichier. Le diagnostic d'autostart est conservé dans
`~/MicroplaiteData/logs/autostart.log`.

## Recettes

Les recettes JSON se trouvent dans `~/MicroplaiteData/recipes/`. Sélectionner une
recette, puis utiliser `START RECIPE`. L'interface indique le nom, l'étape et la
progression. Les actions supportées couvrent la température, PID ON/OFF, pompe,
attentes, attente de température et NeoPixel.

Une recette est strictement séquentielle. STOP, LOST, FAULT ou un timeout
`WAIT_TEMPERATURE` la terminent sans reprise automatique. Après une reconnexion,
la recette doit être redémarrée explicitement.

## Maintenance et fichiers utilisateur

Un appui long d'environ 3 secondes sur `MICROPLAITE CONTROL` ouvre le menu
Maintenance : plein écran, mode fenêtré, fermeture ou annulation. Un appui court
ne fait rien.

Les préférences sont stockées dans
`~/.config/microplaite_control/preferences.json`. Avant expédition ou maintenance,
sauvegarder ce fichier ainsi que `~/MicroplaiteData/`, `~/Microplaite/timelapse/`
et `~/Microplaite/video/` si leurs données doivent être conservées.

## Validation matérielle restante

Le support logiciel du contrat NeoPixel auto-off/Keep On est couvert par les
tests. La validation physique des 120 secondes et de Keep On doit être effectuée
après flash du firmware ESP32 compatible. Les essais de pompe et de chauffage
doivent rester supervisés par l'opérateur.
