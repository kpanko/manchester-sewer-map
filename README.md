# Manchester Sewer & Storm Drain Maps

Interactive maps of the underground pipe systems in Manchester, Connecticut, built from the town's public GIS data.

- **[Sewer map](https://kpanko.github.io/manchester-sewer-map/)** (`index.html`): the sanitary sewer system. 5,684 pipe segments (about 219 miles) and 18 pump stations, colored by which treatment plant each pipe drains to.
- **[Storm drain map](https://kpanko.github.io/manchester-sewer-map/storm.html)** (`storm.html`): the storm drain system. About 15,000 pipes (254 miles), 902 outfalls and 10,000 catch basins, colored by drainage area.

Tap any pipe on either map to trace it downstream. The sewer map shows the route to the treatment plant, the streets it follows, whether it passes a pump station, and an elevation profile. The storm map shows where the rainwater comes out, which stream or pond it reaches, the pipe sizes along the way, and an elevation profile. A checkbox highlights storm pipes 4 ft and larger.

Each page is a single self-contained file; the only external file it loads is Leaflet from cdnjs.

## Where Manchester's sewage goes

| Destination | Pipe segments |
|---|---|
| Hockanum River WPCF (120 Thrall Rd) | 5,289 |
| South Windsor | 153 |
| Vernon | 126 |
| East Hartford / MDC | 35 |
| Septic, inactive, or trace ends at a data gap | 81 |

## Where Manchester's rainwater goes

Storm drains carry untreated rainwater straight to streams and ponds; they are a separate system from the sewers.

| Destination | Pipe segments |
|---|---|
| A stream or pond, through an outfall | 14,791 |
| Dry wells and infiltrators (soaks into the ground) | 269 |
| Detention basins | 229 |
| Trace ends at a data gap | 741 |

## How the trace works

Each pipe in the town's GIS records the structure IDs at its upstream and downstream ends. The build scripts link every pipe to the one it drains into:

1. Follow the downstream ID to the pipe that starts there, but only if the two pipes are within 100 ft of each other. Some ID links point to pipes far away and are treated as errors.
2. If there's no usable ID link, use geometry: the pipe that starts at this pipe's downstream end, or a larger pipe that passes through it (a mid-line tie-in).

Following those links from any pipe reaches a treatment plant, a pipe that leaves town, a storm outfall, a dry well or detention basin, or a dead end. Dead ends are almost always gaps in the data, not real dead ends.

For the sewer map, pumping is flagged when a route passes a pump station or a pipe the town marks as a force main. The trace destinations agree with the town's own `FLOW_DESC` field on nearly every pipe.

For the storm map, the receiving water is the nearest pond or stream on the town's water-body map. Many small brooks and wetlands aren't mapped, so those outfalls name the nearest mapped water instead. The storm data has no street names, so each pipe is labeled with the nearest street, or "off-street" beyond 100 ft. A few storm pipe records have impossible sizes (like 1,818″ tall); the map ignores sizes that can't be real.

## Data

Snapshots of the Town of Manchester's public ArcGIS server:

- [UtilitySystem/Sanitary](https://gisweb.manchesterct.gov/giswebserver/rest/services/UtilitySystem/Sanitary/MapServer): sewer pipes and pump stations (pulled September 22, 2026)
- [UtilitySystem/Storm](https://gisweb.manchesterct.gov/giswebserver/rest/services/UtilitySystem/Storm/MapServer): drainage pipes, outfalls, catch basins, dry wells, detention basins (pulled September 23, 2026)
- [Basemaps/ManchesterBasemap](https://gisweb.manchesterct.gov/giswebserver/rest/services/Basemaps/ManchesterBasemap/MapServer): ponds, rivers and brooks
- [StreetName](https://gisweb.manchesterct.gov/giswebserver/rest/services/StreetName/MapServer): street centerlines

`data/` holds the raw pulls. Coordinates are CT State Plane feet (EPSG:2234), stored as `(x - X0) / 5`, `(y - Y0) / 5`.

These are unofficial maps built from public data. The town's records contain errors and gaps, so check with the Town of Manchester before relying on them for anything that matters. Storm drains are dangerous confined spaces that can flood suddenly; this map is not an invitation to enter them.

## Rebuilding

```
python scripts/fetch_data.py         # re-pull sewer data (overwrites data/)
python scripts/fetch_storm_data.py   # re-pull storm data (overwrites data/)
python scripts/build.py              # rebuild index.html
python scripts/build_storm.py        # rebuild storm.html
```

All scripts use only the Python standard library.
