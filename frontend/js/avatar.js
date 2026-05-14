import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRMUtils } from "@pixiv/three-vrm";

const VRM_PATH = "assets/avatar/AvatarSample_M.vrm";

const FRAMES_PNG = {
  alegre:    ["Happy1.png", "Happy2.png", "Happy3.png"],
  ansioso:   ["Tired1 copy 2.png", "Tired1 copy 3.png", "Tired1 copy 4.png"],
  confundido:["Tired1.png", "Tired1 copy.png", "Tired1 copy 2.png"],
  dormido:   ["Sleepy1.png", "Sleepy2.png", "Sleepy3.png"],
  enojado:   ["Angry1.png", "Angry2.png", "Angry2 copy.png"],
  hablando:  ["Speaking1.png", "Speaking2.png", "Speaking1.png"],
  neutro:    ["Normal1.png", "Normal1 copy.png", "Normal1 copy 2.png"],
  pensativo: ["Thinking1.png", "Thinking2.png", "Thinking3.png"],
  triste:    ["Sad1.png", "Sad2.png", "Sad2 copy.png"],
};

const EMOCION_A_VRM = {
  alegre:"happy", ansioso:"sad", confundido:"sad", dormido:"relaxed",
  enojado:"angry", hablando:"neutral", neutro:"neutral",
  pensativo:"relaxed", triste:"sad",
};

export const EMOJI = {
  alegre:"😊", ansioso:"😰", confundido:"😕", dormido:"😴",
  enojado:"😠", hablando:"🗣️", neutro:"😐", pensativo:"🤔", triste:"😢"
};

