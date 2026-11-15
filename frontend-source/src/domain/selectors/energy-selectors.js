// Pure Energy product selectors. These functions know the normalized Energy V2
// shape; screens must not know Home Assistant entity ids or raw contract paths.
function selectEnergyAsset(store, assetId) {
  return createEnergyAssetProjection(store, assetId);
}

function selectEnergyOverview(store) {
  const row=store?.overview && typeof store.overview === 'object' ? store.overview : {};
  const home=store?.currentField?.('home_consumption.power_kw');
  const primary=home?.resolved===true ? {value:home.value,unit:home.unit || 'kW',
    property_key:'home_consumption.power_kw',source:'RHI_ENERGY_CANONICAL_PROPERTY_V2'} : null;
  return Object.freeze({
    available:store?.available === true,
    status:String(row.status || row.product_status || row.state ||
      (store?.available === true ? 'AVAILABLE':'UNAVAILABLE')),
    primary:row.primary || row.primary_metric || primary,
    summary:row.summary || {},flow:row.flow || {},
    conclusions:Array.isArray(row.conclusions) ? row.conclusions : [],
    reason:String(row.reason || row.product_reason ||
      (store?.available ? '':'canonical_product_unavailable')),
    raw:row,core:store?.core || {},
    source:'RHI_ENERGY_CANONICAL_PROPERTY_V2'
  });
}

function selectEnergyPlanning(store, horizon='D0') {
  const id=String(horizon || 'D0').toUpperCase();
  const planning=store?.planning && typeof store.planning === 'object' ? store.planning : {};
  const horizons=planning.horizons && typeof planning.horizons === 'object' ? planning.horizons : {};
  const row=horizons[id] && typeof horizons[id] === 'object' ? horizons[id] : {};
  return Object.freeze({
    available:store?.available === true && Object.keys(row).length > 0,
    horizon_id:id,
    horizon:row,
    summary:row,
    lane_totals:Object.freeze({
      required_kwh:row.required_kwh ?? null,
      planned_kwh:row.planned_kwh ?? null,
      executed_kwh:row.executed_kwh ?? null,
      still_to_plan_kwh:row.still_to_plan_kwh ?? null,
      flexible_required_kwh:row.flexible_required_kwh ?? null,
      flexible_planned_kwh:row.flexible_planned_kwh ?? null,
      flexible_executed_kwh:row.flexible_executed_kwh ?? null,
      flexible_still_to_plan_kwh:row.flexible_still_to_plan_kwh ?? null
    }),
    buckets:Array.isArray(row.buckets) ? row.buckets : [],
    flexible_plan:{},
    planning_objects:Array.isArray(store?.planningObjects) ? store.planningObjects : [],
    source:'RHI_ENERGY_CANONICAL_PROPERTY_V2.planning.horizons'
  });
}

function selectEnergyConfigurationProperties(store, scope) {
  const kind=String(scope || '').toLowerCase();
  const configuration=store?.configuration && typeof store.configuration === 'object' ? store.configuration : {};
  const section=configuration[kind] && typeof configuration[kind] === 'object' ? configuration[kind] : {};
  if (kind === 'strategy') {
    const configured=section.configured && typeof section.configured === 'object' ? section.configured : {};
    const effective=section.effective && typeof section.effective === 'object' ? section.effective : {};
    const rows=Array.isArray(configured.properties) ? configured.properties : [];
    const effectiveRows=Array.isArray(effective.properties) ? effective.properties : [];
    return Object.freeze({
      available:store?.available === true && configured.status !== 'UNAVAILABLE',
      scope:kind,
      properties:Object.freeze(rows.map(row=>Object.freeze({...row}))),
      effective_properties:Object.freeze(effectiveRows.map(row=>Object.freeze({...row}))),
      effective_state:String(effective.status || 'UNAVAILABLE'),
      effective_reason:String(effective.reason || ''),
      runtime_overrides:Object.freeze((Array.isArray(effective.runtime_overrides) ? effective.runtime_overrides : []).map(row=>Object.freeze({...row}))),
      source:'RHI_ENERGY_CANONICAL_PROPERTY_V2.configuration.strategy'
    });
  }
  const rows=Array.isArray(section.properties) ? section.properties : [];
  return Object.freeze({
    available:store?.available === true && Array.isArray(rows),
    scope:kind,
    properties:Object.freeze(rows.map(row=>Object.freeze({...row}))),
    effective_properties:Object.freeze([]),
    effective_state:String(section.availability || section.status || 'UNAVAILABLE'),
    effective_reason:String(section.reason || ''),
    source:`RHI_ENERGY_CANONICAL_PROPERTY_V2.configuration.${kind}`
  });
}

