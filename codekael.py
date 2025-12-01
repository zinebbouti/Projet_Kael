import sys
import math
from zipfile import ZipFile

from PyQt5.QtWidgets import QApplication, QInputDialog, QMessageBox
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QObject, pyqtSlot
from PyQt5.QtWebChannel import QWebChannel

import simplekml
from geopy.geocoders import Nominatim

# ---------------------------
# Fonction pour géolocaliser un lieu
# ---------------------------
def get_location_coordinates(place_name):
    geolocator = Nominatim(user_agent="gps_simulation")
    location = geolocator.geocode(place_name)
    if location:
        return location.latitude, location.longitude
    else:
        return None, None

# ---------------------------
# HTML de la carte avec placeholders pour latitude et longitude
# ---------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>Carte Rectangle - Mission Drone</title>
<style>
    html, body, #map {{ height: 100%; margin: 0; padding: 0; }}
    .control-panel {{
        position: absolute;
        top: 10px;
        right: 10px;
        z-index: 1000;
        background: white;
        padding: 10px;
        border-radius: 5px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.3);
    }}
    .control-panel button {{
        display: block;
        width: 100%;
        margin: 5px 0;
        padding: 8px;
        cursor: pointer;
        border: none;
        border-radius: 3px;
        font-size: 14px;
    }}
    #validate {{ background: #4CAF50; color: white; }}
    #validate:hover {{ background: #45a049; }}
    #validate:disabled {{ background: #cccccc; cursor: not-allowed; }}
    #reset {{ background: #f44336; color: white; }}
    #reset:hover {{ background: #da190b; }}
    #info {{
        position: absolute;
        bottom: 10px;
        left: 10px;
        z-index: 1000;
        background: white;
        padding: 10px;
        border-radius: 5px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.3);
        font-family: Arial, sans-serif;
        font-size: 12px;
    }}
</style>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
</head>
<body>
<div id="map"></div>
<div class="control-panel">
    <button id="validate" disabled>Valider Rectangle</button>
    <button id="reset">Réinitialiser</button>
</div>
<div id="info">Cliquez sur 4 points pour définir le rectangle</div>

<script>
var map = L.map('map').setView([{lat}, {lon}], 15);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png').addTo(map);

var polygon = null;
var markers = [];
var pointCount = 0;
var bridge = null;

// Initialiser le bridge
new QWebChannel(qt.webChannelTransport, function (channel) {{
    bridge = channel.objects.bridge;
}});

// Gestion des clics sur la carte
map.on('click', function (e) {{
    if (pointCount < 4 && bridge) {{
        // Ajouter un marqueur
        var marker = L.circleMarker([e.latlng.lat, e.latlng.lng], {{
            radius: 6,
            color: '#2196F3',
            fillColor: '#2196F3',
            fillOpacity: 0.8
        }}).addTo(map);
        marker.bindPopup('Point ' + (pointCount + 1)).openPopup();
        markers.push(marker);
        
        // Envoyer le point au bridge
        bridge.sendPoint(e.latlng.lat, e.latlng.lng);
        pointCount++;
        
        // Mettre à jour l'info
        if (pointCount < 4) {{
            document.getElementById('info').textContent = 
                'Point ' + pointCount + '/4 enregistré. Cliquez pour ajouter le point suivant.';
        }} else {{
            document.getElementById('info').textContent = 
                'Rectangle défini. Cliquez sur "Valider Rectangle" pour générer les waypoints.';
            document.getElementById('validate').disabled = false;
        }}
    }}
}});

// Bouton de validation
document.getElementById('validate').addEventListener('click', function() {{
    if (bridge && pointCount === 4) {{
        bridge.validateRectangle();
    }}
}});

