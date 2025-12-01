import simplekml
from zipfile import ZipFile

#  Coordonnées centrales (exemple : lycée)
lat0 = 44.8060109
lon0 = -0.6050179

#  Créer une trajectoire autour du point central (5 waypoints)
waypoints = [
    (lat0, lon0, 40),                # WP1
    (lat0 + 0.0003, lon0, 40),       # WP2
    (lat0 + 0.0003, lon0 + 0.0003, 40), # WP3
    (lat0, lon0 + 0.0003, 40),       # WP4
    (lat0, lon0, 40)                 # WP5 (retour au point de départ)
]

# Créer le KML
kml = simplekml.Kml()
folder = kml.newfolder(name="Mission Auto")

# Ajouter les points comme waypoints
for i, (lat, lon, alt) in enumerate(waypoints):
    folder.newpoint(name=f"WP{i+1}", coords=[(lon, lat, alt)])

# Ajouter la trajectoire (ligne reliant tous les waypoints)
linestring = folder.newlinestring(
    name="Trajectoire",
    coords=[(lon, lat, alt) for (lat, lon, alt) in waypoints]
)
linestring.altitudemode = simplekml.AltitudeMode.absolute

# Sauvegarder le fichier KML
kml.save("doc.kml")

# Créer le fichier KMZ (compressé)
with ZipFile("mission_waypoints.kmz", "w") as kmz:
    kmz.write("doc.kml")

print("✔ KMZ généré : mission_waypoints.kmz")

