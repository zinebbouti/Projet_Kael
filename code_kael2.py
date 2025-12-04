import sys
import math
import time
from zipfile import ZipFile

from PyQt5.QtWidgets import QApplication, QInputDialog, QMessageBox
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QObject, pyqtSlot
from PyQt5.QtWebChannel import QWebChannel

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
# HTML de la carte
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

new QWebChannel(qt.webChannelTransport, function (channel) {{
    bridge = channel.objects.bridge;
}});

map.on('click', function (e) {{
    if (pointCount < 4 && bridge) {{
        var marker = L.circleMarker([e.latlng.lat, e.latlng.lng], {{
            radius: 6,
            color: '#2196F3',
            fillColor: '#2196F3',
            fillOpacity: 0.8
        }}).addTo(map);
        marker.bindPopup('Point ' + (pointCount + 1)).openPopup();
        markers.push(marker);
        
        bridge.sendPoint(e.latlng.lat, e.latlng.lng);
        pointCount++;
        
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

document.getElementById('validate').addEventListener('click', function() {{
    if (bridge && pointCount === 4) {{
        bridge.validateRectangle();
    }}
}});

document.getElementById('reset').addEventListener('click', function() {{
    if (bridge) {{
        bridge.resetPoints();
        markers.forEach(function(m) {{ map.removeLayer(m); }});
        markers = [];
        if (polygon) {{ map.removeLayer(polygon); polygon = null; }}
        map.eachLayer(function(layer) {{
            if (layer instanceof L.CircleMarker || layer instanceof L.Polyline) {{
                if (!markers.includes(layer)) {{
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
# Fonction pour générer un KMZ compatible WaypointMap
# ---------------------------
def generate_waypointmap_kmz(waypoints, drone_speed, gimbal_pitch, output_name="mission_waypoints.kmz"):
    """
    Génère un fichier KMZ compatible avec WaypointMap.com et DJI Fly.
    Structure: wpmz/template.kml + wpmz/waylines.wpml
    """
    
    timestamp = int(time.time() * 1000)
    
    # ========== template.kml (configuration globale) ==========
    template_kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:wpml="http://www.dji.com/wpmz/1.0.2">
<Document>
<wpml:author>fly</wpml:author>
<wpml:createTime>{timestamp}</wpml:createTime>
<wpml:updateTime>{timestamp}</wpml:updateTime>
<wpml:missionConfig>
<wpml:flyToWaylineMode>safely</wpml:flyToWaylineMode>
<wpml:finishAction>noAction</wpml:finishAction>
<wpml:exitOnRCLost>executeLostAction</wpml:exitOnRCLost>
<wpml:executeRCLostAction>hover</wpml:executeRCLostAction>
<wpml:globalTransitionalSpeed>{drone_speed}</wpml:globalTransitionalSpeed>
<wpml:droneInfo>
<wpml:droneEnumValue>68</wpml:droneEnumValue>
<wpml:droneSubEnumValue>0</wpml:droneSubEnumValue>
</wpml:droneInfo>
</wpml:missionConfig>
</Document>
</kml>
"""
    
    # ========== waylines.wpml (waypoints et actions) ==========
    waylines_wpml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:wpml="http://www.dji.com/wpmz/1.0.2">
\t<Document>
\t\t<wpml:missionConfig>
\t\t\t<wpml:flyToWaylineMode>safely</wpml:flyToWaylineMode>
\t\t\t<wpml:finishAction>noAction</wpml:finishAction>
\t\t\t<wpml:exitOnRCLost>executeLostAction</wpml:exitOnRCLost>
\t\t\t<wpml:executeRCLostAction>hover</wpml:executeRCLostAction>
\t\t\t<wpml:globalTransitionalSpeed>{drone_speed}</wpml:globalTransitionalSpeed>
\t\t\t<wpml:droneInfo>
\t\t\t\t<wpml:droneEnumValue>68</wpml:droneEnumValue>
\t\t\t\t<wpml:droneSubEnumValue>0</wpml:droneSubEnumValue>
\t\t\t</wpml:droneInfo>
\t\t</wpml:missionConfig>
\t\t<Folder>
\t\t\t<wpml:templateId>0</wpml:templateId>
\t\t\t<wpml:executeHeightMode>relativeToStartPoint</wpml:executeHeightMode>
\t\t\t<wpml:waylineId>0</wpml:waylineId>
\t\t\t<wpml:distance>0</wpml:distance>
\t\t\t<wpml:duration>0</wpml:duration>
\t\t\t<wpml:autoFlightSpeed>{drone_speed}</wpml:autoFlightSpeed>
"""
    
    # Calculer la direction pour chaque segment
    def get_heading(i, waypoints):
        """Calcule l'angle de cap basé sur la direction du vol"""
        if i == 0:
            # Premier point : regarder vers le prochain
            lat1, lon1, _ = waypoints[0]
            lat2, lon2, _ = waypoints[1]
        elif i == len(waypoints) - 1:
            # Dernier point : même direction que l'avant-dernier segment
            lat1, lon1, _ = waypoints[i-1]
            lat2, lon2, _ = waypoints[i]
        else:
            # Points intermédiaires : direction vers le prochain point
            lat1, lon1, _ = waypoints[i]
            lat2, lon2, _ = waypoints[i+1]
        
        # Calcul de l'angle (0° = Nord, 90° = Est, -90° = Ouest, 180° = Sud)
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        
        angle = math.degrees(math.atan2(dlon, dlat))
        
        # Déterminer si on va vers l'est (-90°) ou l'ouest (90°)
        if abs(dlon) > abs(dlat):  # Mouvement principalement horizontal
            return -90 if dlon > 0 else 90
        else:  # Mouvement principalement vertical
            return -90 if dlat < 0 else -90
    
    # Générer chaque waypoint
    action_id = 1
    for i, (lat, lon, alt) in enumerate(waypoints):
        heading = get_heading(i, waypoints)
        
        # Mode de rotation au waypoint
        if i == 0:
            turn_mode = "toPointAndStopWithContinuityCurvature"
            heading_enable = 1
        else:
            turn_mode = "toPointAndPassWithContinuityCurvature"
            heading_enable = 0
        
        waylines_wpml += f"""<Placemark>
<Point>
<coordinates>
{lon},{lat}
</coordinates>
</Point>
<wpml:index>{i}</wpml:index>
<wpml:executeHeight>{int(alt)}</wpml:executeHeight>
<wpml:waypointSpeed>{drone_speed}</wpml:waypointSpeed>
<wpml:waypointHeadingParam>
<wpml:waypointHeadingMode>smoothTransition</wpml:waypointHeadingMode>
<wpml:waypointHeadingAngle>{heading}</wpml:waypointHeadingAngle>
<wpml:waypointPoiPoint>0.000000,0.000000,0.000000</wpml:waypointPoiPoint>
<wpml:waypointHeadingAngleEnable>{heading_enable}</wpml:waypointHeadingAngleEnable>
<wpml:waypointHeadingPathMode>followBadArc</wpml:waypointHeadingPathMode>
</wpml:waypointHeadingParam>
<wpml:waypointTurnParam>
<wpml:waypointTurnMode>{turn_mode}</wpml:waypointTurnMode>
<wpml:waypointTurnDampingDist>0</wpml:waypointTurnDampingDist>
</wpml:waypointTurnParam>
<wpml:useStraightLine>0</wpml:useStraightLine>
"""
        
        # Action au premier point : rotation de la nacelle + gimbalEvenlyRotate
        if i == 0:
            waylines_wpml += f"""<wpml:actionGroup>
<wpml:actionGroupId>1</wpml:actionGroupId>
<wpml:actionGroupStartIndex>0</wpml:actionGroupStartIndex>
<wpml:actionGroupEndIndex>0</wpml:actionGroupEndIndex>
<wpml:actionGroupMode>parallel</wpml:actionGroupMode>
<wpml:actionTrigger>
<wpml:actionTriggerType>reachPoint</wpml:actionTriggerType>
</wpml:actionTrigger>
<wpml:action>
<wpml:actionId>{action_id}</wpml:actionId>
<wpml:actionActuatorFunc>gimbalRotate</wpml:actionActuatorFunc>
<wpml:actionActuatorFuncParam>
<wpml:gimbalHeadingYawBase>aircraft</wpml:gimbalHeadingYawBase>
<wpml:gimbalRotateMode>absoluteAngle</wpml:gimbalRotateMode>
<wpml:gimbalPitchRotateEnable>1</wpml:gimbalPitchRotateEnable>
<wpml:gimbalPitchRotateAngle>{gimbal_pitch}</wpml:gimbalPitchRotateAngle>
<wpml:gimbalRollRotateEnable>0</wpml:gimbalRollRotateEnable>
<wpml:gimbalRollRotateAngle>0</wpml:gimbalRollRotateAngle>
<wpml:gimbalYawRotateEnable>0</wpml:gimbalYawRotateEnable>
<wpml:gimbalYawRotateAngle>0</wpml:gimbalYawRotateAngle>
<wpml:gimbalRotateTimeEnable>0</wpml:gimbalRotateTimeEnable>
<wpml:gimbalRotateTime>0</wpml:gimbalRotateTime>
<wpml:payloadPositionIndex>0</wpml:payloadPositionIndex>
</wpml:actionActuatorFuncParam>
</wpml:action>
</wpml:actionGroup>
"""
            action_id += 1
            
            # Deuxième action group pour gimbalEvenlyRotate
            waylines_wpml += f"""<wpml:actionGroup>
<wpml:actionGroupId>2</wpml:actionGroupId>
<wpml:actionGroupStartIndex>0</wpml:actionGroupStartIndex>
<wpml:actionGroupEndIndex>{len(waypoints)-1}</wpml:actionGroupEndIndex>
<wpml:actionGroupMode>parallel</wpml:actionGroupMode>
<wpml:actionTrigger>
<wpml:actionTriggerType>reachPoint</wpml:actionTriggerType>
</wpml:actionTrigger>
<wpml:action>
<wpml:actionId>{action_id}</wpml:actionId>
<wpml:actionActuatorFunc>gimbalEvenlyRotate</wpml:actionActuatorFunc>
<wpml:actionActuatorFuncParam>
<wpml:gimbalPitchRotateAngle>{gimbal_pitch}</wpml:gimbalPitchRotateAngle>
<wpml:payloadPositionIndex>0</wpml:payloadPositionIndex>
</wpml:actionActuatorFuncParam>
</wpml:action>
</wpml:actionGroup>
"""
        else:
            # Pour les autres points : action gimbalEvenlyRotate
            waylines_wpml += f"""<wpml:actionGroup>
<wpml:actionGroupId>2</wpml:actionGroupId>
<wpml:actionGroupStartIndex>{i}</wpml:actionGroupStartIndex>
<wpml:actionGroupEndIndex>{i}</wpml:actionGroupEndIndex>
<wpml:actionGroupMode>parallel</wpml:actionGroupMode>
<wpml:actionTrigger>
<wpml:actionTriggerType>reachPoint</wpml:actionTriggerType>
</wpml:actionTrigger>
<wpml:action>
<wpml:actionId>{action_id}</wpml:actionId>
<wpml:actionActuatorFunc>gimbalEvenlyRotate</wpml:actionActuatorFunc>
<wpml:actionActuatorFuncParam>
<wpml:gimbalPitchRotateAngle>{gimbal_pitch}</wpml:gimbalPitchRotateAngle>
<wpml:payloadPositionIndex>0</wpml:payloadPositionIndex>
</wpml:actionActuatorFuncParam>
</wpml:action>
</wpml:actionGroup>
"""
        
        action_id += 1
        waylines_wpml += "</Placemark>"
    
    waylines_wpml += """
\t\t</Folder>
\t</Document>
</kml>
"""
    
    # Créer le fichier KMZ
    with ZipFile(output_name, 'w') as kmz:
        kmz.writestr("wpmz/template.kml", template_kml)
        kmz.writestr("wpmz/waylines.wpml", waylines_wpml)
    
    return output_name

# ---------------------------
# Fonction pour valider le rectangle
# ---------------------------
def validate_rectangle(points):
    if len(points) != 4:
        return False, "Il faut exactement 4 points."
    
    distances = []
    for i in range(4):
        p1 = points[i]
        p2 = points[(i + 1) % 4]
        dist = math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
        distances.append(dist)
    
    ratio1 = abs(distances[0] - distances[2]) / max(distances[0], distances[2])
    ratio2 = abs(distances[1] - distances[3]) / max(distances[1], distances[3])
    
    if ratio1 > 0.2 or ratio2 > 0.2:
        return False, "Les points ne forment pas un rectangle régulier."
    
    return True, "Rectangle valide."

# ---------------------------
# Fonction pour générer des waypoints
# ---------------------------
def generate_waypoints(rect_points, altitude, frontal_cov, lateral_cov,
                       sensor_width, sensor_height, focal_length):
    P0, P1, P2, P3 = rect_points

    def distance_m(pA, pB):
        lat_avg = (pA[0]+pB[0])/2
        dx = (pB[1]-pA[1]) * 111000 * math.cos(math.radians(lat_avg))
        dy = (pB[0]-pA[0]) * 111000
        return math.sqrt(dx*dx + dy*dy)

    fov_width  = 2 * altitude * (sensor_width / (2 * focal_length))
    fov_height = 2 * altitude * (sensor_height / (2 * focal_length))
    dy = fov_height * (1 - lateral_cov)

    Ly_total = distance_m(P0, P3)
    Ny = max(1, int(math.ceil(Ly_total / dy)))

    waypoints = []

    for iy in range(Ny + 1):
        frac_y = iy / Ny
        left_lat  = P0[0] + frac_y * (P3[0]-P0[0])
        left_lon  = P0[1] + frac_y * (P3[1]-P0[1])
        right_lat = P1[0] + frac_y * (P2[0]-P1[0])
        right_lon = P1[1] + frac_y * (P2[1]-P1[1])

        Lx_line = distance_m((left_lat,left_lon), (right_lat,right_lon))
        dx = fov_width * (1 - frontal_cov)
        Nx = max(1, int(math.ceil(Lx_line / dx)))

        line_waypoints = []
        for ix in range(Nx + 1):
            frac_x = ix / Nx
            lat = left_lat + frac_x * (right_lat - left_lat)
            lon = left_lon + frac_x * (right_lon - left_lon)
            line_waypoints.append((lat, lon, altitude))

        if iy % 2 == 1:
            line_waypoints.reverse()
        
        waypoints.extend(line_waypoints)

    return waypoints, Nx + 1, Ny + 1, fov_width, fov_height

# ---------------------------
# Classe Bridge PyQt5
# ---------------------------
class Bridge(QObject):
    def __init__(self, view, altitude, frontal_cov, lateral_cov, 
                 sensor_width, sensor_height, focal_length, drone_speed, gimbal_pitch):
        super().__init__()
        self.view = view
        self.points = []
        self.altitude = altitude
        self.frontal_cov = frontal_cov
        self.lateral_cov = lateral_cov
        self.sensor_width = sensor_width
        self.sensor_height = sensor_height
        self.focal_length = focal_length
        self.drone_speed = drone_speed
        self.gimbal_pitch = gimbal_pitch

    @pyqtSlot(float, float)
    def sendPoint(self, lat, lng):
        print(f"Point {len(self.points) + 1} enregistré: {lat:.6f}, {lng:.6f}")
        self.points.append([lat, lng])

        if len(self.points) == 4:
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
        
        is_valid, message = validate_rectangle(self.points)
        if not is_valid:
            QMessageBox.warning(self.view, "Rectangle invalide", message)
            return
        
        print("Validation du rectangle...")
        
        waypoints, nx, ny, fov_w, fov_h = generate_waypoints(
            self.points, self.altitude, self.frontal_cov, self.lateral_cov,
            self.sensor_width, self.sensor_height, self.focal_length
        )
        
        waypoints_coords = [[lat, lon] for lat, lon, _ in waypoints]
        js_show_waypoints = f"""
            map.eachLayer(function(layer) {{
                if (layer instanceof L.CircleMarker && layer.options.className === 'waypoint') {{
                    map.removeLayer(layer);
                }}
                if (layer instanceof L.Polyline && layer.options.className === 'trajectory') {{
                    map.removeLayer(layer);
                }}
            }});
            
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
            
            L.polyline(coords, {{
                color: 'red', 
                weight: 2, 
                dashArray: '5, 5',
                className: 'trajectory'
            }}).addTo(map);
        """
        self.view.page().runJavaScript(js_show_waypoints)
        
        msg = f"""Mission calculée avec succès !

Paramètres:
- Altitude: {self.altitude} m
- Vitesse drone: {self.drone_speed} m/s
- Angle nacelle: {self.gimbal_pitch}°
- Recouvrement frontal: {self.frontal_cov*100:.0f}%
- Recouvrement latéral: {self.lateral_cov*100:.0f}%
- FOV calculé: {fov_w:.1f}m × {fov_h:.1f}m

Résultats:
- Nombre de passes: {ny}
- Points par passe: {nx}
- Total waypoints: {len(waypoints)}

Le fichier mission_waypoints.kmz a été généré.
Compatible avec WaypointMap et DJI Fly."""
        
        print(f"\n{'='*50}")
        print(msg)
        print(f"{'='*50}\n")
        
        QMessageBox.information(self.view, "Mission générée", msg)
        
        kmz_file = generate_waypointmap_kmz(
            waypoints, 
            self.drone_speed,
            self.gimbal_pitch,
            "mission_waypoints.kmz"
        )
        
        print(f"✔ Fichier KMZ généré: {kmz_file}")
        print("\n📱 Installation dans DJI Fly:")
        print("1. Créez une mission dans DJI Fly (2-3 waypoints)")
        print("2. Connectez la télécommande en USB")
        print("3. Naviguez: Android/data/dji.go.v5/files/waypoint/")
        print("4. Remplacez le .kmz par mission_waypoints.kmz")

    @pyqtSlot()
    def resetPoints(self):
        self.points = []
        print("Points réinitialisés")

# ---------------------------
# Lancer l'application
# ---------------------------
app = QApplication(sys.argv)

place_name, ok_place = QInputDialog.getText(
    None, "Lieu de la mission", 
    "Entrez le nom du lieu (ex: ENSEIRB-MATMECA, Bordeaux) :"
)
if not ok_place or not place_name.strip():
    print("Annulé par l'utilisateur")
    sys.exit()

lat, lon = get_location_coordinates(place_name)
if lat is None:
    print("Lieu introuvable, coordonnées par défaut (Paris)")
    lat, lon = 48.8566, 2.3522

print(f"Lieu localisé: {place_name} ({lat:.6f}, {lon:.6f})")

altitude, ok1 = QInputDialog.getDouble(None, "Hauteur de vol", "Hauteur (m):", 50, 10, 500, 1)
drone_speed, ok2 = QInputDialog.getDouble(None, "Vitesse", "Vitesse (m/s):", 2.5, 1, 15, 1)
gimbal_pitch, ok3 = QInputDialog.getDouble(None, "Angle nacelle", "Angle (-90=bas, 0=horizontal):", -45, -90, 0, 1)
frontal_cov, ok4 = QInputDialog.getDouble(None, "Recouvrement frontal", "Frontal (0.8 = 80%):", 0.8, 0.5, 0.95, 2)
lateral_cov, ok5 = QInputDialog.getDouble(None, "Recouvrement latéral", "Latéral (0.8 = 80%):", 0.8, 0.5, 0.95, 2)
sensor_width, ok6 = QInputDialog.getDouble(None, "Capteur", "Largeur (mm):", 6.17, 1.0, 50.0, 2)
sensor_height, ok7 = QInputDialog.getDouble(None, "Capteur", "Hauteur (mm):", 4.55, 1.0, 50.0, 2)
focal_length, ok8 = QInputDialog.getDouble(None, "Focale", "Focale (mm):", 4.5, 1.0, 100.0, 1)

if not all([ok1, ok2, ok3, ok4, ok5, ok6, ok7, ok8]):
    print("Annulé par l'utilisateur")
    sys.exit()

HTML = HTML_TEMPLATE.format(lat=lat, lon=lon)

view = QWebEngineView()
view.setWindowTitle("Générateur de mission drone - WaypointMap compatible")
view.resize(1200, 800)

channel = QWebChannel()
bridge = Bridge(view, altitude, frontal_cov, lateral_cov, 
                sensor_width, sensor_height, focal_length, drone_speed, gimbal_pitch)
channel.registerObject("bridge", bridge)
view.page().setWebChannel(channel)
view.setHtml(HTML)
view.show()

print("\n" + "="*50)
print("Interface lancée - Suivez les instructions")
print("="*50 + "\n")

sys.exit(app.exec_())