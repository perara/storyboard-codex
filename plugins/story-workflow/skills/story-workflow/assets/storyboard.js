(() => {
  const app = document.querySelector(".app-shell");
  const catalogList = document.querySelector(".record-list");
  const reader = document.getElementById("record-reader");
  const matrix = document.getElementById("compare");
  const search = document.getElementById("search");
  const category = document.getElementById("category");
  const state = document.getElementById("state");
  const review = document.getElementById("review");
  const moduleFilter = document.getElementById("module");
  const columns = document.getElementById("columns");
  const pin = document.getElementById("pin");
  const clearFilters = document.querySelector(".clear-filters");
  const filterCount = document.querySelector(".filter-count");
  const resultCount = document.querySelector(".result-count");
  const emptyState = document.getElementById("catalog-empty");
  const matrixEmpty = document.getElementById("matrix-empty");
  const stateButtons = Array.from(document.querySelectorAll(".state-button"));
  const viewLinks = Array.from(document.querySelectorAll(".view-link"));
  const records = new Map(Array.from(catalogList.children, entry => {
    const { id } = entry.dataset;
    const panel = document.getElementById("record-" + id);
    const overview = panel.querySelector('[data-section="overview"].record-section');
    return [id, {
      entry, panel,
      modules: new Set(entry.dataset.modules.split(" ").filter(Boolean)),
      text: [entry.textContent, overview.textContent].join(" ").toLocaleLowerCase(),
    }];
  }));
  const matrixRows = Array.from(matrix.querySelectorAll("tbody tr"));
  const matrixHead = matrix.querySelector("thead tr");
  const selectedModules = new Map(Array.from(columns.options).slice(1).map(option => [option.value, option.text]));
  let pinned = JSON.parse(columns.dataset.defaults);
  let firstMatch = null;

  function showRoute({ focusRecord = false, focusCatalog = false } = {}) {
    const [requestedId, requestedTab] = location.hash.slice(1).split("/");
    const compare = requestedId === "compare";
    const explicitRecord = records.has(requestedId);
    const selectedId = explicitRecord ? requestedId : firstMatch;
    app.dataset.mode = compare ? "compare" : "browse";
    app.toggleAttribute("data-detail-open", explicitRecord && !compare);
    catalogList.hidden = compare;
    reader.hidden = compare || !selectedId;
    matrix.hidden = !compare;
    emptyState.hidden = Boolean(firstMatch) || compare;
    matrixEmpty.hidden = Boolean(firstMatch);

    for (const link of viewLinks) {
      const active = link.hash === (compare ? "#compare" : "#catalog");
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
    for (const [id, record] of records) {
      const active = id === selectedId && !compare;
      record.panel.hidden = !active;
      const link = record.entry.querySelector(".record-link");
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
      if (!active) continue;
      const tabs = Array.from(record.panel.querySelectorAll(".record-tab"));
      const selectedTab = tabs.find(tab => tab.dataset.section === requestedTab) || tabs[0];
      for (const tab of tabs) {
        const selected = selectedTab === tab;
        tab.setAttribute("aria-selected", String(selected));
        tab.tabIndex = selected ? 0 : -1;
        document.getElementById(tab.getAttribute("aria-controls")).hidden = !selected;
      }
    }
    document.dispatchEvent(new Event("storyboard:view"));
    if (focusRecord && selectedId && !compare) {
      const heading = records.get(selectedId).panel.querySelector(".record-heading");
      heading.focus({ preventScroll: true });
      if (window.matchMedia("(max-width: 53rem)").matches) window.scrollTo(0, 0);
    } else if (focusCatalog) {
      const previous = records.get(focusCatalog)?.entry;
      const focus = previous && !previous.hidden ? previous.querySelector(".record-link") : search;
      focus.focus({ preventScroll: true });
      window.scrollTo(0, 0);
    }
  }

  function navigate(hash, options, replace = false) {
    if (location.hash !== hash) {
      if (replace) history.replaceState(null, "", hash);
      else history.pushState(null, "", hash);
    }
    showRoute(options);
  }

  function applyFilters(keepRoute = false) {
    const term = search.value.trim().toLocaleLowerCase();
    const filters = [category.value, state.value, review.value, moduleFilter.value];
    const activeFilters = filters.filter(Boolean).length;
    const matches = new Set();
    for (const [id, item] of records) {
      const data = item.entry.dataset;
      const match = (!category.value || data.category === category.value)
        && (!state.value || data.state === state.value)
        && (!review.value || data.review === review.value)
        && (!moduleFilter.value || item.modules.has(moduleFilter.value))
        && (!term || item.text.includes(term));
      item.entry.hidden = !match;
      if (match) matches.add(id);
    }
    for (const row of matrixRows) row.hidden = !matches.has(row.dataset.id);
    firstMatch = matches.values().next().value || null;
    resultCount.textContent = matches.size === records.size
      ? String(records.size) + (records.size === 1 ? " record" : " records")
      : String(matches.size) + " of " + String(records.size) + " records";
    filterCount.textContent = String(activeFilters);
    filterCount.hidden = !activeFilters;
    clearFilters.hidden = !activeFilters && !term;
    for (const button of stateButtons) button.setAttribute("aria-pressed", String(button.value === state.value));

    const routeId = location.hash.slice(1).split("/")[0];
    if (!keepRoute && records.has(routeId) && !matches.has(routeId)) {
      navigate("#catalog", {}, true);
    } else {
      showRoute();
    }
  }

  function renderColumns() {
    for (const row of [matrixHead, ...matrixRows]) {
      for (const cell of row.querySelectorAll(".module-column")) cell.remove();
    }
    for (const id of pinned) {
      const label = selectedModules.get(id);
      const heading = document.createElement("th");
      heading.scope = "col";
      heading.className = "module-column";
      heading.textContent = label;
      heading.setAttribute("aria-label", label);
      const remove = document.createElement("button");
      remove.type = "button";
      remove.textContent = "Remove";
      remove.setAttribute("aria-label", "Remove " + label + " column");
      remove.addEventListener("click", () => {
        pinned = pinned.filter(moduleId => moduleId !== id);
        renderColumns();
        columns.focus();
      });
      heading.append(remove);
      matrixHead.append(heading);
      for (const row of matrixRows) {
        const cell = row.insertCell();
        cell.className = "module-column module-value";
        cell.textContent = records.get(row.dataset.id).modules.has(id) ? "Affected" : "—";
      }
    }
    syncColumnControl();
  }

  function syncColumnControl() {
    for (const option of columns.options) option.disabled = pinned.includes(option.value);
    columns.disabled = pinned.length >= Number(columns.dataset.max) || pinned.length === selectedModules.size;
    pin.disabled = columns.disabled || !columns.value;
  }

  for (const { panel } of records.values()) {
    const tabList = panel.querySelector(".record-tabs");
    tabList.setAttribute("role", "tablist");
    const tabs = Array.from(tabList.querySelectorAll(".record-tab"));
    for (const tab of tabs) {
      const content = panel.querySelector('.record-section[data-section="' + tab.dataset.section + '"]');
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-controls", content.id);
      content.setAttribute("role", "tabpanel");
      content.setAttribute("aria-labelledby", tab.id);
      content.tabIndex = 0;
    }
    tabList.addEventListener("keydown", event => {
      const index = tabs.indexOf(event.target);
      if (index < 0) return;
      let next;
      switch (event.key) {
        case "ArrowRight": next = (index + 1) % tabs.length; break;
        case "ArrowLeft": next = (index + tabs.length - 1) % tabs.length; break;
        case "Home": next = 0; break;
        case "End": next = tabs.length - 1; break;
        default: return;
      }
      event.preventDefault();
      navigate(tabs[next].hash, {}, true);
      tabs[next].focus();
    });
  }

  document.addEventListener("click", event => {
    const link = event.target.closest("a[href^='#']");
    if (!link || event.defaultPrevented || event.button !== 0
      || event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return;
    const hash = link.hash;
    const routeId = hash.slice(1).split("/")[0];
    if (!records.has(routeId) && hash !== "#compare" && hash !== "#catalog") return;
    event.preventDefault();
    const isTab = link.classList.contains("record-tab");
    const isBack = link.classList.contains("mobile-back");
    navigate(hash, {
      focusRecord: records.has(routeId) && !isTab,
      focusCatalog: isBack ? link.closest(".record-panel").dataset.id : false,
    }, isTab);
  });

  pin.addEventListener("click", () => {
    if (pin.disabled) return;
    pinned.push(columns.value);
    columns.value = "";
    renderColumns();
    if (columns.disabled) matrixHead.lastElementChild.querySelector("button").focus();
    else columns.focus();
  });
  columns.addEventListener("change", syncColumnControl);
  clearFilters.addEventListener("click", () => {
    for (const control of [search, category, state, review, moduleFilter]) control.value = "";
    applyFilters();
    search.focus();
  });
  for (const button of stateButtons) button.addEventListener("click", () => {
    state.value = button.value;
    applyFilters();
  });
  for (const control of [search, category, state, review, moduleFilter]) {
    control.addEventListener("input", () => applyFilters());
  }

  window.addEventListener("hashchange", () => showRoute());
  window.addEventListener("popstate", () => showRoute());
  app.classList.add("js");
  renderColumns();
  applyFilters(true);
})();
