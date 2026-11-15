// Visual resolver for Energy-owned presentation preferences and registered cross-domain refs.
// Cross-domain visual identity is opaque and resolved only through Foundation registry metadata.
function rhiEnergyVisualAssetUrl(relativePath = "") {
  const normalized = String(relativePath || "").replace(/^\/+/, "");
  return `/rhi_energy/frontend/assets/${normalized}?v=${encodeURIComponent(UX_VERSION)}`;
}

function resolveEnergyOwnedVisualRef(visualRef = "") {
  const ref = String(visualRef || "").trim();
  const entry = typeof rhiEnergyVisualEntryFromRef === "function" ? rhiEnergyVisualEntryFromRef(ref) : null;
  if (!entry) return null;
  const inlineAssets = {
    byd_lvs20: typeof HERO_IMAGE_BYD_LVS20 === "string" ? HERO_IMAGE_BYD_LVS20 : "",
    solaredge_48v_9_6: typeof HERO_IMAGE_SOLAREDGE_92 === "string" ? HERO_IMAGE_SOLAREDGE_92 : ""
  };
  const url = entry.inline_asset
    ? inlineAssets[String(entry.inline_asset || "")] || ""
    : rhiEnergyVisualAssetUrl(entry.package_path || "");
  if (!url) return null;
  return Object.freeze({
    visual_ref: ref,
    owner_domain: "rhi_energy_ux",
    kind: "energy_logical_device",
    asset_type: entry.asset_type,
    catalog_id: entry.id,
    quality: entry.quality || "representative",
    url,
    filter: "none"
  });
}

function resolveEnergyVisualRef(visualRef = "", registry = null, variant = "card") {
  const ref = String(visualRef || "").trim();
  if (!ref) return null;

  // Backend/domain visual refs are registered producer identity. Never interpret
  // their namespace, brand, model, image key or asset id in Energy.
  const registered = typeof rhiRegisteredPresentationUrl === "function"
    ? rhiRegisteredPresentationUrl(registry, ref, variant)
    : null;
  if (registered) return registered;

  // UX-local Energy presentation preferences are not cross-domain semantic identity.
  if (ref.startsWith("energy.logical.")) return resolveEnergyOwnedVisualRef(ref);

  // Missing/unregistered producer identity fails closed. Callers render a neutral icon.
  return null;
}

function resolveEnergyAssetVisual(asset = {}, registry = null, variant = "card") {
  const sourceRef = String(asset.visual_ref || asset.visualRef || asset.raw?.visual_ref || "").trim();

  // Any registered producer/domain visual is authoritative.
  if (sourceRef) {
    const registered = resolveEnergyVisualRef(sourceRef, registry, variant);
    if (registered) return registered;

    // An explicit non-UX-local ref must never be replaced by an Energy semantic image.
    if (!sourceRef.startsWith("energy.logical.")) return null;
  }

  const assetType = String(asset.asset_type || asset.object_class || "").trim().toLowerCase();

  const sourceEntry = typeof rhiEnergyVisualEntryFromRef === "function"
    ? rhiEnergyVisualEntryFromRef(sourceRef)
    : null;
  if (sourceEntry && sourceEntry.asset_type === assetType) {
    return resolveEnergyOwnedVisualRef(sourceRef);
  }

  const fallbackEntry = typeof rhiEnergyDefaultVisualEntry === "function"
    ? rhiEnergyDefaultVisualEntry(asset)
    : null;
  return fallbackEntry ? resolveEnergyOwnedVisualRef(rhiEnergyVisualRef(fallbackEntry)) : null;
}
