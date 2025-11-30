import sys
from PyQt5.QtWidgets import QApplication, QInputDialog, QLineEdit, QMessageBox
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QObject, pyqtSlot
from PyQt5.QtWebChannel import QWebChannel
import simplekml
from zipfile import ZipFile
import math

# ---------------------------
# HTML de la carte
# ---------------------------
HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<title>Carte Rectangle</title>
<style>html, body, #map { height: 100%; margin: 0; padding: 0; }</style>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.7.1/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.7.1/dist/leaflet.js"></script>
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
</head>
<body>
<div id="map"></div>
<script>
var map = L.map('map').setView([46.5, 2.5], 6);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);
var polygon = null;

map.on('click', function (e) {
    new QWebChannel(qt.webChannelTransport, function (channel) {
        channel.objects.bridge.sendPoint(e.latlng.lat, e.latlng.lng);
    });
});
</script>
</body>
</html>
"""

# ---------------------------
# Fonction pour générer des waypoints
# ---------------------------
def generate_waypoints(rect_points, altitude=50, frontal_cov=0.8, lateral_cov=0.8):
    """
    rect_points: liste de 4 points [(lat, lon), ...] formant un rectangle
    altitude: hauteur de vol en mètres
    frontal_cov: recouvrement frontal (0-1)
    lateral_cov: recouvrement latéral (0-1)
    """
    lat1, lon1 = rect_points[0]
    lat2, lon2 = rect_points[2]  # coin opposé
    lat_dist = abs(lat2 - lat1) * 111000
    lon_dist = abs(lon2 - lon1) * 111000 * math.cos(math.radians((lat1+lat2)/2))

    fov = 50  # largeur approximative du capteur à cette altitude
    delta_x = fov * (1 - frontal_cov)
    delta_y = fov * (1 - lateral_cov)

    nx = max(1, int(math.ceil(lon_dist / delta_x)))
    ny = max(1, int(math.ceil(lat_dist / delta_y)))

    waypoints = []
    for iy in range(ny + 1):
        lat = lat1 + (lat2 - lat1) * iy / ny
        line = []
        for ix in range(nx + 1):
            lon = lon1 + (lon2 - lon1) * ix / nx
            line.append((lat, lon, altitude))
        if iy % 2 == 1:
            line.reverse()
        waypoints.extend(line)
    waypoints.append((rect_points[0][0], rect_points[0][1], altitude))
    return waypoints, nx + 1, ny + 1  # on renvoie aussi le nombre de points par ligne et de lignes

# ---------------------------
# Classe pour PyQt5 bridge
# ---------------------------
class Bridge(QObject):
    def __init__(self, view, altitude, frontal_cov, lateral_cov):
        super().__init__()
        self.view = view
        self.points = []
        self.altitude = altitude
        self.frontal_cov = frontal_cov
        self.lateral_cov = lateral_cov

    @pyqtSlot(float, float)
    def sendPoint(self, lat, lng):
        print(f"Point enregistré: {lat}, {lng}")
        self.points.append([lat, lng])

        if len(self.points) == 4:
            # Créer le polygone sur la carte
            js = f"""
                var pts = {self.points + [self.points[0]]};
                if (polygon) map.removeLayer(polygon);
                polygon = L.polygon(pts, {{color:'blue', fillColor:'blue', fillOpacity:0.3}}).addTo(map);
            """
            self.view.page().runJavaScript(js)
            print("Rectangle créé :", self.points)

            # Générer les waypoints
            waypoints, nx, ny = generate_waypoints(self.points, self.altitude, self.frontal_cov, self.lateral_cov)
            msg = f"Nombre de passes: {ny}, points par passe: {nx}, total waypoints: {len(waypoints)}"
            print(msg)
            QMessageBox.information(self.view, "Waypoints calculés", msg)

            # Créer le KML/KMZ
            kml = simplekml.Kml()
            folder = kml.newfolder(name="Mission Auto")
            for i, (lat, lon, alt) in enumerate(waypoints):
                folder.newpoint(name=f"WP{i+1}", coords=[(lon, lat, alt)])
            linestring = folder.newlinestring(
                name="Trajectoire",
                coords=[(lon, lat, alt) for (lat, lon, alt) in waypoints]
            )
            linestring.altitudemode = simplekml.AltitudeMode.absolute
            kml.save("doc.kml")
            with ZipFile("mission_waypoints.kmz", "w") as kmz:
                kmz.write("doc.kml")
            print("✔ KMZ généré : mission_waypoints.kmz")

# ---------------------------
# Lancer l'application
# ---------------------------
app = QApplication(sys.argv)

# Demander la hauteur et recouvrements
altitude, ok1 = QInputDialog.getDouble(None, "Hauteur de vol", "Entrez la hauteur de vol (m):", 50, 10, 200, 1)
frontal_cov, ok2 = QInputDialog.getDouble(None, "Recouvrement frontal", "Recouvrement frontal (0-1):", 0.8, 0.5, 1.0, 2)
lateral_cov, ok3 = QInputDialog.getDouble(None, "Recouvrement latéral", "Recouvrement latéral (0-1):", 0.8, 0.5, 1.0, 2)

if not (ok1 and ok2 and ok3):
    print("Annulé par l'utilisateur")
    sys.exit()

view = QWebEngineView()
channel = QWebChannel()
bridge = Bridge(view, altitude, frontal_cov, lateral_cov)
channel.registerObject("bridge", bridge)
view.page().setWebChannel(channel)
view.setHtml(HTML)
view.show()
sys.exit(app.exec_())

