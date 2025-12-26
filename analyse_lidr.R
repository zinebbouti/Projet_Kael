# =====================================================
# ANALYSE FORESTIÈRE PAR DRONE (WebODM + lidR)
# Projet SAVEWOOD / TER
# =====================================================

# ---------
# 0. Librairies
# ---------
library(lidR)
library(sf)
library(terra)

# # ---------
# # 1. Charger le nuage de points WebODM
# # ---------
# las <- readLAS("LHD_FXX_0411_6670_PTS_LAMB93_IGN69.copc.laz")

# if (is.empty(las)) {
#   stop("❌ Le nuage de points est vide")
# }


## Mon fichier est dense c pour ca j'ai découpé sinon utilise ce qui est en haut


# cat("✅ Nuage chargé\n")
library(lidR)
library(sf)
library(terra)

# Charger le fichier COPC
las_full <- readLAS(
  "LHD_FXX_0411_6670_PTS_LAMB93_IGN69.copc.laz",
  select = "xyz"
)

if (is.empty(las_full)) {
  stop("❌ Nuage vide")
}

cat("✅ Nuage chargé\n")

# Découpe d'une zone 200 m × 200 m (à ajuster si besoin)
las <- clip_rectangle(
  las_full,
  xmin = 667000,
  ymin = 6110000,
  xmax = 667200,
  ymax = 6110200
)

cat("✅ Zone découpée\n")

# ---------
# 2. Classification du sol
# ---------
las <- classify_ground(las, csf())

cat("✅ Sol classifié\n")

# ---------
# 3. Modèle Numérique de Terrain (DTM)
# ---------
dtm <- grid_terrain(
  las,
  algorithm = knnidw(),
  res = 0.5
)

cat("✅ DTM calculé\n")

# ---------
# 4. Normalisation des hauteurs
# ---------
las_norm <- normalize_height(las, dtm)

cat("✅ Hauteurs normalisées\n")

# ---------
# 5. Canopy Height Model (CHM)
# ---------
chm <- grid_canopy(
  las_norm,
  res = 0.25,
  algorithm = p2r()
)

plot(chm, main = "Canopy Height Model")

cat("✅ CHM généré\n")

# ---------
# 6. Détection des arbres (pins)
# ---------
ttops <- locate_trees(
  chm,
  lmf(ws = 3)
)

plot(chm)
plot(ttops, add = TRUE, col = "red")

cat(paste("✅", nrow(ttops), "arbres détectés\n"))

# ---------
# 7. Segmentation arbre par arbre
# ---------
algo <- dalponte2016(
  chm = chm,
  treetops = ttops
)

las_seg <- segment_trees(las_norm, algo)

cat("✅ Segmentation terminée\n")

# ---------
# 8. Calcul des métriques par arbre
# ---------
tree_metrics <- tree_metrics(
  las_seg,
  .stdtreemetrics
)

cat("✅ Hauteurs calculées\n")

# ---------
# 9. Statistiques globales
# ---------
cat("\n--- STATISTIQUES ---\n")
cat("Nombre de pins :", nrow(tree_metrics), "\n")
cat("Hauteur moyenne :", round(mean(tree_metrics$Zmax), 2), "m\n")
cat("Hauteur max :", round(max(tree_metrics$Zmax), 2), "m\n")
cat("Écart-type hauteur :", round(sd(tree_metrics$Zmax), 2), "m\n")

# ---------
# 10. Export carte 2D (GeoJSON)
# ---------
trees_sf <- st_as_sf(
  tree_metrics,
  coords = c("X", "Y"),
  crs = st_crs(las)
)

write_sf(trees_sf, "pins_hauteur.geojson")

cat("\n✅ FICHIER pins_hauteur.geojson CRÉÉ\n")

