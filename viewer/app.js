import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const DATASETS = [
  { slug: "cw-top", label: "CW Top Overview", mode: "json", metaPath: "./data/cw-top.json" },
  { slug: "main-overview", label: "Main Support Overview", mode: "json", metaPath: "./data/main-overview.json" },
  { slug: "sar-overview", label: "SAR ADC Overview", mode: "json", metaPath: "./data/sar-overview.json" },
  { slug: "bandgap", label: "Bandgap Detail", mode: "glb", metaPath: "./data/bandgap.json", glbPath: "/glb/bandgap.glb" },
  { slug: "regulator", label: "LDO Detail", mode: "glb", metaPath: "./data/regulator.json", glbPath: "/glb/regulator.glb" },
  { slug: "bias", label: "Bias Detail", mode: "glb", metaPath: "./data/bias.json", glbPath: "/glb/bias.glb" },
  { slug: "sar-comparator", label: "Comparator Detail", mode: "glb", metaPath: "./data/sar-comparator.json", glbPath: "/glb/sar-comparator.glb" },
  { slug: "sar-dac", label: "SAR DAC Detail", mode: "glb", metaPath: "./data/sar-dac.json", glbPath: "/glb/sar-dac.glb" },
];

const QUICK_DATASETS = ["cw-top", "main-overview", "sar-overview", "bandgap", "regulator", "bias", "sar-comparator", "sar-dac"];
const DATASET_BY_SLUG = new Map(DATASETS.map((dataset) => [dataset.slug, dataset]));
const gltfLoader = new GLTFLoader();

const dom = {
  canvas: document.querySelector("#scene"),
  datasetSelect: document.querySelector("#dataset-select"),
  datasetButtons: document.querySelector("#dataset-buttons"),
  loadStatus: document.querySelector("#load-status"),
  loadProgressTrack: document.querySelector("#load-progress-track"),
  loadProgressBar: document.querySelector("#load-progress-bar"),
  layerList: document.querySelector("#layer-list"),
  sceneStats: document.querySelector("#scene-stats"),
  datasetMeta: document.querySelector("#dataset-meta"),
  explodeRange: document.querySelector("#explode-range"),
  resetCamera: document.querySelector("#reset-camera"),
  controlHint: document.querySelector("#control-hint"),
  grabMode: document.querySelector("#grab-mode"),
  orbitMode: document.querySelector("#orbit-mode"),
};

const scene = new THREE.Scene();
scene.background = new THREE.Color("#08111a");
scene.fog = new THREE.Fog("#08111a", 800, 6800);

