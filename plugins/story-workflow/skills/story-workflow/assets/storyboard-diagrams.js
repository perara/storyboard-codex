window.addEventListener("DOMContentLoaded", () => {
  if (!window.mermaid) return;
  mermaid.initialize({
    startOnLoad: false,
    securityLevel: "strict",
    suppressErrorRendering: true,
    maxTextSize: 16000,
    htmlLabels: false,
    fontFamily: "Inter, system-ui, sans-serif",
    theme: "base",
    themeVariables: {
      primaryColor: "#eef3ee",
      primaryTextColor: "#172420",
      primaryBorderColor: "#769186",
      lineColor: "#4b635a",
      edgeLabelBackground: "#f5f7f4",
    },
    flowchart: { nodeSpacing: 20, rankSpacing: 26, diagramPadding: 14 },
  });

  const dialog = document.getElementById("diagram-dialog");
  const fullSize = dialog.querySelector(".dialog-image");
  const figures = Array.from(document.querySelectorAll(".behavior-diagram"));
  let opener;
  dialog.addEventListener("close", () => {
    fullSize.replaceChildren();
    if (opener?.isConnected) opener.focus();
  });

  async function renderDiagram(figure) {
    if (figure.dataset.rendered || figure.closest("[hidden]") || !figure.getClientRects().length) return;
    figure.dataset.rendered = "true";
    const source = figure.querySelector(".diagram-source pre");
    const view = figure.querySelector(".diagram-view");
    const button = figure.querySelector(".enlarge-diagram");
    view.setAttribute("aria-busy", "true");
    try {
      const { svg } = await mermaid.render(figure.id + "-svg", source.textContent);
      const parsed = new DOMParser().parseFromString(svg, "image/svg+xml");
      const graphic = parsed.documentElement;
      const [, , width, height] = (graphic.getAttribute("viewBox") || "").split(/[ ,]+/).map(Number);
      const image = new Image();
      if (width > 0 && height > 0) {
        graphic.setAttribute("width", Math.ceil(width));
        graphic.setAttribute("height", Math.ceil(height));
        image.width = Math.ceil(width);
        image.height = Math.ceil(height);
      }
      image.alt = parsed.querySelector("desc")?.textContent || "Behavior diagram";
      image.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(new XMLSerializer().serializeToString(graphic));
      await image.decode();
      view.replaceChildren(image);
      button.hidden = false;
      button.addEventListener("click", () => {
        opener = button;
        fullSize.replaceChildren(image.cloneNode());
        dialog.showModal();
        fullSize.scrollTop = 0;
        fullSize.scrollLeft = 0;
      });
    } catch {
      const status = document.createElement("p");
      status.className = "diagram-error";
      status.textContent = "This diagram could not render. Open Mermaid source to read it.";
      view.replaceChildren(status);
    } finally {
      view.removeAttribute("aria-busy");
    }
  }

  function renderVisibleDiagrams() {
    for (const figure of figures) renderDiagram(figure);
  }
  document.addEventListener("storyboard:view", renderVisibleDiagrams);
  window.matchMedia("(max-width: 53rem)").addEventListener("change", renderVisibleDiagrams);
  renderVisibleDiagrams();
});