function selectEnergyStrategies(store) { return selectEnergyConfigurationProperties(store,'strategy'); }
function selectEnergyPricing(store) { return selectEnergyConfigurationProperties(store,'pricing'); }

function selectEnergyValue(store, period='today') {
  const accounting=store?.valueAccounting && typeof store.valueAccounting === 'object' ? store.valueAccounting : {};
  const id=String(period || accounting.selected_period_id || 'today').toLowerCase();
  const periods=accounting.periods && typeof accounting.periods === 'object' ? accounting.periods : {};
  const row=periods[id] && typeof periods[id] === 'object' ? periods[id] : {};
  const raw=row.net_financial_result_eur;
  const valid=row.available === true &&
    typeof raw === 'number' && Number.isFinite(raw);
  return Object.freeze({
    available:valid,
    period_id:id,
    value:row,
    net_financial_result_eur:valid ? raw : null,
    net_financial_result:valid ?
      Object.freeze({value:raw,period_id:id,actual_complete:row.actual_complete === true}) : {},
    quality:row.quality || 'UNKNOWN',actual_complete:row.actual_complete === true,
    reason:valid ? '' : row.reason || 'financial_period_evidence_unavailable',
    source:'rhi_energy.runtime/native_metering_period'
  });
}

function selectEnergyMetering(store, period='today') {
  const id=String(period || 'today').toLowerCase();
  return Object.freeze({
    available:false,
    partial:false,
    period_id:id,
    metrics:Object.freeze({}),
    reason:'canonical_period_energy_not_published',
    source:'RHI_ENERGY_CANONICAL_PROPERTY_V2'
  });
}

function selectEnergyActivity(store) {
  return Object.freeze({
    available:store?.available === true,
    rows:Object.freeze((Array.isArray(store?.activity) ? store.activity : []).map(row=>Object.freeze({...row}))),
    source:'RHI_ENERGY_CANONICAL_PROPERTY_V2.activity'
  });
}

function selectEnergyCommands(store, assetId='') {
  const wanted=String(assetId || '');
  const rows=(Array.isArray(store?.commands) ? store.commands : [])
    .filter(row=>!wanted || String(row.target_asset_id || '') === wanted)
    .map(row=>Object.freeze({...row}));
  return Object.freeze({
    available:store?.available === true,
    rows:Object.freeze(rows),
    source:'RHI_ENERGY_CANONICAL_PROPERTY_V2.commands'
  });
}

function selectEnergyCoverage(store) {
  const present=value => {
    if(Array.isArray(value)) return value.length > 0;
    return !!value && typeof value === 'object' && Object.keys(value).length > 0;
  };
  const capabilities=Object.freeze({
    core:present(store?.core) ? 'SUPPORTED' : 'UNAVAILABLE',
    assets:present(store?.objects) ? 'SUPPORTED' : 'UNAVAILABLE',
    relationships:Array.isArray(store?.relationships) ? 'SUPPORTED' : 'UNAVAILABLE',
    planning:present(store?.planning?.horizons) ? 'SUPPORTED' : 'UNAVAILABLE',
    pricing:present(store?.configuration?.pricing) ? 'SUPPORTED' : 'UNAVAILABLE',
    strategies:present(store?.configuration?.strategy) ? 'SUPPORTED' : 'UNAVAILABLE',
    commands:Array.isArray(store?.commands) ? 'SUPPORTED' : 'UNAVAILABLE',
    value_accounting:present(store?.valueAccounting) ? 'SUPPORTED' : 'UNAVAILABLE'
  });
  return Object.freeze({
    complete:Object.values(capabilities).every(value=>value === 'SUPPORTED'),
    capabilities,
    unsupported:Object.freeze(Object.entries(capabilities).filter(([,v])=>v!=='SUPPORTED').map(([k])=>k)),
    source:'RHI_ENERGY_CANONICAL_PROPERTY_V2.coverage'
  });
}
