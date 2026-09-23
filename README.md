# Manchester Sewer Map

An interactive map of the sanitary sewer system in Manchester, Connecticut: 5,684 pipe segments (about 219 miles) and 18 pump stations, colored by where each pipe's flow ends up.

Tap any pipe to trace it downstream. The page shows:

- the route to the treatment plant, highlighted on the map
- the streets it follows, with pipe sizes and lengths
- whether the route is all gravity or passes through a pump station
- an elevation profile of the pipe inverts
- how many pipes upstream drain into the selected one

Open `index.html` in a browser. It is a single self-contained page; the only external file it loads is Leaflet from cdnjs. With GitHub Pages turned on for this repo, the map is served at the repo's Pages URL.

## Where Manchester's sewage goes

| Destination | Pipe segments |
|---|---|
| Hockanum River WPCF (120 Thrall Rd) | 5,289 |
| South Windsor | 153 |
| Vernon | 126 |
| East Hartford / MDC | 35 |
| Septic, inactive, or trace ends at a data gap | 81 |

## How the trace works

Each pipe in the town's GIS records the manhole IDs at its upstream and downstream ends. `scripts/build.py` links every pipe to the one it drains into:

1. Follow the downstream manhole ID to the pipe that starts there, but only if the two pipes are within 100 ft of each other. About 120 ID links point to pipes far away and are treated as errors.
2. If there's no usable ID link, use geometry: the pipe that starts at this pipe's downstream end, or a larger pipe that passes through it (a mid-line tie-in).

Following those links from any pipe reaches either a treatment plant inlet, a pipe that leaves town, or a dead end. Dead ends are almost always gaps in the data, often newer pipes without attributes, not real dead ends. The trace destinations agree with the town's own `FLOW_DESC` field on nearly every pipe.

Pumping is flagged when a route passes a pipe whose downstream end is a pump station, or a pipe the town marks as a force main.

## Data

Snapshot pulled September 22, 2026 from the Town of Manchester's public ArcGIS server:

- [UtilitySystem/Sanitary](https://gisweb.manchesterct.gov/giswebserver/rest/services/UtilitySystem/Sanitary/MapServer): sewer pipes (layer 5) and pump stations (layer 2)
- [StreetName](https://gisweb.manchesterct.gov/giswebserver/rest/services/StreetName/MapServer): street centerlines

`data/manchester-sewer-network.json` holds the raw pull. Coordinates are CT State Plane feet (EPSG:2234), stored as `(x - X0) / 5`, `(y - Y0) / 5`.

This is an unofficial map built from public data. The town's records contain errors and gaps, so check with the Manchester Water & Sewer Department before relying on it for anything that matters.

## Rebuilding

```
python scripts/fetch_data.py   # re-pull from the town GIS (overwrites data/)
python scripts/build.py        # rebuild index.html from data/ and scripts/template.html
```

Both scripts use only the Python standard library.
