/* ============================================================
   MOTION KERNEL — Lenis smooth scroll + GSAP ScrollTrigger
   Drives the ambient orb field, reveals, split text, marquee,
   magnetic buttons, tilt cards, counters and scroll progress.
   ============================================================ */
(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* --------------------------------------------------------
     Shared utilities (available even with reduced motion)
     -------------------------------------------------------- */
  var SA = {
    reduced: reduced,
    q: function (s, ctx) { return (ctx || document).querySelector(s); },
    qa: function (s, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(s)); }
  };
  window.SA = SA;

  /* --------------------------------------------------------
     Smooth scroll
     -------------------------------------------------------- */
  var lenis = null;
  if (window.Lenis && !reduced) {
    lenis = new Lenis({
      duration: 1.1,
      smoothWheel: true,
      wheelMultiplier: 1,
      touchMultiplier: 1.6
    });
    var raf = function (time) {
      if (lenis) lenis.raf(time);
      requestAnimationFrame(raf);
    };
    requestAnimationFrame(raf);
  }
  SA.lenis = lenis;
  SA.scrollTo = function (target, opts) {
    if (lenis) lenis.scrollTo(target, opts || { duration: 1.2 });
    else if (typeof target === "number") window.scrollTo({ top: target, behavior: "smooth" });
    else if (target && target.scrollIntoView) target.scrollIntoView({ behavior: "smooth" });
  };

  /* --------------------------------------------------------
     Scroll progress + nav state (cheap, always on)
     -------------------------------------------------------- */
  var prog = SA.q(".scroll-prog");
  var nav = SA.q(".nav");
  function onScroll() {
    var h = document.documentElement;
    var max = h.scrollHeight - h.clientHeight;
    var p = max > 0 ? (h.scrollTop || document.body.scrollTop) / max : 0;
    if (prog) prog.style.width = (p * 100).toFixed(2) + "%";
    if (nav) nav.classList.toggle("solid", (h.scrollTop || document.body.scrollTop) > 24);
  }
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  /* --------------------------------------------------------
     Loading screen — short, never blocks content
     -------------------------------------------------------- */
  var loader = SA.q(".loader");
  if (loader) {
    var barFill = SA.q(".loader__bar i", loader);
    var pct = 0;
    var tick = setInterval(function () {
      pct = Math.min(94, pct + 10 + Math.random() * 16);
      if (barFill) barFill.style.width = pct + "%";
    }, 130);

    var dismissed = false;
    function dismiss() {
      if (dismissed) return;
      dismissed = true;
      clearInterval(tick);
      if (barFill) barFill.style.width = "100%";
      setTimeout(function () {
        loader.classList.add("is-done");
        document.documentElement.classList.remove("is-loading");
        document.dispatchEvent(new CustomEvent("sa:ready"));
        setTimeout(function () { if (loader.parentNode) loader.parentNode.removeChild(loader); }, 800);
      }, 200);
    }

    document.documentElement.classList.add("is-loading");
    var t0 = Date.now();
    var minShow = reduced ? 0 : 650;
    function arm() {
      var wait = Math.max(0, minShow - (Date.now() - t0));
      setTimeout(dismiss, wait);
    }
    if (document.readyState === "complete") arm();
    else window.addEventListener("load", arm);
    setTimeout(dismiss, 2800); // hard safety net
  } else {
    document.addEventListener("DOMContentLoaded", function () {
      document.dispatchEvent(new CustomEvent("sa:ready"));
    });
    if (document.readyState !== "loading") document.dispatchEvent(new CustomEvent("sa:ready"));
  }

  /* --------------------------------------------------------
     Video backgrounds — show the clip only if it truly plays
     -------------------------------------------------------- */
  SA.qa("[data-video-bg]").forEach(function (box) {
    var v = box.querySelector("video");
    if (!v) return;
    function ok() { box.classList.add("is-playing"); }
    function bad() { box.classList.remove("is-playing"); }
    v.addEventListener("playing", ok);
    v.addEventListener("error", bad);
    var source = box.querySelector("source");
    if (source) source.addEventListener("error", bad);
    if (v.play) { var pr = v.play(); if (pr && pr.catch) pr.catch(bad); }
  });

  /* --------------------------------------------------------
     In-page anchor smooth scroll (Lenis-aware)
     -------------------------------------------------------- */
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest('a[href^="#"]');
    if (!a) return;
    var id = a.getAttribute("href");
    if (!id || id.length < 2) return;
    var el = SA.q(id);
    if (!el) return;
    e.preventDefault();
    SA.scrollTo(el, { offset: -70, duration: 1.3 });
  });

  /* --------------------------------------------------------
     GSAP layer
     -------------------------------------------------------- */
  function gsapReady(fn) {
    if (window.gsap) fn();
    else window.addEventListener("load", fn);
  }

  /* If GSAP never arrives (CDN blocked), never leave content hidden. */
  window.addEventListener("load", function () {
    if (window.gsap) return;
    SA.qa(".line > span, .line-mask > span").forEach(function (s) { s.style.transform = "none"; });
    SA.qa(".rv").forEach(function (el) { el.classList.add("in"); });
  });

  /* Safety: make sure anything already on screen is never left invisible. */
  window.addEventListener("load", function () {
    setTimeout(function () {
      SA.qa(".rv:not(.in)").forEach(function (el) {
        var r = el.getBoundingClientRect();
        if (r.top < window.innerHeight * 0.92 && r.bottom > 0) el.classList.add("in");
      });
    }, 450);
  });

  gsapReady(function () {
    if (window.ScrollTrigger) gsap.registerPlugin(ScrollTrigger);

    if (lenis && window.ScrollTrigger) {
      lenis.on("scroll", ScrollTrigger.update);
      gsap.ticker.add(function (time) { if (lenis) lenis.raf(time * 1000); });
      gsap.ticker.lagSmoothing(0);
    }

    /* ----- orb field: perpetual drift + scroll parallax ----- */
    SA.qa(".orb").forEach(function (orb, i) {
      if (reduced) return;
      gsap.to(orb, {
        x: (i % 2 ? -1 : 1) * (60 + i * 22),
        y: (i % 2 ? 1 : -1) * (40 + i * 18),
        scale: 1 + (i % 3) * 0.06,
        duration: 14 + i * 3,
        ease: "sine.inOut",
        repeat: -1,
        yoyo: true
      });
      if (window.ScrollTrigger) {
        gsap.to(orb, {
          yPercent: (i % 2 ? 22 : -26),
          ease: "none",
          scrollTrigger: { trigger: document.body, start: "top top", end: "bottom bottom", scrub: 1 }
        });
      }
    });

    /* ----- split-text reveals ----- */
    SA.qa(".line > span, .line-mask > span").forEach(function (span, i) {
      if (span.closest(".hero-cine")) return; // hero owns its own timeline
      if (reduced) { gsap.set(span, { y: 0 }); return; }
      gsap.to(span, {
        y: 0,
        duration: 1,
        ease: "power4.out",
        delay: 0.2 + i * 0.06,
        scrollTrigger: window.ScrollTrigger
          ? { trigger: span.closest(".line, .line-mask"), start: "top 92%" }
          : undefined
      });
    });

    /* ----- generic reveal ----- */
    if (window.ScrollTrigger) {
      ScrollTrigger.batch(".rv", {
        start: "top 90%",
        onEnter: function (batch) { batch.forEach(function (el) { el.classList.add("in"); }); }
      });

      /* pinned / scrubbed sections get their own page scripts */
      SA.qa("[data-parallax]").forEach(function (el) {
        var amount = parseFloat(el.getAttribute("data-parallax")) || 80;
        gsap.to(el, {
          y: amount,
          ease: "none",
          scrollTrigger: { trigger: el, start: "top bottom", end: "bottom top", scrub: true }
        });
      });

      /* counters (support prefix / suffix, e.g. +34%, 8 months) */
      SA.qa("[data-count]").forEach(function (el) {
        var target = parseFloat(el.getAttribute("data-count")) || 0;
        var dec = (el.getAttribute("data-decimals") | 0);
        var pre = el.getAttribute("data-prefix") || "";
        var suf = el.getAttribute("data-suffix") || "";
        var obj = { v: 0 };
        ScrollTrigger.create({
          trigger: el,
          start: "top 88%",
          once: true,
          onEnter: function () {
            gsap.to(obj, {
              v: target,
              duration: 1.6,
              ease: "power2.out",
              onUpdate: function () { el.textContent = pre + obj.v.toFixed(dec) + suf; }
            });
          }
        });
      });
    }

    /* ----- custom cursor ----- */
    var fine = window.matchMedia("(pointer: fine)").matches;
    if (fine && !reduced) {
      var dot = SA.q(".cursor-dot");
      var ring = SA.q(".cursor-ring");
      if (dot && ring) {
        document.documentElement.classList.add("has-cursor");
        var label = SA.q(".cursor-label", ring);
        gsap.set([dot, ring], { xPercent: -50, yPercent: -50, opacity: 0 });
        var cdx = gsap.quickTo(dot, "x", { duration: 0.1, ease: "power2" });
        var cdy = gsap.quickTo(dot, "y", { duration: 0.1, ease: "power2" });
        var crx = gsap.quickTo(ring, "x", { duration: 0.45, ease: "power3" });
        var cry = gsap.quickTo(ring, "y", { duration: 0.45, ease: "power3" });
        window.addEventListener("pointermove", function (e) {
          gsap.to([dot, ring], { opacity: 1, duration: 0.3, overwrite: "auto" });
          cdx(e.clientX); cdy(e.clientY); crx(e.clientX); cry(e.clientY);
        }, { passive: true });
        document.documentElement.addEventListener("mouseleave", function () {
          gsap.to([dot, ring], { opacity: 0, duration: 0.3 });
        });
        document.addEventListener("pointerover", function (e) {
          var t = e.target.closest && e.target.closest("[data-cursor], a, button");
          if (!t) return;
          var txt = t.getAttribute && t.getAttribute("data-cursor");
          ring.classList.toggle("is-hover", !txt);
          ring.classList.toggle("is-label", !!txt);
          if (label) label.textContent = txt || "";
        });
      }
    }

    /* ----- cinematic hero intro ----- */
    var hero = SA.q(".hero-cine");
    if (hero) {
      var heroLines = SA.qa(".hero-cine h1 .line > span", hero);
      var heroTl = gsap.timeline({ paused: true, defaults: { ease: "power4.out" } });
      heroTl
        .fromTo(".nav", { yPercent: -120, opacity: 0 }, { yPercent: 0, opacity: 1, duration: 0.9 }, 0)
        .fromTo(".hero-cine__label", { y: 24, opacity: 0 }, { y: 0, opacity: 1, duration: 0.7 }, 0.18)
        .fromTo(heroLines, { yPercent: 118 }, { yPercent: 0, duration: 1.05, stagger: 0.11 }, 0.3)
        .fromTo(".hero-cine__sub", { y: 24, opacity: 0 }, { y: 0, opacity: 1, duration: 0.7 }, 0.9)
        .fromTo(".hero-cine__actions > *", { y: 26, opacity: 0 }, { y: 0, opacity: 1, duration: 0.6, stagger: 0.09 }, 1.05)
        .fromTo(".hero-cine > .video-bg", { scale: 1.12 }, { scale: 1, duration: 1.7, ease: "power2.out" }, 0)
        .fromTo(".scroll-enter", { opacity: 0 }, { opacity: 1, duration: 0.6 }, 1.35);
      var playHero = function () { heroTl.play(); };
      if (document.documentElement.classList.contains("is-loading")) {
        document.addEventListener("sa:ready", playHero, { once: true });
      } else {
        playHero();
      }
    }

    /* ----- product reveal (blur → sharp) ----- */
    if (window.ScrollTrigger) {
      SA.qa(".product-ui").forEach(function (el) {
        ScrollTrigger.create({
          trigger: el,
          start: "top 78%",
          once: true,
          onEnter: function () {
            gsap.delayedCall(0.12, function () { el.classList.add("is-revealed"); });
          }
        });
      });

      /* drive the Three.js camera from scroll (engine may load later) */
      var engine = SA.q(".engine");
      if (engine) {
        ScrollTrigger.create({
          trigger: engine,
          start: "top bottom",
          end: "bottom top",
          onUpdate: function (self) {
            if (window.VyavasEngine && window.VyavasEngine.setScroll) {
              window.VyavasEngine.setScroll(self.progress);
            }
          }
        });
      }
    }

    /* ----- marquee ----- */
    SA.qa(".marquee-track").forEach(function (track) {
      if (reduced) return;
      var clone = track.cloneNode(true);
      track.parentNode.appendChild(clone);
      var half = track.scrollWidth;
      gsap.set([track, clone], { x: 0 });
      gsap.to([track, clone], {
        x: -half,
        duration: half / 60,
        ease: "none",
        repeat: -1,
        modifiers: { x: function (x) { return (parseFloat(x) % half) + "px"; } }
      });
      if (window.ScrollTrigger) {
        gsap.to([track, clone], {
          x: -half * 0.35,
          ease: "none",
          overwrite: "auto",
          scrollTrigger: { trigger: track, start: "top bottom", end: "bottom top", scrub: 1 }
        });
      }
    });

    /* ----- tilt cards + cursor spotlight ----- */
    if (fine && !reduced) {
      SA.qa(".tilt").forEach(function (el) {
        var rect = null;
        el.addEventListener("pointerenter", function () { rect = el.getBoundingClientRect(); });
        el.addEventListener("pointermove", function (e) {
          if (!rect) rect = el.getBoundingClientRect();
          var px = (e.clientX - rect.left) / rect.width;
          var py = (e.clientY - rect.top) / rect.height;
          el.style.setProperty("--ax", (px * 100).toFixed(1) + "%");
          el.style.setProperty("--ay", (py * 100).toFixed(1) + "%");
          gsap.to(el, {
            rotationY: (px - 0.5) * 12,
            rotationX: -(py - 0.5) * 12,
            transformPerspective: 900,
            duration: 0.5,
            ease: "power2.out"
          });
        });
        el.addEventListener("pointerleave", function () {
          rect = null;
          gsap.to(el, { rotationX: 0, rotationY: 0, duration: 0.7, ease: "power3.out" });
        });
      });

      /* magnetic buttons */
      SA.qa(".magnetic").forEach(function (el) {
        el.addEventListener("pointermove", function (e) {
          var r = el.getBoundingClientRect();
          gsap.to(el, {
            x: (e.clientX - (r.left + r.width / 2)) * 0.22,
            y: (e.clientY - (r.top + r.height / 2)) * 0.3,
            duration: 0.5,
            ease: "power2.out"
          });
        });
        el.addEventListener("pointerleave", function () {
          gsap.to(el, { x: 0, y: 0, duration: 0.7, ease: "elastic.out(1, 0.5)" });
        });
      });

      /* cursor glow */
      var glow = SA.q(".cursor-glow");
      if (glow) {
        gsap.set(glow, { xPercent: -50, yPercent: -50, opacity: 0 });
        var gx = gsap.quickTo(glow, "x", { duration: 0.6, ease: "power3" });
        var gy = gsap.quickTo(glow, "y", { duration: 0.6, ease: "power3" });
        window.addEventListener("pointermove", function (e) {
          gsap.to(glow, { opacity: 0.6, duration: 0.4 });
          gx(e.clientX); gy(e.clientY);
        });
        window.addEventListener("pointerleave", function () {
          gsap.to(glow, { opacity: 0, duration: 0.4 });
        });
      }
    }
  });
})();