const renderer = new THREE.WebGLRenderer({ canvas: dom.canvas, antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;

const camera = new THREE.PerspectiveCamera(46, 1, 0.1, 30000);
camera.position.set(420, 340, 520);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.target.set(0, 25, 0);
controls.minDistance = 8;
controls.maxDistance = 12000;
controls.zoomToCursor = true;

const interactionState = { mode: "grab" };
const dragState = { active: false, pointerId: null, lastX: 0, lastY: 0 };
const cameraForward = new THREE.Vector3();
const cameraRight = new THREE.Vector3();
const cameraUp = new THREE.Vector3();
const translationDelta = new THREE.Vector3();
const raycaster = new THREE.Raycaster();
const screenCenter = new THREE.Vector2(0, 0);
const orbitPivot = new THREE.Vector3();

const ambient = new THREE.HemisphereLight("#dbe6f5", "#07111b", 1.7);
scene.add(ambient);

const keyLight = new THREE.DirectionalLight("#fff7ea", 1.25);
keyLight.position.set(900, 1200, 700);
scene.add(keyLight);

const fillLight = new THREE.DirectionalLight("#7ac9ff", 0.45);
fillLight.position.set(-550, 640, -320);
scene.add(fillLight);

const grid = new THREE.GridHelper(5000, 50, "#35546c", "#122030");
grid.position.y = -7.1;
scene.add(grid);

const axes = new THREE.AxesHelper(60);
scene.add(axes);

const contentRoot = new THREE.Group();
scene.add(contentRoot);

const state = {
  activeDataset: null,
  activeGroup: null,
  activeItems: [],
  activeRenderMode: "json",
  explodeAmount: Number(dom.explodeRange.value),
  loadToken: 0,
};

function disposeMaterial(material) {
  if (Array.isArray(material)) {
    material.forEach(disposeMaterial);
    return;
  }
  material.dispose();
}

function disposeGroup(group) {
  if (!group) {
    return;
  }
  group.traverse((child) => {
    if (child.geometry) {
      child.geometry.dispose();
    }
    if (child.material) {
      disposeMaterial(child.material);
    }
  });
}

function setLoadProgress(text, fraction = null, options = {}) {
  const { indeterminate = false, error = false } = options;
  dom.loadStatus.textContent = text;
  dom.loadProgressTrack.classList.remove("is-indeterminate", "is-error");

  if (error) {
    dom.loadProgressTrack.classList.add("is-error");
    dom.loadProgressBar.style.width = "100%";
    return;
  }

  if (indeterminate || fraction === null) {
    dom.loadProgressTrack.classList.add("is-indeterminate");
    dom.loadProgressBar.style.width = "38%";
    return;
  }

  dom.loadProgressBar.style.width = `${Math.max(0, Math.min(fraction, 1)) * 100}%`;
}

function setInteractionMode(mode) {
  interactionState.mode = mode;
  controls.enabled = mode === "orbit";
  dom.canvas.style.cursor = mode === "grab" ? (dragState.active ? "grabbing" : "grab") : "default";
  dom.grabMode.classList.toggle("is-active", mode === "grab");
  dom.orbitMode.classList.toggle("is-active", mode === "orbit");
  dom.controlHint.textContent =
    mode === "grab"
      ? "Drag to move the layout in X/Y. Hold Shift while dragging to push or pull depth."
      : "Left drag orbits around the center-screen hit point, right drag pans, and wheel or trackpad zoom goes toward the pointer.";

  if (mode === "orbit") {
    retargetOrbitPivot();
  }
}

function translateView(delta) {
  camera.position.add(delta);
  controls.target.add(delta);
  controls.update();
}

function moveViewFromDrag(deltaX, deltaY, depthOnly) {
  const distance = camera.position.distanceTo(controls.target);
  const moveScale = Math.max(distance * 0.0028, 0.04);

  camera.getWorldDirection(cameraForward).normalize();
  cameraRight.crossVectors(cameraForward, camera.up).normalize();
  cameraUp.copy(camera.up).normalize();
  translationDelta.set(0, 0, 0);

  if (depthOnly) {
    translationDelta.addScaledVector(cameraForward, deltaY * moveScale * 1.5);
  } else {
    translationDelta.addScaledVector(cameraRight, -deltaX * moveScale);
    translationDelta.addScaledVector(cameraUp, deltaY * moveScale);
  }

  translateView(translationDelta);
}

function fitCameraToObject(object) {
  const box = new THREE.Box3().setFromObject(object);
  if (box.isEmpty()) {
    return;
  }
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const maxSize = Math.max(size.x, size.y, size.z);
  const fitHeightDistance = maxSize / (2 * Math.tan((Math.PI * camera.fov) / 360));
  const distance = fitHeightDistance * 1.6;

  camera.position.set(center.x + distance * 0.96, center.y + distance * 0.72, center.z + distance * 0.88);
  controls.target.copy(center);
  controls.update();
}

function getOrbitableObjects() {
  return state.activeItems
    .filter((item) => item.object.visible)
    .map((item) => item.object);
}

function retargetOrbitPivot(ndc = screenCenter) {
  if (interactionState.mode !== "orbit" || !state.activeGroup) {
    return false;
  }

  const orbitableObjects = getOrbitableObjects();
  if (!orbitableObjects.length) {
    return false;
  }

  raycaster.setFromCamera(ndc, camera);
  const hits = raycaster.intersectObjects(orbitableObjects, false);
  if (!hits.length) {
    return false;
  }

  orbitPivot.copy(hits[0].point);
  controls.target.copy(orbitPivot);
  controls.update();
  return true;
}

function makeShape(points, offsetX, offsetY) {
  return new THREE.Shape(points.map(([x, y]) => new THREE.Vector2(x - offsetX, y - offsetY)));
}

function buildDetailScene(data) {
  const root = new THREE.Group();
  const items = [];
  const offsetX = data.size_um[0] / 2;
  const offsetY = data.size_um[1] / 2;

  data.layers.forEach((layer, index) => {
    if (!layer.polygons.length) {
      return;
    }
    const shapes = layer.polygons.map((polygon) => makeShape(polygon, offsetX, offsetY));
    const geometry = new THREE.ExtrudeGeometry(shapes, {
      depth: layer.z_top - layer.z_bottom,
      bevelEnabled: false,
      curveSegments: 1,
    });
    geometry.rotateX(Math.PI / 2);
    geometry.translate(0, layer.z_bottom, 0);
    geometry.computeVertexNormals();

    const material = new THREE.MeshPhysicalMaterial({
      color: layer.color,
      transparent: layer.opacity < 0.99,
      opacity: layer.opacity,
      metalness: 0.16,
      roughness: 0.55,
      transmission: layer.opacity < 0.4 ? 0.06 : 0,
      side: THREE.DoubleSide,
    });

    const mesh = new THREE.Mesh(geometry, material);
    mesh.renderOrder = index;
    root.add(mesh);

    items.push({
      id: layer.key,
      label: layer.name,
      subtitle: `GDS ${layer.layer}/${layer.datatype}`,
      metric: `${layer.polygon_count.toLocaleString()} polys`,
      color: layer.color,
      object: mesh,
      explodeIndex: index,
      baseY: 0,
    });
  });

  return { root, items };
}

function buildOverviewScene(data) {
  const root = new THREE.Group();
  const items = [];
  const offsetX = (data.bounds.min[0] + data.bounds.max[0]) / 2;
  const offsetY = (data.bounds.min[1] + data.bounds.max[1]) / 2;

  data.references.forEach((reference, index) => {
    const width = reference.size_um[0];
    const depth = reference.size_um[1];
    const height = Math.max(6, Math.min(26, Math.log2(width * depth + 1) * 1.8));
    const geometry = new THREE.BoxGeometry(width, height, depth);
    const material = new THREE.MeshPhysicalMaterial({
      color: reference.color,
      transparent: true,
      opacity: 0.86,
      metalness: 0.1,
      roughness: 0.45,
    });

    const mesh = new THREE.Mesh(geometry, material);
    const centerX = (reference.bounds.min[0] + reference.bounds.max[0]) / 2 - offsetX;
    const centerZ = (reference.bounds.min[1] + reference.bounds.max[1]) / 2 - offsetY;
    mesh.position.set(centerX, height / 2, centerZ);
    root.add(mesh);

    const edge = new THREE.LineSegments(
      new THREE.EdgesGeometry(geometry),
      new THREE.LineBasicMaterial({ color: "#d6e6f5", transparent: true, opacity: 0.3 })
    );
    edge.position.copy(mesh.position);
    root.add(edge);

    items.push({
      id: `${reference.cell}-${index}`,
      label: reference.title,
      subtitle: reference.cell,
      metric: `${reference.size_um[0].toFixed(1)} x ${reference.size_um[1].toFixed(1)} um`,
      color: reference.color,
      object: mesh,
      companion: edge,
      explodeIndex: index,
      baseY: height / 2,
    });
  });

  return { root, items };
}

function normalizeMaterials(material) {
  const materials = Array.isArray(material) ? material : [material];
  materials.forEach((entry) => {
    entry.side = THREE.DoubleSide;
    if (entry.opacity < 0.999) {
      entry.transparent = true;
      entry.depthWrite = false;
    }
  });
}

function buildGlbScene(data, gltf) {
  const root = gltf.scene;
  const items = [];
  const metaByKey = new Map(data.layers.map((layer) => [`${layer.layer}:${layer.datatype}`, layer]));
  const meshes = [];

  root.traverse((child) => {
    if (child.isMesh) {
      meshes.push(child);
    }
  });

  meshes.forEach((mesh, index) => {
    normalizeMaterials(mesh.material);
    mesh.castShadow = false;
    mesh.receiveShadow = false;
    mesh.renderOrder = index;

    const match = mesh.name.match(/(\d+)\/(\d+)/);
    const meta = match ? metaByKey.get(`${match[1]}:${match[2]}`) : data.layers[index];
    const material = Array.isArray(mesh.material) ? mesh.material[0] : mesh.material;

    items.push({
      id: meta ? meta.key : `mesh-${index}`,
      label: meta ? meta.name : mesh.name || `Layer ${index + 1}`,
      subtitle: meta ? `GDS ${meta.layer}/${meta.datatype}` : "GLB mesh",
      metric: meta ? `${meta.polygon_count.toLocaleString()} polys` : `${mesh.geometry.attributes.position.count.toLocaleString()} verts`,
      color: meta ? meta.color : `#${material.color.getHexString()}`,
      object: mesh,
      explodeIndex: index,
      baseY: mesh.position.y,
    });
  });

  return { root, items };
}

function renderItemList() {
  dom.layerList.innerHTML = "";
  state.activeItems.forEach((item) => {
    const row = document.createElement("label");
    row.className = "layer-row";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = item.object.visible;
    checkbox.addEventListener("change", () => {
      item.object.visible = checkbox.checked;
      if (item.companion) {
        item.companion.visible = checkbox.checked;
      }
      updateStats();
    });

    const label = document.createElement("div");
    label.className = "layer-label";
    label.innerHTML = `<strong>${item.label}</strong><span class="layer-label-text">${item.subtitle}</span>`;

    const swatch = document.createElement("div");
    swatch.className = "layer-label";
    swatch.innerHTML = `<span class="swatch" style="background:${item.color}"></span><span class="swatch-code">${item.metric}</span>`;

    row.append(checkbox, label, swatch);
    dom.layerList.append(row);
  });
}

function renderMeta(data, dataset) {
  const detailLine =
    data.kind === "detail"
      ? `<div class="meta-line"><span>Rendered Layers</span><strong>${data.layer_count}</strong></div>
         <div class="meta-line"><span>Rendered Polygons</span><strong>${data.polygon_count.toLocaleString()}</strong></div>`
      : `<div class="meta-line"><span>Referenced Blocks</span><strong>${data.references.length}</strong></div>
         <div class="meta-line"><span>View Type</span><strong>Placement Overview</strong></div>`;

  const sourceMode = state.activeRenderMode === "glb" ? "GLB scene" : state.activeRenderMode === "json-fallback" ? "JSON fallback" : "JSON prototype";
  dom.datasetMeta.innerHTML = `
    <strong>${data.title}</strong>
    <p>${data.summary}</p>
    <div class="meta-line"><span>Source Cell</span><strong>${data.source.cell}</strong></div>
    <div class="meta-line"><span>Footprint</span><strong>${data.size_um[0].toFixed(1)} x ${data.size_um[1].toFixed(1)} um</strong></div>
    <div class="meta-line"><span>Render Path</span><strong>${sourceMode}</strong></div>
    ${detailLine}
  `;
}

function updateStats() {
  if (!state.activeGroup) {
    dom.sceneStats.innerHTML = "";
    return;
  }

  const box = new THREE.Box3().setFromObject(state.activeGroup);
  const size = box.getSize(new THREE.Vector3());
  const visibleCount = state.activeItems.filter((item) => item.object.visible).length;
  const sourceMode = state.activeRenderMode === "glb" ? "GLB" : state.activeRenderMode === "json-fallback" ? "JSON fallback" : "JSON";

  const stats = [
    ["Visible Items", `${visibleCount}/${state.activeItems.length}`],
    ["Scene Width", `${size.x.toFixed(1)} um`],
    ["Scene Height", `${size.y.toFixed(1)} um`],
    ["Scene Depth", `${size.z.toFixed(1)} um`],
    ["Source", state.activeDataset ? state.activeDataset.source.cell : "-"],
    ["Render Path", sourceMode],
  ];

  dom.sceneStats.innerHTML = stats.map(([label, value]) => `<dt>${label}</dt><dd>${value}</dd>`).join("");
}

function applyExplode(amount) {
  state.explodeAmount = amount;
  state.activeItems.forEach((item) => {
    const isDetail = state.activeDataset?.kind === "detail";
    const extraLift = isDetail ? item.explodeIndex * amount * 0.22 : item.explodeIndex * amount * 0.48;
    item.object.position.y = item.baseY + extraLift;
    if (item.companion) {
      item.companion.position.y = item.baseY + extraLift;
    }
  });
  updateStats();
}

async function fetchMetadata(dataset) {
  setLoadProgress(`Loading ${dataset.label} metadata...`, 0.08);
  const response = await fetch(dataset.metaPath);
  if (!response.ok) {
    throw new Error(`Metadata request failed with ${response.status}`);
  }
  return response.json();
}

function loadGlb(dataset, token) {
  return new Promise((resolve, reject) => {
    gltfLoader.load(
      dataset.glbPath,
      (gltf) => resolve(gltf),
      (event) => {
        if (token !== state.loadToken) {
          return;
        }
        if (event.total > 0) {
          setLoadProgress(
            `Loading ${dataset.label} GLB... ${Math.round((event.loaded / event.total) * 100)}%`,
            0.12 + (event.loaded / event.total) * 0.78
          );
        } else {
          setLoadProgress(`Loading ${dataset.label} GLB...`, null, { indeterminate: true });
        }
      },
      reject
    );
  });
}

async function buildDatasetScene(dataset, data, token) {
  if (dataset.mode === "json") {
    setLoadProgress(`Building ${dataset.label} scene...`, 0.92);
    return { ...((data.kind === "detail" ? buildDetailScene(data) : buildOverviewScene(data))), renderMode: "json" };
  }

  try {
    const gltf = await loadGlb(dataset, token);
    if (token !== state.loadToken) {
      return null;
    }
    setLoadProgress(`Building ${dataset.label} GLB scene...`, 0.96);
    return { ...buildGlbScene(data, gltf), renderMode: "glb" };
  } catch (error) {
    console.error(error);
    setLoadProgress(`GLB failed for ${dataset.label}, falling back to JSON geometry...`, null, { indeterminate: true });
    return { ...buildDetailScene(data), renderMode: "json-fallback" };
  }
}

async function loadDataset(slug) {
  const token = ++state.loadToken;
  const dataset = DATASET_BY_SLUG.get(slug);
  if (!dataset) {
    return;
  }

  try {
    const data = await fetchMetadata(dataset);
    if (token !== state.loadToken) {
      return;
    }

    const built = await buildDatasetScene(dataset, data, token);
    if (!built || token !== state.loadToken) {
      return;
    }

    if (state.activeGroup) {
      contentRoot.remove(state.activeGroup);
      disposeGroup(state.activeGroup);
    }

    state.activeDataset = data;
    state.activeGroup = built.root;
    state.activeItems = built.items;
    state.activeRenderMode = built.renderMode;
    contentRoot.add(built.root);

    dom.datasetSelect.value = slug;
    document.querySelectorAll(".chip").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.slug === slug);
    });

    renderMeta(data, dataset);
    renderItemList();
    applyExplode(state.explodeAmount);
    fitCameraToObject(state.activeGroup);
    setLoadProgress(
      `Loaded ${data.source.cell} from ${built.renderMode === "glb" ? dataset.glbPath : data.source.gds}`,
      1
    );
  } catch (error) {
    console.error(error);
    if (token !== state.loadToken) {
      return;
    }
    setLoadProgress(`Failed to load ${dataset.label}: ${error.message}`, 1, { error: true });
  }
}

