// Canonical current-energy view model. Literal contract keys and direction
// semantics are confined to this adapter so screen renderers cannot drift.
function readTypedPropertyContract(gateway, interfaceKey, propertyKey) {
  // Canonical property entities are the only authority for live current values.
  // No Public V2 or source-integration fallback. Ambiguity is a contract gap.
  const index = gateway.host?.canonicalIndex;
  const expectedClass = ({
    'battery.power_kw':'battery_system',
    'battery.soc_pct':'battery_system',
    'battery.capacity_kwh':'battery_system',
    'battery.available_kwh':'battery_system',
    'battery.state':'battery_system',
    'battery.reserve_target_pct':'battery_system',
    'solar.power_kw':'solar_production',
    'grid.net_power_kw':'grid_connection',
    'grid_import.power_kw':'grid_connection',
    'grid_export.power_kw':'grid_connection',
    'grid.flow_direction':'grid_connection',
    'site_consumption.power_kw':'site_consumption',
    'home_consumption.power_kw':'home_consumption',
    'flexible_loads.power_kw':'flexible_loads',
    'flexible_loads.attributed_power_kw':'flexible_loads'
  })[propertyKey];
  const candidates = expectedClass
    ? (index?.rowsForProperty?.(propertyKey) || []).filter(row=>row.logical_object_class===expectedClass)
    : [];
  const usable = candidates.filter(row => row?.availability === 'AVAILABLE' && row?.value !== null && row?.value !== undefined);
  const valid = candidates.length === 1 && usable.length === 1 ? usable[0] : null;
  const projected = valid ? {
    raw:valid,value:valid.value,status:valid.availability,quality:valid.quality,reason:valid.reason,
    source:valid.entity_id
  } : {
    raw:{},value:null,status:'UNAVAILABLE',quality:'CONTRACT_GAP',
    reason:candidates.length > 1 ? 'ambiguous_canonical_property' : 'canonical_property_not_available',
    source:null
  };
  return Object.freeze({
    envelope:{source:'RHI_ENERGY_CANONICAL_PROPERTY_V2'},
    row:projected.raw || {},
    value:projected.value,
    number:asNumber(projected.value),
    text:String(projected.value ?? ''),
    health:String(projected.status || projected.state || 'UNAVAILABLE').toUpperCase(),
    quality:String(projected.quality || ''),
    reason:String(projected.reason || ''),
    source:projected.source
  });
}

function canonicalBatteryState(value) {
  const state = String(value || '').trim().toLowerCase();
  if (['charging','charge'].includes(state)) return 'charging';
  if (['discharging','discharge'].includes(state)) return 'discharging';
  if (['idle','standby','available','ready'].includes(state)) return 'idle';
  return state || 'unavailable';
}

