# GDSight

Interactive SKY130 GDSII inspection in the browser, with real 3D GLB exports and Quest-oriented interaction patterns.

This repository now contains a Phase 0 browser viewer driven by real SKY130 GDSII data from Christoph Weiser's `sky130_cw_ip` project.

## Data source

- `external/sky130_cw_ip/` is a local clone of the public repo
- `data/design.gds` is the decompressed design GDS used for export
- `scripts/export_sky130_demo.py` converts selected existing GDS cells into browser-friendly JSON
- `scripts/export_gds_glb.py` exports selected existing GDS cells to `.glb`

## Run the viewer

```bash
python3 viewer/serve.py
```

Then open `http://127.0.0.1:8080`.

## Regenerate the browser datasets

```bash
./venv/bin/python scripts/export_sky130_demo.py
```

## Export GLB artifacts

Export all configured detail cells:

```bash
./venv/bin/python scripts/export_gds_glb.py
```

Export one cell:

```bash
./venv/bin/python scripts/export_gds_glb.py --slug regulator
```

Artifacts are written under `output/glb/`.

## What is implemented

- Top-level and sub-block placement overviews derived from actual GDS references
- Detailed 3D views for actual `bandgap`, `regulator`, `bias`, `sar__comparator`, and `sar__dac` cells
- SKY130 layer stack mapping for drawn metal/device layers plus contact/via layers
- Real `GDSII -> GLB` export for the same detailed SKY130 cells
- Browser viewer loads detail datasets from `.glb` artifacts with a visible loading progress bar
- Layer or block visibility toggles
- Grab-mode interaction intended to approximate Quest-style world manipulation

## Current limits

- The browser export currently covers the main SKY130 visualization stack: drawn layers (`datatype 20`) plus contact/via layers (`datatype 44`)
- Implant and marker layers outside that core stack are still omitted
- The overview scenes still use generated JSON placement data; the detailed cell views use GLB
- The first GLB pass emits non-indexed triangle meshes, so files are larger than they need to be; optimization/compression is the next step