function buildDatasetControls() {
  DATASETS.forEach((dataset) => {
    const option = document.createElement("option");
    option.value = dataset.slug;
    option.textContent = dataset.label;
    dom.datasetSelect.append(option);
  });

  QUICK_DATASETS.forEach((slug) => {
    const dataset = DATASET_BY_SLUG.get(slug);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "chip";
    button.dataset.slug = slug;
    button.textContent = dataset.label.replace(" Detail", "").replace(" Overview", "");
    button.addEventListener("click", () => loadDataset(slug));
    dom.datasetButtons.append(button);
  });

  dom.datasetSelect.addEventListener("change", (event) => {
    loadDataset(event.target.value);
  });
}

dom.explodeRange.addEventListener("input", (event) => {
  applyExplode(Number(event.target.value));
});

dom.resetCamera.addEventListener("click", () => {
  fitCameraToObject(state.activeGroup || contentRoot);
});

dom.grabMode.addEventListener("click", () => {
  setInteractionMode("grab");
});

dom.orbitMode.addEventListener("click", () => {
  setInteractionMode("orbit");
});

dom.canvas.addEventListener("pointerdown", (event) => {
  if (interactionState.mode !== "grab" || event.button !== 0) {
    return;
  }
  dragState.active = true;
  dragState.pointerId = event.pointerId;
  dragState.lastX = event.clientX;
  dragState.lastY = event.clientY;
  dom.canvas.style.cursor = "grabbing";
  dom.canvas.setPointerCapture(event.pointerId);
});

