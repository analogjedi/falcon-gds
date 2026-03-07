from __future__ import annotations

import json
from collections import Counter

import gdstk

from sky130_common import DETAIL_DATASETS, GDS_PATH, LAYER_STACK, OVERVIEW_DATASETS, ROOT, VIEWER_DATA_DIR, get_cell


def round_point(point: tuple[float, float]) -> list[float]:
    return [round(point[0], 3), round(point[1], 3)]


def serialize_bbox(bbox) -> dict[str, list[float]]:
    return {"min": round_point(tuple(bbox[0])), "max": round_point(tuple(bbox[1]))}


def export_detail_dataset(library: gdstk.Library, config: dict[str, str]) -> None:
    cell = get_cell(library, config["cell"])
    flat = cell.copy(f"{cell.name}_flat_export")
    flat.flatten()
    bbox = flat.bounding_box()
    if bbox is None:
        raise ValueError(f"No geometry found in {cell.name}")

    min_x, min_y = bbox[0]
    layer_polygons: dict[str, dict[str, object]] = {}
    ignored = Counter()

    for polygon in flat.polygons:
        key = (polygon.layer, polygon.datatype)
        layer_meta = LAYER_STACK.get(key)
        if layer_meta is None:
            ignored[key] += 1
            continue

        layer_key = f"{polygon.layer}:{polygon.datatype}"
        entry = layer_polygons.setdefault(
            layer_key,
            {
                "key": layer_key,
                "layer": polygon.layer,
                "datatype": polygon.datatype,
                **layer_meta,
                "polygons": [],
            },
        )

        points = polygon.points
        coords = []
        for point in points:
            relative = (float(point[0] - min_x), float(point[1] - min_y))
            if not coords or coords[-1] != round_point(relative):
                coords.append(round_point(relative))
        if len(coords) >= 3 and coords[0] == coords[-1]:
            coords.pop()
        if len(coords) >= 3:
            entry["polygons"].append(coords)

    layers = []
    total_polygons = 0
    for layer in sorted(layer_polygons.values(), key=lambda item: (item["z_bottom"], item["layer"])):
        layer["polygon_count"] = len(layer["polygons"])
        total_polygons += layer["polygon_count"]
        layers.append(layer)

    payload = {
        "kind": "detail",
        "slug": config["slug"],
        "title": config["title"],
        "category": config["category"],
        "summary": config["summary"],
        "source": {
            "gds": str(GDS_PATH.relative_to(ROOT)),
            "cell": cell.name,
            "origin": "Christoph Weiser sky130_cw_ip",
        },
        "bounds": serialize_bbox(bbox),
        "size_um": [round(float(bbox[1][0] - bbox[0][0]), 3), round(float(bbox[1][1] - bbox[0][1]), 3)],
        "layer_count": len(layers),
        "polygon_count": total_polygons,
        "ignored_layers": {f"{layer}:{datatype}": count for (layer, datatype), count in ignored.items()},
        "layers": layers,
    }

    VIEWER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = VIEWER_DATA_DIR / f"{config['slug']}.json"
    out_path.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"wrote {out_path.relative_to(ROOT)} polygons={total_polygons}")


def export_overview_dataset(library: gdstk.Library, config: dict[str, object]) -> None:
    cell = get_cell(library, config["cell"])
    bbox = cell.bounding_box()
    if bbox is None:
        raise ValueError(f"No geometry found in {cell.name}")

    references = []
    ref_config = config["references"]
    for reference in cell.references:
        ref_name = getattr(reference, "cell_name", None) or getattr(getattr(reference, "cell", None), "name", None)
        if ref_name not in ref_config:
            continue
        ref_bbox = reference.bounding_box()
        if ref_bbox is None:
            continue

        meta = ref_config[ref_name]
        references.append(
            {
                "cell": ref_name,
                "title": meta["title"],
                "category": meta["category"],
                "color": meta["color"],
                "note": meta["note"],
                "bounds": serialize_bbox(ref_bbox),
                "size_um": [
                    round(float(ref_bbox[1][0] - ref_bbox[0][0]), 3),
                    round(float(ref_bbox[1][1] - ref_bbox[0][1]), 3),
                ],
                "origin_um": round_point(tuple(reference.origin)),
                "rotation": round(float(getattr(reference, "rotation", 0.0) or 0.0), 6),
                "x_reflection": bool(getattr(reference, "x_reflection", False)),
            }
        )

    payload = {
        "kind": "overview",
        "slug": config["slug"],
        "title": config["title"],
        "summary": config["summary"],
        "source": {
            "gds": str(GDS_PATH.relative_to(ROOT)),
            "cell": cell.name,
            "origin": "Christoph Weiser sky130_cw_ip",
        },
        "bounds": serialize_bbox(bbox),
        "size_um": [round(float(bbox[1][0] - bbox[0][0]), 3), round(float(bbox[1][1] - bbox[0][1]), 3)],
        "references": references,
    }

    VIEWER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = VIEWER_DATA_DIR / f"{config['slug']}.json"
    out_path.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"wrote {out_path.relative_to(ROOT)} blocks={len(references)}")


def main() -> None:
    library = gdstk.read_gds(GDS_PATH)
    for config in DETAIL_DATASETS:
        export_detail_dataset(library, config)
    for config in OVERVIEW_DATASETS:
        export_overview_dataset(library, config)


if __name__ == "__main__":
    main()
