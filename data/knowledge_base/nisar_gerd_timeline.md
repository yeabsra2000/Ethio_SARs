# NISAR L-Band Observations of GERD

## What NISAR adds

NISAR is a joint NASA-ISRO radar mission. Its L-band instrument uses a longer
wavelength than Sentinel-1's C-band, so it can penetrate vegetation more deeply
and is sensitive to soil moisture and biomass as well as surface water. For the
GERD reservoir, NISAR provides an independent L-band view that complements the
long Sentinel-1 C-band VV record.

## Curated NISAR scenes over GERD

The project uses two public NISAR Level-2 GCOV browse scenes over the GERD
analysis window:

- `2026-10-25`: `NISAR_L2_PR_GCOV_034_021_D_083_2005_DHDH_A_20261025T160621_20261025T160656_P05036_N_F_J_001`, track 21, descending, HH/HV.
- `2026-11-06`: `NISAR_L2_PR_GCOV_035_021_D_083_2005_SHSH_A_20261106T160622_20261106T160656_P05036_N_F_J_001`, track 21, descending, HH.

The two acquisitions are about 12 days apart and cover the same reservoir. The
timeline labels them as an L-band baseline and a 12-day repeat. They are not
intended to replace the longer Sentinel-1 C-band series.

## Browse images and full GCOV products

The full NISAR GCOV HDF5 product is about 1.46 GB per scene. Downloading it
requires a NASA Earthdata Login: the public product URL returns HTTP 401 without
authentication. The ASF `LATLON` browse PNG and KML are public, already geocoded
in EPSG:4326, and small enough to include in the demo. The app therefore uses the
browse PNGs for the map overlays. The full HDF5 product should be used for
calibrated, quantitative analysis.

## Approximate water-area estimates

The NISAR water-area values in the curated timeline (`1,110.2` and `1,043.2` sq
km) are derived from the public browse image with an Otsu threshold on the
low-backscatter pixels. They are approximate low-backscatter areas, not
calibrated water masks. The GERD analysis window is about 4,350 sq km, so the
estimates represent roughly one quarter of the window. Browse images have
already been contrast-stretched, and dark shadows or smooth surfaces can also be
misclassified. Do not compare these values directly with the curated Sentinel-1
water-area estimates as if they were the same measurement.

## Reading the L-band view

Calm open water still appears dark at L-band because the surface reflects the
radar pulse away from the satellite. The surrounding vegetation, rough terrain,
and dam infrastructure usually return more energy and appear brighter. L-band
can see through more vegetation than C-band, so the NISAR view may show
shoreline and wetland structure differently from Sentinel-1. Use the two
missions together: Sentinel-1 for the long filling history and NISAR for a
complementary longer-wavelength snapshot.