dom.canvas.addEventListener("pointerdown", (event) => {
  if (interactionState.mode === "orbit" && event.button === 0) {
    retargetOrbitPivot();
  }
});

dom.canvas.addEventListener("pointermove", (event) => {
  if (interactionState.mode !== "grab" || !dragState.active || dragState.pointerId !== event.pointerId) {
    return;
  }
  const deltaX = event.clientX - dragState.lastX;
  const deltaY = event.clientY - dragState.lastY;
  dragState.lastX = event.clientX;
  dragState.lastY = event.clientY;
  moveViewFromDrag(deltaX, deltaY, event.shiftKey);
});

function stopGrab(event) {
  if (dragState.pointerId !== event.pointerId) {
    return;
  }
  dragState.active = false;
  dragState.pointerId = null;
  dom.canvas.style.cursor = interactionState.mode === "grab" ? "grab" : "default";
  if (dom.canvas.hasPointerCapture(event.pointerId)) {
    dom.canvas.releasePointerCapture(event.pointerId);
  }
}

dom.canvas.addEventListener("pointerup", stopGrab);
dom.canvas.addEventListener("pointercancel", stopGrab);

function handleResize() {
  const { clientWidth, clientHeight } = dom.canvas.parentElement;
  camera.aspect = clientWidth / clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(clientWidth, clientHeight, false);
}

window.addEventListener("resize", handleResize);

buildDatasetControls();
handleResize();
setInteractionMode("grab");
setLoadProgress("Preparing viewer...", null, { indeterminate: true });
loadDataset("cw-top");

function animate() {
  controls.update();
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}

animate();
