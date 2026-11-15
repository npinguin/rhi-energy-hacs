// Current Energy consumption is read only from backend-owned canonical property
// entities. No Public V2, source-provider, aggregate or derived-power fallback.
function readLiveConsumptionContract(gateway) {
  // Energy publishes Site Consumption as a *native metric* on energy_site.
  // There is no canonical logical object of class site_consumption: reading a
  // property for that imaginary class always produced '—' despite 1.865 kW
  // of valid producer-owned site balance in runtime diagnostics.
  const siteMetric=readNativeEnergyMetric(gateway?.host?.hass || {},'site_consumption_power_kw');
  const site=Object.freeze({
    number:siteMetric.available === true ? Number(siteMetric.value) : null,
    health:siteMetric.available === true ? 'AVAILABLE' : 'UNAVAILABLE',
    reason:siteMetric.reason || 'native_site_consumption_unavailable'
  });
  // Home consumption is published as a dedicated native HA metric by Energy.
  // Do not treat a second property-path guess as fallback or recompute it from
  // solar/grid/battery flows. The producer's availability is authoritative.
  const homeMetric=readNativeEnergyMetric(gateway?.host?.hass || {},'home_consumption_power_kw');
  const home=Object.freeze({
    number:homeMetric.available ? Number(homeMetric.value) : null,
    health:homeMetric.available ? 'AVAILABLE' : 'UNAVAILABLE',
    reason:homeMetric.reason || ''
  });
  // Flexible power is independently published by the backend, if present.
  // This aggregate must also come from Energy-owned evidence, never a
  // frontend sum over charger objects, vehicles or requested setpoints.
  const flexibleMetric=readNativeEnergyMetric(gateway?.host?.hass || {},'flexible_loads_power_kw');
  const flexible=Object.freeze({
    number:flexibleMetric.available === true ? Number(flexibleMetric.value) : null,
    health:flexibleMetric.available === true ? 'AVAILABLE' : 'UNAVAILABLE',
    reason:flexibleMetric.reason || 'native_flexible_loads_power_unavailable'
  });
  const attributed=Object.freeze({number:null,health:'UNAVAILABLE',reason:'attribution_metric_not_published'});
  return Object.freeze({
    envelope:Object.freeze({source:'RHI_ENERGY_CANONICAL_PROPERTY_V2'}),
    siteConsumptionKw:site.number,
    homeConsumptionKw:home.number,
    flexibleLoadsKw:flexible.number,
    attributedFlexibleLoadsKw:attributed.number,
    // Asset participation must come from a separate native participant contract.
    // Empty means no participant evidence published, not zero participation.
    flexibleLoadContributors:Object.freeze([]),
    siteStatus:site.health,
    homeStatus:home.health,
    flexibleStatus:flexible.health,
    siteReason:site.reason,
    homeReason:home.reason,
    flexibleReason:flexible.reason,
    available:[site,home,flexible].some(row=>row.health==='AVAILABLE'),
    source:'RHI_ENERGY_CANONICAL_PROPERTY_V2'
  });
}
