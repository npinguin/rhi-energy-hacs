// Power Flow Card Plus adapter. Only canonical Energy property entities are permitted.
// The external card reads HA entity states; this adapter does not read HA states.
function buildRhiPowerFlowCardConfig(rt) {
  const index = rt?.canonicalIndex;
  const sensor = (key, kind) => {
    const rows = (index?.rowsForProperty?.(key) || []).filter(r => r.logical_object_class === kind);
    if (rows.length !== 1) return '';
    const r = rows[0];
    const id = String(r?.entity_id || '');
    const unit = String(r?.unit || r?.unit_of_measurement || r?.native_unit_of_measurement || '').toLowerCase();
    if (r.availability !== 'AVAILABLE' || !/^sensor\.[a-z0-9_]+$/.test(id)) return '';
    // Native card accepts W or kW; never pass percent, kWh or other measures.
    if (unit && unit !== 'w' && unit !== 'kw') return '';
    return id;
  };
  // SoC is a percentage, never a power sensor. Its use is optional and must
  // not create a battery flow node without direction-safe energy measurements.
  const socSensor = () => {
    const rows = (index?.rowsForProperty?.('battery.soc_pct') || [])
      .filter(r => r.logical_object_class === 'battery_system');
    if (rows.length !== 1) return '';
    const row = rows[0];
    const id = String(row.entity_id || '');
    const unit = String(row.unit || row.unit_of_measurement || row.native_unit_of_measurement || '').toLowerCase();
    return row.availability === 'AVAILABLE' && /^sensor\.[a-z0-9_]+$/.test(id)
      && (!unit || unit === '%') ? id : '';
  };
  const entities = {};
  const importId = sensor('grid_import.power_kw', 'grid_connection');
  const exportId = sensor('grid_export.power_kw', 'grid_connection');
  if (importId || exportId) {
    const split = {};
    if (importId) split.consumption = importId;
    if (exportId) split.production = exportId;
    entities.grid = { entity:split, display_state:'one_way' };
  }
  const solarId = sensor('solar.power_kw', 'solar_production');
  if (solarId) entities.solar = {entity:solarId};
  // The Power Flow Card Plus battery consumes explicit *directional* sensors:
  // consumption = charging the storage; production = discharging storage.
  // battery.power_kw by itself does not publish a compatible signed convention.
  // A partial, ambiguous or stale pair must not animate a misleading arrow.
  // Directional values are producer-owned non-negative magnitudes.
  // Check actual canonical value/quality as well as identity: a stale, negative
  // or non-numeric publication must never animate a physical flow.
  const directionalSensor = key => {
    const id = sensor(key, 'battery_system');
    if (!id) return '';
    const row = (index.rowsForProperty(key) || [])[0];
    const raw = row?.value;
    const unit = String(row?.unit || row?.unit_of_measurement || row?.native_unit_of_measurement || '').toLowerCase();
    const quality = String(row?.quality || '').toUpperCase();
    if (!['w','kw'].includes(unit) || raw === null || raw === undefined ||
        typeof raw === 'boolean' || String(raw).trim() === '' ||
        !Number.isFinite(Number(raw)) || Number(raw) < 0 ||
        ['STALE','INVALID','UNKNOWN'].includes(quality)) return '';
    return id;
  };
  const batteryChargeId = directionalSensor('battery.charge_power_kw');
  const batteryDischargeId = directionalSensor('battery.discharge_power_kw');
  if (batteryChargeId && batteryDischargeId && batteryChargeId !== batteryDischargeId) {
    entities.battery = {
      entity:{consumption:batteryChargeId, production:batteryDischargeId},
      // Multiple physical units may charge and discharge simultaneously.
      // one_way hides a real direction in that case; two_way preserves both.
      display_state:'two_way', name:'Home Battery'
    };
    const socId = socSensor();
    if (socId) entities.battery.state_of_charge = socId;
  }
  // Never use battery.power_kw alone: its direction is not card-compatible
  // without producer-published positive/negative convention metadata.
  // Site Consumption is a producer-owned native Energy metric, not a logical
  // object of class site_consumption (the logical inventory has no such class).
  // Do not substitute Home Consumption: it excludes flexible loads and battery
  // charging, whereas this card needs the full measured site balance.
  const site = rt?.nativeMetric?.('site_consumption_power_kw');
  const siteId = String(site?.entity_id || '');
  const siteUnit = String(site?.unit || '').toLowerCase();
  // A unique available native metric_key is the only supported route.
  // The metric reader rejects duplicates, stale or invalid values.
  if (site?.available !== true || !/^sensor\.[a-z0-9_]+$/.test(siteId) ||
      !['w','kw'].includes(siteUnit)) return null;
  entities.home = {entity:siteId, override_state:true, name:'Site consumption'};
  // Individual flexible consumers belong below the physical supply flow,
  // where Energy can show true consumer identity, energy needed, actual vs
  // requested power and the published charging relationship. Do not render
  // the same load inside the flow diagram or expose charger infrastructure
  // as another consumption node.
  if (!entities.grid && !entities.solar) return null;
  return {
    type:'custom:power-flow-card-plus',
    entities,
    clickable_entities:true,
    title:'Live energy flow'
  };
}