// Bouton de réinitialisation
document.getElementById('reset').addEventListener('click', function() {{
    if (bridge) {{
        bridge.resetPoints();
        // Nettoyer la carte
        markers.forEach(function(m) {{ map.removeLayer(m); }});
        markers = [];
        if (polygon) {{ map.removeLayer(polygon); polygon = null; }}
        map.eachLayer(function(layer) {{
            if (layer instanceof L.CircleMarker || layer instanceof L.Polyline) {{
                if (layer !== markers[0] && !markers.includes(layer)) {{
                    map.removeLayer(layer);
                }}
            }}
        }});
        pointCount = 0;
        document.getElementById('validate').disabled = true;
        document.getElementById('info').textContent = 'Cliquez sur 4 points pour définir le rectangle';
    }}
}});
</script>
</body>
</html>
"""

# ---------------------------
# Fonction pour valider le rectangle
# ---------------------------
def validate_rectangle(points):
    """Vérifie si les 4 points forment approximativement un rectangle"""
    if len(points) != 4:
        return False, "Il faut exactement 4 points."
    
    # Calculer les distances entre points consécutifs
    distances = []
    for i in range(4):
        p1 = points[i]
        p2 = points[(i + 1) % 4]
        dist = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
        distances.append(dist)
    
    # Les côtés opposés doivent être approximativement égaux (tolérance 20%)
    ratio1 = abs(distances[0] - distances[2]) / max(distances[0], distances[2])
    ratio2 = abs(distances[1] - distances[3]) / max(distances[1], distances[3])
    
    if ratio1 > 0.2 or ratio2 > 0.2:
        return False, "Les points ne forment pas un rectangle régulier. Les côtés opposés doivent être approximativement égaux."
    
    return True, "Rectangle valide."

# ---------------------------
# Fonction pour générer des waypoints avec calcul FOV amélioré
# ---------------------------
def generate_waypoints(rect_points, altitude, frontal_cov, lateral_cov,
                       sensor_width, sensor_height, focal_length):
    """
    Génère les waypoints pour un rectangle orienté.
    
    rect_points : liste de 4 points [(lat, lon), ...] dans l'ordre autour du rectangle
    altitude : hauteur de vol
    frontal_cov : recouvrement frontal (0-1)
    lateral_cov : recouvrement latéral (0-1)
    sensor_width/height : dimensions du capteur en mm
    focal_length : focale de l'objectif en mm
    """
    """
    Génération de waypoints avec repère local par ligne.
    rect_points : liste des 4 coins du rectangle dans l'ordre P0,P1,P2,P3
    P0--P1
    |   |
    P3--P2
    """

    import math

    P0, P1, P2, P3 = rect_points

    def distance_m(pA, pB):
        lat_avg = (pA[0]+pB[0])/2
        dx = (pB[1]-pA[1]) * 111000 * math.cos(math.radians(lat_avg))
        dy = (pB[0]-pA[0]) * 111000
        return math.sqrt(dx*dx + dy*dy)

    # FOV caméra
    fov_width  = 2 * altitude * (sensor_width / (2 * focal_length))
    fov_height = 2 * altitude * (sensor_height / (2 * focal_length))
    dy = fov_height * (1 - lateral_cov)

    # nombre de lignes selon dy
    Ly_total = distance_m(P0, P3)
    Ny = max(1, int(math.ceil(Ly_total / dy)))

    waypoints = []

    for iy in range(Ny + 1):
        frac_y = iy / Ny
        # calcul des points gauche et droite de cette ligne
        left_lat  = P0[0] + frac_y * (P3[0]-P0[0])
        left_lon  = P0[1] + frac_y * (P3[1]-P0[1])
        right_lat = P1[0] + frac_y * (P2[0]-P1[0])
        right_lon = P1[1] + frac_y * (P2[1]-P1[1])

        # longueur de la ligne
        Lx_line = distance_m((left_lat,left_lon), (right_lat,right_lon))
        dx = fov_width * (1 - frontal_cov)
        Nx = max(1, int(math.ceil(Lx_line / dx)))

        for ix in range(Nx + 1):
            frac_x = ix / Nx
            lat = left_lat + frac_x * (right_lat - left_lat)
            lon = left_lon + frac_x * (right_lon - left_lon)
            waypoints.append((lat, lon, altitude))

        # serpentin
        if iy % 2 == 1:
            waypoints[-(Nx + 1):] = reversed(waypoints[-(Nx + 1):])

    # retour au point de départ
    waypoints.append((P0[0], P0[1], altitude))

    return waypoints, Nx + 1, Ny + 1, fov_width, fov_height



# ---------------------------
# Classe Bridge PyQt5
# ---------------------------
class Bridge(QObject):
    def __init__(self, view, altitude, frontal_cov, lateral_cov, 
                 sensor_width, sensor_height, focal_length):
        super().__init__()
        self.view = view
        self.points = []
        self.altitude = altitude
        self.frontal_cov = frontal_cov
        self.lateral_cov = lateral_cov
        self.sensor_width = sensor_width
        self.sensor_height = sensor_height
        self.focal_length = focal_length

    @pyqtSlot(float, float)
    def sendPoint(self, lat, lng):
        print(f"Point {len(self.points) + 1} enregistré: {lat:.6f}, {lng:.6f}")
        self.points.append([lat, lng])

        if len(self.points) == 4:
            # Créer le polygone sur la carte
            js = f"""
                var pts = {self.points + [self.points[0]]};
                if (polygon) map.removeLayer(polygon);
                polygon = L.polygon(pts, {{
                    color:'blue', 
                    fillColor:'blue', 
                    fillOpacity:0.2,
                    weight: 2
                }}).addTo(map);
                map.fitBounds(polygon.getBounds());
            """
            self.view.page().runJavaScript(js)
            print("Rectangle défini avec 4 points")

    @pyqtSlot()
    def validateRectangle(self):
        if len(self.points) != 4:
            QMessageBox.warning(self.view, "Erreur", "Veuillez sélectionner exactement 4 points.")
            return
        
        # Valider le rectangle
        is_valid, message = validate_rectangle(self.points)
        if not is_valid:
            QMessageBox.warning(self.view, "Rectangle invalide", message)
            return
        
        print("Validation du rectangle...")
        
        # Générer les waypoints
        waypoints, nx, ny, fov_w, fov_h = generate_waypoints(
            self.points, self.altitude, self.frontal_cov, self.lateral_cov,
            self.sensor_width, self.sensor_height, self.focal_length
        )
        
        # Afficher les waypoints sur la carte
        waypoints_coords = [[lat, lon] for lat, lon, _ in waypoints]
        js_show_waypoints = f"""
            // Supprimer les anciens waypoints
            map.eachLayer(function(layer) {{
                if (layer instanceof L.CircleMarker && layer.options.className === 'waypoint') {{
                    map.removeLayer(layer);
                }}
                if (layer instanceof L.Polyline && layer.options.className === 'trajectory') {{
                    map.removeLayer(layer);
                }}
            }});
            
            // Afficher les waypoints
            var coords = {waypoints_coords};
            coords.forEach(function(wp, i) {{
                L.circleMarker(wp, {{
                    radius: 3,
                    color: 'red',
                    fillColor: 'red',
                    fillOpacity: 0.8,
                    className: 'waypoint'
                }}).addTo(map).bindPopup('WP' + (i+1));
            }});
            
            // Afficher la trajectoire
            L.polyline(coords, {{
                color: 'red', 
                weight: 2, 
                dashArray: '5, 5',
                className: 'trajectory'
            }}).addTo(map);
        """
        self.view.page().runJavaScript(js_show_waypoints)
        
        # Message d'information
        msg = f"""Mission calculée avec succès !

