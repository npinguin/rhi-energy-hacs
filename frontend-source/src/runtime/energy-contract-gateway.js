// Backend-access boundary. Native canonical property/object/metric/command
// entities are indexed by published markers, never by guessed HA entity IDs.
function createEnergyContractGateway(host) {
  const state=id=>host?.rawState?.(id) || host?.hass?.states?.[id] || null;
  const attrs=id=>state(id)?.attributes || {};
  return Object.freeze({
    host,
    state,attrs,
    canonicalProperty:(assetId,propertyKey)=>host?.canonicalIndex?.row(assetId,propertyKey) || null,
    canonicalObject:assetId=>host?.canonicalIndex?.object(assetId) || null,
    nativeMetric:key=>host?.nativeMetric?.(key) || readNativeEnergyMetric(host?.hass || {},key),
    nativePlanningTotals:id=>host?.nativePlanningTotals?.(id) || readNativeEnergyPlanningTotals(host?.hass || {},id),
    nativePlanningHorizon:id=>host?.nativePlanningHorizon?.(id) || {available:false,details:null}
  });
}
