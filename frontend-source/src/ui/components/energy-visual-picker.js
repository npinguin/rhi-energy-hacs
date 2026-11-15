// Compact Energy logical-device image editor.
// Presentation-only: selection is drafted in the card and persisted only on explicit Save.
class HomeBrainEnergyVisualPicker {
  constructor() {}

  catalogFor(asset = {}) {
    const type = String(asset.asset_type || asset.object_class || "").trim().toLowerCase();
    return typeof rhiEnergyVisualCatalogForType === "function" ? rhiEnergyVisualCatalogForType(type) : [];
  }

  render(asset = {}, selectedRef = "", { draftRef = "", brand = "all" } = {}) {
    const assetId = String(asset.asset_id || asset.id || "").trim();
    const type = String(asset.asset_type || asset.object_class || "").trim().toLowerCase();
    const choices = this.catalogFor(asset);
    if (!assetId || !type || !choices.length) return "";

    const current = String(draftRef || selectedRef || "").trim();
    const brands = typeof rhiEnergyVisualBrandsForType === "function"
      ? rhiEnergyVisualBrandsForType(type)
      : [...new Set(choices.map(entry => String(entry.brand || "").trim()).filter(Boolean))].sort();
    const activeBrand = brand !== "all" && brands.includes(brand) ? brand : "all";
    const visible = activeBrand === "all" ? choices : choices.filter(entry => String(entry.brand || "") === activeBrand);

    const filtersHtml = rhiUxVisualFilterButtons({ values:brands, active:activeBrand, attribute:"data-energy-visual-brand" });

    const choicesHtml = visible.map(entry => {
      const ref = rhiEnergyVisualRef(entry);
      const visual = typeof resolveEnergyVisualRef === "function" ? resolveEnergyVisualRef(ref) : null;
      const selected = ref === current;
      return rhiUxVisualChoice({id:ref,image:visual?.url || "",label:entry.model || entry.label,eyebrow:entry.brand || "Representative",detail:entry.variant || human(type),selected,attributes:{"data-energy-visual-select":ref,"data-energy-visual-asset":assetId}});
    }).join("");

    const resetHtml = `<button type="button" data-energy-visual-reset="${escapeHtml(assetId)}">Use profile default</button>`;
    const cancelHtml = `<button type="button" data-energy-visual-cancel="1">Cancel</button>`;
    const saveHtml = `<button type="button" class="primary" data-energy-visual-save="${escapeHtml(assetId)}" ${current ? "" : "disabled"}>Save appearance</button>`;
    const closeHtml = `<button type="button" class="energyVisualClose" data-energy-visual-cancel="1" aria-label="Cancel">×</button>`;

    return typeof rhiUxVisualPickerShell === "function"
      ? rhiUxVisualPickerShell({
          eyebrow:`${rhiEnergyT(this.hass,"common.appearance",{},"Appearance")} · ${human(type)}`,
          title:rhiEnergyT(this.hass,"common.choose_appearance",{},"Choose appearance"),
          description:rhiEnergyT(this.hass,"appearance.description",{},"Choose the representative image. The selection is persisted by the owning domain and confirmed by readback."),
          filtersHtml,
          choicesHtml,
          resetHtml,
          cancelHtml,
          saveHtml,
          modal:true,
          closeHtml
        }).replace('class="rhiUxVisualPickerBackdrop"', 'class="rhiUxVisualPickerBackdrop" data-energy-visual-backdrop="1"')
      : "";
  }
}

function rhiEnergyVisualPickerStyles() {
  return `
    .assetVisual[data-energy-visual-open]{cursor:pointer;outline:0}
    .assetVisual[data-energy-visual-open]:hover{box-shadow:0 0 0 2px rgba(37,99,235,.16)}
    .energyVisualClose{border:0;background:#f1f5f9;border-radius:10px;width:36px;height:36px;font-size:22px;cursor:pointer}
  `;
}
