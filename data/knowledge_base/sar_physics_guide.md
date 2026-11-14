# SAR Physics Guide: Reading Radar Backscatter

## What Synthetic Aperture Radar Sees

Synthetic Aperture Radar (SAR) is an active microwave remote-sensing technique.
A satellite transmits its own radar pulses toward Earth and records the energy
that returns to the antenna, called backscatter. Unlike optical sensors, SAR does
not depend on sunlight, and its longer microwave wavelengths pass through clouds,
smoke, haze, and light rain. This all-weather capability is essential in
Ethiopia, where the Kiremt rainy season (roughly June to September) brings heavy
cloud cover that hides the Blue Nile gorge from optical satellites. Sentinel-1
operates in C-band (about 5.6 cm wavelength) and commonly acquires VV
(vertical-transmit, vertical-receive) polarization over land and water.

## Specular Reflection: Why Calm Water Is Dark

A smooth surface such as calm open water behaves like a mirror at radar
wavelengths. When the radar pulse strikes water at an oblique angle, almost all
of the energy is reflected away from the satellite in the forward direction,
and very little returns to the sensor. The result is a very low backscatter
value, which radar processors display as dark gray or pitch black. A black patch
in a SAR image is therefore often not missing data: it is a strong indication of
smooth, open water. Wind roughens the water surface and can increase the return,
so very windy days may make part of a lake appear lighter and mottled.

## Volume Scattering: Vegetation and Rough Ground

Vegetation canopies and rough natural terrain scatter radar energy in many
directions through their leaves, branches, and stems. This volume scattering
returns a moderate amount of energy to the sensor, so forests, cropland, and
shrubland typically appear as medium gray tones. Denser or taller vegetation
often appears brighter than sparse vegetation, although the exact tone depends
on moisture, structure, and viewing geometry.

## Double-Bounce and Bright Targets

Built structures, metal surfaces, and steep angular features can create
double-bounce scattering: the pulse bounces off the ground and then off a
vertical wall (or vice versa) back toward the satellite. This produces unusually
bright white returns. A concrete dam wall, embankments, bridges, buildings, and
some rocky cliffs therefore stand out as bright linear or geometric features.
The contrast between dark water and bright infrastructure is what makes SAR so
effective for mapping reservoirs and monitoring construction.

## Interpreting Change Between Two Dates

When comparing two SAR scenes, keep acquisition geometry, sensor, polarization,
and processing level constant, because changing these parameters can change the
image tone without any real change on the ground. A transition from mottled gray
or bright terrain to a large coherent dark region usually indicates new standing
water. Conversely, a dark region that becomes brighter may indicate falling water
levels, exposed mud, or vegetation regrowth. During reservoir filling, the water
body expands upstream and into side valleys, while the dam and steep banks remain
bright due to double-bounce and rough-surface scattering. These signatures allow
analysts to estimate surface-water extent even through clouds and at night.