// ━━━━━ CATÁLOGO DE GESTOS ━━━━━
// Cada gesto es lista de keyframes: { t: tiempo_seg, poses: { hueso: [x,y,z] } }
// El sistema interpola con easing entre keyframes.
const GESTOS = {
  saludar: {
    duracion: 1.8,
    keys: [
      { t: 0.0, poses: { rightUpperArm: [0, 0, -1.2],  rightLowerArm: [0, 0.2, 0] } },
      { t: 0.3, poses: { rightUpperArm: [0, 0, -2.6],  rightLowerArm: [0, -1.0, 0] } },
      { t: 0.6, poses: { rightUpperArm: [0, 0, -2.5],  rightLowerArm: [0, -1.4, 0] } },
      { t: 0.9, poses: { rightUpperArm: [0, 0, -2.6],  rightLowerArm: [0, -1.0, 0] } },
      { t: 1.2, poses: { rightUpperArm: [0, 0, -2.5],  rightLowerArm: [0, -1.4, 0] } },
      { t: 1.8, poses: { rightUpperArm: [0, 0, -1.2],  rightLowerArm: [0, 0.2, 0] } },
    ],
  },

  asentir: {
    duracion: 1.2,
    keys: [
      { t: 0.0, poses: { head: [0, 0, 0] } },
      { t: 0.25, poses: { head: [0.3, 0, 0] } },
      { t: 0.5, poses: { head: [-0.05, 0, 0] } },
      { t: 0.75, poses: { head: [0.25, 0, 0] } },
      { t: 1.0, poses: { head: [-0.02, 0, 0] } },
      { t: 1.2, poses: { head: [0, 0, 0] } },
    ],
  },

  negar: {
    duracion: 1.2,
    keys: [
      { t: 0.0, poses: { head: [0, 0, 0] } },
      { t: 0.2, poses: { head: [0, 0.4, 0] } },
      { t: 0.4, poses: { head: [0, -0.4, 0] } },
      { t: 0.6, poses: { head: [0, 0.4, 0] } },
      { t: 0.8, poses: { head: [0, -0.3, 0] } },
      { t: 1.2, poses: { head: [0, 0, 0] } },
    ],
  },

  pensar: {
    duracion: 2.5,
    keys: [
      { t: 0.0, poses: {
        rightUpperArm: [0, 0, -1.2], rightLowerArm: [0, 0.2, 0], head: [0, 0, 0]
      } },
      { t: 0.6, poses: {
        rightUpperArm: [0.2, 0, -1.8], rightLowerArm: [0, -1.8, 0], head: [0.1, 0.2, 0.1]
      } },
      { t: 2.0, poses: {
        rightUpperArm: [0.2, 0, -1.8], rightLowerArm: [0, -1.8, 0], head: [0.1, 0.2, 0.1]
      } },
      { t: 2.5, poses: {
        rightUpperArm: [0, 0, -1.2], rightLowerArm: [0, 0.2, 0], head: [0, 0, 0]
      } },
    ],
  },

  encogerse: {
    duracion: 1.4,
    keys: [
      { t: 0.0, poses: {
        leftUpperArm: [0, 0, 1.2], rightUpperArm: [0, 0, -1.2],
        leftLowerArm: [0, -0.2, 0], rightLowerArm: [0, 0.2, 0],
      } },
      { t: 0.4, poses: {
        leftUpperArm: [-0.3, 0, 0.7], rightUpperArm: [-0.3, 0, -0.7],
        leftLowerArm: [0, -1.4, 0], rightLowerArm: [0, 1.4, 0],
      } },
      { t: 0.9, poses: {
        leftUpperArm: [-0.3, 0, 0.7], rightUpperArm: [-0.3, 0, -0.7],
        leftLowerArm: [0, -1.4, 0], rightLowerArm: [0, 1.4, 0],
      } },
      { t: 1.4, poses: {
        leftUpperArm: [0, 0, 1.2], rightUpperArm: [0, 0, -1.2],
        leftLowerArm: [0, -0.2, 0], rightLowerArm: [0, 0.2, 0],
      } },
    ],
  },

  senalar: {
    duracion: 1.5,
    keys: [
      { t: 0.0, poses: { rightUpperArm: [0, 0, -1.2], rightLowerArm: [0, 0.2, 0] } },
      { t: 0.4, poses: { rightUpperArm: [-0.5, 0, -0.4], rightLowerArm: [0, 0, 0] } },
      { t: 1.1, poses: { rightUpperArm: [-0.5, 0, -0.4], rightLowerArm: [0, 0, 0] } },
      { t: 1.5, poses: { rightUpperArm: [0, 0, -1.2], rightLowerArm: [0, 0.2, 0] } },
    ],
  },

  celebrar: {
    duracion: 1.6,
    keys: [
      { t: 0.0, poses: {
        leftUpperArm: [0, 0, 1.2], rightUpperArm: [0, 0, -1.2],
        leftLowerArm: [0, -0.2, 0], rightLowerArm: [0, 0.2, 0],
      } },
      { t: 0.3, poses: {
        leftUpperArm: [-1.5, 0, 2.7], rightUpperArm: [-1.5, 0, -2.7],
        leftLowerArm: [0, 0, 0], rightLowerArm: [0, 0, 0],
      } },
      { t: 0.7, poses: {
        leftUpperArm: [-1.7, 0, 2.7], rightUpperArm: [-1.7, 0, -2.7],
        leftLowerArm: [0, 0, 0], rightLowerArm: [0, 0, 0],
      } },
      { t: 1.0, poses: {
        leftUpperArm: [-1.5, 0, 2.7], rightUpperArm: [-1.5, 0, -2.7],
      } },
      { t: 1.6, poses: {
        leftUpperArm: [0, 0, 1.2], rightUpperArm: [0, 0, -1.2],
        leftLowerArm: [0, -0.2, 0], rightLowerArm: [0, 0.2, 0],
      } },
    ],
  },

  facepalm: {
    duracion: 2.2,
    keys: [
      { t: 0.0, poses: {
        rightUpperArm: [0, 0, -1.2], rightLowerArm: [0, 0.2, 0], head: [0, 0, 0]
      } },
      { t: 0.5, poses: {
        rightUpperArm: [-1.5, 0, -0.5], rightLowerArm: [0, -2.0, 0], head: [0.3, 0, 0]
      } },
      { t: 1.8, poses: {
        rightUpperArm: [-1.5, 0, -0.5], rightLowerArm: [0, -2.0, 0], head: [0.3, 0, 0]
      } },
      { t: 2.2, poses: {
        rightUpperArm: [0, 0, -1.2], rightLowerArm: [0, 0.2, 0], head: [0, 0, 0]
      } },
    ],
  },

  brazos_abiertos: {
    duracion: 1.5,
    keys: [
      { t: 0.0, poses: {
        leftUpperArm: [0, 0, 1.2], rightUpperArm: [0, 0, -1.2],
      } },
      { t: 0.4, poses: {
        leftUpperArm: [0, 0, 2.0], rightUpperArm: [0, 0, -2.0],
        leftLowerArm: [0, 0, 0], rightLowerArm: [0, 0, 0],
      } },
      { t: 1.0, poses: {
        leftUpperArm: [0, 0, 2.0], rightUpperArm: [0, 0, -2.0],
      } },
      { t: 1.5, poses: {
        leftUpperArm: [0, 0, 1.2], rightUpperArm: [0, 0, -1.2],
        leftLowerArm: [0, -0.2, 0], rightLowerArm: [0, 0.2, 0],
      } },
    ],
  },

  brazos_cruzados: {
    duracion: 1.0,
    keys: [
      { t: 0.0, poses: {
        leftUpperArm: [0, 0, 1.2], rightUpperArm: [0, 0, -1.2],
        leftLowerArm: [0, -0.2, 0], rightLowerArm: [0, 0.2, 0],
      } },
      { t: 0.5, poses: {
        leftUpperArm: [0.5, 0, 0.8], rightUpperArm: [0.5, 0, -0.8],
        leftLowerArm: [0, -1.5, 0], rightLowerArm: [0, 1.5, 0],
      } },
      { t: 1.0, poses: {
        leftUpperArm: [0.5, 0, 0.8], rightUpperArm: [0.5, 0, -0.8],
        leftLowerArm: [0, -1.5, 0], rightLowerArm: [0, 1.5, 0],
      } },
    ],
  },

  bostezar: {
    duracion: 2.0,
    keys: [
      { t: 0.0, poses: {
        leftUpperArm: [0, 0, 1.2], rightUpperArm: [0, 0, -1.2], head: [0, 0, 0]
      } },
      { t: 0.5, poses: {
        leftUpperArm: [-1.8, 0, 2.0], rightUpperArm: [-1.8, 0, -2.0], head: [-0.3, 0, 0]
      } },
      { t: 1.2, poses: {
        leftUpperArm: [-1.8, 0, 2.0], rightUpperArm: [-1.8, 0, -2.0], head: [-0.3, 0, 0]
      } },
      { t: 2.0, poses: {
        leftUpperArm: [0, 0, 1.2], rightUpperArm: [0, 0, -1.2], head: [0, 0, 0]
      } },
    ],
  },

  ladear_cabeza: {
    duracion: 1.5,
    keys: [
      { t: 0.0, poses: { head: [0, 0, 0] } },
      { t: 0.5, poses: { head: [0, 0, 0.3] } },
      { t: 1.0, poses: { head: [0, 0, 0.3] } },
      { t: 1.5, poses: { head: [0, 0, 0] } },
    ],
  },

  pulgar_arriba: {
    duracion: 1.4,
    keys: [
      { t: 0.0, poses: { rightUpperArm: [0, 0, -1.2], rightLowerArm: [0, 0.2, 0] } },
      { t: 0.3, poses: { rightUpperArm: [-0.6, 0, -0.6], rightLowerArm: [0, -1.5, 0] } },
      { t: 1.0, poses: { rightUpperArm: [-0.6, 0, -0.6], rightLowerArm: [0, -1.5, 0] } },
      { t: 1.4, poses: { rightUpperArm: [0, 0, -1.2], rightLowerArm: [0, 0.2, 0] } },
    ],
  },

  estirarse: {
    duracion: 2.2,
    keys: [
      { t: 0.0, poses: {
        leftUpperArm: [0, 0, 1.2], rightUpperArm: [0, 0, -1.2], spine: [0, 0, 0]
      } },
      { t: 0.7, poses: {
        leftUpperArm: [-2.5, 0, 2.5], rightUpperArm: [-2.5, 0, -2.5], spine: [-0.15, 0, 0]
      } },
      { t: 1.5, poses: {
        leftUpperArm: [-2.5, 0, 2.5], rightUpperArm: [-2.5, 0, -2.5], spine: [-0.15, 0, 0]
      } },
      { t: 2.2, poses: {
        leftUpperArm: [0, 0, 1.2], rightUpperArm: [0, 0, -1.2], spine: [0, 0, 0]
      } },
    ],
  },
};

