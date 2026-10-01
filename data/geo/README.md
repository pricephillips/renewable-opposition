# County geometry

Copied from `pricephillips/data-center-map` `data/geo/` at `0938c30`
(passoff B4, its spec 009), with an attribution line; nothing is imported
from that repository.

`counties_2024.topojson` is the county geometry `renewable-opposition-map.html`
draws its county choropleth on. One TopoJSON object, `counties`; each
geometry's `id` is the 5-digit county FIPS and `properties.name` is the Census
name. `counties_2024_manifest.json` records where the file came from, its
SHA-256, size and feature count, as built in data-center-map.

The page loads it from this repository (`./data/geo/counties_2024.topojson`),
decodes it with topojson-client 3.1.0 (jsdelivr, then unpkg) and joins it to
records on `county_fips`, which `scripts/classify.py` derives. It replaced
plotly's pre-2015 county GeoJSON, which had no polygon for Connecticut's nine
planning regions (09110 to 09190), Chugach (02063), Copper River (02066),
Kusilvak (02158) or Oglala Lakota (46102).

## Writer

None in this repository; `config/layers.json` declares `data/geo/*` as
copied reference data. In data-center-map, the `boundaries` job of
`acquire-geo-sources.yml` builds it from the Census cartographic boundary file
`cb_2024_us_county_5m.zip` (mapshaper, then a coverage gate). To refresh it
here, copy both files again from data-center-map's `main` and update the
commit named above.

## Check

`node tests/ui/check_geometry.js` fails if the file's SHA-256 differs from the
manifest, if any geometry id repeats, if the file is over 1 MB, or if any
`county_fips` in `data/processed/restrictions.json` or
`contested_projects.json` has no polygon.
