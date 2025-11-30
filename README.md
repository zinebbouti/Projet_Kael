# Projet Kael – Générateur de Waypoints pour Missions Drones

Ce projet permet de créer et gérer des missions pour drones, avec génération automatique de waypoints et export KML/KMZ pour planification de vol.

---

## 📂 Structure du projet

### 1. `codekael.py`
- **But** : Interface graphique pour sélectionner une zone sur une carte et générer automatiquement les waypoints.
- **Modules utilisés** :
  - `PyQt5` : pour l'interface graphique et l'affichage de la carte.
  - `simplekml` : création de fichiers KML/KMZ.
  - `math` : calculs géographiques.
  - `zipfile` : compression du fichier KML en KMZ.
- **Fonctionnalités principales** :
  1. Affiche une carte OpenStreetMap via Leaflet.
  2. Permet de cliquer sur 4 points pour définir un rectangle de mission.
  3. Calcule les waypoints en fonction de la hauteur de vol et des recouvrements frontal et latéral.
  4. Crée et sauvegarde un fichier KML et un fichier KMZ avec la trajectoire et les waypoints.
  5. Affiche le nombre de passes, points par passe et total de waypoints.

---

### 2. `gps.py`
- **But** : Obtenir les coordonnées GPS (latitude et longitude) à partir d'une adresse.
- **Modules utilisés** :
  - `geopy` : géocodage via l'API OpenStreetMap/Nominatim.
- **Fonctionnalités** :
  - Transforme une adresse (ex : "enseirb-matmeca") en coordonnées GPS.
  - Affiche la latitude et la longitude correspondantes.
  - Utile pour définir des points de référence pour les missions.

---

### 3. `mission.py`
- **But** : Générer un exemple simple de mission autour d’un point central.
- **Modules utilisés** :
  - `simplekml` : création de fichiers KML.
  - `zipfile` : création de fichier KMZ compressé.
- **Fonctionnalités** :
  1. Définit un point central (exemple : lycée) et une petite trajectoire autour.
  2. Crée 5 waypoints pour la mission.
  3. Génère un fichier KML avec les points et la trajectoire.
  4. Compresse le fichier KML en KMZ prêt à l’usage dans un logiciel de planification de vol.

---

## ⚡ Installation et exécution

1. Installer Python 3.8+.
2. Installer les dépendances :  
```bash
pip install PyQt5 PyQtWebEngine simplekml geopy
