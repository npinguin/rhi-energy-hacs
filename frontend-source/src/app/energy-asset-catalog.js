// Energy physical-asset visual catalog.
//
// This catalog is deliberately limited to user-world physical concepts and physical
// installation compositions. Dashboard hero artwork is owned by dashboard/page UX and
// must never be used as an asset fallback.
//
// Default policy (temporary): exact configured/product match first; otherwise the first
// selectable catalog entry for the exact same asset_type; otherwise no image.
const RHI_ENERGY_LOGICAL_VISUALS = Object.freeze([
  { id:"battery_system.generic", asset_type:"battery_system", label:"Home battery system", brand:"Generic", model:"Battery system", variant:"Physical system composition", profile_patterns:["energy.battery_system."], package_path:"energy/battery_system_4_towers.webp", quality:"generic_family", selectable:true },

  { id:"battery.byd_lvs_20", asset_type:"battery", label:"BYD Battery-Box Premium LVS 20.0", brand:"BYD", model:"Battery-Box Premium LVS 20.0", variant:"5 modules / 20 kWh", profile_patterns:["byd_battery_box_premium_lvs_5_module_20kwh"], package_path:"energy/byd_lvs_20.webp", quality:"verified_product", selectable:true },
  { id:"battery.solaredge_home_48v", asset_type:"battery", label:"SolarEdge Home Battery 48V", brand:"SolarEdge", model:"Home Battery 48V", variant:"BAT-05K48", profile_patterns:["solaredge_48v_home_battery"], package_path:"energy/solaredge_home_battery_48v_9_6.webp", quality:"verified_product", selectable:true },
  { id:"battery.huawei_luna2000_15_s0", asset_type:"battery", label:"Huawei LUNA2000-15-S0", brand:"Huawei", model:"LUNA2000-15-S0", variant:"15 kWh", profile_patterns:["huawei_luna2000_15_s0"], package_path:"energy/huawei_luna2000_15_s0.webp", quality:"verified_product", selectable:true },
  { id:"battery.sonnen_batterie10_10", asset_type:"battery", label:"sonnenBatterie 10 · 10 kWh", brand:"sonnen", model:"sonnenBatterie 10", variant:"10 kWh", profile_patterns:["sonnen_batterie_10_10kwh"], package_path:"energy/sonnen_batterie_10_10kwh.webp", quality:"verified_appearance", selectable:true },
  { id:"battery.sonnen_batterie10_20", asset_type:"battery", label:"sonnenBatterie 10 · 20 kWh", brand:"sonnen", model:"sonnenBatterie 10", variant:"20 kWh", profile_patterns:["sonnen_batterie_10_20kwh"], package_path:"energy/sonnen_batterie_10_20kwh.webp", quality:"verified_appearance", selectable:true },

  { id:"solar_zone.generic", asset_type:"solar_zone", label:"Solar zone", brand:"Generic", model:"PV zone", variant:"Physical panel group", profile_patterns:["energy.solar_zone."], package_path:"energy/solar_zone_generic.webp", quality:"generic_family", selectable:true },

  { id:"solar_panel.sunpower_x21_335_blk", asset_type:"solar_panel", label:"SunPower SPR-X21-335-BLK", brand:"SunPower", model:"SPR-X21-335-BLK", variant:"X21 Black · 335 W", profile_patterns:[], package_path:"energy/sunpower_spr_x21_335_blk.webp", quality:"verified_product", selectable:true },
  { id:"solar_panel.jinkosolar_jkm435n_54hl4r", asset_type:"solar_panel", label:"JinkoSolar JKM435N-54HL4R", brand:"JinkoSolar", model:"JKM435N-54HL4R", variant:"Tiger Neo N-Type · 435 W", profile_patterns:[], package_path:"energy/jinkosolar_jkm435n_54hl4r.webp", quality:"verified_product", selectable:true },

  { id:"solar_inverter.solaredge_rwb_10k", asset_type:"solar_inverter", label:"SolarEdge Home Hub 10 kW", brand:"SolarEdge", model:"SE10K-RWB48", variant:"10 kW", profile_patterns:["solaredge_home_hub_10k"], package_path:"energy/solaredge_rwb_10k.webp", quality:"verified_appearance", selectable:true },
  { id:"solar_inverter.solaredge_rws_8k", asset_type:"solar_inverter", label:"SolarEdge StorEdge 8 kW", brand:"SolarEdge", model:"SE8K-RWS", variant:"8 kW", profile_patterns:["solaredge_rws_8k"], package_path:"energy/solaredge_rws_8k.webp", quality:"verified_product", selectable:true },
  { id:"solar_inverter.solaredge_se7k", asset_type:"solar_inverter", label:"SolarEdge Three Phase 7 kW", brand:"SolarEdge", model:"SE7K", variant:"Three phase", profile_patterns:["solaredge_three_phase_7k"], package_path:"energy/solaredge_se7k_rw0tebnn4.webp", quality:"verified_appearance", selectable:true },
  { id:"solar_inverter.huawei_sun2000_4_6ktl_l1", asset_type:"solar_inverter", label:"Huawei SUN2000-4.6KTL-L1", brand:"Huawei", model:"SUN2000-4.6KTL-L1", variant:"4.6 kW · single phase", profile_patterns:["huawei_sun2000_4_6ktl_l1"], package_path:"energy/huawei_sun2000_4_6ktl_l1.webp", quality:"verified_product", selectable:true },
  { id:"solar_inverter.sma_sunny_boy_5", asset_type:"solar_inverter", label:"SMA Sunny Boy 5.0", brand:"SMA", model:"SB5.0-1AV-41", variant:"5.0 kW · single phase", profile_patterns:["sma_sunny_boy_5_0_sb5_0_1av_41"], package_path:"energy/sma_sunny_boy_5_0_sb5_0_1av_41.webp", quality:"verified_product", selectable:true },
  { id:"solar_inverter.sma_sunny_tripower_7000tl", asset_type:"solar_inverter", label:"SMA Sunny Tripower 7000TL", brand:"SMA", model:"STP 7000TL-20", variant:"7.0 kW · three phase", profile_patterns:["sma_sunny_tripower_7000tl_20"], package_path:"energy/sma_sunny_tripower_7000tl_20.webp", quality:"verified_product", selectable:true },

  { id:"solar_optimizer.solaredge_s500b", asset_type:"solar_optimizer", label:"SolarEdge Power Optimizer S500B", brand:"SolarEdge", model:"S500B-1GM4MRM-NA02", variant:"Power Optimizer", profile_patterns:[], package_path:"energy/solaredge_s500b_optimizer.webp", quality:"verified_product", selectable:true },

  { id:"backup_interface.solaredge_3phase", asset_type:"backup_interface", label:"SolarEdge Home Backup Interface 3 Phase", brand:"SolarEdge", model:"BI-NEUNU-3P-01", variant:"Three phase", profile_patterns:[], package_path:"energy/solaredge_backup_interface_3phase.webp", quality:"verified_appearance", selectable:true },

  { id:"gas_meter.flonidan_uniflo_g4", asset_type:"gas_meter", label:"FLONIDAN UniFlo G4", brand:"FLONIDAN", model:"UniFlo G4", variant:"Smart diaphragm gas meter", profile_patterns:["flonidan_uniflo_g4"], package_path:"energy/flonidan_uniflo_g4srtv.webp", quality:"verified_appearance", selectable:true },

  { id:"grid_meter.sagemcom_t211_d3", asset_type:"grid_meter", label:"Sagemcom T211-D3", brand:"Sagemcom", model:"T211-D3", variant:"Electricity meter", profile_patterns:[], package_path:"energy/sagemcom_t211_d3.webp", quality:"verified_appearance", selectable:true }
]);

