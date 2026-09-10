(() => {
  const root = document.documentElement;
  const body = document.body;
  const header = document.querySelector("#header");
  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  root.classList.remove("wf-loading");
  root.classList.add("mirror-js", "wf-active");

  const updateHeaderMetrics = () => {
    if (!header) return;
    const height = header.getBoundingClientRect().height;
    root.style.setProperty("--header-height", `${height}px`);
    root.style.setProperty("--header-fixed-top-offset", `${height}px`);
    root.style.scrollPaddingTop = `${height}px`;
  };

  updateHeaderMetrics();
  addEventListener("resize", updateHeaderMetrics, { passive: true });

  const scaledTextContainers = [...document.querySelectorAll(".sqsrte-scaled-text-container")];
  const fitScaledText = (container) => {
    const scaledText = container.querySelector(".sqsrte-scaled-text");
    const text = scaledText?.firstElementChild;
    if (!scaledText || !text || !container.clientWidth) return;

    container.classList.add("loaded");
    scaledText.style.position = "relative";
    scaledText.style.whiteSpace = "nowrap";
    const probeSize = 1000;
    scaledText.style.fontSize = `${probeSize}px`;
    text.style.position = "relative";
    text.style.fontSize = "inherit";
    text.style.lineHeight = "1";
    text.style.whiteSpace = "nowrap";

    const textRange = document.createRange();
    textRange.selectNodeContents(text.querySelector("span") || text);
    const measuredWidth = textRange.getBoundingClientRect().width;
    if (measuredWidth > 0) {
      const fittedSize = (probeSize * container.clientWidth) / measuredWidth;
      const squarespaceFitAllowance = fittedSize > 100 ? 0.99975 : 1;
      scaledText.style.fontSize = `${Math.round(fittedSize * squarespaceFitAllowance * 10) / 10}px`;
    }
  };
  const fitScaledTexts = () => scaledTextContainers.forEach(fitScaledText);

  fitScaledTexts();
  document.fonts?.ready.then(fitScaledTexts);
  addEventListener("resize", fitScaledTexts, { passive: true });

  document.querySelectorAll(".section-background-content").forEach((background) => {
    const image = background.querySelector("img.background-image-fx");
    if (!image) return;

    const syncImageEffectFallback = () => {
      const activeCanvas = [...background.querySelectorAll("canvas")].some(
        (canvas) => canvas.getBoundingClientRect().width > 0 && getComputedStyle(canvas).display !== "none",
      );
      image.classList.toggle("mirror-image-fallback", !activeCanvas);
    };

    syncImageEffectFallback();
    new MutationObserver(syncImageEffectFallback).observe(background, {
      attributes: true,
      childList: true,
      subtree: true,
    });
  });

  const reveal = (element) => element.classList.add("fadeIn");
  const revealTargets = [...document.querySelectorAll(".preFade")];

  if (reducedMotion || !("IntersectionObserver" in window)) {
    revealTargets.forEach(reveal);
  } else {
    const revealObserver = new IntersectionObserver(
      (entries, observer) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          reveal(entry.target);
          observer.unobserve(entry.target);
        }
      },
      { rootMargin: "12% 0px 12% 0px", threshold: 0.01 },
    );
    revealTargets.forEach((element) => revealObserver.observe(element));
  }

  document.querySelectorAll("img").forEach((image) => {
    image.decoding = "async";
    if (!image.hasAttribute("loading")) image.loading = "lazy";
    image.addEventListener(
      "load",
      () => image.closest(".fluid-image-component-root")?.classList.add("animation-loaded"),
      { once: true },
    );
  });

  document.querySelectorAll(".Marquee-svg").forEach((svg) => {
    svg.style.height = "22px";
    svg.style.transform = "translateY(2.2px)";
    svg.style.overflow = "visible";
    svg.querySelectorAll(".Marquee-path-hitbox-focus-outline").forEach((path) => {
      path.style.transform = "translateY(2.2px)";
    });
  });

  const mobileHeader = document.querySelector(".header-display-mobile");
  const burger = mobileHeader?.querySelector(".header-burger-btn");
  const menu = document.querySelector(".header-menu");
  let openBeforeInteraction = false;

  const isOpen = () => body.classList.contains("header--menu-open");
  const setMenuOpen = (open) => {
    body.classList.toggle("header--menu-open", open);
    burger?.classList.toggle("burger--active", open);
    if (menu && header) menu.style.paddingTop = `${header.getBoundingClientRect().height}px`;
    if (open) menu?.querySelector("a")?.focus({ preventScroll: true });
    else burger?.focus({ preventScroll: true });
  };

  const rememberMenuState = () => {
    openBeforeInteraction = isOpen();
  };

  burger?.addEventListener("pointerdown", rememberMenuState, true);
  burger?.addEventListener("keydown", rememberMenuState, true);
  burger?.addEventListener("click", () => {
    setTimeout(() => {
      if (isOpen() === openBeforeInteraction) setMenuOpen(!openBeforeInteraction);
    }, 50);
  });

  menu?.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener("click", () => setMenuOpen(false));
  });

  document.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener(
      "click",
      (event) => {
        const hash = link.getAttribute("href");
        if (!hash || hash === "#") return;
        const target = document.querySelector(hash);
        if (!target) return;

        event.preventDefault();
        setMenuOpen(false);
        target.scrollIntoView({
          behavior: reducedMotion ? "auto" : "smooth",
          block: "start",
        });
        history.pushState(null, "", hash);
      },
      true,
    );
  });

  addEventListener("keydown", (event) => {
    if (event.key === "Escape" && isOpen()) setMenuOpen(false);
  });
})();