Paramètres:
- Altitude: {self.altitude} m
- Recouvrement frontal: {self.frontal_cov*100:.0f}%
- Recouvrement latéral: {self.lateral_cov*100:.0f}%
- FOV calculé: {fov_w:.1f}m × {fov_h:.1f}m

Résultats:
- Nombre de passes: {ny}
- Points par passe: {nx}
- Total waypoints: {len(waypoints)}

Le fichier mission_waypoints.kmz a été généré."""
        
        print(f"\n{'='*50}")
        print(msg)
        print(f"{'='*50}\n")
        
        QMessageBox.information(self.view, "Mission générée", msg)
        
        # Créer le KML/KMZ
        kml = simplekml.Kml()
        folder = kml.newfolder(name="Mission Automatique Drone")
        
        # Ajouter les waypoints
        for i, (lat, lon, alt) in enumerate(waypoints):
            pnt = folder.newpoint(name=f"WP{i+1}", coords=[(lon, lat, alt)])
            pnt.style.iconstyle.color = simplekml.Color.red
            pnt.style.iconstyle.scale = 0.5
        
        # Ajouter la trajectoire
        linestring = folder.newlinestring(
            name="Trajectoire de vol",
            coords=[(lon, lat, alt) for (lat, lon, alt) in waypoints]
        )
        linestring.altitudemode = simplekml.AltitudeMode.absolute
        linestring.style.linestyle.color = simplekml.Color.red
        linestring.style.linestyle.width = 3
        
        # Ajouter le polygone de la zone
        poly = folder.newpolygon(name="Zone de mission")
        poly.outerboundaryis = [(self.points[i][1], self.points[i][0], self.altitude) 
                                for i in range(4)] + [(self.points[0][1], self.points[0][0], self.altitude)]
        poly.style.polystyle.color = simplekml.Color.changealphaint(100, simplekml.Color.blue)
        
        # Sauvegarder
        kml.save("doc.kml")
        with ZipFile("mission_waypoints.kmz", "w") as kmz:
            kmz.write("doc.kml")
        
        print("✔ Fichier KMZ généré: mission_waypoints.kmz")

    @pyqtSlot()
    def resetPoints(self):
        self.points = []
        print("Points réinitialisés")

# ---------------------------
# Lancer l'application
# ---------------------------
app = QApplication(sys.argv)

# Demander le lieu
place_name, ok_place = QInputDialog.getText(
    None, 
    "Lieu de la mission", 
    "Entrez le nom du lieu (ex: ENSEIRB-MATMECA, Bordeaux) :"
)
if not ok_place or not place_name.strip():
    print("Annulé par l'utilisateur")
    sys.exit()

lat, lon = get_location_coordinates(place_name)
if lat is None:
    print("Lieu introuvable, utilisation des coordonnées par défaut (Paris)")
    lat, lon = 48.8566, 2.3522

print(f"Lieu localisé: {place_name} ({lat:.6f}, {lon:.6f})")

# Demander les paramètres de vol
altitude, ok1 = QInputDialog.getDouble(
    None, "Hauteur de vol", 
    "Entrez la hauteur de vol (m):", 
    50, 10, 500, 1
)

frontal_cov, ok2 = QInputDialog.getDouble(
    None, "Recouvrement frontal", 
    "Recouvrement frontal (0.5 = 50%, 0.8 = 80%):", 
    0.8, 0.5, 0.95, 2
)

lateral_cov, ok3 = QInputDialog.getDouble(
    None, "Recouvrement latéral", 
    "Recouvrement latéral (0.5 = 50%, 0.8 = 80%):", 
    0.8, 0.5, 0.95, 2
)

# Paramètres optionnels de la caméra
sensor_width, ok4 = QInputDialog.getDouble(
    None, "Capteur - Largeur", 
    "Largeur du capteur (mm):", 
    6.17, 1.0, 50.0, 2
)

sensor_height, ok5 = QInputDialog.getDouble(
    None, "Capteur - Hauteur", 
    "Hauteur du capteur (mm):", 
    4.55, 1.0, 50.0, 2
)

focal_length, ok6 = QInputDialog.getDouble(
    None, "Objectif - Focale", 
    "Focale de l'objectif (mm):", 
    4.5, 1.0, 100.0, 1
)

if not all([ok1, ok2, ok3, ok4, ok5, ok6]):
    print("Annulé par l'utilisateur")
    sys.exit()

# Préparer la carte
HTML = HTML_TEMPLATE.format(lat=lat, lon=lon)

view = QWebEngineView()
view.setWindowTitle("Générateur de mission drone - Sélection du rectangle")
view.resize(1200, 800)

channel = QWebChannel()
bridge = Bridge(view, altitude, frontal_cov, lateral_cov, 
                sensor_width, sensor_height, focal_length)
channel.registerObject("bridge", bridge)
view.page().setWebChannel(channel)
view.setHtml(HTML)
view.show()

print("\n" + "="*50)
print("Interface lancée - Suivez les instructions à l'écran")
print("="*50 + "\n")

sys.exit(app.exec_())