function rhiEnergyVisualCatalog() {
  return RHI_ENERGY_LOGICAL_VISUALS.map(row => ({ ...row }));
}

function rhiEnergyVisualCatalogForType(assetType = "") {
  const type = String(assetType || "").trim().toLowerCase();
  return rhiEnergyVisualCatalog().filter(row => row.asset_type === type && row.selectable !== false);
}

function rhiEnergyVisualBrandsForType(assetType = "") {
  return [...new Set(rhiEnergyVisualCatalogForType(assetType)
    .map(row => String(row.brand || "").trim())
    .filter(Boolean))]
    .sort((a, b) => a.localeCompare(b));
}

function rhiEnergyVisualRef(entryOrId = "") {
  const id = typeof entryOrId === "object" ? String(entryOrId?.id || "") : String(entryOrId || "");
  return id ? `energy.logical.${id}` : "";
}

function rhiEnergyVisualEntryFromRef(visualRef = "") {
  const ref = String(visualRef || "").trim();
  if (!ref.startsWith("energy.logical.")) return null;
  const id = ref.slice("energy.logical.".length);
  return RHI_ENERGY_LOGICAL_VISUALS.find(row => row.id === id) || null;
}

function rhiEnergyVisualEntryMatchesAsset(entry = {}, asset = {}) {
  const assetType = String(asset.asset_type || asset.object_class || "").trim().toLowerCase();
  if (!assetType || entry.asset_type !== assetType) return false;
  const profileId = String(asset.profile_id || asset.raw?.profile_id || "").trim();
  return (entry.profile_patterns || []).some(pattern => profileId === pattern || profileId.startsWith(pattern));
}

function rhiEnergyDefaultVisualEntry(asset = {}) {
  const assetType = String(asset.asset_type || asset.object_class || "").trim().toLowerCase();
  const candidates = rhiEnergyVisualCatalogForType(assetType);
  if (!candidates.length) return null;
  return candidates.find(entry => rhiEnergyVisualEntryMatchesAsset(entry, asset))
    || candidates[0]
    || null;
}
