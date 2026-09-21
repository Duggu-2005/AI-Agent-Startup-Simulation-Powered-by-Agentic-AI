/* ============================================================
   VYAVASAI — decision engine accent
   A very restrained Three.js scene: five floating nodes
   (market, customers, capital, product, growth) linked by
   faint connections in a dark field. The camera drifts as the
   section is scrolled. Loaded only on the landing page.

   Degrades to nothing when WebGL, THREE or motion is absent.
   ============================================================ */
(function () {
  "use strict";

  var host = document.getElementById("engineCanvas");
  if (!host || !window.THREE) return;
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  var NODES = [
    { name: "market",    color: 0xd9a94e, pos: [-3.4, 1.1, -0.6] },
    { name: "customers", color: 0x9a8bff, pos: [3.0, 1.9, 0.4] },
    { name: "capital",   color: 0xff8347, pos: [2.1, -1.7, 1.1] },
    { name: "product",   color: 0xc9f24e, pos: [-2.3, -1.3, 1.4] },
    { name: "growth",    color: 0xf0c878, pos: [0.2, 0.1, -1.9] }
  ];
  var LINKS = [
    [0, 4], [1, 4], [2, 4], [3, 4],
    [0, 1], [1, 2], [2, 3], [3, 0]
  ];

  var scene, camera, renderer, group, linksMat, points, raf = null, running = false;
  var target = { x: 0, y: 0 };
  var pointer = { x: 0, y: 0 };
  var scrollProgress = 0;
  var clock;

  function sprite() {
    var c = document.createElement("canvas");
    c.width = c.height = 64;
    var ctx = c.getContext("2d");
    var g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    g.addColorStop(0, "rgba(255,255,255,1)");
    g.addColorStop(0.35, "rgba(255,255,255,0.7)");
    g.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(32, 32, 32, 0, Math.PI * 2);
    ctx.fill();
    var tex = new THREE.CanvasTexture(c);
    return tex;
  }

  function build() {
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(46, 1, 0.1, 100);
    camera.position.set(0, 0, 9);

    renderer = new THREE.WebGLRenderer({ alpha: true, antialias: false, powerPreference: "low-power" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setClearColor(0x000000, 0);
    host.appendChild(renderer.domElement);

    group = new THREE.Group();
    scene.add(group);

    var dot = sprite();

    // nodes
    var geo = new THREE.BufferGeometry();
    var pos = new Float32Array(NODES.length * 3);
    var col = new Float32Array(NODES.length * 3);
    var c = new THREE.Color();
    NODES.forEach(function (n, i) {
      pos[i * 3] = n.pos[0]; pos[i * 3 + 1] = n.pos[1]; pos[i * 3 + 2] = n.pos[2];
      c.setHex(n.color);
      col[i * 3] = c.r; col[i * 3 + 1] = c.g; col[i * 3 + 2] = c.b;
    });
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(col, 3));

    points = new THREE.Points(geo, new THREE.PointsMaterial({
      size: 0.34, map: dot, vertexColors: true, transparent: true,
      opacity: 0.95, depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true
    }));
    group.add(points);

    // faint connections
    var lgeo = new THREE.BufferGeometry();
    var lpos = new Float32Array(LINKS.length * 2 * 3);
    LINKS.forEach(function (pair, i) {
      var a = NODES[pair[0]].pos, b = NODES[pair[1]].pos;
      lpos.set(a, i * 6);
      lpos.set(b, i * 6 + 3);
    });
    lgeo.setAttribute("position", new THREE.BufferAttribute(lpos, 3));
    linksMat = new THREE.LineBasicMaterial({
      color: 0x8a7f66, transparent: true, opacity: 0.14, blending: THREE.AdditiveBlending, depthWrite: false
    });
    group.add(new THREE.LineSegments(lgeo, linksMat));

    // ambient dust
    var pgeo = new THREE.BufferGeometry();
    var pn = 340;
    var ppos = new Float32Array(pn * 3);
    for (var k = 0; k < pn; k++) {
      ppos[k * 3] = (Math.random() - 0.5) * 22;
      ppos[k * 3 + 1] = (Math.random() - 0.5) * 14;
      ppos[k * 3 + 2] = (Math.random() - 0.5) * 14;
    }
    pgeo.setAttribute("position", new THREE.BufferAttribute(ppos, 3));
    group.add(new THREE.Points(pgeo, new THREE.PointsMaterial({
      size: 0.05, map: dot, color: 0x9c978c, transparent: true,
      opacity: 0.4, depthWrite: false, blending: THREE.AdditiveBlending
    })));

    clock = new THREE.Clock();
    onResize();
  }

  function onResize() {
    if (!renderer || !host) return;
    var w = host.clientWidth, h = host.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  function frame() {
    raf = requestAnimationFrame(frame);
    var t = clock.getElapsedTime();

    // eased pointer / target drift
    target.x += (pointer.x - target.x) * 0.04;
    target.y += (pointer.y - target.y) * 0.04;

    group.rotation.y = t * 0.045 + target.x * 0.28;
    group.rotation.x = -0.06 + target.y * 0.18 + Math.sin(t * 0.15) * 0.03;

    var z = 9 - scrollProgress * 4.2;
    camera.position.x = target.x * 0.9 + Math.sin(t * 0.11) * 0.25;
    camera.position.y = -target.y * 0.7 + Math.cos(t * 0.09) * 0.18;
    camera.position.z += (z - camera.position.z) * 0.05;
    camera.lookAt(0, 0, 0);

    if (linksMat) linksMat.opacity = 0.08 + scrollProgress * 0.22;
    if (points) points.material.opacity = 0.75 + Math.sin(t * 0.6) * 0.12;

    renderer.render(scene, camera);
  }

  function start() {
    if (running || !renderer) return;
    running = true;
    clock.start();
    frame();
  }
  function stop() {
    running = false;
    if (raf) cancelAnimationFrame(raf);
    raf = null;
  }

  function setup() {
    try {
      build();
    } catch (err) {
      // no WebGL / blocked — the CSS fallback already covers this
      if (renderer && renderer.domElement && renderer.domElement.parentNode) {
        renderer.domElement.parentNode.removeChild(renderer.domElement);
      }
      return;
    }
    window.addEventListener("resize", onResize);
    window.addEventListener("pointermove", function (e) {
      pointer.x = (e.clientX / window.innerWidth) * 2 - 1;
      pointer.y = (e.clientY / window.innerHeight) * 2 - 1;
    }, { passive: true });

    window.VyavasEngine.setScroll = function (p) { scrollProgress = Math.max(0, Math.min(1, p)); };

    // only animate while the section is on screen
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (entries) {
        entries.forEach(function (en) { en.isIntersecting ? start() : stop(); });
      }, { threshold: 0.05 }).observe(host);
    } else {
      start();
    }
  }

  window.VyavasEngine = window.VyavasEngine || {};

  // lazy: wait until the section is near, then build
  function whenNear() {
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (entries) {
        if (entries.some(function (e) { return e.isIntersecting; })) {
          io.disconnect();
          setup();
        }
      }, { rootMargin: "300px" });
      io.observe(host);
    } else {
      setup();
    }
  }

  if (document.readyState === "complete") whenNear();
  else window.addEventListener("load", whenNear);
})();
