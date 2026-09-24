"""Pull Manchester, CT storm drain data from the town's public ArcGIS server.

Writes data/manchester-storm-network.json in the format build_storm.py expects.
Coordinates are CT State Plane feet (EPSG:2234), stored as (x - X0) / 5, (y - Y0) / 5,
using the same origin as the sewer data.
"""
import json, os, urllib.parse, urllib.request

BASE = "https://gisweb.manchesterct.gov/giswebserver/rest/services"
STORM = f"{BASE}/UtilitySystem/Storm/MapServer"
BASEMAP = f"{BASE}/Basemaps/ManchesterBasemap/MapServer"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "manchester-storm-network.json")
X0, Y0 = 1044000, 830000


def query_all(url, fields, **extra):
    feats, offset = [], 0
    while True:
        params = dict(f="json", where="1=1", outFields=fields, returnGeometry="true", outSR=2234,
                      resultOffset=offset, resultRecordCount=2000, orderByFields="OBJECTID", **extra)
        with urllib.request.urlopen(f"{url}/query?{urllib.parse.urlencode(params)}", timeout=180) as r:
            data = json.load(r)
        if "error" in data:
            raise RuntimeError(data["error"])
        feats += data["features"]
        if len(data["features"]) < 2000 and not data.get("exceededTransferLimit"):
            return feats
        offset += 2000


q = lambda v: round(v / 5)
enc = lambda pl: [c for x, y in pl for c in (q(x - X0), q(y - Y0))]
r1 = lambda v: None if not v else round(v * 10) / 10
s = lambda v: None if v in (None, " ", "NUL") else (str(v).strip() or None)


def plen(g):
    return round(sum(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** .5 for pl in g["paths"] for a, b in zip(pl, pl[1:])))


def main():
    pipes = query_all(f"{STORM}/11", "MAPID,UP_STRM_MAPID,DWN_STRM_MAPID,DIAMETER,HEIGHT,WIDTH,CROSS_SECTION,MATERIAL,"
                      "CULVERT,UP_STRM_INV,DWN_STRM_INV,OWNER,YR_INSTALL,CONST_STATUS,REMARKS", maxAllowableOffset=2)
    outlets = query_all(f"{STORM}/5", "MAPID,TYPE,MATERIAL,OWNER,YR_INSTALL,CONST_STATUS,REMARKS,INV_ELEV,MS4,MS4_NAME,DISCHARGE_TYPE")
    cbs = query_all(f"{STORM}/7", "MAPID,CONST_STATUS")
    dws = query_all(f"{STORM}/6", "MAPID,CONST_STATUS")
    dets = query_all(f"{STORM}/13", "MAPID,TYPE,OWNER,CONST_STATUS", maxAllowableOffset=5)
    water = query_all(f"{BASEMAP}/14", "TYPE,NAME", maxAllowableOffset=5)
    pt = lambda f: f.get("geometry") and f["geometry"].get("x") is not None
    out = dict(X0=X0, Y0=Y0, unit=5,
               pipeFields=["id", "up", "dn", "dia", "h", "w", "shape", "mat", "culvert", "uinv", "dinv", "owner", "yr",
                           "status", "remarks", "len", "paths"],
               pipes=[[a["MAPID"], a["UP_STRM_MAPID"], a["DWN_STRM_MAPID"], a["DIAMETER"] or 0, a["HEIGHT"] or 0,
                       a["WIDTH"] or 0, s(a["CROSS_SECTION"]), s(a["MATERIAL"]), s(a["CULVERT"]), r1(a["UP_STRM_INV"]),
                       r1(a["DWN_STRM_INV"]), s(a["OWNER"]), a["YR_INSTALL"] or None, s(a["CONST_STATUS"]),
                       s(a["REMARKS"]), plen(f["geometry"]), [enc(pl) for pl in f["geometry"]["paths"]]]
                      for f in pipes if f.get("geometry") for a in [f["attributes"]]],
               outletFields=["id", "type", "mat", "owner", "yr", "status", "remarks", "inv", "ms4", "ms4name",
                             "discharge", "x", "y"],
               outlets=[[a["MAPID"], s(a["TYPE"]), s(a["MATERIAL"]), s(a["OWNER"]), a["YR_INSTALL"] or None,
                         s(a["CONST_STATUS"]), s(a["REMARKS"]), r1(a["INV_ELEV"]), s(a["MS4"]), s(a["MS4_NAME"]),
                         s(a["DISCHARGE_TYPE"]), q(f["geometry"]["x"] - X0) if pt(f) else None,
                         q(f["geometry"]["y"] - Y0) if pt(f) else None]
                        for f in outlets for a in [f["attributes"]]],
               catchBasins=[c for f in cbs if pt(f) and f["attributes"]["CONST_STATUS"] != "ABANDONED"
                            for c in (q(f["geometry"]["x"] - X0), q(f["geometry"]["y"] - Y0))],
               dryWells=[c for f in dws if pt(f) for c in (q(f["geometry"]["x"] - X0), q(f["geometry"]["y"] - Y0))],
               detention=[[s(f["attributes"]["TYPE"]), s(f["attributes"]["OWNER"]), [enc(r) for r in f["geometry"]["rings"]]]
                          for f in dets if f.get("geometry")],
               water=[[s(f["attributes"]["TYPE"]), s(f["attributes"]["NAME"]), [enc(r) for r in f["geometry"]["rings"]]]
                      for f in water if f.get("geometry")])
    with open(OUT, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print(f"{len(out['pipes'])} pipes, {len(out['outlets'])} outlets, {len(out['catchBasins']) // 2} catch basins -> {OUT}")


if __name__ == "__main__":
    main()
