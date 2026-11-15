// Energy presentation grammar.
// Owns navigation metadata, tab hero assets, shared visual hierarchy and card primitives.
// Domain semantics, calculations, actions and runtime truth remain backend/domain owned.

const HB_ENERGY_NAVIGATION_SPEC = Object.freeze([
  {
    id:"energy", labelKey:"nav.energy", fallback:"Energy",
    items:[
      { id:"overview", labelKey:"nav.overview", fallback:"Overview", view:"overview", titleKey:"hero.overview.title", descriptionKey:"hero.overview.description" },
      { id:"flow", labelKey:"nav.flow", fallback:"Flow", view:"flow", titleKey:"hero.flow.title", descriptionKey:"hero.flow.description" },
      { id:"solar", labelKey:"nav.solar", fallback:"Solar", view:"solar", titleKey:"hero.solar.title", descriptionKey:"hero.solar.description" },
      { id:"battery", labelKey:"nav.battery", fallback:"Home Battery", view:"battery", titleKey:"hero.battery.title", descriptionKey:"hero.battery.description" },
      { id:"consumers", labelKey:"nav.consumption", fallback:"Consumption", view:"consumers", titleKey:"hero.consumption.title", descriptionKey:"hero.consumption.description" },
      { id:"gas", labelKey:"nav.gas", fallback:"Gas", view:"gas", titleKey:"hero.gas.title", descriptionKey:"hero.gas.description" }
    ]
  },
  {
    id:"intelligence", labelKey:"nav.intelligence", fallback:"Intelligence",
    items:[
      { id:"forecast", labelKey:"nav.forecast", fallback:"Forecast", view:"outlook", titleKey:"hero.plan.title", descriptionKey:"hero.plan.description" },
      { id:"strategic", labelKey:"nav.strategic", fallback:"Strategic", view:"strategic-planning", titleKey:"hero.strategic.title", descriptionKey:"hero.strategic.description" },
      { id:"plan", labelKey:"nav.tactical", fallback:"Tactical", view:"planning", titleKey:"hero.plan.title", descriptionKey:"hero.plan.description" },
      { id:"operational", labelKey:"nav.operational", fallback:"Operational", view:"operational-planning", titleKey:"hero.operational.title", descriptionKey:"hero.operational.description" },
      { id:"settings", labelKey:"nav.settings", fallback:"Settings", view:"strategies", titleKey:"hero.settings.title", descriptionKey:"hero.settings.description" }
    ]
  },
  {
    id:"insights", labelKey:"nav.insights", fallback:"Insights",
    items:[
      { id:"metering", labelKey:"nav.performance", fallback:"Performance", view:"metering", titleKey:"hero.performance.title", descriptionKey:"hero.performance.description" },
      { id:"value", labelKey:"nav.value", fallback:"Value", view:"value", titleKey:"hero.value.title", descriptionKey:"hero.value.description" },
      { id:"retrospective", labelKey:"nav.retrospective", fallback:"Retrospective", view:"retrospective", titleKey:"hero.retrospective.title", descriptionKey:"hero.retrospective.description" }
    ]
  }
]);

function hbEnergyNavigation(hass = null) {
  return HB_ENERGY_NAVIGATION_SPEC.map(section => ({
    id:section.id,
    label:rhiEnergyT(hass,section.labelKey,{},section.fallback),
    items:section.items.map(item => ({
      ...item,
      label:rhiEnergyT(hass,item.labelKey,{},item.fallback),
      title:rhiEnergyT(hass,item.titleKey,{},item.fallback),
      description:rhiEnergyT(hass,item.descriptionKey,{},"")
    }))
  }));
}

const HB_ENERGY_HERO_ASSETS = Object.freeze({
  overview: "heroes/overview-hero.webp",
  flow: "heroes/flow-hero.webp",
  solar: "heroes/solar-hero.webp",
  "solar-generation": "heroes/solar-hero.webp",
  battery: "heroes/battery-hero.webp",
  consumers: "heroes/consumers-hero.webp",
  gas: "heroes/gas-page-hero-v3.webp",
  strategy: "heroes/strategies-hero.webp",
  strategies: "heroes/strategies-hero.webp",
  intelligence: "heroes/intelligence-hero.webp",
  "operational-planning": "heroes/planning-hero.webp",
  outlook: "heroes/outlook-hero.webp",
  "tactical-planning": "heroes/planning-hero.webp",
  planning: "heroes/planning-hero.webp",
  "strategic-planning": "heroes/strategies-hero.webp",
  metering: "heroes/metering-hero.webp",
  value: "heroes/value-hero.webp",
  retrospective: "heroes/diagnostics-hero.webp"
});

const HB_ENERGY_PROFILE_ALIASES = Object.freeze({
  "solar-generation": "solar",
  planning: "outlook",
  settings: "strategies",
  "strategic-planning": "strategies"
});

function hbEnergyAssetUrl(relativePath = "") {
  const normalized = String(relativePath || "").replace(/^\/+/, "");
  return `/rhi_energy/frontend/assets/${normalized}?v=${encodeURIComponent(UX_VERSION)}`;
}

function hbEnergyHeroAsset(tab = "overview") {
  return hbEnergyAssetUrl(HB_ENERGY_HERO_ASSETS[tab] || HB_ENERGY_HERO_ASSETS.overview);
}

function hbEnergyProfileKey(tab = "overview") {
  return HB_ENERGY_PROFILE_ALIASES[tab] || tab;
}

function hbEnergyPresentationStyles() {
  return `${rhiUxCoreStyles()}
    :host{
      /* Transitional aliases for domain-local styles. Shared primitives use --rhi-* directly. */
      --rhi-line:var(--rhi-color-line);
      --rhi-ink:var(--rhi-color-text);
      --rhi-muted:var(--rhi-color-muted);
      --rhi-blue:var(--rhi-color-primary);
      --rhi-surface:var(--rhi-color-surface);
      --rhi-soft:var(--rhi-color-surface-soft);
      --rhi-shadow:var(--rhi-shadow-md);
      --rhi-card-gap:var(--rhi-space-2);
    }
    .rhiEnergyNav-intelligence{--rhi-nav-active-bg:#F1EDFF;--rhi-nav-active-border:#DFD5FB;--rhi-nav-active-text:#5A38B3}
    .rhiEnergyNav-insights{--rhi-nav-active-bg:#E7F7F4;--rhi-nav-active-border:#CDEBE6;--rhi-nav-active-text:#176E67}
    .rhiEnergyPageHeader{display:block;margin:0 0 10px}
    @media(max-width:760px){
    }
    .rhi-context-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--rhi-space-2)}
    .rhi-context-card{min-width:0;border:1px solid var(--rhi-color-line);border-radius:var(--rhi-radius-lg);background:var(--rhi-color-surface);box-shadow:var(--rhi-shadow-sm);padding:10px 12px}
    .rhi-data-list{display:grid;gap:6px}
    .rhi-data-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;padding:9px 10px;border:1px solid #EDF1F6;border-radius:var(--rhi-radius-sm);background:var(--rhi-color-surface-soft)}
    @media(max-width:760px){.rhi-context-grid{grid-template-columns:1fr}}
  `;
}
