from __future__ import annotations

from pathlib import Path

import gdstk


ROOT = Path(__file__).resolve().parents[1]
GDS_PATH = ROOT / "data" / "design.gds"
VIEWER_DATA_DIR = ROOT / "viewer" / "data"
GLB_OUTPUT_DIR = ROOT / "output" / "glb"

LAYER_STACK = {
    (64, 20): {"name": "N-Well", "color": "#ba9776", "opacity": 0.24, "z_bottom": -1.0, "z_top": 0.0},
    (65, 20): {"name": "Diffusion", "color": "#43c96b", "opacity": 0.72, "z_bottom": -0.12, "z_top": 0.01},
    (66, 20): {"name": "Poly", "color": "#ef5d4c", "opacity": 0.84, "z_bottom": 0.0, "z_top": 0.18},
    (66, 44): {"name": "LiCon", "color": "#9c9da2", "opacity": 0.93, "z_bottom": 0.18, "z_top": 0.54},
    (67, 20): {"name": "LI", "color": "#8556af", "opacity": 0.82, "z_bottom": 0.54, "z_top": 0.64},
    (67, 44): {"name": "MCon", "color": "#9c9da2", "opacity": 0.93, "z_bottom": 0.64, "z_top": 0.97},
    (68, 20): {"name": "Metal 1", "color": "#4d7ced", "opacity": 0.82, "z_bottom": 0.97, "z_top": 1.33},
    (68, 44): {"name": "Via 1", "color": "#a6a8ad", "opacity": 0.94, "z_bottom": 1.33, "z_top": 1.68},
    (69, 20): {"name": "Metal 2", "color": "#4ab6d9", "opacity": 0.82, "z_bottom": 1.68, "z_top": 2.04},
    (69, 44): {"name": "Via 2", "color": "#a6a8ad", "opacity": 0.94, "z_bottom": 2.04, "z_top": 2.39},
    (70, 20): {"name": "Metal 3", "color": "#f0a13b", "opacity": 0.84, "z_bottom": 2.39, "z_top": 3.24},
    (70, 44): {"name": "Via 3", "color": "#a6a8ad", "opacity": 0.94, "z_bottom": 3.24, "z_top": 3.59},
    (71, 20): {"name": "Metal 4", "color": "#cf6ca7", "opacity": 0.84, "z_bottom": 3.59, "z_top": 4.44},
    (71, 44): {"name": "Via 4", "color": "#a6a8ad", "opacity": 0.94, "z_bottom": 4.44, "z_top": 4.79},
    (72, 20): {"name": "Metal 5", "color": "#d9c24a", "opacity": 0.84, "z_bottom": 4.79, "z_top": 6.07},
}

DETAIL_DATASETS = [
    {
        "slug": "bandgap",
        "cell": "bandgap",
        "title": "Bandgap Reference",
        "category": "Support Analog",
        "summary": "Actual SKY130 bandgap layout from Christoph Weiser's sky130_cw_ip design.",
    },
    {
        "slug": "regulator",
        "cell": "regulator",
        "title": "LDO Regulator",
        "category": "Power Management",
        "summary": "Actual LDO core layout used in the main support block. The main block instantiates this cell twice.",
    },
    {
        "slug": "bias",
        "cell": "bias",
        "title": "Bias Generator",
        "category": "Support Analog",
        "summary": "Actual bias generation layout with matched analog structures and routing.",
    },
    {
        "slug": "sar-comparator",
        "cell": "sar__comparator",
        "title": "SAR Comparator",
        "category": "SAR ADC",
        "summary": "Actual comparator macro from the 10-bit SAR ADC, including analog device layout and routing.",
    },
    {
        "slug": "sar-dac",
        "cell": "sar__dac",
        "title": "SAR Capacitive DAC",
        "category": "SAR ADC",
        "summary": "Actual DAC macro from the 10-bit SAR ADC. This is the most visually distinctive analog structure in the design.",
    },
]

OVERVIEW_DATASETS = [
    {
        "slug": "cw-top",
        "cell": "user_analog_project_wrapper",
        "title": "CW Top-Level Placement",
        "summary": "Top-level placement derived from GDS references inside user_analog_project_wrapper.",
        "references": {
            "sar_10b": {
                "title": "SAR ADC",
                "category": "ADC Macro",
                "color": "#4ab6d9",
                "note": "10-bit SAR ADC macro. The wrapper instantiates this block twice.",
            },
            "main": {
                "title": "Main Support Block",
                "category": "Support Analog",
                "color": "#f0a13b",
                "note": "Contains bandgap, two regulators, bias generation, clock selection, and test buffer logic.",
            },
            "decap_top": {
                "title": "Decap Array",
                "category": "Infrastructure",
                "color": "#3a5167",
                "note": "Repeated decoupling capacitor tiles surrounding the major macros.",
            },
        },
    },
    {
        "slug": "main-overview",
        "cell": "main",
        "title": "Main Support Floorplan",
        "summary": "Sub-block placement derived from GDS references inside the main support block.",
        "references": {
            "bandgap": {
                "title": "Bandgap",
                "category": "Reference",
                "color": "#ef5d4c",
                "note": "Voltage reference generator.",
            },
            "bias": {
                "title": "Bias Generator",
                "category": "Biasing",
                "color": "#43c96b",
                "note": "Bias distribution for the support analog macros.",
            },
            "regulator": {
                "title": "LDO",
                "category": "Power",
                "color": "#4d7ced",
                "note": "LDO regulator cell instantiated twice in the main support block.",
            },
            "testbuffer": {
                "title": "Test Buffer",
                "category": "I/O",
                "color": "#cf6ca7",
                "note": "Output buffer and mux for debug and characterization.",
            },
            "clksel": {
                "title": "Clock Select",
                "category": "Clocking",
                "color": "#8556af",
                "note": "Clock selection / support logic.",
            },
            "bias_basis_current": {
                "title": "Bias Basis",
                "category": "Biasing",
                "color": "#69b8a8",
                "note": "Bias basis current generator.",
            },
        },
    },
    {
        "slug": "sar-overview",
        "cell": "sar_10b",
        "title": "SAR ADC Floorplan",
        "summary": "Sub-block placement derived from GDS references inside the sar_10b macro.",
        "references": {
            "sar__dac": {
                "title": "CDAC",
                "category": "Capacitive DAC",
                "color": "#f0a13b",
                "note": "Two actual DAC cell instances form the differential CDAC array.",
            },
            "sar__comparator": {
                "title": "Comparator",
                "category": "Front End",
                "color": "#ef5d4c",
                "note": "Dynamic comparator with trim structures.",
            },
            "sar__sarlogic": {
                "title": "SAR Logic",
                "category": "Digital",
                "color": "#4d7ced",
                "note": "Standard-cell SAR control logic synthesized in OpenLane.",
            },
            "sar__latch": {
                "title": "Latch",
                "category": "Mixed-Signal",
                "color": "#8556af",
                "note": "Intermediate latch block near the comparator.",
            },
            "sar__buf_lvt": {
                "title": "Buffer",
                "category": "Support",
                "color": "#69b8a8",
                "note": "Buffer cell near the comparator / logic boundary.",
            },
        },
    },
]


def get_cell(library: gdstk.Library, name: str) -> gdstk.Cell:
    for cell in library.cells:
        if cell.name == name:
            return cell
    raise KeyError(f"Cell not found: {name}")
