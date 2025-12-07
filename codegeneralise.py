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
<title>Carte Polygone - Mission Drone</title>
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
    #close {{ background: #2196F3; color: white; }}
    #close:hover {{ background: #0b7dda; }}
    #close:disabled {{ background: #cccccc; cursor: not-allowed; }}
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
    <button id="close" disabled>Fermer Polygone</button>
    <button id="validate" disabled>Valider Mission</button>
    <button id="reset">Réinitialiser</button>
</div>
<div id="info">Cliquez pour ajouter des points au polygone (minimum 3)</div>

<script>
var map = L.map('map').setView([{lat}, {lon}], 15);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png').addTo(map);

var polygon = null;
var markers = [];
var pointCount = 0;
var polygonClosed = false;
var bridge = null;

new QWebChannel(qt.webChannelTransport, function (channel) {{
    bridge = channel.objects.bridge;
}});

map.on('click', function (e) {{
    if (!polygonClosed && bridge) {{
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
        
        if (pointCount >= 3) {{
            document.getElementById('close').disabled = false;
        }}
        
        document.getElementById('info').textContent = 
            'Point ' + pointCount + ' enregistré. ' + 
            (pointCount >= 3 ? 'Cliquez sur "Fermer Polygone" ou ajoutez plus de points.' : 
             'Ajoutez au moins ' + (3 - pointCount) + ' point(s) supplémentaire(s).');
        
        // Dessiner le polygone temporaire
        if (pointCount >= 2) {{
            if (polygon) map.removeLayer(polygon);
            var pts = markers.map(m => m.getLatLng());
            polygon = L.polyline(pts, {{
                color:'blue', 
                weight: 2,
                dashArray: '5, 5'
            }}).addTo(map);
        }}
    }}
}});

document.getElementById('close').addEventListener('click', function() {{
    if (bridge && pointCount >= 3 && !polygonClosed) {{
        bridge.closePolygon();
        polygonClosed = true;
        document.getElementById('close').disabled = true;
        document.getElementById('validate').disabled = false;
        document.getElementById('info').textContent = 
            'Polygone fermé avec ' + pointCount + ' points. Cliquez sur "Valider Mission".';
        
        // Dessiner le polygone fermé
        if (polygon) map.removeLayer(polygon);
        var pts = markers.map(m => m.getLatLng());
        polygon = L.polygon(pts, {{
            color:'blue', 
            fillColor:'blue', 
            fillOpacity:0.2,
            weight: 2
        }}).addTo(map);
        map.fitBounds(polygon.getBounds());
    }}
}});

