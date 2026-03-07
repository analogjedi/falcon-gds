from __future__ import annotations

import argparse
from collections import Counter

import gdstk
import mapbox_earcut as earcut
import numpy as np
from pygltflib import (
    ARRAY_BUFFER,
    FLOAT,
    GLTF2,
    VEC3,
    Accessor,
    Asset,
    Attributes,
    Buffer,
    BufferView,
    Material,
    Mesh,
    Node,
    PbrMetallicRoughness,
    Primitive,
    Scene,
)

from sky130_common import DETAIL_DATASETS, GDS_PATH, GLB_OUTPUT_DIR, LAYER_STACK, ROOT, get_cell


UP = np.array([0.0, 1.0, 0.0], dtype=np.float32)
DOWN = np.array([0.0, -1.0, 0.0], dtype=np.float32)


def sanitize_vertices(points: np.ndarray) -> np.ndarray:
    if len(points) < 3:
        return np.empty((0, 2), dtype=np.float64)
    if np.allclose(points[0], points[-1]):
        points = points[:-1]
    deduped = [points[0]]
    for point in points[1:]:
        if not np.allclose(point, deduped[-1]):
            deduped.append(point)
    if len(deduped) >= 3 and np.allclose(deduped[0], deduped[-1]):
        deduped.pop()
    if len(deduped) < 3:
        return np.empty((0, 2), dtype=np.float64)
    return np.asarray(deduped, dtype=np.float64)


def append_triangle(
    positions: list[np.ndarray],
    normals: list[np.ndarray],
    a: np.ndarray,
    b: np.ndarray,
    c: np.ndarray,
    expected_normal: np.ndarray | None = None,
    outward_hint: np.ndarray | None = None,
) -> None:
    normal = np.cross(b - a, c - a)
    length = np.linalg.norm(normal)
    if length < 1e-9:
        return
    normal = normal / length

    if expected_normal is not None and np.dot(normal, expected_normal) < 0:
        b, c = c, b
        normal = -normal
    elif outward_hint is not None and np.dot(normal, outward_hint) < 0:
        b, c = c, b
        normal = -normal

    positions.extend((a, b, c))
    normals.extend((normal, normal, normal))


def build_polygon_mesh(points: np.ndarray, z_bottom: float, z_top: float, center_x: float, center_y: float) -> tuple[list[np.ndarray], list[np.ndarray]]:
    points = sanitize_vertices(points)
    if len(points) < 3:
        return [], []

    positions: list[np.ndarray] = []
    normals: list[np.ndarray] = []
    ring_end_indices = np.array([len(points)], dtype=np.uint32)
    triangles = earcut.triangulate_float64(points, ring_end_indices).reshape(-1, 3)

    def lift(point: np.ndarray, height: float) -> np.ndarray:
        return np.array([point[0] - center_x, height, point[1] - center_y], dtype=np.float32)

    top_vertices = np.array([lift(point, z_top) for point in points], dtype=np.float32)
    bottom_vertices = np.array([lift(point, z_bottom) for point in points], dtype=np.float32)
    polygon_center = np.array([points[:, 0].mean() - center_x, (z_bottom + z_top) * 0.5, points[:, 1].mean() - center_y], dtype=np.float32)

    for i0, i1, i2 in triangles:
        append_triangle(positions, normals, top_vertices[i0], top_vertices[i1], top_vertices[i2], expected_normal=UP)
        append_triangle(positions, normals, bottom_vertices[i0], bottom_vertices[i1], bottom_vertices[i2], expected_normal=DOWN)

    for index in range(len(points)):
        next_index = (index + 1) % len(points)
        b0 = bottom_vertices[index]
        b1 = bottom_vertices[next_index]
        t0 = top_vertices[index]
        t1 = top_vertices[next_index]
        edge_center = (b0 + b1 + t0 + t1) / 4.0
        outward_hint = edge_center - polygon_center
        outward_hint[1] = 0.0

        append_triangle(positions, normals, b0, b1, t1, outward_hint=outward_hint)
        append_triangle(positions, normals, b0, t1, t0, outward_hint=outward_hint)

    return positions, normals


def hex_to_rgba(color: str, opacity: float) -> list[float]:
    color = color.lstrip("#")
    return [int(color[0:2], 16) / 255.0, int(color[2:4], 16) / 255.0, int(color[4:6], 16) / 255.0, opacity]


def pad4(blob: bytearray) -> None:
    padding = (-len(blob)) % 4
    if padding:
        blob.extend(b"\x00" * padding)


def add_blob_and_accessor(
    blob: bytearray,
    gltf: GLTF2,
    array: np.ndarray,
    accessor_type: str,
    component_type: int,
) -> int:
    array = np.ascontiguousarray(array)
    pad4(blob)
    offset = len(blob)
    raw = array.tobytes()
    blob.extend(raw)

    gltf.bufferViews.append(
        BufferView(
            buffer=0,
            byteOffset=offset,
            byteLength=len(raw),
            target=ARRAY_BUFFER,
        )
    )

    accessor_index = len(gltf.accessors)
    mins = array.min(axis=0).tolist() if array.ndim > 1 else [float(array.min())]
    maxs = array.max(axis=0).tolist() if array.ndim > 1 else [float(array.max())]
    gltf.accessors.append(
        Accessor(
            bufferView=len(gltf.bufferViews) - 1,
            byteOffset=0,
            componentType=component_type,
            count=int(array.shape[0]),
            type=accessor_type,
            min=mins,
            max=maxs,
        )
    )
    return accessor_index


