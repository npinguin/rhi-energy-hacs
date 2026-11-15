// Generic cross-domain visual presentation resolver.
// Producer domains register visual identity + presentation with Foundation.
// Energy must never carry producer model/brand/image-key mappings.
const RHI_FOUNDATION_VISUAL_REGISTRY_CONTRACT = "RHI_VISUAL_ASSET_REGISTRY_V2";

function readFoundationVisualRegistry(hass = {}) {
  const states = Object.values(hass?.states || {});
  const state = states.find(candidate =>
    String(candidate?.attributes?.contract_id || "") === RHI_FOUNDATION_VISUAL_REGISTRY_CONTRACT
  ) || null;
  const attributes = state?.attributes || {};
  const rawEntries = parseMaybeJson(attributes.entries, attributes.entries);
  const entries = Array.isArray(rawEntries)
    ? rawEntries.filter(row => row && typeof row === "object")
    : [];
  const byRef = new Map(entries.map(row => [String(row.visual_ref || ""), Object.freeze({...row})]).filter(([ref]) => ref));
  return Object.freeze({
    available: !!state,
    entityId: String(state?.entity_id || ""),
    contractId: String(attributes.contract_id || ""),
    contractVersion: String(attributes.contract_version || ""),
    status: String(attributes.status || state?.state || "UNAVAILABLE"),
    entries: Object.freeze(entries),
    entry(visualRef = "") { return byRef.get(String(visualRef || "").trim()) || null; }
  });
}

function rhiRegisteredPresentationUrl(registry, visualRef = "", variant = "card") {
  const ref = String(visualRef || "").trim();
  if (!ref || !registry?.available) return null;
  const entry = registry.entry(ref);
  if (!entry) return null;
  const presentation = entry.presentation && typeof entry.presentation === "object" ? entry.presentation : null;
  const packageId = String(presentation?.package_id || "").trim();
  const variants = presentation?.variants && typeof presentation.variants === "object" ? presentation.variants : {};
  const wanted = String(variant || "card");
  const packagePath = String(
    variants[wanted]
    || variants.card
    || variants.detail
    || variants.thumbnail
    || variants.hero
    || ""
  ).trim();
  if (!/^[a-z0-9][a-z0-9_-]*$/.test(packageId)) return null;
  if (!packagePath || packagePath.startsWith("/") || packagePath.includes("..") || packagePath.includes("://")) return null;
  const owner = String(entry.owner_domain || "").trim();
  if (!owner) return null;
  // Only our own package transport changes; producer identity and other packages stay intact.
  const own = packageId === "rhi-energy-ux";
  if (own && (owner !== "rhi_energy" || !/^assets\/(?:[a-z0-9][a-z0-9_.-]*\/)*[a-z0-9][a-z0-9_.-]*\.(?:webp|svg|png|jpg|jpeg)$/.test(packagePath))) return null;
  const url = own
    ? `/rhi_energy/frontend/${packagePath}?r=${encodeURIComponent(String(entry.revision || 1))}&v=${encodeURIComponent(UX_VERSION)}`
    : `/hacsfiles/${packageId}/${packagePath}?r=${encodeURIComponent(String(entry.revision || 1))}`;
  return Object.freeze({
    visual_ref: ref,
    owner_domain: String(entry.owner_domain || ""),
    asset_type: String(entry.asset_type || ""),
    kind: String(entry.asset_type || ""),
    url,
    filter: "none",
    fallback: false,
    registry_contract: RHI_FOUNDATION_VISUAL_REGISTRY_CONTRACT
  });
}
