# NISAR L-Band Observations of GERD

## What NISAR adds

NISAR is a joint NASA-ISRO radar mission. Its L-band instrument uses a longer
wavelength than Sentinel-1's C-band, so it can penetrate vegetation more deeply
and is sensitive to soil moisture and biomass as well as surface water. For the
GERD reservoir, NISAR provides an independent L-band view that complements the
long Sentinel-1 C-band VV record.

## Curated NISAR scenes over GERD

The project uses two NISAR Level-2 GCOV scenes over the GERD analysis window:

- `2026-10-25`: `NISAR_L2_PR_GCOV_034_021_D_083_2005_DHDH_A_20261025T160621_20261025T160656_P05036_N_F_J_001`, track 21, descending, HH/HV available; HH processed.
- `2026-11-06`: `NISAR_L2_PR_GCOV_035_021_D_083_2005_SHSH_A_20261106T160622_20261106T160656_P05036_N_F_J_001`, track 21, descending, HH.

The two acquisitions are about 12 days apart and cover the same reservoir. They
are not intended to replace the longer Sentinel-1 C-band series.

## Full GCOV processing

The app downloads the full NISAR GCOV HDF5 products with a NASA Earthdata token.
The products are approximately 1.98 GB and 1.54 GB. Processing uses the
frequency-A `HHHH` covariance term, which is RTC-calibrated gamma0 linear power on
a 20 m UTM grid. Values are converted to dB with `10*log10(HHHH)`, cropped to the
GERD window in EPSG:32636, and masked with `0 < mask < 255`. Noise correction was
not applied by the NISAR processor.

The two dates share one Otsu threshold computed from both valid crops (about
`-14.05 dB`). The resulting HH water masks give `936.6` and `958.5` sq km.
Persistent water is `881.9` sq km, with `54.7` sq km lost and `76.7` sq km new,
for a net change of `+21.9` sq km and a Jaccard overlap of `0.870`.

## Interpretation limits

These are calibrated, threshold-based estimates, not independently validated
water products. L-band HH is not directly comparable to Sentinel-1 C-band VV, and
the 12-day interval is short enough that small changes may reflect threshold,
speckle, or moisture variation. The calibrated overlays are `nisar_*_gcov.png`;
the water masks are `nisar_*_water.png`.

## Reading the L-band view

Calm open water still appears dark at L-band because the surface reflects the
radar pulse away from the satellite. The surrounding vegetation, rough terrain,
and dam infrastructure usually return more energy and appear brighter. L-band
can see through more vegetation than C-band, so the NISAR view may show
shoreline and wetland structure differently from Sentinel-1. Use the two
missions together: Sentinel-1 for the long filling history and NISAR for a
complementary longer-wavelength snapshot.
