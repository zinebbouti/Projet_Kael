from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="gps_simulation")

# Adresse complète et précise
location = geolocator.geocode("enseirb-matmeca")

if location:
    print(location.latitude, location.longitude)
else:
    print("Adresse non trouvée ! Vérifie la saisie.")