def export_cell(library: gdstk.Library, config: dict[str, str], out_dir: str) -> None:
    cell = get_cell(library, config["cell"])
    flat = cell.copy(f"{cell.name}_flat_glb")
    flat.flatten()
    bbox = flat.bounding_box()
    if bbox is None:
        raise ValueError(f"No geometry found in {cell.name}")

    center_x = float((bbox[0][0] + bbox[1][0]) * 0.5)
    center_y = float((bbox[0][1] + bbox[1][1]) * 0.5)
    grouped: dict[tuple[int, int], list[np.ndarray]] = {}
    ignored = Counter()

    for polygon in flat.polygons:
        key = (polygon.layer, polygon.datatype)
        if key not in LAYER_STACK:
            ignored[key] += 1
            continue
        grouped.setdefault(key, []).append(np.asarray(polygon.points, dtype=np.float64))

    gltf = GLTF2(asset=Asset(version="2.0"))
    gltf.scenes = [Scene(nodes=[])]
    gltf.scene = 0
    gltf.nodes = []
    gltf.meshes = []
    gltf.materials = []
    gltf.accessors = []
    gltf.bufferViews = []
    blob = bytearray()

    total_vertices = 0
    rendered_layers = 0
    for (layer, datatype), polygons in sorted(grouped.items(), key=lambda item: (LAYER_STACK[item[0]]["z_bottom"], item[0][0], item[0][1])):
        meta = LAYER_STACK[(layer, datatype)]
        position_parts: list[np.ndarray] = []
        normal_parts: list[np.ndarray] = []

        for points in polygons:
            positions, normals = build_polygon_mesh(points, meta["z_bottom"], meta["z_top"], center_x, center_y)
            if positions:
                position_parts.append(np.asarray(positions, dtype=np.float32))
                normal_parts.append(np.asarray(normals, dtype=np.float32))

        if not position_parts:
            continue

        positions_array = np.vstack(position_parts)
        normals_array = np.vstack(normal_parts)
        total_vertices += int(positions_array.shape[0])
        rendered_layers += 1

        position_accessor = add_blob_and_accessor(blob, gltf, positions_array, VEC3, FLOAT)
        normal_accessor = add_blob_and_accessor(blob, gltf, normals_array, VEC3, FLOAT)

        gltf.materials.append(
            Material(
                name=f"{meta['name']} ({layer}/{datatype})",
                doubleSided=True,
                alphaMode="BLEND" if meta["opacity"] < 0.999 else "OPAQUE",
                pbrMetallicRoughness=PbrMetallicRoughness(
                    baseColorFactor=hex_to_rgba(meta["color"], meta["opacity"]),
                    metallicFactor=0.12,
                    roughnessFactor=0.55,
                ),
            )
        )

        primitive = Primitive(
            attributes=Attributes(POSITION=position_accessor, NORMAL=normal_accessor),
            material=len(gltf.materials) - 1,
            mode=4,
        )
        gltf.meshes.append(Mesh(name=f"{meta['name']}_{layer}_{datatype}", primitives=[primitive]))
        gltf.nodes.append(Node(name=f"{meta['name']} ({layer}/{datatype})", mesh=len(gltf.meshes) - 1))
        gltf.scenes[0].nodes.append(len(gltf.nodes) - 1)

    pad4(blob)
    gltf.buffers = [Buffer(byteLength=len(blob))]
    gltf.set_binary_blob(bytes(blob))

    output_dir = ROOT / out_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{config['slug']}.glb"
    gltf.save_binary(out_path)

    size_um = (float(bbox[1][0] - bbox[0][0]), float(bbox[1][1] - bbox[0][1]))
    print(
        f"wrote {out_path.relative_to(ROOT)} layers={rendered_layers} vertices={total_vertices} "
        f"size_um=({size_um[0]:.2f},{size_um[1]:.2f}) ignored={sum(ignored.values())}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export selected SKY130 GDSII cells to GLB.")
    parser.add_argument(
        "--slug",
        action="append",
        dest="slugs",
        help="Dataset slug to export. Repeatable. Defaults to all detail datasets.",
    )
    parser.add_argument(
        "--outdir",
        default=str(GLB_OUTPUT_DIR.relative_to(ROOT)),
        help="Output directory relative to the repo root.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configs = DETAIL_DATASETS
    if args.slugs:
        selected = set(args.slugs)
        configs = [config for config in DETAIL_DATASETS if config["slug"] in selected]
        missing = sorted(selected - {config["slug"] for config in configs})
        if missing:
            raise SystemExit(f"Unknown slug(s): {', '.join(missing)}")

    library = gdstk.read_gds(GDS_PATH)
    for config in configs:
        export_cell(library, config, args.outdir)


if __name__ == "__main__":
    main()
