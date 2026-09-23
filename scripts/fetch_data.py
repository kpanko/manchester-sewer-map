"""Pull Manchester, CT sanitary sewer data from the town's public ArcGIS server.

Writes data/manchester-sewer-network.json in the compact format build.py expects.
Coordinates are CT State Plane feet (EPSG:2234), stored as (x - X0) / 5, (y - Y0) / 5.
"""
import json, math, os, urllib.parse, urllib.request

BASE = "https://gisweb.manchesterct.gov/giswebserver/rest/services"
SAN = f"{BASE}/UtilitySystem/Sanitary/MapServer"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "manchester-sewer-network.json")


def query_all(layer_url, fields, **extra):
    feats, offset = [], 0
    while True:
        params = dict(f="json", where="1=1", outFields=fields, returnGeometry="true", outSR=2234,
                      resultOffset=offset, resultRecordCount=2000, orderByFields="OBJECTID", **extra)
        with urllib.request.urlopen(f"{layer_url}/query?{urllib.parse.urlencode(params)}", timeout=120) as r:
            data = json.load(r)
        if "error" in data:
            raise RuntimeError(data["error"])
        feats += data["features"]
        if len(data["features"]) < 2000 and not data.get("exceededTransferLimit"):
            return feats
        offset += 2000


def main():
    pipes = query_all(f"{SAN}/5", "MAPID,UP_STRM_MAPID,DWN_STRM_MAPID,DIAMETER,MATERIAL,UP_STRM_INV,DWN_STRM_INV,"
                                   "STREET_NAME,FLOW_DESC,CONST_STATUS,OWNER,YR_INSTALL,REMARKS")
    pumps = query_all(f"{SAN}/2", "MAPID,NAME,OWNER,TYPE,YR_INSTALL")
    streets = query_all(f"{BASE}/StreetName/MapServer/0", "STREETNAME", maxAllowableOffset=12)

    xs = [x for p in pipes if p.get("geometry") for pl in p["geometry"]["paths"] for x, _ in pl]
    ys = [y for p in pipes if p.get("geometry") for pl in p["geometry"]["paths"] for _, y in pl]
    X0 = math.floor(min(xs) / 1000) * 1000 - 2000
    Y0 = math.floor(min(ys) / 1000) * 1000 - 2000
    q = lambda v: round(v / 5)
    enc = lambda pl: [[q(x - X0), q(y - Y0)] for x, y in pl]
    r1 = lambda v: None if v is None else round(v * 10) / 10

    names, idx = [], {}
    def si(s):
        s = (s or "").strip()
        if s not in idx:
            idx[s] = len(names); names.append(s)
        return idx[s]

    P = []
    for p in pipes:
        if not p.get("geometry"):
            continue
        a = p["attributes"]
        rem = a.get("REMARKS")
        P.append([a["MAPID"], a["UP_STRM_MAPID"], a["DWN_STRM_MAPID"], a["DIAMETER"], a["MATERIAL"],
                  r1(a["UP_STRM_INV"]), r1(a["DWN_STRM_INV"]), si(a["STREET_NAME"]), a["FLOW_DESC"],
                  a["CONST_STATUS"], a["OWNER"], a["YR_INSTALL"] or None,
                  rem if rem and rem not in ("NUL", " ") else None, 0,
                  [enc(pl) for pl in p["geometry"]["paths"]]])
    S = [[s["attributes"]["MAPID"], s["attributes"]["NAME"], s["attributes"]["OWNER"], s["attributes"]["TYPE"],
          s["attributes"]["YR_INSTALL"], q(s["geometry"]["x"] - X0), q(s["geometry"]["y"] - Y0)] for s in pumps]
    ST = {}
    for f in streets:
        ST.setdefault((f["attributes"]["STREETNAME"] or "").strip(), []).extend(enc(pl) for pl in f["geometry"]["paths"])

    out = dict(crs="EPSG:2234 (CT State Plane ft), coords = (x-X0)/5,(y-Y0)/5", X0=X0, Y0=Y0, unit=5,
               fields=["id", "up", "dn", "dia", "mat", "uinv", "dinv", "street", "flow", "status", "owner", "yr",
                       "remarks", "len", "paths"], streetNames=names, pipes=P, pumps=S, streets=ST)
    with open(OUT, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print(f"{len(P)} pipes, {len(S)} pump stations, {len(streets)} street segments -> {OUT}")


if __name__ == "__main__":
    main()
