(() => {
  const nodes = [...document.querySelectorAll(".node")];
  const stageLinks = [...document.querySelectorAll("[data-nav-stage]")];
  const toc = document.querySelector(".toc");
  const compact = matchMedia("(max-width: 680px)");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const dialog = document.querySelector("dialog");
  const pan = dialog.querySelector(".pan");
  const scaleButton = dialog.querySelector(".scale");
  let current, opener, readingY, scheduled = false;

  function mark(node) {
    if (current === node) return;
    current?.classList.remove("active");
    current = node;
    current.classList.add("active");
    for (const link of stageLinks) {
      if (link.dataset.navStage === node.dataset.stage) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    }
    document.querySelector(".mobile-stage").textContent = node.dataset.stage + " · " + node.id;
  }

  function followScroll() {
    scheduled = false;
    if (dialog.open) return;
    const line = compact.matches ? 76 : 90;
    const node = nodes.findLast(item => item.getBoundingClientRect().top <= line);
    mark(node || nodes[0]);
  }

  function updateSoon() {
    if (!scheduled) {
      scheduled = true;
      requestAnimationFrame(followScroll);
    }
  }
  function sizeMenu() { toc.open = !compact.matches; }
  sizeMenu();
  compact.addEventListener("change", sizeMenu);
  window.addEventListener("scroll", updateSoon, {passive:true});
  window.addEventListener("resize", updateSoon);
  document.addEventListener("toggle", updateSoon, true);
  followScroll();

  document.addEventListener("click", event => {
    const link = event.target.closest('a[href^="#"]');
    if (!link || event.defaultPrevented || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const node = document.getElementById(link.hash.slice(1));
    if (!node?.classList.contains("node")) return;
    event.preventDefault();
    if (compact.matches) toc.open = false;
    if (location.hash !== link.hash) history.pushState(null, "", link.hash);
    node.focus({preventScroll:true});
    node.scrollIntoView({block:"start", behavior:"instant"});
    mark(node);
    if (!reduced.matches) {
      node.classList.remove("arrived");
      requestAnimationFrame(() => node.classList.add("arrived"));
    }
  });
  window.addEventListener("hashchange", updateSoon);
  window.addEventListener("pageshow", updateSoon);

  function setScale(fullSize) {
    pan.classList.toggle("full-size", fullSize);
    scaleButton.setAttribute("aria-pressed", String(fullSize));
    scaleButton.textContent = fullSize ? "适应窗口" : "原尺寸";
    pan.scrollTo(0, 0);
  }
  scaleButton.addEventListener("click", () => setScale(!pan.classList.contains("full-size")));
  document.querySelectorAll(".enlarge").forEach(button => {
    button.addEventListener("click", () => {
      opener = button;
      readingY = window.scrollY;
      const figure = button.closest("figure");
      const original = button.querySelector("img");
      const enlarged = dialog.querySelector("img");
      enlarged.src = original.src;
      enlarged.alt = original.alt;
      const caption = dialog.querySelector("figcaption");
      caption.replaceChildren(...[...figure.querySelectorAll(".caption,.credit")].map(el => el.cloneNode(true)));
      setScale(false);
      dialog.showModal();
      document.documentElement.style.overflow = "hidden";
    });
  });
  dialog.querySelector(".close").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", event => {
    if (event.target !== dialog) return;
    const r = dialog.getBoundingClientRect();
    if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close();
  });
  dialog.addEventListener("close", () => {
    document.documentElement.style.overflow = "";
    opener?.focus({preventScroll:true});
    window.scrollTo({top:readingY, behavior:"instant"});
  });
})();
