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
### 5️⃣ `analyse_lidr.R`

**But**  
Analyse forestière à partir d’un nuage de points LiDAR ou photogrammétrique.

**Fonctionnalités**
- Lecture de fichiers `.laz` (LiDAR HD IGN ou WebODM).
- Découpage spatial de la zone d’étude.
- Classification du sol.
- Calcul du Modèle Numérique de Terrain (DTM).
- Normalisation des hauteurs.
- Génération du **Canopy Height Model (CHM)**.
- Détection automatique des arbres.
- Calcul de la hauteur de chaque arbre.
- Export des résultats en **GeoJSON**.

**Bibliothèques utilisées**
- `lidR`
- `sf`
- `terra`

⚠️ Les fichiers `.laz` ne sont pas inclus dans le dépôt GitHub en raison de leur taille.
## 🗺️ Données LiDAR (.LAZ)

Les données LiDAR utilisées pour les tests et l’analyse proviennent de **sources publiques officielles** :

- **IGN – LiDAR HD (France)**  
  - https://geoservices.ign.fr/lidarhd  
  - https://cartes.gouv.fr/telechargement/IGNF_NUAGES-DE-POINTS-LIDAR-HD  

Les fichiers doivent être **téléchargés localement** puis référencés dans le script `analyse_lidr.R`.



## ⚡ Installation et exécution

1. Installer Python 3.8+.
2. Installer les dépendances :  
```bash
pip install PyQt5 PyQtWebEngine simplekml geopy
