"""Pull the USGS NHDPlus HR stream network around Manchester, CT, following it downstream
to the Connecticut River. Writes data/manchester-streams.json for build_storm.py.
"""
import json, os, urllib.parse, urllib.request

URL = "https://hydro.nationalmap.gov/arcgis/rest/services/NHDPlus_HR/MapServer/3/query"
FIELDS = "hydroseq,dnhydroseq,gnis_name,fcode,lengthkm,pathlength,totdasqkm,streamorde,maxelevsmo,minelevsmo"
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "manchester-streams.json")
X0, Y0 = 1044000, 830000
BOX = "1038000,824000,1082000,866000"  # CT State Plane ft (EPSG:2234) around Manchester
q = lambda v: round(v / 5)
enc = lambda pl: [c for x, y in pl for c in (q(x - X0), q(y - Y0))]


def get(**params):
    p = dict(f="json", outFields=FIELDS, returnGeometry="true", outSR=2234, maxAllowableOffset=5, **params)
    with urllib.request.urlopen(URL + "?" + urllib.parse.urlencode(p), timeout=180) as r:
        data = json.load(r)
    if "error" in data:
        raise RuntimeError(data["error"])
    return data


def main():
    feats, offset = [], 0
    while True:
        d = get(where="1=1", geometry=BOX, geometryType="esriGeometryEnvelope", inSR=2234,
                spatialRel="esriSpatialRelIntersects", resultOffset=offset, resultRecordCount=2000, orderByFields="OBJECTID")
        feats += d["features"]
        if not d.get("exceededTransferLimit") and len(d["features"]) < 2000:
            break
        offset += 2000
    have = {f["attributes"]["hydroseq"] for f in feats}
    frontier = {f["attributes"]["dnhydroseq"] for f in feats} - have - {0, None}
    for _ in range(60):  # follow rivers downstream until they reach the Connecticut River
        if not frontier:
            break
        d = get(where=f"hydroseq in ({','.join(str(h) for h in frontier)})")
        nxt = set()
        for f in d["features"]:
            a = f["attributes"]
            have.add(a["hydroseq"]); feats.append(f)
            if "Connecticut River" not in (a["gnis_name"] or "") and a["dnhydroseq"] and a["dnhydroseq"] not in have:
                nxt.add(a["dnhydroseq"])
        frontier = nxt
    out = dict(source="USGS NHDPlus HR, NetworkNHDFlowline", X0=X0, Y0=Y0, unit=5,
               fields=["hydroseq", "dn", "name", "fcode", "lenkm", "pathkm", "dasqkm", "order", "maxelev_cm", "minelev_cm", "paths"],
               lines=[[a["hydroseq"], a["dnhydroseq"] or 0, a["gnis_name"], a["fcode"], a["lengthkm"], a["pathlength"],
                       a["totdasqkm"], a["streamorde"], a["maxelevsmo"], a["minelevsmo"], [enc(pl) for pl in f["geometry"]["paths"]]]
                      for f in feats for a in [f["attributes"]]])
    with open(OUT, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print(f"{len(feats)} stream segments -> {OUT}")


if __name__ == "__main__":
    main()