// ━━━━━ Estado global ━━━━━
let _modo = "png";
let _emocionActual = "alegre";
let _ttsActivo = false;

let _imgEl = null;
let _canvasEl = null;
let _frameIdx = 0;
let _timer = null;

let _scene, _camera, _renderer, _vrm, _clock;
let _expresionActualVRM = "neutral";
let _expresionPesoActual = 0;
let _expresionPesoTarget = 1;
let _blinkTimer = 0;
let _blinkActive = false;
let _amplitudActual = 0;
let _amplitudTarget = 0;

let _gestoTiempo = 0;
let _gestoActual = null;
let _gestoTiempoLocal = 0;
let _gestoIntensidad = 1.0;

// Easing cubic in-out (lo que quita el "plasticoso")
function ease(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

// Suma rotaciones en un hueso target (modo aditivo sobre idle)
function aplicarPose(hueso, [x, y, z], peso) {
  if (!hueso) return;
  hueso.rotation.x += x * peso;
  hueso.rotation.y += y * peso;
  hueso.rotation.z += z * peso;
}

function init() {
  _imgEl = document.getElementById("avatar");
  iniciarVRM().catch(err => {
    console.warn("VRM no disponible, usando PNG fallback:", err);
    _modo = "png";
    if (_imgEl) _imgEl.style.display = "";
    if (_canvasEl) _canvasEl.style.display = "none";
    mostrarFrame(_emocionActual, 0);
  });
}

async function iniciarVRM() {
  const wrap = document.getElementById("av-wrap");
  if (!wrap) throw new Error("no av-wrap");

  _canvasEl = document.createElement("canvas");
  _canvasEl.id = "avatar3d";
  _canvasEl.style.width  = "175px";
  _canvasEl.style.height = "175px";
  _canvasEl.style.display = "none";
  wrap.appendChild(_canvasEl);

  _renderer = new THREE.WebGLRenderer({
    canvas: _canvasEl, alpha: true, antialias: true,
    premultipliedAlpha: false, powerPreference: "high-performance",
  });
  _renderer.setPixelRatio(Math.min(window.devicePixelRatio * 2, 4));
  _renderer.setSize(460, 460, false);
  _renderer.setClearColor(0x000000, 0);
  _renderer.outputColorSpace = THREE.SRGBColorSpace;
  _renderer.toneMapping = THREE.ACESFilmicToneMapping;
  _renderer.toneMappingExposure = 1.1;

  _scene = new THREE.Scene();
  _camera = new THREE.PerspectiveCamera(30, 1, 0.1, 20);

  const luzAmbiente = new THREE.AmbientLight(0xffffff, 0.7);
  const luzFrontal = new THREE.DirectionalLight(0xffffff, 1.0);
  luzFrontal.position.set(0, 1, 2);
  const luzRelleno = new THREE.DirectionalLight(0xaaccff, 0.4);
  luzRelleno.position.set(-1, 0.5, 1);
  const luzContraluz = new THREE.DirectionalLight(0xffeecc, 0.3);
  luzContraluz.position.set(0, 1, -1);
  _scene.add(luzAmbiente, luzFrontal, luzRelleno, luzContraluz);

  _clock = new THREE.Clock();

  const loader = new GLTFLoader();
  loader.register(parser => new VRMLoaderPlugin(parser));

  const gltf = await loader.loadAsync(VRM_PATH);
  _vrm = gltf.userData.vrm;
  try { VRMUtils.removeUnnecessaryVertices(gltf.scene); } catch (_) {}
  try { VRMUtils.combineSkeletons?.(gltf.scene); } catch (_) {}

  _vrm.scene.rotation.y = Math.PI;
  _scene.add(_vrm.scene);

  if (_vrm.humanoid) {
    const head  = _vrm.humanoid.getNormalizedBoneNode("head");
    const chest = _vrm.humanoid.getNormalizedBoneNode("chest")
               || _vrm.humanoid.getNormalizedBoneNode("upperChest")
               || _vrm.humanoid.getNormalizedBoneNode("spine");
    if (head) {
      const headPos  = new THREE.Vector3();
      const chestPos = new THREE.Vector3();
      head.getWorldPosition(headPos);
      (chest || head).getWorldPosition(chestPos);
      const targetY = (headPos.y + chestPos.y) / 2;
      _camera.position.set(headPos.x, targetY, headPos.z + 1.6);
      _camera.lookAt(headPos.x, targetY, headPos.z);
    }
  }

  _modo = "vrm";
  if (_imgEl) _imgEl.style.display = "none";
  _canvasEl.style.display = "";

  loop();
  console.log("Avatar VRM cargado");
}

function loop() {
  if (_modo !== "vrm" || !_vrm) return;
  requestAnimationFrame(loop);
  const dt = _clock.getDelta();
  actualizarExpresiones(dt);
  aplicarMovimientos(dt);
  _vrm.update(dt);
  _renderer.render(_scene, _camera);
}

function actualizarExpresiones(dt) {
  const em = _vrm.expressionManager;
  if (!em) return;

  for (const nombre of ["happy", "angry", "sad", "relaxed", "neutral"]) {
    em.setValue(nombre, 0);
  }
  _expresionPesoActual += (_expresionPesoTarget - _expresionPesoActual) * Math.min(dt * 8, 1);
  const peso = Math.min(_expresionPesoActual, 1.5);
  em.setValue(_expresionActualVRM, peso);

  _amplitudActual += (_amplitudTarget - _amplitudActual) * Math.min(dt * 12, 1);
  em.setValue("aa", _amplitudActual);

  _blinkTimer -= dt;
  if (_blinkTimer <= 0 && !_blinkActive) {
    _blinkActive = true;
    _blinkTimer = 0.15;
    em.setValue("blink", 1);
  } else if (_blinkActive && _blinkTimer <= 0) {
    _blinkActive = false;
    _blinkTimer = 2.5 + Math.random() * 3.5;
    em.setValue("blink", 0);
  } else if (_blinkActive) {
    em.setValue("blink", 1);
  }
}

// ━━━━━ Movimiento corporal: idle + gesto activo ━━━━━
function aplicarMovimientos(dt) {
  if (!_vrm.humanoid) return;
  _gestoTiempo += dt;

  const get = (n) => _vrm.humanoid.getNormalizedBoneNode(n);
  const head     = get("head");
  const chest    = get("chest") || get("upperChest");
  const spine    = get("spine");
  const brazoIzq = get("leftUpperArm");
  const brazoDer = get("rightUpperArm");
  const antIzq   = get("leftLowerArm");
  const antDer   = get("rightLowerArm");

  // ── 1) Pose base + idle (siempre activo) ──
  const respiracion = Math.sin(_gestoTiempo * 1.2) * 0.012;
  const sway        = Math.sin(_gestoTiempo * 0.4) * 0.015;
  const microIzq    = Math.sin(_gestoTiempo * 0.5) * 0.015;
  const microDer    = Math.sin(_gestoTiempo * 0.5 + 0.7) * 0.015;

  if (head)     head.rotation.set(
    Math.sin(_gestoTiempo * 0.4) * 0.015,
    Math.sin(_gestoTiempo * 0.6) * 0.01,
    0,
  );
  if (spine)    spine.rotation.set(respiracion * 0.5, 0, sway);
  if (chest)    chest.rotation.set(respiracion, 0, 0);
  if (brazoIzq) brazoIzq.rotation.set(0, 0, 1.2 + microIzq);
  if (brazoDer) brazoDer.rotation.set(0, 0, -1.2 + microDer);
  if (antIzq)   antIzq.rotation.set(0, -0.2, 0.15);
  if (antDer)   antDer.rotation.set(0, 0.2, -0.15);

  // ── 2) Capa de habla (encima del idle, si hay TTS) ──
  if (_ttsActivo) {
    const f = Math.min(_amplitudActual * 2, 1);
    if (brazoIzq) brazoIzq.rotation.z += Math.sin(_gestoTiempo * 3.5) * 0.08 * f;
    if (brazoDer) brazoDer.rotation.z += Math.sin(_gestoTiempo * 3.5 + 1.5) * 0.08 * f;
    if (head)     head.rotation.y    += Math.sin(_gestoTiempo * 2.5) * 0.05 * f;
  }

  // ── 3) Capa de gesto activo (encima de todo, con easing) ──
  if (_gestoActual) {
    _gestoTiempoLocal += dt;
    const gesto = GESTOS[_gestoActual];
    if (!gesto) { _gestoActual = null; return; }

    if (_gestoTiempoLocal >= gesto.duracion) {
      _gestoActual = null;
      _gestoTiempoLocal = 0;
      return;
    }

    // Encontrar keyframes alrededor del tiempo actual
    let kA = gesto.keys[0], kB = gesto.keys[0];
    for (let i = 0; i < gesto.keys.length - 1; i++) {
      if (gesto.keys[i].t <= _gestoTiempoLocal && gesto.keys[i+1].t >= _gestoTiempoLocal) {
        kA = gesto.keys[i];
        kB = gesto.keys[i+1];
        break;
      }
    }

    const span = Math.max(kB.t - kA.t, 0.001);
    const tNorm = (_gestoTiempoLocal - kA.t) / span;
    const t = ease(Math.max(0, Math.min(1, tNorm)));

    // Fade in/out del gesto (entra rápido, mantiene, sale suave)
    let intensidad = _gestoIntensidad;
    if (_gestoTiempoLocal < 0.15) {
      intensidad *= _gestoTiempoLocal / 0.15;
    } else if (_gestoTiempoLocal > gesto.duracion - 0.25) {
      intensidad *= (gesto.duracion - _gestoTiempoLocal) / 0.25;
    }

    const huesos = new Set([
      ...Object.keys(kA.poses || {}),
      ...Object.keys(kB.poses || {}),
    ]);
    for (const nombreHueso of huesos) {
      const a = (kA.poses && kA.poses[nombreHueso]) || [0,0,0];
      const b = (kB.poses && kB.poses[nombreHueso]) || a;
      const x = a[0] + (b[0] - a[0]) * t;
      const y = a[1] + (b[1] - a[1]) * t;
      const z = a[2] + (b[2] - a[2]) * t;
      aplicarPose(get(nombreHueso), [x, y, z], intensidad);
    }
  }
}

// ━━━━━ API pública para gestos ━━━━━
function ejecutarGesto(nombre, intensidad = 1.0) {
  if (!GESTOS[nombre]) {
    console.warn("Gesto desconocido:", nombre);
    return false;
  }
  _gestoActual = nombre;
  _gestoTiempoLocal = 0;
  _gestoIntensidad = Math.max(0, Math.min(1.5, intensidad));
  return true;
}

function gestosDisponibles() {
  return Object.keys(GESTOS);
}

// ━━━━━ Resto (PNG fallback, emoción, habla) ━━━━━
function mostrarFrame(emo, idx) {
  if (_modo !== "png" || !_imgEl) return;
  const lista = FRAMES_PNG[emo] || FRAMES_PNG.neutro;
  _imgEl.src = `assets/avatar/${emo}/${encodeURIComponent(lista[idx % lista.length])}`;
}

function cambiarEmocion(nuevaEmo) {
  _emocionActual = nuevaEmo;
  if (_modo === "vrm") {
    const nuevaVRM = EMOCION_A_VRM[nuevaEmo] || "neutral";
    if (nuevaVRM !== _expresionActualVRM) {
      _expresionActualVRM = nuevaVRM;
      _expresionPesoActual = 0;
      _expresionPesoTarget = nuevaVRM === "neutral" ? 0.4 : 1.2;
    }
  } else if (!_ttsActivo) {
    if (FRAMES_PNG[nuevaEmo]) mostrarFrame(nuevaEmo, 0);
  }
}

function iniciarHabla() {
  if (_ttsActivo) return;
  _ttsActivo = true;
  if (_modo === "vrm") _amplitudTarget = 0.5;
  else {
    document.getElementById("avatar")?.classList.add("talk");
    _frameIdx = 0;
    _timer = setInterval(() => {
      _frameIdx = (_frameIdx + 1) % 3;
      mostrarFrame(_emocionActual, _frameIdx);
    }, 110);
  }
}

function actualizarAmplitudHabla(rms) {
  if (_modo === "vrm" && _ttsActivo) {
    _amplitudTarget = Math.min(1, Math.max(0, rms * 8));
  }
}

function detenerHabla() {
  _ttsActivo = false;
  if (_modo === "vrm") _amplitudTarget = 0;
  else {
    document.getElementById("avatar")?.classList.remove("talk");
    if (_timer) { clearInterval(_timer); _timer = null; }
    mostrarFrame(_emocionActual, 0);
  }
}

export const Avatar = {
  init, mostrarFrame, cambiarEmocion,
  iniciarHabla, detenerHabla, actualizarAmplitudHabla,
  ejecutarGesto, gestosDisponibles,
  emojiDe: (emo) => EMOJI[emo] || "😐",
  FRAMES: FRAMES_PNG, EMOJI,
};