function createBatteryCurrentFlowViewModel(gateway) {
  const signed = readTypedPropertyContract(gateway, 'battery', 'battery.power_kw');
  const stateProperty = readTypedPropertyContract(gateway, 'battery', 'battery.state');
  const soc = readTypedPropertyContract(gateway, 'battery', 'battery.soc_pct');
  const available = readTypedPropertyContract(gateway, 'battery', 'battery.available_kwh');
  const capacity = readTypedPropertyContract(gateway, 'battery', 'battery.capacity_kwh');
  const reserve = readTypedPropertyContract(gateway, 'battery', 'battery.reserve_target_pct');
  const state = canonicalBatteryState(stateProperty.value);
  const signedReady = signed.health === 'AVAILABLE' && signed.number !== null;
  const projectedPowerKw = signedReady ? Math.abs(signed.number) : null;
  // Energy owns canonical sign (+ discharge, - charge) and its derived state.
  // Contradictory, missing or stale direction is NOT a measured zero.
  const matchesCharge = signedReady && state === 'charging' && signed.number < -0.05;
  const matchesDischarge = signedReady && state === 'discharging' && signed.number > 0.05;
  const matchesIdle = signedReady && state === 'idle' && Math.abs(signed.number) <= 0.05;
  const direction = matchesCharge ? 'into_storage'
    : matchesDischarge ? 'out_of_storage'
    : matchesIdle ? 'idle' : 'unknown';
  const displayPowerKw = direction === 'unknown' ? null : projectedPowerKw;
  const label = direction === 'into_storage' ? 'Charging'
    : direction === 'out_of_storage' ? 'Discharging'
    : direction === 'idle' ? 'Idle' : 'Unavailable';
  const detail = direction === 'into_storage' ? 'Charging from Home Bus'
    : direction === 'out_of_storage' ? 'Supplying the Home Bus'
    : direction === 'idle' ? 'No active battery flow'
    : 'Battery charge/discharge direction is unavailable or inconsistent';
  const contradictory = signedReady && ['charging','discharging','idle'].includes(state) && direction === 'unknown';
  const reason = contradictory ? 'battery_state_power_conflict'
    : signedReady && state === 'unavailable' ? 'battery_direction_not_available'
    : String(firstDefined(stateProperty.reason, signed.reason, 'battery_flow_unavailable'));
  const health = direction === 'unknown' ? 'UNAVAILABLE' : 'OK';
  return Object.freeze({
    state,health,reason,
    signedPowerKw:signed.number,
    chargePowerKw:direction === 'into_storage' ? projectedPowerKw
      : direction === 'out_of_storage' || direction === 'idle' ? 0 : null,
    dischargePowerKw:direction === 'out_of_storage' ? projectedPowerKw
      : direction === 'into_storage' || direction === 'idle' ? 0 : null,
    displayPowerKw,
    signedFlowKw:direction === 'unknown' ? null : direction === 'idle' ? 0 : signed.number,
    direction,label,detail,
    flowRole:direction === 'out_of_storage' ? 'producer' : direction === 'into_storage' ? 'consumer' : 'inactive',
    uxVisible:displayPowerKw !== null,
    socPct:soc.number,
    availableKwh:available.number,
    capacityKwh:capacity.number,
    reserveTargetPct:reserve.number,
    valueAvailable:displayPowerKw !== null
  });
}

function createGridCurrentFlowViewModel(gateway) {
  const netPower = readTypedPropertyContract(gateway, 'grid', 'grid.net_power_kw');
  const importPower = readTypedPropertyContract(gateway, 'grid', 'grid_import.power_kw');
  const exportPower = readTypedPropertyContract(gateway, 'grid', 'grid_export.power_kw');
  const directionProperty = readTypedPropertyContract(gateway, 'grid', 'grid.flow_direction');
  const rawDirection = String(firstDefined(directionProperty.value, '') || '').toLowerCase();
  const direction = /export/.test(rawDirection) ? 'exporting' : /import/.test(rawDirection) ? 'importing' : /balanc|idle|none/.test(rawDirection) ? 'balanced' : 'unknown';
  // A net reading without producer-owned flow direction is diagnostic truth,
  // not a trustworthy Grid Import, Grid Export or confirmed zero state.
  const consistent = direction === 'importing'
    ? importPower.number !== null && importPower.number >= 0
      && (netPower.number === null || netPower.number >= 0)
    : direction === 'exporting'
      ? exportPower.number !== null && exportPower.number >= 0
        && (netPower.number === null || netPower.number <= 0)
      : direction === 'balanced'
        ? netPower.number !== null && Math.abs(netPower.number) <= 0.05
        : false;
  const effectiveDirection = consistent ? direction : 'unknown';
  const displayPowerKw = effectiveDirection === 'exporting' ? exportPower.number
    : effectiveDirection === 'importing' ? importPower.number
    : effectiveDirection === 'balanced' ? 0 : null;
  return Object.freeze({
    netPowerKw:netPower.number,
    importPowerKw:importPower.number,
    exportPowerKw:exportPower.number,
    displayPowerKw,
    direction:effectiveDirection,
    reason:effectiveDirection === 'unknown' ? 'grid_direction_not_available_or_inconsistent' : '',
    label:effectiveDirection === 'exporting' ? 'Exporting'
      : effectiveDirection === 'importing' ? 'Importing'
      : effectiveDirection === 'balanced' ? 'Balanced' : 'Unavailable'
  });
}

function createSolarCurrentViewModel(gateway) {
  const power = readTypedPropertyContract(gateway, 'solar', 'solar.power_kw');
  return Object.freeze({ powerKw:power.number, health:power.health, reason:power.reason });
}

function createCurrentEnergyViewModel(gateway) {
  return Object.freeze({
    battery:createBatteryCurrentFlowViewModel(gateway),
    grid:createGridCurrentFlowViewModel(gateway),
    solar:createSolarCurrentViewModel(gateway),
    consumption:readLiveConsumptionContract(gateway)
  });
}