document.getElementById('validate').addEventListener('click', function() {{
    if (bridge && polygonClosed) {{
        bridge.validatePolygon();
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
        polygonClosed = false;
        document.getElementById('close').disabled = true;
        document.getElementById('validate').disabled = true;
        document.getElementById('info').textContent = 'Cliquez pour ajouter des points au polygone (minimum 3)';
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
    timestamp = int(time.time() * 1000)
    
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
    
    def get_heading(i, waypoints):
        if i == 0:
            lat1, lon1, _ = waypoints[0]
            lat2, lon2, _ = waypoints[1]
        elif i == len(waypoints) - 1:
            lat1, lon1, _ = waypoints[i-1]
            lat2, lon2, _ = waypoints[i]
        else:
            lat1, lon1, _ = waypoints[i]
            lat2, lon2, _ = waypoints[i+1]
        
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        angle = math.degrees(math.atan2(dlon, dlat))
        
        if abs(dlon) > abs(dlat):
            return -90 if dlon > 0 else 90
        else:
            return -90 if dlat < 0 else -90
    
    action_id = 1
    for i, (lat, lon, alt) in enumerate(waypoints):
        heading = get_heading(i, waypoints)
        
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
    
    with ZipFile(output_name, 'w') as kmz:
        kmz.writestr("wpmz/template.kml", template_kml)
        kmz.writestr("wpmz/waylines.wpml", waylines_wpml)
    
    return output_name

# ---------------------------
# Fonctions géométriques pour polygone
# ---------------------------
def point_in_polygon(point, polygon):
    """Test si un point est dans un polygone (ray casting algorithm)"""
    x, y = point
    n = len(polygon)
    inside = False
    
    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    
    return inside

def get_bounding_box(polygon):
    """Retourne le bounding box du polygone (min_lat, max_lat, min_lon, max_lon)"""
    lats = [p[0] for p in polygon]
    lons = [p[1] for p in polygon]
    return (min(lats), max(lats), min(lons), max(lons))

def get_main_axis_angle(polygon):
    """Calcule l'angle principal du polygone pour l'orientation des passes"""
    if len(polygon) < 2:
        return 0
    
    p1, p2 = polygon[0], polygon[1]
    dx = p2[1] - p1[1]
    dy = p2[0] - p1[0]
    angle = math.atan2(dy, dx)
    return angle

# ---------------------------
# Fonction pour générer des waypoints dans un polygone
# ---------------------------
def generate_waypoints_polygon(polygon_points, altitude, frontal_cov, lateral_cov,
                               sensor_width, sensor_height, focal_length):
    """
    Génère des waypoints pour couvrir un polygone quelconque avec un pattern boustrophédon.
    Utilise un algorithme de balayage horizontal (scanlines) avec détection d'intersections.
    """
    def distance_m(pA, pB):
        """Calcule la distance en mètres entre deux points GPS"""
        lat_avg = (pA[0] + pB[0]) / 2
        dx = (pB[1] - pA[1]) * 111000 * math.cos(math.radians(lat_avg))
        dy = (pB[0] - pA[0]) * 111000
        return math.sqrt(dx*dx + dy*dy)
    
    # Calcul du FOV (Field of View) basé sur les paramètres de la caméra
    fov_width = 2 * altitude * (sensor_width / (2 * focal_length))
    fov_height = 2 * altitude * (sensor_height / (2 * focal_length))
    
    # Calcul de l'espacement entre les passes en tenant compte du recouvrement
    dy = fov_height * (1 - lateral_cov)
    dx = fov_width * (1 - frontal_cov)
    
    # Obtenir le bounding box du polygone
    min_lat, max_lat, min_lon, max_lon = get_bounding_box(polygon_points)
    
    # Convertir l'espacement en degrés de latitude
    dy_deg = dy / 111000  # 1 degré de latitude ≈ 111km
    
    # Calculer le nombre de lignes de balayage nécessaires
    height_deg = max_lat - min_lat
    n_lines = max(1, int(math.ceil(height_deg / dy_deg))) + 1
    
    waypoints = []
    line_count = 0
    
    # Générer les lignes de balayage horizontales
    for i in range(n_lines):
        current_lat = min_lat + i * dy_deg
        
        if current_lat > max_lat:
            break
        
        # Trouver toutes les intersections de cette ligne avec le polygone
        intersections = []
        
        for j in range(len(polygon_points)):
            p1 = polygon_points[j]
            p2 = polygon_points[(j + 1) % len(polygon_points)]
            
            # Vérifier si le segment du polygone traverse la ligne horizontale
            if (p1[0] <= current_lat <= p2[0]) or (p2[0] <= current_lat <= p1[0]):
                if p2[0] != p1[0]:  # Éviter division par zéro
                    # Calculer la longitude du point d'intersection
                    t = (current_lat - p1[0]) / (p2[0] - p1[0])
                    lon_intersect = p1[1] + t * (p2[1] - p1[1])
                    intersections.append(lon_intersect)
        
        # Trier les intersections par longitude
        intersections.sort()
        
        # Générer les waypoints par paires d'intersections (entrée/sortie du polygone)
        for k in range(0, len(intersections) - 1, 2):
            lon_start = intersections[k]
            lon_end = intersections[k + 1]
            
            # Calculer le nombre de points nécessaires sur cette ligne
            line_length_m = distance_m((current_lat, lon_start), (current_lat, lon_end))
            n_points = max(1, int(math.ceil(line_length_m / dx))) + 1
            
            # Générer les waypoints sur cette ligne
            line_waypoints = []
            for m in range(n_points):
                frac = m / (n_points - 1) if n_points > 1 else 0
                lon = lon_start + frac * (lon_end - lon_start)
                
                # Vérifier que le point est bien dans le polygone
                if point_in_polygon((current_lat, lon), polygon_points):
                    line_waypoints.append((current_lat, lon, altitude))
            
            # Pattern boustrophédon : alterner la direction des lignes
            if line_count % 2 == 1:
                line_waypoints.reverse()
            
            waypoints.extend(line_waypoints)
            line_count += 1
    
    return waypoints, line_count, len(waypoints), fov_width, fov_height

# ---------------------------
# Classe Bridge PyQt5 pour communication JS ↔ Python
# ---------------------------
class Bridge(QObject):
    def __init__(self, view, altitude, frontal_cov, lateral_cov, 
                 sensor_width, sensor_height, focal_length, drone_speed, gimbal_pitch):
        super().__init__()
        self.view = view
        self.points = []
        self.polygon_closed = False
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
        """Reçoit un point cliqué sur la carte"""
        print(f"Point {len(self.points) + 1} enregistré: {lat:.6f}, {lng:.6f}")
        self.points.append([lat, lng])

    @pyqtSlot()
    def closePolygon(self):
        """Ferme le polygone une fois que l'utilisateur a fini de placer les points"""
        if len(self.points) >= 3:
            self.polygon_closed = True
            print(f"Polygone fermé avec {len(self.points)} points")

    @pyqtSlot()
    def validatePolygon(self):
        """Valide le polygone et génère la mission de waypoints"""
        if not self.polygon_closed or len(self.points) < 3:
            QMessageBox.warning(self.view, "Erreur", "Veuillez fermer le polygone d'abord.")
            return
        
        print(f"Validation du polygone ({len(self.points)} points)...")
        
        # Générer les waypoints
        waypoints, n_lines, n_points, fov_w, fov_h = generate_waypoints_polygon(
            self.points, self.altitude, self.frontal_cov, self.lateral_cov,
            self.sensor_width, self.sensor_height, self.focal_length
        )
        
        if len(waypoints) == 0:
            QMessageBox.warning(self.view, "Erreur", "Aucun waypoint généré. Vérifiez le polygone.")
            return
        
        # Afficher les waypoints sur la carte
        waypoints_coords = [[lat, lon] for lat, lon, _ in waypoints]
        js_show_waypoints = f"""
            // Nettoyer les waypoints précédents
            map.eachLayer(function(layer) {{
                if (layer instanceof L.CircleMarker && layer.options.className === 'waypoint') {{
                    map.removeLayer(layer);
                }}
                if (layer instanceof L.Polyline && layer.options.className === 'trajectory') {{
                    map.removeLayer(layer);
                }}
            }});
            
            // Afficher les nouveaux waypoints
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
        
        # Préparer le message de confirmation
        msg = f"""Mission calculée avec succès !

Paramètres:
- Forme: Polygone ({len(self.points)} sommets)
- Altitude: {self.altitude} m
- Vitesse drone: {self.drone_speed} m/s
- Angle nacelle: {self.gimbal_pitch}°
- Recouvrement frontal: {self.frontal_cov*100:.0f}%
- Recouvrement latéral: {self.lateral_cov*100:.0f}%
- FOV calculé: {fov_w:.1f}m × {fov_h:.1f}m

Résultats:
- Nombre de passes: {n_lines}
- Total waypoints: {n_points}

Le fichier mission_waypoints.kmz a été généré.
Compatible avec WaypointMap et DJI Fly."""
        
        print(f"\n{'='*50}")
        print(msg)
        print(f"{'='*50}\n")
        
        QMessageBox.information(self.view, "Mission générée", msg)
        
        # Générer le fichier KMZ
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
        """Réinitialise tous les points"""
        self.points = []
        self.polygon_closed = False
        print("Points réinitialisés")

# ---------------------------
# Lancer l'application
# ---------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Demander le lieu de la mission
    place_name, ok_place = QInputDialog.getText(
        None, "Lieu de la mission", 
        "Entrez le nom du lieu (ex: ENSEIRB-MATMECA, Bordeaux) :"
    )
    if not ok_place or not place_name.strip():
        print("Annulé par l'utilisateur")
        sys.exit()

    # Géolocaliser le lieu
    lat, lon = get_location_coordinates(place_name)
    if lat is None:
        print("Lieu introuvable, coordonnées par défaut (Paris)")
        lat, lon = 48.8566, 2.3522

    print(f"Lieu localisé: {place_name} ({lat:.6f}, {lon:.6f})")

    # Demander les paramètres de mission
    altitude, ok1 = QInputDialog.getDouble(
        None, "Hauteur de vol", "Hauteur (m):", 50, 10, 500, 1
    )
    drone_speed, ok2 = QInputDialog.getDouble(
        None, "Vitesse", "Vitesse (m/s):", 2.5, 1, 15, 1
    )
    gimbal_pitch, ok3 = QInputDialog.getDouble(
        None, "Angle nacelle", "Angle (-90=bas, 0=horizontal):", -45, -90, 0, 1
    )
    frontal_cov, ok4 = QInputDialog.getDouble(
        None, "Recouvrement frontal", "Frontal (0.8 = 80%):", 0.8, 0.5, 0.95, 2
    )
    lateral_cov, ok5 = QInputDialog.getDouble(
        None, "Recouvrement latéral", "Latéral (0.8 = 80%):", 0.8, 0.5, 0.95, 2
    )
    sensor_width, ok6 = QInputDialog.getDouble(
        None, "Capteur", "Largeur (mm):", 6.17, 1.0, 50.0, 2
    )
    sensor_height, ok7 = QInputDialog.getDouble(
        None, "Capteur", "Hauteur (mm):", 4.55, 1.0, 50.0, 2
    )
    focal_length, ok8 = QInputDialog.getDouble(
        None, "Focale", "Focale (mm):", 4.5, 1.0, 100.0, 1
    )

    if not all([ok1, ok2, ok3, ok4, ok5, ok6, ok7, ok8]):
        print("Annulé par l'utilisateur")
        sys.exit()

    # Créer le HTML avec les coordonnées
    HTML = HTML_TEMPLATE.format(lat=lat, lon=lon)

    # Créer la fenêtre et le bridge
    view = QWebEngineView()
    view.setWindowTitle("Générateur de mission drone - Polygone généralisé")
    view.resize(1200, 800)

    # Configurer le canal de communication
    channel = QWebChannel()
    bridge = Bridge(
        view, altitude, frontal_cov, lateral_cov, 
        sensor_width, sensor_height, focal_length, drone_speed, gimbal_pitch
    )
    channel.registerObject("bridge", bridge)
    view.page().setWebChannel(channel)
    view.setHtml(HTML)
    view.show()

    print("\n" + "="*50)
    print("Interface lancée - Définissez votre polygone")
    print("="*50 + "\n")

    sys.exit(app.exec_())