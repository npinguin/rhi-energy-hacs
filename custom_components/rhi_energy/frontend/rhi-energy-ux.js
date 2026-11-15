(() => {
  const UX_VERSION = 'R0.15.142';
  const RELEASE_ENTITY = 'sensor.rhi_energy_release';
  // ---- src/runtime/public-interface-registry.js ----
// Native Energy publication is discovered by exact canonical contract markers.
// Release metadata is diagnostic only; there is no aggregate product sensor.
const UX_INTERFACES=Object.freeze({release:'sensor.rhi_energy_release'});

// ---- src/runtime/canonical-property-index.js ----
// Canonical Energy property index.
//
// RHI_ENERGY_CANONICAL_PROPERTY_V2 property entities are the product-property
// truth. Missing canonical properties are contract gaps and fail closed.
//
// This index deliberately uses backend-published presentation metadata literally.
// It never derives family/role/surface from property_key or object_class.
const RHI_ENERGY_CANONICAL_PROPERTY_V2 = 'RHI_ENERGY_CANONICAL_PROPERTY_V2';
// Logical object status is a separate canonical HA entity. Treat it as the
// sole authority for identity, parentage, profile and presentation; properties
// supply values but must not invent topology or missing physical assets.
const RHI_ENERGY_CANONICAL_OBJECT_V2 = 'RHI_ENERGY_CANONICAL_OBJECT_V2';
function canonicalEnergyObjectRow(entityId,state) {
  const a=state?.attributes || {};
  if(a.canonical_contract !== RHI_ENERGY_CANONICAL_OBJECT_V2) return null;
  const assetId=String(a.asset_id || '').trim();
  const objectClass=String(a.logical_object_class || '').trim();
  if(!assetId || !objectClass) return null;
  return Object.freeze({
    asset_id:assetId,object_class:objectClass,asset_type:objectClass,
    logical_object_class:objectClass,entity_id:String(entityId),
    display_name:String(a.display_name || assetId),
    parent_asset_id:a.parent_asset_id || null,
    children:Object.freeze(Array.isArray(a.children) ? [...a.children] : []),
    canonical_path:Object.freeze(Array.isArray(a.canonical_path) ? [...a.canonical_path] : []),
    canonical_depth:a.canonical_depth ?? null,
    canonical_root:a.canonical_root ?? null,
    projection_role:String(a.projection_role || ''),
    ha_materialization:a.ha_materialization === true,
    runtime_truth:a.runtime_truth === true,
    profile_id:String(a.profile_id || ''),
    visual_ref:String(a.visual_ref || ''),
    configured_visual_ref:String(a.configured_visual_ref || ''),
    appearance_editable:a.appearance_editable === true,
    appearance_owner:a.appearance_owner || null,
    // Preserve producer-owned object lifecycle and readiness where published.
    // Absence is unknown, never an implicit participating/plan-ready state.
    participation_state:a.participation_state ?? null,
    operating_state:a.operating_state ?? null,
    availability_state:a.availability_state ?? null,
    planning_input_ready:a.planning_input_ready === true ? true : a.planning_input_ready === false ? false : null,
    planning_input_reason:a.planning_input_reason ?? null,
    source_asset_kind:a.source_asset_kind ?? null,
    infrastructure_only:a.infrastructure_only === true,
    health:String(a.health || state?.state || 'UNKNOWN'),
    availability:String(a.availability || 'UNAVAILABLE'),
    source_devices:Object.freeze(Array.isArray(a.source_devices) ? [...a.source_devices] : []),
    source_device_ids:Object.freeze(Array.isArray(a.source_device_ids) ? [...a.source_device_ids] : []),
    selected_device_ids:Object.freeze(Array.isArray(a.selected_device_ids) ? [...a.selected_device_ids] : [])
  });
}


function normalizeCanonicalEnergyAvailability(state = null, attributes = {}) {
  // Availability and quality are distinct backend dimensions. A quality label
  // such as CANONICAL is not an availability state; neither is RESOLVED.
  const explicit = String(attributes.availability ?? '').trim().toUpperCase();
  if (['AVAILABLE','UNAVAILABLE','STALE','INVALID','UNKNOWN'].includes(explicit))
    return explicit === 'AVAILABLE' ? 'AVAILABLE' : 'UNAVAILABLE';
  // Unknown explicit availability is not proof of a valid value.
  if (explicit) return 'UNAVAILABLE';
  const raw = String(state?.state ?? '').trim().toLowerCase();
  return ['unknown','unavailable','none','null',''].includes(raw) ? 'UNAVAILABLE' : 'AVAILABLE';
}

function canonicalEnergyPropertyRow(entityId, state) {
  const attributes = state?.attributes || {};
  if (String(attributes.canonical_contract || '') !== RHI_ENERGY_CANONICAL_PROPERTY_V2) return null;

  const assetId = String(attributes.asset_id || '').trim();
  const objectClass = String(attributes.logical_object_class || attributes.object_class || '').trim();
  const propertyKey = String(attributes.property_key || '').trim();
  if (!assetId || !objectClass || !propertyKey) return null;

  const family = String(attributes.presentation_family || '').trim();
  const role = String(attributes.presentation_role || '').trim();
  const surface = String(attributes.presentation_surface || '').trim();
  const primary = attributes.presentation_primary === true;
  const technical = attributes.presentation_technical === true;
  const presentationComplete = !!family && !!role && !!surface;

  const availability = normalizeCanonicalEnergyAvailability(state, attributes);
  const rawState = state?.state;
  // HA state and backend quality must both permit a product value. A stale,
  // invalid or unknown state cannot be made healthy by an AVAILABLE attribute.
  const invalidStates = new Set(['unknown','unavailable','none','null','']);
  const invalidQualities = new Set(['STALE','INVALID','UNKNOWN']);
  const rawInvalid = invalidStates.has(String(rawState ?? '').trim().toLowerCase());
  const publishedValue = Object.prototype.hasOwnProperty.call(attributes,'value') ? attributes.value : rawState;
  const invalidPublishedValue = publishedValue === null || publishedValue === undefined ||
    (typeof publishedValue === 'string' &&
      invalidStates.has(publishedValue.trim().toLowerCase()));
  const effectiveAvailability = rawInvalid || invalidPublishedValue ||
    invalidQualities.has(String(attributes.quality || '').toUpperCase())
    ? 'UNAVAILABLE' : availability;
  const value = effectiveAvailability === 'AVAILABLE' ? publishedValue : null;

  return Object.freeze({
    entity_id:String(entityId || ''),
    canonical_contract:RHI_ENERGY_CANONICAL_PROPERTY_V2,
    asset_id:assetId,
    logical_object_class:objectClass,
    object_class:objectClass,
    parent_asset_id:attributes.parent_asset_id || null,
    asset_display_name:String(attributes.asset_display_name || assetId),
    property_key:propertyKey,
    property_id:propertyKey,
    key:propertyKey,
    value,
    unit:String(attributes.unit ?? attributes.unit_of_measurement ?? ''),
    availability:effectiveAvailability,
    status:String(effectiveAvailability),
    quality:String(attributes.quality ?? ''),
    reason:String(attributes.reason ?? attributes.reason_code ?? ''),
    editable:attributes.editable === true,
    editor:attributes.editor || null,
    constraints:attributes.constraints || {},
    operation:attributes.operation || {},
    write_supported:attributes.write_supported === true,
    write:attributes.write || null,
    source:attributes.source || attributes.provenance || null,
    statistics_entity_id:String(attributes.statistics_entity_id || ''),
    history_entity_id:String(attributes.history_entity_id || ''),
    source_entity_id:String(attributes.source_entity_id || attributes.source?.entity_id || ''),
    source_device_path:String(attributes.source_device_path || ''),
    device_registry_id:String(attributes.device_registry_id || ''),
    integration_domain:String(attributes.integration_domain || ''),
    capability_ref:String(attributes.capability_ref || ''),
    presentation_family:family,
    presentation_role:role,
    presentation_surface:surface,
    presentation_primary:primary,
    presentation_technical:technical,
    presentation_complete:presentationComplete,
    display_name:String(attributes.friendly_name || attributes.display_name || state?.attributes?.friendly_name || propertyKey)
  });
}

class EnergyCanonicalPropertyIndex {
  constructor(hass = {}) {
    this.byEntity = new Map();
    this.byObject = new Map();
    this.objectStates = new Map();
    this.ambiguousObjects = new Set();
    this.byAssetAndKey = new Map();
    this.ambiguousAssetKeys = new Set();
    this.byPropertyKey = new Map();
    this.bySurface = new Map();
    this.byFamily = new Map();
    this.stateRefs = new Map();
    this._stateCount = 0;
    this._hassRef = null;
    this.discover(hass);
  }

  _index(row, stateRef) {
    if (!row) return;
    this.byEntity.set(row.entity_id,row);
    const compound = `${row.asset_id}::${row.property_key}`;
    if (this.byAssetAndKey.has(compound)) this.ambiguousAssetKeys.add(compound);
    else this.byAssetAndKey.set(compound,row);
    if (!this.byPropertyKey.has(row.property_key)) this.byPropertyKey.set(row.property_key,[]);
    this.byPropertyKey.get(row.property_key).push(row);
    if (!this.bySurface.has(row.presentation_surface)) this.bySurface.set(row.presentation_surface,[]);
    this.bySurface.get(row.presentation_surface).push(row);
    if (!this.byFamily.has(row.presentation_family)) this.byFamily.set(row.presentation_family,[]);
    this.byFamily.get(row.presentation_family).push(row);
    this.stateRefs.set(row.entity_id,stateRef);
  }

  discover(hass = {}) {
    this.byEntity.clear();
    this.byObject.clear();
    this.objectStates.clear();
    this.ambiguousObjects.clear();
    this.byAssetAndKey.clear();
    this.ambiguousAssetKeys.clear();
    this.byPropertyKey.clear();
    this.bySurface.clear();
    this.byFamily.clear();
    this.stateRefs.clear();
    const states = hass?.states || {};
    this._hassRef = hass;
    this._stateCount = Object.keys(states).length;
    for (const [entityId,state] of Object.entries(states)) {
      this._index(canonicalEnergyPropertyRow(entityId,state),state);
      const object=canonicalEnergyObjectRow(entityId,state);
      if(object){
        if(this.byObject.has(object.asset_id)) this.ambiguousObjects.add(object.asset_id);
        else this.byObject.set(object.asset_id,object);
        this.objectStates.set(entityId,state);
      }
    }
    return this;
  }

  refresh(hass = {}) {
    const states = hass?.states || {};
    // Entity replacement can preserve the total HA state count; membership must
    // be checked explicitly or stale canonical rows remain visible.
    const objectChanged=[...this.objectStates.entries()].some(([id,previous])=>states[id] !== previous) ||
      Object.entries(states).some(([id,state]) => !this.objectStates.has(id) && canonicalEnergyObjectRow(id,state) !== null);
    const membershipChanged = [...this.stateRefs.keys()].some(id => !Object.prototype.hasOwnProperty.call(states,id)) ||
      Object.entries(states).some(([id,state]) =>
        !this.stateRefs.has(id) && canonicalEnergyPropertyRow(id,state) !== null);
    if (Object.keys(states).length !== this._stateCount || membershipChanged || objectChanged) {
      const before = new Map(this.stateRefs);
      const priorObjects=new Map(this.objectStates);
      this.discover(hass);
      const changed = new Set();
      for (const [id,ref] of this.stateRefs.entries())
        if (!before.has(id) || before.get(id) !== ref) changed.add(id);
      for (const id of before.keys()) if (!this.stateRefs.has(id)) changed.add(id);
      for(const [id,state] of this.objectStates) if(priorObjects.get(id) !== state) changed.add(id);
      for(const id of priorObjects.keys()) if(!this.objectStates.has(id)) changed.add(id);
      return changed;
    }
    // Decide whether a full rebuild is needed before mutating any secondary
    // index. A metadata change in a later entity must not leave earlier rows
    // partially updated, or omit their changes from the invalidation set.
    const changed = new Set();
    let rebuild = false;
    const updates = [];
    for (const [entityId,previous] of this.stateRefs.entries()) {
      const current = states[entityId];
      if (current === previous) continue;
      changed.add(entityId);
      const row = canonicalEnergyPropertyRow(entityId,current);
      const before = this.byEntity.get(entityId);
      if (!row || !before ||
          this.ambiguousAssetKeys.has(`${before.asset_id}::${before.property_key}`) ||
          row.asset_id !== before.asset_id ||
          row.property_key !== before.property_key ||
          row.logical_object_class !== before.logical_object_class ||
          row.presentation_surface !== before.presentation_surface ||
          row.presentation_family !== before.presentation_family ||
          row.presentation_role !== before.presentation_role ||
          row.presentation_primary !== before.presentation_primary ||
          row.presentation_technical !== before.presentation_technical) rebuild = true;
      updates.push([entityId,current,row]);
    }
    if (rebuild) {
      this.discover(hass);
      return changed;
    }
    for (const [entityId,current,row] of updates) {
      this.byEntity.set(entityId,row);
      this.byAssetAndKey.set(`${row.asset_id}::${row.property_key}`,row);
      this.byPropertyKey.set(row.property_key,(this.byPropertyKey.get(row.property_key)||[]).map(candidate=>candidate.entity_id===entityId?row:candidate));
      this.bySurface.set(row.presentation_surface,(this.bySurface.get(row.presentation_surface)||[]).map(candidate=>candidate.entity_id===entityId?row:candidate));
      this.byFamily.set(row.presentation_family,(this.byFamily.get(row.presentation_family)||[]).map(candidate=>candidate.entity_id===entityId?row:candidate));
      this.stateRefs.set(entityId,current);
    }
    this._hassRef = hass;
    return changed;
  }

  changedRows(entityIds = []) {
    return [...entityIds].map(id=>this.byEntity.get(id)).filter(Boolean);
  }
  // Object status and product properties are joined only by exact canonical ID.
  object(assetId){
    const id=String(assetId || '');
    return this.ambiguousObjects.has(id) ? null : (this.byObject.get(id) || null);
  }
  objectRows(){return [...this.byObject.values()].filter(row=>!this.ambiguousObjects.has(row.asset_id));}
  objectEntityIds(){return [...this.objectStates.keys()];}

  uniqueProductRows() {
    // Property keys describe semantics, not globally unique physical assets.
    // Two batteries may both publish battery.soc_pct; only a duplicate for
    // the same asset/property pair is ambiguous and must fail closed.
    return [...this.byEntity.values()].filter(row =>
      !this.ambiguousAssetKeys.has(`${row.asset_id}::${row.property_key}`) &&
      row.presentation_complete === true && row.presentation_technical !== true);
  }

  hasProductTruthForSurfaces(surfaces = []) {
    const wanted = new Set((surfaces || []).map(String));
    if (!wanted.size) return false;
    return [...this.byEntity.values()].some(row=>
      row.presentation_complete === true &&
      row.presentation_technical !== true &&
      !this.ambiguousAssetKeys.has(`${row.asset_id}::${row.property_key}`) &&
      wanted.has(row.presentation_surface)
    );
  }

  affectedComponents(entityIds = []) {
    const propertyChanges=this.changedRows(entityIds).map(row=>Object.freeze({
      entity_id:row.entity_id,
      asset_id:row.asset_id,
      property_key:row.property_key,
      surface:row.presentation_surface,
      role:row.presentation_role,
      family:row.presentation_family,
      component_key:`${row.asset_id}::${row.property_key}`
    }));
    // Identity/topology changes affect all page types; expose a generic
    // product-level invalidation rather than silently ignoring object changes.
    const changedObjects=[...entityIds].filter(id=>this.objectStates.has(id))
      .map(id=>Object.freeze({entity_id:id,surface:'all',role:'identity',family:'asset',asset_id:'*'}));
    return [...propertyChanges,...changedObjects];
  }

  get size() { return this.byEntity.size; }
  hasCanonicalTruth() { return this.size > 0; }
  entityIds() { return [...this.byEntity.keys()]; }
  row(assetId, propertyKey) {
    const key = `${String(assetId||'')}::${String(propertyKey||'')}`;
    return this.ambiguousAssetKeys.has(key) ? null : (this.byAssetAndKey.get(key) || null);
  }
  // All public row selectors share the same fail-closed identity boundary.
  // Secondary indexes retain every publisher for diagnostics and invalidation,
  // but never expose a conflicting asset/property pair as product truth.
  unambiguousRows(rows = []) {
    return rows.filter(row => !this.ambiguousAssetKeys.has(`${row.asset_id}::${row.property_key}`));
  }
  rowsForProperty(propertyKey) { return this.unambiguousRows(this.byPropertyKey.get(String(propertyKey||'')) || []); }
  rowsForSurface(surface) { return this.unambiguousRows(this.bySurface.get(String(surface||'')) || []); }
  rowsForFamily(family) { return this.unambiguousRows(this.byFamily.get(String(family||'')) || []); }
  productRows() { return this.uniqueProductRows(); }
  technicalRows() { return [...this.byEntity.values()].filter(row=>row.presentation_technical === true || row.presentation_surface === 'diagnostics'); }
  contractGaps() {
    return [
      ...[...this.ambiguousObjects].sort().map(asset_id=>Object.freeze({asset_id,reason:'duplicate_canonical_object'})),
      ...[...this.byEntity.values()].filter(row=>!row.presentation_complete && row.presentation_technical !== true),
      ...[...this.ambiguousAssetKeys].sort().map(key=>Object.freeze({key,reason:'duplicate_canonical_property'}))
    ];
  }

  entityIdsForSurfaces(surfaces = []) {
    const ids = new Set();
    for (const surface of surfaces) for (const row of this.rowsForSurface(surface)) ids.add(row.entity_id);
    return [...ids];
  }
}

function createEnergyCanonicalPropertyIndex(hass = {}) {
  return new EnergyCanonicalPropertyIndex(hass);
}

/**
 * Native Energy metric authority (domain-owned HA contract).
 * Select by backend-published metric_key, not an assumed HA entity_id.
 * Ambiguous/missing/unavailable publication fails closed; zero is preserved.
 */
function readNativeEnergyMetric(hass = {}, metricKey = '') {
  const key = String(metricKey || '').trim();
  const matches = Object.entries(hass?.states || {}).filter(([,state]) =>
    String(state?.attributes?.metric_key || '') === key &&
    String(state?.attributes?.canonical_source || '') === 'rhi_energy.runtime'
  );
  if (!key || matches.length !== 1) return Object.freeze({
    available:false, value:null, entity_id:null,
    reason:matches.length > 1 ? 'duplicate_native_energy_metric' : 'native_energy_metric_not_published'
  });
  const [entityId,state] = matches[0];
  const attrs = state.attributes || {};
  const availability = String(attrs.availability || '').toUpperCase();
  const raw = String(state.state ?? '').trim();
  const invalid = ['unknown','unavailable','none','null',''].includes(raw.toLowerCase());
  // Native Energy metrics are numeric. Reject non-finite or malformed readings,
  // even when their HA availability metadata is incorrectly marked AVAILABLE.
  // Number('') is zero, so check empty/unknown before numeric conversion.
  const numericValue = invalid ? null : Number(raw);
  const validNumber = numericValue !== null && Number.isFinite(numericValue);
  const quality = String(attrs.quality || '').trim().toUpperCase();
  const invalidQuality = ['STALE','INVALID','UNKNOWN'].includes(quality);
  const available = availability === 'AVAILABLE' && validNumber && !invalidQuality;
  return Object.freeze({
    available,
    entity_id:entityId,
    value:available ? state.state : null,
    unit:String(attrs.unit_of_measurement || ''),
    quality:attrs.quality ?? null,
    provenance:attrs.provenance ?? null,
    reason:available ? null : String(attrs.reason_code ||
      (invalidQuality ? 'invalid_native_energy_metric_quality' :
       (availability === 'AVAILABLE' && !validNumber ? 'invalid_native_energy_metric' :
        (availability || 'native_energy_metric_unavailable')))),
    metric_key:key,
    // Native evidence is period/horizon scoped and must not be reused for an
    // unrelated selector (e.g. 'today' result shown as 'this month').
    period:String(attrs.period || ''),
    horizon:String(attrs.horizon || ''),
    actual_complete:attrs.actual_complete === true,
    totals_complete:attrs.totals_complete === true,
    evidence_method:String(attrs.evidence_method || ''),
    source_field:String(attrs.source_field || ''),
    observed_at:String(attrs.observed_at || '')
  });
}

/** Published planning totals only. No frontend total arithmetic or Public V2 fallback. */
function readNativeEnergyPlanningTotals(hass = {}, horizonId = 'D0') {
  const horizon=String(horizonId || '').toUpperCase();
  if (!['D0','D1'].includes(horizon)) return Object.freeze({
    available:false,horizon,values:Object.freeze({}),missing:Object.freeze(['unsupported_planning_horizon'])
  });
  const prefix=horizon==='D0' ? 'planning_today_' : 'planning_tomorrow_';
  const fields=['required_kwh','planned_kwh','still_to_plan_kwh',
    'flexible_required_kwh','flexible_planned_kwh','flexible_still_to_plan_kwh'];
  const values={};
  const missing=[];
  for (const field of fields) {
    const metric=readNativeEnergyMetric(hass,prefix+field);
    values[field]=metric;
    if (!metric.available) missing.push(field);
  }
  return Object.freeze({
    available:missing.length===0,
    horizon,
    values:Object.freeze(values),
    missing:Object.freeze(missing)
  });
}

// ---- src/runtime/energy-contract-gateway.js ----
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

// ---- src/runtime/energy-v2-contract.js ----
// Canonical Energy product projection from direct HA object/property entities,
// domain-owned native metrics and published horizon decisions. No aggregate
// Public V2 snapshot is read here. Screens receive one coherent read-only view.
function readEnergyCanonicalProduct(gateway) {
  const index=gateway?.host?.canonicalIndex;
  const hass=gateway?.host?.hass || {};
  const propertyRows=index?.productRows?.() || [];
  const ids=new Set();
  const byId=new Map();
  const byKey=new Map();
  const byAssetAndKey=new Map();
  const conflicts=new Set();
  const objectRows=index?.objectRows?.() || [];
  for(const object of objectRows) {
    if(object.object_class === 'energy_configuration') continue;
    if(byId.has(object.asset_id)){conflicts.add(object.asset_id);continue;}
    byId.set(object.asset_id,{...object,properties:[]});
  }
  for(const property of propertyRows) {
    const id=String(property.asset_id || '');
    const key=String(property.property_key || '');
    if(!id || !key || index?.ambiguousObjects?.has(id)) continue;
    const objectClass=String(property.logical_object_class || '');
    if(objectClass === 'energy_configuration') continue;
    const object=byId.get(id);
    if(object && object.object_class !== objectClass) {conflicts.add(id);continue;}
    if(!object)byId.set(id,{
      asset_id:id,object_class:objectClass,asset_type:objectClass,
      display_name:String(property.asset_display_name || id),
      parent_asset_id:property.parent_asset_id || null,
      profile_id:'',visual_ref:'',properties:[]
    });
    byId.get(id).properties.push(property);
  }
  for(const id of conflicts)byId.delete(id);
  for(const [id,obj] of byId) {
    ids.add(id);
    Object.freeze(obj.properties);
    byId.set(id,Object.freeze(obj));
    for(const p of obj.properties) {
      const key=String(p.property_key);
      byAssetAndKey.set(id+'::'+key,p);
      if(!byKey.has(key))byKey.set(key,p);
      else {byKey.set(key,null);}
    }
  }
  const objects=Object.freeze([...byId.values()]);
  const semantic=raw=>{
    if(!raw || raw.availability !== 'AVAILABLE')return Object.freeze({
      resolved:false,value:null,display:'—',status:'UNAVAILABLE',state:'unavailable',
      reason:String(raw?.reason || 'canonical_property_not_published'),
      quality:String(raw?.quality || 'UNKNOWN'),unit:String(raw?.unit || ''),raw:raw || {}
    });
    return Object.freeze({
      resolved:true,value:raw.value,display:String(raw.value),status:'AVAILABLE',
      state:'available',reason:String(raw.reason || ''),quality:String(raw.quality || ''),
      unit:String(raw.unit || ''),editable:raw.editable === true,
      editor:raw.editor || null,write:raw.write || null,
      constraints:raw.constraints || {},raw
    });
  };
  const currentField=key=>semantic(byKey.get(String(key || '')) || null);
  const currentMap=[
    ['battery','battery_system',['power_kw','soc_pct','capacity_kwh','available_kwh','state','reserve_target_pct']],
    ['solar','solar_production',['power_kw']],
    ['grid','grid_connection',['net_power_kw','flow_direction']],
    ['home','home_consumption',['power_kw']],
    ['consumption','site_consumption',['power_kw']],
    ['flexible','flexible_loads',['power_kw','attributed_power_kw','available_power_kw']]
  ];
  const core={},coreByKey=new Map();
  for(const [section,cls,keys] of currentMap) {
    const sectionFields={};
    const matching=objects.filter(obj=>obj.object_class===cls);
    for(const field of keys) {
      const key=section==='grid' && field==='net_power_kw' ? 'grid.net_power_kw'
        : section==='grid' && field==='flow_direction' ? 'grid.flow_direction'
        : section==='grid' ? 'grid_'+field
        : section==='consumption' ? 'site_consumption.'+field
        : section==='home' ? 'home_consumption.'+field
        : section==='battery' ? 'battery.'+field
        : section==='solar' ? 'solar.'+field : 'flexible_loads.'+field;
      const rows=matching.flatMap(o=>o.properties.filter(p=>p.property_key===key));
      const one=rows.length===1?rows[0]:null;
      const value=semantic(one);
      coreByKey.set(key,value);
      sectionFields[field]=value;
    }
    core[section]={fields:sectionFields,...Object.fromEntries(Object.entries(sectionFields).map(([key,row])=>[key,row.resolved ? row.value : null]))};
  }
  const configRows=propertyRows.filter(row=>row.logical_object_class === 'energy_configuration');
  for(const p of configRows){
    const key=String(p.property_key || ''),id=String(p.asset_id || '');
    if(!key || !id)continue;
    byAssetAndKey.set(id+'::'+key,p);
    if(!byKey.has(key))byKey.set(key,p);
    else byKey.set(key,null);
  }
  const forFamily=kind=>configRows.filter(row=>row.presentation_family === kind);
  const pricingRows=forFamily('pricing'), strategyRows=forFamily('strategy'), meteringRows=forFamily('metering');
  const groupProfiles=new Map();
  for(const row of strategyRows) {
    const id=String(row.asset_id || '').replace(/^configuration:/,'');
    if(!id)continue;
    if(!groupProfiles.has(id))groupProfiles.set(id,{
      profile_id:id,display_name:id.replace(/_/g,' '),configured_properties:[],effective_properties:[]
    });
    groupProfiles.get(id).configured_properties.push(row);
  }
  const configuration={
    pricing:{properties:pricingRows},
    metering:{properties:meteringRows},
    strategy:{profiles:[...groupProfiles.values()],configured:{properties:strategyRows},
      configured_properties:strategyRows,effective:{properties:[],status:'UNAVAILABLE',reason:'effective_strategy_not_published'}}
  };
  const horizons={},planningObjects=[];
  for(const id of ['D0','D1']) {
    const native=typeof gateway.host?.nativePlanningTotals==='function'
      ? gateway.host.nativePlanningTotals(id) : readNativeEnergyPlanningTotals(hass,id);
    const detail=typeof gateway.host?.nativePlanningHorizon==='function'
      ? gateway.host.nativePlanningHorizon(id):null;
    const attrs=detail?.published === true && detail.details ? detail.details : {};
    const numeric=(field)=>{
      const cell=native?.values?.[field];
      return cell?.available === true ? Number(cell.value) : null;
    };
    const totalFields=['required_kwh','planned_kwh','still_to_plan_kwh',
      'flexible_required_kwh','flexible_planned_kwh','flexible_still_to_plan_kwh'];
    horizons[id]={
      horizon_id:id,
      // Numeric totals are evidence, not proof that an effective plan exists.
      status:detail?.available === true ? 'AVAILABLE' : (detail?.status || 'INCOMPLETE'),
      quality:{availability:detail?.available === true ? 'AVAILABLE' : (detail?.status || 'INCOMPLETE'),
        reason_code:detail?.reason || null,
        missing:native?.missing || totalFields},
      requested_provider:detail?.metadata?.requested_provider ?? null,
      effective_provider:detail?.available === true ? (detail?.metadata?.effective_provider ?? detail?.metadata?.provider_id ?? null) : null,
      ...Object.fromEntries(totalFields.map(k=>[k,numeric(k)])),
      buckets:Array.isArray(attrs.buckets) ? attrs.buckets:[],
      planning_assets:Array.isArray(attrs.planning_assets)?attrs.planning_assets:[],
      source_lanes:attrs.source_lanes || {},consumer_lanes:attrs.consumer_lanes || {},
      balance:attrs.balance || {},battery_ledger:attrs.battery_ledger || {},
      policy_evidence:attrs.policy_evidence || {},plan_id:attrs.plan_id || null,
      generated_at:attrs.generated_at || null,provider_id:attrs.provider_id || null,
      execution_policy:attrs.execution_policy || {}
    };
    for(const row of horizons[id].planning_assets) if(row?.asset_id)
      planningObjects.push({...row,horizon_id:id});
  }
  // Period-integrated Metering is a distinct producer-owned HA contract.
  // Do not integrate instantaneous kW, guess periods or revive Public V2.
  const meteringPeriods={},meteringConflicts=new Set();
  for(const [entityId,state] of Object.entries(hass.states || {})) {
    const a=state?.attributes || {};
    // HA may retain attributes after a native producer has become unavailable.
    // Do not revive an invalid period or its old financial value.
    if(['unavailable','unknown',''].includes(String(state?.state ?? '').trim().toLowerCase())) continue;
    if(a.contract_id !== 'RHI_ENERGY_METERING_PERIOD_V1' ||
       a.canonical_source !== 'rhi_energy.runtime' || a.publisher !== 'rhi_energy') continue;
    const periodId=String(a.period_id || '').toLowerCase();
    if(!['hour','today','week','month','year'].includes(periodId)) continue;
    if(meteringPeriods[periodId]) {meteringConflicts.add(periodId);continue;}
    const measured=a.summary?.measured;
    if(!measured || typeof measured !== 'object' || Array.isArray(measured)) continue;
    meteringPeriods[periodId]=Object.freeze({
      entity_id:entityId,period_id:periodId,
      availability:String(a.availability || 'UNAVAILABLE'),
      measurement_state:String(a.availability || 'UNAVAILABLE'),
      quality:String(a.quality || 'UNKNOWN'),
      summary:Object.freeze({measured:Object.freeze({...measured}),
        quality:Object.freeze({...a.summary?.quality || {}}),
        cost:Object.freeze({...a.summary?.cost || {}})}),
      flexible_assets_kwh:Object.freeze({...a.flexible_assets_kwh || {}}),
      field_quality:Object.freeze({...a.field_quality || {}}),
      field_coverage_seconds:Object.freeze({...a.field_coverage_seconds || {}}),
      baseline_reset_required:a.baseline_reset_required === true,
      can_be_used_for_remaining:a.can_be_used_for_remaining === true
    });
  }
  for(const id of meteringConflicts) delete meteringPeriods[id];
  const metering=Object.freeze({
    periods:Object.freeze(meteringPeriods),
    available:Object.values(meteringPeriods).some(row=>row.availability === 'AVAILABLE'),
    reason:meteringConflicts.size ? 'duplicate_native_metering_period' :
      Object.keys(meteringPeriods).length ? '' : 'canonical_period_publication_unavailable'
  });
  // Retrospective is already published by Energy as a native HA sensor.
  // Never synthesize a retrospective assessment in the browser. Preserve
  // genuine PENDING/WAITING statuses and producer-owned prerequisites.
  let retrospective=null;
  let retrospectiveCount=0;
  for(const [entityId,state] of Object.entries(hass.states || {})) {
    const a=state?.attributes || {};
    if(a.canonical_contract !== 'ENERGY_CANONICAL_RETROSPECTIVE_V1' ||
       a.canonical_source !== 'rhi_energy.runtime' || a.publisher !== 'rhi_energy') continue;
    retrospectiveCount++;
    retrospective=Object.freeze({
      status:String(state.state || 'UNAVAILABLE'),entity_id:entityId,
      availability:a.availability || 'UNAVAILABLE',
      reason:a.reason || '',prerequisites:Array.isArray(a.prerequisites)?a.prerequisites:[],
      score:a.score ?? null,confidence:a.confidence ?? null,
      evidence_coverage_pct:a.evidence_coverage_pct ?? null,
      trend:a.trend ?? null,objectives:Array.isArray(a.objectives)?a.objectives:[],
      execution_kpis:a.execution_kpis || {},score_semantics:a.score_semantics || null,
      observed_at:a.observed_at || null
    });
  }
  if(retrospectiveCount!==1) retrospective=null;
  // Exact planner selection/status is a native Energy entity, not an
  // inference from a baseline or a favorable planning metric.
  let plannerStatus=null,plannerPublishers=0;
  for(const [entityId,state] of Object.entries(hass.states || {})) {
    const a=state?.attributes || {};
    if(a.canonical_contract !== 'RHI_ENERGY_PLANNER_PROVIDER_CATALOG_V1' ||
       a.canonical_source !== 'rhi_energy.runtime' || a.publisher !== 'rhi_energy') continue;
    plannerPublishers++;
    plannerStatus=Object.freeze({
      entity_id:entityId,status:String(state.state || 'UNAVAILABLE'),
      requested_provider:a.requested_provider || null,
      effective_provider:a.effective_provider || null,
      selection_reason:a.selection_reason || null,
      requested_runtime_reason:a.requested_runtime_reason || null,
      requested_runtime_status:a.requested_runtime_status || null,
      baseline_available:a.baseline_available === true,
      execution_authorized:a.execution_authorized === true
    });
  }
  if(plannerPublishers!==1) plannerStatus=null;
  // Every period is published independently by Energy, including its own
  // priced-interval proof. Do not calculate profit from cost/revenue in UX.
  const nativeValue=readNativeEnergyMetric(hass,'net_financial_result_eur');
  const period=nativeValue?.period || null;
  const financialPeriods={};
  for(const [id,row] of Object.entries(meteringPeriods)) {
    const cost=row.summary?.cost || {};
    const valid=row.availability === 'AVAILABLE' &&
      cost.available === true && cost.actual_complete === true &&
      typeof cost.net_financial_result_eur === 'number' &&
      Number.isFinite(cost.net_financial_result_eur);
    financialPeriods[id]=Object.freeze({
      entity_id:row.entity_id,period_id:id,available:valid,
      net_financial_result_eur:valid ? cost.net_financial_result_eur : null,
      actual_complete:valid && cost.actual_complete === true,
      site_period_complete:valid && cost.site_period_complete === true,
      quality:String(cost.quality || 'UNKNOWN'),
      reason:String(cost.reason_code || 'financial_period_evidence_unavailable'),
      evidence_method:cost.evidence_method || null
    });
  }
  // The selected standalone metric is an older native HA projection. Preserve
  // it only when per-period backend net proof is not yet published; never
  // override explicit unavailable/invalid financial evidence from a period.
  if(period && nativeValue?.available === true &&
     ['number','string'].includes(typeof nativeValue.value) &&
     String(nativeValue.value).trim() !== '' && Number.isFinite(Number(nativeValue.value)) &&
     !(period in financialPeriods && 
       Object.prototype.hasOwnProperty.call(meteringPeriods[period]?.summary?.cost || {}, 'available'))) {
    financialPeriods[period]=Object.freeze({
      entity_id:nativeValue.entity_id || null,period_id:period,available:true,
      net_financial_result_eur:Number(nativeValue.value),
      actual_complete:nativeValue.actual_complete === true,
      site_period_complete:nativeValue.site_period_complete === true,
      quality:String(nativeValue.quality || 'UNKNOWN'),reason:nativeValue.reason || '',
      evidence_method:'selected_native_metric'
    });
  }
  const valueAccounting={
    selected_period_id:period,
    periods:Object.freeze(financialPeriods),
    net_financial_result:period && financialPeriods[period]?.available ?
      {value:financialPeriods[period].net_financial_result_eur,period_id:period,
       actual_complete:financialPeriods[period].actual_complete} : {}
  };
  const flexibleAssets=objects.filter(obj=>obj.object_class==='flexible_load').map(obj=>{
    const rows=obj.properties;
    const facts=Object.fromEntries(rows.filter(p=>p.availability === 'AVAILABLE')
      .map(p=>[p.property_key,p.value]));
    const propertyValue=suffix=>rows.find(p=>p.property_key===suffix)?.value ?? null;
    return {...obj,...facts,power_kw:propertyValue('power_kw'),
      energy_to_target_kwh:propertyValue('energy_to_target_kwh'),
      flexible_role:propertyValue('flexible_role'),visible:true,show_in_primary_ux:true};
  });
  const nativeCommands=readEnergyCommandContract(gateway).rows;
  const envelope=Object.freeze({entityId:null,available:!!index?.hasCanonicalTruth?.(),
    contractVersion:'ENERGY_CANONICAL_NATIVE_V2'});
  // Navigation presence is published by the native object/configuration
  // inventory, not guessed from a momentary power measurement or old snapshot.
  // An unavailable battery remains visible so the user can diagnose it.
  const objectClasses=new Set(objects.map(obj=>String(obj.object_class || '')));
  const presence=Object.freeze({
    battery:objectClasses.has('battery_system') || objectClasses.has('battery'),
    gas:objectClasses.has('gas_meter'),
    flexible_loads:objectClasses.has('flexible_load') ||
      objectClasses.has('flexible_loads'),
    solar:objectClasses.has('solar_production'),
    pricing:pricingRows.length>0,
    strategy:strategyRows.length>0,
    metering:meteringRows.length>0,
    planning:Object.values(horizons).some(h=>h.status==='AVAILABLE')
  });
  const capabilities={
    core:propertyRows.length>0,assets:objects.length>0,
    planning:Object.values(horizons).some(h=>h.status==='AVAILABLE'),
    pricing:pricingRows.length>0,strategy:strategyRows.length>0,
    commands:nativeCommands.length>0,
    value_accounting:Object.values(financialPeriods).some(row=>row.available === true)
  };
  return Object.freeze({
    envelope,available:envelope.available,publicContractOk:envelope.available,
    corePresent:capabilities.core,capabilities,compatibilityReason:envelope.available?'':'canonical_energy_property_unavailable',
    contractVersion:envelope.contractVersion,release:'',
    health:envelope.available?'AVAILABLE':'UNAVAILABLE',
    core,summary:{},experience:{presence},presence,
    objects,profiles:[],relationships:[],connections:[],commands:nativeCommands,activity:[],
    planning:{horizons,provider_status:plannerStatus||{}},metering,retrospective:retrospective||{},intelligence:{},overview:{},
    configuration,valueAccounting,layers:{planning_objects:planningObjects},
    flexibleAssets:Object.freeze(flexibleAssets),planningObjects:Object.freeze(planningObjects),
    objectById:byId,profileById:new Map(),
    propertyRows:Object.freeze(propertyRows),configurationRows:Object.freeze(configRows),
    allPropertyRows:Object.freeze(propertyRows),propertyByKey:byKey,
    propertyByAssetAndKey:byAssetAndKey,coreByKey,
    currentAggregateObject:()=>null,currentField,
    object:id=>byId.get(String(id||''))||null,
    profile:()=>null,
    property:(key,id='')=>id ? (byAssetAndKey.get(String(id)+'::'+String(key)) || null)
      : (byKey.get(String(key)) || null),
    field:(key,id='')=>semantic(id ? byAssetAndKey.get(String(id)+'::'+String(key))
      : byKey.get(String(key)))
  });
}

function createEnergyAssetProjection(product,assetId) {
  const asset=product?.object?.(assetId);
  if(!asset)return null;
  const properties=(asset.properties || []).map(row=>({...row,projection:product.field(row.property_key,assetId)}));
  return Object.freeze({
    identity:Object.freeze({asset_id:asset.asset_id,display_name:asset.display_name,
      asset_type:asset.object_class,object_class:asset.object_class,
      profile_id:asset.profile_id || '',visual_ref:asset.visual_ref || '',
      source:'RHI_ENERGY_CANONICAL_OBJECT_V2'}),
    lifecycle:Object.freeze({state:asset.health || 'UNKNOWN',source:'RHI_ENERGY_CANONICAL_OBJECT_V2'}),
    properties:Object.freeze(properties),
    property:key=>product.field(key,assetId),
    relationships:Object.freeze([]),controls:Object.freeze([]),
    profile:null,raw:asset
  });
}

// ---- src/domain/selectors/energy-selectors.js ----
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

// ---- src/app/energy-asset-catalog.js ----
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

// ---- src/runtime/foundation-visual-registry.js ----
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

// ---- src/runtime/visual-asset-resolver.js ----
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

// ---- src/runtime/asset-profile-contract.js ----
// Native Energy asset context. Only backend canonical object and property
// publications own identity, hierarchy, appearance and technical details.
function readEnergyAssetContext(gateway, assetId = '') {
  const id=String(assetId || '').trim(),index=gateway?.host?.canonicalIndex;
  if(!id || index?.ambiguousObjects?.has(id))return Object.freeze({
    available:false,asset:null,profile:null,publication:null,
    reason:index?.ambiguousObjects?.has(id) ? 'duplicate_canonical_object':'asset_id_required'
  });
  const status=index?.object?.(id) || null;
  const rows=(index?.productRows?.() || []).filter(r=>r.asset_id===id);
  const classes=new Set([status?.object_class,...rows.map(r=>r.logical_object_class)].filter(Boolean));
  if(classes.size!==1)return Object.freeze({available:false,asset:null,profile:null,publication:null,
    reason:classes.size>1 ? 'ambiguous_asset_class':'canonical_asset_not_published'});
  const cls=[...classes][0];
  const first=rows[0] || {};
  const asset=Object.freeze({
    asset_id:id,object_class:cls,asset_type:cls,
    display_name:String(status?.display_name || first.asset_display_name || id),
    parent_asset_id:status?.parent_asset_id || first.parent_asset_id || null,
    integration_domain:first.integration_domain || null,
    profile_id:status?.profile_id || '',visual_ref:status?.visual_ref || '',
    health:status?.health || 'UNKNOWN',
    source_device_ids:status?.source_device_ids || [],
    children:status?.children || [],
    properties:Object.freeze(rows.map(row=>Object.freeze({...row})))
  });
  return Object.freeze({available:true,asset,profile:null,publication:null});
}
function energyAssetPublicationGap(gateway,assetId='') {
  const context=readEnergyAssetContext(gateway,assetId);
  return Object.freeze({
    status:context.available ? 'not_published':'unavailable',
    missing:[],unresolved:[],resolution_complete:false,
    authority:'RHI_ENERGY_CANONICAL_OBJECT_V2',
    reason:context.reason || 'backend_publication_completeness_not_published'
  });
}

// ---- src/runtime/consumption-contract.js ----
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

// ---- src/domain/models/current-energy-view-model.js ----
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

// ---- src/domain/models/physical-flow-view-model.js ----
// R1.89.39 physical-flow model. Consumers and physical connections are
// separate semantic views and may show the same measured kW. They are never
// summed together. Connection totals and rows come only from one coherent
// backend-owned connection snapshot.
  function buildPhysicalFlowViewModel(runtime, gateway, consumers = [], connections = [], connectionSnapshot = {}) {
    const consumption = readLiveConsumptionContract(gateway);
    const physicalPower = (row, id) => asNumber(firstDefined(
      row?.actual_power_kw,
      row?.current_power_kw,
      row?.power_kw,
      id ? runtime.number(`${id}.actual_power_kw`) : null,
      id ? runtime.number(`${id}.current_power_kw`) : null,
      id ? runtime.number(`${id}.power_kw`) : null
    ));
    const consumerRows = consumers.map(row => {
      const assetId = String(firstDefined(row.asset_id,row.flexible_asset_id,row.target_asset_id,'') || '');
      return Object.freeze({ ...row, asset_id:assetId, physical_power_kw:physicalPower(row, assetId) });
    });
    const connectionRows = connections.map(row => {
      const assetId = String(firstDefined(row.connection_asset_id,row.asset_id,row.charger_id,'') || '');
      return Object.freeze({ ...row, asset_id:assetId, connection_asset_id:assetId, physical_power_kw:asNumber(firstDefined(row.power_kw,row.physical_power_kw)) });
    });
    return Object.freeze({
      consumption,
      siteConsumptionKw:consumption.siteConsumptionKw,
      homeConsumptionKw:consumption.homeConsumptionKw,
      flexibleLoadsKw:consumption.flexibleLoadsKw,
      consumers:Object.freeze(consumerRows),
      connections:Object.freeze(connectionRows),
      connectionPowerKw:asNumber(connectionSnapshot.totalPowerKw),
      snapshotRevision:String(connectionSnapshot.snapshotRevision || ''),
      observedAt:String(connectionSnapshot.observedAt || ''),
      connectionHealth:connectionSnapshot.available ? 'OK' : 'UNAVAILABLE'
    });
  }

// ---- src/runtime/power-flow-card-adapter.js ----
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

// ---- src/domain/models/metering-status-model.js ----
// R1.89.43 end-user mapping. status_label is authoritative when published;
// null energy is never interpreted without measurement state and measured zero remains visible.
  function createMeteringStatusModel(row = {}) {
    const state = String(firstDefined(row.measurement_state,row.status,row.health,row.quality,'UNAVAILABLE') || 'UNAVAILABLE').toUpperCase();
    const labels = {
      MEASURED: 'Measured', TRUSTED: 'Measured', COMPLETE: 'Complete', OK: 'Measured',
      ATTRIBUTION_PENDING: 'Waiting for trusted meter attribution',
      PENDING: 'Waiting for period baseline',
      NOT_APPLICABLE: 'Not applicable',
      UNAVAILABLE: 'Unavailable', UNKNOWN: 'Unavailable', FAILED: 'Measurement failed',
      INCOMPLETE: 'Incomplete measurement', PARTIAL: 'Incomplete measurement'
    };
    const label = String(firstDefined(row.status_label, labels[state], human(state, 'Unavailable')) || 'Unavailable');
    const measured = row.value !== null && row.value !== undefined && ['MEASURED','TRUSTED','COMPLETE','OK'].includes(state);
    const technicalKey = String(firstDefined(row.metric_key,row.semantic_key,row.property_key,row.key,row.asset_id,'') || '').toLowerCase();
    const unattributed = /unattributed|unassigned/.test(technicalKey);
    const value = asNumber(row.value);
    const degraded = /DEGRADED|FAIL|ERROR|INCOMPLETE|PENDING|ATTRIBUTION/.test(state) || asBool(row.attribution_degraded, false);
    const applicable = state !== 'NOT_APPLICABLE' && row.applicable !== false;
    const explicitlyVisible = row.ux_visible === undefined ? true : asBool(row.ux_visible, false);
    return Object.freeze({
      state, label, measured, applicable, unattributed,
      userActionRequired:asBool(row.user_action_required, false),
      visible: explicitlyVisible && applicable && (!unattributed || (value !== null && value > 0.0001) || degraded)
    });
  }

// ---- src/runtime/command-contract.js ----
// Native Energy command authority. A canonical button advertises a literal,
// backend-owned service invocation; availability is never inferred from HA IDs.
function readEnergyCommandContract(gateway) {
  const states=gateway?.host?.hass?.states || {};
  const grouped=new Map(),ambiguous=new Set();
  for(const [entityId,state] of Object.entries(states)) {
    const a=state?.attributes || {};
    if(a.canonical_contract !== 'RHI_ENERGY_CANONICAL_COMMAND_V1') continue;
    const id=String(a.asset_id || a.target_asset_id || '').trim();
    const key=String(a.command_id || a.command_key || '').trim();
    const role=String(a.role || '').trim();
    if(!id || !key || !role || id!==String(a.target_asset_id || id).trim()) continue;
    const composite=`${id}::${key}`;
    if(grouped.has(composite)){ambiguous.add(composite);continue;}
    const invoke=a.invoke && typeof a.invoke==='object' ? a.invoke : {};
    const data=invoke.data && typeof invoke.data==='object' ? invoke.data : {};
    const exact=String(invoke.service || '')==='rhi_energy.invoke_command' &&
      String(data.command_id || '')===key &&
      String(data.target_asset_id || '')===id;
    const supported=a.supported===true;
    const visible=supported && a.visible===true;
    const allowed=visible && exact && a.execution_allowed===true &&
      String(a.availability || '').toUpperCase()==='AVAILABLE';
    grouped.set(composite,Object.freeze({
      entity_id:entityId,command_row_id:composite,command_instance_id:composite,
      command_id:key,command_key:key,target_asset_id:id,asset_id:id,role,
      label:String(a.label || role.replace(/_/g,' ')),
      command_owner:'energy',action_kind:'command',
      contract_valid:exact,
      command_resolved:exact,
      currently_applicable:allowed,visible,enabled:allowed,
      supported,execution_allowed:allowed,
      blocked_reason:String(a.blocked_reason || (allowed ? '' : exact ? 'backend_not_available':'incomplete_command_invocation')),
      invoke:exact ? Object.freeze({service:invoke.service,data:Object.freeze({...data})}) : null,
      source:'RHI_ENERGY_CANONICAL_COMMAND_V1'
    }));
  }
  const rows=[...grouped.entries()].filter(([id])=>!ambiguous.has(id)).map(([,row])=>row);
  return Object.freeze({
    envelope:Object.freeze({entityId:null,available:rows.length>0}),
    rows:Object.freeze(rows),
    ambiguous:Object.freeze([...ambiguous]),
    source:'RHI_ENERGY_CANONICAL_COMMAND_V1'
  });
}

// ---- src/runtime/command-action-model.js ----
// Stable R1.89.39 UX action model. Labels, visibility, enablement and blocked
// guidance are published by the command owner and are not reconstructed.
  function createCommandActionModel(command) {
    if (!command || command.visible !== true || !command.invoke) return null;
    const role = String(command.role || '').toLowerCase();
    const reason = String(firstDefined(command.blocked_reason, command.user_action_text, command.enabled ? 'Available' : 'Currently unavailable') || 'Currently unavailable');
    return Object.freeze({
      id: command.command_id,
      rowId: command.command_instance_id || command.command_row_id || '',
      targetAssetId: command.target_asset_id || '',
      role,
      label: String(firstDefined(command.label, human(role)) || ''),
      owner: command.command_owner || '',
      kind: command.action_kind || '',
      visible: true,
      enabled: command.enabled === true,
      currentlyApplicable: command.enabled === true,
      reason,
      userActionText:String(command.user_action_text || ''),
      command
    });
  }
  function commandActionModelsForAsset(commandContract, assetId) {
    const wanted = String(assetId || '');
    const order = { start: 10, stop: 20, pause: 30, resume: 40 };
    return commandContract.rows
      .filter(row => String(row.target_asset_id || '') === wanted && row.contract_valid === true)
      .map(createCommandActionModel)
      .filter(Boolean)
      .sort((a, b) => (order[a.role] || 99) - (order[b.role] || 99));
  }
  const ENGINEERING_DIAGNOSTICS = [
    'sensor.energy_runtime_deployment_health',
    'sensor.energy_runtime_proof_health',
    'sensor.energy_audit_closure_health',
    'sensor.energy_contract_version_consistency_health',
    'sensor.energy_home_intelligence_contract_standard_health'
  ];
  const SUPPLEMENTAL_DIAGNOSTICS = [
    'sensor.energy_solar_excess_supervisor_health',
    'sensor.energy_property_index_health',
    'sensor.energy_command_index_health',
    'sensor.energy_activity_index_health',
    'sensor.energy_relationship_index_health',
    'sensor.energy_intelligence_index_health',
    'sensor.energy_metering_integrity_health',
    'sensor.energy_publication_health',
    'sensor.energy_contract_traceability_health'
  ];

  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const parseMaybeJson = (value, fallback = null) => {
    if (value === undefined || value === null || value === '') return fallback;
    if (typeof value !== 'string') return value;
    const text = value.trim();
    if (!text) return fallback;
    try { return JSON.parse(text); } catch { return value; }
  };
  const asArray = (value) => {
    const parsed = parseMaybeJson(value, value);
    if (Array.isArray(parsed)) return parsed;
    if (parsed && typeof parsed === 'object') return Object.values(parsed);
    if (typeof parsed === 'string') return parsed.split(',').map(s => s.trim()).filter(Boolean);
    return [];
  };
  const asBool = (value, fallback = false) => {
    if (value === true || value === false) return value;
    const s = String(value ?? '').trim().toLowerCase();
    if (['true','1','yes','on','ok','ready','active','enabled','available'].includes(s)) return true;
    if (['false','0','no','off','fail','degraded','blocked','disabled','inactive','unavailable'].includes(s)) return false;
    return fallback;
  };
  const asNumber = (value) => {
    // Missing values are semantically different from a measured numeric zero.
    // Number(null), Number('') and Number(undefined) must never leak as 0 into UX.
    if (value === undefined || value === null || value === '') return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  };
  const rowValue = (row, fallback = null) => {
    if (!row || typeof row !== 'object') return row ?? fallback;
    const value = row.value ?? row.current_value ?? row.state ?? row.native_value ?? row.numeric_value ?? row.last_value;
    return value === undefined || value === null || value === '' ? fallback : value;
  };
  const fmtNumber = (value, decimals = 1, fallback = '—') => {
    const n = asNumber(value);
    return n === null ? fallback : n.toFixed(Math.max(0, Math.min(2, decimals)));
  };
  const fmtKw = (value, fallback = '—') => {
    const n = asNumber(value);
    return n === null ? fallback : `${Math.abs(n).toFixed(1)} kW`;
  };
  const fmtKwh = (value, fallback = '—') => {
    const n = asNumber(value);
    return n === null ? fallback : `${Math.abs(n).toFixed(1)} kWh`;
  };
  const fmtPct = (value, fallback = '—') => {
    const n = asNumber(value);
    return n === null ? fallback : `${Math.round(n)}%`;
  };
  const fmtEur = (value, fallback = '—') => {
    const n = asNumber(value);
    return n === null ? fallback : `€${n.toFixed(2)}`;
  };

  const rowState = (row) => {
    if (!row || row.missing) return 'missing';
    const value = rowValue(row, null);
    const health = String(row.health ?? row.quality ?? row.value_status ?? row.status ?? '').trim().toLowerCase();
    if (['fail','failed','error','critical','unavailable'].includes(health)) return 'fail';
    if (['degraded','stale','warning','warn','low_quality','partial','estimated','estimate','forecast','forecasted','modelled','modeled'].includes(health)) return 'warn';
    if (['unknown','not_published','not_available','missing'].includes(health)) return value === null ? 'missing' : 'unknown';
    if (['ok','ready','healthy','good','valid','fresh'].includes(health)) return 'ok';
    return value === null ? 'not-measured' : 'unknown';
  };
  const rowStatusLabel = (row) => {
    const state = rowState(row);
    if (state === 'ok') return 'OK';
    if (state === 'warn') return human(row.health || row.quality || 'Degraded');
    if (state === 'fail') return human(row.health || row.quality || 'Fail');
    if (state === 'missing') return rhiEnergyT(null,'common.not_available',{},'Not available');
    if (state === 'not-measured') return rhiEnergyT(null,'common.not_measured',{},'Not measured');
    return rhiEnergyT(null,'common.unknown',{},'Unknown');
  };
  const rowDisplayValue = (row, fallback = '—') => {
    if (!row || row.missing) return fallback;
    const value = rowValue(row, null);
    if (value === null || value === undefined || value === '') return rhiEnergyT(null,'common.not_measured',{},'Not measured');
    if (typeof value === 'number') return `${value}${row.unit ? ` ${row.unit}` : ''}`;
    return `${human(value, fallback)}${row.unit ? ` ${row.unit}` : ''}`;
  };

  const human = (value, fallback = '—') => {
    if (value === undefined || value === null || value === '') return fallback;
    if (Array.isArray(value)) return value.length ? value.map(v => human(v, '')).filter(Boolean).join(', ') : fallback;
    if (typeof value === 'object') return value.display_name || value.name || value.label || value.summary || value.reason || fallback;
    return String(value)
      .replace(/^energy_intelligence\./, '')
      .replace(/^battery_strategy\./, '')
      .replace(/^consumer_strategy\./, '')
      .replace(/^forecast\./, '')
      .replace(/[_.]+/g, ' ')
      .replace(/\b\w/g, c => c.toUpperCase());
  };

  const humanReason = (value, fallback = '—') => {
    if (value === undefined || value === null || value === '') return fallback;
    const raw = typeof value === 'object' ? (value.message || value.user_label || value.label || value.display_name || value.reason || value.reason_code || value.code || '') : String(value);
    const key = String(raw || '').trim();
    if (!key) return fallback;
    const normalized = key.toLowerCase().replace(/[\s.-]+/g, '_');
    const labels = {
      policy_mode_off: rhiEnergyT(null,'reason.intelligence_off',{},'Energy Intelligence is off'),
      mode_off: rhiEnergyT(null,'reason.intelligence_off',{},'Energy Intelligence is off'),
      intelligence_off: rhiEnergyT(null,'reason.intelligence_off',{},'Energy Intelligence is off'),
      energy_intelligence_off: rhiEnergyT(null,'reason.intelligence_off',{},'Energy Intelligence is off'),
      automation_disabled: rhiEnergyT(null,'reason.automation_disabled',{},'Automation is disabled'),
      disabled: rhiEnergyT(null,'reason.disabled',{},'Disabled'),
      not_available: rhiEnergyT(null,'reason.not_available',{},'Not available'),
      not_published: rhiEnergyT(null,'reason.not_published',{},'Information is not available yet'),
      no_battery_policy_reason_published: rhiEnergyT(null,'reason.no_battery_policy',{},'Battery policy information is not available yet'),
      data_incomplete: rhiEnergyT(null,'reason.data_incomplete',{},'Some details are unavailable'),
      trust_state: rhiEnergyT(null,'reason.verification_required',{},'Verification is needed'),
      baseline_untrusted: rhiEnergyT(null,'reason.verification_required',{},'Verification is needed'),
      reset_pending: rhiEnergyT(null,'reason.reset_pending',{},'Reset in progress'),
      approval_required: rhiEnergyT(null,'reason.confirmation_needed',{},'Confirmation needed'),
      configuration_required: rhiEnergyT(null,'reason.not_configured',{},'Setup needed')
    };
    return labels[normalized] || human(key, fallback);
  };

  const normalizeHealthState = (state) => String(state ?? '').trim();
  const isOkHealth = (state) => normalizeHealthState(state).toUpperCase() === 'OK';
  const isIgnoredDiagnosticState = (state) => ['unknown','unavailable',''].includes(normalizeHealthState(state).toLowerCase());
  const labelHealthEntity = (entityId) => human(String(entityId || '')
    .replace(/^sensor\.energy_/, '')
    .replace(/_health$/, '') || entityId);


  function canonicalEditableProperty(row = {}) {
    const write = objectFrom(row.write || row.write_operation || {});
    const operationId = String(firstDefined(write.operation_id, row.write_operation, row.operation_id, '') || '');
    return asBool(firstDefined(row.editable, row.write_supported, operationId === 'energy.property.write'), false)
      && operationId === 'energy.property.write'
      && !!String(firstDefined(write.readback_property, row.readback_property, row.property_id, row.key, '') || '');
  }
  class EnergyRuntime {
    constructor(hass, canonicalIndex = null) {
      this.hass = hass || {};
      this.canonicalIndex = canonicalIndex || null;
      rhiEnergySetLocaleFromHass(this.hass);
      this._allowed = null;
      this._rows = null;
      this._assets = null;
      this._commands = null;
      this._activities = null;
      this._flexibleAssets = null;
      this._consumerMixRows = null;
      this._consumerMixSummary = null;
      this._planningExperienceRows = null;
      this._commandReadiness = null;
      this._planningOutcomes = null;
      this._effectiveStrategies = null;
      this._strategyProfiles = null;
      this._outlookHorizons = null;
      this._meteringHorizons = null;
      this._meteringPeriods = null;
      this._meteringRemediations = null;
      this._visualRegistry = null;
    }
    // Read domain-owned native HA evidence only; never reconstruct aggregate semantics.
    nativePlanningTotals(horizonId = 'D0') {
      return readNativeEnergyPlanningTotals(this.hass, horizonId);
    }
    nativePlanningHorizon(horizonId = 'D0', variant = 'effective') {
      const horizon=String(horizonId || '').toUpperCase();
      if(!['effective','baseline'].includes(variant)) return Object.freeze({published:false,available:false,details:null});
      if (!['D0','D1','D2'].includes(horizon)) return Object.freeze({available:false,details:null});
      // Baseline and INCOMPLETE horizons may be read as preview only.
      // They never authorize physical action or masquerade as effective plans.
      const contract=variant==='baseline'
        ? 'RHI_ENERGY_BASELINE_PLANNING_HORIZON_V1'
        : 'RHI_ENERGY_PLANNING_HORIZON_V1';
      const matches=Object.values(this.hass?.states || {}).filter(state=>
        state?.attributes?.canonical_contract === contract &&
        state?.attributes?.canonical_source === 'rhi_energy.runtime' &&
        state?.attributes?.horizon_id === horizon &&
        state?.attributes?.variant === variant);
      if (matches.length !== 1) return Object.freeze({
        published:false,available:false,status:'UNAVAILABLE',details:null,
        metadata:null,reason:matches.length>1?'duplicate_native_horizon':'native_horizon_not_published'
      });
      const attrs=matches[0].attributes || {};
      const details=attrs.details;
      const structurallyValid=details && typeof details === 'object' &&
        !Array.isArray(details) && Array.isArray(details.buckets) &&
        (details.horizon_id == null || details.horizon_id === horizon);
      const ready=String(attrs.availability || '').toUpperCase() === 'AVAILABLE' &&
        attrs.totals_complete === true && structurallyValid && variant==='effective';
      return Object.freeze({
        published:true,available:!!ready,
        status:ready?'AVAILABLE':String(attrs.availability || 'INCOMPLETE').toUpperCase(),
        reason:ready?'':String(attrs.reason_code || 'effective_horizon_incomplete'),
        details:structurallyValid?details:null,metadata:attrs
      });
    }

    nativeMetric(metricKey = '') {
      return readNativeEnergyMetric(this.hass, metricKey);
    }
    rawState(entityId) { return this.hass?.states?.[entityId] || null; }
    subscriptionEntityIds(surfaces = []) {
      const registryEntity = String(this.visualRegistry()?.entityId || '');
      const canonicalIds = this.canonicalIndex?.hasCanonicalTruth?.()
        ? (surfaces.length ? this.canonicalIndex.entityIdsForSurfaces(surfaces) : this.canonicalIndex.entityIds())
        : [];
      // Native Energy metric sensors are not canonical property rows; subscribe
      // explicitly so D0/D1 planning and financial states refresh on HA updates.
      const nativeMetrics = Object.entries(this.hass?.states || {})
        .filter(([,state])=>String(state?.attributes?.canonical_source || '') === 'rhi_energy.runtime'
          && (!!String(state?.attributes?.metric_key || '').trim() ||
            ['RHI_ENERGY_PLANNING_HORIZON_V1','RHI_ENERGY_BASELINE_PLANNING_HORIZON_V1']
              .includes(state?.attributes?.canonical_contract)))
        .map(([entityId])=>entityId);
      const objectIds=this.canonicalIndex?.objectEntityIds?.() || [];
      const planningConfigIds=Object.entries(this.hass?.states || {})
        .filter(([id,state])=>id.startsWith('select.') &&
          ['RHI_ENERGY_PLANNER_PROVIDER_CATALOG_V1','RHI_ENERGY_PLANNING_RESOLUTION_V1']
            .includes(state?.attributes?.canonical_contract) &&
          state?.attributes?.write_authority==='rhi_energy.config_entry.options')
        .map(([id])=>id);
      const commandIds=Object.entries(this.hass?.states || {})
        .filter(([,state])=>state?.attributes?.canonical_contract === 'RHI_ENERGY_CANONICAL_COMMAND_V1')
        .map(([id])=>id);
      return [...new Set([...canonicalIds, ...objectIds, ...nativeMetrics, ...commandIds, ...planningConfigIds, registryEntity].filter(Boolean))];
    }
    entitySignature(entityIds = []) {
      return (entityIds || []).map(id => {
        const state = this.rawState(id);
        return `${id}:${state?.state ?? ''}:${state?.last_updated ?? ''}`;
      }).join('|');
    }
    gasStatisticsEntityId(assetId = '') {
      const row = this.canonicalIndex?.row?.(String(assetId || ''), 'gas.total_m3') || null;
      if (!row) return '';
      return String(firstDefined(
        row.statistics_entity_id,
        row.history_entity_id,
        row.source_entity_id,
        ''
      ) || '').trim();
    }
    visualRegistry() {
      if (!this._visualRegistry) this._visualRegistry = readFoundationVisualRegistry(this.hass);
      return this._visualRegistry;
    }
    resolveVisualRef(visualRef, variant = 'card') {
      return resolveEnergyVisualRef(visualRef, this.visualRegistry(), variant);
    }
    sourceAssetNavigation(asset = {}) {
      if (typeof rhiUxResolveDomainAssetNavigation !== 'function') return '';
      const assetId = String(firstDefined(asset.asset_id, asset.id, asset.raw?.asset_id, '') || '').trim();
      const visualRef = String(firstDefined(asset.visual_ref, asset.visualRef, asset.raw?.visual_ref, '') || '').trim();
      const registryOwner = visualRef ? String(this.visualRegistry()?.entry?.(visualRef)?.owner_domain || '').trim() : '';
      const ownerDomain = String(firstDefined(
        asset.producer_domain,
        asset.source_domain,
        asset.visual_owner_domain,
        registryOwner,
        ''
      ) || '').trim();
      if (!assetId || !ownerDomain || ['rhi_energy','rhi_energy_ux'].includes(ownerDomain)) return '';
      return rhiUxResolveDomainAssetNavigation(ownerDomain, assetId);
    }
    releaseState() { return this.rawState(RELEASE_ENTITY); }
    releaseAttrs() {
      const diagnostic = this.releaseState()?.attributes || {};
      // The legacy release sensor is disabled by default; release identity
      // must instead travel on actual canonical Energy property entities.
      const versions = new Set(Object.values(this.hass?.states || {})
        .filter(state => state?.attributes?.canonical_contract === 'RHI_ENERGY_CANONICAL_PROPERTY_V2'
          && state?.attributes?.publisher_release)
        .map(state => String(state.attributes.publisher_release))
        .filter(value => /^E\d+\.\d+\.\d+$/.test(value)));
      const observed = versions.size === 1 ? [...versions][0] : '';
      return {
        ...diagnostic,
        backend_release: observed || (versions.size > 1 ? 'unknown' : String(diagnostic.backend_release || (this.releaseState()?.state?.startsWith('E') ? this.releaseState().state : 'unknown')))
      };
    }
    publicUxEntities() { return this.subscriptionEntityIds(); }
    isCanonicalUxInterface(entityId) {
      return !!this.canonicalIndex?.byEntity?.has(entityId) ||
        !!this.canonicalIndex?.objectStates?.has(entityId);
    }
    isAllowed(entityId) { return entityId === RELEASE_ENTITY || this.isCanonicalUxInterface(entityId); }
    state(entityId) { return this.isAllowed(entityId) ? this.rawState(entityId) : null; }
    attrs(entityId) { return this.state(entityId)?.attributes || {}; }
    contractGateway() { return createEnergyContractGateway(this); }
    interfaceEntity(_interfaceKey) { return null; }
    entityForKey(key) { return this.row(key)?.entity_id || null; }
    rowsForEntity(entityId) { const row=this.canonicalIndex?.byEntity?.get(entityId); return row ? [row] : []; }
    allRows() {
      if (this._rows) return this._rows;
      const result = new Map();
      const ambiguousKeys = new Set();
      // Unscoped lookups cannot choose a physical asset. Preserve multiple
      // assets in the canonical index, but never silently let the last asset
      // overwrite another asset's semantic value in a global projection.
      for (const row of (this.canonicalIndex?.uniqueProductRows?.() || [])) {
        const key = String(row?.property_key || '');
        if (!key) continue;
        if (result.has(key)) {
          ambiguousKeys.add(key);
          result.delete(key);
          continue;
        }
        if (ambiguousKeys.has(key)) continue;
        result.set(key, {
          ...row,
          entity_id:row.entity_id,
          property_id:key,
          property_key:key,
          key
        });
      }
      this._rows = result;
      return result;
    }
    propertyRows() { return [...this.allRows().values()]; }
    row(key) {
      const wanted=String(key || '');
      return this.allRows().get(wanted)
        || { key:wanted, property_id:wanted, property_key:wanted, value:null, unit:'', health:'NOT_PUBLISHED', quality:'missing', missing:true };
    }
    editablePropertyRows() {
      return (this.canonicalIndex?.productRows?.() || [])
        .filter(row => row?.editable === true || row?.write_supported === true || row?.write?.supported === true);
    }
    editableProperty(propertyId) {
      const wanted=String(propertyId || '');
      return this.editablePropertyRows().find(row => String(row.property_id || row.key || row.property_key || '') === wanted) || null;
    }
    value(key, fallback = null) { return rowValue(this.row(key), fallback); }
    number(key) { return asNumber(this.value(key, null)); }
    text(key, fallback = '—') { return human(this.value(key, fallback), fallback); }
    rawText(key, fallback = '') {
      const v = this.value(key, fallback);
      return v === undefined || v === null || v === '' ? fallback : String(v);
    }
    release() {
      const attrs = this.releaseAttrs();
      return {
        ux_version: UX_VERSION,
        backend_release: attrs.backend_release || 'unknown',
        contract_version: attrs.contract_version || 'unknown',
        release_contract_entity: RELEASE_ENTITY,
        governance_gate: attrs.governance_gate || attrs.health || this.releaseState()?.state || 'unknown',
        public_ux_entities_json: this.publicUxEntities()
      };
    }
    backendStatus() {
      // A diagnostics-only or stale canonical publication is not evidence
      // that the user-facing Energy product is healthy.
      const canonicalReady = (this.canonicalIndex?.productRows?.() || []).some(row=>
        row.availability === 'AVAILABLE' &&
        ['key_properties','details','configuration'].includes(row.presentation_surface));
      return {
        runtimeTrusted: canonicalReady,
        showMainWarning: !canonicalReady,
        failedHardGates: canonicalReady ? [] : ['canonical_property_contract'],
        diagnosticsNotes: [],
        statusText: canonicalReady
          ? 'Canonical Energy property contract active'
          : 'Canonical Energy property contract unavailable',
        warningText: canonicalReady ? '' : 'Canonical Energy properties are unavailable.'
      };
    }
    footerModel() {
      const backendStatus = this.backendStatus();
      const release=this.releaseAttrs();
      return {
        uxVersion: UX_VERSION,
        backendVersion:String(release.backend_release === 'unknown' ? 'Unknown' : (release.backend_release || 'Unknown')),
        releaseContractEntity:RELEASE_ENTITY,
        contractVersion:'RHI_ENERGY_CANONICAL_PROPERTY_V2',
        runtimeTrusted:backendStatus.runtimeTrusted,
        failedHardGates:backendStatus.failedHardGates,
        diagnosticsNotes:backendStatus.diagnosticsNotes,
        statusText:backendStatus.statusText,
        warningText:backendStatus.warningText,
        showMainWarning:backendStatus.showMainWarning
      };
    }
    canonicalProduct() {
      if (!this._canonicalProduct) this._canonicalProduct = readEnergyCanonicalProduct(this.contractGateway());
      return this._canonicalProduct;
    }
    experiencePresence() {
      return Object.freeze({...(this.canonicalProduct().presence || {})});
    }
    contractCompatibility() {
      const v2=this.canonicalProduct();
      return Object.freeze({
        available:v2.available === true,
        reason:String(v2.compatibilityReason || ''),
        release:String(v2.release || ''),
        contractVersion:String(v2.contractVersion || ''),
        capabilities:v2.capabilities || {}
      });
    }
    contractEntityId() { return this.canonicalProduct().envelope.entityId; }
    assetProjection(assetId) { return selectEnergyAsset(this.canonicalProduct(), assetId); }
    overviewProjection() { return selectEnergyOverview(this.canonicalProduct()); }
    planningProjection(horizon = 'D0') {
      const native=readPlanningContract(this,horizon);
      return Object.freeze({...native,
        lane_totals:native.laneTotals,
        planning_objects:native.planningAssets,
        source:'rhi_energy.runtime/native_metric'
      });
    }
    strategyProjection() { return selectEnergyStrategies(this.canonicalProduct()); }
    pricingProjection() { return selectEnergyPricing(this.canonicalProduct()); }
    valueProjection(period = 'today') {
      const requested=String(period || '').toLowerCase();
      const result=selectEnergyValue(this.canonicalProduct(),requested);
      const amount=result.available === true ? result.net_financial_result_eur : null;
      return Object.freeze({
        available:result.available === true,period_id:requested,
        value:Object.freeze({net_financial_result_eur:amount}),
        net_financial_result_eur:amount,
        net_financial_result:result.net_financial_result,
        quality:result.quality,actual_complete:result.actual_complete,
        reason:result.reason,source:result.source
      });
    }
    meteringProjection(period = 'today') { return selectEnergyMetering(this.canonicalProduct(), period); }
    activityProjection() { return selectEnergyActivity(this.canonicalProduct()); }
    commandProjection(assetId = '') { return selectEnergyCommands(this.canonicalProduct(), assetId); }
    coverage() { return selectEnergyCoverage(this.canonicalProduct()); }
    assets() {
      if (this._assets) return this._assets;
      const grouped=new Map();
      // The object status entity owns identity, appearance and HA parentage.
      // It may represent a structural node with zero product properties.
      for(const row of (this.canonicalIndex?.objectRows?.() || [])) {
        if(row.object_class === 'energy_configuration') continue;
        grouped.set(row.asset_id,{...row,properties:[]});
      }
      // Direct canonical properties also publish their own asset/class identity.
      // Keep this independent evidence visible when the object entity has not
      // yet been materialized; never overwrite a conflicting canonical identity.
      for(const row of (this.canonicalIndex?.productRows?.() || [])) {
        const id=String(row.asset_id || '').trim();
        const objectClass=String(row.logical_object_class || '').trim();
        if(!id || !objectClass || objectClass === 'energy_configuration' || this.canonicalIndex?.ambiguousObjects?.has(id)) continue;
        const existing=grouped.get(id);
        if(existing && existing.object_class !== objectClass) {
          grouped.delete(id); // inconsistent product authority: fail closed
          continue;
        }
        const asset=existing || {
          asset_id:id,asset_type:objectClass,object_class:objectClass,
          parent_asset_id:row.parent_asset_id || null,
          display_name:String(row.asset_display_name || id),
          integration_domain:row.integration_domain || null,properties:[]
        };
        asset.properties.push(row);
        grouped.set(id,asset);
      }
      this._assets=[...grouped.values()].map(asset=>Object.freeze({
        ...asset,properties:Object.freeze(asset.properties)
      }));
      return this._assets;
    }
    asset(assetId) { return this.assets().find(a => String(a.asset_id || '') === String(assetId)) || null; }
    assetName(assetId) { return this.asset(assetId)?.display_name || human(assetId, '—'); }
    assetField(assetId, propertyKey) {
      const direct = this.canonicalIndex?.row?.(String(assetId || ''), String(propertyKey || ''));
      if (!direct) {
        return Object.freeze({
          resolved:false,
          value:null,
          unit:'',
          status:'UNAVAILABLE',
          quality:'missing',
          reason:'canonical_property_not_published',
          source:null,
          raw:null
        });
      }
      return Object.freeze({
        resolved:direct.availability !== 'UNAVAILABLE',
        value:direct.value,
        unit:direct.unit,
        status:direct.availability,
        quality:direct.quality,
        reason:direct.reason,
        source:direct.source,
        raw:direct
      });
    }
    assetValue(assetId, propertyKey, fallback = null) {
      const field = this.assetField(assetId, propertyKey);
      return field?.resolved === true ? field.value : fallback;
    }
    assetNumber(assetId, propertyKey) {
      return asNumber(this.assetValue(assetId, propertyKey, null));
    }
    assetText(assetId, propertyKey, fallback = '') {
      const value = this.assetValue(assetId, propertyKey, fallback);
      return value === undefined || value === null || value === '' ? fallback : String(value);
    }
    childrenOfType(parentAssetId, childType = '') {
      const wanted = String(childType || '').toLowerCase();
      return this.containsChildren(parentAssetId).filter(id => {
        if (!wanted) return true;
        const asset = this.asset(id) || {};
        return [asset.asset_type, asset.object_class].some(value => String(value || '').toLowerCase() === wanted);
      });
    }
    commandContract() {
      if (!this._commandContract) this._commandContract = readEnergyCommandContract(this.contractGateway());
      return this._commandContract;
    }
    commands() {
      return this.commandContract().rows;
    }
    commandVisible(command) { return !!command && command.command_resolved === true && command.visible === true; }
    commandResolved(command) { return !!command && command.command_resolved === true; }
    commandApplicable(command) { return !!command && command.currently_applicable === true; }
    commandEnabled(command) { return !!command && command.enabled === true; }
    commandReasonObject(command) { return objectFrom(command?.reason || {}); }
    commandReason(command) {
      const model = createCommandActionModel(command);
      return model?.reason || 'Currently unavailable';
    }
    commandReasonCode(command) { return String(this.commandReasonObject(command).code || ''); }
    commandRole(command) { return String(command?.role || '').toLowerCase(); }
    commandsForAsset(assetId) { return this.commands().filter(command => String(command.target_asset_id || '') === String(assetId)); }
    commandForAssetRole(assetId, role) {
      const wanted = String(role || '').toLowerCase();
      return this.commandsForAsset(assetId).find(command => this.commandRole(command) === wanted && this.commandVisible(command)) || null;
    }
    commandActionModelsForAsset(assetId) { return commandActionModelsForAsset(this.commandContract(), assetId); }
    visibleCommands(targetAssetId = null) {
      return this.commands().filter(command => this.commandVisible(command) && (!targetAssetId || String(command.target_asset_id || '') === String(targetAssetId)));
    }
    activities() {
      if (!this._activities) this._activities = [...this.activityProjection().rows];
      return this._activities;
    }
    activity(type) { return this.activities().find(a => String(a.activity_type || '').toLowerCase() === String(type).toLowerCase()) || null; }
    decision() {
      const d = this.value('energy_intelligence.decision', null);
      if (d && typeof d === 'object') return d;
      return {
        goal: this.value('energy_intelligence.goal', ''),
        observation: this.value('energy_intelligence.observation', ''),
        assessment: this.value('energy_intelligence.assessment', ''),
        recommendation: this.value('energy_intelligence.recommendation', ''),
        automation_mode: this.value('energy_intelligence.automation_mode', ''),
        automation_status: this.value('energy_intelligence.automation_status', ''),
        status: this.value('energy_intelligence.status', ''),
        reason: this.value('energy_intelligence.reason', ''),
        confidence: this.value('energy_intelligence.confidence', ''),
        affected_assets: this.value('energy_intelligence.affected_assets', []),
        next_review: this.value('energy_intelligence.next_review', '')
      };
    }
    overviewExperience() {
      const projection=this.overviewProjection();
      return projection.available ? { entity_id:this.contractEntityId(), ...projection.raw } : null;
    }
    pilotReadiness() {
      const backend=this.backendStatus();
      // Product parity and target-HA qualification remain independent gates;
      // native property publication alone must never declare the pilot READY.
      return {
        entity_id:RELEASE_ENTITY,
        state:backend.runtimeTrusted ? 'PARTIAL' : 'UNAVAILABLE',
        contract_id:'RHI_ENERGY_CANONICAL_PROPERTY_V2',
        contract_version:'2.0.0',
        release:String(this.releaseAttrs().backend_release || ''),
        coverage:this.coverage()
      };
    }
    planningExperienceRows() {
      if (this._planningExperienceRows) return this._planningExperienceRows;
      // The same backend-owned planning assets drive all cross-screen views.
      // No separate aggregate planning_objects list or fabricated participant ID.
      this._planningExperienceRows=this.planningIndexRows().map(row=>Object.freeze({
        ...row,experience_id:String(row.experience_id || row.planning_id)
      }));
      return this._planningExperienceRows;
    }
    planningExperienceFor(assetId) {
      return this.planningExperienceRows().find(row => String(row.asset_id || row.target_asset_id || '') === String(assetId)) || null;
    }
    consumerMixIndexEntity() { return this.canonicalProduct().envelope.entityId; }
    consumerMixRows() {
      if (this._consumerMixRows) return this._consumerMixRows;
      const v2=this.canonicalProduct();
      this._consumerMixRows=(v2.flexibleAssets || []).map((raw,index)=>{
        const row=objectFrom(raw);
        const assetId=String(row.asset_id || `flexible_${index+1}`);
        const projected=this.assetProjection(assetId);
        const power=asNumber(projected?.property?.('power_kw')?.value ?? row.power_kw);
        const need=asNumber(projected?.property?.('energy_to_target_kwh')?.value ?? row.energy_to_target_kwh);
        return {
          mix_row_id:assetId,
          entity_id:v2.envelope.entityId,
          ...row,
          asset_id:assetId,
          display_name:row.display_name || this.assetName(assetId),
          category:row.asset_type || row.object_class || 'flexible_asset',
          controllability:'FLEXIBLE',
          current_power_kw:power,
          energy_today_kwh:null,
          energy_need_kwh:need,
          availability:row.availability_state || row.health || 'UNAVAILABLE',
          visible:true,
          flexible:true,
          source_refs:['RHI_ENERGY_CANONICAL_PROPERTY_V2.objects'],
          metering_state:'UNAVAILABLE',
          metering_reason:'Canonical per-asset period energy is not published by the current public contract.'
        };
      });
      return this._consumerMixRows;
    }
    consumerMixSummary() {
      if (this._consumerMixSummary) return this._consumerMixSummary;
      const rows=this.consumerMixRows();
      const power=rows.map(row=>asNumber(row.current_power_kw));
      const need=rows.map(row=>asNumber(row.energy_need_kwh)).filter(value=>value!==null);
      this._consumerMixSummary={
        current_power_kw:power.length && power.every(value=>value!==null) ? power.reduce((sum,value)=>sum+value,0) : null,
        known_energy_need_kwh:need.length ? need.reduce((sum,value)=>sum+value,0) : null,
        asset_count:rows.length,
        energy_kwh:null,
        energy_by_asset_kwh:{},
        health:'PARTIAL',
        reason:'Canonical current flexible-asset truth is available; category/per-asset period energy is not published by the current public contract.',
        source_refs:['RHI_ENERGY_CANONICAL_PROPERTY_V2.objects']
      };
      return this._consumerMixSummary;
    }
    consumerRows() {
      return this.assets().filter(a => String(a.asset_type || '') === 'consumer' && String(a.parent_asset_id || '') === 'consumer').map(asset => {
        const id = asset.asset_id;
        return {
          ...asset,
          current_power_kw: this.number(`${id}.power_kw`) ?? this.number(`${id}.current_power_kw`) ?? this.number(`${id}.actual_power_kw`),
          active: asBool(this.value(`${id}.active`, false)),
          enabled: asBool(this.value(`${id}.enabled`, false)),
          flexibility_available: asBool(this.value(`${id}.flexibility_available`, false)),
          connected: asBool(this.value(`${id}.connected`, false)),
          charging: asBool(this.value(`${id}.charging`, false)),
          min_power_kw: this.number(`${id}.min_power_kw`),
          max_power_kw: this.number(`${id}.max_power_kw`),
          effective_charger: this.value(`${id}.effective_charger`, ''),
          health: this.value(`${id}.health`, this.row(`${id}.health`).health || 'UNKNOWN')
        };
      });
    }

    flexibleRuntimePropertyRow(assetId, names) {
      const exact = [];
      names.forEach(name => {
        exact.push(`${assetId}.${name}`);
        exact.push(`${assetId}.${name.replace(/^energy_control_/, '')}`);
      });
      const direct = exact.map(key => this.row(key)).find(r => r && !r.missing);
      if (direct) return direct;
      const rows = this.propertyRows().filter(row => String(row.asset_id || '') === String(assetId));
      return rows.find(row => names.some(name => String(row.key || row.property_key || '').toLowerCase().endsWith(`.${name.toLowerCase()}`) || String(row.key || row.property_key || '').toLowerCase() === name.toLowerCase())) || { missing: true };
    }
    isDeprecatedTargetEnergyAlias(row) {
      if (!row || row.missing) return false;
      const text = `${row.key || row.property_key || ''} ${row.quality || ''} ${row.source_type || ''} ${row.resolution_mode || ''} ${row.alias_of || ''} ${row.deprecated_alias_of || ''} ${row.migration_role || ''}`.toLowerCase();
      return /deprecated|source_alias|derived_alias|alias/.test(text);
    }
    targetEnergyForAsset(assetId, sourceRow = {}) {
      const canonical = this.flexibleRuntimePropertyRow(assetId, ['energy_to_target_kwh']);
      if (canonical && !canonical.missing) return rowValue(canonical, null);
      if (sourceRow && sourceRow.energy_to_target_kwh !== undefined) return asNumber(sourceRow.energy_to_target_kwh);
      const aliases = [this.flexibleRuntimePropertyRow(assetId, ['remaining_energy_kwh']), this.flexibleRuntimePropertyRow(assetId, ['energy_needed_kwh'])];
      for (const row of aliases) {
        if (row && !row.missing && this.isDeprecatedTargetEnergyAlias(row)) return rowValue(row, null);
      }
      const rowText = `${sourceRow.alias_of || ''} ${sourceRow.deprecated_alias_of || ''} ${sourceRow.migration_role || ''} ${sourceRow.source_type || ''}`.toLowerCase();
      if (/deprecated|source_alias|derived_alias|alias/.test(rowText)) return asNumber(sourceRow.remaining_energy_kwh ?? sourceRow.energy_needed_kwh);
      return null;
    }
    normalizeFlexibleAssetRow(row) {
      const id = row.asset_id || row.flexible_asset_id || row.target_asset_id;
      // R1.59.4AKL: active flexible-load/runtime path is canonical-only.
      // Use power_kw + energy_flow_direction. Legacy actual/current power aliases are not active UX truth.
      const actual = this.number(`${id}.power_kw`) ?? asNumber(row.power_kw);
      const targetEnergy = this.targetEnergyForAsset(id, row);
      const remaining = this.number(`${id}.remaining_energy_kwh`) ?? asNumber(row.remaining_energy_kwh);
      const required = this.number(`${id}.required_energy_kwh`) ?? asNumber(row.required_energy_kwh);
      const requestedEffective = this.number(`${id}.requested_power_kw_effective`) ?? this.number(`${id}.requested_power_kw`) ?? asNumber(row.requested_power_kw_effective ?? row.requested_power_kw);
      return {
        ...row,
        asset_id: id,
        display_name: row.display_name || this.assetName(id),
        ux_asset_type: row.ux_asset_type || row.asset_type || (String(row.flexible_role || '').includes('storage') ? 'storage' : 'flexible_asset'),
        flexible_role: row.flexible_role || (String(row.asset_type || '').toLowerCase().includes('storage') ? 'storage' : 'load'),
        cluster_role: row.cluster_role || 'standalone',
        show_in_primary_ux: row.show_in_primary_ux ?? true,
        show_in_engineering: row.show_in_engineering ?? false,
        planning_enabled: row.planning_enabled ?? null,
        contributor_asset_ids: asArray(row.contributor_asset_ids),
        actual_power_kw: actual,
        current_power_kw: actual,
        power_kw: actual,
        energy_flow_direction: this.value(`${id}.energy_flow_direction`, row.energy_flow_direction || 'unknown'),
        power_direction: this.value(`${id}.energy_flow_direction`, row.energy_flow_direction || 'unknown'),
        energy_to_target_kwh: targetEnergy,
        remaining_energy_kwh: remaining,
        required_energy_kwh: required,
        energy_needed_kwh: targetEnergy,
        requested_power_kw_effective: requestedEffective,
        min_power_kw: this.number(`${id}.min_power_kw`) ?? asNumber(row.min_power_kw),
        max_power_kw: this.number(`${id}.max_power_kw`) ?? asNumber(row.max_power_kw),
        energy_control_priority: this.value(`${id}.energy_control_priority`, row.energy_control_priority ?? row.priority ?? 'normal'),
        availability_state: this.value(`${id}.availability_state`, row.availability_state || 'unknown'),
        availability_reason: this.value(`${id}.availability_reason`, row.availability_reason || ''),
        operating_state: this.value(`${id}.operating_state`, row.operating_state || 'unknown'),
        energy_control_hold_state: this.value(`${id}.energy_control_hold_state`, row.energy_control_hold_state || 'none'),
        energy_control_mode: this.value(`${id}.energy_control_mode`, row.energy_control_mode || row.current_mode || 'advice'),
        can_execute_energy_action_now: asBool(this.value(`${id}.can_execute_energy_action_now`, row.can_execute_energy_action_now), false),
        energy_planning: this.planningOutcomeFor(id),
        // Canonical producer-owned charging relation aliases. These are
        // presentation conveniences only; the values remain Mobility-owned.
        effective_charger: firstDefined(
          row.effective_charger,
          row.effective_connection_id,
          row.assigned_connection_id,
          row.physical_connection_id,
          row.charger_asset_id,
          row.connection_asset_id,
          ''
        ),
        charger_asset_id: firstDefined(
          row.charger_asset_id,
          row.effective_connection_id,
          row.assigned_connection_id,
          row.physical_connection_id,
          row.connection_asset_id,
          ''
        )
      };
    }
    flexibleAssetIndexRows() {
      if (this._flexibleAssets) return this._flexibleAssets;
      const v2=this.canonicalProduct();
      this._flexibleAssetSource='RHI_ENERGY_CANONICAL_PROPERTY_V2.flexible_assets';
      this._flexibleAssets=(v2.flexibleAssets || []).map(row=>this.normalizeFlexibleAssetRow({
        ...row,
        compatibility_fallback:false,
        contract_source:v2.envelope.entityId
      })).filter(row=>row.asset_id);
      return this._flexibleAssets;
    }
    primaryFlexibleAssets() {
      // R1.59.4AKL / R3.45.16: Solar and Consumers must use the same
      // broad Flexible Loads interpretation. The projection is already the
      // UX-safe list of Energy-controllable flexible-load assets and may
      // include the battery storage cluster. Do not restrict Solar to
      // ux_asset_type=flexible_load, Mobility/vehicle assets, or a narrow
      // cluster_role list; that hides storage_cluster rows. Visibility is
      // controlled by the projection flags only.
      return this.flexibleAssetIndexRows().filter(asset => {
        const visible = asset.visible !== undefined
          ? asBool(asset.visible, true)
          : asBool(asset.show_in_primary_ux, true);
        const showPrimary = asset.show_in_primary_ux !== undefined
          ? asBool(asset.show_in_primary_ux, true)
          : true;
        return visible && showPrimary;
      });
    }
    commandReadinessRows() {
      return this.commands();
    }
    readinessFor(assetId, role) {
      return this.commandForAssetRole(assetId, role);
    }
    commandFromReadiness(assetId, role) {
      return this.commandForAssetRole(assetId, role);
    }

    planningIndexRows() {
      if (this._planningOutcomes) return this._planningOutcomes;
      this._planningOutcomes=['D0','D1',
        ...(this.nativePlanningHorizon('D2').published === true ? ['D2'] : [])
      ].flatMap(id=>{
        const native=this.planningProjection(id);
        return native.planningAssets
          .filter(row=>row && String(row.asset_id || '').trim())
          .map(row=>Object.freeze({...row,horizon_id:id,
            planning_id:String(row.planning_id || row.id || `${id}:${row.asset_id}`),
            contract_source:'RHI_ENERGY_PLANNING_HORIZON_V1'}));
      });
      return this._planningOutcomes;
    }
    planningOutcomeFor(assetId) {
      return this.planningIndexRows().find(row => String(row.asset_id || '') === String(assetId || '')) || null;
    }

    planningHorizons() {
      // Only the two backend-supported native horizons exist. An incomplete
      // horizon remains visible as incomplete rather than vanishing or using
      // a retired aggregate to fill missing totals.
      return ['D0','D1',
        ...(this.nativePlanningHorizon('D2').published === true ? ['D2'] : [])
      ].map(id=>this.planningProjection(id).horizon);
    }
    planningHorizon(id = 'D0') {
      return this.planningProjection(id).horizon || null;
    }
    planningHorizonTotals(id = 'D0') {
      return this.planningProjection(id).lane_totals;
    }
    planningBuckets(id = 'D0') {
      return this.planningProjection(id).buckets;
    }

    relationships() {
      return this.canonicalProduct().available ? [...this.canonicalProduct().relationships] : [];
    }
    flowRelationships() {
      return this.relationships().filter(r => String(r.relationship_type || '').toLowerCase() === 'flows_to');
    }
    connectedRelationships() {
      return this.relationships().filter(r => String(r.relationship_type || '').toLowerCase() === 'connected_to');
    }
    containsChildren(parentAssetId) {
      const relChildren = this.relationships()
        .filter(r => String(r.relationship_type || '').toLowerCase() === 'contains' && String(r.source_asset_id || r.from_asset_id || '') === String(parentAssetId))
        .map(r => String(r.target_asset_id || r.to_asset_id || '')).filter(Boolean);
      const assetChildren = this.assets().filter(a => String(a.parent_asset_id || '') === String(parentAssetId)).map(a => String(a.asset_id || '')).filter(Boolean);
      return [...new Set([...relChildren, ...assetChildren])];
    }
    powerForAsset(assetId) {
      const id = String(assetId || '');
      const asset = this.asset(id) || {};
      const type = String(asset.asset_type || asset.object_class || '').toLowerCase();
      const candidatesByType = {
        battery: ['battery.power_kw','battery.charge_power_kw','battery.discharge_power_kw'],
        inverter: ['inverter.power_kw','solar.power_kw'],
        solar_inverter: ['solar.power_kw','inverter.power_kw'],
        grid_phase: ['grid_phase.power_kw'],
        flexible_load: ['flexible_load.power_kw','flexible_load.current_power_kw']
      };
      const candidates = candidatesByType[type] || ['power_kw'];
      for (const key of candidates) {
        const n = this.assetNumber(id, key);
        if (n !== null) return n;
      }
      return null;
    }
    rowsByAsset(assetId) {
      return [...this.allRows().values()].filter(row => String(row.asset_id || '') === String(assetId));
    }
    rowsByPrefix(prefix) {
      const p = String(prefix || '');
      return [...this.allRows().values()].filter(row => String(row.key || '').startsWith(p));
    }
    editableRows() {
      return [...this.allRows().values()].filter(row => asBool(row.editable, false) || String(row.access || '').toLowerCase() === 'editable');
    }
    strategyIntentRows() { return []; }
    strategyProfileRows() {
      if (this._strategyProfiles) return this._strategyProfiles;
      const v2=this.canonicalProduct();
      // Settings grouping is Energy-owned. UX consumes the published groups and
      // never rebuilds them from property-name/group heuristics.
      this._strategyProfiles=asArray(v2.configuration?.strategy?.profiles).map(raw=>{
        const profile=objectFrom(raw);
        const profileId=String(profile.profile_id || '');
        const configured=asArray(profile.configured_properties).map(row=>({
          entity_id:v2.envelope.entityId,
          ...objectFrom(row),
          profile_id:profileId,
          strategy_profile_id:profileId
        }));
        return {
          ...profile,
          strategy_id:profileId,
          profile_id:profileId,
          profile_type:profileId,
          asset_type:profileId,
          profile_label:profile.display_name || human(profileId),
          display_name:profile.display_name || human(profileId),
          entity_id:v2.envelope.entityId,
          contract_role:'editable_strategy_profile',
          editable_field_rows:configured.filter(row=>canonicalEditableProperty(row)),
          properties:configured,
          effective_properties:asArray(profile.effective_properties)
        };
      }).filter(profile=>profile.profile_id);
      return this._strategyProfiles;
    }
    strategyProfileFor(profileId) {
      const wanted = String(profileId || '').toLowerCase();
      if (!wanted) return null;
      return this.strategyProfileRows().find(row => String(row.profile_id || '').toLowerCase() === wanted || String(row.profile_type || '').toLowerCase() === wanted || String(row.asset_type || '').toLowerCase() === wanted) || null;
    }
    strategyProfileEditableFieldRows(profile = {}) {
      const profileId=String(profile.profile_id || profile.strategy_profile_id || '').trim().toLowerCase();
      if (!profileId) return [];
      const labels={
        objective:'Objective', surplus_objective:'Objective', reserve_target_pct:'Minimum reserve',
        minimum_target_value:'Minimum target', preferred_target_value:'Preferred target', maximum_useful_value:'Maximum useful',
        deadline:'Default deadline', deadline_time:'Default deadline', grid_policy:'Grid policy', solar_policy:'Solar policy',
        battery_policy:'Home Battery policy', surplus_policy:'Surplus policy', confidence_policy:'Confidence',
        minimum_run_minutes:'Minimum run time', minimum_off_minutes:'Minimum off time', adjust_deadband_kw:'Deadband'
      };
      return asArray(profile.editable_field_rows).map(row=>{
        const key=String(row.property_id || row.key || row.property_key || '');
        const suffix=key.split('.').pop();
        return {
          ...row,
          entity_id:this.canonicalProduct().envelope.entityId,
          source_index:'RHI_ENERGY_CANONICAL_PROPERTY_V2.configuration.strategy',
          contract_role:'canonical_strategy_property',
          profile_id:profileId,
          strategy_profile_id:profileId,
          field_key:suffix,
          display_name:firstDefined(row.display_name,row.label,labels[suffix],human(suffix)),
          allowed_values:firstDefined(row.allowed_values,row.choices,objectFrom(row.constraints).allowed,[]),
          min:firstDefined(row.min,objectFrom(row.constraints).min,''),
          max:firstDefined(row.max,objectFrom(row.constraints).max,''),
          step:firstDefined(row.step,objectFrom(row.constraints).step,''),
          editable_reason:firstDefined(row.reason_text,row.reason_code,'Canonical public property is not writable')
        };
      });
    }
    strategyProfileEditableRowByKey(propertyKey) {
      const key = String(propertyKey || '');
      if (!key) return null;
      for (const profile of this.strategyProfileRows()) {
        const hit = this.strategyProfileEditableFieldRows(profile).find(row => String(row.key || row.property_key || '') === key);
        if (hit) return hit;
      }
      return null;
    }
    settingsParticipationRows() {
      const v2=this.canonicalProduct();
      return asArray(v2.configuration?.strategy?.participating_assets)
        .map(row=>objectFrom(row))
        .filter(row=>row.asset_id);
    }
    effectiveStrategyRows() {
      if (this._effectiveStrategies) return this._effectiveStrategies;
      const v2=this.canonicalProduct();
      const rows=asArray(v2.configuration?.strategy?.effective?.properties);
      const byGroup=new Map();
      rows.forEach(raw=>{
        const row=objectFrom(raw);
        const group=String(row.group || row.asset_id || 'home');
        const current=byGroup.get(group) || {
          strategy_id:group, policy_id:group, asset_id:group,
          entity_id:v2.envelope.entityId,
          contract_role:'effective_strategy_policy',
          effective_state:v2.configuration?.strategy?.effective?.status || 'UNAVAILABLE',
          reason_code:v2.configuration?.strategy?.effective?.reason || ''
        };
        const key=String(row.property_id || row.key || row.property_key || '');
        if(key) current[key]=row.value;
        current.properties=[...(current.properties || []),row];
        byGroup.set(group,current);
      });
      this._effectiveStrategies=[...byGroup.values()];
      return this._effectiveStrategies;
    }
    strategyBehaviorTopics() {
      const v2=this.canonicalProduct();
      return asArray(v2.configuration?.strategy?.behavior_topics)
        .map(row=>objectFrom(row))
        .filter(row=>row.topic_id)
        .sort((a,b)=>(asNumber(a.display_order) ?? 999) - (asNumber(b.display_order) ?? 999));
    }
    effectiveStrategyFor(assetId) {
      return this.effectiveStrategyRows().find(row => String(row.asset_id || '') === String(assetId || '')) || null;
    }
    commandState(command) {
      if (!this.commandVisible(command)) return 'hidden';
      return this.commandEnabled(command) ? 'enabled' : 'disabled';
    }
    statusForKeys(keys) {
      const rows = asArray(keys).map(key => this.row(key));
      if (!rows.length) return 'unknown';
      const states = rows.map(row => rowState(row));
      if (states.includes('fail')) return 'fail';
      if (states.includes('warn')) return 'warn';
      if (states.every(s => s === 'missing')) return 'missing';
      if (states.includes('not-measured')) return 'not-measured';
      if (states.includes('unknown')) return 'unknown';
      return 'ok';
    }

    outlookHorizons() {
      if (!this._outlookHorizons) this._outlookHorizons=this.planningHorizons();
      return this._outlookHorizons;
    }
    meteringHorizons() {
      if (!this._meteringHorizons) {
        this._meteringHorizons=this.planningHorizons().map(row=>({ ...row, contract_kind:'metering_context' }));
      }
      return this._meteringHorizons;
    }
    meteringPeriods() {
      if (this._meteringPeriods) return this._meteringPeriods;
      const v2=this.canonicalProduct();
      const periods=objectFrom(v2.metering?.periods || {});
      const labels={hour:'This hour',today:'Today',day:'Today',week:'This week',month:'This month',year:'This year'};
      const order={hour:0,today:1,day:1,week:2,month:3,year:4};
      this._meteringPeriods=Object.entries(periods).map(([period_id,raw])=>{
        const id=String(period_id).toLowerCase();
        const row=objectFrom(raw);
        return {
          entity_id:v2.envelope.entityId,
          period_id:id,
          label:labels[id] || human(id),
          selector_order:order[id] ?? 99,
          graph_support:false,
          bucket_support:false,
          ...row,
          summary:objectFrom(row.summary),
          measurement_state:String(firstDefined(row.measurement_state,row.availability,'UNAVAILABLE')),
          quality:String(firstDefined(row.quality,row.summary?.quality?.period,'UNKNOWN')),
          user_action_required:asBool(firstDefined(row.user_action_required,row.baseline_reset_required,false),false)
        };
      }).sort((a,b)=>(a.selector_order??99)-(b.selector_order??99));
      return this._meteringPeriods;
    }
    valuePeriods() {
      if (this._valuePeriods) return this._valuePeriods;
      const periods=objectFrom(this.canonicalProduct().valueAccounting?.periods || {});
      const labels={hour:'This hour',today:'Today',week:'This week',month:'This month',year:'This year'};
      const order={hour:0,today:1,week:2,month:3,year:4};
      this._valuePeriods=Object.entries(periods)
        .filter(([id])=>Object.hasOwn(order,id))
        .map(([id,raw])=>{
          const row=objectFrom(raw);
          const amount=row.available === true && typeof row.net_financial_result_eur === 'number'
            && Number.isFinite(row.net_financial_result_eur) ? row.net_financial_result_eur : null;
          return Object.freeze({
            entity_id:row.entity_id || null,period_id:id,label:labels[id],
            selector_order:order[id],available:amount !== null,
            net_financial_result_eur:amount,actual_complete:row.actual_complete === true,
            summary:{cost:{net_financial_result_eur:amount},
              quality:{financial:row.quality || 'UNKNOWN'}},
            reason:row.reason || ''
          });
        })
        .sort((a,b)=>a.selector_order-b.selector_order);
      return this._valuePeriods;
    }
    meteringRemediations() {
      if (this._meteringRemediations) return this._meteringRemediations;
      this._meteringRemediations=this.commands()
        .filter(command=>command.command_id === 'energy.command.reset_metering_baseline' && command.visible === true)
        .map(command=>({
          remediation_id:command.command_instance_id || command.command_row_id,
          period_id:String(command.period_id || '').toLowerCase(),
          command_id:command.command_id,
          command,
          applicable:true,
          requires_confirmation:command.requires_confirmation !== false
        }));
      return this._meteringRemediations;
    }
    meteringRemediationsForPeriod(periodId) {
      const wanted = String(periodId || '').toLowerCase();
      return this.meteringRemediations().filter(row => !row.period_id || !wanted || row.period_id === wanted);
    }
    meteringResetCommandFor(remediation = {}, periodId = '') {
      const commandId = String(firstDefined(remediation.command_id,remediation.command_ref,remediation.command_key,'') || '');
      if (!commandId) return null;
      return this.commands().find(command => String(command.command_id || '') === commandId && command.visible === true) || null;
    }
    meteringResetRemediationForPeriod(periodId = '') {
      return this.meteringRemediationsForPeriod(periodId)[0] || null;
    }

    commandBindingMismatches() {
      return this.commands().filter(command =>
        !command.command_id
        || !command.target_asset_id
        || !command.role
        || !command.invoke
        || typeof command.visible !== 'boolean'
        || typeof command.enabled !== 'boolean'
        || !command.label
        || (!command.enabled && !String(firstDefined(command.blocked_reason,command.user_action_text,'')))
      ).map(command => ({
        command_instance_id:command.command_instance_id || command.command_row_id || '',
        target_asset_id:command.target_asset_id || '',
        role:command.role || '',
        problem:'invalid_R1_89_39_public_command_shape'
      }));
    }

    coverageReport() {
      const rows = [...this.allRows().values()];
      return {
        release: this.release(),
        allowed_public_entities: this.publicUxEntities().length,
        assets: this.assets().length,
        properties: rows.length,
        commands: this.commands().length,
        activities: this.activities().length,
        relationships: this.relationships().length,
        strategy_profiles: this.strategyProfileRows().length,
        effective_strategies: this.effectiveStrategyRows().length,
        flow_relationships: this.flowRelationships().length,
        command_binding_mismatches: this.commandBindingMismatches(),
        connected_relationships: this.connectedRelationships().length,
        missing_core_keys: [
          'solar.power_kw','forecast.solar_today_kwh','forecast.next_hour_energy_kwh','battery.soc_pct','home_consumption.power_kw','energy_intelligence.recommendation'
        ].filter(key => this.row(key).missing)
      };
    }
  }

  const firstDefined = (...values) => values.find(value => value !== undefined && value !== null && value !== '');
  const objectFrom = (value) => {
    const parsed = parseMaybeJson(value, value);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
  };
  const splitService = (service) => {
    const text = String(service || '').trim();
    if (!text || !text.includes('.')) return { domain: '', action: '' };
    const [domain, ...rest] = text.split('.');
    return { domain, action: rest.join('.') };
  };
  const allowedValuesForRow = (row) => {
    if (!row || typeof row !== 'object') return [];
    const validation = objectFrom(row.validation);
    let values = firstDefined(row.allowed_values, row.allowedValues, row.options, row.choices, validation.allowed_values, validation.options, validation.choices);
    if (!values && typeof row.validation === 'string' && row.validation.includes('|')) values = row.validation.split('|');
    return asArray(values).map(v => (v && typeof v === 'object') ? (v.value ?? v.id ?? v.key ?? v.label ?? v.name) : v).filter(v => v !== undefined && v !== null && v !== '');
  };
  const coerceAllowedValue = (row, value) => {
    const allowed = allowedValuesForRow(row);
    if (!allowed.length) return value;
    const wanted = String(value ?? '').trim().toLowerCase();
    const hit = allowed.find(v => String(v).trim().toLowerCase() === wanted)
      || allowed.find(v => human(v, '').trim().toLowerCase() === wanted)
      || allowed.find(v => String(v).replace(/[\s_\-]+/g, '').toLowerCase() === wanted.replace(/[\s_\-]+/g, ''));
    return hit ?? value;
  };
  const valueAtPath = (source, path) => {
    if (!source || !path) return undefined;
    const parts = String(path).split('.').filter(Boolean);
    let current = source;
    for (const part of parts) {
      if (current === undefined || current === null || typeof current !== 'object') return undefined;
      current = current[part];
    }
    return current;
  };
  const renderTemplateValue = (value, context = {}) => {
    if (Array.isArray(value)) return value.map(item => renderTemplateValue(item, context));
    if (value && typeof value === 'object') {
      return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, renderTemplateValue(v, context)]));
    }
    if (typeof value !== 'string') return value;
    const replaced = value.replace(/{{\s*([a-zA-Z0-9_\.]+)\s*}}/g, (_, key) => {
      const direct = context[key];
      const nested = valueAtPath(context, key);
      const result = direct !== undefined ? direct : nested;
      return result === undefined || result === null ? '' : String(result);
    });
    return replaced;
  };
  const renderPayloadTemplate = (template, context = {}) => {
    if (template === undefined || template === null || template === '') return {};
    const parsed = parseMaybeJson(template, template);
    const rendered = renderTemplateValue(parsed, context);
    if (typeof rendered === 'string') return objectFrom(parseMaybeJson(rendered, {}));
    return objectFrom(rendered);
  };


  // ---- src/domain/models/flexible-asset-model.js ----
class FlexibleAssetDomainModel {
    constructor(runtime) {
      this.runtime = runtime;
      this._all = null;
      this._byId = null;
    }
    assetContext(asset = {}) {
      const id = String(firstDefined(asset.asset_id, asset.flexible_asset_id, asset.target_asset_id, ''));
      if (!id || typeof readEnergyAssetContext !== 'function') return { available:false, asset:null, profile:null, publication:null };
      return readEnergyAssetContext(this.runtime.contractGateway(), id);
    }
    isInfrastructure(asset = {}) {
      const sourceContext = asset.source_context && typeof asset.source_context === 'object' ? asset.source_context : {};
      const mobilityContext = sourceContext.mobility && typeof sourceContext.mobility === 'object' ? sourceContext.mobility : {};
      const values = [
        asset.participation_state,
        asset.source_asset_kind,
        asset.asset_type,
        asset.object_class,
        asset.energy_asset_role,
        mobilityContext.consumer_fallback
      ].map(value => String(value || '').trim().toLowerCase());
      return asset.infrastructure_only === true
        || values.includes('infrastructure_only')
        || values.includes('unassigned_charger')
        || values.includes('charger')
        || values.includes('connection');
    }
    isStorage(asset = {}) {
      const context = this.assetContext(asset);
      const values = [
        context.asset?.asset_type,
        context.profile?.asset_type,
        asset.energy_asset_role,
        asset.asset_type,
        asset.ux_asset_type,
        asset.flexible_role,
        asset.category
      ].map(value => String(value || '').trim().toLowerCase()).filter(Boolean);
      return values.some(value => ['battery','battery_system','storage','storage_cluster'].includes(value));
    }
    planningFor(assetId) {
      return this.runtime.planningOutcomeFor(assetId) || {};
    }
    participationState(asset = {}, planning = {}) {
      if (this.isStorage(asset)) return 'storage';
      if (this.isInfrastructure(asset)) return 'infrastructure_only';
      const context = this.assetContext(asset);
      const explicit = String(firstDefined(
        context.asset?.participation_state,
        asset.participation_state,
        asset.automation_participation,
        asset.planning_participation,
        ''
      ) || '').trim().toLowerCase();
      if (['disabled','excluded','off','not_participating','not participating'].includes(explicit)) return 'disabled';
      if (['participating','enabled','active'].includes(explicit)) {
        const availability = String(firstDefined(context.asset?.availability_state, asset.availability_state, '') || '').trim().toLowerCase();
        return ['unavailable','disconnected','offline','blocked'].includes(availability) ? 'temporarily_unavailable' : 'participating';
      }
      const lifecycle = String(firstDefined(asset.lifecycle_state, asset.lifecycle_status, '') || '').trim().toLowerCase();
      if (['disabled','inactive'].includes(lifecycle)) return 'disabled';
      return 'unknown';
    }
    operationalState(asset = {}, planning = {}) {
      const context = this.assetContext(asset);
      const raw = String(firstDefined(
        context.asset?.operating_state,
        asset.operating_state,
        asset.operation_state,
        planning.product_state,
        planning.state,
        planning.status,
        ''
      ) || '').trim().toLowerCase();
      const aliases = {
        charging:'active', running:'active', executing:'active',
        selected:'planned', pending:'waiting',
        offline:'unavailable', disconnected:'unavailable', blocked:'unavailable',
        hold:'paused'
      };
      const normalized = aliases[raw] || raw;
      return ['paused','starting','stopping','active','planned','waiting','unavailable','idle'].includes(normalized)
        ? normalized
        : 'unknown';
    }
    build(asset = {}) {
      const id = String(firstDefined(asset.asset_id, asset.flexible_asset_id, asset.target_asset_id, ''));
      const planning = this.planningFor(id);
      const context = this.assetContext(asset);
      // Materialize one UX asset from two canonical views of the same V2 object:
      // core.flexible.assets owns participation/planning semantics, while objects[]
      // carries richer producer identity such as visual_ref and charger linkage.
      // No semantic inference or cross-domain lookup is performed here.
      const materialized = context.asset
        ? {
            // Energy object context enriches the producer-owned flexible row.
            // Producer identity must win for visual_ref, asset kind and connection semantics.
            ...context.asset,
            ...asset,
            asset_id:id,
            visual_ref:String(firstDefined(asset.visual_ref, context.asset.visual_ref, '') || '')
          }
        : { ...asset, asset_id:id };
      const participation = this.participationState(materialized, planning);
      return {
        id,
        raw: materialized,
        planning,
        profile: context.profile,
        profileId: String(materialized.profile_id || context.profile?.profile_id || ''),
        publication: context.publication,
        visualRef: String(firstDefined(materialized.visual_ref, '') || ''),
        visual: typeof this.runtime.resolveVisualRef === 'function'
          ? this.runtime.resolveVisualRef(firstDefined(materialized.visual_ref, ''), 'card')
          : null,
        publicationGap: typeof energyAssetPublicationGap === 'function'
          ? energyAssetPublicationGap(this.runtime.contractGateway(), id)
          : { status:'unavailable', missing:[] },
        participation,
        operation: this.operationalState(materialized, planning),
        isStorage: participation === 'storage',
        isInfrastructure: participation === 'infrastructure_only',
        isDisabled: participation === 'disabled',
        isParticipating: participation === 'participating' || participation === 'temporarily_unavailable',
        isTemporarilyUnavailable: participation === 'temporarily_unavailable'
      };
    }
    all() {
      if (!this._all) {
        this._all = this.runtime.primaryFlexibleAssets().map(asset => this.build(asset));
        this._byId = new Map(this._all.map(vm => [vm.id, vm]));
      }
      return this._all;
    }
    byId(assetId) { this.all(); return this._byId.get(String(assetId)) || null; }
    // Only a genuine flexible-load consumer is a consumption identity.
    // Producer-owned charger/connection fallback projections may also have
    // object_class=flexible_load; those remain connection infrastructure, not
    // consumers to count or render a second time.
    consumerFacing() { return this.all().filter(vm => !vm.isStorage && !vm.isInfrastructure && String(vm.raw?.object_class || '') === 'flexible_load'); }
    // Unknown participation is an inventory/readiness gap, not an active plan.
    inventory() { return this.consumerFacing(); }
    participating() { return this.consumerFacing().filter(vm => vm.isParticipating); }
    planningParticipants() {
      // Backend-owned readiness is positive evidence. Unknown/missing does
      // not mean eligible and must never synthesize a schedulable consumer.
      return this.participating().filter(vm => vm.raw?.planning_input_ready === true);
    }
    disabled() { return this.consumerFacing().filter(vm => vm.isDisabled); }
    infrastructure() { return this.all().filter(vm => vm.isInfrastructure); }
    storage() { return this.all().filter(vm => vm.isStorage); }
    planningRows() {
      const published = new Map(this.runtime.planningIndexRows().map(row => [String(row.asset_id || row.consumer_id || row.id || ''), row]));
      return this.planningParticipants().map(vm => {
        const row = published.get(vm.id) || vm.planning || {};
        return {
          ...row,
          asset_id: vm.id,
          participation_state: vm.participation,
          operational_state: vm.operation,
          status: vm.operation,
          state: vm.operation,
          waiting: vm.operation === 'waiting',
          planned: vm.operation === 'planned',
          active: vm.operation === 'active',
          paused: vm.operation === 'paused'
        };
      });
    }
    summary() {
      const rows = this.planningRows();
      return {
        participating_count: rows.length,
        disabled_count: this.disabled().length,
        storage_count: this.storage().length,
        infrastructure_count: this.infrastructure().length,
        waiting_count: rows.filter(row => row.operational_state === 'waiting').length,
        planned_count: rows.filter(row => row.operational_state === 'planned').length,
        active_count: rows.filter(row => row.operational_state === 'active').length,
        paused_count: rows.filter(row => row.operational_state === 'paused').length,
        temporarily_unavailable_count: rows.filter(row => row.participation_state === 'temporarily_unavailable').length
      };
    }
    physicalFlowParticipants() {
      const relationships = this.runtime.connectedRelationships();
      const related = new Set();
      relationships.forEach(rel => {
        if (rel.from_asset_id) related.add(String(rel.from_asset_id));
        if (rel.to_asset_id) related.add(String(rel.to_asset_id));
      });
      return this.participating().filter(vm => {
        const asset = vm.raw || {};
        const measured = asNumber(firstDefined(asset.current_power_kw, asset.actual_power_kw, asset.power_kw, this.runtime.number(`${vm.id}.current_power_kw`), this.runtime.number(`${vm.id}.power_kw`))) || 0;
        const connectionState = String(firstDefined(asset.connection_state, '') || '').trim().toLowerCase();
        const connected = asBool(firstDefined(asset.connected, this.runtime.value(`${vm.id}.connected`, false)), false)
          || ['connected','asset_connected'].includes(connectionState);
        const charger = firstDefined(
          asset.effective_charger,
          asset.effective_connection_id,
          asset.assigned_connection_id,
          asset.physical_connection_id,
          asset.charger_asset_id,
          asset.connection_asset_id,
          asset.execution_target_asset_id,
          ''
        );
        return measured > 0.05 || connected || related.has(vm.id) || Boolean(charger) || (charger && related.has(String(charger)));
      });
    }
  }

  // ---- src/domain/planning/contract-adapter.js ----
// Canonical support is capability-based. R1.79.3 compatibility is deliberately bounded to the
// published bucket fields and must not become a second planning owner.
  function planningArray(value) {
    const parsed = parseMaybeJson(value, value);
    return Array.isArray(parsed) ? parsed : [];
  }

  function planningParticipantId(row = {}) {
    return String(firstDefined(row.participant_id, row.asset_id, row.target_asset_id, row.flexible_asset_id, ''));
  }

  function planningEnergyFromPower(row = {}, durationMinutes = 60) {
    const direct = asNumber(firstDefined(row.planned_demand_kwh, row.planned_supply_kwh, row.planned_energy_kwh, row.energy_kwh));
    if (direct !== null) return direct;
    const power = asNumber(firstDefined(row.planned_power_kw, row.power_kw, row.allocated_power_kw));
    return power === null ? null : power * Math.max(0, asNumber(durationMinutes) || 60) / 60;
  }

  function signedPlanningGrid(bucket = {}) {
    const signed = asNumber(firstDefined(bucket.grid_net_kwh, bucket.expected_grid_net_kwh, bucket.net_grid_kwh, bucket.grid_kwh));
    if (signed !== null) return { importKwh: Math.max(0, signed), exportKwh: Math.max(0, -signed) };
    return {
      importKwh: asNumber(firstDefined(bucket.expected_grid_import_kwh, bucket.grid_import_kwh)),
      exportKwh: asNumber(firstDefined(bucket.expected_grid_export_kwh, bucket.grid_export_kwh))
    };
  }

  function adaptPlanningBucket(bucket = {}, contractVersion = '') {
    const version = String(contractVersion || '');
    if (version === 'ENERGY_NATIVE_PLANNING') {
      // The canonical D0/D1 producer publishes bucket facts directly. Never
      // derive kWh from power/time, invent Home or Grid lane occupants, or
      // promote an old R1.79.x advisory transport to native authority.
      const durationMinutes=asNumber(bucket.duration_minutes);
      const allocations=planningArray(bucket.asset_allocations);
      // Authoritative Energy interval lanes are published as advisory_*.
      // No power-to-energy or consumer inference is permitted in this adapter.
      const sourceRows=planningArray(firstDefined(bucket.advisory_source_lane,bucket.source_lane));
      const consumerRows=planningArray(firstDefined(bucket.advisory_consumer_lane,bucket.consumer_lane));
      const boundary=objectFrom(firstDefined(bucket.advisory_boundary_flows,bucket.boundary_flows,{}));
      const nativeRow=(row,role)=>({
        ...row, participantId:planningParticipantId(row),laneRole:role,
        energyKwh:asNumber(firstDefined(row.planned_energy_kwh,row.planned_demand_kwh,row.planned_supply_kwh)),
        powerKw:asNumber(firstDefined(row.planned_power_kw,row.power_kw)),
        state:String(firstDefined(row.planning_state,row.state,row.status,'')||'').toLowerCase(),
        allocationState:String(firstDefined(row.allocation_state,'')||'').toLowerCase(),
        executionAllowed:firstDefined(row.plan_execution_allowed,null),
        reason:firstDefined(row.reason_code,row.reason,'')
      });
      const consumers=consumerRows.length?consumerRows.map(row=>nativeRow(row,'consumer'))
        :allocations.map(row=>nativeRow(row,'consumer'));
      return {
        raw:bucket,
        id:String(firstDefined(bucket.bucket_id,bucket.id,'')),
        startTime:firstDefined(bucket.start_time,bucket.start,bucket.bucket_start,''),
        endTime:firstDefined(bucket.end_time,bucket.end,bucket.bucket_end,''),
        durationMinutes,
        sources:sourceRows.map(row=>nativeRow(row,'source')),
        consumers,
        boundary:{gridExportKwh:asNumber(firstDefined(boundary.grid_export_kwh,bucket.grid_export_kwh))},
        balanceDeltaKwh:asNumber(firstDefined(bucket.advisory_lane_balance_delta_kwh,bucket.balance_delta_kwh)),
        state:String(firstDefined(bucket.planning_state,bucket.state,'')||'').toLowerCase(),
        reason:firstDefined(bucket.reason_code,bucket.reason,''),
        confidence:firstDefined(bucket.confidence,''),
        forecastQuality:firstDefined(bucket.forecast_quality,''),
        disclosure:firstDefined(bucket.estimation_disclosure,''),
        canonicalLanes:sourceRows.length>0||consumerRows.length>0,
        contractSupported:true,contractFamily:'ENERGY_NATIVE_PLANNING'
      };
    }
    const isR1794 = ['advisory_source_lane','advisory_consumer_lane','advisory_boundary_flows','advisory_lane_balance_delta_kwh']
      .some(key => Object.prototype.hasOwnProperty.call(bucket, key));
    const isR1793 = version.includes('R1.79.3');
    if (!isR1794 && !isR1793) return { raw:bucket, id:String(firstDefined(bucket.bucket_id,bucket.id,'')), startTime:firstDefined(bucket.start_time,bucket.start,bucket.bucket_start,''), endTime:firstDefined(bucket.end_time,bucket.end,bucket.bucket_end,''), durationMinutes:asNumber(bucket.duration_minutes)||60, sources:[], consumers:[], boundary:{gridExportKwh:null}, balanceDeltaKwh:null, state:'unavailable', reason:'unsupported_planning_contract', confidence:'', forecastQuality:'', disclosure:'', canonicalLanes:false, contractSupported:false, contractFamily:'unsupported' };
    const durationMinutes = asNumber(bucket.duration_minutes) || 60;
    const canonicalSources = planningArray(bucket.advisory_source_lane);
    const canonicalConsumers = planningArray(bucket.advisory_consumer_lane);
    const hasCanonicalLanes = isR1794;
    let sources = canonicalSources;
    let consumers = canonicalConsumers;
    let boundary = objectFrom(parseMaybeJson(bucket.advisory_boundary_flows, bucket.advisory_boundary_flows || {}));

    if (!hasCanonicalLanes) {
      const grid = signedPlanningGrid(bucket);
      const allocations = planningArray(firstDefined(bucket.asset_allocations, bucket.asset_allocations_json, []));
      sources = [
        { participant_id:'solar', display_name:'Solar', participant_type:'producer', lane_role:'source', flow_direction:'production', planned_supply_kwh:asNumber(bucket.solar_forecast_kwh), planning_state:'forecast', forecast_quality:bucket.forecast_quality },
        { participant_id:'grid', display_name:'Grid', participant_type:'grid_connection', lane_role:'source', flow_direction:(grid.importKwh || 0) > 0 ? 'import' : 'idle', planned_supply_kwh:grid.importKwh, planning_state:(grid.importKwh || 0) > 0 ? 'residual_supply' : 'not_required' }
      ];
      consumers = [
        { participant_id:'home', display_name:'Home', participant_type:'fixed_consumer', lane_role:'consumer', flow_direction:'consume', planned_demand_kwh:asNumber(bucket.base_demand_forecast_kwh), planning_state:'forecast' },
        ...allocations.map(row => ({ ...row, participant_id:planningParticipantId(row), lane_role:'consumer', flow_direction:'charge', planned_demand_kwh:planningEnergyFromPower(row, durationMinutes), allocation_state:firstDefined(row.allocation_state, 'advisory') }))
      ];
      boundary = { grid_export_kwh:grid.exportKwh };
    }

    const normalize = (row, laneRole) => ({
      ...row,
      participantId: planningParticipantId(row),
      laneRole,
      energyKwh: planningEnergyFromPower(row, durationMinutes),
      powerKw: asNumber(firstDefined(row.planned_power_kw, row.power_kw, row.allocated_power_kw)),
      state: String(firstDefined(row.planning_state, row.state, row.status, '') || '').toLowerCase(),
      allocationState: String(firstDefined(row.allocation_state, '') || '').toLowerCase(),
      executionAllowed: firstDefined(row.plan_execution_allowed, null),
      reason: firstDefined(row.reason_label, row.user_reason_label, row.reason_code, row.reason, '')
    });
    const normalizedSources = sources.map(row => normalize(row, 'source'));
    const normalizedConsumers = consumers.map(row => normalize(row, 'consumer'));
    return {
      raw: bucket,
      id: String(firstDefined(bucket.bucket_id, bucket.id, '')),
      startTime: firstDefined(bucket.start_time, bucket.start, bucket.bucket_start, ''),
      endTime: firstDefined(bucket.end_time, bucket.end, bucket.bucket_end, ''),
      durationMinutes,
      sources: normalizedSources,
      consumers: normalizedConsumers,
      boundary: { gridExportKwh: asNumber(firstDefined(boundary.grid_export_kwh, boundary.export_kwh)) },
      balanceDeltaKwh: asNumber(bucket.advisory_lane_balance_delta_kwh),
      state: String(firstDefined(bucket.planning_state, bucket.state, '') || '').toLowerCase(),
      reason: firstDefined(bucket.reason_label, bucket.reason_code, bucket.reason, ''),
      confidence: firstDefined(bucket.confidence, ''),
      forecastQuality: firstDefined(bucket.forecast_quality, ''),
      disclosure: firstDefined(bucket.estimation_disclosure, ''),
      canonicalLanes: hasCanonicalLanes
      ,contractSupported: true
      ,contractFamily: isR1794 ? 'R1.79.4' : 'R1.79.3'
    };
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { adaptPlanningBucket, signedPlanningGrid, planningEnergyFromPower };

// ---- src/domain/planning/planning-contract.js ----
// Authoritative Planning contract reader. No cross-domain fallback and no business recalculation.
  function planningObject(value) {
    const parsed = parseMaybeJson(value, value);
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
  }
  function planningRows(value) {
    const parsed = parseMaybeJson(value, value);
    if (Array.isArray(parsed)) return parsed;
    if (parsed && typeof parsed === 'object') return Object.values(parsed);
    return [];
  }
  function planningById(value) {
    const parsed = parseMaybeJson(value, value);
    if (Array.isArray(parsed)) {
      return Object.fromEntries(parsed.map((row, index) => [
        String(row?.horizon_id || row?.id || (index === 0 ? 'D0' : 'D1')).toUpperCase(),
        planningObject(row)
      ]));
    }
    return planningObject(parsed);
  }
  function readPlanningContract(runtime, horizonId = 'D0') {
    const normalized=String(horizonId || '').toUpperCase();
    const today=runtime.nativePlanningTotals('D0');
    const tomorrow=runtime.nativePlanningTotals('D1');
    const supported=['D0','D1','D2'].includes(normalized);
    // D2 has a canonical provider-owned horizon sensor when the native 48h
    // result crosses into a third calendar day, but no full six-KPI numeric
    // scalar set is published for that incomplete rolling horizon. Never
    // populate D2 totals from D0/D1 or client-side bucket arithmetic.
    const dayAfter=Object.freeze({
      available:false,
      missing:['native_d2_scalar_totals_unavailable'],
      values:{},
    });
    const selected=normalized==='D2' ? dayAfter
      : supported ? (normalized==='D1' ? tomorrow : today) : {
      available:false, missing:['unsupported_planning_horizon'], values:{}
    };
    const nativeHorizon = supported && typeof runtime.nativePlanningHorizon === 'function'
      ? runtime.nativePlanningHorizon(normalized) : null;
    // Keep incomplete native evidence and baseline preview visible; it does
    // not obtain action authority or masquerade as the selected provider.
    const effectivePublished=nativeHorizon?.published===true && nativeHorizon?.details ? nativeHorizon : null;
    const baseline=(!effectivePublished && typeof runtime.nativePlanningHorizon==='function')
      ? runtime.nativePlanningHorizon(normalized,'baseline') : null;
    const published=effectivePublished || (baseline?.published===true && baseline.details ? baseline : null);
    const previewOnly=!!published && (published!==effectivePublished || published.available!==true);
    const horizonDetails=published?.details || {};
    const publicationMetadata = nativeHorizon?.metadata || {};
    // Native numeric totals remain available as measurement evidence but never
    // authorize an effective schedule without one quality-complete horizon.
    const effectiveAvailable = selected.available===true && effectivePublished?.available===true;
    const publicationStatus = effectiveAvailable ? 'AVAILABLE' :
      published ? 'INCOMPLETE' : nativeHorizon?.status || 'UNAVAILABLE';
    const requestedProvider=String(publicationMetadata.requested_provider||'');
    const effectiveProvider=String(publicationMetadata.provider_id||'');
    const providerHold=!!requestedProvider&&!effectiveProvider;
    const planningAssets = published && Array.isArray(horizonDetails.planning_assets)
      ? horizonDetails.planning_assets : [];

    const totals=reader=>Object.fromEntries(Object.entries(reader.values).map(([key,row])=>
      [key,row.available ? Number(row.value) : null]));
    // Preserve native producer semantics.  Numeric KPI projections are not a
    // substitute for the horizon's Supply / Demand / Balance publication.
    // A deterministic baseline remains visibly preview-only and cannot grant
    // planning/execution authority.
    const nativeSummary=Object.freeze({
      ...planningObject(horizonDetails.summary),
      supply:planningObject(horizonDetails.supply),
      demand:planningObject(horizonDetails.demand),
      balance:planningObject(horizonDetails.balance),
      known_demand_projection:planningObject(horizonDetails.known_demand_projection),
      mode:planningObject(horizonDetails.mode),
      quality:planningObject(horizonDetails.quality)
    });
    const horizon=Object.freeze({
      horizon_id:normalized,
      ...totals(selected),
      summary:nativeSummary,
      status:publicationStatus,
      quality:Object.freeze({availability:publicationStatus,
        missing:selected.missing,
        effective_horizon:effectiveAvailable,
        metrics_available:selected.available===true})
    });
    const todayTotals=totals(today),tomorrowTotals=totals(tomorrow),
      dayAfterTotals=totals(dayAfter);
    return Object.freeze({
      entityId:null,
      contractVersion:'ENERGY_NATIVE_PLANNING',
      available:effectiveAvailable,
      totalsAvailable:selected.available===true,
      provisionalTotals:selected.available===true&&!effectiveAvailable,
      previewOnly,previewSource:published===baseline?'rhi_deterministic_baseline':previewOnly?'incomplete_effective':'effective',
      published:nativeHorizon?.published===true||!!published,
      publicationStatus,
      requestedProvider,effectiveProvider,providerHold,
      reasonCode:effectiveAvailable?'':String(nativeHorizon?.reason||publicationMetadata.reason_code||'effective_horizon_not_published'),
      executionAuthorized:effectiveAvailable&&publicationMetadata.execution_authorized===true,
      attrs:Object.freeze({}),
      planId:published ? publicationMetadata.plan_id ?? horizonDetails.plan_id ?? null : null,
      providerId:published ? publicationMetadata.provider_id ?? horizonDetails.provider_id ?? null : null,
      providerPlanReference:published ? horizonDetails.provider_plan_ref ?? null : null,
      generatedAt:published ? publicationMetadata.generated_at ?? horizonDetails.generated_at ?? null : null,
      sourceLanes:Object.freeze(planningObject(horizonDetails.source_lanes)),
      consumerLanes:Object.freeze(planningObject(horizonDetails.consumer_lanes)),
      balance:Object.freeze(planningObject(horizonDetails.balance)),
      batteryLedger:Object.freeze(planningObject(horizonDetails.battery_ledger)),
      policyEvidence:Object.freeze(planningObject(horizonDetails.policy_evidence)),
      planningAssets:Object.freeze(planningAssets),
      planningAssetsById:Object.freeze(Object.fromEntries(planningAssets
        .filter(row=>row && String(row.asset_id || '').trim())
        .map(row=>[String(row.asset_id),row]))),
      planningTodayTotals:Object.freeze(todayTotals),
      planningTomorrowTotals:Object.freeze(tomorrowTotals),
      planningDayAfterTotals:Object.freeze(dayAfterTotals),
      planningCombinedTotals:Object.freeze({}),
      horizonsById:Object.freeze({D0:todayTotals,D1:tomorrowTotals,D2:dayAfterTotals}),
      horizonId:normalized,horizon,summary:nativeSummary,
      // D0/D1 lane totals are backend-owned and must never be reconstructed
      // from flat numeric KPI readbacks.
      laneTotals:Object.freeze(planningObject(planningObject(horizonDetails.summary).lane_totals)),
      buckets:Object.freeze(Array.isArray(horizonDetails.buckets) ? horizonDetails.buckets : []),
      // The producer may explicitly identify the current bucket; otherwise it is unknown.
      currentPlanningBucket:Object.freeze(planningObject(horizonDetails.current_bucket)),
      currentActionIntent:Object.freeze(published && horizonDetails.execution_policy && typeof horizonDetails.execution_policy === 'object' ? horizonDetails.execution_policy : {}),
      missingContractCapabilities:Object.freeze([
        ...(!effectiveAvailable ? ['native_effective_horizon'] : []),
        ...(!published ? ['native_planning_buckets'] : []),
        ...(!published || !Array.isArray(horizonDetails.planning_assets) ? ['native_planning_assets'] : []),
        ...(!published || !horizonDetails.execution_policy || typeof horizonDetails.execution_policy !== 'object' || Array.isArray(horizonDetails.execution_policy)
          ? ['native_planning_actions'] : [])
      ]),
      totalsSource:'rhi_energy.runtime/native_metric'
    });
  }

  function normalizePlanningLaneTotals(rawTotals = {}) {
    const totals = planningObject(rawTotals);
    const sources = planningObject(totals.sources);
    const consumers = planningObject(totals.consumers);
    const boundary = planningObject(totals.boundary);
    const flexibleRaw = firstDefined(
      consumers.flexible_assets,
      totals.flexible_assets,
      totals.flexible_loads_by_asset,
      totals.flexible_load_totals_by_asset,
      totals.consumer_totals_by_asset,
      totals.assets_by_id,
      {}
    );
    const parsedFlexible = parseMaybeJson(flexibleRaw, flexibleRaw);
    const flexibleAssetsById = Array.isArray(parsedFlexible)
      ? Object.fromEntries(parsedFlexible.map(row => [String(row?.asset_id || row?.id || ''), planningObject(row)]).filter(([id]) => id))
      : planningObject(parsedFlexible);
    const value = (...keys) => {
      for (const key of keys) {
        for (const scope of [totals, sources, consumers, boundary]) {
          const number = asNumber(scope[key]);
          if (number !== null) return number;
        }
      }
      return null;
    };
    return Object.freeze({
      raw: totals,
      sources,
      consumers,
      boundary,
      flexibleAssetsById,
      solarKwh: value('solar_kwh','solar_production_kwh','solar_total_kwh'),
      homeBatteryOutKwh: value('home_battery_supply_kwh','home_battery_discharge_kwh','battery_discharge_kwh','battery_out_kwh'),
      gridInKwh: value('grid_in_kwh','grid_import_kwh'),
      homeKwh: value('home_kwh','home_consumption_kwh','fixed_demand_kwh'),
      flexibleLoadsKwh: value('managed_energy_kwh','flexible_loads_kwh','planned_flexible_kwh','flexible_planned_kwh'),
      homeBatteryInKwh: value('home_battery_charge_kwh','battery_charge_kwh','battery_in_kwh'),
      gridOutKwh: value('grid_out_kwh','grid_export_kwh'),
      sourceTotalKwh: value('source_total_kwh','sources_total_kwh'),
      useTotalKwh: value('use_total_kwh','demand_total_kwh','consumer_total_kwh'),
      balanceDeltaKwh: value('balance_delta_kwh','lane_balance_delta_kwh'),
      homeBatteryNeedKwh: value('home_battery_need_kwh','battery_reserve_need_kwh')
    });
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { readPlanningContract, normalizePlanningLaneTotals };

// ---- src/domain/planning/planning-view-model.js ----
// Stable UX model builder for Planning. Renderers receive meaning, never backend paths.
  function createPlanningViewModel({ runtime, horizonId, flexibleAssets = [], storage = null }) {
    const contract = readPlanningContract(runtime, horizonId);
    const laneTotals = normalizePlanningLaneTotals(contract.laneTotals);
    const rows = contract.buckets.map(bucket => adaptPlanningBucket(bucket, contract.contractVersion));
    const quality = planningObject(contract.horizon.quality);
    const contractSupported = contract.published === true && contract.contractVersion === 'ENERGY_NATIVE_PLANNING';
    const stateText = String(firstDefined(contract.horizon.state, contract.horizon.status, quality.health, contract.horizon.quality, '')).toLowerCase();
    return Object.freeze({
      horizonId: contract.horizonId,
      horizon: contract.horizon,
      buckets: contract.buckets,
      assets: flexibleAssets,
      planningAssets: contract.planningAssets,
      planningAssetsById: contract.planningAssetsById,
      todayTotals: contract.planningTodayTotals,
      tomorrowTotals: contract.planningTomorrowTotals,
      dayAfterTotals: contract.planningDayAfterTotals,
      combinedTotals: contract.planningCombinedTotals,
      storage,
      rows,
      summary: contract.summary,
      laneTotals,
      quality,
      currentActionIntent: contract.currentActionIntent,
      contractVersion: contract.contractVersion,
      contractSupported,
      previewOnly:contract.previewOnly===true,previewSource:contract.previewSource,
      effectiveProvider:contract.effectiveProvider,requestedProvider:contract.requestedProvider,
      reasonCode:contract.reasonCode,
      currentBucketId: String(contract.currentPlanningBucket.bucket_id || ''),
      totalsSource: contract.totalsSource,
      complete: contract.available === true && !contract.previewOnly && contract.missingContractCapabilities.length === 0 && !/incomplete|partial|unavailable/.test(stateText)
    });
  }

  // ---- src/vendor/rhi-ux-core.js ----
/* RHI UX Core 1.6.4 */
// RHI UX Core 1.6.3 — build-time presentation primitives only.
// No domain semantics or Home Assistant contract/entity knowledge belongs here.
const RHI_UX_CORE_VERSION = "1.6.4";
const RHI_UX_COMPANY_LOGO_SVG = "<svg viewBox=\"75 116 1624 688\" role=\"img\" aria-labelledby=\"title desc\">\n<title id=\"title\">Robotix.be</title>\n<desc id=\"desc\">DomotiX · Network · Security</desc>\n<path fill=\"#0B4C86\" fill-rule=\"evenodd\" d=\"M536,549 L516,554 L512,556 L501,558 L497,560 L497,609 L512,608 L513,607 L525,606 L537,603 L537,551ZM1698,698 L1696,696 L1692,695 L1678,695 L1677,694 L1658,694 L1657,693 L1638,693 L1637,692 L1618,692 L1617,691 L1573,690 L1572,689 L1552,689 L1551,688 L1524,688 L1523,687 L1494,687 L1493,686 L1447,685 L1446,684 L1441,684 L1440,683 L1441,682 L1440,679 L1440,636 L1419,633 L1418,632 L1397,630 L1396,629 L1381,628 L1380,627 L1364,625 L1362,623 L1362,542 L1360,539 L1334,531 L1327,530 L1313,525 L1310,525 L1293,519 L1262,511 L1255,508 L1245,506 L1211,495 L1201,493 L1175,484 L1172,484 L1148,476 L1145,476 L1122,468 L1115,467 L1092,459 L1085,458 L1076,454 L1059,450 L1049,446 L1036,443 L1033,441 L1030,441 L1013,435 L1006,434 L997,430 L987,428 L964,420 L957,419 L944,414 L941,414 L928,409 L925,409 L909,403 L906,403 L890,397 L887,397 L867,404 L857,406 L848,410 L832,414 L819,419 L809,421 L784,430 L781,430 L771,434 L761,436 L752,440 L749,440 L721,450 L714,451 L683,462 L680,462 L639,476 L623,480 L620,482 L614,483 L601,488 L598,488 L595,490 L583,493 L573,497 L563,496 L562,495 L554,495 L547,499 L538,508 L343,571 L342,572 L342,638 L338,640 L332,640 L321,643 L315,643 L314,644 L309,644 L301,646 L300,648 L300,683 L296,685 L252,686 L251,687 L231,687 L230,688 L210,688 L209,689 L191,689 L190,690 L170,690 L169,691 L152,691 L151,692 L135,692 L134,693 L82,695 L81,696 L77,696 L76,700 L78,701 L121,701 L122,702 L299,704 L300,705 L300,729 L302,732 L306,733 L315,733 L316,734 L334,735 L335,736 L360,738 L361,739 L371,739 L372,740 L380,740 L381,741 L400,742 L401,743 L408,743 L409,744 L417,744 L418,745 L427,745 L428,746 L436,746 L437,747 L453,748 L454,749 L472,750 L473,751 L489,752 L490,753 L514,755 L515,756 L522,756 L523,757 L558,760 L559,761 L591,764 L599,766 L607,766 L608,767 L625,768 L632,770 L657,772 L665,774 L691,776 L692,777 L698,777 L706,779 L713,779 L714,780 L721,780 L729,782 L752,784 L753,785 L765,786 L766,787 L781,788 L789,790 L812,792 L813,793 L819,793 L820,794 L826,794 L827,795 L833,795 L841,797 L848,797 L849,798 L855,798 L856,799 L862,799 L870,801 L884,802 L885,801 L906,799 L907,798 L913,798 L914,797 L920,797 L921,796 L927,796 L928,795 L934,795 L935,794 L941,794 L942,793 L948,793 L949,792 L955,792 L956,791 L962,791 L970,789 L985,788 L986,787 L992,787 L999,785 L1006,785 L1007,784 L1035,781 L1036,780 L1042,780 L1050,778 L1057,778 L1058,777 L1065,777 L1066,776 L1072,776 L1080,774 L1103,772 L1104,771 L1112,771 L1113,770 L1127,769 L1128,768 L1149,766 L1150,765 L1157,765 L1165,763 L1173,763 L1174,762 L1190,761 L1191,760 L1205,759 L1213,757 L1223,757 L1224,756 L1256,753 L1257,752 L1264,752 L1265,751 L1272,751 L1273,750 L1316,746 L1324,744 L1332,744 L1333,743 L1341,743 L1342,742 L1350,742 L1351,741 L1359,741 L1360,740 L1369,740 L1370,739 L1378,739 L1379,738 L1387,738 L1388,737 L1398,737 L1399,736 L1416,735 L1417,734 L1424,734 L1425,733 L1434,733 L1440,731 L1440,708 L1441,707 L1440,706 L1442,704 L1513,704 L1514,703 L1524,703 L1527,704 L1528,703 L1657,702 L1658,701 L1695,701ZM1408,720 L1404,722 L1400,721 L1400,652 L1399,651 L1384,649 L1383,648 L1377,648 L1376,647 L1369,647 L1368,646 L1349,644 L1349,726 L1348,727 L1341,727 L1340,728 L1333,728 L1332,729 L1314,730 L1313,729 L1313,640 L1307,638 L1278,635 L1277,634 L1271,634 L1263,632 L1224,628 L1224,738 L1222,740 L1189,743 L1188,744 L1180,744 L1179,745 L1171,745 L1170,746 L1163,746 L1162,747 L1139,749 L1138,750 L1131,750 L1130,751 L1122,751 L1121,752 L1114,752 L1113,753 L1096,754 L1095,753 L1095,611 L1071,608 L1070,607 L1048,605 L1047,604 L1040,604 L1039,603 L1033,603 L1032,602 L1026,602 L1025,601 L1019,601 L1011,599 L1003,599 L995,597 L972,595 L971,594 L959,593 L958,592 L954,592 L953,593 L953,772 L951,774 L937,775 L936,776 L908,779 L900,781 L893,781 L885,783 L877,783 L876,782 L862,781 L861,780 L855,780 L847,778 L840,778 L839,777 L817,775 L816,774 L807,774 L806,773 L800,773 L799,772 L793,772 L785,770 L778,770 L777,769 L770,769 L769,768 L762,768 L761,767 L739,765 L738,764 L730,764 L729,763 L729,606 L714,607 L706,609 L676,612 L675,613 L661,614 L660,615 L646,616 L645,617 L631,618 L630,619 L623,619 L622,620 L622,750 L621,751 L588,748 L587,747 L571,746 L570,745 L562,745 L561,744 L552,744 L551,743 L544,743 L537,741 L537,631 L536,630 L507,633 L506,634 L500,634 L499,635 L485,636 L484,637 L476,638 L476,735 L475,736 L466,736 L465,735 L465,644 L464,643 L464,639 L402,648 L402,729 L401,730 L364,727 L361,725 L361,661 L364,659 L370,659 L371,658 L377,658 L378,657 L394,655 L395,654 L395,650 L394,649 L362,653 L361,654 L355,654 L354,655 L340,656 L339,657 L327,658 L326,659 L318,659 L317,660 L313,660 L312,659 L312,655 L322,652 L342,650 L355,647 L393,643 L406,640 L413,640 L414,639 L420,639 L421,638 L434,637 L435,636 L441,636 L449,634 L456,634 L457,633 L463,633 L471,631 L479,631 L480,630 L492,629 L493,628 L509,627 L510,626 L530,624 L536,622 L552,621 L553,620 L576,618 L583,616 L607,614 L608,613 L615,613 L616,612 L624,612 L632,610 L640,610 L648,608 L671,606 L672,605 L701,602 L702,601 L709,601 L710,600 L716,600 L717,599 L723,599 L731,597 L739,597 L747,595 L755,595 L762,593 L770,593 L771,592 L792,590 L800,588 L832,585 L833,584 L861,581 L862,580 L879,579 L880,578 L887,578 L888,577 L898,577 L906,579 L915,579 L916,580 L923,580 L924,581 L956,584 L963,586 L979,587 L986,589 L1002,590 L1003,591 L1031,594 L1039,596 L1046,596 L1054,598 L1062,598 L1063,599 L1069,599 L1076,601 L1083,601 L1084,602 L1090,602 L1098,604 L1106,604 L1107,605 L1113,605 L1114,606 L1120,606 L1121,607 L1127,607 L1135,609 L1143,609 L1144,610 L1166,612 L1167,613 L1181,614 L1189,616 L1197,616 L1198,617 L1210,618 L1211,619 L1218,619 L1219,620 L1233,621 L1234,622 L1242,622 L1243,623 L1272,626 L1273,627 L1279,627 L1287,629 L1312,631 L1313,632 L1319,632 L1320,633 L1339,635 L1340,636 L1347,636 L1354,638 L1362,638 L1363,639 L1369,639 L1376,641 L1404,644 L1408,646ZM885,440 L886,441 L886,560 L883,562 L875,562 L869,564 L861,564 L853,566 L846,566 L845,567 L817,570 L816,569 L816,460 L819,458 L822,458 L826,456 L829,456 L833,454 L836,454 L840,452 L843,452 L847,450 L858,448 L875,442ZM1339,551 L1339,612 L1338,613 L1338,620 L1337,621 L1332,620 L1330,617 L1330,589 L1331,588 L1331,578 L1330,577 L1331,559 L1330,558 L1330,554 L1316,549 L1283,541 L1276,538 L1269,537 L1251,531 L1248,531 L1248,606 L1246,608 L1238,608 L1237,607 L1230,607 L1222,605 L1215,605 L1214,604 L1208,604 L1207,603 L1201,603 L1200,602 L1194,602 L1193,601 L1187,601 L1186,600 L1180,600 L1172,598 L1149,596 L1142,594 L1135,594 L1128,592 L1086,587 L1085,586 L1066,584 L1065,583 L1058,583 L1057,582 L1035,580 L1034,579 L1021,578 L1020,577 L1014,577 L1013,576 L1007,576 L999,574 L992,574 L991,573 L985,573 L977,571 L963,570 L959,568 L959,524 L958,523 L958,509 L959,508 L959,455 L958,454 L958,448 L955,448 L941,443 L920,438 L891,429 L885,429 L860,437 L843,441 L823,448 L820,448 L813,451 L799,454 L786,459 L779,460 L766,465 L749,469 L743,472 L743,579 L741,581 L709,585 L708,586 L702,586 L701,587 L695,587 L694,588 L688,588 L687,589 L666,591 L665,592 L657,592 L656,593 L650,593 L649,594 L643,594 L635,596 L620,597 L612,599 L604,599 L603,598 L603,583 L602,582 L602,578 L603,577 L603,546 L602,545 L603,543 L603,523 L602,522 L602,513 L600,513 L556,527 L553,527 L543,531 L526,535 L488,548 L485,548 L482,550 L482,564 L480,566 L444,575 L440,577 L429,579 L425,581 L421,581 L414,584 L411,584 L395,589 L395,625 L396,626 L404,624 L416,623 L417,622 L423,622 L424,621 L451,618 L458,616 L464,616 L470,614 L478,614 L479,613 L489,612 L490,611 L490,556 L493,554 L522,547 L543,540 L545,547 L545,599 L544,600 L545,607 L543,609 L525,611 L518,613 L504,614 L503,615 L497,615 L496,616 L477,618 L476,619 L464,620 L463,621 L456,621 L455,622 L429,625 L428,626 L422,626 L421,627 L389,631 L388,632 L376,633 L375,634 L369,634 L362,636 L358,635 L358,583 L360,581 L372,578 L391,571 L394,571 L429,559 L432,559 L435,557 L444,555 L466,547 L469,547 L491,539 L494,539 L506,534 L509,534 L542,523 L545,523 L551,520 L564,517 L577,512 L580,512 L587,509 L590,509 L597,506 L610,503 L616,500 L636,495 L665,485 L679,482 L689,478 L692,478 L728,466 L735,465 L778,451 L785,450 L798,445 L818,440 L828,436 L848,431 L861,426 L870,424 L873,422 L884,420 L887,418 L913,426 L916,426 L926,430 L933,431 L936,433 L957,438 L999,451 L1006,452 L1023,458 L1030,459 L1033,461 L1065,469 L1085,476 L1092,477 L1099,480 L1120,485 L1130,489 L1141,491 L1147,494 L1182,503 L1212,513 L1231,517 L1265,528 L1268,528 L1272,530 L1303,538 L1309,541 L1316,542 L1326,546 L1336,548ZM1248,241 L1248,281 L1249,282 L1295,282 L1296,281 L1296,241 L1295,240 L1249,240ZM1493,178 L1490,184 L1487,195 L1487,246 L1488,247 L1489,255 L1493,263 L1498,270 L1503,274 L1515,280 L1523,282 L1533,282 L1534,283 L1640,282 L1641,280 L1641,250 L1640,246 L1549,246 L1546,245 L1541,240 L1540,237 L1541,234 L1639,234 L1641,226 L1641,198 L1640,197 L1640,191 L1635,178 L1625,167 L1618,163 L1602,159 L1526,159 L1525,160 L1517,161 L1505,166ZM1540,201 L1548,193 L1581,193 L1584,194 L1589,199 L1590,206 L1589,207 L1582,207 L1581,208 L1545,208 L1540,206ZM998,159 L995,161 L995,281 L996,282 L1049,282 L1049,160 L1048,159ZM1059,159 L1059,162 L1114,221 L1105,232 L1062,276 L1059,280 L1059,282 L1126,282 L1150,257 L1160,266 L1174,282 L1241,282 L1241,280 L1190,226 L1187,221 L1243,163 L1244,161 L1243,159 L1178,159 L1151,187 L1125,159 L1119,159 L1118,158 L1117,159ZM865,177 L852,165 L842,161 L834,160 L833,159 L819,159 L818,158 L815,159 L749,159 L748,160 L740,161 L728,166 L715,179 L712,185 L709,196 L709,245 L713,258 L718,266 L725,273 L737,279 L749,282 L831,282 L832,281 L841,280 L853,275 L866,262 L870,254 L872,246 L873,203 L872,202 L871,190ZM765,202 L770,198 L775,196 L805,196 L806,197 L810,197 L816,202 L819,211 L819,231 L816,239 L813,242 L804,245 L777,245 L768,242 L763,236 L763,230 L762,229 L762,211ZM514,177 L508,170 L499,164 L482,159 L456,159 L455,158 L446,158 L445,159 L392,159 L375,164 L365,171 L359,178 L353,193 L353,199 L352,200 L352,240 L353,241 L354,252 L358,261 L372,275 L385,280 L395,281 L396,282 L476,282 L477,281 L483,281 L491,279 L505,272 L513,264 L517,257 L520,248 L520,242 L521,241 L521,197 L520,196 L519,188ZM408,204 L414,198 L420,196 L450,196 L457,198 L463,204 L465,209 L465,232 L463,237 L457,243 L449,245 L422,245 L414,243 L409,239 L406,231 L406,210ZM894,134 L894,158 L893,159 L877,159 L876,160 L876,196 L893,196 L894,197 L894,247 L895,248 L896,257 L901,268 L911,277 L924,282 L929,282 L930,283 L965,283 L966,282 L980,281 L982,279 L982,245 L981,244 L959,245 L954,243 L951,240 L949,234 L949,197 L950,196 L979,196 L979,160 L978,159 L950,159 L949,158 L949,122 L948,121 L924,127 L920,127 L912,130 L899,132ZM134,122 L134,281 L135,282 L191,282 L192,281 L192,230 L193,229 L223,229 L272,282 L345,282 L343,277 L338,273 L295,227 L312,223 L323,217 L333,206 L336,199 L338,191 L338,155 L336,147 L332,139 L324,130 L315,125 L306,122 L289,121 L288,120 L137,120ZM192,163 L193,162 L266,162 L271,164 L275,168 L277,173 L277,178 L275,183 L271,187 L266,189 L193,189 L192,188ZM1311,117 L1310,118 L1310,260 L1311,261 L1310,263 L1310,280 L1311,282 L1358,282 L1362,272 L1372,279 L1383,282 L1435,282 L1448,279 L1458,274 L1467,265 L1471,258 L1474,247 L1474,240 L1475,239 L1474,193 L1471,183 L1465,173 L1458,167 L1451,163 L1435,159 L1390,159 L1375,163 L1366,169 L1365,168 L1365,118 L1364,117ZM1366,200 L1373,196 L1407,196 L1413,198 L1418,203 L1420,209 L1420,232 L1419,233 L1419,237 L1415,242 L1407,245 L1373,245 L1368,243 L1365,239 L1365,202ZM995,118 L995,151 L1049,151 L1049,117 L996,117ZM533,118 L533,281 L534,282 L582,282 L583,276 L585,272 L591,277 L597,280 L605,281 L606,282 L658,282 L674,278 L684,272 L690,266 L697,251 L698,239 L699,238 L699,229 L698,228 L698,193 L697,192 L697,188 L692,177 L684,168 L673,162 L661,159 L613,159 L600,162 L589,169 L588,168 L588,118 L587,117 L534,117ZM593,197 L596,196 L630,196 L638,199 L643,206 L643,234 L641,239 L638,242 L629,245 L598,245 L591,243 L588,239 L588,203Z\"/>\n<path fill=\"#5B95C8\" fill-rule=\"evenodd\" d=\"M1143,328 L1137,334 L1136,337 L1137,342 L1140,346 L1144,348 L1150,348 L1156,343 L1157,340 L1156,333 L1150,328ZM594,328 L588,334 L588,341 L593,347 L601,348 L607,344 L609,338 L608,334 L602,328ZM1591,313 L1590,314 L1609,341 L1609,360 L1617,360 L1618,359 L1618,341 L1635,317 L1636,313 L1635,312 L1628,312 L1614,331 L1612,330 L1605,319 L1599,312 L1598,313ZM1539,312 L1537,314 L1538,321 L1551,321 L1552,322 L1552,358 L1553,360 L1561,360 L1562,359 L1562,322 L1563,321 L1576,321 L1577,320 L1577,313 L1576,312ZM1519,312 L1512,313 L1512,360 L1520,360 L1521,358 L1521,314ZM1453,312 L1452,313 L1452,360 L1460,360 L1461,359 L1461,343 L1462,342 L1469,342 L1483,360 L1492,360 L1493,359 L1481,343 L1482,341 L1487,339 L1490,336 L1492,331 L1492,324 L1489,318 L1484,314 L1477,312ZM1461,322 L1462,321 L1478,321 L1482,324 L1483,329 L1478,334 L1462,334 L1461,333ZM1391,313 L1391,347 L1394,354 L1398,358 L1405,361 L1418,361 L1424,359 L1428,356 L1432,348 L1432,313 L1431,312 L1425,312 L1423,314 L1423,346 L1419,351 L1414,353 L1408,353 L1402,349 L1400,344 L1400,313 L1399,312ZM1273,313 L1273,359 L1274,360 L1308,360 L1308,352 L1283,352 L1282,351 L1282,341 L1283,340 L1305,340 L1306,339 L1306,332 L1283,332 L1282,331 L1282,322 L1283,321 L1306,321 L1308,319 L1308,314 L1306,312 L1275,312ZM1040,313 L1040,359 L1041,360 L1048,360 L1049,359 L1049,345 L1054,341 L1071,360 L1082,360 L1081,357 L1061,335 L1081,313 L1079,312 L1071,312 L1051,331 L1049,330 L1049,313 L1048,312ZM982,312 L981,313 L981,325 L980,326 L980,345 L981,346 L981,356 L980,358 L981,360 L989,360 L990,343 L991,342 L992,343 L993,342 L998,343 L1012,360 L1021,360 L1020,356 L1010,343 L1011,341 L1017,338 L1020,333 L1021,326 L1019,320 L1013,314 L1006,312ZM989,325 L991,321 L1007,321 L1011,324 L1012,328 L1006,334 L991,334 L990,333ZM832,313 L834,322 L838,332 L838,335 L847,360 L854,360 L856,358 L865,330 L867,332 L876,359 L877,360 L884,360 L885,359 L899,315 L898,312 L891,312 L890,313 L885,327 L883,337 L880,343 L870,313 L863,312 L861,314 L854,337 L851,342 L848,336 L841,313 L839,312ZM781,312 L780,313 L780,320 L781,321 L794,321 L795,322 L795,358 L796,360 L804,360 L804,329 L805,328 L805,322 L806,321 L818,321 L820,319 L820,314 L818,312ZM731,312 L729,314 L729,355 L730,356 L730,360 L765,360 L765,353 L764,352 L740,352 L739,351 L739,341 L740,340 L762,340 L763,339 L763,333 L762,332 L740,332 L739,331 L739,322 L740,321 L763,321 L765,319 L764,313 L763,312ZM664,313 L664,359 L665,360 L672,360 L673,359 L673,330 L674,329 L698,360 L707,360 L707,313 L706,312 L698,313 L698,342 L697,343 L673,312 L666,312ZM493,312 L492,314 L508,336 L491,359 L492,360 L501,360 L510,348 L515,344 L527,360 L536,360 L537,358 L521,337 L521,334 L536,315 L536,313 L535,312 L527,312 L514,328 L501,312ZM466,312 L465,313 L465,359 L466,360 L474,360 L474,312ZM410,312 L409,313 L409,319 L413,321 L423,321 L424,322 L424,359 L425,360 L432,360 L433,359 L433,322 L435,320 L436,321 L448,320 L449,319 L449,314 L448,312ZM274,313 L274,323 L273,324 L273,358 L275,360 L282,360 L283,359 L283,336 L284,335 L288,341 L296,358 L302,358 L307,350 L311,340 L313,338 L313,336 L315,334 L316,335 L316,359 L317,360 L324,360 L325,359 L325,313 L324,312 L315,312 L303,338 L299,343 L283,312 L275,312ZM139,312 L138,313 L138,359 L139,360 L161,360 L162,359 L166,359 L172,356 L179,349 L182,343 L182,330 L179,322 L172,315 L164,312ZM148,320 L163,321 L170,326 L173,333 L173,338 L171,344 L165,350 L162,351 L148,351 L147,350 L147,321ZM1344,312 L1339,314 L1330,322 L1326,332 L1327,345 L1330,351 L1338,358 L1346,361 L1357,361 L1368,356 L1371,353 L1371,351 L1366,346 L1361,350 L1354,353 L1349,353 L1343,351 L1338,346 L1336,342 L1336,331 L1338,327 L1343,322 L1348,320 L1358,321 L1365,326 L1368,325 L1371,320 L1366,315 L1359,312 L1354,312 L1353,311ZM1237,311 L1224,313 L1220,315 L1215,322 L1215,330 L1221,337 L1230,340 L1239,341 L1244,345 L1244,348 L1240,352 L1237,353 L1230,353 L1223,350 L1220,347 L1218,347 L1214,352 L1214,354 L1227,361 L1243,360 L1247,358 L1251,354 L1253,350 L1253,341 L1247,335 L1243,333 L1227,330 L1224,327 L1224,324 L1229,320 L1237,320 L1244,323 L1246,325 L1249,323 L1251,318 L1249,316ZM929,312 L922,315 L913,325 L911,331 L911,342 L915,351 L920,356 L927,360 L931,361 L946,360 L952,357 L959,350 L962,344 L962,329 L961,326 L954,317 L947,313 L939,311ZM930,321 L933,320 L944,321 L950,326 L953,333 L952,343 L943,352 L939,353 L930,352 L923,346 L920,339 L921,330 L924,325ZM355,315 L350,320 L345,330 L346,345 L352,354 L360,359 L367,361 L379,360 L387,356 L393,350 L397,340 L397,332 L394,323 L385,314 L377,311 L364,311ZM361,322 L365,320 L376,320 L381,322 L385,326 L387,330 L387,341 L385,345 L380,350 L375,352 L366,352 L358,347 L355,342 L354,333 L357,326ZM215,313 L205,322 L202,329 L201,338 L204,348 L211,356 L219,360 L230,361 L242,357 L249,351 L253,342 L253,336 L254,335 L253,334 L253,328 L250,322 L243,315 L234,311 L221,311ZM218,322 L222,320 L233,320 L237,322 L242,327 L244,332 L244,339 L241,346 L237,350 L232,352 L223,352 L217,349 L213,345 L211,340 L211,332 L213,327Z\"/>\n</svg>";

function rhiUxEscape(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[ch]));
}

function rhiUxDisplay(value, fallback = "—") {
  return value === undefined || value === null || value === "" ? fallback : String(value);
}

function rhiUxLocaleCandidates(locale = "en") {
  const normalized = String(locale || "en").trim().replace(/_/g, "-").toLowerCase();
  const base = normalized.split("-")[0] || "en";
  return [...new Set([normalized, base, "en"])];
}

function rhiUxTranslate(resources = {}, key = "", { locale = "en", params = {}, fallback = "" } = {}) {
  const wanted = String(key || "");
  let template = "";
  for (const candidate of rhiUxLocaleCandidates(locale)) {
    const row = resources?.[candidate];
    if (row && Object.prototype.hasOwnProperty.call(row, wanted)) {
      template = String(row[wanted] ?? "");
      break;
    }
  }
  if (!template) template = fallback || wanted;
  return template.replace(/\{([a-zA-Z0-9_]+)\}/g, (_, name) => rhiUxEscape(rhiUxDisplay(params?.[name], "")));
}

function rhiUxFormatNumber(value, { locale = "en", maximumFractionDigits = 2, minimumFractionDigits = 0 } = {}) {
  if (value === undefined || value === null || value === "" || !Number.isFinite(Number(value))) return "—";
  return new Intl.NumberFormat(locale, { maximumFractionDigits, minimumFractionDigits }).format(Number(value));
}

function rhiUxFormatCurrency(value, currency = "EUR", { locale = "en", maximumFractionDigits = 2 } = {}) {
  if (value === undefined || value === null || value === "" || !Number.isFinite(Number(value))) return "—";
  return new Intl.NumberFormat(locale, { style:"currency", currency, maximumFractionDigits }).format(Number(value));
}

function rhiUxFormatPercent(value, { locale = "en", scale = 100, maximumFractionDigits = 1 } = {}) {
  if (value === undefined || value === null || value === "" || !Number.isFinite(Number(value))) return "—";
  return new Intl.NumberFormat(locale, { style:"percent", maximumFractionDigits }).format(Number(value) / Number(scale || 100));
}

function rhiUxFormatDateTime(value, { locale = "en", dateStyle = "medium", timeStyle = "short" } = {}) {
  if (value === undefined || value === null || value === "") return "—";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat(locale, { dateStyle, timeStyle }).format(date);
}

function rhiUxStatusItem({ icon = "•", label = "", value = "—", detail = "" } = {}) {
  const iconMarkup = /^mdi:/.test(String(icon || "")) ? `<ha-icon icon="${rhiUxEscape(icon)}"></ha-icon>` : rhiUxEscape(icon);
  return `<div class="rhiUxStatusItem"><span class="rhiUxStatusIcon">${iconMarkup}</span><div class="rhiUxStatusCopy"><small>${rhiUxEscape(label)}</small><b>${rhiUxEscape(rhiUxDisplay(value))}</b>${detail ? `<em>${rhiUxEscape(detail)}</em>` : ""}</div></div>`;
}

function rhiUxStatusGrid(items = []) {
  return `<section class="rhiUxStatusGrid">${items.map(rhiUxStatusItem).join("")}</section>`;
}

function rhiUxPageHero({ eyebrow = "", title = "", description = "", image = "", imageAlt = "" } = {}) {
  return `<section class="rhiUxPageHero"><div class="rhiUxPageHeroCopy">${eyebrow ? `<small>${rhiUxEscape(eyebrow)}</small>` : ""}<h2>${rhiUxEscape(title)}</h2>${description ? `<p>${rhiUxEscape(description)}</p>` : ""}</div>${image ? `<div class="rhiUxPageHeroArt"><img src="${rhiUxEscape(image)}" alt="${rhiUxEscape(imageAlt)}"></div>` : ""}</section>`;
}

function rhiUxState({ state = "unavailable", title = "Unavailable", detail = "" } = {}) {
  return `<div class="rhiUxState" data-state="${rhiUxEscape(state)}"><b>${rhiUxEscape(title)}</b>${detail ? `<span>${rhiUxEscape(detail)}</span>` : ""}</div>`;
}

function rhiUxConclusion({ title = "", detail = "", label = "Conclusion" } = {}) {
  return `<section class="rhiUxConclusion"><div><small>${rhiUxEscape(label)}</small><h2>${rhiUxEscape(title)}</h2>${detail ? `<p>${rhiUxEscape(detail)}</p>` : ""}</div></section>`;
}

function rhiUxTechnicalFooter({ product = "", uxVersion = "", backendVersion = "", issue = "", severity = "" } = {}) {
  return `<footer class="rhiUxTechnicalFooter"><span>${rhiUxEscape(product)} UX ${rhiUxEscape(uxVersion)}</span><span>Backend ${rhiUxEscape(rhiUxDisplay(backendVersion,"Unknown"))}</span>${issue ? `<span data-severity="${rhiUxEscape(severity)}">${rhiUxEscape(issue)}</span>` : ""}</footer>`;
}

function rhiUxCompanyBrand({ ariaLabel = "Robotix.be — DomotiX · Network · Security" } = {}) {
  return `<span class="rhiUxCompanyLogo" role="img" aria-label="${rhiUxEscape(ariaLabel)}">${RHI_UX_COMPANY_LOGO_SVG}</span>`;
}

function rhiUxDomainShell({ product = "Home Intelligence", domain = "", modules = [], activeModule = "", activeItem = "", brandHtml = rhiUxCompanyBrand() } = {}) {
  const selected = modules.find(row => String(row.id || "") === String(activeModule || "")) || modules[0] || { items:[] };
  const moduleButtons = modules.map(row => {
    const active = String(row.id || "") === String(selected.id || "");
    return `<button type="button" class="rhiUxModuleTab${active ? " active" : ""}" data-rhi-module="${rhiUxEscape(row.id || "")}"${row.target ? ` data-nav="${rhiUxEscape(row.target)}"` : ""}><span>${rhiUxEscape(row.label || row.id || "")}</span></button>`;
  }).join("");
  const itemButtons = (selected.items || []).map(row => {
    const active = String(row.id || "") === String(activeItem || "");
    return `<button type="button" class="rhiUxDomainTab${active ? " active" : ""}" data-rhi-item="${rhiUxEscape(row.id || "")}"${row.target ? ` data-nav="${rhiUxEscape(row.target)}"` : ""}><span>${rhiUxEscape(row.label || row.id || "")}</span></button>`;
  }).join("");
  return `<header class="rhiUxDomainShell"><div class="rhiUxProductArea"><div class="rhiUxDomainShellTop"><div class="rhiUxDomainIdentity"><span>${rhiUxEscape(product)}</span><strong>${rhiUxEscape(domain)}</strong></div><nav class="rhiUxModuleTabs" aria-label="Modules">${moduleButtons}</nav></div><div class="rhiUxDomainShellBottom"><nav class="rhiUxDomainTabs" aria-label="${rhiUxEscape(selected.label || domain || "Domain")} navigation">${itemButtons}</nav></div></div>${brandHtml ? `<div class="rhiUxCompanyBrand">${brandHtml}</div>` : ""}</header>`;
}


function rhiUxQuickActionBar({ label = "Quick actions", actions = [] } = {}) {
  const visibleActions = actions.filter(action => action?.visible !== false);
  if (!visibleActions.length) return "";
  return `<section class="rhiUxQuickActionBar" aria-label="${rhiUxEscape(label)}"><small>${rhiUxEscape(label)}</small><div class="rhiUxQuickActions">${visibleActions.map((action,index) => {
    const disabled = action.enabled === false || action.disabled === true;
    const reason = String(action.reason || "");
    return `<button type="button" class="rhiUxQuickAction${action.primary || index === 0 ? " primary" : ""}"${action.target ? ` data-nav="${rhiUxEscape(action.target)}"` : ""}${disabled ? " disabled" : ""}${reason ? ` title="${rhiUxEscape(reason)}"` : ""}>${action.icon ? `<ha-icon icon="${rhiUxEscape(action.icon)}"></ha-icon>` : ""}<span>${rhiUxEscape(action.label || "Open")}</span></button>`;
  }).join("")}</div></section>`;
}

function rhiUxContextBar({ label = "View", controls = [], controlsId = "" } = {}) {
  if (!Array.isArray(controls) || controls.length === 0) return "";
  const labelled = label ? `<small>${rhiUxEscape(label)}</small>` : "";
  const body = controls.filter(control => control?.visible !== false).map((control,index) => {
    const attrs = [];
    if (control.value !== undefined) attrs.push(`data-value="${rhiUxEscape(control.value)}"`);
    if (control.target) attrs.push(`data-nav="${rhiUxEscape(control.target)}"`);
    if (control.pressed !== undefined) attrs.push(`aria-pressed="${control.pressed ? "true" : "false"}"`);
    if (control.enabled === false || control.disabled) attrs.push("disabled");
    if (control.reason) attrs.push(`title="${rhiUxEscape(control.reason)}"`);
    const cls = `rhiUxContextControl${control.active || control.pressed ? " active" : ""}`;
    return `<button type="button" class="${cls}" ${attrs.join(" ")}>${rhiUxEscape(control.label || control.value || `Option ${index+1}`)}</button>`;
  }).join("");
  const idAttr = controlsId ? ` aria-controls="${rhiUxEscape(controlsId)}"` : "";
  return `<section class="rhiUxContextBar" aria-label="${rhiUxEscape(label || "View controls")}"${idAttr}>${labelled}<div class="rhiUxContextControls">${body}</div></section>`;
}


function rhiUxPageTemplate({ hero = "", status = "", actions = "", context = "", content = "", className = "" } = {}) {
  return `<main class="rhiUxPage rhiUxPageStack ${rhiUxEscape(className)}">${hero}${status}${actions}${context}<section class="rhiUxPageContent">${content}</section></main>`;
}


/* Shared presentation only. Domain adapters supply the factual values and safe actions. */
function rhiUxCompactAssetRow({
  name = "", visualHtml = "", context = "", power = "—", state = "",
  relationshipLabel = "", relationshipTarget = "", disclosureHtml = ""
} = {}) {
  const link = relationshipLabel && relationshipTarget
    ? `<button type="button" class="rhiUxAssetRelationshipLink" data-nav="${rhiUxEscape(relationshipTarget)}">${rhiUxEscape(relationshipLabel)}</button>`
    : (relationshipLabel ? `<span>${rhiUxEscape(relationshipLabel)}</span>` : "");
  return `<div class="rhiUxAssetRow">
    <div class="rhiUxAssetImage">${visualHtml}</div>
    <div class="rhiUxAssetRowIdentity"><strong class="rhiUxAssetName">${rhiUxEscape(name)}</strong>${context ? `<span class="rhiUxAssetContext">${rhiUxEscape(context)}</span>` : ""}${link ? `<div class="rhiUxAssetRowRelationship">${link}</div>` : ""}</div>
    <div class="rhiUxAssetLive"><strong class="rhiUxAssetPower">${rhiUxEscape(rhiUxDisplay(power))}</strong>${state ? `<span class="rhiUxAssetState">${rhiUxEscape(state)}</span>` : ""}</div>
    ${disclosureHtml ? `<div class="rhiUxAssetExpand">${disclosureHtml}</div>` : ""}
  </div>`;
}

function rhiUxAssetCardShell({ identity = "", facts = "", relationships = "", actions = "", details = "", feedback = "", className = "" } = {}) {
  const cls = ["rhiUxAssetCardShell", String(className || "").trim()].filter(Boolean).join(" ");
  const body = [
    identity ? `<div class="rhiUxAssetCardIdentity">${identity}</div>` : "",
    facts ? `<div class="rhiUxAssetCardFacts">${facts}</div>` : "",
    relationships ? `<div class="rhiUxAssetCardRelationships">${relationships}</div>` : "",
    actions ? `<div class="rhiUxAssetCardActions">${actions}</div>` : "",
    details ? `<div class="rhiUxAssetCardDetails">${details}</div>` : "",
    feedback ? `<div class="rhiUxAssetCardFeedback">${feedback}</div>` : ""
  ].join("");
  return `<article class="${rhiUxEscape(cls)}">${body}</article>`;
}

function rhiUxAssetIdentity({ eyebrow = "", title = "", subtitle = "", visual = "" } = {}) {
  return `<header class="rhiUxAssetIdentity">${visual ? `<div class="rhiUxAssetVisual">${visual}</div>` : ""}<div class="rhiUxAssetIdentityCopy">${eyebrow ? `<small>${rhiUxEscape(eyebrow)}</small>` : ""}<h2>${rhiUxEscape(title)}</h2>${subtitle ? `<p>${rhiUxEscape(subtitle)}</p>` : ""}</div></header>`;
}

function rhiUxAssetFactGrid(items = []) {
  return `<div class="rhiUxAssetFactGrid">${items.map(item => `<div class="rhiUxAssetFact"><small>${rhiUxEscape(item?.label || "")}</small><b>${rhiUxEscape(rhiUxDisplay(item?.value))}</b>${item?.detail ? `<span>${rhiUxEscape(item.detail)}</span>` : ""}</div>`).join("")}</div>`;
}

function rhiUxAssetRelationship({ label = "", value = "", detail = "", target = "" } = {}) {
  return `<div class="rhiUxAssetRelationship"><div><small>${rhiUxEscape(label)}</small><b>${rhiUxEscape(rhiUxDisplay(value))}</b>${detail ? `<span>${rhiUxEscape(detail)}</span>` : ""}</div>${target ? `<button type="button" data-nav="${rhiUxEscape(target)}">Open</button>` : ""}</div>`;
}

function rhiUxAssetDisclosure({ title = "Details", content = "", open = false } = {}) {
  return `<details class="rhiUxAssetDisclosure"${open ? " open" : ""}><summary>${rhiUxEscape(title)}</summary><div>${content}</div></details>`;
}

function rhiUxWriteFeedback({ state = "idle", message = "" } = {}) {
  if (!message) return "";
  return `<div class="rhiUxWriteFeedback" data-state="${rhiUxEscape(state)}" role="status">${rhiUxEscape(message)}</div>`;
}




const RHI_UX_NAVIGATION_STORAGE_KEY = "rhi.navigation.registry.v1";

function rhiUxReadNavigationRegistry(storage = globalThis?.localStorage) {
  try {
    const raw = storage?.getItem?.(RHI_UX_NAVIGATION_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch (_) {
    return {};
  }
}

function rhiUxRegisterDomainNavigation({ domain = "", assetDetailTemplate = "" } = {}, storage = globalThis?.localStorage) {
  const key = String(domain || "").trim();
  const template = String(assetDetailTemplate || "").trim();
  if (!/^[a-z0-9][a-z0-9_-]*$/.test(key)) return false;
  if (!template || !template.includes("{asset_id}")) return false;
  if (/^https?:\/\//i.test(template)) return false;
  try {
    const registry = rhiUxReadNavigationRegistry(storage);
    registry[key] = { asset_detail_template:template };
    storage?.setItem?.(RHI_UX_NAVIGATION_STORAGE_KEY, JSON.stringify(registry));
    return true;
  } catch (_) {
    return false;
  }
}

function rhiUxResolveDomainAssetNavigation(domain = "", assetId = "", storage = globalThis?.localStorage) {
  const key = String(domain || "").trim();
  const id = String(assetId || "").trim();
  if (!key || !id) return "";
  const row = rhiUxReadNavigationRegistry(storage)[key];
  const template = String(row?.asset_detail_template || "");
  if (!template.includes("{asset_id}")) return "";
  return template.replaceAll("{asset_id}", encodeURIComponent(id));
}


function rhiUxVisualPickerStyles() {
  return `
.rhiUxVisualPickerBackdrop{position:fixed;inset:0;z-index:9999;background:rgba(15,23,42,.44);display:grid;place-items:center;padding:20px}
.rhiUxVisualPickerPanel{width:min(920px,94vw);max-height:min(82vh,760px);overflow:hidden;background:#fff;border:1px solid var(--rhi-color-line,#e5ebf3);border-radius:20px;box-shadow:0 30px 80px rgba(15,23,42,.24);padding:16px;box-sizing:border-box;display:grid;grid-template-rows:auto auto minmax(0,1fr) auto auto;gap:10px}
.rhiUxVisualPickerHead{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;min-height:0}
.rhiUxVisualPickerHead small{font-size:var(--rhi-font-label);font-weight:800;letter-spacing:.12em;color:#64748b}.rhiUxVisualPickerHead h3{margin:2px 0 0;font-size:20px}.rhiUxVisualPickerHead p{margin:3px 0 0;font-size:11px;color:#64748b}
.rhiUxVisualPickerFilters{display:flex;gap:6px;flex-wrap:wrap;margin:0;min-height:0}
.rhiUxVisualPickerFilters button{border:1px solid #dbe3ee;background:#fff;border-radius:999px;padding:5px 10px;font-size:11px;font-weight:700;cursor:pointer}.rhiUxVisualPickerFilters button.selected{border-color:#93c5fd;background:#eff6ff;color:#1d4ed8}
.rhiUxVisualChoiceGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-auto-rows:142px;gap:8px;margin:0;overflow-y:auto;overscroll-behavior:contain;padding:2px 3px 4px 1px;align-content:start}
.rhiUxVisualChoice{height:142px;min-height:142px;max-height:142px;display:grid;grid-template-rows:86px minmax(0,1fr);gap:6px;align-items:stretch;text-align:left;border:1px solid #e2e8f0;background:#fff;border-radius:12px;padding:8px;cursor:pointer;overflow:hidden}.rhiUxVisualChoice:hover{border-color:#93c5fd;background:#f8fbff}.rhiUxVisualChoice.selected{border-color:#2563eb;box-shadow:0 0 0 2px rgba(37,99,235,.12);background:#f8fbff}
.rhiUxVisualChoiceImage{width:100%;height:86px;min-width:0;min-height:86px;max-width:none;max-height:86px;display:grid;place-items:center;overflow:hidden}.rhiUxVisualChoiceImage img{display:block;width:100%;height:100%;min-width:0;min-height:0;max-width:100%;max-height:100%;object-fit:contain;object-position:center}
.rhiUxVisualChoiceCopy{min-width:0;align-self:end}.rhiUxVisualChoiceCopy small,.rhiUxVisualChoiceCopy b,.rhiUxVisualChoiceCopy em{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.rhiUxVisualChoiceCopy small{font-size:var(--rhi-font-label);color:#64748b;text-transform:uppercase}.rhiUxVisualChoiceCopy b{font-size:12px;margin-top:1px}.rhiUxVisualChoiceCopy em{font-size:var(--rhi-font-small);color:#64748b;font-style:normal;margin-top:1px}
.rhiUxVisualPickerRefine{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:8px;margin:0}.rhiUxVisualPickerRefine label span{display:block;font-size:var(--rhi-font-label);color:#64748b;margin-bottom:3px}.rhiUxVisualPickerRefine select{width:100%;height:34px;border:1px solid #dbe3ee;border-radius:8px;background:#fff;padding:0 8px}
.rhiUxVisualPickerFooter{display:flex;align-items:center;gap:8px;margin:0;padding-top:9px;border-top:1px solid #edf1f6}.rhiUxVisualPickerSpacer{flex:1}.rhiUxVisualPickerFooter button{height:34px;border:1px solid #dbe3ee;border-radius:9px;background:#fff;padding:0 12px;font-size:var(--rhi-font-small);font-weight:700}.rhiUxVisualPickerFooter button.primary{background:#0b65ea;color:#fff;border-color:#0b65ea}.rhiUxVisualPickerFooter button:disabled{opacity:.45}
@media(max-width:900px){.rhiUxVisualChoiceGrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:560px){.rhiUxVisualPickerBackdrop{padding:8px}.rhiUxVisualPickerPanel{width:96vw;max-height:88vh;padding:12px}.rhiUxVisualChoiceGrid{grid-template-columns:1fr;grid-auto-rows:116px}.rhiUxVisualChoice{height:116px;min-height:116px;max-height:116px;grid-template-columns:94px minmax(0,1fr);grid-template-rows:1fr}.rhiUxVisualChoiceImage{width:94px;height:86px;min-width:94px;max-width:94px}.rhiUxVisualChoiceCopy{align-self:center}.rhiUxVisualPickerRefine{grid-template-columns:1fr 1fr}.rhiUxVisualPickerFooter{flex-wrap:wrap}}
`;
}

function rhiUxVisualPickerShell({
  eyebrow = "Appearance",
  title = "Choose appearance",
  description = "",
  filtersHtml = "",
  choicesHtml = "",
  refineHtml = "",
  selectedHtml = "",
  resetHtml = "",
  cancelHtml = "",
  saveHtml = "",
  modal = false,
  closeHtml = ""
} = {}) {
  const panel = `<section class="rhiUxVisualPickerPanel" role="${modal ? "dialog" : "region"}"${modal ? ' aria-modal="true"' : ""}>
    <header class="rhiUxVisualPickerHead"><div><small>${rhiUxEscape(eyebrow)}</small><h3>${rhiUxEscape(title)}</h3>${description ? `<p>${rhiUxEscape(description)}</p>` : ""}</div>${closeHtml}</header>
    ${filtersHtml ? `<div class="rhiUxVisualPickerFilters">${filtersHtml}</div>` : ""}
    <div class="rhiUxVisualChoiceGrid">${choicesHtml}</div>
    ${refineHtml ? `<div class="rhiUxVisualPickerRefine">${refineHtml}</div>` : ""}
    <footer class="rhiUxVisualPickerFooter">${resetHtml}<span class="rhiUxVisualPickerSpacer"></span>${selectedHtml}${cancelHtml}${saveHtml}</footer>
  </section>`;
  return modal ? `<div class="rhiUxVisualPickerBackdrop">${panel}</div>` : panel;
}


function rhiUxVisualFilterButtons({ values = [], active = "all", allLabel = "All", attribute = "data-rhi-visual-filter" } = {}) {
  const rows = [{ value:"all", label:allLabel }, ...values.map(value => typeof value === "object" ? value : { value, label:value })];
  return rows.map(row => { const value=String(row?.value ?? ""); const label=String(row?.label ?? value); const selected=value===String(active ?? "all"); return `<button type="button" class="${selected ? "selected" : ""}" ${rhiUxEscape(attribute)}="${rhiUxEscape(value)}" aria-pressed="${selected ? "true" : "false"}">${rhiUxEscape(label)}</button>`; }).join("");
}
function rhiUxVisualChoice({ id = "", image = "", imageAlt = "", eyebrow = "", label = "", detail = "", selected = false, imageStyle = "", attributes = {} } = {}) {
  const attrs=Object.entries(attributes || {}).filter(([key])=>/^data-[a-z0-9_-]+$/i.test(String(key))).map(([key,value])=>`${rhiUxEscape(key)}="${rhiUxEscape(value)}"`).join(" "); const style=imageStyle ? ` style="${rhiUxEscape(imageStyle)}"` : "";
  return `<button type="button" class="rhiUxVisualChoice${selected ? " selected" : ""}" data-rhi-visual-choice="${rhiUxEscape(id)}" ${attrs} aria-pressed="${selected ? "true" : "false"}><span class="rhiUxVisualChoiceImage">${image ? `<img src="${rhiUxEscape(image)}" alt="${rhiUxEscape(imageAlt)}"${style}>` : ""}</span><span class="rhiUxVisualChoiceCopy">${eyebrow ? `<small>${rhiUxEscape(eyebrow)}</small>` : ""}<b>${rhiUxEscape(label)}</b>${detail ? `<em>${rhiUxEscape(detail)}</em>` : ""}</span></button>`;
}
function rhiUxVisualSelect({ label = "", value = "", options = [], placeholder = "", disabled = false, attribute = "data-rhi-visual-select" } = {}) {
  const current=String(value ?? ""); const first=placeholder ? `<option value="" ${current ? "" : "selected"} disabled>${rhiUxEscape(placeholder)}</option>` : ""; const rows=options.map(row=>typeof row==="object" ? row : {value:row,label:row}).map(row=>`<option value="${rhiUxEscape(row.value)}" ${String(row.value)===current ? "selected" : ""}>${rhiUxEscape(row.label ?? row.value)}</option>`).join(""); return `<label><span>${rhiUxEscape(label)}</span><select ${rhiUxEscape(attribute)}="1" ${disabled ? "disabled" : ""}>${first}${rows}</select></label>`;
}

function rhiUxCoreStyles() {
  return "/* RHI UX Core 1.6.4 */\n:host,.rhi-ux-root{\n  --rhi-color-primary:#1467F5;\n  --rhi-color-primary-soft:#EAF3FF;\n  --rhi-color-text:#0F172A;\n  --rhi-color-muted:#64748B;\n  --rhi-color-muted-soft:#758399;\n  --rhi-color-line:#DCE5EF;\n  --rhi-color-line-soft:#EAF0F6;\n  --rhi-color-surface:#FFFFFF;\n  --rhi-color-surface-soft:#F8FAFC;\n  --rhi-color-ok:#22C55E;\n  --rhi-color-attention:#F59E0B;\n  --rhi-color-error:#B42318;\n  --rhi-color-unknown:#94A3B8;\n\n  --rhi-font-family:var(--ha-font-family-body,Roboto,Noto,sans-serif);\n  --rhi-font-family-mono:var(--ha-font-family-code,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace);\n  --rhi-font-display:clamp(29px,2.55vw,42px);\n  --rhi-font-section:clamp(18px,1.4vw,22px);\n  --rhi-font-card:15px;\n  --rhi-font-body:12.5px;\n  --rhi-font-small:11px;\n  --rhi-font-label:10.5px;\n  --rhi-font-value:13px;\n  --rhi-font-diagnostic:10px;\n  --rhi-weight-regular:400;\n  --rhi-weight-medium:500;\n  --rhi-weight-strong:600;\n  --rhi-line-height-tight:1.15;\n  --rhi-line-height-body:1.42;\n\n  --rhi-space-1:4px;\n  --rhi-space-2:7px;\n  --rhi-space-3:10px;\n  --rhi-space-4:14px;\n  --rhi-space-5:18px;\n  --rhi-space-6:24px;\n  --rhi-radius-sm:9px;\n  --rhi-radius-md:12px;\n  --rhi-radius-lg:16px;\n  --rhi-radius-xl:20px;\n  --rhi-shadow-sm:0 4px 14px rgba(21,61,115,.025);\n  --rhi-shadow-md:0 7px 20px rgba(15,35,80,.035);\n  --rhi-page-max:1640px;\n  --rhi-page-pad-x:24px;\n  --rhi-page-pad-y:14px;\n  --rhi-control-h:38px;\n  --rhi-icon-action:18px;\n  --rhi-icon-status:24px;\n  --rhi-break-phone:430px;\n  --rhi-break-tablet:760px;\n  --rhi-break-desktop:1024px;\n  --rhi-domain-accent:var(--rhi-color-primary);\n\n  color:var(--rhi-color-text);\n  font-family:var(--rhi-font-family);\n  font-size:var(--rhi-font-body);\n  font-weight:var(--rhi-weight-regular);\n  line-height:var(--rhi-line-height-body);\n}\n\n.rhiUxDomainShell{\n  --rhi-nav-active-bg:var(--rhi-color-primary-soft);\n  --rhi-nav-active-border:#CFDEF1;\n  --rhi-nav-active-text:#0F4CA4;\n  position:relative;display:grid;grid-template-columns:minmax(0,1fr) clamp(190px,23%,280px);\n  width:100%;margin:0 0 12px;border:1px solid var(--rhi-color-line);border-radius:var(--rhi-radius-xl);\n  background:linear-gradient(180deg,rgba(255,255,255,.96),rgba(249,251,254,.91));box-shadow:var(--rhi-shadow-md);overflow:hidden;\n}\n.rhiUxProductArea{min-width:0;overflow:hidden}\n.rhiUxDomainShellTop{min-height:68px;display:grid;grid-template-columns:minmax(168px,.52fr) minmax(0,1.48fr);align-items:center;gap:14px;padding:10px 22px 9px}\n.rhiUxDomainIdentity{display:grid;align-content:center;gap:2px;min-width:0;min-height:48px;padding:2px 0 0 4px}\n.rhiUxDomainIdentity span{font-size:13px;line-height:1.15;font-weight:var(--rhi-weight-regular);color:#58708F;white-space:nowrap}\n.rhiUxDomainIdentity strong{font-size:21px;line-height:1.03;letter-spacing:.045em;font-weight:var(--rhi-weight-strong);color:#0B467F;white-space:nowrap}\n.rhiUxModuleTabs{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;min-width:0}\n.rhiUxModuleTab,.rhiUxDomainTab{appearance:none;border:0;background:transparent;font:inherit;color:#53647D;cursor:pointer;white-space:nowrap}\n.rhiUxModuleTab{min-height:40px;border-radius:12px;padding:8px;font-size:12px;font-weight:var(--rhi-weight-medium)}\n.rhiUxModuleTab.active{background:var(--rhi-nav-active-bg);color:var(--rhi-nav-active-text);box-shadow:inset 0 0 0 1px var(--rhi-nav-active-border),0 6px 16px rgba(15,23,42,.035)}\n.rhiUxDomainShellBottom{padding:5px 22px 7px;border-top:1px solid var(--rhi-color-line-soft);background:rgba(255,255,255,.52);min-height:46px;box-sizing:border-box}\n.rhiUxDomainTabs{display:flex;align-items:center;gap:10px;min-height:34px;overflow-x:auto;scrollbar-width:none}\n.rhiUxDomainTabs::-webkit-scrollbar{display:none}\n.rhiUxDomainTab{flex:0 0 auto;min-height:34px;border-radius:11px;padding:7px 12px;font-size:11.5px;font-weight:var(--rhi-weight-medium);color:#5F6D80}\n.rhiUxDomainTab.active{background:var(--rhi-nav-active-bg);color:var(--rhi-nav-active-text);box-shadow:inset 0 0 0 1px var(--rhi-nav-active-border)}\n.rhiUxCompanyBrand{min-width:0;border-left:1px solid var(--rhi-color-line-soft);display:grid;place-items:center;padding:10px 16px;background:linear-gradient(180deg,rgba(252,254,255,.78),rgba(247,250,253,.58))}\n.rhiUxCompanyLogo{display:block;width:min(100%,250px);max-height:116px;line-height:0;overflow:hidden}\n.rhiUxCompanyLogo svg{display:block;width:100%;height:auto;max-height:116px;object-fit:contain;object-position:center}\n\n/* Canonical page stack: visual order is invariant across domains. */\n.rhiUxPageStack{display:flex;flex-direction:column}\n.rhiUxPageStack>.rhiUxPageHero{order:1}\n.rhiUxPageStack>.rhiUxStatusGrid{order:2}\n.rhiUxPageStack>.rhiUxQuickActionBar{order:3}\n\n/* Canonical page hero: image is one background layer, never a split side panel. */\n.rhiUxPageHero{\n  position:relative;display:block;height:146px;min-height:146px;overflow:hidden;\n  border:0;border-radius:var(--rhi-radius-lg);background:#fff;box-shadow:none;margin:0;\n}\n.rhiUxPageHeroCopy{\n  position:relative;z-index:4;width:min(48%,650px);max-width:none;padding:20px 18px 18px 22px;box-sizing:border-box;\n}\n.rhiUxPageHeroCopy>small{display:none}\n.rhiUxPageHeroCopy h1,.rhiUxPageHeroCopy h2{\n  margin:4px 0 8px;font-size:var(--rhi-font-display);line-height:1.02;letter-spacing:-.038em;\n  color:#0B1739;font-weight:var(--rhi-weight-strong);\n}\n.rhiUxPageHeroCopy p{\n  margin:0;max-width:520px;font-size:clamp(12.5px,1.05vw,15px);line-height:var(--rhi-line-height-body);\n  color:#536781;font-weight:var(--rhi-weight-regular);\n}\n.rhiUxPageHeroArt{position:absolute;z-index:1;inset:0 0 0 28%;display:block;overflow:hidden;pointer-events:none}\n.rhiUxPageHeroArt:before{\n  content:\"\";display:block;position:absolute;z-index:2;inset:0;\n  background:linear-gradient(90deg,#fff 0%,rgba(255,255,255,.95) 8%,rgba(255,255,255,.62) 19%,rgba(255,255,255,.10) 38%,rgba(255,255,255,0) 57%);\n}\n.rhiUxPageHeroArt img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:center 52%;transform:none}\n\n/* One canonical page status layer. */\n.rhiUxStatusGrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin:7px 0 0;padding:0;border:0;background:transparent;box-shadow:none}\n.rhiUxStatusItem{\n  min-width:0;min-height:68px;display:grid;grid-template-columns:44px minmax(0,1fr);gap:10px;align-items:center;\n  padding:10px 12px;border:1px solid var(--rhi-color-line);border-radius:var(--rhi-radius-md);background:#fff;box-shadow:var(--rhi-shadow-md);\n}\n.rhiUxStatusIcon{width:36px;height:36px;border-radius:11px;display:flex;align-items:center;justify-content:center;background:#F0F5FC;color:#355D96;font-size:18px}\n.rhiUxStatusIcon ha-icon{--mdc-icon-size:var(--rhi-icon-status)}\n.rhiUxStatusCopy{min-width:0;display:block}\n.rhiUxStatusCopy small{display:block;margin:0 0 2px;color:#476487;font-size:var(--rhi-font-label);font-weight:var(--rhi-weight-medium);line-height:1.2}\n.rhiUxStatusCopy b{display:block;margin:0 0 2px;color:var(--rhi-color-text);font-size:clamp(14px,1.12vw,17px);font-weight:var(--rhi-weight-strong);line-height:1.12;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.rhiUxStatusCopy em{display:block;margin-top:2px;color:var(--rhi-color-muted);font-size:var(--rhi-font-small);font-style:normal;font-weight:var(--rhi-weight-regular);line-height:1.25;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n\n/* Canonical page-level quick actions. */\n.rhiUxQuickActionBar,.rhiEnergyQuickActions,.rhi-top-actions{\n  min-height:48px;padding:5px 8px;margin:7px 0 0;border:1px solid var(--rhi-color-line);border-radius:var(--rhi-radius-md);\n  background:#fff;box-shadow:var(--rhi-shadow-sm);display:flex;align-items:center;gap:7px;flex-wrap:wrap;\n}\n.rhiUxQuickActionBar>small,.rhiEnergyQuickActions>small,.rhi-top-actions-title{\n  font-size:var(--rhi-font-label);letter-spacing:.10em;text-transform:uppercase;color:#476487;\n  font-weight:var(--rhi-weight-medium);margin-right:2px;white-space:nowrap;\n}\n.rhiUxQuickActions{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:0}\n.rhiUxQuickAction,.rhiUxQuickActionBar button,.rhiEnergyQuickActions .hiAction,.rhi-top-action{\n  height:36px;min-height:36px;border:1px solid #D6E0EB;border-radius:9px;background:#fff;color:#125DB7;\n  box-shadow:none;font:inherit;font-size:11.5px;font-weight:var(--rhi-weight-medium);padding:0 12px;\n  display:inline-flex;align-items:center;justify-content:center;gap:7px;cursor:pointer;white-space:nowrap;\n}\n.rhiUxQuickAction.primary,.rhiUxQuickActionBar button:first-of-type,.rhiEnergyQuickActions .hiAction:first-of-type,.rhi-top-action.primary{\n  background:var(--rhi-color-primary);border-color:var(--rhi-color-primary);color:#fff;\n}\n.rhiUxQuickAction:disabled,.rhiEnergyQuickActions .hiAction:disabled,.rhi-top-action:disabled{opacity:.46}\n\n/* Canonical body grammar. */\n.rhiUxDomainBody{font-family:var(--rhi-font-family);color:var(--rhi-color-text);font-size:var(--rhi-font-body);line-height:var(--rhi-line-height-body)}\n.rhiUxDomainBody button,.rhiUxDomainBody select,.rhiUxDomainBody input,.rhiUxDomainBody textarea{font-family:inherit}\n.rhiUxPanel,.rhiUxDomainBody .panel,.rhiUxDomainBody .info,.rhiUxDomainBody .summary,.rhiUxDomainBody .ov-panel{\n  border:1px solid var(--rhi-color-line);border-radius:var(--rhi-radius-lg);background:var(--rhi-color-surface);box-shadow:var(--rhi-shadow-sm);\n}\n.rhiUxPanel{padding:14px 16px}\n.rhiUxDomainBody .panel h2,.rhiUxDomainBody .info h2,.rhiUxDomainBody .summary h2,.rhiUxDomainBody .ov-panel h2{\n  font-size:var(--rhi-font-section);font-weight:var(--rhi-weight-strong);line-height:var(--rhi-line-height-tight);letter-spacing:-.02em;color:var(--rhi-color-text);\n}\n.rhiUxDomainBody .panel h3,.rhiUxDomainBody .info h3,.rhiUxDomainBody .summary h3,.rhiUxDomainBody .ov-panel h3{\n  font-size:var(--rhi-font-card);font-weight:var(--rhi-weight-strong);line-height:1.2;color:var(--rhi-color-text);\n}\n.rhiUxDomainBody .panel p,.rhiUxDomainBody .info p,.rhiUxDomainBody .summary p,.rhiUxDomainBody .ov-panel p{\n  font-size:var(--rhi-font-body);font-weight:var(--rhi-weight-regular);line-height:var(--rhi-line-height-body);color:var(--rhi-color-muted);\n}\n.rhiUxDataList{display:grid;gap:6px}\n.rhiUxDataRow{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:12px;align-items:center;padding:9px 10px;border:1px solid var(--rhi-color-line-soft);border-radius:var(--rhi-radius-sm);background:var(--rhi-color-surface-soft)}\n.rhiUxState{display:grid;gap:4px;padding:14px 16px;border:1px dashed var(--rhi-color-line);border-radius:var(--rhi-radius-md);background:var(--rhi-color-surface-soft);color:var(--rhi-color-muted)}\n.rhiUxState b{color:var(--rhi-color-text);font-size:13px}\n.rhiUxState[data-state=\"attention\"]{border-color:#F6D48C;background:#FFFBEB}\n.rhiUxState[data-state=\"error\"]{border-color:#F1B8B4;background:#FFF7F7}\n.rhiUxConclusion{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:12px;margin:8px 0 0;padding:10px 12px;border:1px solid var(--rhi-color-line);border-radius:var(--rhi-radius-md);background:linear-gradient(135deg,rgba(255,255,255,.98),rgba(247,250,252,.96))}\n.rhiUxConclusion small{font-size:var(--rhi-font-label);letter-spacing:.1em;text-transform:uppercase;color:var(--rhi-color-muted)}\n.rhiUxConclusion h2{font-size:var(--rhi-font-card);line-height:1.2;margin:1px 0 2px}\n.rhiUxConclusion p{font-size:var(--rhi-font-small);line-height:1.3;margin:0;color:var(--rhi-color-muted)}\n.rhiUxTechnicalFooter{display:flex;justify-content:center;flex-wrap:wrap;gap:4px 9px;margin:6px 0 0;padding:3px 2px 0;border-top:1px solid rgba(148,163,184,.20);color:#94A3B8;font-size:9px;line-height:1.2}\n.rhiUxTechnicalFooter span+span:before{content:\"·\";margin-right:9px;color:#CBD5E1}\n.rhiUxTechnicalFooter [data-severity=\"warning\"]{color:#B7791F;font-weight:var(--rhi-weight-strong)}\n.rhiUxTechnicalFooter [data-severity=\"error\"]{color:var(--rhi-color-error);font-weight:var(--rhi-weight-strong)}\n\n@media(max-width:1180px){\n  :host,.rhi-ux-root{--rhi-page-pad-x:18px}\n  .rhiUxPageHero{height:140px;min-height:140px}\n  .rhiUxPageHeroCopy{width:51%;padding:18px 14px 16px 18px}\n  .rhiUxPageHeroArt{inset:0 0 0 30%}\n  .rhiUxStatusItem{grid-template-columns:40px minmax(0,1fr);padding:9px 10px;min-height:66px}\n  .rhiUxStatusIcon{width:37px;height:37px}\n}\n@media(max-width:760px){\n  :host,.rhi-ux-root{--rhi-page-pad-x:10px;--rhi-page-pad-y:9px;--rhi-font-body:12px;--rhi-font-small:10.75px}\n  .rhiUxDomainShell{grid-template-columns:1fr}.rhiUxCompanyBrand{display:none}.rhiUxDomainShellTop{grid-template-columns:1fr;padding:10px 12px}.rhiUxDomainIdentity{min-height:auto}.rhiUxDomainShellBottom{padding:7px 12px 9px}\n  .rhiUxPageHero{height:128px;min-height:128px;border-radius:14px}\n  .rhiUxPageHeroCopy{width:59%;padding:18px 9px 16px 13px}\n  .rhiUxPageHeroCopy h1,.rhiUxPageHeroCopy h2{font-size:27px;letter-spacing:-.032em}\n  .rhiUxPageHeroCopy p{font-size:11px;line-height:1.32;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}\n  .rhiUxPageHeroArt{inset:0 0 0 34%}\n  .rhiUxStatusGrid{grid-template-columns:repeat(2,minmax(0,1fr))}\n  .rhiUxStatusItem{min-height:74px;grid-template-columns:34px minmax(0,1fr);gap:7px;padding:8px}\n  .rhiUxStatusIcon{width:32px;height:32px;border-radius:9px}.rhiUxStatusIcon ha-icon{--mdc-icon-size:20px}\n  .rhiUxQuickActionBar,.rhiEnergyQuickActions,.rhi-top-actions{overflow-x:auto;flex-wrap:nowrap}\n  .rhiUxQuickActionBar>small,.rhiEnergyQuickActions>small,.rhi-top-actions-title,.rhiUxQuickAction,.rhiUxQuickActionBar button,.rhiEnergyQuickActions .hiAction,.rhi-top-action{flex:0 0 auto}\n  .rhiUxConclusion{grid-template-columns:1fr}\n}\n@media(max-width:430px){\n  :host,.rhi-ux-root{--rhi-page-pad-x:8px;--rhi-page-pad-y:8px}\n  .rhiUxPageHero{height:118px;min-height:118px}\n  .rhiUxPageHeroCopy{width:64%;padding:16px 8px 14px 11px}\n  .rhiUxPageHeroCopy h1,.rhiUxPageHeroCopy h2{font-size:24px}\n  .rhiUxPageHeroCopy p{font-size:10.5px;-webkit-line-clamp:2}\n  .rhiUxPageHeroArt{inset:0 0 0 38%}\n  .rhiUxStatusGrid{grid-template-columns:1fr 1fr}\n}\n\n/* Optional body/section-scoped view and filter controls. */\n.rhiUxContextBar{\n  min-height:42px;padding:4px 7px;margin:0 0 8px;border:1px solid var(--rhi-color-line);border-radius:var(--rhi-radius-md);\n  background:#fff;box-shadow:var(--rhi-shadow-sm);display:flex;align-items:center;gap:7px;flex-wrap:wrap;\n}\n.rhiUxContextBar>small{\n  font-size:var(--rhi-font-label);letter-spacing:.10em;text-transform:uppercase;color:#476487;font-weight:var(--rhi-weight-medium);white-space:nowrap;\n}\n.rhiUxContextControls{display:flex;align-items:center;gap:6px;flex-wrap:wrap}\n.rhiUxContextControl{\n  min-height:32px;border:1px solid #D6E0EB;border-radius:9px;background:#fff;color:#355D96;font:inherit;font-size:11.5px;font-weight:var(--rhi-weight-medium);padding:0 11px;cursor:pointer;white-space:nowrap;\n}\n.rhiUxContextControl.active,.rhiUxContextControl[aria-pressed=\"true\"]{background:var(--rhi-color-primary-soft);border-color:#CFDEF1;color:#0F4CA4}\n.rhiUxContextControl:disabled{opacity:.46}\n@media(max-width:760px){.rhiUxContextBar{overflow-x:auto;flex-wrap:nowrap}.rhiUxContextBar>small,.rhiUxContextControls,.rhiUxContextControl{flex:0 0 auto}}\n\n/* Canonical cross-domain appearance picker. Domains own catalogs and persistence. */\n.rhiUxVisualPickerBackdrop{position:fixed;inset:0;z-index:9999;background:rgba(15,23,42,.44);display:grid;place-items:center;padding:20px}\n.rhiUxVisualPickerPanel{width:min(920px,94vw);max-height:min(82vh,760px);overflow:hidden;background:#fff;border:1px solid var(--rhi-color-line);border-radius:20px;box-shadow:0 30px 80px rgba(15,23,42,.24);padding:16px;box-sizing:border-box;display:grid;grid-template-rows:auto auto minmax(0,1fr) auto auto;gap:10px}\n.rhiUxVisualPickerHead{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;min-height:0}\n.rhiUxVisualPickerHead small{font-size:var(--rhi-font-label);font-weight:800;letter-spacing:.12em;color:#64748b}.rhiUxVisualPickerHead h3{margin:2px 0 0;font-size:20px}.rhiUxVisualPickerHead p{margin:3px 0 0;font-size:11px;color:#64748b}\n.rhiUxVisualPickerFilters{display:flex;gap:6px;flex-wrap:wrap;margin:0;min-height:0}\n.rhiUxVisualPickerFilters button{border:1px solid #dbe3ee;background:#fff;border-radius:999px;padding:5px 10px;font-size:11px;font-weight:700;cursor:pointer}.rhiUxVisualPickerFilters button.selected{border-color:#93c5fd;background:#eff6ff;color:#1d4ed8}\n.rhiUxVisualChoiceGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));grid-auto-rows:142px;gap:8px;margin:0;overflow-y:auto;overscroll-behavior:contain;padding:2px 3px 4px 1px;align-content:start}\n.rhiUxVisualChoice{height:142px;min-height:142px;max-height:142px;display:grid;grid-template-rows:86px minmax(0,1fr);gap:6px;align-items:stretch;text-align:left;border:1px solid #e2e8f0;background:#fff;border-radius:12px;padding:8px;cursor:pointer;overflow:hidden}.rhiUxVisualChoice:hover{border-color:#93c5fd;background:#f8fbff}.rhiUxVisualChoice.selected{border-color:#2563eb;box-shadow:0 0 0 2px rgba(37,99,235,.12);background:#f8fbff}\n.rhiUxVisualChoiceImage{width:100%;height:86px;min-width:0;min-height:86px;max-width:none;max-height:86px;display:grid;place-items:center;overflow:hidden}.rhiUxVisualChoiceImage img{display:block;width:100%;height:100%;min-width:0;min-height:0;max-width:100%;max-height:100%;object-fit:contain;object-position:center}\n.rhiUxVisualChoiceCopy{min-width:0;align-self:end}.rhiUxVisualChoiceCopy small,.rhiUxVisualChoiceCopy b,.rhiUxVisualChoiceCopy em{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.rhiUxVisualChoiceCopy small{font-size:var(--rhi-font-label);color:#64748b;text-transform:uppercase}.rhiUxVisualChoiceCopy b{font-size:12px;margin-top:1px}.rhiUxVisualChoiceCopy em{font-size:var(--rhi-font-small);color:#64748b;font-style:normal;margin-top:1px}\n.rhiUxVisualPickerRefine{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:8px;margin:0}.rhiUxVisualPickerRefine label span{display:block;font-size:var(--rhi-font-label);color:#64748b;margin-bottom:3px}.rhiUxVisualPickerRefine select{width:100%;height:34px;border:1px solid #dbe3ee;border-radius:8px;background:#fff;padding:0 8px}\n.rhiUxVisualPickerFooter{display:flex;align-items:center;gap:8px;margin:0;padding-top:9px;border-top:1px solid #edf1f6}.rhiUxVisualPickerSpacer{flex:1}.rhiUxVisualPickerFooter button{height:34px;border:1px solid #dbe3ee;border-radius:9px;background:#fff;padding:0 12px;font-size:var(--rhi-font-small);font-weight:700}.rhiUxVisualPickerFooter button.primary{background:#0b65ea;color:#fff;border-color:#0b65ea}.rhiUxVisualPickerFooter button:disabled{opacity:.45}\n@media(max-width:900px){.rhiUxVisualChoiceGrid{grid-template-columns:repeat(2,minmax(0,1fr))}}\n@media(max-width:560px){.rhiUxVisualPickerBackdrop{padding:8px}.rhiUxVisualPickerPanel{width:96vw;max-height:88vh;padding:12px}.rhiUxVisualChoiceGrid{grid-template-columns:1fr;grid-auto-rows:116px}.rhiUxVisualChoice{height:116px;min-height:116px;max-height:116px;grid-template-columns:94px minmax(0,1fr);grid-template-rows:1fr}.rhiUxVisualChoiceImage{width:94px;height:86px;min-width:94px;max-width:94px}.rhiUxVisualChoiceCopy{align-self:center}.rhiUxVisualPickerRefine{grid-template-columns:1fr 1fr}.rhiUxVisualPickerFooter{flex-wrap:wrap}}\n\n\n/* Canonical page and asset composition primitives. */\n.rhiUxPage{display:block;width:100%;max-width:var(--rhi-page-max);margin:0 auto;padding:var(--rhi-page-pad-y) var(--rhi-page-pad-x);box-sizing:border-box}\n.rhiUxPageContent{display:grid;gap:var(--rhi-space-3);margin-top:var(--rhi-space-3)}\n.rhiUxAssetCardShell{display:grid;gap:var(--rhi-space-3);min-width:0;padding:12px;border:1px solid var(--rhi-color-line);border-radius:var(--rhi-radius-lg);background:var(--rhi-color-surface);box-shadow:var(--rhi-shadow-sm)}\n.rhiUxAssetCardIdentity,.rhiUxAssetCardFacts,.rhiUxAssetCardRelationships,.rhiUxAssetCardActions,.rhiUxAssetCardDetails,.rhiUxAssetCardFeedback{min-width:0}\n.rhiUxAssetCardRelationships{display:grid;gap:var(--rhi-space-2)}\n.rhiUxAssetCardActions{display:flex;align-items:center;gap:var(--rhi-space-2);flex-wrap:wrap}\n.rhiUxAssetCardDetails:empty,.rhiUxAssetCardFeedback:empty{display:none}\n.rhiUxAssetIdentity{display:grid;grid-template-columns:auto minmax(0,1fr);gap:12px;align-items:center;min-width:0}\n.rhiUxAssetVisual{width:72px;height:58px;display:grid;place-items:center;overflow:hidden}\n.rhiUxAssetVisual img{display:block;width:100%;height:100%;object-fit:contain}\n.rhiUxAssetIdentityCopy{min-width:0}.rhiUxAssetIdentityCopy small{display:block;color:var(--rhi-color-muted);font-size:var(--rhi-font-label);text-transform:uppercase;letter-spacing:.08em}\n.rhiUxAssetIdentityCopy h2{margin:2px 0;font-size:var(--rhi-font-section);line-height:1.12}.rhiUxAssetIdentityCopy p{margin:0;color:var(--rhi-color-muted);font-size:var(--rhi-font-body)}\n.rhiUxAssetFactGrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--rhi-space-2)}\n.rhiUxAssetFact{min-width:0;padding:9px 10px;border:1px solid var(--rhi-color-line);border-radius:var(--rhi-radius-md);background:var(--rhi-color-surface)}\n.rhiUxAssetFact small,.rhiUxAssetFact b,.rhiUxAssetFact span{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}\n.rhiUxAssetFact small{font-size:var(--rhi-font-label);color:var(--rhi-color-muted)}.rhiUxAssetFact b{margin-top:2px;font-size:13px}.rhiUxAssetFact span{margin-top:2px;font-size:var(--rhi-font-small);color:var(--rhi-color-muted)}\n.rhiUxAssetRelationship{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:9px 10px;border:1px solid var(--rhi-color-line-soft);border-radius:var(--rhi-radius-md);background:var(--rhi-color-surface-soft)}\n.rhiUxAssetRelationship small,.rhiUxAssetRelationship b,.rhiUxAssetRelationship span{display:block}.rhiUxAssetRelationship small,.rhiUxAssetRelationship span{color:var(--rhi-color-muted);font-size:var(--rhi-font-small)}\n.rhiUxAssetDisclosure{border-top:1px solid var(--rhi-color-line-soft);padding-top:8px}.rhiUxAssetDisclosure summary{cursor:pointer;font-weight:var(--rhi-weight-medium)}\n.rhiUxAssetDisclosure>div{padding-top:8px}\n.rhiUxWriteFeedback{margin-top:6px;font-size:var(--rhi-font-small);color:var(--rhi-color-muted)}.rhiUxWriteFeedback[data-state=\"success\"]{color:#15803D}.rhiUxWriteFeedback[data-state=\"error\"]{color:var(--rhi-color-error)}\n@media(max-width:760px){.rhiUxAssetCardShell{padding:10px}.rhiUxAssetFactGrid{grid-template-columns:repeat(2,minmax(0,1fr))}}\n@media(max-width:430px){.rhiUxAssetCardShell{gap:var(--rhi-space-2);padding:9px}.rhiUxAssetFactGrid{grid-template-columns:1fr 1fr}}\n\n\n/* Compact asset grammar. Opt-in: existing page heroes, navigation and panels are unchanged.\n   Domains own asset facts and relationships; Core only lays out their presentation. */\n.rhiUxAssetRow{\n  display:grid;grid-template-columns:52px minmax(0,1fr) minmax(76px,max-content) auto;\n  align-items:center;gap:10px;min-width:0;padding:8px 10px;\n  border-bottom:1px solid var(--rhi-color-line-soft);\n}\n.rhiUxAssetRow:last-child{border-bottom:0}\n.rhiUxAssetImage{\n  display:flex;align-items:center;justify-content:center;width:52px;height:52px;\n  border-radius:var(--rhi-radius-sm);background:var(--rhi-color-surface-soft);overflow:hidden;\n}\n.rhiUxAssetImage img{display:block;width:100%;height:100%;object-fit:contain}\n.rhiUxAssetRowIdentity{display:grid;gap:3px;min-width:0}\n.rhiUxAssetName{font-weight:var(--rhi-weight-strong);overflow-wrap:anywhere}\n.rhiUxAssetContext,.rhiUxAssetRowRelationship{font-size:var(--rhi-font-small);color:var(--rhi-color-muted);line-height:1.25}\n.rhiUxAssetRowRelationship .rhiUxAssetRelationshipLink{color:var(--rhi-color-primary);text-decoration:underline;text-underline-offset:2px}\n.rhiUxAssetRowRelationship .rhiUxAssetRelationshipLink:focus-visible{outline:2px solid var(--rhi-color-primary);outline-offset:3px}\n.rhiUxAssetLive{display:grid;justify-items:end;gap:3px;text-align:right;min-width:76px}\n.rhiUxAssetPower{font-size:var(--rhi-font-card);font-weight:var(--rhi-weight-strong);font-variant-numeric:tabular-nums;white-space:nowrap}\n.rhiUxAssetState{font-size:var(--rhi-font-small);color:var(--rhi-color-muted)}\n.rhiUxAssetExpand{display:flex;align-items:center;justify-content:center;min-width:32px;min-height:36px}\n@media(max-width:430px){\n  .rhiUxAssetRow{grid-template-columns:42px minmax(0,1fr) minmax(64px,max-content) auto;gap:7px;padding:7px 5px}\n  .rhiUxAssetImage{width:42px;height:42px}\n  .rhiUxAssetLive{min-width:64px}\n}\n\n/* Opt-in time-series presentation: preserve domain-owned data, periods and charts. */\n.rhiUxChartPanel{min-width:0;padding:12px;border:1px solid var(--rhi-color-line);border-radius:var(--rhi-radius-lg);background:var(--rhi-color-surface)}\n.rhiUxChartHeader{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-bottom:8px}\n.rhiUxChartLegend{display:flex;align-items:center;gap:8px 14px;flex-wrap:wrap;font-size:var(--rhi-font-small);color:var(--rhi-color-muted)}\n.rhiUxChartViewport{width:100%;min-width:0;overflow-x:auto}\n.rhiUxChartViewport svg,.rhiUxChartViewport canvas{display:block;max-width:100%}\n.rhiUxChartEmpty{padding:20px 12px;text-align:center;color:var(--rhi-color-muted);font-size:var(--rhi-font-small)}\n@media(max-width:760px){.rhiUxChartPanel{padding:9px}.rhiUxChartHeader{align-items:flex-start}}\n";
}

// ---- src/app/localization.js ----
// Energy product localization.
// Machine identifiers and backend semantic codes remain untranslated.
const RHI_ENERGY_TRANSLATIONS = Object.freeze({
  en:Object.freeze({
    "planning.day_after_tomorrow":"Day after tomorrow",
    "planning.d2_need":"Need entering day after tomorrow",
    "planning.d2_planned":"Planned day after tomorrow",
    "planning.d2_remaining":"Still after day after tomorrow",

    "history.grid_import":"Grid import history",
    "history.grid_export":"Grid export history",
    "history.home":"Home consumption history",
    "history.flexible":"Flexible load history",
    "history.measured_power":"Measured power (kW) from Home Assistant history; not a derived energy total.",
    "history.unavailable":"Measured history unavailable",
    "history.unavailable_desc":"No unique, available canonical Home Assistant sensor is published for this history. No values are estimated.",

    "flow.native_title":"Measured energy flow",
    "flow.native_desc":"Measured canonical power; unknown sources and directions are not estimated.",
    "flow.native_solar":"Solar production",
    "flow.native_grid_import":"Grid import",
    "flow.native_grid_export":"Grid export",
    "flow.native_site":"Site consumption",
    "flow.native_home":"Home consumption",
    "flow.native_flexible":"Flexible loads",
    "flow.native_battery":"Battery power",

    "nav.energy":"Energy","nav.overview":"Overview","nav.flow":"Flow","nav.solar":"Solar","nav.battery":"Home Battery","nav.consumption":"Consumption","nav.gas":"Gas",
    "nav.intelligence":"Intelligence","nav.plan":"Plan","nav.operational_plan":"Now","nav.tactical_plan":"Today & Tomorrow","nav.strategic_plan":"Long term","nav.settings":"Settings","nav.insights":"Insights","nav.performance":"Performance","nav.value":"Value","nav.retrospective":"Retrospective",
    "hero.overview.title":"Energy Overview","hero.overview.description":"See what your home is producing, using, storing and exchanging right now.",
    "hero.flow.title":"Energy Flow","hero.flow.description":"See where energy is coming from and where it is going right now.",
    "hero.solar.title":"Solar","hero.solar.description":"See current solar production and the equipment contributing to it.",
    "hero.battery.title":"Home Battery","hero.battery.description":"See stored energy, current battery activity and the reserve available to your home.",
    "hero.consumption.title":"Consumption","hero.consumption.description":"See where energy is being used and which flexible loads can be planned.",
    "hero.gas.title":"Gas","hero.gas.description":"See gas use over time and whether measurements are available.",
    "hero.plan.title":"Plan","hero.plan.description":"See what should happen now, today and tomorrow, and what still needs attention.",
    "hero.strategic.title":"Strategic","hero.strategic.description":"Understand longer-term energy policy and where supporting evidence is still incomplete.",
    "hero.operational.title":"Operational","hero.operational.description":"See which flexible loads can act now, which are waiting and why.","nav.forecast":"Forecast","forecast.incomplete_title":"Forecast is incomplete","forecast.incomplete_desc":"Some supply, demand or grid totals are not published. The available values do not form a complete energy balance.","forecast.flexible_scheduled":"Flexible loads planned","forecast.flexible_known":"Known charging need","forecast.flexible_unknown":"Flexible load demand","forecast.per_asset_missing":"Individual charging needs are not published for this horizon. Check Mobility planning readiness.","forecast.row_planned":"Planned","forecast.row_needed":"Needed, not scheduled","forecast.grid_unavailable":"Grid balance requires both import and export forecasts.",
    "hero.settings.title":"Settings","hero.settings.description":"Adjust how Home Intelligence should manage your energy within the available options.",
    "hero.performance.title":"Performance","hero.performance.description":"Review measured energy and how Home Intelligence performed.",
    "hero.value.title":"Value","hero.value.description":"See the financial result of your energy system for the selected period.",
    "hero.retrospective.title":"Retrospective","hero.retrospective.description":"See what worked, what needs attention and where evidence is still incomplete.",
    "common.quick_actions":"Quick actions","common.not_available":"Not available","common.not_measured":"Not measured","common.unknown":"Unknown",
    "common.details":"Details","common.diagnostics":"Diagnostics","common.configuration":"Configuration","common.children":"Children","common.save":"Save","common.cancel":"Cancel","common.reset":"Reset",
    "common.today":"Today","common.tomorrow":"Tomorrow","common.information_missing":"This information is not available yet.",
    "reason.intelligence_off":"Energy Intelligence is off","reason.automation_disabled":"Automation is disabled","reason.disabled":"Disabled","reason.not_available":"Not available","reason.not_published":"Information is not available yet.","reason.no_battery_policy":"Battery policy information is not available yet","reason.data_incomplete":"Some details are unavailable","reason.verification_required":"Verification is needed","reason.reset_pending":"Reset in progress","reason.confirmation_needed":"Confirmation needed","reason.waiting":"Waiting","reason.preparing":"Preparing","reason.not_configured":"Setup needed","common.appearance":"Appearance","common.choose_appearance":"Choose appearance","common.selected":"Selected","common.save_appearance":"Save appearance","common.automatic":"Automatic","common.off":"Off","common.advice":"Advice","common.forced":"Forced","common.high":"High","common.normal":"Normal","common.low":"Low","section.production_supply":"Production & supply","section.production_supply_desc":"Energy available to the home now.","section.consumption_desc":"Home use, flexible loads and battery charging. Grid export is separate.","overview.battery_charge":"Battery Charge","overview.battery_discharge":"Battery Discharge","overview.battery_charging":"Charging stationary storage","overview.battery_flow_unavailable":"Battery flow unavailable","overview.battery_flow_reason":"Battery charging or discharging cannot be confirmed.","overview.grid_flow_unavailable":"Grid flow unavailable","overview.grid_flow_reason":"Grid import or export cannot be confirmed.","overview.balance_incomplete":"The current site energy balance is not verified.","overview.home_excludes_storage":"Household consumption excluding Flexible Loads and Battery Charge","section.flexible_loads":"Flexible loads","section.flexible_loads_desc":"Current execution, next action, requested power and operational reason. Hardware configuration is not shown here.","section.other_assets":"Other assets","section.supply":"Supply","section.supply_desc":"Expected usable energy for the selected horizon.","section.demand":"Demand","section.demand_desc":"Expected Home Consumption, Flexible Loads and storage charging.","section.grid_impact":"Grid impact","section.grid_impact_desc":"Expected grid exchange for the selected horizon.","flow.physical":"Physical Energy Flow","flow.physical_desc":"Live measured energy paths only. Disabled and planning-only assets are excluded.","flow.producers":"Producers","flow.consumers":"Consumers","flow.charging_connections":"Charging connections","flow.charging_connections_desc":"Chargers and vehicle assignments currently visible to Energy.","flow.physical_consumers":"Physical consumers","flow.physical_consumers_desc":"Participating loads and their current charging connection; idle assets remain visible.","gas.history":"Gas usage history","gas.meter":"Gas meter","gas.meter_desc":"Current meter state and measured values.","gas.connect":"Connect your gas meter","gas.connect_desc":"Connect a gas meter before consumption history can be shown.","battery.state":"Home Battery state","battery.state_desc":"Combined operational truth for the Home Battery system.","battery.contributors":"Home Battery contributors","battery.contributors_desc":"Physical batteries contributing to the aggregate.","settings.automation":"Automation","settings.automation_desc":"Choose how much Home Intelligence may act for you.","settings.adjust":"What do you want to adjust?","settings.adjust_desc":"Settings are grouped by the part of your energy system you want to influence.","settings.effective":"Effective behavior","settings.participants":"Participating assets","metering.period":"Measurement period","metering.attention":"Metering attention","metering.attention_desc":"Resolve the selected period before relying on its totals.","metering.flexible_loads":"Flexible Loads","value.financial_result":"Financial result","value.pricing_settings":"Pricing settings","value.flexible_pricing":"Pricing of flexible loads","value.consumer_allocation":"Consumer allocation","planning.tactical":"Tactical planning","planning.strategic":"Strategic Planning","planning.not_available":"Strategy not available","planning.solar_generation":"Solar generation","planning.solar_unavailable":"Solar generation details are not available yet","planning.no_renderer":"This navigation target has no dedicated renderer.","appearance.description":"Choose the representative image. The selection is persisted by the owning domain and confirmed by readback.","common.horizon":"Horizon","common.period":"Period","common.status":"Status","common.default":"Default","common.name":"Name","common.this_hour":"This hour","common.week":"Week","common.month":"Month","common.year":"Year","common.highest_value":"Highest value","common.lowest_value":"Lowest value","pricing.export_compensation":"Export compensation","pricing.export_fee":"Export fee","pricing.commodity":"Commodity","pricing.network":"Network","pricing.taxes_levies":"Taxes & levies","pricing.vat":"VAT","hero.energy_overview":"Energy overview","hero.site_consumption":"Site Consumption","hero.energy_outlook":"Energy outlook","hero.live_flow":"Live energy flow","hero.solar_unavailable":"Solar production unavailable","hero.generating":"Generating now","hero.not_generating":"Not generating","hero.settings":"Settings","hero.operational_planning":"Operational Planning","hero.metering":"Metering","hero.home_intelligence":"Home Intelligence","hero.energy_retrospective":"Energy retrospective","hero.energy_value":"Energy value","overview.producing_now":"Producing now","overview.grid_import":"Grid Import","overview.importing":"Importing","overview.flex_contributor":"Flexible Load contributor","automation.mode":"Automation mode","automation.quick_action":"Quick action","automation.control":"Home Intelligence control","connection.not_connected":"Not connected","connection.connect_hint":"Connect to enable planning and charging.","connection.disabled_hint":"This load is disabled and excluded from planning.","connection.connected":"Connected","control.requested_charge_power":"Requested charge power","control.requested_charge_power_desc":"Charging power requested from this asset.","relationship.part_of":"Part of","battery.system":"Battery system","battery.power_now":"Power now","battery.soc":"State of charge","battery.capacity":"Capacity","battery.available_energy":"Available energy","solar.production_now":"Production now","automation.authority":"Automation authority","consumer.managed":"Flexible loads","consumer.managed_desc":"Primary cards show current power and energy need. Details contain additional user information; technical evidence stays in diagnostics.","retro.planning_outcomes":"Planning outcomes","retro.execution_results":"Execution results","retro.measured_energy":"Measured energy","retro.open_period":"Open period review","retro.weekly":"Weekly review","intelligence.current_situation":"Current situation","planning.solar":"Solar","planning.battery_out":"Home Battery out","planning.grid_in":"Grid in","planning.home":"Home","planning.battery_in":"Home Battery in","planning.grid_out":"Grid out","planning.hourly_desc":"Hourly view of expected production, consumption, storage and grid exchange.","common.recommendation":"Recommendation","common.producing":"Producing","common.idle":"Idle","common.month_label":"Month","common.year_label":"Year","common.total":"Total","common.sort":"Sort","common.error":"Error","gas.history_unavailable":"Gas history temporarily unavailable","gas.history_unavailable_desc":"The meter is available, but Home Assistant could not load the Statistics Graph card.","gas.consumption":"Gas consumption","gas.not_connected":"Gas meter not connected","gas.total_meter":"total meter reading","gas.measured_desc":"Measured gas use, meter state and history.","automation.pause_mode":"Pause mode","automation.pause_unavailable":"Pause mode cannot be changed for this asset","strategy.min_start_time":"Min start time","strategy.surplus_start":"Surplus start","strategy.min_stop_time":"Min stop time","strategy.surplus_stop":"Surplus stop","strategy.max_start_attempts":"Max start attempts","strategy.retry_delay":"Retry delay","strategy.settings":"Strategy settings","strategy.settings_desc":"Editable planning properties for flexible-load execution.","planning.ready_by":"Ready by","planning.priority":"Priority","planning.goal":"Goal","planning.target":"Target","planning.deadline":"Deadline","planning.route_grid":"Route / grid","planning.mode_confidence":"Mode / confidence","consumer.not_managed":"Not managed by Home Intelligence","solar.panel":"SOLAR PANEL","solar.panel_available":"Panel available","solar.panel_identity":"Panel identity","solar.optimizer_panel":"OPTIMIZER / PANEL","solar.measurements":"Measurements","solar.measurements_unavailable":"Energy measurements are not available right now; the optimizer remains part of the solar system.","solar.zone_string":"SOLAR ZONE / STRING","solar.production":"SOLAR PRODUCTION","solar.production_title":"Solar Production","solar.production_unavailable":"Production unavailable","solar.home":"Home","solar.grid":"Grid","solar.consumption_now":"Consumption now","asset.other":"Other assets","asset.excluded_planning":"These assets are excluded from operational planning.","asset.not_managed":"These assets are not managed by Home Intelligence.","flow.main_switchboard":"Main Switchboard","flow.physical_bus":"Physical bus","flow.home_bus":"Home Bus","flow.site_consumption":"Site Consumption","metering.reset_baseline":"Reset baseline","metering.reset_unavailable":"Reset is not available right now","metering.no_flexible":"No Flexible Load measurements available","metering.no_flexible_desc":"Measurements appear when Energy publishes a visible period record.","retro.prerequisites":"REVIEW PREREQUISITES","retro.collecting":"Collecting evidence","retro.collecting_desc":"This section appears when Energy Intelligence publishes enough measurable evidence.","value.period_result_desc":"Accumulated measured value for the Metering-selected period. No future value is predicted.","value.net_financial_result":"Net financial result","planning.no_effective":"No effective values available.","planning.no_long_term":"No long-term strategy available","planning.no_long_term_desc":"Long-term strategy details are not available yet."
  }),
  nl:Object.freeze({
    "planning.day_after_tomorrow":"Overmorgen",
    "planning.d2_need":"Benodigd bij aanvang overmorgen",
    "planning.d2_planned":"Gepland overmorgen",
    "planning.d2_remaining":"Nog te plannen na overmorgen",

    "history.grid_import":"Historiek netafname",
    "history.grid_export":"Historiek netinjectie",
    "history.home":"Historiek huishoudelijk verbruik",
    "history.flexible":"Historiek flexibel verbruik",
    "history.measured_power":"Gemeten vermogen (kW) uit Home Assistant-historiek; geen berekend energietotaal.",
    "history.unavailable":"Meetgeschiedenis niet beschikbaar",
    "history.unavailable_desc":"Er is geen unieke, beschikbare canonieke Home Assistant-sensor voor deze historiek. Waarden worden niet geschat.",

    "flow.native_title":"Gemeten energiestromen",
    "flow.native_desc":"Gemeten vermogen uit de bron; ontbrekende bronnen en richtingen worden niet geschat.",
    "flow.native_solar":"Zonneproductie",
    "flow.native_grid_import":"Netafname",
    "flow.native_grid_export":"Netinjectie",
    "flow.native_site":"Totaal verbruik",
    "flow.native_home":"Huishoudelijk verbruik",
    "flow.native_flexible":"Flexibele verbruikers",
    "flow.native_battery":"Batterijvermogen",

    "nav.energy":"Energie","nav.overview":"Overzicht","nav.flow":"Stromen","nav.solar":"Zonne-energie","nav.battery":"Thuisbatterij","nav.consumption":"Verbruik","nav.gas":"Gas",
    "nav.intelligence":"Intelligentie","nav.plan":"Planning","nav.operational_plan":"Nu","nav.tactical_plan":"Vandaag & morgen","nav.strategic_plan":"Lange termijn","nav.settings":"Instellingen","nav.insights":"Inzichten","nav.performance":"Prestaties","nav.value":"Waarde","nav.retrospective":"Terugblik",
    "hero.overview.title":"Energieoverzicht","hero.overview.description":"Zie wat je woning nu produceert, verbruikt, opslaat en uitwisselt.",
    "hero.flow.title":"Energiestromen","hero.flow.description":"Zie waar energie nu vandaan komt en waar ze naartoe gaat.",
    "hero.solar.title":"Zonne-energie","hero.solar.description":"Zie de huidige zonneproductie en welke installatieonderdelen daaraan bijdragen.",
    "hero.battery.title":"Thuisbatterij","hero.battery.description":"Zie de opgeslagen energie, de huidige batterijactiviteit en de reserve voor je woning.",
    "hero.consumption.title":"Verbruik","hero.consumption.description":"Zie waar energie wordt gebruikt en welke flexibele verbruikers gepland kunnen worden.",
    "hero.gas.title":"Gas","hero.gas.description":"Bekijk het gasverbruik doorheen de tijd en of metingen beschikbaar zijn.",
    "hero.plan.title":"Planning","hero.plan.description":"Zie wat nu, vandaag en morgen moet gebeuren en wat nog aandacht nodig heeft.",
    "hero.strategic.title":"Strategisch","hero.strategic.description":"Bekijk het energiebeleid op langere termijn en welke onderbouwing nog ontbreekt.",
    "hero.operational.title":"Operationeel","hero.operational.description":"Bekijk welke flexibele verbruikers nu kunnen reageren, welke wachten en waarom.","nav.forecast":"Voorspelling","forecast.incomplete_title":"Voorspelling onvolledig","forecast.incomplete_desc":"Een deel van aanbod, vraag of netbalans is niet gepubliceerd. De beschikbare waarden vormen geen volledig energiebeeld.","forecast.flexible_scheduled":"Geplande flexibele verbruikers","forecast.flexible_known":"Bekende laadbehoefte","forecast.flexible_unknown":"Flexibele energievraag","forecast.per_asset_missing":"De laadbehoefte per voertuig is voor deze periode niet gepubliceerd. Controleer de planningsstatus in Mobility.","forecast.row_planned":"Gepland","forecast.row_needed":"Nodig, nog niet gepland","forecast.grid_unavailable":"Voor de netbalans zijn zowel de import- als exportvoorspelling nodig.",
    "hero.settings.title":"Instellingen","hero.settings.description":"Pas aan hoe Home Intelligence je energie mag beheren binnen de beschikbare opties.",
    "hero.performance.title":"Prestaties","hero.performance.description":"Bekijk gemeten energie en hoe Home Intelligence heeft gepresteerd.",
    "hero.value.title":"Waarde","hero.value.description":"Zie het financiële resultaat van je energiesysteem voor de gekozen periode.",
    "hero.retrospective.title":"Terugblik","hero.retrospective.description":"Zie wat goed werkte, wat aandacht nodig heeft en waar nog informatie ontbreekt.",
    "common.quick_actions":"Snelle acties","common.not_available":"Niet beschikbaar","common.not_measured":"Niet gemeten","common.unknown":"Onbekend",
    "common.details":"Details","common.diagnostics":"Diagnose","common.configuration":"Configuratie","common.children":"Onderdelen","common.save":"Opslaan","common.cancel":"Annuleren","common.reset":"Herstellen",
    "common.today":"Vandaag","common.tomorrow":"Morgen","common.information_missing":"Deze informatie is nog niet beschikbaar.",
    "reason.intelligence_off":"Energie-intelligentie staat uit","reason.automation_disabled":"Automatisering is uitgeschakeld","reason.disabled":"Uitgeschakeld","reason.not_available":"Niet beschikbaar","reason.not_published":"Deze informatie is nog niet beschikbaar.","reason.no_battery_policy":"Informatie over het batterijbeleid is nog niet beschikbaar","reason.data_incomplete":"Sommige details zijn niet beschikbaar","reason.verification_required":"Controle is nodig","reason.reset_pending":"Herstel wordt uitgevoerd","reason.confirmation_needed":"Bevestiging nodig","reason.waiting":"Wachten","reason.preparing":"Voorbereiden","reason.not_configured":"Instelling nodig","common.appearance":"Weergave","common.choose_appearance":"Weergave kiezen","common.selected":"Geselecteerd","common.save_appearance":"Weergave opslaan","common.automatic":"Automatisch","common.off":"Uit","common.advice":"Advies","common.forced":"Geforceerd","common.high":"Hoog","common.normal":"Normaal","common.low":"Laag","section.production_supply":"Productie & aanvoer","section.production_supply_desc":"Energie die nu voor de woning beschikbaar is.","section.consumption_desc":"Huishoudelijk verbruik, flexibele verbruikers en batterijladen. Netinjectie staat apart.","overview.battery_charge":"Batterij laden","overview.battery_discharge":"Batterij ontladen","overview.battery_charging":"De thuisbatterij wordt geladen","overview.battery_flow_unavailable":"Batterijstroom niet beschikbaar","overview.battery_flow_reason":"Laden of ontladen van de batterij kan niet worden bevestigd.","overview.grid_flow_unavailable":"Netstroom niet beschikbaar","overview.grid_flow_reason":"Netafname of netinjectie kan niet worden bevestigd.","overview.balance_incomplete":"De actuele energiebalans van de woning is niet bevestigd.","overview.home_excludes_storage":"Huishoudelijk verbruik zonder flexibele verbruikers en batterijladen","section.flexible_loads":"Flexibele verbruikers","section.flexible_loads_desc":"Huidige uitvoering, volgende actie, gevraagd vermogen en operationele reden. Hardwareconfiguratie wordt hier niet getoond.","section.other_assets":"Andere assets","section.supply":"Aanvoer","section.supply_desc":"Verwachte bruikbare energie voor de gekozen horizon.","section.demand":"Vraag","section.demand_desc":"Verwacht woningverbruik, flexibele verbruikers en batterijladen.","section.grid_impact":"Netimpact","section.grid_impact_desc":"Verwachte netuitwisseling voor de gekozen horizon.","flow.physical":"Fysieke energiestroom","flow.physical_desc":"Alleen live gemeten energiestromen. Uitgeschakelde en enkel geplande assets zijn uitgesloten.","flow.producers":"Producenten","flow.consumers":"Verbruikers","flow.charging_connections":"Laadverbindingen","flow.charging_connections_desc":"Laadpunten en voertuigtoewijzingen die momenteel zichtbaar zijn voor Energy.","flow.physical_consumers":"Fysieke verbruikers","flow.physical_consumers_desc":"Deelnemende verbruikers en hun huidige laadverbinding; inactieve assets blijven zichtbaar.","gas.history":"Historiek gasverbruik","gas.meter":"Gasmeter","gas.meter_desc":"Huidige meterstatus en gemeten waarden.","gas.connect":"Verbind je gasmeter","gas.connect_desc":"Verbind een gasmeter voordat verbruikshistoriek kan worden getoond.","battery.state":"Status thuisbatterij","battery.state_desc":"Gecombineerde operationele waarheid voor het thuisbatterijsysteem.","battery.contributors":"Onderdelen thuisbatterij","battery.contributors_desc":"Fysieke batterijen die bijdragen aan het totaal.","settings.automation":"Automatisering","settings.automation_desc":"Kies hoeveel Home Intelligence voor jou mag uitvoeren.","settings.adjust":"Wat wil je aanpassen?","settings.adjust_desc":"Instellingen zijn gegroepeerd volgens het deel van je energiesysteem dat je wilt beïnvloeden.","settings.effective":"Effectief gedrag","settings.participants":"Deelnemende assets","metering.period":"Meetperiode","metering.attention":"Aandacht voor metingen","metering.attention_desc":"Los problemen voor de gekozen periode op voordat je op de totalen vertrouwt.","metering.flexible_loads":"Flexibele verbruikers","value.financial_result":"Financieel resultaat","value.pricing_settings":"Prijsinstellingen","value.flexible_pricing":"Prijs van flexibele verbruikers","value.consumer_allocation":"Verdeling over verbruikers","planning.tactical":"Tactische planning","planning.strategic":"Strategische planning","planning.not_available":"Strategie niet beschikbaar","planning.solar_generation":"Zonneproductie","planning.solar_unavailable":"Details over zonneproductie zijn nog niet beschikbaar","planning.no_renderer":"Voor dit navigatiedoel is nog geen aparte weergave beschikbaar.","appearance.description":"Kies de representatieve afbeelding. De keuze wordt door het owning domain opgeslagen en via readback bevestigd.","common.horizon":"Horizon","common.period":"Periode","common.status":"Status","common.default":"Standaard","common.name":"Naam","common.this_hour":"Dit uur","common.week":"Week","common.month":"Maand","common.year":"Jaar","common.highest_value":"Hoogste waarde","common.lowest_value":"Laagste waarde","pricing.export_compensation":"Injectievergoeding","pricing.export_fee":"Injectiekost","pricing.commodity":"Energieprijs","pricing.network":"Netkosten","pricing.taxes_levies":"Belastingen & heffingen","pricing.vat":"BTW","hero.energy_overview":"Energieoverzicht","hero.site_consumption":"Woningverbruik","hero.energy_outlook":"Energievooruitzicht","hero.live_flow":"Live energiestroom","hero.solar_unavailable":"Zonneproductie niet beschikbaar","hero.generating":"Produceert nu","hero.not_generating":"Produceert niet","hero.settings":"Instellingen","hero.operational_planning":"Operationele planning","hero.metering":"Metingen","hero.home_intelligence":"Home Intelligence","hero.energy_retrospective":"Energieterugblik","hero.energy_value":"Energiewaarde","overview.producing_now":"Produceert nu","overview.grid_import":"Netafname","overview.importing":"Afname","overview.flex_contributor":"Bijdrage flexibele verbruiker","automation.mode":"Automatiseringsmodus","automation.quick_action":"Snelle actie","automation.control":"Home Intelligence-bediening","connection.not_connected":"Niet verbonden","connection.connect_hint":"Verbind om planning en laden mogelijk te maken.","connection.disabled_hint":"Deze verbruiker is uitgeschakeld en uitgesloten van planning.","connection.connected":"Verbonden","control.requested_charge_power":"Gevraagd laadvermogen","control.requested_charge_power_desc":"Laadvermogen dat voor deze asset wordt gevraagd.","relationship.part_of":"Onderdeel van","battery.system":"Batterijsysteem","battery.power_now":"Vermogen nu","battery.soc":"Laadniveau","battery.capacity":"Capaciteit","battery.available_energy":"Beschikbare energie","solar.production_now":"Productie nu","automation.authority":"Automatiseringsbevoegdheid","consumer.managed":"Flexibele verbruikers","consumer.managed_desc":"Primaire kaarten tonen huidig vermogen en energiebehoefte. Details bevatten extra gebruikersinformatie; technische evidence blijft in diagnose.","retro.planning_outcomes":"Planningsresultaten","retro.execution_results":"Uitvoeringsresultaten","retro.measured_energy":"Gemeten energie","retro.open_period":"Open periode-evaluatie","retro.weekly":"Wekelijkse evaluatie","intelligence.current_situation":"Huidige situatie","planning.solar":"Zonne-energie","planning.battery_out":"Thuisbatterij uit","planning.grid_in":"Netafname","planning.home":"Woning","planning.battery_in":"Thuisbatterij in","planning.grid_out":"Netinjectie","planning.hourly_desc":"Uurweergave van verwachte productie, verbruik, opslag en netuitwisseling.","common.recommendation":"Aanbeveling","common.producing":"Produceert","common.idle":"Inactief","common.month_label":"Maand","common.year_label":"Jaar","common.total":"Totaal","common.sort":"Sorteren","common.error":"Fout","gas.history_unavailable":"Gashistoriek tijdelijk niet beschikbaar","gas.history_unavailable_desc":"De meter is beschikbaar, maar Home Assistant kon de Statistics Graph-kaart niet laden.","gas.consumption":"Gasverbruik","gas.not_connected":"Gasmeter niet verbonden","gas.total_meter":"totale meterstand","gas.measured_desc":"Gemeten gasverbruik, meterstatus en historiek.","automation.pause_mode":"Pauzemodus","automation.pause_unavailable":"De pauzemodus kan voor deze asset niet worden gewijzigd","strategy.min_start_time":"Minimale starttijd","strategy.surplus_start":"Startoverschot","strategy.min_stop_time":"Minimale stoptijd","strategy.surplus_stop":"Stopoverschot","strategy.max_start_attempts":"Maximale startpogingen","strategy.retry_delay":"Wachttijd voor nieuwe poging","strategy.settings":"Strategie-instellingen","strategy.settings_desc":"Wijzigbare planningsinstellingen voor uitvoering van flexibele verbruikers.","planning.ready_by":"Klaar tegen","planning.priority":"Prioriteit","planning.goal":"Doel","planning.target":"Streefwaarde","planning.deadline":"Deadline","planning.route_grid":"Route / net","planning.mode_confidence":"Modus / betrouwbaarheid","consumer.not_managed":"Niet beheerd door Home Intelligence","solar.panel":"ZONNEPANEEL","solar.panel_available":"Paneel beschikbaar","solar.panel_identity":"Paneelidentiteit","solar.optimizer_panel":"OPTIMIZER / PANEEL","solar.measurements":"Metingen","solar.measurements_unavailable":"Energiemetingen zijn momenteel niet beschikbaar; de optimizer blijft onderdeel van het zonnesysteem.","solar.zone_string":"ZONNEZONE / STRING","solar.production":"ZONNEPRODUCTIE","solar.production_title":"Zonneproductie","solar.production_unavailable":"Productie niet beschikbaar","solar.home":"Woning","solar.grid":"Net","solar.consumption_now":"Verbruik nu","asset.other":"Andere assets","asset.excluded_planning":"Deze assets zijn uitgesloten van operationele planning.","asset.not_managed":"Deze assets worden niet beheerd door Home Intelligence.","flow.main_switchboard":"Hoofdverdeelkast","flow.physical_bus":"Fysieke bus","flow.home_bus":"Woningbus","flow.site_consumption":"Woningverbruik","metering.reset_baseline":"Baseline herstellen","metering.reset_unavailable":"Herstellen is momenteel niet beschikbaar","metering.no_flexible":"Geen metingen voor flexibele verbruikers beschikbaar","metering.no_flexible_desc":"Metingen verschijnen zodra Energy een zichtbare perioderegistratie publiceert.","retro.prerequisites":"VOORWAARDEN VOOR EVALUATIE","retro.collecting":"Bewijs verzamelen","retro.collecting_desc":"Dit onderdeel verschijnt zodra Energy Intelligence voldoende meetbaar bewijs publiceert.","value.period_result_desc":"Opgebouwde gemeten waarde voor de in Metering gekozen periode. Er wordt geen toekomstige waarde voorspeld.","value.net_financial_result":"Netto financieel resultaat","planning.no_effective":"Geen effectieve waarden beschikbaar.","planning.no_long_term":"Geen langetermijnstrategie beschikbaar","planning.no_long_term_desc":"Details over de langetermijnstrategie zijn nog niet beschikbaar."
  }),
  fr:Object.freeze({
    "planning.day_after_tomorrow":"Après-demain",
    "planning.d2_need":"Besoin au début d'après-demain",
    "planning.d2_planned":"Planifié après-demain",
    "planning.d2_remaining":"Reste à planifier après après-demain",

    "history.grid_import":"Historique de l'import réseau",
    "history.grid_export":"Historique de l'injection réseau",
    "history.home":"Historique de consommation domestique",
    "history.flexible":"Historique des charges flexibles",
    "history.measured_power":"Puissance mesurée (kW) dans l'historique Home Assistant ; pas un total énergétique calculé.",
    "history.unavailable":"Historique mesuré indisponible",
    "history.unavailable_desc":"Aucun capteur Home Assistant canonique, unique et disponible pour cet historique. Aucune valeur n'est estimée.",

    "flow.native_title":"Flux d'énergie mesurés",
    "flow.native_desc":"Puissances mesurées à la source ; les données et directions manquantes ne sont pas estimées.",
    "flow.native_solar":"Production solaire",
    "flow.native_grid_import":"Import du réseau",
    "flow.native_grid_export":"Injection réseau",
    "flow.native_site":"Consommation totale",
    "flow.native_home":"Consommation domestique",
    "flow.native_flexible":"Charges flexibles",
    "flow.native_battery":"Puissance batterie",

    "nav.energy":"Énergie","nav.overview":"Vue d’ensemble","nav.flow":"Flux","nav.solar":"Solaire","nav.battery":"Batterie domestique","nav.consumption":"Consommation","nav.gas":"Gaz",
    "nav.intelligence":"Intelligence","nav.plan":"Planification","nav.operational_plan":"Maintenant","nav.tactical_plan":"Aujourd’hui & demain","nav.strategic_plan":"Long terme","nav.settings":"Réglages","nav.insights":"Analyses","nav.performance":"Performance","nav.value":"Valeur","nav.retrospective":"Bilan",
    "hero.overview.title":"Vue d’ensemble de l’énergie","hero.overview.description":"Voyez ce que votre habitation produit, consomme, stocke et échange en ce moment.",
    "hero.flow.title":"Flux d’énergie","hero.flow.description":"Voyez d’où vient l’énergie et où elle va en ce moment.",
    "hero.solar.title":"Solaire","hero.solar.description":"Voyez la production solaire actuelle et les équipements qui y contribuent.",
    "hero.battery.title":"Batterie domestique","hero.battery.description":"Voyez l’énergie stockée, l’activité actuelle de la batterie et la réserve disponible.",
    "hero.consumption.title":"Consommation","hero.consumption.description":"Voyez où l’énergie est utilisée et quelles charges flexibles peuvent être planifiées.",
    "hero.gas.title":"Gaz","hero.gas.description":"Consultez la consommation de gaz et vérifiez si les mesures sont disponibles.",
    "hero.plan.title":"Planification","hero.plan.description":"Voyez ce qui doit se passer maintenant, aujourd’hui et demain, et ce qui demande encore votre attention.",
    "hero.strategic.title":"Stratégique","hero.strategic.description":"Examinez les politiques énergétiques à long terme et les informations encore manquantes.",
    "hero.operational.title":"Opérationnel","hero.operational.description":"Voyez quelles charges flexibles peuvent agir maintenant, lesquelles attendent et pourquoi.","nav.forecast":"Prévisions","forecast.incomplete_title":"Prévisions incomplètes","forecast.incomplete_desc":"Une partie de l'offre, de la demande ou des échanges réseau n'est pas publiée. Les chiffres disponibles ne constituent pas un bilan énergétique complet.","forecast.flexible_scheduled":"Charges flexibles planifiées","forecast.flexible_known":"Besoin de charge connu","forecast.flexible_unknown":"Demande des charges flexibles","forecast.per_asset_missing":"Les besoins de charge par véhicule ne sont pas publiés pour cette période. Vérifiez la disponibilité de planification dans Mobility.","forecast.row_planned":"Planifié","forecast.row_needed":"Nécessaire, non planifié","forecast.grid_unavailable":"Le bilan réseau exige des prévisions d'importation et d'exportation.",
    "hero.settings.title":"Réglages","hero.settings.description":"Ajustez la manière dont Home Intelligence peut gérer votre énergie dans les limites disponibles.",
    "hero.performance.title":"Performance","hero.performance.description":"Consultez l’énergie mesurée et les performances de Home Intelligence.",
    "hero.value.title":"Valeur","hero.value.description":"Voyez le résultat financier de votre système énergétique pour la période sélectionnée.",
    "hero.retrospective.title":"Bilan","hero.retrospective.description":"Voyez ce qui a fonctionné, ce qui demande votre attention et où des informations manquent encore.",
    "common.quick_actions":"Actions rapides","common.not_available":"Non disponible","common.not_measured":"Non mesuré","common.unknown":"Inconnu",
    "common.details":"Détails","common.diagnostics":"Diagnostic","common.configuration":"Configuration","common.children":"Éléments","common.save":"Enregistrer","common.cancel":"Annuler","common.reset":"Réinitialiser",
    "common.today":"Aujourd’hui","common.tomorrow":"Demain","common.information_missing":"Cette information n’est pas encore disponible.",
    "reason.intelligence_off":"L’intelligence énergétique est désactivée","reason.automation_disabled":"L’automatisation est désactivée","reason.disabled":"Désactivé","reason.not_available":"Non disponible","reason.not_published":"Cette information n’est pas encore disponible.","reason.no_battery_policy":"Les informations sur la politique de batterie ne sont pas encore disponibles","reason.data_incomplete":"Certains détails ne sont pas disponibles","reason.verification_required":"Une vérification est nécessaire","reason.reset_pending":"Réinitialisation en cours","reason.confirmation_needed":"Confirmation nécessaire","reason.waiting":"En attente","reason.preparing":"Préparation","reason.not_configured":"Configuration nécessaire","common.appearance":"Apparence","common.choose_appearance":"Choisir l’apparence","common.selected":"Sélectionné","common.save_appearance":"Enregistrer l’apparence","common.automatic":"Automatique","common.off":"Désactivé","common.advice":"Conseil","common.forced":"Forcé","common.high":"Haute","common.normal":"Normale","common.low":"Basse","section.production_supply":"Production & alimentation","section.production_supply_desc":"Énergie disponible pour l’habitation maintenant.","section.consumption_desc":"Usages domestiques, charges flexibles et recharge de batterie. L’export réseau est séparé.","overview.battery_charge":"Charge de batterie","overview.battery_discharge":"Décharge de batterie","overview.battery_charging":"Recharge du stockage domestique","overview.battery_flow_unavailable":"Flux de batterie indisponible","overview.battery_flow_reason":"Impossible de confirmer la charge ou la décharge de la batterie.","overview.grid_flow_unavailable":"Flux réseau indisponible","overview.grid_flow_reason":"Impossible de confirmer l’import ou l’export réseau.","overview.balance_incomplete":"Le bilan énergétique actuel du site n’est pas vérifié.","overview.home_excludes_storage":"Consommation domestique hors charges flexibles et recharge de batterie","section.flexible_loads":"Charges flexibles","section.flexible_loads_desc":"Exécution actuelle, prochaine action, puissance demandée et raison opérationnelle. La configuration matérielle n’est pas affichée ici.","section.other_assets":"Autres équipements","section.supply":"Alimentation","section.supply_desc":"Énergie utilisable prévue pour l’horizon sélectionné.","section.demand":"Demande","section.demand_desc":"Consommation domestique, charges flexibles et charge du stockage prévues.","section.grid_impact":"Impact réseau","section.grid_impact_desc":"Échange réseau prévu pour l’horizon sélectionné.","flow.physical":"Flux d’énergie physique","flow.physical_desc":"Uniquement les flux d’énergie mesurés en direct. Les équipements désactivés ou uniquement planifiés sont exclus.","flow.producers":"Producteurs","flow.consumers":"Consommateurs","flow.charging_connections":"Connexions de charge","flow.charging_connections_desc":"Bornes et attributions de véhicules actuellement visibles dans Energy.","flow.physical_consumers":"Consommateurs physiques","flow.physical_consumers_desc":"Charges participantes et leur connexion de charge actuelle; les équipements inactifs restent visibles.","gas.history":"Historique de consommation de gaz","gas.meter":"Compteur de gaz","gas.meter_desc":"État actuel du compteur et valeurs mesurées.","gas.connect":"Connectez votre compteur de gaz","gas.connect_desc":"Connectez un compteur avant d’afficher l’historique de consommation.","battery.state":"État de la batterie domestique","battery.state_desc":"État opérationnel combiné du système de batterie domestique.","battery.contributors":"Composants de la batterie domestique","battery.contributors_desc":"Batteries physiques contribuant à l’ensemble.","settings.automation":"Automatisation","settings.automation_desc":"Choisissez dans quelle mesure Home Intelligence peut agir pour vous.","settings.adjust":"Que voulez-vous ajuster ?","settings.adjust_desc":"Les réglages sont regroupés selon la partie de votre système énergétique à influencer.","settings.effective":"Comportement effectif","settings.participants":"Équipements participants","metering.period":"Période de mesure","metering.attention":"Attention aux mesures","metering.attention_desc":"Résolvez la période sélectionnée avant de vous fier à ses totaux.","metering.flexible_loads":"Charges flexibles","value.financial_result":"Résultat financier","value.pricing_settings":"Réglages des prix","value.flexible_pricing":"Tarification des charges flexibles","value.consumer_allocation":"Répartition par consommateur","planning.tactical":"Planification tactique","planning.strategic":"Planification stratégique","planning.not_available":"Stratégie indisponible","planning.solar_generation":"Production solaire","planning.solar_unavailable":"Les détails de production solaire ne sont pas encore disponibles","planning.no_renderer":"Cette destination de navigation n’a pas encore de vue dédiée.","appearance.description":"Choisissez l’image représentative. La sélection est enregistrée par le domaine propriétaire et confirmée par lecture.","common.horizon":"Horizon","common.period":"Période","common.status":"État","common.default":"Par défaut","common.name":"Nom","common.this_hour":"Cette heure","common.week":"Semaine","common.month":"Mois","common.year":"Année","common.highest_value":"Valeur la plus élevée","common.lowest_value":"Valeur la plus faible","pricing.export_compensation":"Rémunération d’injection","pricing.export_fee":"Frais d’injection","pricing.commodity":"Énergie","pricing.network":"Réseau","pricing.taxes_levies":"Taxes & prélèvements","pricing.vat":"TVA","hero.energy_overview":"Vue d’ensemble énergétique","hero.site_consumption":"Consommation du site","hero.energy_outlook":"Prévision énergétique","hero.live_flow":"Flux d’énergie en direct","hero.solar_unavailable":"Production solaire indisponible","hero.generating":"Production en cours","hero.not_generating":"Pas de production","hero.settings":"Réglages","hero.operational_planning":"Planification opérationnelle","hero.metering":"Mesures","hero.home_intelligence":"Home Intelligence","hero.energy_retrospective":"Bilan énergétique","hero.energy_value":"Valeur énergétique","overview.producing_now":"Production en cours","overview.grid_import":"Import réseau","overview.importing":"Importation","overview.flex_contributor":"Contribution d’une charge flexible","automation.mode":"Mode d’automatisation","automation.quick_action":"Action rapide","automation.control":"Contrôle Home Intelligence","connection.not_connected":"Non connecté","connection.connect_hint":"Connectez pour permettre la planification et la charge.","connection.disabled_hint":"Cette charge est désactivée et exclue de la planification.","connection.connected":"Connecté","control.requested_charge_power":"Puissance de charge demandée","control.requested_charge_power_desc":"Puissance de charge demandée à cet équipement.","relationship.part_of":"Fait partie de","battery.system":"Système de batterie","battery.power_now":"Puissance actuelle","battery.soc":"État de charge","battery.capacity":"Capacité","battery.available_energy":"Énergie disponible","solar.production_now":"Production actuelle","automation.authority":"Autorité d’automatisation","consumer.managed":"Charges flexibles","consumer.managed_desc":"Les cartes principales montrent la puissance actuelle et le besoin énergétique. Les détails contiennent les informations utilisateur supplémentaires; les preuves techniques restent dans le diagnostic.","retro.planning_outcomes":"Résultats de planification","retro.execution_results":"Résultats d’exécution","retro.measured_energy":"Énergie mesurée","retro.open_period":"Bilan de période ouverte","retro.weekly":"Bilan hebdomadaire","intelligence.current_situation":"Situation actuelle","planning.solar":"Solaire","planning.battery_out":"Batterie domestique sortante","planning.grid_in":"Import réseau","planning.home":"Habitation","planning.battery_in":"Batterie domestique entrante","planning.grid_out":"Injection réseau","planning.hourly_desc":"Vue horaire de la production, consommation, stockage et échange réseau prévus.","common.recommendation":"Recommandation","common.producing":"Production","common.idle":"Inactif","common.month_label":"Mois","common.year_label":"Année","common.total":"Total","common.sort":"Trier","common.error":"Erreur","gas.history_unavailable":"Historique du gaz temporairement indisponible","gas.history_unavailable_desc":"Le compteur est disponible, mais Home Assistant n’a pas pu charger la carte Statistics Graph.","gas.consumption":"Consommation de gaz","gas.not_connected":"Compteur de gaz non connecté","gas.total_meter":"relevé total du compteur","gas.measured_desc":"Consommation de gaz mesurée, état du compteur et historique.","automation.pause_mode":"Mode pause","automation.pause_unavailable":"Le mode pause ne peut pas être modifié pour cet équipement","strategy.min_start_time":"Temps de démarrage minimum","strategy.surplus_start":"Surplus de démarrage","strategy.min_stop_time":"Temps d’arrêt minimum","strategy.surplus_stop":"Surplus d’arrêt","strategy.max_start_attempts":"Tentatives de démarrage max.","strategy.retry_delay":"Délai avant nouvelle tentative","strategy.settings":"Réglages de stratégie","strategy.settings_desc":"Propriétés de planification modifiables pour l’exécution des charges flexibles.","planning.ready_by":"Prêt pour","planning.priority":"Priorité","planning.goal":"Objectif","planning.target":"Cible","planning.deadline":"Échéance","planning.route_grid":"Route / réseau","planning.mode_confidence":"Mode / fiabilité","consumer.not_managed":"Non géré par Home Intelligence","solar.panel":"PANNEAU SOLAIRE","solar.panel_available":"Panneau disponible","solar.panel_identity":"Identité du panneau","solar.optimizer_panel":"OPTIMISEUR / PANNEAU","solar.measurements":"Mesures","solar.measurements_unavailable":"Les mesures d’énergie ne sont pas disponibles pour le moment; l’optimiseur reste intégré au système solaire.","solar.zone_string":"ZONE SOLAIRE / STRING","solar.production":"PRODUCTION SOLAIRE","solar.production_title":"Production solaire","solar.production_unavailable":"Production indisponible","solar.home":"Habitation","solar.grid":"Réseau","solar.consumption_now":"Consommation actuelle","asset.other":"Autres équipements","asset.excluded_planning":"Ces équipements sont exclus de la planification opérationnelle.","asset.not_managed":"Ces équipements ne sont pas gérés par Home Intelligence.","flow.main_switchboard":"Tableau principal","flow.physical_bus":"Bus physique","flow.home_bus":"Bus habitation","flow.site_consumption":"Consommation du site","metering.reset_baseline":"Réinitialiser la référence","metering.reset_unavailable":"La réinitialisation n’est pas disponible pour le moment","metering.no_flexible":"Aucune mesure de charge flexible disponible","metering.no_flexible_desc":"Les mesures apparaissent lorsque Energy publie un enregistrement de période visible.","retro.prerequisites":"PRÉREQUIS DU BILAN","retro.collecting":"Collecte des preuves","retro.collecting_desc":"Cette section apparaît lorsque Energy Intelligence publie suffisamment de preuves mesurables.","value.period_result_desc":"Valeur mesurée cumulée pour la période sélectionnée dans Metering. Aucune valeur future n’est prédite.","value.net_financial_result":"Résultat financier net","planning.no_effective":"Aucune valeur effective disponible.","planning.no_long_term":"Aucune stratégie à long terme disponible","planning.no_long_term_desc":"Les détails de la stratégie à long terme ne sont pas encore disponibles."
  })
});
let RHI_ENERGY_LOCALE="en";
function rhiEnergyLocale(hass=null){
  const raw=hass?.locale?.language || hass?.language || RHI_ENERGY_LOCALE || globalThis?.document?.documentElement?.lang || "en";
  return String(raw||"en").replace(/_/g,"-");
}
function rhiEnergySetLocaleFromHass(hass=null){RHI_ENERGY_LOCALE=rhiEnergyLocale(hass);return RHI_ENERGY_LOCALE;}
function rhiEnergyT(hass,key,params={},fallback=""){return rhiUxTranslate(RHI_ENERGY_TRANSLATIONS,key,{locale:rhiEnergyLocale(hass),params,fallback});}
function rhiEnergyFormatNumber(hass,value,options={}){return rhiUxFormatNumber(value,{locale:rhiEnergyLocale(hass),...options});}
function rhiEnergyFormatCurrency(hass,value,currency="EUR",options={}){return rhiUxFormatCurrency(value,currency,{locale:rhiEnergyLocale(hass),...options});}
function rhiEnergyFormatPercent(hass,value,options={}){return rhiUxFormatPercent(value,{locale:rhiEnergyLocale(hass),...options});}

// ---- src/app/presentation.js ----
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

// ---- src/ui/components/page-header.js ----
// Energy domain adapter onto shared RHI UX Core presentation primitives.
// Page-level header owns Hero, Status and executable Quick Actions only.
// Body-scoped view/filter controls are rendered immediately above the content they govern.
function rhiEnergyPageHeader({
  sectionLabel = "",
  itemLabel = "",
  title = "",
  description = "",
  hero = "",
  metrics = [],
  commandActions = "",
  tone = ""
} = {}) {
  const eyebrow = [sectionLabel, itemLabel].filter(Boolean).join(" / ");
  const heroMarkup = rhiUxPageHero({ eyebrow, title, description, image:hero, imageAlt:"" });
  const statusMarkup = rhiUxStatusGrid((metrics || []).map(([icon,label,value,detail]) => ({
    icon:icon || "•", label:label || "", value:value ?? "—", detail:detail || ""
  })));
  const actionsMarkup = commandActions
    ? `<section class="rhiUxQuickActionBar" aria-label="${rhiUxEscape(rhiEnergyT(null,'common.quick_actions',{},'Quick actions'))}"><small>${rhiUxEscape(rhiEnergyT(null,'common.quick_actions',{},'Quick actions'))}</small><div class="rhiUxQuickActions">${commandActions}</div></section>`
    : "";
  return `<section class="rhiEnergyPageHeader rhiUxPageStack ${rhiUxEscape(tone)}">${heroMarkup}${statusMarkup}${actionsMarkup}</section>`;
}

// ---- src/ui/components/energy-visual-picker.js ----
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

  class HomeBrainEnergyCard extends HTMLElement {
    static getStubConfig() { return {type: 'custom:homebrain-energy-card'}; }
    constructor() {
      super();
      this.attachShadow({ mode: 'open' });
      const interaction = this.restoreInteractionContext();
      const restoredView = interaction.view || this.restoreView();
      const navigation = this.resolveNavigation(interaction.navSection, interaction.navItem, restoredView);
      this.navSection = navigation.section;
      this.navItem = navigation.item;
      this.view = navigation.view;
      this.navSelectionBySection = interaction.navSelectionBySection && typeof interaction.navSelectionBySection === 'object'
        ? interaction.navSelectionBySection
        : { [this.navSection]: this.navItem };
      this.navSelectionBySection[this.navSection] = this.navItem;
      this.loadSort = interaction.loadSort || 'priority';
      this.detailOpen = {};
      this.selectedStrategyProfileId = interaction.selectedStrategyProfileId || '';
      this.strategyEditProfileId = '';
      this.selectedOutlookHorizonId = interaction.selectedOutlookHorizonId || 'D0';
      this.selectedPlanningHorizonId = interaction.selectedPlanningHorizonId || 'D0';
      this.selectedMeteringHorizonId = interaction.selectedMeteringHorizonId || 'D0';
      // Metering selection is a persisted Energy setting, never browser-owned intent.
      this.selectedMeteringPeriodId = 'today';
      this.selectedGasHorizonId = interaction.selectedGasHorizonId || 'month';
      this._meteringPeriodHydrated = false;
      this.meteringSort = interaction.meteringSort || 'default';
      this.consumerSort = interaction.consumerSort || 'power';
      this.consumerFilter = interaction.consumerFilter || 'all';
      this.writeFeedback = {};
      this.pendingAppearanceByAsset = {};
      this.remediationFeedback = {};
      this.editSession = null;
      this.pendingRuntimeRender = false;
      this.editDrafts = {};
      this.disclosureOpen = interaction.disclosureOpen && typeof interaction.disclosureOpen === 'object' ? interaction.disclosureOpen : {};
      this.navScrollLeft = Number(interaction.navScrollLeft) || 0;
      this.planningScrollLeft = Number(interaction.planningScrollLeft) || 0;
      this.planningScrollTop = Number(interaction.planningScrollTop) || 0;
      this._renderTimer = null;
      this._canonicalIndex = null;
      this._deferredCanonicalSurfaces = new Set();
      this._lastRuntimeSignature = '';
      this._lastMarkup = '';
      this._forceRender = true;
      this.energyVisualPickerAssetId = '';
      this.energyVisualPickerDraftRef = '';
      this.energyVisualPickerBrand = 'all';
    }
    restoreView() {
      try {
        const saved = window.sessionStorage.getItem('homebrain.energy.active_view');
        return ['overview','outlook','flow','solar','battery','consumers','strategies','metering','intelligence','value','planning','retrospective'].includes(saved) ? saved : 'overview';
      } catch (_) { return 'overview'; }
    }
    persistView() {
      try { window.sessionStorage.setItem('homebrain.energy.active_view', this.view); } catch (_) {}
      this.persistInteractionContext();
    }
    restoreInteractionContext() {
      try {
        const raw = window.sessionStorage.getItem('homebrain.energy.interaction_context.v1');
        const parsed = raw ? JSON.parse(raw) : {};
        return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
      } catch (_) { return {}; }
    }
    persistInteractionContext() {
      try {
        const context = {
          view: this.view,
          navSection: this.navSection,
          navItem: this.navItem,
          navSelectionBySection: this.navSelectionBySection,
          loadSort: this.loadSort,
          selectedStrategyProfileId: this.selectedStrategyProfileId,
          selectedOutlookHorizonId: this.selectedOutlookHorizonId,
          selectedPlanningHorizonId: this.selectedPlanningHorizonId,
          selectedMeteringHorizonId: this.selectedMeteringHorizonId,
          selectedGasHorizonId: this.selectedGasHorizonId,
          meteringSort: this.meteringSort,
          consumerSort: this.consumerSort,
          consumerFilter: this.consumerFilter,
          disclosureOpen: this.disclosureOpen,
          navScrollLeft: this.navScrollLeft,
          planningScrollLeft: this.planningScrollLeft,
          planningScrollTop: this.planningScrollTop
        };
        window.sessionStorage.setItem('homebrain.energy.interaction_context.v1', JSON.stringify(context));
      } catch (_) {}
    }
    setConfig(config) { this.config = config || {}; }
    set hass(hass) {
      const previous = this._hass;
      this._hass = hass;
      rhiEnergySetLocaleFromHass(hass);

      let canonicalChanged = null;
      if (!this._canonicalIndex) this._canonicalIndex = createEnergyCanonicalPropertyIndex(hass);
      else canonicalChanged = this._canonicalIndex.refresh(hass);

      // Direct canonical property revisions own normal telemetry invalidation.
      // Aggregate capability contracts must not dirty canonical property surfaces.
      if (previous && this.canonicalRuntimeActive() && canonicalChanged) {
        const relevant = new Set(this.relevantEntityIds());
        const affected = this._canonicalIndex.affectedComponents(canonicalChanged)
          .filter(item => relevant.has(item.entity_id));
        const localeChanged = rhiEnergyLocale(previous) !== rhiEnergyLocale(hass);
        if (!affected.length && !localeChanged && !this._forceRender) return;

        if (!localeChanged && !this._forceRender && affected.length) {
          const visible = affected.filter(item => this.isCanonicalSurfaceVisible(item.surface));
          if (!visible.length) {
            affected.forEach(item => this._deferredCanonicalSurfaces.add(item.surface));
            return;
          }
        }
      }

      this.reconcileWriteFeedback();
      this.reconcilePendingAppearances();
      this.syncMeteringPeriodFromRuntime();
      if (this.editSession) { this.pendingRuntimeRender = true; return; }
      this._preserveViewportOnRender = true;
      this.scheduleRender();
    }
    connectedCallback() {
      this.scheduleRender(true);
      if (this._powerFlowWatchArmed) return;
      this._powerFlowWatchArmed = true;
      if (typeof customElements !== 'undefined' && !customElements.get('power-flow-card-plus')) {
        customElements.whenDefined('power-flow-card-plus').then(() => {
          if (this.isConnected) { this._forceRender = true; this.scheduleRender(true); }
        });
      }
      this._powerFlowProbeTimer = setTimeout(() => {
        this._powerFlowProbeSettled = true;
        if (this.isConnected && this.view === 'flow') { this._forceRender = true; this.scheduleRender(true); }
      }, 1500);
    }
    disconnectedCallback() {
      if (this._renderTimer) clearTimeout(this._renderTimer);
      if (this._powerFlowProbeTimer) clearTimeout(this._powerFlowProbeTimer);
      this._renderTimer = null;
      this._powerFlowProbeTimer = null;
    }
    scheduleRender(immediate = false) {
      if (!this._hass) return;
      if (this._renderTimer) clearTimeout(this._renderTimer);
      this._renderTimer = setTimeout(() => {
        this._renderTimer = null;
        this.render();
      }, immediate ? 0 : 350);
    }
    relevantEntityIds() {
      return this.runtime().subscriptionEntityIds(this.activeCanonicalSurfaces());
    }
    runtimeSignature() {
      const rt = this.runtime();
      const entities = rt.entitySignature(this.relevantEntityIds());
      return `${this.navSection}|${this.navItem}|${this.view}|${this.selectedMeteringPeriodId}|${this.selectedOutlookHorizonId}|${this.selectedPlanningHorizonId}|${this.selectedMeteringHorizonId}|${this.selectedStrategyProfileId}|${this.loadSort}|${this.meteringSort}|${this.consumerSort}|${this.consumerFilter}|${entities}`;
    }

    syncMeteringPeriodFromRuntime() {
      const feedback = this.writeFeedback['metering.selected_period'];
      if (feedback && ['pending','verifying'].includes(String(feedback.state || '').toLowerCase())) return;
      const row = this.runtime().row('metering.selected_period');
      if (!row || row.missing) return;
      const value = String(rowValue(row, '') || '').toLowerCase();
      if (!['hour','today','day','week','month','year'].includes(value)) return;
      // Canonical backend readback wins on every accepted revision, including
      // external options/other-browser changes and rejection of a local write.
      this.selectedMeteringPeriodId = value === 'day' ? 'today' : value;
      this._meteringPeriodHydrated = true;
    }
    selectMeteringPeriod(value, source) {
      const normalized = String(value || 'today').toLowerCase();
      const period = normalized === 'day' ? 'today' : normalized;
      if (!['hour','today','week','month','year'].includes(period)) return;
      const runtime = this.runtime();
      const row = runtime.editableProperty('metering.selected_period') || runtime.row('metering.selected_period');
      if (!this.isWritableRow(row)) {
        this.writeFeedback['metering.selected_period'] = {
          state: 'rejected', reason: 'Canonical metering period writer unavailable',
          updated: Date.now()
        };
        this.render();
        return;
      }
      // Keep showing the last confirmed period until the exact new producer
      // operation and native property readback agree. No optimistic browser save.
      this.requestPropertyWrite('metering.selected_period', period, { source });
    }
    runtime() { return new EnergyRuntime(this._hass || {}, this._canonicalIndex); }
    activeCanonicalSurfaces() {
      if (['overview','flow'].includes(this.view)) return ['key_properties'];
      if (['solar','battery','consumers','gas'].includes(this.view)) return ['key_properties','details','configuration'];
      if (['strategies','intelligence'].includes(this.view)) return ['configuration'];
      if (['metering','value','retrospective'].includes(this.view)) return ['key_properties','details'];
      return [];
    }
    canonicalAuthoritySurfaces() {
      if (['strategies','intelligence'].includes(this.view)) return ['configuration'];
      if (['overview','flow','solar','battery','consumers','gas','metering','value','retrospective'].includes(this.view)) return ['key_properties'];
      return [];
    }
    canonicalRuntimeActive() {
      return !!this._canonicalIndex?.hasProductTruthForSurfaces?.(this.canonicalAuthoritySurfaces());
    }
    isCanonicalSurfaceVisible(surface = '') {
      const value = String(surface || '');
      if (value === 'key_properties') return true;
      if (value === 'details') return !!this.shadowRoot?.querySelector('.energyAssetDetails[open]');
      if (value === 'configuration') return !!this.editSession || !!this.shadowRoot?.querySelector('.energyAssetConfiguration[open]');
      if (value === 'diagnostics') return this.config?.show_diagnostics === true && !!this.shadowRoot?.querySelector('.energyAssetDiagnostics[open]');
      if (value === 'history' || value === 'metering') return ['metering','value','retrospective'].includes(this.view);
      if (value === 'planning') return ['planning','operational-planning','strategic-planning'].includes(this.view);
      return true;
    }
    navigationModel() {
      const presence=this.runtime().experiencePresence();
      const has=(key,fallback=true)=>Object.prototype.hasOwnProperty.call(presence,key)
        ? presence[key] === true
        : fallback;
      const showConsumers=has('flexible_loads', false);
      const showValue=has('pricing', false);
      return hbEnergyNavigation(this._hass).map(section=>({
        ...section,
        items:section.items.filter(item=>{
          if(item.id === 'battery') return has('battery', false);
          if(item.id === 'gas') return has('gas', false);
          if(item.id === 'consumers') return showConsumers;
          if(item.id === 'value') return showValue;
          return true;
        })
      })).filter(section=>section.items.length > 0);
    }
    resolveNavigation(sectionId = '', itemId = '', legacyView = '') {
      const sections = this.navigationModel();
      const bySection = sections.find(section => section.id === String(sectionId || ''));
      const byItem = bySection?.items.find(item => item.id === String(itemId || ''));
      if (bySection && byItem) return { section:bySection.id, item:byItem.id, view:byItem.view };
      const legacy = {
        overview:['energy','overview'], flow:['energy','flow'], battery:['energy','battery'], consumers:['energy','consumers'], gas:['energy','gas'],
        strategies:['intelligence','settings'], intelligence:['intelligence','settings'], solar:['energy','solar'], 'operational-planning':['intelligence','operational'],
        planning:['intelligence','plan'], outlook:['intelligence','plan'],
        metering:['insights','metering'], value:['insights','value'], retrospective:['insights','retrospective'],
        'solar-generation':['energy','solar'], 'strategic-planning':['intelligence','strategic']
      };
      const [fallbackSection,fallbackItem] = legacy[String(legacyView || '')] || ['energy','overview'];
      const section = sections.find(row => row.id === fallbackSection) || sections[0];
      const item = section.items.find(row => row.id === fallbackItem) || section.items[0];
      return { section:section.id, item:item.id, view:item.view };
    }
    activeNavigation() {
      return this.resolveNavigation(this.navSection, this.navItem, this.view);
    }
    activeNavigationItem() {
      const active = this.activeNavigation();
      return this.navigationModel().find(section => section.id === active.section)?.items.find(item => item.id === active.item)
        || this.navigationModel()[0].items[0];
    }
    selectNavigation(sectionId, itemId = '') {
      const sections = this.navigationModel();
      const section = sections.find(row => row.id === sectionId) || sections[0];
      const remembered = this.navSelectionBySection?.[section.id];
      const item = section.items.find(row => row.id === itemId)
        || section.items.find(row => row.id === remembered)
        || section.items[0];
      this.navSection = section.id;
      this.navItem = item.id;
      this.view = item.view;
      this.navSelectionBySection = { ...(this.navSelectionBySection || {}), [section.id]:item.id };
      this.persistView();
      this._forceRender = true;
      this.render();
    }
    navigateToView(view) {
      const target = this.resolveNavigation('', '', view);
      const requested = String(view || target.view || '');
      const planningViews = new Set(['operational-planning','planning','outlook','strategic-planning']);
      this.navSection = target.section;
      this.navItem = target.item;
      this.view = planningViews.has(requested) ? requested : target.view;
      this.navSelectionBySection = { ...(this.navSelectionBySection || {}), [target.section]:target.item };
      this.persistView();
      this._forceRender = true;
      this.render();
    }
    title() { return this.activeNavigationItem().title || rhiEnergyT(this._hass,'nav.energy',{},'Energy'); }
    subtitle() { return this.activeNavigationItem().description || ''; }
    nav() {
      const sections = this.navigationModel();
      const active = this.activeNavigation();
      const modules = sections.map(section => ({
        id:section.id,
        label:section.label,
        items:section.items.map(item => ({ id:item.id, label:item.label }))
      }));
      return `<div class="rhiEnergyNav rhiEnergyNav-${escapeHtml(active.section)}">${rhiUxDomainShell({
        product:'Home Intelligence',
        domain:rhiEnergyT(this._hass,'nav.energy',{},'Energy').toUpperCase(),
        modules,
        activeModule:active.section,
        activeItem:active.item
      })}</div>`;
    }
    onClick(event) {
      const coreModule = event.target.closest('[data-rhi-module]');
      if (coreModule) {
        this.selectNavigation(coreModule.dataset.rhiModule || 'energy', '');
        return;
      }
      const coreItem = event.target.closest('[data-rhi-item]');
      if (coreItem) {
        this.selectNavigation(this.navSection, coreItem.dataset.rhiItem || '');
        return;
      }
      const closeVisualEditor = () => {
        this.energyVisualPickerAssetId = '';
        this.energyVisualPickerDraftRef = '';
        this.energyVisualPickerBrand = 'all';
      };
      const visualBackdrop = event.target.closest('[data-energy-visual-backdrop]');
      if (visualBackdrop && event.target === visualBackdrop) {
        closeVisualEditor();
        this._forceRender = true;
        this.render();
        return;
      }
      const visualCancel = event.target.closest('[data-energy-visual-cancel]');
      if (visualCancel) {
        closeVisualEditor();
        this._forceRender = true;
        this.render();
        return;
      }
      const visualReset = event.target.closest('[data-energy-visual-reset]');
      if (visualReset) {
        const assetId = visualReset.dataset.energyVisualReset || this.energyVisualPickerAssetId || '';
        if (assetId) {
          this.pendingAppearanceByAsset[assetId] = '';
          this.requestPropertyWrite(`appearance:${assetId}:visual_ref`, '', { source:'energy_visual_picker_reset', asset_id:assetId });
        }
        closeVisualEditor();
        this._forceRender = true;
        this.render();
        return;
      }
      const visualBrand = event.target.closest('[data-energy-visual-brand]');
      if (visualBrand) {
        this.energyVisualPickerBrand = visualBrand.dataset.energyVisualBrand || 'all';
        this._forceRender = true;
        this.render();
        return;
      }
      const visualSelect = event.target.closest('[data-energy-visual-select]');
      if (visualSelect) {
        this.energyVisualPickerDraftRef = visualSelect.dataset.energyVisualSelect || '';
        this._forceRender = true;
        this.render();
        return;
      }
      const visualSave = event.target.closest('[data-energy-visual-save]');
      if (visualSave && !visualSave.disabled) {
        const assetId = visualSave.dataset.energyVisualSave || this.energyVisualPickerAssetId || '';
        const visualRef = String(this.energyVisualPickerDraftRef || '').trim();
        if (assetId && visualRef) {
          this.pendingAppearanceByAsset[assetId] = visualRef;
          this.requestPropertyWrite(`appearance:${assetId}:visual_ref`, visualRef, { source:'energy_visual_picker_save', asset_id:assetId });
        }
        closeVisualEditor();
        this._forceRender = true;
        this.render();
        return;
      }
      const visualOpen = event.target.closest('[data-energy-visual-open]');
      if (visualOpen) {
        const assetId = visualOpen.dataset.energyVisualOpen || '';
        const rt = this.runtime();
        const asset = typeof rt.asset === 'function' ? rt.asset(assetId) : null;
        this.energyVisualPickerAssetId = assetId;
        this.energyVisualPickerDraftRef = String(
          firstDefined(
            asset?.appearance?.configured_visual_ref,
            asset?.appearance?.effective_visual_ref,
            asset?.visual_ref,
            ''
          ) || ''
        );
        this.energyVisualPickerBrand = 'all';
        this._forceRender = true;
        this.render();
        return;
      }
      const settingsTopic = event.target.closest('[data-settings-topic-profile]');
      if (settingsTopic && !settingsTopic.disabled) {
        this.selectedStrategyProfileId = settingsTopic.dataset.settingsTopicProfile || '';
        this.persistInteractionContext();
        this._forceRender = true;
        this.render();
        return;
      }
      const strategyEdit = event.target.closest('[data-strategy-edit]');
      if (strategyEdit && !strategyEdit.disabled) { this.strategyEditProfileId = strategyEdit.dataset.strategyEdit || ''; this.render(); return; }
      const strategyCancel = event.target.closest('[data-strategy-cancel]');
      if (strategyCancel && !strategyCancel.disabled) {
        const profileId = strategyCancel.dataset.strategyCancel || '';
        this.clearProfileDrafts(this.runtime(), profileId);
        this.strategyEditProfileId = '';
        this.render();
        return;
      }
      const strategySave = event.target.closest('[data-strategy-save]');
      if (strategySave && !strategySave.disabled) {
        const profileId = strategySave.dataset.strategySave || '';
        this.savePropertyDrafts(profileId);
        return;
      }
      const saveAll = event.target.closest('[data-save-property-drafts]');
      if (saveAll && !saveAll.disabled) { this.savePropertyDrafts(); return; }
      const discardAll = event.target.closest('[data-discard-property-drafts]');
      if (discardAll && !discardAll.disabled) { this.editDrafts = {}; this.render(); return; }
      const sourceNav = event.target.closest('[data-source-asset-nav], .rhiUxAssetRelationshipLink[data-nav]');
      if (sourceNav && !sourceNav.disabled) {
        const path = String(sourceNav.dataset.sourceAssetNav || sourceNav.dataset.nav || '').trim();
        if (path && !/^[a-z][a-z0-9+.-]*:/i.test(path) && !path.startsWith('//')) {
          event.preventDefault();
          history.pushState(null, '', path);
          window.dispatchEvent(new Event('location-changed'));
        }
        return;
      }
      const tabTarget = event.target.closest('[data-tab-target]');
      if (tabTarget) {
        event.preventDefault();
        this.navigateToView(tabTarget.dataset.tabTarget || this.view);
        return;
      }
      const sectionTab = event.target.closest('[data-nav-section]:not([data-nav-item])');
      if (sectionTab) {
        this.selectNavigation(sectionTab.dataset.navSection || 'energy');
        return;
      }
      const itemTab = event.target.closest('[data-nav-item]');
      if (itemTab) {
        const tabs = this.shadowRoot.querySelector('.navItems');
        if (tabs) this.navScrollLeft = tabs.scrollLeft;
        this.selectNavigation(itemTab.dataset.navSection || this.navSection, itemTab.dataset.navItem || '');
        return;
      }
      const scrollTarget = event.target.closest('[data-scroll-target]');
      if (scrollTarget) { this.shadowRoot.getElementById(scrollTarget.dataset.scrollTarget)?.scrollIntoView({ behavior: 'auto', block: 'start' }); return; }
      const sort = event.target.closest('[data-load-sort]');
      if (sort && !sort.disabled) { this.loadSort = sort.dataset.loadSort || 'priority'; this.render(); return; }
      const meteringSort = event.target.closest('[data-metering-sort]');
      if (meteringSort && !meteringSort.disabled) { this.meteringSort = meteringSort.dataset.meteringSort || 'default'; this.render(); return; }
      const consumerSort = event.target.closest('[data-consumer-sort]');
      if (consumerSort && !consumerSort.disabled) { this.consumerSort = consumerSort.dataset.consumerSort || 'power'; this.render(); return; }
      const consumerFilter = event.target.closest('[data-consumer-filter]');
      if (consumerFilter && !consumerFilter.disabled) { this.consumerFilter = consumerFilter.dataset.consumerFilter || 'all'; this.render(); return; }
      const profilePick = event.target.closest('[data-strategy-profile-id]');
      if (profilePick && !profilePick.disabled) { this.selectedStrategyProfileId = profilePick.dataset.strategyProfileId || ''; this.render(); return; }
      const energyHistoryPeriod = event.target.closest('[data-energy-history-period]');
      if (energyHistoryPeriod && !energyHistoryPeriod.disabled) {
        this.selectedEnergyHistoryPeriodId = energyHistoryPeriod.dataset.energyHistoryPeriod || 'day';
        this._forceRender = true;
        this.render();
        return;
      }
      const gasHorizon = event.target.closest('[data-gas-horizon]');
      if (gasHorizon && !gasHorizon.disabled) {
        this.selectedGasHorizonId = gasHorizon.dataset.gasHorizon || 'month';
        this.persistInteractionContext();
        this._forceRender = true;
        this.render();
        return;
      }
      const planningHorizon = event.target.closest('[data-planning-horizon]');
      if (planningHorizon && !planningHorizon.disabled) {
        this.selectedPlanningHorizonId = planningHorizon.dataset.planningHorizon || 'D0';
        this.persistInteractionContext();
        this._forceRender = true;
        this.render();
        return;
      }
      const scopePick = event.target.closest('[data-scope-id]');
      if (scopePick && !scopePick.disabled) {
        const context = scopePick.dataset.scopeContext || 'outlook';
        const id = scopePick.dataset.scopeId || '';
        if (context === 'metering-period') this.selectMeteringPeriod(id, 'metering_period_selector');
        else if (context === 'metering') this.selectedMeteringHorizonId = id || 'D0';
        else if (context === 'value') this.selectMeteringPeriod(id, 'value_period_selector');
        else this.selectedOutlookHorizonId = id || 'D0';
        this.render();
        return;
      }
      const horizonPick = event.target.closest('[data-horizon-id]');
      if (horizonPick && !horizonPick.disabled) {
        const context = horizonPick.dataset.horizonContext || 'outlook';
        if (context === 'metering') this.selectedMeteringHorizonId = horizonPick.dataset.horizonId || 'D0';
        else this.selectedOutlookHorizonId = horizonPick.dataset.horizonId || 'D0';
        this.render();
        return;
      }
      const detailSummary = event.target.closest('summary[data-detail-id]');
      if (detailSummary) {
        // Native details behaviour is intentional. Never rebuild the page merely
        // because the user opens or closes a disclosure.
        return;
      }
      const mode = event.target.closest('[data-mode-value]');
      if (mode && !mode.disabled) {
        this.requestPropertyWrite(mode.dataset.propertyKey, mode.dataset.modeValue, { source: 'segmented_mode' });
        return;
      }
      const remediationButton = event.target.closest('[data-metering-remediation-command-row-id]');
      if (remediationButton && !remediationButton.disabled) {
        const runtime = this.runtime();
        const command = runtime.commands().find(c => String(c.command_row_id || c.composite_key || '') === String(remediationButton.dataset.meteringRemediationCommandRowId || '')) || null;
        const remediation = runtime.meteringRemediations().find(r => String(r.remediation_id || '') === String(remediationButton.dataset.remediationId || '')) || {};
        this.requestMeteringRemediation(command, remediation);
        return;
      }
      const cmd = event.target.closest('[data-command-key]');
      if (cmd) {
        if (cmd.dataset.executable !== 'true') return;
        const runtime = this.runtime();
        const target = cmd.dataset.targetAssetId || '';
        const role = cmd.dataset.commandRole || '';
        const command = (target && role ? runtime.commandForAssetRole(target, role) : null)
          || runtime.commands().find(c => String(c.command_instance_id || c.command_row_id || '') === String(cmd.dataset.commandRowId || ''))
          || runtime.commands().find(c => String(c.command_id || '') === String(cmd.dataset.commandKey || '') && (!target || String(c.asset_id || c.target_asset_id || '') === String(target)))
          || null;
        this.requestCommandExecution(command, target);
      }
    }
    onInput(event) {
      const profileSelect = event.target.closest('[data-strategy-profile-select]');
      if (profileSelect && !profileSelect.disabled) {
        this.selectedStrategyProfileId = profileSelect.value || '';
        this.render();
        return;
      }
      const editor = event.target.closest('[data-property-key]');
      if (editor) {
        const key = editor.dataset.propertyKey || '';
        if (key) {
          this.editDrafts[key] = editor.type === 'checkbox' ? editor.checked : editor.value;
          editor.classList.add('dirty');
          editor.closest('.strategyTableRow')?.classList.add('changed');
          this.refreshDraftUi(editor.dataset.profileId || this.strategyEditProfileId || '');
        }
      }
      const input = event.target.closest('input[type=range][data-property-key]');
      if (!input) return;
      const value = Number(input.value);
      const field = input.closest('.sliderField');
      const live = field?.querySelector('[data-live-range-value]');
      if (live) {
        const unit = input.dataset.rangeUnit || '';
        live.textContent = Number.isFinite(value) ? `${value}${unit ? ` ${unit}` : ''}` : '—';
      }
    }
    onFocusIn(event) {
      const editor = event.target.closest('input,select,textarea');
      if (!editor) return;
      this.editSession = { propertyKey: editor.dataset.propertyKey || '', started: Date.now() };
      this.shadowRoot.querySelector('main')?.classList.add('editing');
    }
    onFocusOut(event) {
      const leaving = event.target.closest('input,select,textarea');
      if (!leaving) return;
      queueMicrotask(() => {
        const active = this.shadowRoot.activeElement;
        if (active && active.matches && active.matches('input,select,textarea')) return;
        this.editSession = null;
        this.shadowRoot.querySelector('main')?.classList.remove('editing');
        if (this.pendingRuntimeRender) {
          this.pendingRuntimeRender = false;
          this.render();
        }
      });
    }
    onKeyDown(event) {
      const input = event.target.closest('[data-property-key]');
      if (!input || input.disabled || event.key !== 'Enter') return;
      event.preventDefault();
      this.savePropertyDrafts();
    }
    onToggle(event) {
      const details = event.target.closest('details');
      if (!details) return;
      const key = details.dataset.persistKey || details.querySelector('summary')?.dataset.detailId || '';
      if (key) { this.disclosureOpen[key] = details.open; this.persistInteractionContext(); }
      if (!details.open) return;
      const surface = details.classList.contains('energyAssetDiagnostics') ? 'diagnostics'
        : details.classList.contains('energyAssetConfiguration') ? 'configuration'
        : details.classList.contains('energyAssetDetails') ? 'details'
        : '';
      if (surface && this._deferredCanonicalSurfaces.has(surface)) {
        this._deferredCanonicalSurfaces.delete(surface);
        this._forceRender = true;
        this.scheduleRender(true);
      }
    }
    restoreInteractionState() {
      const details = [...this.shadowRoot.querySelectorAll('details')];
      details.forEach((node, index) => {
        const summary = node.querySelector('summary');
        const key = summary?.dataset.detailId || `${this.view}:${index}:${(summary?.textContent || 'details').trim()}`;
        node.dataset.persistKey = key;
        if (Object.prototype.hasOwnProperty.call(this.disclosureOpen, key)) node.open = !!this.disclosureOpen[key];
      });
      Object.entries(this.editDrafts).forEach(([key, value]) => {
        const selector = `[data-property-key="${CSS.escape(key)}"]`;
        const control = this.shadowRoot.querySelector(selector);
        if (!control) return;
        if (control.type === 'checkbox') control.checked = !!value;
        else control.value = value;
        control.classList.add('dirty');
      });
    }
    onChange(event) {
      const nativePlanningSelect=event.target.closest('[data-planning-select]');
      if(nativePlanningSelect && !nativePlanningSelect.disabled) {
        const kind=String(nativePlanningSelect.dataset.planningSelect || '');
        const contract=kind==='provider'?'RHI_ENERGY_PLANNER_PROVIDER_CATALOG_V1':
          kind==='resolution'?'RHI_ENERGY_PLANNING_RESOLUTION_V1':null;
        const entityId=String(nativePlanningSelect.dataset.planningEntity || '');
        const source=this.runtime().rawState(entityId);
        const option=String(nativePlanningSelect.value || '');
        if(contract && entityId.startsWith('select.') &&
           source?.attributes?.canonical_contract===contract &&
           source?.attributes?.write_authority==='rhi_energy.config_entry.options' &&
           asArray(source.attributes.options).includes(option)) {
          // HA persists and reloads its single config entry. No speculative
          // success or frontend planner state change before native readback.
          this._hass.callService('select','select_option',{entity_id:entityId,option});
        }
        return;
      }
      const commandSelect = event.target.closest('[data-hold-command-select]');
      if (commandSelect && !commandSelect.disabled) {
        const runtime = this.runtime();
        const value = String(commandSelect.value || '').toLowerCase();
        const key = commandSelect.dataset.commandKey || '';
        const target = commandSelect.dataset.targetAssetId || '';
        if (key) {
          const command = runtime.commands().find(c => String(c.command_id || '') === String(key)) || null;
          this.requestCommandExecution(command, target);
        }
        return;
      }
      const meteringSortSelect = event.target.closest('[data-metering-sort-select]');
      if (meteringSortSelect && !meteringSortSelect.disabled) { this.meteringSort = meteringSortSelect.value || 'default'; this.render(); return; }
      const consumerSortSelect = event.target.closest('[data-consumer-sort-select]');
      if (consumerSortSelect && !consumerSortSelect.disabled) { this.consumerSort = consumerSortSelect.value || 'power'; this.render(); return; }
      const consumerFilterSelect = event.target.closest('[data-consumer-filter-select]');
      if (consumerFilterSelect && !consumerFilterSelect.disabled) { this.consumerFilter = consumerFilterSelect.value || 'all'; this.render(); return; }
      const profileSelect = event.target.closest('[data-strategy-profile-select]');
      if (profileSelect && !profileSelect.disabled) { this.selectedStrategyProfileId = profileSelect.value || ''; this.render(); return; }
      const scopeSelect = event.target.closest('[data-scope-select]');
      if (scopeSelect && !scopeSelect.disabled) {
        const context = scopeSelect.dataset.scopeContext || 'outlook';
        if (context === 'metering-period') this.selectMeteringPeriod(scopeSelect.value, 'metering_period_selector');
        else if (context === 'value') this.selectMeteringPeriod(scopeSelect.value, 'value_period_selector');
        else if (context === 'metering') this.selectedMeteringHorizonId = scopeSelect.value || 'D0';
        else this.selectedOutlookHorizonId = scopeSelect.value || 'D0';
        this.render();
        return;
      }
      const horizonSelect = event.target.closest('[data-horizon-select]');
      if (horizonSelect && !horizonSelect.disabled) {
        const context = horizonSelect.dataset.horizonContext || 'outlook';
        if (context === 'metering') this.selectedMeteringHorizonId = horizonSelect.value || 'D0';
        else this.selectedOutlookHorizonId = horizonSelect.value || 'D0';
        this.render();
        return;
      }
      const input = event.target.closest('[data-property-key]');
      if (!input || input.disabled) return;
      if (input.dataset.strategyProfileField && this.strategyEditProfileId) {
        const key = input.dataset.propertyKey || '';
        if (!key) return;
        this.editDrafts[key] = input.type === 'checkbox' ? input.checked : input.value;
        input.classList.add('dirty');
        this.refreshDraftUi(input.dataset.profileId || this.strategyEditProfileId || '');
        this.render();
        return;
      }
      const value = input.type === 'checkbox' ? input.checked : input.value;
      if (input.dataset.propertyImmediateWrite === 'true') {
        this.requestPropertyWrite(input.dataset.propertyKey, value, { source:'editable_property', profile_id:input.dataset.profileId || '', field_key:input.dataset.fieldKey || '' });
        return;
      }
      // Free-form and range editors remain local drafts until the shared Save action.
      // Selects and toggles are discrete stable-ID choices and commit immediately.
      if (['number','range','text','time','date','datetime-local','email','url','tel','password','search','textarea'].includes(String(input.type || input.tagName).toLowerCase())) return;
      this.requestPropertyWrite(input.dataset.propertyKey, value, { source: input.dataset.strategyProfileField ? 'strategy_profile_field' : 'editable_property', profile_id: input.dataset.profileId || '', field_key: input.dataset.fieldKey || '' });
    }
    validationMeta(row) {
      const validation = parseMaybeJson(row?.validation, row?.validation || {});
      const meta = (validation && typeof validation === 'object') ? { ...validation } : {};
      const text = typeof validation === 'string' ? validation : '';
      const nums = text.match(/-?\d+(?:\.\d+)?/g)?.map(Number) || [];
      if (meta.min === undefined && nums.length >= 1) meta.min = nums[0];
      if (meta.max === undefined && nums.length >= 2) meta.max = nums[1];
      if (meta.step === undefined) {
        const stepMatch = text.match(/step\s+(-?\d+(?:\.\d+)?)/i);
        if (stepMatch) meta.step = Number(stepMatch[1]);
      }
      return meta;
    }
    isEditableRow(row) {
      return !!row && (asBool(row.editable, false) || String(row.access || '').toLowerCase() === 'editable');
    }
    writeMeta(row) {
      const rawOperation = row?.write_operation;
      const write = objectFrom(row?.write || row?.write_contract || row?.write_metadata || (typeof rawOperation === 'object' ? rawOperation : {}));
      const operationId = String(firstDefined(write.operation_id, typeof rawOperation === 'string' ? rawOperation : null, row?.operation_id, '') || '').trim();
      const supported = asBool(firstDefined(write.supported, row?.write_supported, operationId === 'energy.property.write'), false);
      const data = objectFrom(firstDefined(write.data, row?.write_data, {}));
      const propertyId = String(firstDefined(row?.property_id, row?.property_key, row?.key, data.property_id, '') || '').trim();
      const valueParameter = String(firstDefined(write.value_parameter, row?.value_parameter, 'value') || 'value');
      const readbackProperty = String(firstDefined(write.readback_property, row?.readback_property, propertyId, '') || '').trim();
      const service=String(firstDefined(write.service,row?.service,'') || '').trim();
      const split=splitService(service);
      return { supported, operationId, service, domain:split.domain, action:split.action, data:{...data, property_id:propertyId}, valueParameter, readbackProperty, propertyId };
    }
    hasPublicWriteRoute(row) {
      const meta = this.writeMeta(row);
      return meta.supported && meta.operationId === 'energy.property.write' && meta.service === 'rhi_energy.write_property' && !!meta.propertyId && !!meta.readbackProperty;
    }
    isWritableRow(row) { return this.hasPublicWriteRoute(row); }
    refreshDraftUi(profileId = '') {
      const rt = this.runtime();
      const profile = profileId ? rt.strategyProfileFor(profileId) : null;
      const keys = profile ? new Set(this.profileEditableRows(rt, profile).map(row => this.propertyKeyFor(row)).filter(Boolean)) : (profileId === 'pricing_settings' ? new Set(Object.keys(this.editDrafts || {}).filter(key => String(key).startsWith('pricing.'))) : null);
      const count = Object.keys(this.editDrafts || {}).filter(key => !keys || keys.has(key)).length;
      const save = profileId ? this.shadowRoot.querySelector(`[data-strategy-save="${CSS.escape(profileId)}"]`) : this.shadowRoot.querySelector('[data-save-property-drafts]');
      if (save) save.disabled = count === 0;
      const counter = save?.parentElement?.querySelector('.strategyChangeCount');
      if (counter) counter.textContent = count ? `${count} changed` : 'No changes';
    }
    writeFeedbackFor(row = {}) {
      const key = String(row.key || row.property_key || row.property_id || '');
      return key ? (this.writeFeedback[key] || null) : null;
    }
    valuesEqual(expected, actual) {
      const en = asNumber(expected), an = asNumber(actual);
      if (en !== null && an !== null) return Math.abs(en - an) <= 0.000001;
      return String(expected ?? '') === String(actual ?? '');
    }
    reconcileWriteFeedback() {
      if (!this._hass || !Object.keys(this.writeFeedback || {}).length) return;
      const runtime = this.runtime();
      Object.entries(this.writeFeedback).forEach(([propertyKey, fb]) => {
        if (!fb || !['pending','verifying'].includes(fb.state)) return;
        const row = runtime.row(fb.readbackProperty || propertyKey);
        const operation = objectFrom(row?.operation || {});
        const operationId = String(operation.operation_id || '').trim();
        const newOperation = Boolean(operationId && operationId !== String(fb.previousOperationId || ''));
        const lifecycle = String(firstDefined(operation.status, row.write_state, row.write_status, '') || '').toUpperCase();
        const reason = firstDefined(operation.reason, row.reason_text, row.write_message, row.reason, '');
        if (newOperation && ['REJECTED','FAILED','INVALID'].includes(lifecycle)) {
          this.writeFeedback[propertyKey] = { ...fb, state: 'rejected', reason: String(reason || 'Backend rejected the requested value'), updated: Date.now() };
          return;
        }
        if ((newOperation && ['TIMED_OUT','TIMEOUT'].includes(lifecycle)) || Date.now() - (fb.issuedAt || fb.updated) > 30000) {
          this.writeFeedback[propertyKey] = { ...fb, state: 'timed_out', reason: String(reason || 'No authoritative readback received'), updated: Date.now() };
          return;
        }
        // Transport completion and old equal-valued state are NOT proof.
        // Require the exact new producer operation, its CONFIRMED status,
        // matching requested/readback values and matching visible native state.
        if (fb.transportComplete && newOperation && lifecycle === 'CONFIRMED'
            && this.valuesEqual(fb.value, operation.requested_value)
            && this.valuesEqual(fb.value, operation.readback_value)
            && this.valuesEqual(fb.value, rowValue(row, null))) {
          this.writeFeedback[propertyKey] = { ...fb, state: 'accepted', acceptedValue: rowValue(row, null), updated: Date.now(), confirmedOperationId: operationId };
          delete this.editDrafts[propertyKey];
        } else if (fb.transportComplete) {
          this.writeFeedback[propertyKey] = { ...fb, state: 'verifying' };
        }
      });
    }
    reconcilePendingAppearances() {
      if (!this._hass || !Object.keys(this.pendingAppearanceByAsset || {}).length) return;
      const runtime = this.runtime();
      Object.entries(this.pendingAppearanceByAsset).forEach(([assetId, expected]) => {
        const feedback = this.writeFeedback[`appearance:${assetId}:visual_ref`];
        if (feedback && ['rejected','timed_out'].includes(String(feedback.state || '').toLowerCase())) {
          delete this.pendingAppearanceByAsset[assetId];
          return;
        }
        const asset = runtime.asset(assetId) || {};
        const actual = String(firstDefined(asset?.appearance?.configured_visual_ref, asset?.appearance?.effective_visual_ref, asset?.visual_ref, '') || '');
        if (actual === String(expected || '')) delete this.pendingAppearanceByAsset[assetId];
      });
    }

    requestPropertyWrite(propertyKey, value, context = {}) {
      const runtime = this.runtime();
      const catalogRow = runtime.editableProperty(propertyKey);
      const row = runtime.row(propertyKey);
      const profileRow = catalogRow || (row && !row.missing ? null : runtime.strategyProfileEditableRowByKey(propertyKey));
      const effectiveRow = catalogRow || profileRow || row;
      if (!this.isWritableRow(effectiveRow)) return;
      const meta = this.writeMeta(effectiveRow);
      const finalValue = coerceAllowedValue(effectiveRow, value);
      const propertyId = String(effectiveRow.property_id || effectiveRow.property_key || effectiveRow.key || propertyKey);
      const payload = { ...meta.data, property_id: String(meta.data.property_id || propertyId), [meta.valueParameter]: finalValue };
      this.writeFeedback[propertyKey] = { state: 'pending', value: finalValue, readbackProperty: meta.readbackProperty || propertyKey, operationId: meta.operationId, previousOperationId: String(objectFrom(row?.operation || effectiveRow?.operation || {}).operation_id || ''), issuedAt: Date.now(), updated: Date.now() };
      if (!this._hass?.callService) {
        this.writeFeedback[propertyKey] = { ...this.writeFeedback[propertyKey], state: 'rejected', reason: 'Public property writer unavailable', updated: Date.now() };
        this.render();
        return;
      }
      const call = this._hass.callService(meta.domain, meta.action, payload);
      Promise.resolve(call).then(() => {
        this.writeFeedback[propertyKey] = { ...this.writeFeedback[propertyKey], state: 'verifying', transportComplete: true, updated: Date.now() };
        this.render();
      }).catch(error => {
        this.writeFeedback[propertyKey] = { ...this.writeFeedback[propertyKey], state: 'rejected', reason: error?.message || String(error), updated: Date.now() };
        this.render();
      });
      this.dispatchEvent(new CustomEvent('homebrain-energy-property-intent-sent', {
        bubbles: true, composed: true, detail: { operation_id: meta.operationId, property_id: payload.property_id, value: finalValue, context }
      }));
    }
    savePropertyDrafts(profileId = '') {
      const runtime = this.runtime();
      const selectedProfile = profileId ? runtime.strategyProfileFor(profileId) : null;
      const allowedKeys = selectedProfile ? new Set(this.profileEditableRows(runtime, selectedProfile).map(row => this.propertyKeyFor(row)).filter(Boolean)) : (profileId === 'pricing_settings' ? new Set(Object.keys(this.editDrafts || {}).filter(key => String(key).startsWith('pricing.'))) : null);
      const drafts = Object.entries(this.editDrafts || {}).filter(([key]) => !allowedKeys || allowedKeys.has(key));
      if (!drafts.length) return;
      let dispatched = 0;
      drafts.forEach(([propertyKey, raw]) => {
        const catalogRow = runtime.editableProperty(propertyKey);
        const row = runtime.row(propertyKey);
        const profileRow = runtime.strategyProfileEditableRowByKey(propertyKey);
        const effectiveRow = catalogRow || profileRow || (row && !row.missing ? row : null);
        if (!this.isWritableRow(effectiveRow)) {
          this.writeFeedback[propertyKey] = { state: 'rejected', reason: effectiveRow?.editable_reason || 'Editing is unavailable', updated: Date.now() };
          return;
        }
        const control = this.shadowRoot.querySelector(`[data-property-key="${CSS.escape(propertyKey)}"]`);
        const inputType = String(control?.type || '').toLowerCase();
        const value = inputType === 'checkbox' ? !!raw : ((inputType === 'number' || inputType === 'range') ? Number(raw) : raw);
        this.requestPropertyWrite(propertyKey, value, { source: 'strategy_save', profile_id: effectiveRow?.profile_id || profileId, field_key: effectiveRow?.field_key || '' });
        dispatched += 1;
      });
      this.render();
    }
    propertyDraftBar() { return ''; }
    commandMeta(command) {
      const invoke = objectFrom(command?.invoke || {});
      const service = String(invoke.service || '').trim();
      const split = splitService(service);
      return {
        operationId: String(invoke.operation_id || ''),
        service,
        domain: split.domain,
        action: split.action,
        data: objectFrom(invoke.data || {})
      };
    }
    requestCommandExecution(command, targetAssetId = '', parameterValues = {}) {
      if (!command || !this.runtime().commandEnabled(command)) return;
      const meta = this.commandMeta(command);
      if (meta.operationId !== 'energy.command.execute' || meta.service !== 'rhi_energy.invoke_command' || !meta.domain || !meta.action || !this._hass?.callService) return;
      const commandId = String(command.command_id || meta.data.command_id || '');
      const target = String(targetAssetId || command.target_asset_id || meta.data.target_asset_id || '');
      const parameters = { ...objectFrom(meta.data.parameters || {}), ...objectFrom(parameterValues || {}) };
      const payload = { ...meta.data, command_id: commandId, target_asset_id: target, parameters };
      this._hass.callService(meta.domain, meta.action, payload);
      this.dispatchEvent(new CustomEvent('homebrain-energy-command-intent-sent', {
        bubbles: true, composed: true, detail: { operation_id: meta.operationId, ...payload }
      }));
    }
    requestMeteringRemediation(command, remediation = {}) {
      if (!command || !this.runtime().commandEnabled(command)) return;
      const id = String(remediation.remediation_id || remediation.problem_id || command.command_instance_id || command.command_id || 'metering_remediation');
      const affected = asArray(remediation.affected_keys || []);
      const requiresConfirmation = asBool(command.requires_confirmation ?? remediation.requires_confirmation ?? true, true);
      if (requiresConfirmation) {
        const period = human(remediation.period_id || command.period_id || 'selected period');
        const ok = window.confirm(`Reset metering baseline for ${period}?\n\nThis calibrates only the selected period baseline. It does not change source lifetime totals or Home Assistant statistics.`);
        if (!ok) return;
      }
      this.remediationFeedback[id] = { state: 'pending', updated: Date.now(), command_id: command.command_id };
      try {
        // The period is part of the authoritative public invoke payload. Do not
        // reinterpret it as a typed parameter or add remediation-only fields.
        this.requestCommandExecution(command, command.target_asset_id || 'metering', {});
        this.remediationFeedback[id] = { state: 'pending_verification', updated: Date.now(), command_id: command.command_id };
      } catch (error) {
        this.remediationFeedback[id] = { state: 'failed', updated: Date.now(), reason: error?.message || String(error), command_id: command.command_id };
      }
      this.render();
    }
    componentActionButton(command, label, assetId) {
      const model = createCommandActionModel(command);
      if (!model) return '';
      const effectiveLabel = label || model.label;
      const target = assetId || model.targetAssetId;
      return `<button class="hiAction rhiUxQuickAction ${model.enabled ? 'enabled' : 'disabled'}" ${model.enabled ? '' : 'disabled'} data-command-key="${escapeHtml(model.id)}" data-command-row-id="${escapeHtml(model.rowId)}" data-command-role="${escapeHtml(model.role)}" data-target-asset-id="${escapeHtml(target)}" data-executable="${model.enabled ? 'true' : 'false'}" title="${escapeHtml(model.reason)}">${escapeHtml(effectiveLabel)}</button>`;
    }
    componentActionModelButton(model) {
      return model ? this.componentActionButton(model.command, model.label, model.targetAssetId) : '';
    }
    componentSegmentedControl(options, active, extraClass = '') {
      return `<div class="hiSegmented ${escapeHtml(extraClass)}">${options.map(option => {
        const activeClass = String(option.value).toLowerCase() === String(active || '').toLowerCase() ? 'active' : '';
        const disabled = option.disabled ? 'disabled' : '';
        const attrs = Object.entries(option.attrs || {}).map(([key, value]) => `${key}="${escapeHtml(value)}"`).join(' ');
        return `<button class="hiSegment ${activeClass}" ${disabled} ${attrs}>${escapeHtml(option.label)}</button>`;
      }).join('')}</div>`;
    }
    componentDetailsBlock(id, label, bodyHtml) {
      const detailsOpen = this.detailOpen[id] ? ' open' : '';
      return `<details class="hiDetails"${detailsOpen}><summary data-detail-id="${escapeHtml(id)}">${escapeHtml(label)}</summary><div class="softBox">${bodyHtml}</div></details>`;
    }

    componentQualityChip(status) {
      const raw = String(status || '').trim();
      const key = raw.toUpperCase().replace(/[\s-]+/g, '_');
      const semantic = {
        MEASURED:['ok','Measured'], TRUSTED:['ok','Measured'], COMPLETE:['ok','Complete'],
        OK:['ok','OK'], READY:['ok','Ready'], VERIFIED:['ok','Verified'],
        NOT_APPLICABLE:['missing','Not applicable'],
        ATTRIBUTION_PENDING:['warn','Attribution pending'], PENDING:['warn','Pending'],
        PARTIAL:['warn','Partial'], INCOMPLETE:['warn','Incomplete'],
        UNAVAILABLE:['missing','Unavailable'], UNKNOWN:['missing','Unavailable'],
        FAILED:['fail','Measurement failed'], ERROR:['fail','Error']
      };
      if (semantic[key]) {
        const [tone,label] = semantic[key];
        return `<span class="qs ${escapeHtml(tone)}">${escapeHtml(label)}</span>`;
      }
      const normalized = rowState({ health: status, value: status || null });
      return `<span class="qs ${escapeHtml(normalized)}">${escapeHtml(rowStatusLabel({ health: status, value: status || null }))}</span>`;
    }
    componentKpiCard({ icon = '•', label = '', value = '—', sub = '', tone = '', status = '' } = {}) {
      return `<div class="metric ${escapeHtml(tone)}"><div class="mi">${escapeHtml(icon)}</div><div><span class="ml">${escapeHtml(label)}</span><b class="mv">${escapeHtml(value)}</b><span class="ms">${escapeHtml(sub)}</span></div>${status ? this.componentQualityChip(status) : ''}</div>`;
    }
    componentInfoRow(label, value) {
      return `<div class="kv"><span>${escapeHtml(label)}</span><b>${escapeHtml(value ?? '—')}</b></div>`;
    }
    componentProgressBar(value, max = null) {
      const n = asNumber(value);
      if (n === null) return 0;
      const ceiling = asNumber(max);
      if (ceiling !== null && ceiling > 0) return Math.max(0, Math.min(100, (n / ceiling) * 100));
      return Math.max(0, Math.min(100, Math.abs(n) * 10));
    }
    componentAssetRow({ icon = '•', title = '', label = '', value = '—', pct = 0 } = {}) {
      const width = Math.max(0, Math.min(100, asNumber(pct) ?? 0));
      return `<div class="assetRow"><div class="round">${escapeHtml(icon)}</div><div class="grow"><b>${escapeHtml(title)}</b><span>${escapeHtml(label)}</span><div class="bar"><i style="width:${escapeHtml(width)}%"></i></div></div><strong>${escapeHtml(value)}</strong></div>`;
    }
    productStoryCard({ eyebrow = 'Current situation', title = '', why = '', recommendation = '', actions = '', details = '', tone = 'blue' } = {}) {
      return `<section class="panel productStory ${escapeHtml(tone)}"><div class="productStoryCopy"><small>${escapeHtml(eyebrow)}</small><h2>${escapeHtml(title)}</h2>${why ? `<p>${escapeHtml(why)}</p>` : ''}${recommendation ? `<div class="productStoryRecommendation"><span>Home Intelligence recommendation</span><b>${escapeHtml(recommendation)}</b></div>` : ''}</div>${actions ? `<div class="productStoryActions">${actions}</div>` : ''}${details ? this.componentDetailsBlock(`story-${Math.abs(String(title).split('').reduce((a,c)=>a+c.charCodeAt(0),0))}`, 'Details', details) : ''}</section>`;
    }
    userSafeProductText(value, fallback = '') {
      const raw = String(value ?? '').trim();
      if (!raw) return fallback;
      if (/\b(?:RHI_[A-Z0-9_]+|sensor\.|script\.|property[_ ]?key|entity[_ ]?id|asset[_ ]?id|command[_ ]?id|contract(?:_id)?|canonical contract|public\s+write\s+route|backend)\b/i.test(raw)) return fallback;
      if (/^[a-z0-9]+(?:[_.:-][a-z0-9]+)+$/i.test(raw)) return fallback;
      return raw;
    }
    userSafeReason(value, fallback = 'This information is not available yet.') {
      const raw = String(value ?? '').trim();
      const key = raw.toLowerCase().replace(/[\s.-]+/g,'_');
      const known = {
        not_published:'reason.not_published', not_available:'reason.not_available',
        unavailable:'reason.not_available', disabled:'reason.disabled',
        automation_disabled:'reason.automation_disabled', intelligence_off:'reason.intelligence_off',
        verification_required:'reason.verification_required', reset_pending:'reason.reset_pending',
        confirmation_needed:'reason.confirmation_needed', not_configured:'reason.not_configured',
        configuration_required:'reason.not_configured'
      };
      if (known[key]) return rhiEnergyT(this._hass,known[key],{},fallback);
      return this.userSafeProductText(raw,fallback);
    }
    productStateLabel(value, fallback = 'Not available') {
      const key = String(value ?? '').trim().toLowerCase().replace(/[\s.-]+/g, '_');
      const map = {
        available:'Ready', ready:'Ready', ok:'Ready', verified:'Verified', trusted:'Verified', complete:'Complete',
        unavailable:'Not available', not_available:'Not available', missing:'Not available', not_published:'Not available',
        disabled:'Not managed', excluded:'Not managed', off:'Off', advice:'Advice', recommend:'Advice', recommendation:'Advice', automatic:'Automatic', automation:'Automatic',
        waiting:'Waiting', planned:'Scheduled', scheduled:'Scheduled', active:'Running', running:'Running', charging:'Charging', discharging:'Discharging', paused:'Paused', busy:'In progress',
        succeeded:'Completed', completed:'Completed', failed:'Could not complete', blocked:'Blocked', constrained:'Limited', overridden:'Overridden',
        baseline_required:'Needs one-time reset', baseline_untrusted:'Needs one-time reset', verification_required:'Verification required', reset_pending:'Reset in progress',
        partial:'Partial', estimated:'Estimated', incomplete:'Incomplete', configuration_required:'Setup required',
        preparing:'Preparing', pending:'In progress', unknown:'Not available', trust_state:'Measurement quality'
      };
      return map[key] || fallback;
    }
    userStateText(value, fallback = 'Available') {
      const raw = String(value ?? '').trim();
      const mapped = this.productStateLabel(raw, '');
      if (mapped) return mapped;
      return this.userSafeProductText(raw, this.productStateLabel(fallback, 'Not available'));
    }
    userRelationshipLabel(value, fallback = 'Assigned charger') {
      const raw = String(value ?? '').trim();
      if (!raw) return fallback;
      if (/\b[0-9a-f]{12,}\b/i.test(raw) || /[0-9a-f]{8}-[0-9a-f-]{20,}/i.test(raw)) return fallback;
      return this.userSafeProductText(raw, fallback);
    }
    componentRecommendationCard({ title = '', body = '', meta = '' } = {}) {
      return `<div class="rec"><div class="check">✓</div><div><small>${escapeHtml(rhiEnergyT(this._hass,"common.recommendation",{},"Recommendation"))}</small><h2>${escapeHtml(title)}</h2><p>${escapeHtml(body)}</p>${meta ? `<div class="recMeta">${meta}</div>` : ''}</div><span>›</span></div>`;
    }

    // Backwards-compatible aliases keep the R3.44.8 visual output stable while making
    // shared components the single place for reusable UI behavior.
    qualityChip(status) { return this.componentQualityChip(status); }
    metric(icon, label, value, sub, tone = '', status = '') { return this.componentKpiCard({ icon, label, value, sub, tone, status }); }
    kv(label, value) { return this.componentInfoRow(label, value); }
    flexibleAssetDomain(rt) {
      if (!this._flexibleAssetDomains) this._flexibleAssetDomains = new WeakMap();
      if (!this._flexibleAssetDomains.has(rt)) this._flexibleAssetDomains.set(rt, new FlexibleAssetDomainModel(rt));
      return this._flexibleAssetDomains.get(rt);
    }
    dataRow(rt, keys) {
      const list = asArray(keys);
      const rows = list.map(key => rt.row(key));
      return rows.find(row => !row.missing && rowValue(row, null) !== null) || rows[0] || { missing: true, value: null, health: 'NOT_PUBLISHED' };
    }
    selectedHorizon(horizons = [], wanted = 'D0') {
      const list = Array.isArray(horizons) ? horizons : [];
      if (!list.length) return null;
      const w = String(wanted || 'D0').toLowerCase();
      return list.find(h => String(h.horizon_id || '').toLowerCase() === w) || null;
    }
    selectedPeriod(periods = [], wanted = 'today') {
      const list = Array.isArray(periods) ? periods : [];
      if (!list.length) return null;
      const w = String(wanted || 'today').toLowerCase();
      return list.find(p => String(p.period_id || '').toLowerCase() === w) || null;
    }
    horizonValue(horizon, group, key, fallback = null) {
      const summary = objectFrom(horizon?.summary || {});
      const source = group ? objectFrom(summary[group] || {}) : summary;
      const value = firstDefined(valueAtPath(source, key), source[key], fallback);
      return value === undefined || value === '' ? fallback : value;
    }
    horizonNumber(horizon, group, key) { return asNumber(this.horizonValue(horizon, group, key, null)); }
    horizonLabel(horizon) { return human(firstDefined(horizon?.label, horizon?.horizon_id, 'Horizon')); }
    periodLabel(period) { return human(firstDefined(period?.label, period?.period_id, 'Period')); }
    isFutureHorizon(horizon) { return String(horizon?.horizon_id || '').toUpperCase() === 'D1' || /tomorrow/i.test(String(horizon?.label || '')); }
    componentScopeSelector({ context = 'outlook', title = 'Horizon', items = [], selectedId = '', idField = 'id', labelFn = item => human(item?.label || item?.id || '') }) {
      const list = Array.isArray(items) ? items : [];
      if (!list.length) return '';
      const normalized = list.map(item => ({ item, id: String(item?.[idField] || item?.id || ''), label: labelFn(item) })).filter(row => row.id);
      if (!normalized.length) return '';
      const requestedId = String(selectedId || '');
      const active = normalized.find(row => row.id.toLowerCase() === requestedId.toLowerCase()) || null;
      const unavailableOption = requestedId && !active
        ? `<option value="${escapeHtml(requestedId)}" selected disabled>Selected ${escapeHtml(title.toLowerCase())} temporarily unavailable</option>`
        : '';
      const buttons = normalized.map(row => `<button type="button" class="scopeOption ${active && row.id === active.id ? 'active' : ''}" data-scope-context="${escapeHtml(context)}" data-scope-id="${escapeHtml(row.id)}">${escapeHtml(row.label)}</button>`).join('');
      const select = `<select data-scope-select data-scope-context="${escapeHtml(context)}">${unavailableOption}${normalized.map(row => `<option value="${escapeHtml(row.id)}" ${active && row.id === active.id ? 'selected' : ''}>${escapeHtml(row.label)}</option>`).join('')}</select>`;
      return `<div class="scopeSelector"><div class="scopeSelectorTitle"><span>${escapeHtml(title)}</span><b>${escapeHtml(active ? active.label : (requestedId ? 'Temporarily unavailable' : 'Not selected'))}</b></div><div class="scopeButtons">${buttons}</div>${select}</div>`;
    }
    componentHorizonSelector(context, horizons = [], selectedId = 'D0') {
      return this.componentScopeSelector({ context, title: rhiEnergyT(this._hass,'common.horizon',{},'Horizon'), items: horizons, selectedId, idField: 'horizon_id', labelFn: h => this.horizonLabel(h) });
    }
    componentPeriodSelector(periods = [], selectedId = 'today', context = 'metering-period') {
      return this.componentScopeSelector({ context, title: rhiEnergyT(this._hass,'common.period',{},'Period'), items: periods, selectedId, idField: 'period_id', labelFn: p => this.periodLabel(p) });
    }
    listChips(values) {
      const items = asArray(values).map(item => human(item, '')).filter(Boolean);
      return items.length ? `<div class="warningChips">${items.map(item => `<span>${escapeHtml(item)}</span>`).join('')}</div>` : '';
    }
    contractGap(title, body, details = '') {
      const safeTitle = this.userSafeProductText(title, rhiEnergyT(this._hass,'common.not_available',{},'Not available'));
      const safeBody = this.userSafeProductText(body, rhiEnergyT(this._hass,'common.information_missing',{},'This information is not available yet.'));
      const diagnostics = this.config?.show_diagnostics === true && details
        ? this.componentDetailsBlock('diagnostics-' + String(title || 'information').toLowerCase().replace(/[^a-z0-9]+/g, '-'), rhiEnergyT(this._hass,'common.diagnostics',{},'Diagnostics'), details)
        : '';
      return `<section class="panel wide"><h2>${escapeHtml(safeTitle)}</h2><p>${escapeHtml(safeBody)}</p>${diagnostics}</section>`;
    }
    rowStatus(row) {
      if (!row || row.missing) return 'missing';
      return row.health || row.quality || row.value_status || row.status || rowState(row);
    }
    metricFromRow(rt, icon, label, keys, formatter, sub, tone = '', fallback = '—') {
      const row = this.dataRow(rt, keys);
      const value = rowValue(row, null);
      const display = value === null || value === undefined || value === '' ? fallback : formatter(value);
      return this.metric(icon, label, display, sub, tone, this.rowStatus(row));
    }
    energyAutomationMode(rt, d = null) {
      const decision = d || rt.decision();
      return String(firstDefined(decision.automation_mode, decision.mode, rt.value('energy_intelligence.automation_mode', ''), rt.value('energy_intelligence.mode', '')) || '').toLowerCase();
    }
    isEnergyIntelligenceActive(rt, d = null) {
      const mode = this.energyAutomationMode(rt, d);
      return mode && !['disabled','off','manual','observe_only','observe only'].includes(mode);
    }
    effectiveBatteryPolicy(rt) {
      return rt.effectiveStrategyFor('battery')
        || rt.effectiveStrategyFor('home_battery')
        || rt.effectiveStrategyRows().find(row => /battery|storage/i.test(`${row.asset_id || ''} ${row.asset_type || ''} ${row.profile_id || ''} ${row.flexible_role || ''}`))
        || {};
    }
    batteryReservePct(rt) {
      const row = this.dataRow(rt, ['battery.protected_reserve_pct','battery.reserve_target_pct','battery.minimum_reserve_pct']);
      const rowValueNumber = asNumber(rowValue(row, null));
      if (rowValueNumber !== null) return rowValueNumber;
      const effective = this.effectiveBatteryPolicy(rt);
      return asNumber(firstDefined(effective.protected_reserve_pct, effective.reserve_target_pct, effective.minimum_target_value));
    }
    batteryProtectedReserveKwh(rt) {
      const row = this.dataRow(rt, ['battery.protected_reserve_kwh','battery.reserve_target_kwh','battery.minimum_reserve_kwh']);
      const rowValueNumber = asNumber(rowValue(row, null));
      if (rowValueNumber !== null) return rowValueNumber;
      const effective = this.effectiveBatteryPolicy(rt);
      return asNumber(firstDefined(effective.protected_reserve_kwh, effective.reserve_target_kwh));
    }
    batteryAboveReserveKwh(rt) {
      const row = this.dataRow(rt, ['battery.available_above_reserve_kwh','battery.usable_above_reserve_kwh']);
      const rowValueNumber = asNumber(rowValue(row, null));
      if (rowValueNumber !== null) return rowValueNumber;
      const effective = this.effectiveBatteryPolicy(rt);
      return asNumber(firstDefined(effective.available_above_reserve_kwh, effective.usable_above_reserve_kwh));
    }
    flexibleNeedKwh(rt) {
      const values = this.flexibleAssetDomain(rt).planningParticipants().map(vm => asNumber(firstDefined(vm.raw.energy_to_target_kwh, vm.raw.energy_needed_kwh, vm.raw.remaining_energy_kwh))).filter(value => value !== null);
      if (!values.length) return null;
      return values.reduce((sum, value) => sum + Math.max(0, value), 0);
    }
    flexiblePowerNowKw(rt) {
      // Aggregate managed power is backend-owned current truth. Never rebuild it
      // from participant rows, which are a different semantic population.
      const physical = rt.number('flexible_loads.power_kw');
      return physical === null ? null : Math.abs(physical);
    }
    currentEnergyModel(rt) { return createCurrentEnergyViewModel(rt.contractGateway()); }
    progress(value, max = null) { return this.componentProgressBar(value, max); }
    assetRow(icon, title, label, value, pct) { return this.componentAssetRow({ icon, title, label, value, pct }); }
    recCard(title, body, meta = '') { return this.componentRecommendationCard({ title, body, meta }); }
    scene(rt) {
      const current = this.currentEnergyModel(rt);
      const solar = current.solar.powerKw;
      const batteryShown = current.battery.displayPowerKw;
      const batteryLabel = current.battery.label;
      const gridExport = current.grid.exportPowerKw;
      const gridShown = current.grid.displayPowerKw;
      const gridLabel = current.grid.label;
      return `<div class="energyScene liveFlow">
        <div class="sceneTitle"><b>${escapeHtml(rhiEnergyT(this._hass,"hero.overview.title",{},"Energy Overview"))}</b><span>${escapeHtml(rhiEnergyT(this._hass,"hero.overview.description",{},"See what your home is producing, using, storing and exchanging right now."))}</span></div>
        <div class="solarPath"></div><div class="batteryPath"></div><div class="gridPath"></div>
        <div class="house"><div class="roof"></div><div class="wall"><i></i><i></i><i></i></div><div class="panels"><i></i><i></i><i></i><i></i><i></i></div></div>
        <div class="car"></div>
        <div class="float solar"><span>${escapeHtml(rhiEnergyT(this._hass,"nav.solar",{},"Solar"))}</span><b>${fmtKw(solar)}</b><small>${solar === null ? escapeHtml(rhiEnergyT(this._hass,"common.not_available",{},"Not available")) : solar > 0.005 ? escapeHtml(rhiEnergyT(this._hass,"common.producing",{},"Producing")) : escapeHtml(rhiEnergyT(this._hass,"common.idle",{},"Idle"))}</small></div>
        <div class="float battery"><span>${escapeHtml(rhiEnergyT(this._hass,"nav.battery",{},"Home Battery"))}</span><b>${fmtKw(batteryShown)}</b><small>${escapeHtml(batteryLabel)}</small></div>
        <div class="float grid"><span>${escapeHtml(rhiEnergyT(this._hass,"solar.grid",{},"Grid"))}</span><b>${fmtKw(gridShown)}</b><small>${escapeHtml(gridLabel)}</small></div>
        <div class="float export">↔ ${fmtKw(gridExport, '0.0 kW')}</div>
      </div>`;
    }
    overviewExperiencePanel(rt) { return ''; }
    pilotReadinessPanel(rt) { return ''; }


    pageContextControls(rt, tab) {
      if (tab === 'outlook') return this.componentHorizonSelector('outlook', rt.outlookHorizons(), this.selectedOutlookHorizonId);
      if (tab === 'consumers') return `<label class="hiQuickSelect"><span>Group</span><select data-consumer-filter-select>${this.consumerFilterOptions().map(([id,label])=>`<option value="${id}"${this.consumerFilter===id?' selected':''}>${label}</option>`).join('')}</select></label><label class="hiQuickSelect"><span>${escapeHtml(rhiEnergyT(this._hass,"common.sort",{},"Sort"))}</span><select data-consumer-sort-select>${this.consumerSortOptions().map(([id,label])=>`<option value="${id}"${this.consumerSort===id?' selected':''}>${label}</option>`).join('')}</select></label>`;
      if (tab === 'metering') return this.componentPeriodSelector(rt.meteringPeriods().length ? rt.meteringPeriods() : this.defaultMeteringPeriods(), this.selectedMeteringPeriodId) + this.componentMeteringSort();
      if (['operational-planning','planning','strategic-planning'].includes(tab)) {
        const selector = this.componentSegmentedControl([
          { value:'operational-planning', label:rhiEnergyT(this._hass,'nav.operational_plan',{},'Now'), attrs:{'data-tab-target':'operational-planning'} },
          { value:'planning', label:rhiEnergyT(this._hass,'nav.tactical_plan',{},'Today & Tomorrow'), attrs:{'data-tab-target':'planning'} },
          { value:'strategic-planning', label:rhiEnergyT(this._hass,'nav.strategic_plan',{},'Long term'), attrs:{'data-tab-target':'strategic-planning'} }
        ], tab, 'planningViewSelector');
        const d2Published = rt.nativePlanningHorizon('D2').published === true;
        const horizon = tab === 'planning'
          ? `<div class="scopeSelector"><button class="scopeOption ${this.selectedPlanningHorizonId==='D0'?'active':''}" data-planning-horizon="D0">${escapeHtml(rhiEnergyT(this._hass,'common.today',{},'Today'))}</button><button class="scopeOption ${this.selectedPlanningHorizonId==='D1'?'active':''}" data-planning-horizon="D1">${escapeHtml(rhiEnergyT(this._hass,'common.tomorrow',{},'Tomorrow'))}</button>${d2Published ? `<button class="scopeOption ${this.selectedPlanningHorizonId==='D2'?'active':''}" data-planning-horizon="D2">${escapeHtml(rhiEnergyT(this._hass,'planning.day_after_tomorrow',{},'Day after tomorrow'))}</button>` : ''}</div>`
          : '';
        return selector + horizon;
      }
      if (tab === 'value') return this.componentPeriodSelector(rt.meteringPeriods().length ? rt.meteringPeriods() : this.defaultMeteringPeriods(), this.selectedMeteringPeriodId, 'value');
      return '';
    }

    bodyContextBar(rt, tab, controlsId = '') {
      const controls = this.pageContextControls(rt, tab);
      if (!controls) return '';
      const aria = controlsId ? ` aria-controls="${escapeHtml(controlsId)}"` : '';
      return `<section class="rhiUxContextBar" aria-label="View"${aria}><small>View</small><div class="rhiUxContextControls">${controls}</div></section>`;
    }

    valueStateLabel(state) {
      const normalized = String(state || '').trim().toLowerCase();
      if (['complete','ok','ready'].includes(normalized)) return 'Complete';
      if (['incomplete','partial'].includes(normalized)) return 'Partial result';
      if (['not_configured','configuration_required','not ready','not_ready'].includes(normalized)) return 'Setup needed';
      if (['reset_pending','pending','baseline_reset_required'].includes(normalized)) return 'Awaiting reset';
      return 'Unavailable';
    }
    valueMoney(value, currency = 'EUR', state = '', missingLabel = '—') {
      const n = asNumber(value);
      if (n === null) return missingLabel;
      const symbol = String(currency || '').toUpperCase() === 'EUR' ? '€' : `${currency || ''} `;
      return `${symbol}${n.toFixed(2)}`;
    }
    pricingMode(rt) {
      const explicit = String(firstDefined(
        rt.value('pricing.export_pricing_mode', null),
        rt.value('pricing.export_compensation_mode', null),
        rt.value('pricing.mode', null),
        ''
      )).trim().toUpperCase();
      if (explicit === 'DIRECT_COMPENSATION' || explicit === 'SOURCE_MINUS_FEE') return explicit;
      return rt.value('pricing.export_compensation_fallback_eur_kwh', null) !== null
        ? 'DIRECT_COMPENSATION'
        : 'SOURCE_MINUS_FEE';
    }
    pricingTariffSpecs(rt) {
      const mode = this.pricingMode(rt);
      const exportInput = mode === 'DIRECT_COMPENSATION'
        ? { id:'export_compensation_fallback', label:rhiEnergyT(this._hass,'pricing.export_compensation',{},'Export compensation'), match:/export_compensation_fallback_eur_kwh/i, required:true, input:true }
        : { id:'export_fee', label:rhiEnergyT(this._hass,'pricing.export_fee',{},'Export fee'), match:/export_fee_eur_kwh/i, required:true, input:true };
      return [
        { id:'commodity', label:rhiEnergyT(this._hass,'pricing.commodity',{},'Commodity'), match:/(spot_price_current|commodity)(_eur_kwh)?$/i, required:true, input:true },
        { id:'network', label:rhiEnergyT(this._hass,'pricing.network',{},'Network'), match:/(import_network|distribution).*eur_kwh/i, required:true, input:true },
        { id:'taxes_levies', label:rhiEnergyT(this._hass,'pricing.taxes_levies',{},'Taxes & levies'), match:/(import_levies|taxes|levies).*eur_kwh/i, required:true, input:true },
        { id:'vat', label:rhiEnergyT(this._hass,'pricing.vat',{},'VAT'), match:/(import_vat_pct|vat_pct)/i, required:true, input:true },
        exportInput,
        { id:'export_compensation', label:rhiEnergyT(this._hass,'pricing.export_compensation',{},'Export compensation'), match:/export_compensation_current_eur_kwh/i, required:true, input:false, derived:true }
      ];
    }
    valueTariffRows(rt, breakdown = {}) {
      const all = rt.allRows ? [...rt.allRows().values()] : [];
      const findRow = (spec) => all.find(row => {
        const text = [row.key,row.property_key,row.property_id,row.display_name,row.name].filter(Boolean).join(' ');
        return spec.match.test(text);
      }) || null;
      const aliases = {
        commodity:['commodity','spot_price_current_eur_kwh','spot_price'],
        network:['network','distribution','import_network_eur_kwh'],
        taxes_levies:['taxes_levies','taxes','levies','import_levies_eur_kwh'],
        vat:['vat','import_vat_pct'],
        export_fee:['export_fee','export_fee_eur_kwh'],
        export_compensation_fallback:['export_compensation_fallback','export_compensation_fallback_eur_kwh'],
        export_compensation:['export_compensation','export_compensation_current_eur_kwh']
      };
      const pickBreakdown = (id) => {
        for (const key of aliases[id] || [id]) {
          if (breakdown && Object.prototype.hasOwnProperty.call(breakdown,key)) return breakdown[key];
        }
        return undefined;
      };
      const directFacts = {
        commodity: firstDefined(rt.value('pricing.spot_price_current_eur_kwh', null), rt.value('spot_price_current_eur_kwh', null), rt.value('pricing.raw_source_value', null)),
        network: rt.value('pricing.import_network_eur_kwh', null),
        taxes_levies: rt.value('pricing.import_levies_eur_kwh', null),
        vat: rt.value('pricing.import_vat_pct', null),
        export_fee: rt.value('pricing.export_fee_eur_kwh', null),
        export_compensation_fallback: rt.value('pricing.export_compensation_fallback_eur_kwh', null),
        export_compensation: rt.value('pricing.export_compensation_current_eur_kwh', null)
      };
      return this.pricingTariffSpecs(rt).map(spec => {
        const row = findRow(spec);
        const published = pickBreakdown(spec.id);
        const rowVal = rowValue(row, null);
        const direct = directFacts[spec.id];
        const value = published !== undefined && published !== null ? published : (rowVal !== null ? rowVal : direct);
        const configured = asNumber(value) !== null || (value !== undefined && value !== null && value !== '');
        const pricingConfig=objectFrom(rt.canonicalProduct().configuration?.pricing || {});
        const blockers=new Set(asArray(pricingConfig.blocking_property_ids).map(String));
        const propertyId=String(firstDefined(row?.property_id,row?.property_key,row?.key,'') || '');
        const required=propertyId ? blockers.has(propertyId) : false;
        return { ...spec, required, row, value, configured, writable: !!spec.input && row ? this.isWritableRow(row) : false, pricingMode:this.pricingMode(rt), accountingMode:String(pricingConfig.accounting_mode || '') };
      });
    }
    valuePeriodContext(rt) {
      const selected=String(this.selectedMeteringPeriodId || 'today').toLowerCase();
      const periodId=selected === 'day' ? 'today' : selected;
      const valueProjection=rt.valueProjection(periodId);
      const summary=objectFrom(valueProjection.value || {});
      const label=({today:'Today',week:'This week',month:'This month',year:'This year'})[periodId] || human(periodId);
      const currency='EUR';
      const net=asNumber(summary.net_financial_result_eur);
      const importCost=asNumber(summary.import_cost_eur);
      const exportRevenue=asNumber(summary.export_revenue_eur);
      const netEnergyCost=asNumber(summary.net_energy_cost_eur);
      const accountingReady=summary.available === true;
      const actualResultComplete=summary.actual_complete === true;
      const state=actualResultComplete ? 'OK' : accountingReady ? 'PARTIAL' : 'UNAVAILABLE';
      const stateLabel=actualResultComplete ? 'Available' : accountingReady ? 'Partial' : 'Unavailable';
      const resultCompletenessLabel=actualResultComplete ? 'Actual result complete' : stateLabel;
      const resultScopeLabel=actualResultComplete
        ? 'Comparison and per-asset allocation are not evaluated.'
        : String(summary.reason || 'Financial result is not complete.');
      const interpretation=net !== null
        ? `${label} financial result is ${net >= 0 ? 'positive' : 'negative'}.`
        : `${label} financial result is unavailable.`;
      const attention=actualResultComplete
        ? `Measured import cost and export revenue are complete for ${label.toLowerCase()}.`
        : String(summary.reason || 'Financial calculation is not available yet.');
      return {
        period:summary, periodId, label, state, stateLabel, resultCompletenessLabel, resultScopeLabel,
        actualResultComplete, counterfactualEvaluated:false, attributionEvaluated:false,
        currency, net, importCost, exportRevenue, netEnergyCost,
        savings:null, avoided:null, selfConsumption:null, breakdown:{}, consumers:[],
        interpretation, attention, reason:String(summary.reason || ''),
        tariffs:this.valueTariffRows(rt, {}), accountingReady,
        pricingComplete:objectFrom(rt.canonicalProduct().configuration?.pricing || {}).accounting_configuration_complete === true
      };
    }

    buildMeteringPeriodViewModel(rt) {
      const publishedPeriods = rt.meteringPeriods();
      const defaultPeriods = this.defaultMeteringPeriods();
      const byPeriodId = new Map(defaultPeriods.map(period => [String(period.period_id).toLowerCase(), period]));
      publishedPeriods.forEach(period => {
        const id = String(period.period_id || '').toLowerCase();
        if (id) byPeriodId.set(id, { ...(byPeriodId.get(id) || {}), ...period });
      });
      const periods = [...byPeriodId.values()].sort((a, b) => (asNumber(a.selector_order) || 99) - (asNumber(b.selector_order) || 99));
      const requested = String(this.selectedMeteringPeriodId || rt.value('metering.selected_period','today') || 'today').toLowerCase();
      const periodId = requested === 'day' ? 'today' : requested;
      const period = byPeriodId.get(periodId) || { period_id:periodId, label:this.periodLabel({ period_id:periodId }), graph_support:false, bucket_support:false };
      const rawPeriod=objectFrom(period);
      const summary=objectFrom(rawPeriod.summary);
      const measured=objectFrom(summary.measured);
      const qualityPayload=objectFrom(summary.quality);
      const effectivePeriod={ ...rawPeriod, summary:{ ...summary, measured, quality:qualityPayload } };
      const flexibleLoadRows = this.flexibleLoadMeteringRows(rt, periodId);
      const rows = this.meteringRowsFromPeriod(effectivePeriod);
      const recordsHaveValues = this.meteringPeriodRowsAvailable(rows);
      const summaryHasData = recordsHaveValues || Object.keys(measured).some(key => measured[key] !== null && measured[key] !== undefined);
      const quality = {
        ...qualityPayload,
        health:String(firstDefined(qualityPayload.health,rawPeriod.quality,rawPeriod.measurement_state,'UNAVAILABLE')),
        measurement_state:String(firstDefined(qualityPayload.measurement_state,rawPeriod.measurement_state,rawPeriod.availability,'UNAVAILABLE')),
        user_action_required:asBool(firstDefined(qualityPayload.user_action_required,rawPeriod.user_action_required,rawPeriod.baseline_reset_required,false),false)
      };
      const normalizeMetricKey = value => String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
      const allRows = Object.values(rows).flat().filter(Boolean);
      const metricValue = aliases => {
        const wanted = aliases.map(normalizeMetricKey);
        const row = allRows.find(candidate => {
          const keys = [candidate.metric_key, candidate.semantic_key, candidate.fact_key, candidate.property_key, candidate.key].map(normalizeMetricKey).filter(Boolean);
          return keys.some(key => wanted.some(alias => key === alias || key.endsWith(`_${alias}`)));
        });
        return asNumber(row?.value);
      };
      const health = normalizeMetricKey(firstDefined(quality.health, quality.status, period.health, 'unavailable'));
      const verifiedStates = new Set(['trusted','verified','complete','ok','ready']);
      const verificationStates = new Set(['pending','verification_required','verify','reset_required','untrusted','baseline_untrusted','baseline_required','configuration_required']);
      const partialStates = new Set(['partial','estimated','incomplete']);
      const rowStates=allRows.filter(row=>row.value !== null && row.value !== undefined).map(row=>String(row.status || 'UNKNOWN').toUpperCase());
      const allFieldsTrusted=rowStates.length>0 && rowStates.every(state=>state==='OK');
      const siteTotal=asNumber(measured.site_consumption_kwh);
      const flexibleTotal=asNumber(measured.flexible_loads_energy_in_kwh);
      const impossibleBalance=siteTotal !== null && flexibleTotal !== null &&
        flexibleTotal > siteTotal + 0.2;
      // The period-level 'OK' flag cannot overrule missing field evidence or
      // impossible energy conservation (e.g. 28.6 kWh flexible > 16.6 kWh site).
      const qualityState=impossibleBalance ? 'partial' :
        verifiedStates.has(health) && allFieldsTrusted ? 'verified' :
        verificationStates.has(health) ? 'verification_required' :
        rowStates.length || partialStates.has(health) ? 'partial' : 'unavailable';
      const qualityLabel = impossibleBalance ? 'Inconsistent totals' : qualityState === 'verified' ? 'Verified' : qualityState === 'verification_required' ? 'Verification required' : qualityState === 'partial' ? 'Partial' : 'Unavailable';
      const remediations = rt.meteringRemediationsForPeriod(periodId);
      const label = this.periodLabel(period);
      const remediation = remediations[0] || null;
      const userActionRequired = asBool(firstDefined(quality.user_action_required,effectivePeriod.user_action_required,false),false);
      const command = remediation && userActionRequired ? (remediation.command || rt.meteringResetCommandFor(remediation, periodId)) : null;
      const conclusion = impossibleBalance
        ? {title:`${label} totals need reconciliation`,why:'Flexible Load energy exceeds measured Site Consumption. Do not trust the period totals until the Energy producer resolves this inconsistency.',recommendation:'Inspect physical meters and attribution; do not reset or invent measurements.',tone:'orange'}
        : qualityState === 'verified'
        ? { title:`${label} totals are verified`, why:'These totals are measured and ready to use.', recommendation:'No action is needed.', tone:'green' }
        : qualityState === 'partial'
          ? { title:`${label} totals are partial`, why:'Measured values are available, but the selected period is not yet complete.', recommendation:'Use the available totals with the shown completeness in mind.', tone:'orange' }
          : qualityState === 'verification_required'
            ? { title:`${label} totals need verification`, why:'Measurements exist, but Home Intelligence cannot yet verify the complete period.', recommendation:command ? `Reset ${label.toLowerCase()} once and wait for confirmation.` : 'Wait for Home Intelligence to confirm the measured period.', tone:'orange' }
            : { title:`${label} totals are unavailable`, why:'Reliable measured totals are not currently published for this period.', recommendation:'The totals will appear when measurements become available.', tone:'blue' };
      return {
        periodId, period, periods, label, rows, quality, health, qualityState, qualityLabel, conclusion, command,
        available:this.meteringPeriodRowsAvailable(rows), summaryHasData,
        solar:metricValue(['solar_production_kwh']),
        consumption:metricValue(['site_consumption_kwh']),
        homeConsumption:metricValue(['home_consumption_kwh']),
        gridImport:metricValue(['grid_import_kwh']),
        gridExport:metricValue(['grid_export_kwh']),
        batteryCharge:metricValue(['battery_charge_kwh']),
        batteryDischarge:metricValue(['battery_discharge_kwh']),
        flexibleLoads:metricValue(['flexible_loads_energy_in_kwh']),
        sourceRefs:firstDefined(period.summary?.source_refs, period.source_refs, []), flexibleLoadRows, remediations
      };
    }
    meteringHeaderContext(rt) {
      return this.buildMeteringPeriodViewModel(rt);
    }

    gasModel(rt) {
      const index=rt.canonicalIndex;
      // Only the backend-published gas_meter object owns these facts.
      const rows=index && typeof index.rowsForProperty === 'function' ? index.rowsForProperty('gas.total_m3') : [];
      const candidates=rows.filter(row=>row.logical_object_class==='gas_meter');
      const root=candidates.length===1 ? candidates[0] : null;
      const assetId=String(root?.asset_id || '');
      const owned=(key)=>{
        if (!assetId) return null;
        const matches=(index && typeof index.rowsForProperty === 'function' ? index.rowsForProperty(key) : []).filter(row=>
          row.logical_object_class==='gas_meter' && String(row.asset_id)===assetId);
        return matches.length===1 && matches[0].availability==='AVAILABLE' ? matches[0] : null;
      };
      const total=owned('gas.total_m3');
      const flow=owned('gas.flow_m3_h');
      const totalM3=total ? asNumber(total.value) : null;
      const flowM3h=flow ? asNumber(flow.value) : null;
      const asset=root ? Object.freeze({
        asset_id:assetId,
        asset_type:'gas_meter',
        object_class:'gas_meter',
        display_name:String(root.asset_display_name || assetId),
        integration_domain:String(root.integration_domain || '')
      }) : null;
      return Object.freeze({
        asset,totalM3,flowM3h,
        health:total?.availability || 'UNAVAILABLE',
        source:String(root?.integration_domain || 'Gas meter'),
        totalEntityId:total?.entity_id || null
      });
    }
    gasVolume(value, fallback = '—') {
      const number = asNumber(value);
      return number === null ? fallback : `${number.toLocaleString(undefined,{maximumFractionDigits:3})} m³`;
    }
    gasFlow(value, fallback = '—') {
      const number = asNumber(value);
      return number === null ? fallback : `${number.toLocaleString(undefined,{maximumFractionDigits:3})} m³/h`;
    }
    // Historical charts never infer energy totals from live power. They use only
    // uniquely resolved, available canonical HA numeric sensor entities.
    canonicalEnergyHistorySensor(rt, propertyKey, objectClass) {
      const candidates = (rt.canonicalIndex?.rowsForProperty?.(propertyKey) || [])
        .filter(row => row.logical_object_class === objectClass);
      if (candidates.length !== 1) return '';
      const row = candidates[0];
      const id = String(row?.entity_id || '').trim();
      if (row.availability !== 'AVAILABLE' || !/^sensor\.[a-z0-9_]+$/.test(id)) return '';
      return id;
    }
    energyHistorySection(rt, kind) {
      const definitions = {
        battery: { key:'battery.soc_pct', cls:'battery_system',
          title:'Battery state of charge history',
          description:'Recorded battery state of charge (%), from Home Assistant sensor history.' },
        solar: { key:'solar.power_kw', cls:'solar_production',
          title:'Solar production power history',
          description:'Measured solar power (kW), from Home Assistant sensor history. This is not a produced-energy total.' },
        grid_import: { key:'grid_import.power_kw', cls:'grid_connection',
          title:rhiEnergyT(this._hass,'history.grid_import',{},'Grid import history'),
          description:rhiEnergyT(this._hass,'history.measured_power',{},'Measured power (kW) from Home Assistant history; not a derived energy total.') },
        grid_export: { key:'grid_export.power_kw', cls:'grid_connection',
          title:rhiEnergyT(this._hass,'history.grid_export',{},'Grid export history'),
          description:rhiEnergyT(this._hass,'history.measured_power',{},'Measured power (kW) from Home Assistant history; not a derived energy total.') },
        home: { key:'home_consumption.power_kw', cls:'home_consumption',
          title:rhiEnergyT(this._hass,'history.home',{},'Home consumption history'),
          description:rhiEnergyT(this._hass,'history.measured_power',{},'Measured power (kW) from Home Assistant history; not a derived energy total.') },
        flexible: { key:'flexible_loads.power_kw', cls:'flexible_loads',
          title:rhiEnergyT(this._hass,'history.flexible',{},'Flexible load history'),
          description:rhiEnergyT(this._hass,'history.measured_power',{},'Measured power (kW) from Home Assistant history; not a derived energy total.') }
      };
      const spec = definitions[kind];
      if (!spec) return '';
      const {key,cls,title,description}=spec;
      const entityId = this.canonicalEnergyHistorySensor(rt,key,cls);
      const period = ['day','week','month'].includes(this.selectedEnergyHistoryPeriodId) ? this.selectedEnergyHistoryPeriodId : 'day';
      const controls = entityId ? `<div class="scopeSelector energyHistorySelector" aria-label="${escapeHtml(title)} period">${[['day',rhiEnergyT(this._hass,'common.today',{},'Today')],['week',rhiEnergyT(this._hass,'common.week',{},'Week')],['month',rhiEnergyT(this._hass,'common.month',{},'Month')]].map(([id,label])=>`<button type="button" class="scopeOption ${period===id?'active':''}" data-energy-history-period="${id}" aria-pressed="${period===id?'true':'false'}">${label}</button>`).join('')}</div>` : '';
      const body = entityId
        ? `<div class="rhiUxChartViewport energyHistoryHost" data-energy-history-host data-entity-id="${escapeHtml(entityId)}" data-history-kind="${kind}" data-hours-to-show="${({day:24,week:168,month:720})[period]}"></div>`
        : `<div class="empty compact"><b>${escapeHtml(rhiEnergyT(this._hass,'history.unavailable',{},'Measured history unavailable'))}</b><span>${escapeHtml(rhiEnergyT(this._hass,'history.unavailable_desc',{},'No unique, available canonical Home Assistant sensor is published for this history. No values are estimated.'))}</span></div>`;
      return `<section class="panel rhiUxChartPanel energyHistoryPanel" id="${escapeHtml(kind)}-history"><div class="rhiUxSectionHead rhiUxChartHeader"><div><h2>${escapeHtml(title)}</h2><p>${escapeHtml(description)}</p></div>${controls}</div>${body}</section>`;
    }
    async mountEnergyHistoryGraphs() {
      if (!['solar','battery','flow'].includes(this.view)) return;
      const hosts = this.shadowRoot?.querySelectorAll
        ? [...this.shadowRoot.querySelectorAll('[data-energy-history-host]')]
        : [this.shadowRoot?.querySelector?.('[data-energy-history-host]')];
      for (const host of hosts) {
        if (!host || host.firstElementChild || host.dataset.loading === 'true') continue;
        const entityId = String(host.dataset.entityId || '');
        const hours = Number(host.dataset.hoursToShow);
        const kind = String(host.dataset.historyKind || '');
        const inScope = this.view === kind ||
          (this.view === 'flow' && ['grid_import','grid_export','home','flexible'].includes(kind));
        if (!inScope || !/^sensor\.[a-z0-9_]+$/.test(entityId) || ![24,168,720].includes(hours)) continue;
        host.dataset.loading = 'true';
        try {
          if (typeof window.loadCardHelpers !== 'function') throw new Error('Home Assistant card helpers unavailable');
          const helpers = await window.loadCardHelpers();
          if (!host.isConnected || this.view !== 'flow' && this.view !== kind) continue;
          const card = await helpers.createCardElement({
            type:'history-graph', entities:[entityId],
            hours_to_show:hours, show_names:false
          });
          card.hass = this._hass;
          if (host.isConnected) host.replaceChildren(card);
        } catch (_) {
          if (host.isConnected) host.innerHTML = '<div class="empty compact"><b>History temporarily unavailable</b><span>Home Assistant could not load this sensor history.</span></div>';
        } finally {
          delete host.dataset.loading;
        }
      }
    }

    async mountGasStatisticsGraph() {
      if (this.view !== 'gas') return;
      const host = this.shadowRoot?.querySelector('[data-gas-statistics-host]');
      if (!host || host.firstElementChild || host.dataset.loading === 'true') return;
      const entityId = String(host.dataset.entityId || '');
      if (!entityId) return;
      host.dataset.loading = 'true';
      try {
        if (typeof window.loadCardHelpers !== 'function') throw new Error('Home Assistant card helpers unavailable');
        const helpers = await window.loadCardHelpers();
        if (this.view !== 'gas' || !host.isConnected) return;
        const card = await helpers.createCardElement({
          type:'statistics-graph',
          title:rhiEnergyT(this._hass,'hero.gas.title',{},'Gas'),
          entities:[entityId],
          stat_types:['change'],
          period:'day',
          days_to_show:({week:7,month:30,quarter:90,year:365}[this.selectedGasHorizonId] || 30),
          chart_type:'bar',
          hide_legend:true
        });
        card.hass = this._hass;
        host.replaceChildren(card);
      } catch (error) {
        if (host.isConnected) {
          host.innerHTML = `<div class="empty"><b>${escapeHtml(rhiEnergyT(this._hass,"gas.history_unavailable",{},"Gas history temporarily unavailable"))}</b><span>${escapeHtml(rhiEnergyT(this._hass,"gas.history_unavailable_desc",{},"The meter is available, but Home Assistant could not load the Statistics Graph card."))}</span></div>`;
        }
      } finally {
        delete host.dataset.loading;
      }
    }

    solarTodayMeasurement(rt) {
      // The native Energy metering-period contract is the primary measured
      // daily kWh authority. A live solar kW reading is NOT a day total.
      const periods = rt.meteringPeriods();
      const matches = periods.filter(period => period.period_id === 'today');
      if (matches.length === 1) {
        const period = matches[0];
        const measured = objectFrom(period.summary?.measured);
        const quality = String(firstDefined(period.field_quality?.solar_kwh,
          period.summary?.quality?.field_quality?.solar_kwh, 'UNKNOWN')).toUpperCase();
        const value = asNumber(measured.solar_kwh);
        if (value !== null && value >= 0 && ['OK','PARTIAL'].includes(quality)) {
          return Object.freeze({ value, quality, detail:quality === 'PARTIAL'
            ? 'Partial measured production today' : 'Measured production today' });
        }
      }
      // Native solar-inverter daily energy is independently valid when
      // published; never infer kWh from current kW or forecast remaining.
      const direct = rt.number('solar.energy_today_kwh');
      if (direct !== null && direct >= 0) {
        return Object.freeze({ value:direct, quality:'SOURCE', detail:'Inverter measured production today' });
      }
      return Object.freeze({ value:null, quality:'UNAVAILABLE',
        detail:'Day production meter unavailable' });
    }
    buildPageViewModel(rt, tab) {
      const current = this.currentEnergyModel(rt);
      const solar = current.solar.powerKw;
      const budgetEvidence = rt.canonicalProduct()?.core?.flexible?.fields?.available_power_kw;
      const flexibleLoadBudget = budgetEvidence?.resolved === true ? asNumber(budgetEvidence.value) : null;
      const solarTodayMeasurement = this.solarTodayMeasurement(rt);
      const solarToday = solarTodayMeasurement.value;
      const solarForecast = rt.number('forecast.solar_today_kwh');
      const solarRemaining = rt.number('forecast.solar_remaining_today_kwh');
      const batterySoc = current.battery.socPct;
      const batteryAvailable = current.battery.availableKwh;
      const gridImport = current.grid.importPowerKw;
      const gridExport = current.grid.exportPowerKw;
      const liveConsumption = current.consumption;
      const siteConsumption = liveConsumption.siteConsumptionKw;
      const demand = siteConsumption;
      const demandUnit = 'site consumption now';
      const flexPower = this.flexiblePowerNowKw(rt);
      const flexNeed = this.flexibleNeedKwh(rt);
      const decision = rt.decision();
      const status = this.productStateLabel(decision.status || rt.value('energy_intelligence.status', 'observed'), 'Observed');
      const recommendation = humanReason(decision.recommendation || rt.value('energy_intelligence.recommendation', null), 'Not available');
      const flowValue = current.grid.displayPowerKw;
      const flowState = flowValue === null
        ? 'Grid flow unavailable'
        : current.grid.direction === 'exporting'
          ? 'Exporting surplus'
          : current.grid.direction === 'importing'
            ? 'Importing from grid'
            : current.grid.direction === 'idle'
              ? 'No grid exchange'
              : 'Grid flow unavailable';
      const batteryPower = current.battery.displayPowerKw;
      const batteryState = current.battery.label;
      const selectedContext = this.selectedHorizon(rt.outlookHorizons(), this.selectedOutlookHorizonId);
      const meteringContext = this.meteringHeaderContext(rt);
      const valueContext = this.valuePeriodContext(rt);
      const contextTomorrow = this.isFutureHorizon(selectedContext);
      const contextLabel = contextTomorrow ? 'Tomorrow' : 'Today';
      const contextSupply = objectFrom(selectedContext?.summary?.supply || {});
      const contextDemand = objectFrom(selectedContext?.summary?.demand || {});
      const contextBalance = objectFrom(selectedContext?.summary?.balance || {});
      const contextSolar = asNumber(firstDefined(contextSupply.solar_forecast_kwh, contextSupply.solar_today_kwh, solarForecast));
      const contextRemaining = asNumber(firstDefined(contextSupply.solar_remaining_kwh, contextTomorrow ? null : solarRemaining));
      const contextDemandTotal = asNumber(firstDefined(contextDemand.total_expected_demand_kwh, contextDemand.expected_demand_kwh, flexNeed));
      const contextBalanceTotal = asNumber(firstDefined(contextBalance.balance_kwh, contextBalance.outlook_balance_kwh));
      const contextGridCost = asNumber(firstDefined(contextBalance.expected_grid_cost_eur, contextBalance.grid_cost_eur));
      const contextGridImport = asNumber(firstDefined(contextBalance.expected_grid_import_kwh, contextBalance.grid_import_kwh));
      const gas = this.gasModel(rt);
      const profiles = {
        overview: { image:hbEnergyHeroAsset('overview'), icon:'✦', eyebrow:rhiEnergyT(this._hass,'hero.energy_overview',{},'Energy overview'), title:rhiEnergyT(this._hass,'hero.site_consumption',{},'Site Consumption'), value:fmtKw(demand,'—'), unit:'current site demand', explanation:`${flowState} · ${fmtKw(solar)} solar · ${fmtKw(current.grid.displayPowerKw)} grid`, tone:'blue', metrics:[['☀','Solar now',fmtKw(solar),solar===null?'Unavailable':solar>0.05?'Producing now':'Not producing'],['▣','Home Battery',fmtPct(batterySoc),batteryState],['⚡','Grid',fmtKw(flowValue),current.grid.label],['↗','Solar remaining',fmtKwh(solarRemaining),solarRemaining===null?'Unavailable':'Forecast left today']] },
        outlook: { image:hbEnergyHeroAsset('outlook'), icon:'↗', eyebrow:rhiEnergyT(this._hass,'hero.energy_outlook',{},'Energy outlook'), title:`${contextLabel} outlook`, value:fmtKwh(contextSolar), unit:`solar forecast ${contextLabel.toLowerCase()}`, explanation:human(firstDefined(selectedContext?.summary?.reason, rt.value('energy_intelligence.outlook_reason','Forecast, demand and planning in one view'))), tone:'purple', metrics:[['☀',`${contextLabel} forecast`,fmtKwh(contextSolar),`Expected solar ${contextLabel.toLowerCase()}`],['↗',contextTomorrow?'Expected demand':'Remaining',contextTomorrow?fmtKwh(contextDemandTotal):fmtKwh(contextRemaining),contextTomorrow?'Known demand tomorrow':'Forecast left today'],['⌂','Demand',fmtKwh(contextDemandTotal),'Expected demand'],['✓','Balance',fmtKwh(contextBalanceTotal),'Supply minus demand']] },
        flow: { image:hbEnergyHeroAsset('flow'), icon:'⚡', eyebrow:rhiEnergyT(this._hass,'hero.live_flow',{},'Live energy flow'), title:flowState, value:fmtKw(flowValue), unit:current.grid.direction === 'exporting' ? 'to grid' : current.grid.direction === 'importing' ? 'from grid' : 'grid flow', explanation:`${fmtKw(solar)} solar · ${fmtKw(demand)} demand`, tone:'purple', metrics:[['☀','Solar',fmtKw(solar),'Supplying the home'],['▣','Home Battery',fmtKw(batteryPower),batteryState],['⚡','Grid',fmtKw(flowValue),current.grid.label],['⌂','Demand',fmtKw(demand),'Home consumption']] },
        solar: { image:hbEnergyHeroAsset('solar-generation'), icon:'☀', eyebrow:rhiEnergyT(this._hass,'nav.solar',{},'Solar'), title:solar===null?rhiEnergyT(this._hass,'hero.solar_unavailable',{},'Solar production unavailable'):solar>0.05?rhiEnergyT(this._hass,'hero.generating',{},'Generating now'):rhiEnergyT(this._hass,'hero.not_generating',{},'Not generating'), value:fmtKw(solar), unit:'current production', explanation:`${fmtKwh(solarToday)} today · ${fmtKwh(solarForecast)} forecast`, tone:'orange', metrics:[['↗','Today so far',solarToday===null?'Unavailable':fmtKwh(solarToday),solarTodayMeasurement.detail],['☀','Forecast today',fmtKwh(solarForecast),'Expected total'],['◷','Remaining today',fmtKwh(solarRemaining),'Forecast left'],['⚡','Available for Flexible Loads',fmtKw(flexibleLoadBudget),'Planning budget unavailable']] },
        battery: { image:hbEnergyHeroAsset('battery'), icon:'▣', eyebrow:rhiEnergyT(this._hass,'nav.battery',{},'Home Battery'), title:batteryState, value:fmtPct(batterySoc), unit:`${fmtKwh(batteryAvailable)} available`, explanation:human(rt.value('battery.reason','Storage ready for the energy plan')), tone:'green', metrics:[['▣','State of charge',fmtPct(batterySoc),'Stored capacity'],['↗','Available',fmtKwh(batteryAvailable),'Usable energy'],['↔','Power now',fmtKw(batteryPower),batteryState],['◉','Reserve',fmtPct(this.batteryReservePct(rt)),'Protected minimum']] },
        consumers: { image:hbEnergyHeroAsset('consumers'), icon:'⌂', eyebrow:'Consumers', title:'Managed assets', value:fmtKw(flexPower), unit:'using managed energy now', explanation:`${this.flexibleAssetDomain(rt).summary().participating_count} participating assets · ${this.flexibleAssetDomain(rt).summary().disabled_count} disabled · ${fmtKwh(flexNeed)} need`, tone:'blue', metrics:[['⚡','Flexible power',fmtKw(flexPower),'Using energy now'],['⌂','Energy need',fmtKwh(flexNeed),'Energy still needed'],['☀','Available for Flexible Loads',flexibleLoadBudget===null?rhiEnergyT(this._hass,'common.not_available',{},'Not available'):fmtKw(flexibleLoadBudget),flexibleLoadBudget===null?'Planning budget not published':'Current planning budget'],['◷','Planning',flexibleLoadBudget===null && flexNeed===null?'Incomplete':this.productStateLabel(rt.value('energy_intelligence.planning_state','observed'), 'Observed'),flexibleLoadBudget===null?'Budget not published':'Planning data available']] },
        gas: { image:hbEnergyHeroAsset('gas'), icon:'🔥', eyebrow:rhiEnergyT(this._hass,'nav.gas',{},'Gas'), title:gas.asset ? rhiEnergyT(this._hass,'gas.consumption',{},'Gas consumption') : rhiEnergyT(this._hass,'gas.not_connected',{},'Gas meter not connected'), value:this.gasVolume(gas.totalM3), unit:rhiEnergyT(this._hass,'gas.total_meter',{},'total meter reading'), explanation:gas.asset ? 'Measured gas use, meter health and 30-day history.' : 'Connect a gas meter to start measured consumption history.', tone:'orange', metrics:[['🔥','Flow now',this.gasFlow(gas.flowM3h),gas.flowM3h===null?'Not measured':'Current measured flow'],['◫','Meter total',this.gasVolume(gas.totalM3),gas.totalM3===null?'Not measured':'Cumulative meter reading'],['↺','History',gas.totalEntityId?({week:'7 days',month:'30 days',quarter:'90 days',year:'365 days'}[this.selectedGasHorizonId] || '30 days'):'Not available',gas.totalEntityId?'Daily measured consumption':gas.asset?'Historical statistics not available':'Connect a gas meter'],['✓','Health',gas.asset?human(gas.health):'Not configured',gas.asset?'Gas meter health':'Authoritative source required']] },
        strategies: { image:hbEnergyHeroAsset('strategies'), icon:'◎', eyebrow:rhiEnergyT(this._hass,'hero.settings',{},'Settings'), title:this.productStateLabel(rt.value('energy_intelligence.automation_mode','advice'), 'Advice'), value:String(rt.strategyProfileRows().length), unit:'available profiles', explanation:'Domain-owned settings, configured intent and effective policy', tone:'purple', metrics:[['◎','Mode',this.productStateLabel(rt.value('energy_intelligence.automation_mode','advice'), 'Advice'),'Energy control mode'],['◫','Profiles',String(rt.strategyProfileRows().length),'Available choices'],['✓','Effective',String(rt.effectiveStrategyRows().length),'Applied strategies'],['✦','Decision',this.productStateLabel(decision.product_state || decision.status || 'available', 'Available'),'Product decision state']] },
        'operational-planning': { image:hbEnergyHeroAsset('operational-planning'), icon:'◷', eyebrow:rhiEnergyT(this._hass,'hero.operational_planning',{},'Operational Planning'), title:this.productStateLabel(rt.value('energy_intelligence.planning_state','observed'), 'Observed'), value:fmtKw(flexPower), unit:'managed power now', explanation:'Current flexible-load execution and next actions', tone:'purple', metrics:[['⚡','Flexible power',fmtKw(flexPower),'Managed power now'],['⌂','Energy need',fmtKwh(flexNeed),'Known remaining need'],['◷','Planning',this.productStateLabel(rt.value('energy_intelligence.planning_state','observed'), 'Observed'),'Current operational state'],['◎','Mode',this.productStateLabel(rt.value('energy_intelligence.automation_mode','advice'), 'Advice'),'Energy control mode']] },
        metering: { image:hbEnergyHeroAsset('metering'), icon:'▥', eyebrow:rhiEnergyT(this._hass,'hero.metering',{},'Metering'), title:meteringContext.label, value:meteringContext.solar === null ? 'Unavailable' : fmtKwh(meteringContext.solar), unit:'Solar production', explanation:`Measured energy flows this ${meteringContext.label.toLowerCase()}`, tone:'blue', metrics:[['▥','Consumption',meteringContext.consumption === null ? 'Unavailable' : fmtKwh(meteringContext.consumption),meteringContext.label],['☀','Solar',meteringContext.solar === null ? 'Unavailable' : fmtKwh(meteringContext.solar),meteringContext.label],['↓','Grid import',meteringContext.gridImport === null ? 'Unavailable' : fmtKwh(meteringContext.gridImport),meteringContext.label],['↑','Grid export',meteringContext.gridExport === null ? 'Unavailable' : fmtKwh(meteringContext.gridExport),meteringContext.label]] },
        intelligence: { image:hbEnergyHeroAsset('intelligence'), icon:'✦', eyebrow:rhiEnergyT(this._hass,'hero.home_intelligence',{},'Home Intelligence'), title:status, value:this.productStateLabel(rt.value('energy_intelligence.automation_mode','advice'), 'Advice'), unit:'automation mode', explanation:'Your home energy control center', tone:'orange', metrics:[['✓','Status',status,'Current intelligence state'],['✦','Confidence',this.productStateLabel(decision.confidence || rt.value('energy_intelligence.confidence','unknown'), 'Not available'),'Decision confidence'],['◎','Recommendation',recommendation,'What Home Intelligence advises'],['✦','Decision',this.productStateLabel(decision.product_state || decision.status || 'available', 'Available'),'Product decision state']] },
        retrospective: (() => { const review=this.retrospectiveModel(); return { image:hbEnergyHeroAsset('intelligence'), icon:'↺', eyebrow:rhiEnergyT(this._hass,'hero.energy_retrospective',{},'Energy retrospective'), title:review.rating, value:review.scoreText, unit:'intelligence performance', explanation:review.explanation, tone:'purple', metrics:[['◎','Coverage',review.coverageText,'Measured evidence'],['✦','Confidence',review.confidence,'Assessment confidence'],['↗','Trend',review.trendText,'Compared with previous period'],['✓','Objectives',String(review.kpis.length),'Measured goals']] }; })(),
        value: { image:hbEnergyHeroAsset('value'), icon:'€', eyebrow:rhiEnergyT(this._hass,'hero.energy_value',{},'Energy value'), title:valueContext.label, value:this.valueMoney(valueContext.net,valueContext.currency,valueContext.state), unit:'net financial result', explanation:valueContext.attention, tone:'green', metrics:[['✓','Result',valueContext.resultCompletenessLabel,'Measured site accounting'],['↓','Import cost',this.valueMoney(valueContext.importCost,valueContext.currency,valueContext.state),valueContext.label],['↑','Export revenue',this.valueMoney(valueContext.exportRevenue,valueContext.currency,valueContext.state),valueContext.label],['€','Net energy cost',this.valueMoney(valueContext.netEnergyCost,valueContext.currency,valueContext.state),valueContext.label]] }
      };
      const profileKey = hbEnergyProfileKey(tab);
      const baseProfile = profiles[profileKey] || profiles.overview;
      const p = { ...baseProfile, image: hbEnergyHeroAsset(tab) };
      const badgeKey = tab === 'gas' ? '' : tab === 'solar' ? 'solar.power_kw' : tab === 'battery' ? 'battery.soc_pct' : tab === 'flow' ? 'grid.flow_direction' : tab === 'metering' ? 'metering.integrity_state' : tab === 'value' ? 'value_accounting.state' : 'energy_intelligence.status';
      let rawBadge = badgeKey ? String(this.rowStatus(rt.row(badgeKey)) || '').trim().toLowerCase() : '';
      if (tab === 'metering') rawBadge = String(meteringContext.health || rawBadge).toLowerCase();
      if (tab === 'value') rawBadge = String(valueContext.state || rawBadge).toLowerCase();
      const attentionBadgeByTab = {gas:'Gas meter needs attention',overview:'Overview needs attention',outlook:'Forecast needs attention',flow:'Flow needs attention',solar:'Solar needs attention',battery:'Home Battery needs attention',consumers:'Consumers need attention',strategies:'Strategy needs attention',metering:'Measurements need attention',intelligence:'Guidance needs attention',retrospective:'Review needs evidence',value:'Financial setup needs attention'};
      // R3.70.0: hero availability is based on required tab interfaces, not optional row completeness.
      // Optional fields remain local to their own cards and Diagnostics and may not degrade the whole tab.
      const requiredInterfacesWorking = this.diagnosticSpec(tab)
        .map(spec => this.diagnosticEntity(rt, ...spec))
        .every(row => row.working);
      const explicitAttention = ['fail','error','blocked'].includes(rawBadge);
      let badgeText = requiredInterfacesWorking ? 'Available' : attentionBadgeByTab[tab];
      let badgeTone = requiredInterfacesWorking ? 'ok' : 'attention';
      if (tab === 'gas') {
        const gm = this.gasModel(rt);
        badgeText = !gm.asset ? 'Setup needed' : /ok|ready|available/i.test(gm.health) ? 'Available' : human(gm.health);
        badgeTone = !gm.asset ? 'neutral' : /ok|ready|available/i.test(gm.health) ? 'ok' : 'attention';
      } else if (tab === 'retrospective') {
        const review=this.retrospectiveModel();
        badgeText = review.available ? 'Available' : 'Collecting evidence';
        badgeTone = review.available ? 'ok' : 'neutral';
      } else if (tab === 'value') {
        const valueUnavailable = !valueContext.accountingReady;
        badgeText = valueUnavailable ? valueContext.stateLabel : 'Available';
        badgeTone = valueUnavailable ? 'neutral' : 'ok';
      } else if (tab === 'metering') {
        badgeText = meteringContext.qualityLabel;
        badgeTone = meteringContext.qualityLabel === 'Verified' ? 'ok' : meteringContext.qualityLabel === 'Unavailable' ? 'neutral' : 'attention';
      }
      return { tab, ...p, badgeText, badgeTone, facts:{ solar, flexibleLoadBudget, solarToday, solarForecast, solarRemaining, batterySoc, batteryAvailable, batteryCharge:current.battery.chargePowerKw, batteryDischarge:current.battery.dischargePowerKw, batteryPower, batteryState, gridImport, gridExport, demand, flexPower, flexNeed, flowValue, flowState, status, recommendation }, selectedPeriod: tab === 'metering' ? meteringContext : null, selectedHorizon: tab === 'outlook' ? selectedContext : null, valueContext: tab === 'value' ? valueContext : null };
    }
    tabExperienceHeader(rt, tab, pageViewModel = null) {
      const p = pageViewModel || this.buildPageViewModel(rt, tab);
      const navItem = this.activeNavigationItem();
      const navSection = this.navigationModel().find(section => section.id === this.navSection);
      const semanticTitle = navItem?.title || p.title;
      const semanticDescription = navItem?.description || p.explanation;
      const heroKey = navItem?.id || tab;
      return rhiEnergyPageHeader({
        sectionLabel:navSection?.label || rhiEnergyT(this._hass,'nav.energy',{},'Energy'),
        itemLabel:navItem?.label || p.eyebrow,
        title:semanticTitle,
        description:semanticDescription,
        hero:hbEnergyHeroAsset(heroKey),
        metrics:p.metrics,
        commandActions:this.pageQuickActions(rt, tab),
        tone:p.tone
      });
    }

    pageQuickActions(rt, tab) {
      // Page headers are product-level context, never an arbitrary asset command tray.
      // Asset-scoped commands belong on the corresponding asset card. This prevents
      // ambiguous Start/Stop charging and repeated per-device "Commit" actions.
      const assets = new Map(rt.assets().map(asset => [String(asset.asset_id || ''), asset]));
      const candidates = rt.visibleCommands().filter(command => {
        const target = String(command.target_asset_id || '');
        if (!target) return true;
        const asset = assets.get(target) || {};
        const type = String(asset.asset_type || asset.object_class || '').toLowerCase();
        return type === 'energy_system' || target === 'energy' || target === 'energy_system';
      });
      const bySemantic = new Map();
      for (const command of candidates) {
        const model = createCommandActionModel(command);
        if (!model) continue;
        const labelKey = String(model.label || '').trim().toLowerCase();
        const semantic = `${model.role || 'command'}::${labelKey}`;
        const existing = bySemantic.get(semantic);
        if (!existing || (!existing.enabled && model.enabled)) bySemantic.set(semantic, model);
      }
      return [...bySemantic.values()].slice(0,4).map(model => this.componentActionModelButton(model)).join('');
    }

    coherentCommandModels(models = [], stateHint = '') {
      const normalizedState = String(stateHint || '').toLowerCase();
      const enabled = models.filter(model => model && model.visible && model.enabled);
      const bySemantic = new Map();
      for (const model of enabled) {
        const key = `${model.role || 'command'}::${String(model.label || '').trim().toLowerCase()}`;
        if (!bySemantic.has(key)) bySemantic.set(key, model);
      }
      let rows = [...bySemantic.values()];
      const has = role => rows.some(model => model.role === role);
      const drop = role => { rows = rows.filter(model => model.role !== role); };
      if (has('pause') && has('resume')) {
        if (/paused|suspended|held/.test(normalizedState)) drop('pause');
        else drop('resume');
      }
      if (has('start') && has('stop')) {
        if (/charging|running|active|executing/.test(normalizedState)) drop('start');
        else drop('stop');
      }
      return rows;
    }
    assetQuickActions(rt, assetId, limit = 3, stateHint = '') {
      const id = String(assetId || '');
      if (!id) return '';
      const models = this.coherentCommandModels(rt.commandActionModelsForAsset(id).filter(Boolean), stateHint).slice(0, limit);
      if (!models.length) return '';
      return `<div class="energyAssetQuickActions"><small>${escapeHtml(rhiEnergyT(this._hass,'common.quick_actions',{},'Quick actions'))}</small><div>${models.map(model => this.componentActionModelButton(model)).join('')}</div></div>`;
    }
    measuredAssetPower(asset = {}) {
      return asNumber(firstDefined(asset.actual_power_kw, asset.current_power_kw, asset.power_kw));
    }
    explicitExecutionState(asset = {}) {
      return String(firstDefined(asset.execution_state, asset.operating_state, asset.operation_state, asset.physical_state, '') || '').toLowerCase();
    }
    canonicalOperationalStatus(rt, asset = {}, planning = {}) {
      const id = String(firstDefined(asset.asset_id, asset.flexible_asset_id, asset.target_asset_id, '') || '');
      const actualPowerKw = this.measuredAssetPower(asset);
      const executionState = this.explicitExecutionState(asset);
      const connectionState = String(firstDefined(asset.connection_state, asset.physical_connection_state, asset.assignment_state, '') || '').toLowerCase();
      const plannedTodayKwh = asNumber(firstDefined(planning.planned_today_kwh, planning.today_planned_kwh));
      const explicitException = firstDefined(planning.exception_state, planning.risk_state, planning.plan_conformance_state, asset.exception_state, null);
      const blockedReason = String(firstDefined(planning.operational_blocked_reason, planning.blocked_reason, asset.blocked_reason, '') || '');
      const isCharging = actualPowerKw !== null && actualPowerKw > 0.05;
      const unavailable = /unavailable|offline|disconnected|failed/.test(`${executionState} ${connectionState}`);
      const exceptional = explicitException === null
        ? (/blocked|failed|exception|at.?risk/.test(`${executionState} ${blockedReason}`) ? true : null)
        : /exception|at.?risk|blocked|failed|degraded|mismatch/.test(String(explicitException).toLowerCase());
      return Object.freeze({ id, actualPowerKw, executionState, connectionState, plannedTodayKwh, isCharging, unavailable, exceptional, blockedReason });
    }
    canonicalLiveEnergyBalance(rt) {
      const current = this.currentEnergyModel(rt);
      const consumption = current.consumption;
      const contributors = consumption.flexibleLoadContributors.map(row => {
        const id = String(firstDefined(row.asset_id,row.flexible_asset_id,row.consumer_asset_id,'') || '');
        return Object.freeze({ id, name:firstDefined(row.display_name,rt.assetName(id),human(id)), powerKw:asNumber(firstDefined(row.power_kw,row.actual_power_kw,row.current_power_kw)), raw:row });
      });
      return Object.freeze({
        consumption,
        siteConsumptionKw:consumption.siteConsumptionKw,
        homeConsumptionKw:consumption.homeConsumptionKw,
        flexibleLoadsKw:consumption.flexibleLoadsKw,
        flexible:contributors,
        solarKw:current.solar.powerKw,
        battery:current.battery,
        batteryChargeKw:current.battery.chargePowerKw,
        batteryDischargeKw:current.battery.dischargePowerKw,
        grid:current.grid,
        gridImportKw:current.grid.importPowerKw,
        gridExportKw:current.grid.exportPowerKw
      });
    }
    overviewEnergyRow({ icon = '', label = '', subtitle = '', value = '—', variant = 'normal', progress = null, asset = null } = {}) {
      const progressBar = progress === null ? '' : `<div class="bar"><i style="width:${escapeHtml(progress)}%"></i></div>`;
      const identity = asset ? `<span class="overviewEnergyAssetVisual">${this.assetVisual(asset,{size:'xs',fallbackIcon:icon || this.flexibleAssetIcon(asset)})}</span>` : `<span class="overviewEnergyIcon">${icon}</span>`;
      return `<div class="overviewEnergyRow ${escapeHtml(variant)}">${identity}<div class="overviewEnergyCopy"><b>${escapeHtml(label)}</b><small>${escapeHtml(subtitle)}</small>${progressBar}</div><strong>${escapeHtml(value)}</strong></div>`;
    }
    overview(rt) {
      const pageVm = this.buildPageViewModel(rt, 'overview');
      const compatibility = rt.contractCompatibility();
      if (!compatibility.available && compatibility.reason) {
        return `${this.tabExperienceHeader(rt,'overview',pageVm)}
          <section class="panel energyUnavailableState">
            ${rhiUxState({state:'unavailable',title:rhiEnergyT(this._hass,'common.not_available',{},'Not available'),detail:rhiEnergyT(this._hass,'common.information_missing',{},'This information is not available yet.')})}
          </section>`;
      }
      const d = rt.decision();
      const balanceVm = this.canonicalLiveEnergyBalance(rt);
      const batterySoc = balanceVm.battery.socPct;
      const reasonRaw = firstDefined(objectFrom(d.reason || {}).message, d.reason_label, rt.rawText('energy_intelligence.reason', null));
      const reasonCandidate = reasonRaw ? humanReason(reasonRaw, '') : '';
      const reason = /residual|reconciliation|canonical|bucket|projection|not.?published|completed|unsustainable/i.test(reasonCandidate)
        ? 'Current production, demand and grid exchange are being monitored against the active strategy.'
        : (reasonCandidate || 'Current production, demand and grid exchange are being monitored against the active strategy.');
      const solarRemaining = rt.number('forecast.solar_remaining_today_kwh');
      const reservePct = this.batteryReservePct(rt);
      const sourceRows = [];
      if (balanceVm.solarKw !== null && balanceVm.solarKw > 0.05) sourceRows.push(this.overviewEnergyRow({icon:'☀',label:rhiEnergyT(this._hass,'nav.solar',{},'Solar'),subtitle:rhiEnergyT(this._hass,'overview.producing_now',{},'Producing now'),value:fmtKw(balanceVm.solarKw),progress:this.progress(balanceVm.solarKw)}));
      if (balanceVm.battery.direction === 'out_of_storage' && balanceVm.batteryDischargeKw !== null) sourceRows.push(this.overviewEnergyRow({icon:'▣',label:rhiEnergyT(this._hass,'overview.battery_discharge',{},'Battery Discharge'),subtitle:balanceVm.battery.label,value:fmtKw(balanceVm.batteryDischargeKw),progress:this.progress(balanceVm.batteryDischargeKw)}));
      if (balanceVm.gridImportKw !== null && balanceVm.gridImportKw > 0.05) sourceRows.push(this.overviewEnergyRow({icon:'⚡',label:rhiEnergyT(this._hass,'overview.grid_import',{},'Grid Import'),subtitle:rhiEnergyT(this._hass,'overview.importing',{},'Importing'),value:fmtKw(balanceVm.gridImportKw),progress:this.progress(balanceVm.gridImportKw)}));
      const contributors = balanceVm.flexible.filter(row => row.powerKw !== null && row.powerKw > 0.05);
      const contributorRows = contributors.map(row => this.overviewEnergyRow({icon:this.flexibleAssetIcon(row.raw || {display_name:row.name}),asset:row.raw || null,label:row.name,subtitle:rhiEnergyT(this._hass,'overview.flex_contributor',{},'Flexible Load contributor'),value:fmtKw(row.powerKw,'—'),variant:'child'})).join('');
      const siteConsumptionText = fmtKw(balanceVm.siteConsumptionKw,'—');
      const homeConsumptionSubtitle = balanceVm.homeConsumptionKw === null
        ? (String(balanceVm.consumption.homeStatus || '').toUpperCase() === 'INCOMPLETE' ? 'Unavailable · Flexible Load power incomplete' : 'Household consumption unavailable')
        : rhiEnergyT(this._hass,'overview.home_excludes_storage',{},'Household consumption excluding Flexible Loads and Battery Charge');
      const flexibleLoadsSubtitle = balanceVm.flexibleLoadsKw === null
        ? (String(balanceVm.flexibleStatus || '').toUpperCase() === 'INCOMPLETE' ? 'Measurement incomplete' : 'Measurement unavailable')
        : `${contributors.length} active contributor${contributors.length===1?'':'s'}`;
      const batteryPresent = rt.experiencePresence().battery === true;
      const batteryChargeRow = batteryPresent && balanceVm.battery.direction === 'into_storage'
        && balanceVm.batteryChargeKw !== null && balanceVm.batteryChargeKw > 0.05
        ? `<section class="panel overviewBatteryChargingPanel" data-rhi-battery-charging="separate"
              aria-label="Home Battery Charging"><div class="overviewSectionTitle"><span class="overviewSectionIcon blue">▣</span><div>
              <h2>Home Battery Charging</h2><p>Storage charging is separate from household consumption.</p></div></div>
              ${this.overviewEnergyRow({icon:'↓',label:'Charging',subtitle:'Physical battery charging power',value:fmtKw(balanceVm.batteryChargeKw,'—'),progress:this.progress(balanceVm.batteryChargeKw)})}</section>`
        : '';
      if (balanceVm.grid.direction === 'unknown') sourceRows.push(this.overviewEnergyRow({icon:'⚡',label:rhiEnergyT(this._hass,'overview.grid_flow_unavailable',{},'Grid flow unavailable'),subtitle:rhiEnergyT(this._hass,'overview.grid_flow_reason',{},'Import or export cannot be confirmed'),value:'—',variant:'unavailable'}));
      const gridDirection = balanceVm.grid.label;
      const gridValue = balanceVm.grid.displayPowerKw;
      const balanceComplete = balanceVm.solarKw !== null
        && balanceVm.siteConsumptionKw !== null
        && balanceVm.grid.displayPowerKw !== null
        && (rt.experiencePresence().battery !== true || balanceVm.battery.displayPowerKw !== null);
      const recommendation = balanceComplete
        ? String(firstDefined(d.what_text, d.recommendation_text, d.recommendation, d.summary, 'Monitoring current energy flow') || 'Monitoring current energy flow')
        : 'Energy assessment unavailable';
      const missingDirections = [
        batteryPresent && balanceVm.battery.direction === 'unknown'
          ? rhiEnergyT(this._hass,'overview.battery_flow_reason',{},'Charging or discharging cannot be confirmed') : '',
        balanceVm.grid.direction === 'unknown'
          ? rhiEnergyT(this._hass,'overview.grid_flow_reason',{},'Import or export cannot be confirmed') : ''
      ].filter(Boolean);
      const decisionReason = balanceComplete
        ? reason
        : [rhiEnergyT(this._hass,'overview.balance_incomplete',{},'The current site balance is not verified.'),
           ...missingDirections].join(' ');
      return `${this.tabExperienceHeader(rt,'overview',pageVm)}
        <div class="overviewCoreGrid">
          <section class="panel overviewCorePanel"><div class="overviewSectionTitle"><span class="overviewSectionIcon orange">☀</span><div><h2>${escapeHtml(rhiEnergyT(this._hass,'section.production_supply',{},'Production & supply'))}</h2><p>${escapeHtml(rhiEnergyT(this._hass,'section.production_supply_desc',{},'Energy available to the home now.'))}</p></div></div>${sourceRows.join('') || `<div class="empty compact"><b>Supply unavailable</b><span>Current supply cannot be determined from the available measurements.</span></div>`}</section>
          <section class="panel overviewDecisionPanel overviewHouseHero"><div class="overviewHouseHeroImage"></div><div class="overviewDecisionOverlay"><span class="overviewDecisionLabel">HOME INTELLIGENCE</span><h2>${escapeHtml(recommendation)}</h2><p>${escapeHtml(decisionReason)}</p><div class="overviewDecisionFacts"><div><small>Site Consumption</small><b>${siteConsumptionText}</b></div><div><small>${escapeHtml(rhiEnergyT(this._hass,"solar.grid",{},"Grid"))}</small><b>${escapeHtml(fmtKw(gridValue,'—'))} ${escapeHtml(gridDirection)}</b></div>${rt.experiencePresence().battery === true ? `<div><small>Battery</small><b>${escapeHtml(fmtPct(batterySoc))}</b></div>` : ''}</div></div></section>
          <div class="overviewRightStack"><section class="panel overviewCorePanel"><div class="overviewSectionTitle"><span class="overviewSectionIcon blue">⌂</span><div><h2>${escapeHtml(rhiEnergyT(this._hass,'nav.consumption',{},'Consumption'))}</h2><p>${escapeHtml(rhiEnergyT(this._hass,'section.consumption_desc',{},'Site demand and its active components.'))}</p></div></div>${this.overviewEnergyRow({icon:'⌂',label:'Home Consumption',subtitle:homeConsumptionSubtitle,value:fmtKw(balanceVm.homeConsumptionKw,'—'),progress:this.progress(balanceVm.homeConsumptionKw)})}${rt.experiencePresence().flexible_loads === true ? this.overviewEnergyRow({icon:'⚡',label:'Flexible Loads',subtitle:flexibleLoadsSubtitle,value:fmtKw(balanceVm.flexibleLoadsKw,'—'),variant:'aggregate'}) : ''}${contributorRows}${this.overviewEnergyRow({icon:'',label:'Site Consumption',subtitle:'Total current site demand',value:siteConsumptionText,variant:'total'})}${balanceVm.grid.direction === 'exporting' && balanceVm.grid.exportPowerKw !== null ? this.overviewEnergyRow({icon:'↗',label:'Grid Export',subtitle:'Exporting to grid',value:fmtKw(balanceVm.grid.exportPowerKw),variant:'boundary'}) : ''}</section>${batteryChargeRow}</div>
        </div>
        ${this.overviewExperiencePanel(rt)}`;
    }
    commandForLoad(rt, assetId, role) {
      // Manual flexible-load controls bind only to the public operational
      // command projection. No planning, activity, automatic-readiness or
      // internal resolution fallback is allowed to override button state.
      return rt.commandForAssetRole(assetId, role);
    }
    commandButton(command, label, assetId) { return this.componentActionButton(command, label, assetId); }
    segmentedControl(options, active, attrName, extraClass = '') { return this.componentSegmentedControl(options, active, extraClass); }
    propertyKeyFor(row = {}) { return String(row.key || row.property_key || row.field_key || ''); }
    draftValueForRow(row = {}, fallback = null) {
      const key = this.propertyKeyFor(row);
      return key && Object.prototype.hasOwnProperty.call(this.editDrafts, key) ? this.editDrafts[key] : rowValue(row, fallback);
    }
    clearProfileDrafts(rt, profileId) {
      const profile = rt.strategyProfileFor(profileId);
      const keys = profile
        ? new Set(this.profileEditableRows(rt, profile).map(row => this.propertyKeyFor(row)).filter(Boolean))
        : new Set(Object.keys(this.editDrafts || {}).filter(key => profileId === 'pricing_settings' && String(key).startsWith('pricing.')));
      Object.keys(this.editDrafts || {}).forEach(key => { if (keys.has(key)) delete this.editDrafts[key]; });
    }
    editValueLabel(row, value, fallback = '—') {
      if (value === undefined || value === null || value === '') return fallback;
      const unit = row?.unit || '';
      const n = asNumber(value);
      if (n !== null) return `${n}${unit ? ` ${unit}` : ''}`;
      return `${value}${unit ? ` ${unit}` : ''}`;
    }
    editableNumberControl(row, label, description = '') {
      if (!row || row.missing) return '';
      const value = this.draftValueForRow(row, null);
      const writable = this.isWritableRow(row);
      const meta = this.validationMeta(row);
      const min = meta.min !== undefined ? ` min="${escapeHtml(meta.min)}"` : '';
      const max = meta.max !== undefined ? ` max="${escapeHtml(meta.max)}"` : '';
      const step = meta.step !== undefined ? ` step="${escapeHtml(meta.step)}"` : ' step="0.1"';
      const editor = `<label class="editField"><input type="number" inputmode="decimal" value="${escapeHtml(value ?? '')}" ${min}${max}${step} ${writable ? '' : 'disabled'} data-property-key="${escapeHtml(this.propertyKeyFor(row))}" data-profile-id="${escapeHtml(row.profile_id || '')}" data-field-key="${escapeHtml(row.field_key || '')}" data-strategy-profile-field="${escapeHtml((row.__strategyProfileField || row.contract_role === 'editable_strategy_profile_field') ? 'true' : '')}"><em>${escapeHtml(row.unit || '')}</em></label>`;
      return this.editablePropertyShell({ row, title:label, description, editor, readback:`Current: ${this.editValueLabel(row, rowValue(row, value), '—')}`, className:'numberProperty' });
    }
    editablePropertyFeedback(row) {
      const fb = this.writeFeedbackFor(row);
      if (!fb) return '';
      const labels = { pending:'Changing…', verifying:'Confirming…', accepted:'Updated', rejected:'Change failed' };
      const label = labels[String(fb.state || '').toLowerCase()] || this.productStateLabel(fb.state, 'Updating');
      const reason = fb.reason ? this.userSafeReason(fb.reason,'') : '';
      return `<small class="writeState ${escapeHtml(fb.state || '')}">${escapeHtml(label)}${reason ? ` · ${escapeHtml(reason)}` : ''}</small>`;
    }
    editablePropertyShell({ row, title, description = '', editor = '', readback = '', className = '' } = {}) {
      const writable = this.isWritableRow(row);
      const disabledReason = writable ? '' : this.userSafeReason(row?.editable_reason,'This setting is not currently editable.');
      return `<div class="editableProperty ${escapeHtml(className)} ${writable ? 'writable' : 'readonly'}"><div class="editablePropertyCopy"><span>${escapeHtml(title || row?.display_name || 'Setting')}</span>${description ? `<small>${escapeHtml(description)}</small>` : ''}</div><div class="editablePropertyEditor">${editor}${readback ? `<em class="editablePropertyReadback">${escapeHtml(readback)}</em>` : ''}${this.editablePropertyFeedback(row)}${disabledReason ? `<small class="editablePropertyDisabled">${escapeHtml(disabledReason)}</small>` : ''}</div></div>`;
    }
    editablePropertyControl(row, { title = '', description = '', type = 'number', fallbackValue = null, fallbackOptions = [], immediateWrite = false } = {}) {
      if (!row || row.missing) return '';
      if (type === 'range') return this.editableRangeControl(row, title, fallbackValue, immediateWrite, description);
      if (type === 'select') return this.editableSelectControl(row, title, fallbackValue, fallbackOptions, description);
      if (type === 'toggle') return this.editableToggleControl(row, title, description);
      if (type === 'time') return this.editableTimeControl(row, title, description);
      return this.editableNumberControl(row, title, description);
    }
    editableRangeControl(row, label, fallbackValue = null, immediateWrite = false, description = '') {
      if (!row || row.missing) return '';
      const value = this.draftValueForRow(row, fallbackValue);
      const writable = this.isWritableRow(row);
      const meta = this.validationMeta(row);
      const min = meta.min ?? asNumber(row.min) ?? asNumber(row.minimum) ?? 0;
      const max = meta.max ?? asNumber(row.max) ?? asNumber(row.maximum) ?? Math.max(10, Number(value || 0));
      const step = meta.step ?? asNumber(row.step) ?? 0.1;
      const title = writable ? 'Adjustable setting' : this.userSafeReason(row.editable_reason,'This setting is read-only');
      const unit = row.unit || '';
      const editor = `<label class="sliderField"><div><b data-live-range-value="true">${escapeHtml(this.editValueLabel(row, value, '—'))}</b></div><input type="range" value="${escapeHtml(value ?? '')}" min="${escapeHtml(min)}" max="${escapeHtml(max)}" step="${escapeHtml(step)}" ${writable ? '' : 'disabled'} data-property-key="${escapeHtml(row.key || row.property_key || '')}" data-profile-id="${escapeHtml(row.profile_id || '')}" data-field-key="${escapeHtml(row.field_key || '')}" data-strategy-profile-field="${escapeHtml((row.__strategyProfileField || row.contract_role === 'editable_strategy_profile_field') ? 'true' : '')}" data-property-immediate-write="${immediateWrite ? 'true' : 'false'}" data-range-unit="${escapeHtml(unit)}" title="${escapeHtml(title)}"></label>`;
      return this.editablePropertyShell({ row, title:label, description, editor, readback:`Current: ${this.editValueLabel(row, rowValue(row, value), '—')}`, className:'rangeProperty' });
    }
    editableTimeControl(row, label, description = '') {
      if (!row || row.missing) return '';
      const value = this.draftValueForRow(row, '');
      const writable = this.isWritableRow(row);
      const editor = `<label class="editField"><input type="time" value="${escapeHtml(value ?? '')}" ${writable ? '' : 'disabled'} data-property-key="${escapeHtml(this.propertyKeyFor(row))}" data-profile-id="${escapeHtml(row.profile_id || '')}" data-field-key="${escapeHtml(row.field_key || '')}" data-strategy-profile-field="${escapeHtml((row.__strategyProfileField || row.contract_role === 'editable_strategy_profile_field') ? 'true' : '')}"></label>`;
      return this.editablePropertyShell({ row, title:label, description, editor, readback:`Current: ${this.editValueLabel(row, rowValue(row, value), '—')}`, className:'timeProperty' });
    }
    editableToggleControl(row, label, description = '') {
      if (!row || row.missing) return '';
      const value = asBool(this.draftValueForRow(row, false), false);
      const writable = this.isWritableRow(row);
      const editor = `<label class="toggleField"><input type="checkbox" ${value ? 'checked' : ''} ${writable ? '' : 'disabled'} data-property-key="${escapeHtml(this.propertyKeyFor(row))}" data-profile-id="${escapeHtml(row.profile_id || '')}" data-field-key="${escapeHtml(row.field_key || '')}" data-strategy-profile-field="${escapeHtml((row.__strategyProfileField || row.contract_role === 'editable_strategy_profile_field') ? 'true' : '')}"><b>${escapeHtml(value ? 'On' : 'Off')}</b></label>`;
      return this.editablePropertyShell({ row, title:label, description, editor, readback:`Current: ${value ? 'On' : 'Off'}`, className:'toggleProperty' });
    }
    editableSelectControl(row, label, fallbackValue = '', fallbackOptions = [], description = '') {
      if (!row || row.missing) return '';
      const writable = this.isWritableRow(row);
      const value = this.draftValueForRow(row, fallbackValue);
      const allowed = allowedValuesForRow(row);
      const opts = allowed.length ? allowed.map(v => ({ value:v, label:this.productStateLabel(v, human(v)) })) : fallbackOptions;
      let editor = '';
      if (!opts.length) {
        editor = `<label class="selectField noOptions"><select disabled data-property-key="${escapeHtml(this.propertyKeyFor(row))}"><option>${escapeHtml(value ? this.productStateLabel(value, human(value)) : 'Options unavailable')}</option></select></label>`;
      } else {
        const options = opts.map(option => { const optValue=(option&&typeof option==='object')?(option.value??option.id??option.key??option.label):option; const optLabel=(option&&typeof option==='object')?(option.label??option.name??this.productStateLabel(optValue,human(optValue))):this.productStateLabel(optValue,human(optValue)); const selected=String(optValue).toLowerCase()===String(value??'').toLowerCase()?' selected':''; return `<option value="${escapeHtml(optValue)}"${selected}>${escapeHtml(optLabel)}</option>`; }).join('');
        editor = `<label class="selectField"><select ${writable ? '' : 'disabled'} data-property-key="${escapeHtml(this.propertyKeyFor(row))}" data-profile-id="${escapeHtml(row.profile_id || '')}" data-field-key="${escapeHtml(row.field_key || '')}" data-strategy-profile-field="${escapeHtml((row.__strategyProfileField || row.contract_role === 'editable_strategy_profile_field') ? 'true' : '')}">${options}</select></label>`;
      }
      return this.editablePropertyShell({ row, title:label, description, editor, readback:`Current: ${this.productStateLabel(rowValue(row, value), human(rowValue(row, value), '—'))}`, className:'selectProperty' });
    }
    flexiblePropertyRow(rt, assetId, names) {
      for (const name of names) {
        const direct = rt.editableProperty(`${assetId}.${name}`);
        if (direct) return direct;
      }
      const matches = row => {
        const key = String(row?.property_id || row?.key || row?.property_key || '').toLowerCase();
        return String(row?.asset_id || '').toLowerCase() === String(assetId).toLowerCase()
          && names.some(name => key === `${String(assetId).toLowerCase()}.${name.toLowerCase()}` || key.endsWith(`.${name.toLowerCase()}`));
      };
      const canonical = rt.propertyRows().find(matches) || null;
      return canonical ? { entity_id:rt.contractEntityId(), ...canonical } : { missing:true };
    }
    isDeprecatedTargetEnergyAlias(row) {
      if (!row || row.missing) return false;
      const text = `${row.key || row.property_key || ''} ${row.quality || ''} ${row.source_type || ''} ${row.resolution_mode || ''} ${row.alias_of || ''} ${row.deprecated_alias_of || ''} ${row.migration_role || ''}`.toLowerCase();
      return /deprecated|source_alias|derived_alias|alias/.test(text);
    }
    targetEnergyValue(rt, assetId, sourceRow = {}) {
      const canonical = this.flexiblePropertyRow(rt, assetId, ['energy_to_target_kwh']);
      if (canonical && !canonical.missing) return rowValue(canonical, null);
      const aliases = [this.flexiblePropertyRow(rt, assetId, ['remaining_energy_kwh']), this.flexiblePropertyRow(rt, assetId, ['energy_needed_kwh'])];
      for (const row of aliases) {
        if (row && !row.missing && this.isDeprecatedTargetEnergyAlias(row)) return rowValue(row, null);
      }
      if (sourceRow && sourceRow.energy_to_target_kwh !== undefined) return asNumber(sourceRow.energy_to_target_kwh);
      return null;
    }
    pauseModeControl(rt, assetId) {
      const row = this.flexiblePropertyRow(rt, assetId, ['pause_mode', 'energy_control_hold_state', 'control_hold_state', 'hold_state']);
      if (row && !row.missing) {
        const allowed = allowedValuesForRow(row);
        const options = (allowed.some(v => String(v).toLowerCase() === 'none') || allowed.some(v => String(v).toLowerCase() === 'paused'))
          ? [{ value: 'none', label: rhiEnergyT(this._hass,'common.automatic',{},'Automatic') }, { value: 'paused', label: 'Forced pause' }]
          : [{ value: 'automatic', label: rhiEnergyT(this._hass,'common.automatic',{},'Automatic') }, { value: 'forced', label: rhiEnergyT(this._hass,'common.forced',{},'Forced') }];
        return this.editableSelectControl(row, 'Pause mode', rowValue(row, options[0].value), options);
      }
      const pauseCommand = this.commandForLoad(rt, assetId, 'pause');
      const resumeCommand = this.commandForLoad(rt, assetId, 'resume');
      const runtime = this.runtime();
      const pauseReady = pauseCommand && runtime.commandEnabled(pauseCommand);
      const resumeReady = resumeCommand && runtime.commandEnabled(resumeCommand);
      if (pauseReady || resumeReady) {
        const key = pauseReady ? pauseCommand.command_id : resumeCommand.command_id;
        const title = pauseReady ? 'Pause is handled automatically for this asset' : 'Resume is handled automatically for this asset';
        return `<label class="selectField"><span>${escapeHtml(rhiEnergyT(this._hass,"automation.pause_mode",{},"Pause mode"))}</span><select data-hold-command-select="true" data-command-key="${escapeHtml(key)}" data-target-asset-id="${escapeHtml(assetId)}" title="${escapeHtml(title)}"><option value="automatic">Automatic</option><option value="forced">Forced pause</option></select></label>`;
      }
      return `<label class="selectField"><span>${escapeHtml(rhiEnergyT(this._hass,"automation.pause_mode",{},"Pause mode"))}</span><select disabled title="${escapeHtml(rhiEnergyT(this._hass,"automation.pause_unavailable",{},"Pause mode cannot be changed for this asset"))}"><option>Automatic</option></select></label>`;
    }
    strategySettingsPanel(rt) {
      const wanted = [
        { match: /min.*start.*time|minimum.*start.*time|start.*delay/i, label: rhiEnergyT(this._hass,'strategy.min_start_time',{},'Min start time') },
        { match: /surplus.*start|start.*surplus|minimum.*start.*power|minimum_start_power/i, label: rhiEnergyT(this._hass,'strategy.surplus_start',{},'Surplus start') },
        { match: /min.*stop.*time|minimum.*stop.*time|stop.*delay/i, label: rhiEnergyT(this._hass,'strategy.min_stop_time',{},'Min stop time') },
        { match: /surplus.*stop|stop.*surplus|minimum.*stop.*power/i, label: rhiEnergyT(this._hass,'strategy.surplus_stop',{},'Surplus stop') },
        { match: /max.*start.*attempt|start.*attempt/i, label: rhiEnergyT(this._hass,'strategy.max_start_attempts',{},'Max start attempts') },
        { match: /retry.*delay|cooldown/i, label: rhiEnergyT(this._hass,'strategy.retry_delay',{},'Retry delay') }
      ];
      const editable = rt.editableRows().filter(row => {
        const key = String(row.key || row.property_key || '');
        const asset = String(row.asset_id || '');
        return /consumer_strategy|solar_strategy|planning|flexible|policy|intent/i.test(`${asset}.${key}`);
      });
      const rows = [];
      wanted.forEach(spec => {
        const hit = editable.find(row => spec.match.test(String(row.key || row.property_key || row.display_name || '')) || spec.match.test(String(row.display_name || row.name || '')));
        if (hit && !rows.some(item => String(item.row.key || item.row.property_key) === String(hit.key || hit.property_key))) rows.push({ row: hit, label: spec.label });
      });
      const controls = rows.map(({ row, label }) => {
        const editor = String(row.editor || row.ui_control || row.control || '').toLowerCase();
        if (editor.includes('select') || allowedValuesForRow(row).length) return this.editableSelectControl(row, label);
        return this.editableNumberControl(row, label);
      }).join('');
      return `<div class="strategySettingsRow"><div class="strategySettingsIntro"><b>⚙ ${escapeHtml(rhiEnergyT(this._hass,"strategy.settings",{},"Strategy settings"))}</b><span>${escapeHtml(rhiEnergyT(this._hass,"strategy.settings_desc",{},"Editable planning properties for flexible-load execution."))}</span></div><div class="strategySettingsControls">${controls || `<span class="noStrategySettings">No adjustable strategy settings are available for this asset.</span>`}</div></div>`;
    }
    normalizeEnergyModeValue(value) {
      const text = String(value || '').toLowerCase().trim();
      const map = { off: 'disabled', disabled: 'disabled', recommend: 'advice', recommendation: 'advice', advice: 'advice', automatic: 'automation', automation: 'automation' };
      return map[text] || text || 'disabled';
    }
    automationModeRow(rt) {
      const exactKeys = [
        'energy.operating_mode',
        'energy_intelligence.automation_mode',
        'consumer.automation_mode',
        'energy.automation_mode',
        'automation.mode'
      ];
      const exact = exactKeys.map(key => rt.row(key)).filter(row => row && !row.missing);
      const discovered = rt.propertyRows().filter(row => {
        const key = String(row.key || row.property_key || row.property_id || '').toLowerCase();
        const asset = String(row.asset_id || '').toLowerCase();
        return /(^|\.)(automation_mode|automation\.mode|control_mode)$/.test(key)
          && (!asset || /energy|intelligence|consumer/.test(asset));
      });
      const candidates = [...exact, ...discovered].filter((row, index, all) => {
        const key = String(row.key || row.property_key || row.property_id || '');
        return key && all.findIndex(other => String(other.key || other.property_key || other.property_id || '') === key) === index;
      });
      return candidates.find(row => this.isWritableRow(row)) || candidates[0] || { missing:true };
    }
    automationModeWriteValue(row, normalized) {
      const aliases = {
        disabled: ['disabled','off','none','manual'],
        advice: ['advice','recommend','recommendation','recommended'],
        automation: ['automation','automatic','auto']
      };
      const allowed = allowedValuesForRow(row);
      if (!allowed.length) {
        const canonical = { disabled: 'off', advice: 'recommend', automation: 'automatic' };
        return canonical[normalized] || normalized;
      }
      const wanted = aliases[normalized] || [normalized];
      const hit = allowed.find(value => wanted.includes(String(value).trim().toLowerCase()))
        || allowed.find(value => wanted.includes(human(value,'').trim().toLowerCase()));
      return hit ?? normalized;
    }
    automationModeValue(rt, fallback = 'Advice') {
      const row = this.automationModeRow(rt);
      return row && !row.missing ? rowValue(row, fallback) : fallback;
    }
    automationExecutionPolicy(rt) {
      const policy = objectFrom(rt.canonicalProduct().planning?.execution_policy || {});
      const configuredMode = String(firstDefined(policy.configured_mode, this.automationModeValue(rt, 'advice')) || 'advice').toLowerCase();
      return {
        configuredMode,
        planningEnabled: policy.planning_enabled !== false,
        autonomousExecutionAllowed: policy.autonomous_execution_allowed === true,
        manualPlanExecutionAllowed: policy.manual_plan_execution_allowed === true,
        directManualCommandsAllowed: policy.direct_manual_commands_allowed !== false,
        allocationState: String(firstDefined(policy.allocation_state, configuredMode === 'automatic' ? 'scheduled' : configuredMode === 'advice' ? 'advisory' : 'informational')),
        authority: String(firstDefined(policy.authority, configuredMode === 'automatic' ? 'home_intelligence' : configuredMode === 'advice' ? 'user_approval' : 'none'))
      };
    }
    modeSelector(rt, activeMode) {
      const modeRow = this.automationModeRow(rt);
      const writable = this.isWritableRow(modeRow);
      const active = this.normalizeEnergyModeValue(activeMode);
      const propertyKey = modeRow.key || modeRow.property_key || modeRow.property_id || 'energy_intelligence.automation_mode';
      const opts = [
        { value: 'disabled', label: rhiEnergyT(this._hass,'common.off',{},'Off') },
        { value: 'advice', label: rhiEnergyT(this._hass,'common.advice',{},'Advice') },
        { value: 'automation', label: rhiEnergyT(this._hass,'common.automatic',{},'Automatic') }
      ].map(opt => ({
        ...opt,
        disabled: !writable,
        attrs: {
          'data-mode-value': this.automationModeWriteValue(modeRow, opt.value),
          'data-property-key': propertyKey
        }
      }));
      const explanation = writable ? 'Choose how Home Intelligence manages flexible energy.' : 'Automation mode cannot be changed right now.';
      const editor = `<div class="automationQuickControl">${this.segmentedControl(opts, active, 'mode')}</div>`;
      return this.editablePropertyShell({ row:modeRow, title:rhiEnergyT(this._hass,'automation.mode',{},'Automation mode'), description:explanation, editor, readback:`Current: ${{disabled:'Off',advice:'Recommend',automation:'Automatic'}[active] || 'Not available'}`, className:'automationProperty' });
    }
    automationQuickAction(rt, activeMode, context = 'intelligence') {
      const normalized = this.normalizeEnergyModeValue(activeMode);
      const descriptions = {
        disabled:'Home Intelligence observes but does not start managed devices.',
        advice:'Home Intelligence recommends actions and waits for approval.',
        automation:'Home Intelligence can act within your configured strategies.'
      };
      return `<section class="panel automationQuickAction ${escapeHtml(context)}"><div class="automationQuickCopy"><small>${escapeHtml(rhiEnergyT(this._hass,'automation.quick_action',{},'Quick action'))}</small><h2>${escapeHtml(rhiEnergyT(this._hass,'automation.control',{},'Home Intelligence control'))}</h2><p>${escapeHtml(descriptions[normalized] || descriptions.disabled)}</p></div>${this.modeSelector(rt, activeMode)}</section>`;
    }
    automationQuickInline(rt, activeMode) {
      const modeRow = this.automationModeRow(rt);
      const writable = this.isWritableRow(modeRow);
      const active = this.normalizeEnergyModeValue(activeMode);
      const propertyKey = modeRow.key || modeRow.property_key || modeRow.property_id || 'energy_intelligence.automation_mode';
      const opts = [
        { value: 'disabled', label: rhiEnergyT(this._hass,'common.off',{},'Off') },
        { value: 'advice', label: rhiEnergyT(this._hass,'common.advice',{},'Advice') },
        { value: 'automation', label: rhiEnergyT(this._hass,'common.automatic',{},'Automatic') }
      ].map(opt => ({
        ...opt,
        disabled: !writable,
        attrs: {
          'data-mode-value': this.automationModeWriteValue(modeRow, opt.value),
          'data-property-key': propertyKey
        }
      }));
      const label = writable ? 'Automation' : 'Automation unavailable';
      return `<div class="quickAutomation" aria-label="Automation quick action"><span class="quickAutomationLabel">✧ ${escapeHtml(label)}</span>${this.segmentedControl(opts, active, 'mode', 'compact')}</div>`;
    }
    automationModeSummary(activeMode) {
      const normalized = this.normalizeEnergyModeValue(activeMode);
      const labels = { disabled:'Off', advice:'Advice', automation:'Automatic' };
      const descriptions = { disabled:'Home Intelligence is observing only.', advice:'Home Intelligence recommends actions and waits for your approval.', automation:'Home Intelligence is managing participating assets automatically.' };
      return `<div class="automationModeSummary"><span>Home Intelligence</span><b>${escapeHtml(labels[normalized] || human(activeMode))}</b><em>${escapeHtml(descriptions[normalized] || '')}</em></div>`;
    }
    flexibleAssetIcon(load) {
      const type = `${load?.ux_asset_type || ''} ${load?.asset_type || ''} ${load?.asset_id || ''} ${load?.display_name || ''}`.toLowerCase();
      if (/storage|battery/.test(type)) return '▣';
      if (/vehicle|ev|phev|car|bmw|renault|audi|mercedes/.test(type)) return '🚗';
      if (/heat|pump|hvac/.test(type)) return '♨';
      if (/boiler|water/.test(type)) return '♨';
      if (/plug|socket/.test(type)) return '🔌';
      return '⚡';
    }
    flexibleConnectionLabel(rt, load, id) {
      const availability = String(load.availability_state || rt.value(`${id}.availability_state`, '') || '').toLowerCase();
      const reason = String(load.availability_reason || rt.value(`${id}.availability_reason`, '') || '').toLowerCase();
      if (/not.?connected|disconnected|unplugged|no_connection|charger_not_connected/.test(`${availability} ${reason}`)) return { label: rhiEnergyT(this._hass,'connection.not_connected',{},'Not connected'), tone: 'warn', hint: rhiEnergyT(this._hass,'connection.connect_hint',{},'Connect to enable planning and charging.') };
      if (/disabled|inactive/.test(String(load.lifecycle_status || '').toLowerCase())) return { label: 'Disabled', tone: 'off', hint: rhiEnergyT(this._hass,'connection.disabled_hint',{},'This load is disabled and excluded from planning.') };
      if (/available|connected|ready|active/.test(`${availability} ${reason}`) || load.effective_charger || load.parent_asset_id) return { label: rhiEnergyT(this._hass,'connection.connected',{},'Connected'), tone: 'ok', hint: '' };
      return { label: human(load.availability_state || 'Unknown'), tone: 'neutral', hint: human(load.availability_reason || '') };
    }
    planningDisplayFor(rt, load, id, planning, powerKw, energyNeed) {
      const todayStatus = String(firstDefined(planning.today_status, planning.expected_today_status, '') || '').toLowerCase();
      const todayLabel = String(firstDefined(planning.today_label, planning.what_text, '') || '');
      const whyText = String(firstDefined(planning.why_text, planning.user_reason_label, planning.reason_label, '') || '');
      const plannedToday = asNumber(planning.planned_today_kwh);
      const plannedTomorrow = asNumber(planning.planned_tomorrow_kwh);
      const rawState = String(firstDefined(planning.state, planning.planning_state, todayStatus, '') || '').toLowerCase();
      const operating = String(load.operating_state || rt.value(`${id}.operating_state`, '') || '').toLowerCase();
      const powerActive = (asNumber(powerKw) || 0) > 0.05 || /running|charging|executing/.test(operating);
      const canonical = todayLabel || whyText || todayStatus || plannedToday !== null || plannedTomorrow !== null;
      if (canonical) {
        const status = todayStatus || (plannedToday !== null && plannedToday > 0 ? 'planned_today' : (plannedTomorrow !== null && plannedTomorrow > 0 ? 'planned_later' : 'not_planned_today'));
        const expected = /planned_today|charging_today/.test(status) || (plannedToday !== null && plannedToday > 0)
          ? 'Planned today'
          : /planned_later/.test(status) || (plannedTomorrow !== null && plannedTomorrow > 0)
            ? 'Planned later'
            : /paused/.test(status) ? 'Paused' : /no_charge_needed/.test(status) ? 'No charge needed' : 'Not planned today';
        const state = todayLabel || (plannedToday !== null && plannedToday > 0 ? `${fmtKwh(plannedToday)} planned today` : human(status));
        const tone = /planned today|charging|completed|no charge needed/i.test(`${state} ${expected}`) ? 'ok' : /paused|not planned|waiting|later/i.test(`${state} ${expected}`) ? 'wait' : 'neutral';
        return { state, tone, why: whyText || 'From the current plan', sub: planning.what_text && planning.what_text !== state ? planning.what_text : '', expected, expectedSub: plannedToday !== null ? `${fmtKwh(plannedToday)} planned today` : '' };
      }
      const rawReason = String(planning.reason || planning.blocked_reason || load.availability_reason || rt.value(`${id}.availability_reason`, '') || '').toLowerCase();
      if (powerActive) return { state: 'Charging now', tone: 'ok', why: human(planning.reason || 'Charging now'), sub: '', expected: '—', expectedSub: '' };
      if (/waiting|scheduled|planned/.test(rawState)) return { state: human(rawState), tone: 'wait', why: human(planning.reason || 'Waiting'), sub: '', expected: '—', expectedSub: '' };
      if (/blocked|failed|unavailable/.test(rawState)) return { state: human(rawState), tone: 'warn', why: human(planning.blocked_reason || planning.reason || 'Blocked'), sub: '', expected: '—', expectedSub: '' };
      return { state: planning.state ? human(planning.state) : 'No plan available', tone: 'neutral', why: planning.reason ? human(planning.reason) : '', sub: '', expected: '—', expectedSub: '' };
    }
    etaDisplayFor(planning) {
      // R1.64.0 UX brief: UX must not invent ready-in or infer ETA from energy/power.
      const explicitMinutes = asNumber(planning.eta_minutes ?? planning.eta_to_target_minutes ?? planning.ready_in_minutes ?? planning.estimated_duration_minutes ?? planning.duration_minutes);
      const explicitAt = planning.ready_at || planning.expected_ready_at || planning.target_time || '';
      if (explicitMinutes !== null && Number.isFinite(explicitMinutes) && explicitMinutes >= 0) {
        const total = Math.round(explicitMinutes);
        const h = Math.floor(total / 60);
        const m = total % 60;
        return { main: h > 0 ? `${h}h ${String(m).padStart(2,'0')}m` : `${m}m`, sub: explicitAt ? `≈ ${human(explicitAt)}` : 'Estimated' };
      }
      if (explicitAt) return { main: human(explicitAt), sub: rhiEnergyT(this._hass,'planning.ready_by',{},'Ready by') };
      return { main: '—', sub: '' };
    }
    automationDisplayFor(rt, load, id) {
      const allowed = load.automation?.allowed ?? load.automation_allowed ?? rt.value(`${id}.automation.allowed`, rt.value(`${id}.automation_allowed`, null));
      const blocked = load.automation?.blocked_reason || load.automation_blocked_reason || rt.value(`${id}.automation.blocked_reason`, rt.value(`${id}.automation_blocked_reason`, ''));
      if (allowed === null || allowed === undefined) return { label: human(load.energy_control_mode || 'Advice'), sub: human(blocked || 'Normal priority'), on: !/off|manual|disabled|not automatic/i.test(String(load.energy_control_mode || '')) };
      return { label: asBool(allowed, false) ? 'Automatic' : 'Not automatic', sub: asBool(allowed, false) ? human(load.priority_label || 'Normal priority') : human(blocked || 'Not automatic'), on: asBool(allowed, false) };
    }
    priorityControl(rt, load, id) {
      const row = this.flexiblePropertyRow(rt, id, ['energy_control_priority', 'priority', 'planning_priority']);
      if (row && !row.missing && this.isWritableRow(row)) return this.editableSelectControl(row, 'Priority', rowValue(row, load.priority_label || load.priority || 'normal'), [
        { value: 'high', label: rhiEnergyT(this._hass,'common.high',{},'High') }, { value: 'normal', label: rhiEnergyT(this._hass,'common.normal',{},'Normal') }, { value: 'low', label: rhiEnergyT(this._hass,'common.low',{},'Low') }
      ]);
      return `<div class="readOnlyPriority"><span>${escapeHtml(rhiEnergyT(this._hass,"planning.priority",{},"Priority"))}</span><b>${escapeHtml(human(load.priority_label || load.priority || 'Normal'))}</b></div>`;
    }
    firstPublishedValue(...values) { return firstDefined(...values); }
    genericValueWithUnit(value, unit = '') {
      const n = asNumber(value);
      if (n === null) return human(value, '—');
      const u = String(unit || '').trim();
      if (u === '%') return fmtPct(n);
      if (/kwh/i.test(u)) return fmtKwh(n);
      if (/kw/i.test(u)) return fmtKw(n);
      if (/°|celsius|temperature/i.test(u)) return `${n.toFixed(1)} °C`;
      return `${n % 1 === 0 ? n.toFixed(0) : n.toFixed(1)}${u ? ` ${u}` : ''}`;
    }
    isMeaningfulPrimaryValue(value, options = {}) {
      if (value === undefined || value === null) return false;
      const text = String(value).trim();
      if (!text) return false;
      if (/^(—|-|none|null|undefined|unknown)$/i.test(text)) return false;
      if (/^(00:?00(?::?00)?|0:00:00)$/i.test(text)) return false;
      if (/not published|no .*published|no route|no target|no deadline|grid policy not published|confidence not published|goal not published|no backend/i.test(text)) return false;
      const n = asNumber(value);
      if (n !== null && !options.allowZero && Math.abs(n) < 0.000001) return false;
      return true;
    }
    firstMeaningfulPrimary(options, ...values) {
      for (const value of values) {
        if (this.isMeaningfulPrimaryValue(value, options)) return value;
      }
      return undefined;
    }
    targetSummaryFor(planning = {}, strategy = {}) {
      const unit = this.firstPublishedValue(planning.target_unit, strategy.target_unit, planning.unit, strategy.unit, '');
      const min = this.firstMeaningfulPrimary({}, planning.minimum_target_value, planning.minimum_target, strategy.minimum_target_value, strategy.minimum, strategy.minimum_target);
      const preferred = this.firstMeaningfulPrimary({}, planning.preferred_target_value, planning.preferred_target, strategy.preferred_target_value, strategy.preferred, strategy.preferred_target);
      const max = this.firstMeaningfulPrimary({}, planning.maximum_useful_value, planning.maximum_target, strategy.maximum_useful_value, strategy.maximum, strategy.maximum_target);
      const parts = [];
      if (min !== undefined) parts.push(`min ${this.genericValueWithUnit(min, unit)}`);
      if (preferred !== undefined) parts.push(`preferred ${this.genericValueWithUnit(preferred, unit)}`);
      if (max !== undefined) parts.push(`max ${this.genericValueWithUnit(max, unit)}`);
      return parts.join(' · ');
    }
    routeLabelFor(planning = {}) {
      const route = objectFrom(planning.source_route || {});
      return this.firstMeaningfulPrimary({ allowZero: true }, planning.route_label, planning.selected_route_label, route.route_label, route.label, planning.selected_route, planning.user_summary_label) || '';
    }
    goalContextStrip(rt, load, planning = {}) {
      const id = load.asset_id;
      const strategy = rt.effectiveStrategyFor(id) || {};
      const items = [];
      const goal = this.firstMeaningfulPrimary({ allowZero: true }, planning.goal_label, strategy.goal_label, planning.goal_type, strategy.goal_type);
      const target = this.targetSummaryFor(planning, strategy);
      const deadline = this.firstMeaningfulPrimary({ allowZero: true }, planning.deadline, planning.deadline_time, strategy.deadline, strategy.deadline_time);
      const route = this.routeLabelFor(planning);
      const grid = this.firstMeaningfulPrimary({ allowZero: true }, planning.grid_use_state, strategy.grid_use_policy, strategy.grid_policy);
      const confidence = this.firstMeaningfulPrimary({ allowZero: true }, planning.confidence_state, planning.confidence, strategy.confidence_policy);
      const mode = this.firstMeaningfulPrimary({ allowZero: true }, strategy.mode, strategy.energy_control_mode);
      if (goal !== undefined) items.push(`<div><small>${escapeHtml(rhiEnergyT(this._hass,"planning.goal",{},"Goal"))}</small><b>${escapeHtml(human(goal))}</b></div>`);
      if (target) items.push(`<div><small>${escapeHtml(rhiEnergyT(this._hass,"planning.target",{},"Target"))}</small><b>${escapeHtml(target)}</b></div>`);
      if (deadline !== undefined) items.push(`<div><small>${escapeHtml(rhiEnergyT(this._hass,"planning.deadline",{},"Deadline"))}</small><b>${escapeHtml(human(deadline))}</b></div>`);
      if (route || grid !== undefined) items.push(`<div><small>${escapeHtml(rhiEnergyT(this._hass,"planning.route_grid",{},"Route / grid"))}</small>${route ? `<b>${escapeHtml(human(route))}</b>` : ''}${grid !== undefined ? `<span>${escapeHtml(human(grid))}</span>` : ''}</div>`);
      if (mode !== undefined || confidence !== undefined) items.push(`<div><small>${escapeHtml(rhiEnergyT(this._hass,"planning.mode_confidence",{},"Mode / confidence"))}</small>${mode !== undefined ? `<b>${escapeHtml(human(mode))}</b>` : ''}${confidence !== undefined ? `<span>${escapeHtml(human(confidence))}</span>` : ''}</div>`);
      return items.length ? `<div class="r164GoalContext">${items.join('')}</div>` : '';
    }
    effectiveStrategyCard(rt, strategy) {
      const id = strategy.asset_id || '';
      const target = this.targetSummaryFor({}, strategy);
      return `<div class="effectiveStrategyCard"><div><b>${escapeHtml(rt.assetName(id))}</b><span>${escapeHtml(id)}</span></div><div class="effectiveStrategyFacts">${this.kv('Mode', human(strategy.mode || strategy.energy_control_mode || '—'))}${this.kv('Target', target)}${this.kv('Deadline', human(strategy.deadline || strategy.deadline_time || '—'))}${this.kv('Objective', human(strategy.objective_mode || '—'))}${this.kv('Grid policy', human(strategy.grid_use_policy || strategy.grid_policy || '—'))}${this.kv('Surplus policy', human(strategy.surplus_policy || '—'))}${this.kv('Confidence policy', human(strategy.confidence_policy || '—'))}${this.kv('Stability', human(strategy.stability || '—'))}</div></div>`;
    }
    isStorageFlexibleAsset(load = {}) {
      return /battery|storage/i.test(`${load.ux_asset_type || ''} ${load.asset_type || ''} ${load.flexible_role || ''} ${load.energy_asset_role || ''} ${load.cluster_role || ''}`);
    }
    isDisabledFlexibleAsset(rt, load = {}, planning = {}) {
      const id = String(load.asset_id || load.flexible_asset_id || '');
      const lifecycle = String(firstDefined(load.lifecycle_status, load.lifecycle_state, rt.value(`${id}.lifecycle_status`, ''), rt.value(`${id}.lifecycle_state`, '')) || '').toLowerCase();
      const participation = String(firstDefined(load.participation_state, load.automation_participation, load.planning_participation, '') || '').toLowerCase();
      const explicitEnabled = firstDefined(load.enabled, load.participating, load.automation_enabled, load.planning_enabled);
      const reason = String(firstDefined(load.lifecycle_reason, load.disabled_reason, planning.waiting_reason_code, planning.reason_code, planning.reason, '') || '').toLowerCase();
      return /disabled|excluded|not.participating|inactive.by.user/.test(`${lifecycle} ${participation} ${reason}`)
        || explicitEnabled === false
        || (planning.eligible === false && /disabled|excluded|not.participating/.test(reason));
    }
    disabledFlexibleAssetCard(rt, load = {}, planning = {}) {
      const id = String(load.asset_id || load.flexible_asset_id || load.target_asset_id || '');
      const name = load.display_name || rt.assetName(id) || human(id);
      const explicitReason = firstDefined(load.disabled_reason, load.lifecycle_reason, load.participation_reason, planning.disabled_reason, planning.disabled_reason_code, '');
      const reason = explicitReason ? humanReason(explicitReason, '') : '';
      const sourceAssetPath = rt.sourceAssetNavigation(load);
      const sourceAssetLink = sourceAssetPath
        ? `<button type="button" class="action sourceAssetLink" data-source-asset-nav="${escapeHtml(sourceAssetPath)}">Open source asset</button>`
        : '';
      return `<article class="disabledAssetCompact"><div class="disabledAssetLead">${this.assetVisual(load,{size:'sm',fallbackIcon:this.flexibleAssetIcon(load)})}<div><b>${escapeHtml(name)}</b><span>${escapeHtml(rhiEnergyT(this._hass,"consumer.not_managed",{},"Not managed by Home Intelligence"))}</span>${reason ? `<small>${escapeHtml(reason)}</small>` : ''}${sourceAssetLink}</div></div></article>`;
    }
    operationalLoadCard(rt, load, recommendation, targetId) {
      const id = load.asset_id;
      const actionModels = rt.commandActionModelsForAsset(id).filter(action => ['start','stop','pause','resume'].includes(action.role));
      const enabledActions = actionModels.filter(action => action.visible && action.enabled);
      const unavailableActions = actionModels.filter(action => action.visible && !action.enabled);
      const commandAvailability = actionModels
        .filter(action => action.visible && !action.enabled)
        .map(action => `<span><small>${escapeHtml(action.label || human(action.role))}</small><b>${escapeHtml(humanReason(action.reason, 'Currently unavailable'))}</b></span>`)
        .join('');
      const requestedRow = this.flexiblePropertyRow(rt, id, ['requested_charge_power_kw','requested_power_kw','energy_control_requested_power_kw','target_power_kw','setpoint_power_kw','charge_power_setpoint_kw']);
      const requestedEffectiveRow = this.flexiblePropertyRow(rt,id,['requested_power_kw_effective']);
      const requested = rowValue(requestedRow,null) ?? rowValue(requestedEffectiveRow,null) ?? load.requested_charge_power_kw ?? load.requested_power_kw ?? load.requested_power_kw_effective ?? null;
      const planning = load.energy_planning || rt.planningOutcomeFor(id) || {};
      if (this.isDisabledFlexibleAsset(rt, load, planning)) return this.disabledFlexibleAssetCard(rt, load, planning);
      const powerKw = asNumber(firstDefined(load.actual_power_kw,load.current_power_kw,load.power_kw,null));
      const energyNeed = asNumber(load.energy_to_target_kwh ?? this.targetEnergyValue(rt,id,load));
      const plannedTodayKwh = asNumber(firstDefined(planning.planned_today_kwh,planning.today_planned_kwh,null));
      const connection = this.flexibleConnectionLabel(rt,load,id);
      const planningView = this.planningDisplayFor(rt,load,id,planning,powerKw,energyNeed);
      const explicitState = String(firstDefined(load.operating_state,load.current_status,'') || '');
      const liveState = explicitState ? human(explicitState) : (powerKw === null ? 'Not measured' : powerKw > 0.05 ? 'Active' : 'Idle');
      const nextActionRaw = String(firstDefined(planning.what_text,planning.next_action_label,planning.next_action,'') || '').trim();
      const nextAction = nextActionRaw && !/^none$/i.test(nextActionRaw) ? human(nextActionRaw) : '';
      const reasonRaw = String(firstDefined(planning.why_text,planning.user_reason_label,planning.reason_label,planning.reason,planning.reason_code,'') || '').trim();
      const reason = reasonRaw && !/^(none|no explanation available\.?|no explanation published\.?)$/i.test(reasonRaw) ? humanReason(reasonRaw,'') : '';
      const requestedControl = requestedRow && !requestedRow.missing && this.isWritableRow(requestedRow)
        ? this.editablePropertyControl(requestedRow,{title:rhiEnergyT(this._hass,'control.requested_charge_power',{},'Requested charge power'),description:rhiEnergyT(this._hass,'control.requested_charge_power_desc',{},'Charging power requested from this asset.'),type:'range',fallbackValue:requested,immediateWrite:true})
        : '';
      const priority = this.priorityControl(rt,load,id);
      const configurationBody = [requestedControl,priority].filter(Boolean).join('');
      const configuration = configurationBody
        ? `<details class="energyAssetDisclosure energyAssetConfiguration"><summary>${escapeHtml(rhiEnergyT(this._hass,'common.configuration',{},'Configuration'))}</summary><div class="energyAssetFoldBody">${configurationBody}</div></details>`
        : '';
      const detailsRows = [
        ['Connection',connection.label || 'Unavailable'],
        energyNeed !== null ? ['Energy needed',fmtKwh(energyNeed)] : null,
        plannedTodayKwh !== null ? ['Planned today',fmtKwh(plannedTodayKwh)] : null,
        nextAction ? ['Next action',nextAction] : null,
        reason ? ['Reason',reason] : null
      ].filter(Boolean);
      const details = detailsRows.length
        ? `<details class="energyAssetDisclosure energyAssetDetails"><summary>${escapeHtml(rhiEnergyT(this._hass,'common.details',{},'Details'))}</summary><div class="energyAssetFoldBody energyAssetDetailGrid">${detailsRows.map(([label,value])=>`<span><small>${escapeHtml(label)}</small><b>${escapeHtml(value)}</b></span>`).join('')}</div></details>`
        : '';
      const diagnosticRows = [
        ['Asset id', id],
        ...unavailableActions.map(action=>[`${action.label || human(action.role)} command`,humanReason(action.reason,'Unavailable')]),
        requestedControl ? null : ['Requested charge power',requestedRow && !requestedRow.missing ? (this.userSafeReason(requestedRow.editable_reason,'Read-only')) : 'Not available']
      ].filter(Boolean);
      const diagnostics = `<details class="energyAssetDisclosure energyAssetDiagnostics"><summary>Diagnostics</summary><div class="energyAssetFoldBody energyAssetDiagnosticGrid">${commandAvailability}${diagnosticRows.map(([label,value])=>`<span><small>${escapeHtml(label)}</small><b>${escapeHtml(value)}</b></span>`).join('')}</div></details>`;
      const actions = enabledActions.length
        ? `<div class="energyAssetQuickActions"><small>${escapeHtml(rhiEnergyT(this._hass,"common.quick_actions",{},"Quick actions"))}</small><div>${enabledActions.map(action=>this.componentActionModelButton(action)).join('')}</div></div>`
        : '';
      const keyFacts = [
        energyNeed !== null ? ['Energy needed',fmtKwh(energyNeed)] : null,
        plannedTodayKwh !== null ? ['Planned today',fmtKwh(plannedTodayKwh)] : null,
        requested !== null ? ['Power target',fmtKw(requested,'—')] : null,
        nextAction ? ['Next action',nextAction] : null
      ].filter(Boolean).slice(0,4);
      return `<article class="flexLoadCard compactOperationalLoad">
        <div class="managedAssetHeader"><div class="managedAssetIdentity">${this.assetVisual(load,{size:'sm',fallbackIcon:this.flexibleAssetIcon(load)})}<div><h3>${escapeHtml(load.display_name || human(id))}</h3><span>${escapeHtml(liveState)}${connection.label ? ` · ${escapeHtml(connection.label)}` : ''}</span></div></div><b>${escapeHtml(fmtKw(powerKw,'—'))}</b></div>
        ${keyFacts.length ? `<div class="managedAssetFacts">${keyFacts.map(([label,value])=>`<span><small>${escapeHtml(label)}</small><b>${escapeHtml(value)}</b></span>`).join('')}</div>` : ''}
        ${actions}<div class="energyAssetFoldStack">${configuration}${details}${diagnostics}</div>
      </article>`;
    }

    energyAssetContext(rt, asset = {}) {
      const id = String(firstDefined(asset.asset_id, asset.id, '') || '');
      const context = id && typeof readEnergyAssetContext === 'function'
        ? readEnergyAssetContext(rt.contractGateway(), id)
        : { asset:null, profile:null, publication:null };
      return {
        ...asset,
        ...objectFrom(context.asset || {}),
        // A producer-published visual_ref supplied by the caller is authoritative.
        // Energy object context may enrich the asset, but must never replace
        // Mobility's chosen vehicle/charger appearance with an Energy fallback.
        visual_ref:firstDefined(asset.visual_ref, asset.visualRef, context.asset?.visual_ref, ''),
        profile_id:firstDefined(context.asset?.profile_id, asset.profile_id, ''),
        profile:objectFrom(context.profile || {}),
        publication:objectFrom(context.publication || {})
      };
    }
    energyAssetFacts(rt, asset = {}, limit = 4) {
      const id = String(firstDefined(asset.asset_id, asset.id, '') || '');
      if (!id) return [];
      const projection = rt.assetProjection(id) || {};
      const publishedKeyFacts = (projection.properties || [])
        .filter(row => row?.presentation?.role === 'key' && row?.projection?.resolved === true)
        .map(row => {
          const field = row.projection || {};
          let value = field.display && field.display !== '—' ? String(field.display) : String(field.value ?? '—');
          if (field.unit && value !== '—' && !value.toLowerCase().includes(String(field.unit).toLowerCase())) value += ` ${field.unit}`;
          return {
            key:String(firstDefined(row.property_key,row.property_id,row.key,'') || ''),
            keys:[String(firstDefined(row.property_key,row.property_id,row.key,'') || '')],
            label:String(firstDefined(row.display_name,row.label,human(row.property_key || row.key || 'Property')) || ''),
            value,
            direct:[],
            formatter:'published'
          };
        })
        .filter(row => row.label && row.value !== '—')
        .slice(0, limit);
      if (publishedKeyFacts.length) return publishedKeyFacts;
      const type = this.energyAssetType(asset);
      const fact = (key, label, direct = [], formatter = '') => {
        const keys = Array.isArray(key) ? key : [key];
        return { key:keys[0] || '', keys, label, direct, formatter };
      };
      const byType = {
        battery:[
          fact('battery.soc_pct','State of charge',['battery.soc_pct','soc_pct','battery_soc_pct'],'pct'),
          fact('battery.power_kw','Power now',['battery.power_kw','power_kw','current_power_kw','actual_power_kw'],'kw'),
          fact('battery.available_kwh','Available energy',['battery.available_kwh','available_kwh'],'kwh'),
          fact('battery.capacity_kwh','Capacity',['battery.capacity_kwh','capacity_kwh'],'kwh'),
          fact('battery.state','State',['battery.state','operating_state','state'],'state'),
          fact('battery.temperature_c','Temperature',['battery.temperature_c','temperature_c'],'c')
        ],
        battery_system:[
          fact('battery.soc_pct','State of charge',['battery.soc_pct','soc_pct','battery_soc_pct'],'pct'),
          fact('battery.power_kw','Power now',['battery.power_kw','power_kw','current_power_kw','actual_power_kw'],'kw'),
          fact('battery.available_kwh','Available energy',['battery.available_kwh','available_kwh'],'kwh'),
          fact('battery.capacity_kwh','Capacity',['battery.capacity_kwh','capacity_kwh'],'kwh'),
          fact('battery.reserve_target_pct','Reserve',['battery.reserve_target_pct','reserve_target_pct'],'pct'),
          fact('battery.state','State',['battery.state','operating_state','state'],'state')
        ],
        home_battery_system:[
          fact('battery.soc_pct','State of charge',['battery.soc_pct','soc_pct','battery_soc_pct'],'pct'),
          fact('battery.power_kw','Power now',['battery.power_kw','power_kw','current_power_kw','actual_power_kw'],'kw'),
          fact('battery.available_kwh','Available energy',['battery.available_kwh','available_kwh'],'kwh'),
          fact('battery.capacity_kwh','Capacity',['battery.capacity_kwh','capacity_kwh'],'kwh'),
          fact('battery.reserve_target_pct','Reserve',['battery.reserve_target_pct','reserve_target_pct'],'pct'),
          fact('battery.state','State',['battery.state','operating_state','state'],'state')
        ],
        solar_production:[
          fact('solar.power_kw','Production now',['solar.power_kw','power_kw','current_power_kw'],'kw'),
          fact('solar.energy_today_kwh','Produced today',['solar.energy_today_kwh','energy_today_kwh'],'kwh'),
          fact('solar.capacity_kwp','Installed capacity',['solar.capacity_kwp','capacity_kwp'],'kwp'),
          fact('solar.state','State',['solar.state','operating_state','state'],'state')
        ],
        solar_array:[
          fact('solar.power_kw','Production now',['solar.power_kw','power_kw','current_power_kw'],'kw'),
          fact('solar.energy_today_kwh','Produced today',['solar.energy_today_kwh','energy_today_kwh'],'kwh'),
          fact('solar.capacity_kwp','Installed capacity',['solar.capacity_kwp','capacity_kwp'],'kwp'),
          fact('solar.state','State',['solar.state','operating_state','state'],'state')
        ],
        solar_zone:[
          fact('solar_zone.power_w','Power now',['solar_zone.power_w','power_w'],'w'),
          fact('solar_zone.energy_kwh','Lifetime energy',['solar_zone.energy_kwh','energy_kwh'],'kwh'),
          fact('solar_zone.status','Status',['solar_zone.status','status','operating_state','state'],'state'),
          fact('solar_zone.child_count','Optimizers',['solar_zone.child_count','child_count'],'count'),
          fact('solar_zone.last_measurement','Last measurement',['solar_zone.last_measurement','last_measurement'],'state'),
          fact('solar_zone.voltage_average_v','Average voltage',['solar_zone.voltage_average_v','voltage_average_v'],'v'),
          fact('solar_zone.current_average_a','Average current',['solar_zone.current_average_a','current_average_a'],'a')
        ],
        solar_panel:[
          fact('solar.power_kw','Production now',['solar.power_kw','power_kw','current_power_kw'],'kw'),
          fact('solar.energy_today_kwh','Produced today',['solar.energy_today_kwh','energy_today_kwh'],'kwh'),
          fact('solar.state','State',['solar.state','operating_state','state'],'state')
        ],
        solar_optimizer:[
          fact('solar_optimizer.power_w','Power now',['solar_optimizer.power_w','optimizer.power_w','power_w','current_power_w'],'w'),
          fact('solar_optimizer.energy_kwh','Lifetime energy',['solar_optimizer.energy_kwh','optimizer.energy_kwh','energy_kwh'],'kwh'),
          fact('solar_optimizer.status','Status',['solar_optimizer.status','optimizer.status','status','operating_state','state'],'state'),
          fact('solar_optimizer.last_measurement','Last measurement',['solar_optimizer.last_measurement','optimizer.last_measurement','last_measurement'],'state'),
          fact('solar_optimizer.optimizer_voltage_v','Optimizer voltage',['solar_optimizer.optimizer_voltage_v','optimizer_voltage_v'],'v'),
          fact('solar_optimizer.panel_voltage_v','Panel voltage',['solar_optimizer.panel_voltage_v','panel_voltage_v'],'v'),
          fact('solar_optimizer.current_a','Current',['solar_optimizer.current_a','optimizer.current_a','current_a'],'a'),
          fact('solar_optimizer.temperature_c','Temperature',['solar_optimizer.temperature_c','temperature_c'],'c'),
          fact('solar_optimizer.panel_identity','Panel',['solar_optimizer.panel_identity','panel_identity'],'state')
        ],
        solar_inverter:[
          fact(['solar.power_kw','inverter.power_kw'],'Power now',['solar.power_kw','inverter.power_kw','power_kw','current_power_kw','actual_power_kw'],'kw'),
          fact('inverter.efficiency_pct','Efficiency',['inverter.efficiency_pct','efficiency_pct'],'pct'),
          fact(['inverter.state','operating_state'],'State',['inverter.state','operating_state','state'],'state')
        ],
        inverter:[
          fact('inverter.power_kw','Power now',['inverter.power_kw','power_kw','current_power_kw','actual_power_kw'],'kw'),
          fact('solar.power_kw','Solar power',['solar.power_kw','solar_power_kw'],'kw'),
          fact('inverter.efficiency_pct','Efficiency',['inverter.efficiency_pct','efficiency_pct'],'pct'),
          fact('inverter.state','State',['inverter.state','operating_state','state'],'state')
        ],
        grid_connection:[
          fact('grid.net_power_kw','Grid power',['grid.net_power_kw','net_power_kw','power_kw'],'kw'),
          fact('grid_import.power_kw','Import',['grid_import.power_kw','import_power_kw','grid_import_power_kw'],'kw'),
          fact('grid_export.power_kw','Export',['grid_export.power_kw','export_power_kw','grid_export_power_kw'],'kw'),
          fact('grid.flow_direction','Direction',['grid.flow_direction','flow_direction','direction'],'state')
        ],
        gas_meter:[
          fact('gas.flow_m3_h','Flow now',['gas.flow_m3_h','flow_m3_h'],'m3h'),
          fact('gas.total_m3','Meter total',['gas.total_m3','total_m3'],'m3'),
          fact('gas.state','State',['gas.state','measurement_state','state'],'state')
        ],
        flexible_load:[
          fact(['flexible_load.power_kw','power_kw'],'Power now',['flexible_load.power_kw','power_kw','current_power_kw','actual_power_kw'],'kw'),
          fact(['flexible_load.energy_to_target_kwh','energy_to_target_kwh','energy_needed_kwh','remaining_energy_kwh'],'Energy needed',['flexible_load.energy_to_target_kwh','energy_to_target_kwh','energy_needed_kwh','remaining_energy_kwh'],'kwh'),
          fact(['flexible_load.state','operating_state'],'State',['flexible_load.state','operating_state','state'],'state'),
          fact(['flexible_load.automation_mode','automation_mode'],'Automation',['flexible_load.automation_mode','automation_mode'],'state')
        ],
        flexible_asset:[
          fact(['flexible_load.power_kw','power_kw'],'Power now',['flexible_load.power_kw','power_kw','current_power_kw','actual_power_kw'],'kw'),
          fact(['flexible_load.energy_to_target_kwh','energy_to_target_kwh','energy_needed_kwh','remaining_energy_kwh'],'Energy needed',['flexible_load.energy_to_target_kwh','energy_to_target_kwh','energy_needed_kwh','remaining_energy_kwh'],'kwh'),
          fact(['flexible_load.state','operating_state'],'State',['flexible_load.state','operating_state','state'],'state'),
          fact(['flexible_load.automation_mode','automation_mode'],'Automation',['flexible_load.automation_mode','automation_mode'],'state')
        ],
        consumer:[
          fact('consumer.power_kw','Power now',['consumer.power_kw','power_kw','current_power_kw','actual_power_kw'],'kw'),
          fact('consumer.energy_today_kwh','Energy today',['consumer.energy_today_kwh','energy_today_kwh'],'kwh'),
          fact('consumer.state','State',['consumer.state','operating_state','state'],'state')
        ],
        vehicle:[
          fact('vehicle.power_kw','Charging power',['vehicle.power_kw','charging_power_kw','current_power_kw','actual_power_kw','power_kw'],'kw'),
          fact('vehicle.energy_to_target_kwh','Energy needed',['vehicle.energy_to_target_kwh','energy_to_target_kwh','energy_needed_kwh','remaining_energy_kwh'],'kwh'),
          fact('vehicle.soc_pct','State of charge',['vehicle.soc_pct','soc_pct'],'pct'),
          fact('vehicle.state','State',['vehicle.state','charging_state','operating_state','state'],'state')
        ],
        charger:[
          fact('charger.power_kw','Power now',['charger.power_kw','current_power_kw','actual_power_kw','power_kw'],'kw'),
          fact('charger.requested_power_kw','Requested power',['charger.requested_power_kw','requested_power_kw'],'kw'),
          fact('charger.state','State',['charger.state','connection_state','operating_state','state'],'state')
        ],
        charging_point:[
          fact('charger.power_kw','Power now',['charger.power_kw','current_power_kw','actual_power_kw','power_kw'],'kw'),
          fact('charger.requested_power_kw','Requested power',['charger.requested_power_kw','requested_power_kw'],'kw'),
          fact('charger.state','State',['charger.state','connection_state','operating_state','state'],'state')
        ],
        site_consumption:[
          fact(['site_consumption.power_kw','consumption.power_kw'],'Power now',['site_consumption.power_kw','consumption.power_kw','power_kw','current_power_kw'],'kw'),
          fact(['site_consumption.energy_today_kwh','consumption.energy_today_kwh'],'Energy today',['site_consumption.energy_today_kwh','consumption.energy_today_kwh','energy_today_kwh'],'kwh'),
          fact(['site_consumption.state','consumption.state'],'State',['site_consumption.state','consumption.state','measurement_state','state'],'state')
        ],
        home_consumption:[
          fact(['home_consumption.power_kw','consumption.power_kw'],'Power now',['home_consumption.power_kw','consumption.power_kw','power_kw','current_power_kw'],'kw'),
          fact(['home_consumption.energy_today_kwh','consumption.energy_today_kwh'],'Energy today',['home_consumption.energy_today_kwh','consumption.energy_today_kwh','energy_today_kwh'],'kwh'),
          fact(['home_consumption.state','consumption.state'],'State',['home_consumption.state','consumption.state','measurement_state','state'],'state')
        ],
        backup_interface:[
          fact('backup.power_kw','Power now',['backup.power_kw','power_kw','current_power_kw'],'kw'),
          fact('backup.state','State',['backup.state','operating_state','state'],'state'),
          fact('backup.grid_state','Grid state',['backup.grid_state','grid_state'],'state')
        ],
        energy_system:[
          fact('energy.net_power_kw','Net power',['energy.net_power_kw','net_power_kw','power_kw'],'kw'),
          fact('energy.state','State',['energy.state','operating_state','state'],'state')
        ],
        home_bus:[
          fact('energy.net_power_kw','Net power',['energy.net_power_kw','net_power_kw','power_kw'],'kw'),
          fact('energy.state','State',['energy.state','operating_state','state'],'state')
        ]
      };
      const candidates = byType[type] || [];
      const facts = [];
      const seenLabels = new Set();
      const formatDirect = (value, formatter) => {
        const n = asNumber(value);
        if (formatter === 'kw') return n === null ? human(value,'—') : fmtKw(n);
        if (formatter === 'w') return n === null ? human(value,'—') : `${Math.round(n)} W`;
        if (formatter === 'kwh') return n === null ? human(value,'—') : fmtKwh(n);
        if (formatter === 'pct') return n === null ? human(value,'—') : fmtPct(n);
        if (formatter === 'kwp') return n === null ? human(value,'—') : `${n.toFixed(1)} kWp`;
        if (formatter === 'm3h') return n === null ? human(value,'—') : `${n.toFixed(2)} m³/h`;
        if (formatter === 'm3') return n === null ? human(value,'—') : `${n.toFixed(1)} m³`;
        if (formatter === 'v') return n === null ? human(value,'—') : `${n.toFixed(1)} V`;
        if (formatter === 'a') return n === null ? human(value,'—') : `${n.toFixed(2)} A`;
        if (formatter === 'c') return n === null ? human(value,'—') : `${n.toFixed(1)} °C`;
        if (formatter === 'count') return n === null ? human(value,'—') : String(Math.round(n));
        return human(value,'—');
      };
      for (const spec of candidates) {
        if (seenLabels.has(spec.label)) continue;
        let field = null;
        let usedKey = spec.key;
        for (const key of spec.keys || [spec.key]) {
          const candidate = rt.assetField(id, key);
          if (!field) field = candidate;
          if (candidate?.resolved) { field = candidate; usedKey = key; break; }
        }
        let value = '';
        let status = field?.status || field?.quality || 'AVAILABLE';
        if (field?.resolved) {
          value = field.display && field.display !== '—'
            ? field.display
            : (field.value === null || field.value === undefined ? '' : `${field.value}${field.unit ? ` ${field.unit}` : ''}`);
        }
        if (!value || value === '—') {
          let direct;
          for (const path of spec.direct) {
            const candidate = valueAtPath(asset, path);
            if (candidate !== undefined && candidate !== null && candidate !== '') { direct = candidate; break; }
          }
          if (direct !== undefined) value = formatDirect(direct, spec.formatter);
        }
        if (!value || value === '—') continue;
        seenLabels.add(spec.label);
        facts.push({ label:spec.label, value, status, key:usedKey });
        if (facts.length >= limit) break;
      }
      return facts;
    }

    energyAssetAreaLabel(asset = {}) {
      const raw = firstDefined(
        asset.ha_area_name,
        asset.area_name,
        asset.area_label,
        asset.location_name,
        asset.location,
        ''
      );
      if (typeof raw === 'string') return raw.trim();
      if (raw && typeof raw === 'object') return String(firstDefined(raw.name, raw.label, '') || '').trim();
      return '';
    }

    energyAssetConfigurationDisclosure(rt, asset = {}) {
      const enriched = this.energyAssetContext(rt, asset);
      const id = String(firstDefined(enriched.asset_id,enriched.id,'') || '');
      if (!id) return '';
      const rows = rt.editablePropertyRows().filter(row => {
        const key = String(firstDefined(row.property_id,row.property_key,row.key,'') || '');
        const rowAsset = String(firstDefined(row.asset_id,row.target_asset_id,'') || '');
        if (/^appearance:/.test(key)) return false;
        const belongs = rowAsset === id || key.startsWith(`${id}.`);
        return belongs && row?.presentation?.role === 'configuration';
      });
      if (!rows.length) return '';
      const controls = rows.map(row => {
        const label = firstDefined(row.display_name,row.label,human(row.field_key || row.property_key || row.key || 'Setting'));
        const allowed = allowedValuesForRow(row);
        const value = rowValue(row, null);
        const valueType = String(firstDefined(row.value_type,row.type,typeof value) || '').toLowerCase();
        const editorType = allowed.length ? 'select'
          : valueType === 'boolean' ? 'toggle'
          : (asNumber(firstDefined(row.min,row.minimum,null)) !== null || asNumber(firstDefined(row.max,row.maximum,null)) !== null) ? 'range'
          : 'number';
        return this.editablePropertyControl(row,{title:label,type:editorType,fallbackValue:value,fallbackOptions:allowed});
      }).filter(Boolean).join('');
      return controls ? `<details class="energyAssetDisclosure energyAssetConfiguration"><summary>Configuration</summary><div class="energyAssetFoldBody">${controls}</div></details>` : '';
    }

    energyAssetDetailDisclosure(rt, asset = {}) {
      const enriched = this.energyAssetContext(rt, asset);
      const id = String(firstDefined(enriched.asset_id,enriched.id,'') || '');
      if (!id) return '';
      const profile = objectFrom(enriched.profile || {});
      const projection = rt.assetProjection(id) || {};
      const parentId = this.energyAssetParentId(enriched);
      const parentName = parentId ? String(rt.assetName(parentId) || '').trim() : '';
      const area = this.energyAssetAreaLabel(enriched);
      const rows = [
        area ? ['Area',area] : null,
        parentName ? ['Part of',parentName] : null,
        firstDefined(profile.display_name,profile.label,profile.name,'') ? ['Profile',firstDefined(profile.display_name,profile.label,profile.name,'')] : null
      ].filter(Boolean);
      const properties = (projection?.properties || [])
        .filter(row => row?.presentation?.role === 'detail')
        .map(row => {
          const field = row?.projection || {};
          if (!field.resolved) return null;
          const label = String(firstDefined(row.display_name,row.label,human(row.property_key || row.key || 'Property')) || '');
          if (!label) return null;
          let value = field.display && field.display !== '—' ? String(field.display) : String(field.value ?? '—');
          if (value === '—') return null;
          if (field.unit && !value.toLowerCase().includes(String(field.unit).toLowerCase())) value += ` ${field.unit}`;
          return [label,value];
        }).filter(Boolean);
      const all = [...rows,...properties];
      if (!all.length) return '';
      return `<details class="energyAssetDisclosure energyAssetDetails"><summary>${escapeHtml(rhiEnergyT(this._hass,'common.details',{},'Details'))}</summary><div class="energyAssetFoldBody"><small class="energyAssetPublishedLabel">More information</small><div class="energyAssetDetailGrid">${all.map(([label,value])=>`<span><small>${escapeHtml(label)}</small><b>${escapeHtml(String(value))}</b></span>`).join('')}</div></div></details>`;
    }

    energyAssetDiagnosticsDisclosure(rt, asset = {}) {
      if (this.config?.show_diagnostics !== true) return '';
      const enriched = this.energyAssetContext(rt, asset);
      const id = String(firstDefined(enriched.asset_id,enriched.id,'') || '');
      if (!id) return '';
      const publication = objectFrom(enriched.publication || {});
      const projection = rt.assetProjection(id) || {};
      const lifecycle = objectFrom(projection.lifecycle || {});
      const telemetry = publication.resolution_complete === false ? 'Incomplete'
        : publication.complete === false ? 'Partial'
        : publication.complete === true ? 'Complete' : 'Unknown';
      const source = firstDefined(enriched.integration_domain,enriched.source_domain,enriched.source,'');
      const missing = Array.isArray(publication.missing) ? publication.missing : Array.isArray(publication.missing_fields) ? publication.missing_fields : [];
      const propertyRows = (projection?.properties || [])
        .filter(row => row?.presentation?.role === 'diagnostics')
        .map(row => {
          const field = row?.projection || {};
          const label = String(firstDefined(row.display_name,row.label,human(row.property_key || row.key || 'Property')) || '');
          const value = field.resolved
            ? (field.display && field.display !== '—' ? field.display : firstDefined(field.value,'—'))
            : humanReason(firstDefined(field.reason,row.reason_code,row.resolution?.reason_code,'Unavailable'),'Unavailable');
          return label ? [label,String(value)] : null;
        }).filter(Boolean);
      const rows = [
        ['Asset id',id],
        source ? ['Source', source] : null,
        ['Lifecycle',firstDefined(lifecycle.state,enriched.health,enriched.status,'Unknown')],
        ['Telemetry', telemetry],
        missing.length ? ['Missing publication fields',missing.join(' · ')] : null,
        ...propertyRows
      ].filter(Boolean);
      return `<details class="energyAssetDisclosure energyAssetDiagnostics"><summary>${escapeHtml(rhiEnergyT(this._hass,'common.diagnostics',{},'Diagnostics'))}</summary><div class="energyAssetFoldBody energyAssetDiagnosticGrid">${rows.map(([label,value])=>`<span><small>${escapeHtml(label)}</small><b>${escapeHtml(String(value))}</b></span>`).join('')}</div></details>`;
    }

    energyAppearanceAction(rt, asset = {}) {
      const enriched = this.energyAssetContext(rt, asset);
      const id = String(firstDefined(enriched.asset_id,enriched.id,'') || '');
      const type = this.energyAssetType(enriched);
      const choices = typeof rhiEnergyVisualCatalogForType === 'function' ? rhiEnergyVisualCatalogForType(type) : [];
      if (!id || !choices.length || enriched.appearance?.editable !== true) return '';
      const row = rt.editableProperty(`appearance:${id}:visual_ref`);
      const directWrite = objectFrom(enriched.appearance?.write || {});
      if (!this.isWritableRow(row) && !(directWrite.supported === true && directWrite.operation_id === 'energy.property.write' && directWrite.service === 'rhi_energy.write_property')) return '';
      return `<button type="button" class="energyAppearanceAction" data-energy-visual-open="${escapeHtml(id)}">${escapeHtml(rhiEnergyT(this._hass,'common.appearance',{},'Appearance'))}</button>`;
    }

    energyDeviceStatusCard(rt, asset = {}, roleLabel = '', childrenHtml = '') {
      const enriched = this.energyAssetContext(rt, asset);
      const id = String(firstDefined(enriched.asset_id,enriched.id,'') || '');
      const name = firstDefined(enriched.display_name,enriched.name,rt.assetName(id),human(id));
      const type = String(firstDefined(enriched.asset_type,enriched.object_class,'device') || 'device');
      const facts = this.energyAssetFacts(rt,enriched,5);
      const stateFact = facts.find(row => /^(state|status|direction)$/i.test(String(row.label || ''))) || null;
      const measuredPower = this.measuredAssetPower(enriched);
      const solarLike = /solar|inverter|panel|optimizer/.test(type);
      const fallbackState = solarLike && measuredPower !== null ? (measuredPower > 0.005 ? 'Producing' : 'Idle') : '';
      const primaryState = this.userSafeProductText(stateFact?.value, fallbackState) || fallbackState;
      const area = this.energyAssetAreaLabel(enriched);
      const parentId = this.energyAssetParentId(enriched);
      const parentName = parentId ? String(rt.assetName(parentId) || '').trim() : '';
      const actions = this.assetQuickActions(rt,id,3);
      const keyFacts = facts.filter(row => !/^(state|status)$/i.test(String(row.label || ''))).slice(0,4);
      const identity = rhiUxAssetIdentity({
        eyebrow:roleLabel || human(type),
        title:name,
        subtitle:[area,primaryState].filter(Boolean).join(' · '),
        visual:this.assetVisual(enriched,{size:'lg',fallbackIcon:this.planningAssetIcon(enriched),decorative:false})
      });
      const factGrid = rhiUxAssetFactGrid(
        keyFacts.length
          ? keyFacts.map(row=>({label:row.label,value:row.value}))
          : [{label:'Energy state',value:primaryState || rhiEnergyT(this._hass,'common.not_available',{},'Not available')}]
      );
      const relationship = parentName
        ? rhiUxAssetRelationship({label:rhiEnergyT(this._hass,'relationship.part_of',{},'Part of'),value:parentName})
        : '';
      const configuration = this.energyAssetConfigurationDisclosure(rt,enriched);
      const details = this.energyAssetDetailDisclosure(rt,enriched);
      const diagnostics = this.energyAssetDiagnosticsDisclosure(rt,enriched);
      const children = childrenHtml
        ? `<details class="energyAssetChildrenSibling"${roleLabel === 'Solar inverter' ? ' open' : ''}><summary>${escapeHtml(rhiEnergyT(this._hass,'common.children',{},'Children'))}</summary><div class="energyAssetChildrenStack">${childrenHtml}</div></details>`
        : '';
      return `<div class="energyAssetNode" data-energy-device-type="${escapeHtml(type)}"><article class="energyDeviceCard rhiEnergyCoreAssetCard">
        ${identity}
        ${factGrid}
        ${relationship}
        ${actions}
        <div class="energyAssetFoldStack">${configuration}${details}${diagnostics}</div>
      </article>${children}</div>`;
    }

    energyAssetType(asset = {}) {
      return String(firstDefined(asset.asset_type,asset.object_class,'') || '').trim().toLowerCase();
    }
    energyAssetParentId(asset = {}) {
      return String(firstDefined(asset.parent_asset_id,asset.parent_id,asset.system_asset_id,asset.group_asset_id,asset.array_asset_id,asset.zone_asset_id,'') || '').trim();
    }
    solarHardwareSection(title, description, body, meta = '', anchorId = '') {
      if (!body) return '';
      const anchor = anchorId ? ` id="${escapeHtml(anchorId)}"` : '';
      return `<section class="panel solarHardwareSection"${anchor}><div class="solarHardwareSectionHead"><div><h2>${escapeHtml(title)}</h2><p>${escapeHtml(description)}</p></div>${meta ? `<span>${escapeHtml(meta)}</span>` : ''}</div>${body}</section>`;
    }
    solarModuleCard(rt, panel, optimizers = []) {
      const enriched = this.energyAssetContext(rt,panel);
      const id = String(firstDefined(enriched.asset_id,enriched.id,'') || '');
      const name = firstDefined(enriched.display_name,enriched.name,rt.assetName(id),human(id),'Solar module');
      const area = this.energyAssetAreaLabel(enriched);
      const panelFacts = this.energyAssetFacts(rt,enriched,3);
      const optimizerDetails = optimizers.map(optimizer=>this.energyAssetDetailDisclosure(rt,optimizer)).join('');
      return `<article class="solarModuleCard solarPanelOnlyCard">
        <div class="solarModuleVisual">${this.assetVisual(enriched,{size:'md',fallbackIcon:'☀',decorative:false})}</div>
        <div class="solarModuleBody"><div class="solarModuleHead"><div><small>${escapeHtml(rhiEnergyT(this._hass,"solar.panel",{},"SOLAR PANEL"))}</small><h4>${escapeHtml(name)}</h4>${area ? `<span>${escapeHtml(area)}</span>` : ''}</div><div class="solarModuleHeadActions"><b>Panel</b></div></div>
        <div class="solarModuleFacts">${panelFacts.map(f=>`<span><small>${escapeHtml(f.label)}</small><b>${escapeHtml(f.value)}</b></span>`).join('') || `<span><small>${escapeHtml(rhiEnergyT(this._hass,'common.status',{},'Status'))}</small><b>${escapeHtml(rhiEnergyT(this._hass,'solar.panel_available',{},'Panel available'))}</b></span>`}</div>
        ${this.energyAssetDetailDisclosure(rt,enriched)}
        ${optimizerDetails ? `<details class="solarTopologyDetails"><summary>Related optimizer details</summary>${optimizerDetails}</details>` : ''}
        </div>
      </article>`;
    }
    solarOptimizerPrimaryCard(rt, optimizer, linkedPanel = null) {
      const enriched = this.energyAssetContext(rt,optimizer);
      const id = String(firstDefined(enriched.asset_id,enriched.id,'') || '');
      const name = firstDefined(enriched.display_name,enriched.name,rt.assetName(id),human(id),'Power optimizer');
      const area = this.energyAssetAreaLabel(enriched);
      const allFacts = this.energyAssetFacts(rt,enriched,12);
      const preferred = ['Power now','Lifetime energy','Status'];
      const seen = new Set();
      const primaryFacts = allFacts.filter(fact => {
        if (!preferred.includes(fact.label) || seen.has(fact.label)) return false;
        seen.add(fact.label);
        return true;
      }).slice(0,3);
      const projection = id ? rt.assetProjection(id) : null;
      const lifecycle = String(firstDefined(projection?.lifecycle?.state,enriched.health,enriched.status,'') || '');
      const unavailable = /unavailable|offline|failed/i.test(String(firstDefined(enriched.availability_state,enriched.connection_state,lifecycle,'')));
      const telemetryAvailable = primaryFacts.length > 0;
      const statusLabel = unavailable ? 'Unavailable' : lifecycle && !/unknown/i.test(lifecycle) ? human(lifecycle) : 'Available';
      const parentId = this.energyAssetParentId(enriched);
      const parentName = parentId ? String(rt.assetName(parentId) || '').trim() : '';
      const panelId = linkedPanel ? String(firstDefined(linkedPanel.asset_id,linkedPanel.id,'') || '') : '';
      const panelName = panelId ? String(firstDefined(linkedPanel.display_name,linkedPanel.name,rt.assetName(panelId),human(panelId)) || '').trim() : '';
      const relationship = panelName
        ? `<span class="solarOptimizerRelation"><small>${escapeHtml(rhiEnergyT(this._hass,"solar.panel_identity",{},"Panel identity"))}</small><b>${escapeHtml(panelName)}</b></span>`
        : parentName
          ? `<span class="solarOptimizerRelation"><small>${escapeHtml(rhiEnergyT(this._hass,"relationship.part_of",{},"Part of"))}</small><b>${escapeHtml(parentName)}</b></span>`
          : '';
      const facts = primaryFacts.length
        ? primaryFacts.map(f=>`<span><small>${escapeHtml(f.label)}</small><b>${escapeHtml(f.value)}</b></span>`).join('')
        : `<span><small>${escapeHtml(rhiEnergyT(this._hass,'solar.measurements',{},'Measurements'))}</small><b>${escapeHtml(rhiEnergyT(this._hass,'common.not_available',{},'Not available'))}</b></span>`;
      const panelDetails = linkedPanel ? this.energyAssetDetailDisclosure(rt,this.energyAssetContext(rt,linkedPanel)) : '';
      return `<article class="solarModuleCard solarOptimizerPrimaryCard">
        <div class="solarModuleVisual">${this.assetVisual(enriched,{size:'md',fallbackIcon:'☀',decorative:false})}</div>
        <div class="solarModuleBody"><div class="solarModuleHead"><div><small>${escapeHtml(rhiEnergyT(this._hass,"solar.optimizer_panel",{},"OPTIMIZER / PANEL"))}</small><h4>${escapeHtml(name)}</h4>${area ? `<span>${escapeHtml(area)}</span>` : ''}</div><div class="solarModuleHeadActions"><b>${escapeHtml(statusLabel)}</b></div></div>
        <div class="solarModuleFacts">${facts}</div>
        ${relationship}
        ${!telemetryAvailable && !unavailable ? `<small class="solarOptimizerHint">${escapeHtml(rhiEnergyT(this._hass,'solar.measurements_unavailable',{},'Energy measurements are not available right now; the optimizer remains part of the solar system.'))}</small>` : ''}
        ${this.energyAssetDetailDisclosure(rt,enriched)}
        ${panelDetails ? `<details class="solarTopologyDetails"><summary>Panel details</summary>${panelDetails}</details>` : ''}
        </div>
      </article>`;
    }

    solarProductionRepresentative(rt) {
      // Presentation-only representative artwork. Solar Production stays a
      // logical aggregate and never receives a physical asset visual_ref.
      const resolved = typeof resolveEnergyVisualRef === 'function'
        ? resolveEnergyVisualRef('energy.logical.solar_zone.generic', rt.visualRegistry(), 'card')
        : null;
      return `<div class="solarProductionRepresentative" aria-label="Solar zone representative image">${resolved?.url ? `<img src="${escapeHtml(resolved.url)}" alt="Solar panel zone" style="filter:${escapeHtml(resolved.filter || 'none')}">` : '<span>☀</span>'}</div>`;
    }

    solarStringLink(rt, asset, childPanels = [], childOptimizers = []) {
      const enriched = this.energyAssetContext(rt, asset);
      const id = String(firstDefined(enriched.asset_id,enriched.id,'') || '');
      const name = firstDefined(enriched.display_name,enriched.name,rt.assetName(id),human(id),'Solar string');
      const facts = this.energyAssetFacts(rt,enriched,8);
      const power = facts.find(fact => /^(Power now|Production now)$/i.test(String(fact.label || ''))) || null;
      const panelById = new Map(childPanels.map(panel => [String(firstDefined(panel.asset_id,panel.id,'') || ''),panel]));
      const optimizerCards = childOptimizers.map(optimizer => {
        const linkedPanel = panelById.get(this.energyAssetParentId(optimizer)) || null;
        return this.solarOptimizerPrimaryCard(rt,optimizer,linkedPanel);
      }).join('');
      const solarPanelOnlyGrid = childPanels
        .filter(panel => !childOptimizers.some(optimizer => this.energyAssetParentId(optimizer) === String(firstDefined(panel.asset_id,panel.id,'') || '')))
        .map(panel => this.solarModuleCard(rt,panel,[]))
        .join('');
      const children = optimizerCards || solarPanelOnlyGrid
        ? `<details class="energyAssetChildrenSibling"><summary>Children · ${childOptimizers.length + childPanels.length}</summary><div class="energyAssetChildrenStack solarModuleGrid">${optimizerCards}${solarPanelOnlyGrid}</div></details>`
        : '';
      return `<div class="energyAssetNode solarStringNode" data-solar-string="${escapeHtml(id)}"><article class="solarStringLink">
        <div class="solarStringSummary">
          <div class="solarStringVisual">${this.assetVisual(enriched,{size:'sm',fallbackIcon:'☀',decorative:false})}</div>
          <span><small>${escapeHtml(rhiEnergyT(this._hass,"solar.zone_string",{},"SOLAR ZONE / STRING"))}</small><b>${escapeHtml(name)}</b></span>
          ${power ? `<span><small>${escapeHtml(rhiEnergyT(this._hass,"common.producing",{},"Producing"))}</small><b>${escapeHtml(power.value)}</b></span>` : ''}
        </div>
        <div class="energyAssetFoldStack">${this.energyAssetConfigurationDisclosure(rt,enriched)}${this.energyAssetDetailDisclosure(rt,enriched)}${this.energyAssetDiagnosticsDisclosure(rt,enriched)}</div>
      </article>${children}</div>`;
    }
    solarInverterCard(rt, inverter, strings = [], panelsFor = () => [], optimizersFor = () => []) {
      const inverterId = String(firstDefined(inverter.asset_id,inverter.id,'') || '');
      const children = strings.map(string => this.solarStringLink(rt,string,panelsFor(string),optimizersFor(string,panelsFor(string)))).join('');
      return `<div class="solarInverterCard" data-solar-inverter="${escapeHtml(inverterId)}">${this.energyDeviceStatusCard(rt,inverter,'Solar inverter',children)}</div>`;
    }
    solarInverterSystem(rt, inverters = [], stringsForInverter = () => [], panelsFor = () => [], optimizersFor = () => [], unresolvedStrings = []) {
      if (!inverters.length && !unresolvedStrings.length) return '';
      const inverterCards = inverters.length
        ? `<div class="solarInverterGrid">${inverters.map(asset=>this.solarInverterCard(rt,asset,stringsForInverter(asset),panelsFor,optimizersFor)).join('')}</div>`
        : '';
      const unresolved = unresolvedStrings.length
        ? `<details class="solarTopologyDiagnostics"><summary>Topology diagnostics · ${unresolvedStrings.length} unresolved string${unresolvedStrings.length===1?'':'s'}</summary><p>The backend has not yet published an authoritative inverter parent for these strings. Home Intelligence does not guess the relationship.</p><div class="solarStringList">${unresolvedStrings.map(array=>this.solarStringLink(rt,array,panelsFor(array),optimizersFor(array,panelsFor(array)))).join('')}</div></details>`
        : '';
      return `<div class="solarProductionChildren" id="solar-inverter-detail">${inverterCards}${unresolved}</div>`;
    }
    homeBatteryAggregateCard(rt, system = null) {
      const battery = this.currentEnergyModel(rt).battery;
      const enriched = system ? this.energyAssetContext(rt, system) : {};
      const name = firstDefined(enriched.display_name,enriched.name,'Home Battery System');
      const identity = rhiUxAssetIdentity({
        eyebrow:rhiEnergyT(this._hass,'battery.system',{},'Battery system'),
        title:name,
        subtitle:battery.label || rhiEnergyT(this._hass,'common.not_available',{},'Not available'),
        visual:system ? this.assetVisual(enriched,{size:'lg',fallbackIcon:'▣',decorative:false}) : ''
      });
      const factGrid = rhiUxAssetFactGrid([
        {label:rhiEnergyT(this._hass,'battery.power_now',{},'Power now'),value:fmtKw(battery.displayPowerKw,'—')},
        {label:rhiEnergyT(this._hass,'battery.soc',{},'State of charge'),value:fmtPct(battery.socPct)},
        {label:rhiEnergyT(this._hass,'battery.capacity',{},'Capacity'),value:fmtKwh(battery.capacityKwh)},
        {label:rhiEnergyT(this._hass,'battery.available_energy',{},'Available energy'),value:fmtKwh(battery.availableKwh)}
      ]);
      const folds = system
        ? `<div class="energyAssetFoldStack">${this.energyAssetConfigurationDisclosure(rt,enriched)}${this.energyAssetDetailDisclosure(rt,enriched)}${this.energyAssetDiagnosticsDisclosure(rt,enriched)}</div>`
        : '';
      return `<div class="energyAssetNode" data-current-energy-projection="battery"><article class="energyDeviceCard rhiEnergyCoreAssetCard">${identity}${factGrid}${folds}</article></div>`;
    }

    solarBatterySystem(rt, systems = [], batteries = []) {
      if (!systems.length && !batteries.length) return '';
      const system = systems[0] || null;
      const head = this.homeBatteryAggregateCard(rt, system);
      const children = batteries.length ? `<div class="solarChildGrid">${batteries.map(asset=>this.batteryChildCard(rt,String(firstDefined(asset.asset_id,asset.id,'') || ''))).join('')}</div>` : '';
      return this.solarHardwareSection(
        'Home Battery',
        'Storage system with its physical batteries.',
        head+children,
        `${batteries.length} batter${batteries.length===1?'y':'ies'}`,
        'solar-battery-detail'
      );
    }

    solarHardwareExperience(rt) {
      const assets = rt.assets().map(asset=>this.energyAssetContext(rt,asset));
      const production = assets.filter(asset=>this.energyAssetType(asset)==='solar_production');
      const arrays = assets
        .filter(asset=>['solar_array','solar_zone'].includes(this.energyAssetType(asset)))
        .sort((left,right) => {
          const leftName = String(firstDefined(left.display_name,left.name,rt.assetName(String(firstDefined(left.asset_id,left.id,'')||'')),'') || '');
          const rightName = String(firstDefined(right.display_name,right.name,rt.assetName(String(firstDefined(right.asset_id,right.id,'')||'')),'') || '');
          return leftName.localeCompare(rightName, undefined, { sensitivity:'base', numeric:true });
        });
      const panels = assets.filter(asset=>this.energyAssetType(asset)==='solar_panel');
      const inverters = assets.filter(asset=>this.energyAssetType(asset)==='solar_inverter');
      const systems = assets.filter(asset=>['battery_system','home_battery_system'].includes(this.energyAssetType(asset)));
      const batteries = assets.filter(asset=>this.energyAssetType(asset)==='battery');
      const optimizers = assets.filter(asset=>this.energyAssetType(asset)==='solar_optimizer');
      const arrayById = new Map(arrays.map(asset => [String(firstDefined(asset.asset_id,asset.id,'') || ''),asset]));
      const inverterIds = new Set(inverters.map(asset => String(firstDefined(asset.asset_id,asset.id,'') || '')));

      const panelsFor = array => {
        const id = String(firstDefined(array.asset_id,array.id,'') || '');
        return panels.filter(panel => this.energyAssetParentId(panel) === id);
      };
      const optimizersFor = (array, childPanels = []) => {
        const ids = new Set([String(firstDefined(array.asset_id,array.id,'') || ''), ...childPanels.map(panel=>String(firstDefined(panel.asset_id,panel.id,'') || ''))]);
        return optimizers.filter(optimizer => ids.has(this.energyAssetParentId(optimizer)));
      };
      const canonicalInverterFor = array => {
        let parentId = this.energyAssetParentId(array);
        const seen = new Set();
        for (let depth = 0; parentId && depth < 8 && !seen.has(parentId); depth += 1) {
          if (inverterIds.has(parentId)) return parentId;
          seen.add(parentId);
          const parentArray = arrayById.get(parentId);
          if (!parentArray) return '';
          parentId = this.energyAssetParentId(parentArray);
        }
        return '';
      };
      const stringsForInverter = inverter => {
        const inverterId = String(firstDefined(inverter.asset_id,inverter.id,'') || '');
        return arrays.filter(array => canonicalInverterFor(array) === inverterId);
      };
      const assignedArrayIds = new Set(inverters.flatMap(inverter => stringsForInverter(inverter).map(array=>String(firstDefined(array.asset_id,array.id,'')||''))));
      const unassignedArrays = arrays.filter(array => !assignedArrayIds.has(String(firstDefined(array.asset_id,array.id,'')||'')));
      const inverterSection = this.solarInverterSystem(rt,inverters,stringsForInverter,panelsFor,optimizersFor,unassignedArrays);
      const aggregate = production[0] || null;
      let productionBody = inverterSection;
      if (aggregate) {
        const enriched = this.energyAssetContext(rt,aggregate);
        const currentSolar = this.currentEnergyModel(rt).solar;
        const secondaryFacts = this.energyAssetFacts(rt,enriched,8)
          .filter(row=>!/^(state|status|power now|production now)$/i.test(String(row.label || '')))
          .slice(0,3);
        const aggregateFacts = [{label:rhiEnergyT(this._hass,'solar.production_now',{},'Production now'),value:fmtKw(currentSolar.powerKw,'—')}, ...secondaryFacts];
        const aggregateState = currentSolar.powerKw === null ? 'Unavailable' : currentSolar.powerKw > 0.005 ? 'Producing' : 'Idle';
        const children = inverterSection
          ? `<details class="energyAssetChildrenSibling solarProductionChildrenDisclosure" open><summary>Children · ${inverters.length}</summary><div class="energyAssetChildrenStack">${inverterSection}</div></details>`
          : '';
        productionBody = `<div class="energyAssetNode solarProductionNode"><article class="solarProductionObject">
          <div class="solarProductionRepresentativeWrap">${this.solarProductionRepresentative(rt)}</div>
          <div class="solarProductionObjectBody"><div class="solarProductionObjectHead"><div><small>${escapeHtml(rhiEnergyT(this._hass,"solar.production",{},"SOLAR PRODUCTION"))}</small><h3>${escapeHtml(firstDefined(enriched.display_name,enriched.name,rhiEnergyT(this._hass,'solar.production_title',{},'Solar Production')))}</h3></div>${aggregateState ? `<b>${escapeHtml(aggregateState)}</b>` : ''}</div>
          <div class="energyDeviceFacts">${aggregateFacts.map(row=>`<span><small>${escapeHtml(row.label)}</small><b>${escapeHtml(row.value)}</b></span>`).join('') || `<span><small>${escapeHtml(rhiEnergyT(this._hass,'solar.production_now',{},'Production'))}</small><b>${escapeHtml(rhiEnergyT(this._hass,'common.unavailable',{},'Unavailable'))}</b></span>`}</div>
          <div class="energyAssetFoldStack">${this.energyAssetConfigurationDisclosure(rt,enriched)}${this.energyAssetDetailDisclosure(rt,enriched)}${this.energyAssetDiagnosticsDisclosure(rt,enriched)}</div></div>
        </article>${children}</div>`;
      }
      const productionSection = productionBody
        ? this.solarHardwareSection(
            rhiEnergyT(this._hass,'solar.production_title',{},'Solar Production'),
            'Generation system with its physical inverter → string → optimizer/panel hierarchy.',
            productionBody,
            `${inverters.length} inverter${inverters.length===1?'':'s'}`,
            'solar-production-detail'
          )
        : '';
      const batterySection = this.solarBatterySystem(rt,systems,batteries);
      return `<div class="solarHardwareExperience">${batterySection}${productionSection}</div>`;
    }

    solarEnergyStory(rt) {
      const current = this.currentEnergyModel(rt);
      const solar = current.solar.powerKw;
      const site = current.consumption.siteConsumptionKw;
      const battery = current.battery;
      const gridImport = current.grid.importPowerKw;
      const gridExport = current.grid.exportPowerKw;
      const gridPower = current.grid.direction === 'exporting' ? gridExport : gridImport;
      const incomplete = [
        solar === null ? 'solar' : '',
        site === null ? 'home' : '',
        battery.displayPowerKw === null ? 'battery' : '',
        gridPower === null ? 'grid' : ''
      ].filter(Boolean);
      const status = incomplete.length
        ? `<div class="solarFlowStatus">Current balance incomplete · ${escapeHtml(incomplete.join(', '))} unavailable</div>`
        : '';
      return `<section class="panel solarEnergyStory" aria-label="Current energy balance">
        <div class="solarValueFlow solarBalancePositions">
          <button type="button" data-scroll-target="solar-production-detail"><small>Solar</small><b>${fmtKw(solar)}</b><span>Production now</span></button>
          <button type="button" data-scroll-target="solar-battery-detail"><small>Battery</small><b>${fmtKw(battery.displayPowerKw)}</b><span>${escapeHtml(battery.label || human(battery.state || ''))}</span></button>
          <div class="solarFlowNode"><small>${escapeHtml(rhiEnergyT(this._hass,"solar.home",{},"Home"))}</small><b>${fmtKw(site)}</b><span>${escapeHtml(rhiEnergyT(this._hass,"solar.consumption_now",{},"Consumption now"))}</span></div>
          <div class="solarFlowNode"><small>${escapeHtml(rhiEnergyT(this._hass,"solar.grid",{},"Grid"))}</small><b>${fmtKw(gridPower)}</b><span>${escapeHtml(current.grid.label || human(current.grid.direction || ''))}</span></div>
        </div>
        ${status}
      </section>`;
    }

    powerFlowCardStyles() { return `.rhiNativeFlowDiagram{margin:10px 0;padding:13px;border:1px solid #dce5ef;border-radius:13px;background:linear-gradient(145deg,#f8fbff,#f7fcf9)}.rhiNativeFlowStage{display:grid;grid-template-columns:minmax(0,1fr) minmax(145px,.85fr) minmax(0,1fr);gap:13px;align-items:center}.rhiNativeFlowLane{display:grid;gap:8px;align-content:start;min-width:0}.rhiNativeFlowLane h3{font-size:12px;font-weight:650;margin:0 0 3px;color:#334155}.rhiNativeFlowNode{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:11px;border:1px solid #dce5ef;border-radius:10px;background:#fff}.rhiNativeFlowNode b{display:block;font-size:11px}.rhiNativeFlowNode small{display:block;font-size:9px;color:#64748b}.rhiNativeFlowNode strong{white-space:nowrap;font-size:14px;font-variant-numeric:tabular-nums}.rhiNativeFlowNode.solar{border-left:3px solid #e8ae42}.rhiNativeFlowNode.grid{border-left:3px solid #60a5fa}.rhiNativeFlowNode.battery{border-left:3px solid #34b589}.rhiNativeFlowNode.home{border-left:3px solid #94a3b8}.rhiNativeFlowBus{display:flex;align-items:center;justify-content:center;gap:6px}.rhiNativeFlowBus>span{color:#64748b;font-size:19px}.rhiNativeFlowHub{min-width:0;flex:1;text-align:center;border:1px solid #bad9cf;background:#ebf7f3;padding:13px 8px;border-radius:12px}.rhiNativeFlowHub strong{font-size:19px;display:block;font-variant-numeric:tabular-nums}.rhiNativeFlowHub small{font-size:9px;color:#48675e}.rhiNativeFlowDisclaimer{font-size:10px;color:#64748b;margin:10px 2px 0}.rhiOptionalPowerFlow{margin:12px 0 0;border-top:1px solid #edf1f6;padding-top:10px}.rhiOptionalPowerFlow>summary{cursor:pointer;color:#526685;font-size:11px;font-weight:600}@media(max-width:800px){.rhiNativeFlowStage{grid-template-columns:1fr;gap:9px}.rhiNativeFlowBus{min-height:62px}.rhiNativeFlowBus>span{transform:rotate(90deg)}.rhiNativeFlowHub{flex:0 1 240px}.rhiNativeFlowNode{min-height:36px}}.rhiFlowHistoryGrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:1rem;align-items:stretch}.rhiFlowHistoryGrid>.panel{min-width:0}.rhiPowerFlowPanel{min-width:0}.rhiPowerFlowHost{min-height:230px;width:100%;overflow-x:auto}.rhiPowerFlowHost power-flow-card-plus{display:block;width:100%}.rhiFlowMeasurementNote{font-size:11px;color:var(--rhi-color-muted);margin-top:7px}.rhiFlowAllLoads{margin-top:10px}.rhiFlowAllLoads .flowPhysicalConsumerCard{margin-top:5px}`; }
    flowDependencyStyles() {
      return `.rhiFlowDependencyNotice{border-left:3px solid #c08420;background:#fffbef;padding:10px 14px;margin-bottom:10px}
        .rhiFlowDependencyNotice strong{font-size:12px;color:#713f12}
        .rhiFlowDependencyNotice p{font-size:11px;line-height:1.4;margin:6px 0;color:#66502b}
        .rhiFlowDependencyNotice a{font-size:11px;text-decoration:underline;color:#1d4ed8}`;
    }
    energyHardwareStyles() {
      return `
        .gasPage{display:grid;gap:12px}.gasKpiStrip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.gasKpiStrip article{background:#fff;border:1px solid #e5ebf3;border-radius:12px;padding:11px 12px;min-width:0}.gasKpiStrip small,.gasKpiStrip b,.gasKpiStrip span{display:block}.gasKpiStrip small{font-size:9px;color:#64748b}.gasKpiStrip b{font-size:14px;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.gasKpiStrip span{font-size:9px;color:#64748b;margin-top:4px}.gasUseFacts,.gasSetupFacts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:10px}.gasUseFacts article,.gasSetupFacts>div{border:1px solid #e5ebf3;border-radius:12px;padding:12px;background:#fbfdff;min-width:0}.gasUseFacts article{display:grid;grid-template-columns:30px minmax(0,1fr);gap:9px;align-items:center}.gasUseFacts article>span{font-size:18px}.gasUseFacts small,.gasUseFacts b,.gasSetupFacts small,.gasSetupFacts b,.gasSetupFacts span{display:block}.gasUseFacts small,.gasSetupFacts small,.gasSetupFacts span{font-size:9px;color:#64748b}.gasUseFacts b,.gasSetupFacts b{font-size:12px;margin-top:3px}.gasSetupFacts span{margin-top:4px;line-height:1.35}.gasHistoryControls{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}.gasHistoryControls>span{font-size:9px;color:#64748b}.gasStatisticsHost{min-height:260px;margin-top:10px}.gasStatisticsHost hui-statistics-graph-card{display:block}.energyHistoryPanel{margin-top:12px}.energyHistoryHost{min-height:205px;margin-top:6px}.energyHistoryHost hui-history-graph-card{display:block}.energyHistorySelector{display:flex;flex-wrap:wrap}.gasMeterPanel .energyDeviceGrid{display:grid;grid-template-columns:minmax(0,1fr);width:100%}.gasMeterPanel .energyDeviceCard{width:100%;max-width:none;min-width:0;grid-template-columns:96px minmax(0,1fr);align-items:start}.gasMeterPanel .energyDeviceBody,.gasMeterPanel .energyDeviceTop,.gasMeterPanel .energyDeviceFacts{min-width:0;max-width:100%}.gasMeterPanel .energyDeviceTop{flex-wrap:wrap}.gasMeterPanel .energyDeviceTop h3{overflow-wrap:anywhere}.gasMeterPanel .energyDeviceFacts{grid-template-columns:repeat(auto-fit,minmax(min(100%,120px),1fr))}@media(max-width:720px){.gasKpiStrip{grid-template-columns:repeat(2,minmax(0,1fr))}.gasUseFacts,.gasSetupFacts{grid-template-columns:1fr}.gasContextGrid,.planningContextGrid{grid-template-columns:repeat(2,minmax(0,1fr))}.gasStatisticsHost{min-height:220px}}

        .energyHardwarePanel,.solarEnergyStory{margin:12px 0}.energyHardwareHead{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:14px}.energyHardwareHead>span{font-size:11px;font-weight:700;color:#64748b;background:#f8fafc;border:1px solid #e5ebf3;border-radius:999px;padding:6px 9px;white-space:nowrap}
        .solarEnergyStory{padding:10px 12px}.solarValueFlow{display:grid;grid-template-columns:repeat(4,minmax(92px,1fr));gap:7px;align-items:stretch}.solarValueFlow button,.solarFlowNode{border:0;background:#f8fafc;border-radius:10px;padding:8px 10px;text-align:left;min-width:0}.solarValueFlow button{cursor:pointer}.solarValueFlow button:hover{background:#eff6ff;box-shadow:inset 0 0 0 1px #bfdbfe}.solarValueFlow small,.solarValueFlow b,.solarValueFlow span{display:block}.solarValueFlow small{font-size:8px;color:#64748b;font-weight:700}.solarValueFlow b{font-size:14px;color:#0f172a;margin-top:2px;white-space:nowrap}.solarValueFlow span{font-size:8px;color:#64748b;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.solarFlowStatus{margin-top:7px;font-size:8.5px;color:#9a5b17;padding:0 2px}.solarHardwareSection{scroll-margin-top:12px}@media(max-width:720px){.solarValueFlow{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.solarValueFlow button,.solarFlowNode{padding:8px}.solarValueFlow b{font-size:12px}}
        .solarProductionHierarchy{margin-top:12px;padding-top:10px;border-top:1px solid #e5ebf3}.solarProductionHierarchyHead{display:flex;justify-content:space-between;align-items:center;margin:0 2px 8px}.solarProductionHierarchyHead small{font-size:9px;font-weight:750;color:#64748b;letter-spacing:.08em}.solarProductionHierarchyHead b{font-size:10px;color:#476487}.solarTopologyDiagnostics{margin-top:10px;border-top:1px solid #edf1f6;padding-top:8px}.solarTopologyDiagnostics>summary{cursor:pointer;color:#64748b;font-size:9px;font-weight:650}.solarTopologyDiagnostics>p{font-size:9px;color:#64748b;margin:7px 0}.solarModuleHeadActions{display:flex;align-items:center;gap:6px}.solarModuleHeadActions .energyAppearanceAction{font-size:7.5px;padding:4px 6px}.solarInverterGrid{display:grid;gap:9px}.solarInverterCard{border:1px solid #e5ebf3;border-radius:13px;background:#fff;padding:8px}.solarInverterCard>.energyDeviceCard{border:0;padding:2px;min-height:150px}.solarInverterStrings{margin-top:8px;border-top:1px solid #edf1f6;padding-top:8px}.solarInverterStringsHead{display:flex;justify-content:space-between;align-items:center;padding:0 4px 6px}.solarInverterStringsHead small{font-size:8px;letter-spacing:.1em;color:#64748b;font-weight:800}.solarInverterStringsHead b{font-size:10px;color:#475569}.solarStringLink{border-top:1px solid #edf1f6;padding:9px 4px}.solarProductionLead{display:grid;grid-template-columns:150px minmax(0,1fr);gap:10px;align-items:stretch}.solarProductionRepresentative{min-height:118px;border:1px solid #e5ebf3;border-radius:12px;background:#f8fafc;display:flex;align-items:center;justify-content:center;overflow:hidden}.solarProductionRepresentative img{width:100%;height:100%;max-height:138px;object-fit:contain;padding:6px;box-sizing:border-box}.solarStringSummary{display:grid;grid-template-columns:86px minmax(0,1.6fr) minmax(90px,.7fr) minmax(70px,.5fr);gap:10px;align-items:center}.solarStringVisual{height:64px;display:flex;align-items:center;justify-content:center;background:#f8fafc;border-radius:9px;overflow:hidden}.solarStringVisual .assetVisual{width:100%;height:100%}.solarStringVisual img{width:100%;height:100%;object-fit:contain}.solarStringSummary span small,.solarStringSummary span b{display:block}.solarStringSummary small{font-size:8px;color:#64748b}.solarStringSummary b{font-size:11px;color:#1e293b;margin-top:2px}.solarStringLink>.solarModuleGrid{margin-top:8px}.solarStringLink>.energyAssetDetails{margin-top:8px}.solarStringList{border:1px solid #e5ebf3;border-radius:12px;padding:0 8px;background:#fff}.solarUnresolvedStrings{margin-top:10px;padding-top:8px;border-top:1px solid #edf1f6}.solarUnresolvedStrings>p{margin:0 4px 8px;color:#64748b;font-size:9.5px;line-height:1.4}@media(max-width:720px){.solarProductionLead{grid-template-columns:1fr}.solarProductionRepresentative{max-height:120px}.solarStringSummary{grid-template-columns:72px minmax(0,1fr) auto}.solarStringSummary span:nth-of-type(2){display:none}}
                .energyDeviceGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.energyDeviceCard{display:grid;grid-template-columns:108px minmax(0,1fr);gap:10px;border:1px solid #e5ebf3;background:#fff;border-radius:12px;padding:9px;min-height:126px}.energyDeviceCard.rhiEnergyCoreAssetCard{grid-template-columns:minmax(0,1fr);grid-auto-flow:row;align-content:start}
        .energyDeviceCard.rhiEnergyCoreAssetCard>.rhiUxAssetIdentity,.energyDeviceCard.rhiEnergyCoreAssetCard>.rhiUxAssetFactGrid,.energyDeviceCard.rhiEnergyCoreAssetCard>.rhiUxAssetRelationship,.energyDeviceCard.rhiEnergyCoreAssetCard>.energyAssetFoldStack{min-width:0;max-width:100%}
        .energyDeviceCard.rhiEnergyCoreAssetCard>.rhiUxAssetFactGrid{grid-template-columns:repeat(auto-fit,minmax(min(100%,160px),1fr))}
        .energyDeviceCard.rhiEnergyCoreAssetCard .rhiUxAssetIdentityCopy h2{overflow-wrap:anywhere}.energyDeviceVisual{height:108px;display:flex;align-items:center;justify-content:center;background:linear-gradient(180deg,#fbfdff,#f6f8fb);border-radius:11px;overflow:hidden}.energyDeviceVisual .assetVisual{width:100%;height:100%;display:flex;align-items:center;justify-content:center}.energyDeviceVisual .assetVisual img{width:100%;height:100%;object-fit:contain;object-position:center;padding:5px;box-sizing:border-box}.energyDeviceBody{min-width:0}.energyDeviceTop{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}.energyDeviceTopActions{display:flex;align-items:center;gap:6px;flex-wrap:wrap;justify-content:flex-end}.energyAppearanceAction{border:1px solid #cbd5e1;background:#fff;color:#355D96;border-radius:8px;padding:5px 7px;font-size:8.5px;font-weight:700;cursor:pointer}.energyAppearanceAction:hover{background:#eff6ff;border-color:#93c5fd}.energyDeviceTop small{color:#64748b;font-size:9px;text-transform:uppercase;letter-spacing:.08em;font-weight:700}.energyDeviceTop h3{font-size:13px;line-height:1.25;margin:3px 0 8px}.energyDeviceArea{display:block;margin:-4px 0 7px;color:#64748b;font-size:9px}.batteryContributorArea{display:block;margin-top:3px;color:#64748b;font-size:9px}.energyDeviceState{font-size:9px;background:#eef7f1;color:#3f7f5a;border-radius:999px;padding:5px 7px;white-space:nowrap}.energyDeviceConfig{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}.energyDeviceConfig span{font-size:9px;color:#64748b;background:#f8fafc;border-radius:7px;padding:5px 6px}.energyDeviceConfig b{color:#334155;margin-right:4px}.energyDeviceFacts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.energyDeviceFacts span{background:#f8fafc;border-radius:7px;padding:6px;min-width:0}.energyDeviceRelation{grid-column:1/-1}.energyDeviceFacts small,.energyDeviceFacts b{display:block}.energyDeviceFacts small{font-size:8px;color:#64748b}.energyDeviceFacts b{font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.energyDeviceNoFacts{grid-column:1/-1}.energyAssetQuickActions{grid-column:1/-1;display:grid;gap:5px;margin-top:8px;padding-top:8px;border-top:1px solid #edf1f6}.energyAssetQuickActions>small{font-size:8px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;font-weight:700}.energyAssetQuickActions>div{display:flex;gap:6px;flex-wrap:wrap}.energyAssetQuickActions .hiAction{min-height:30px;padding:0 9px;font-size:9.5px}
        .energyAssetDetails{margin-top:8px;border-top:1px solid #edf1f6;padding-top:7px}.energyAssetDetails>summary{cursor:pointer;color:#355D96;font-size:9px;font-weight:650;list-style:none}.energyAssetDetails>summary::-webkit-details-marker{display:none}.energyAssetDetails>summary:after{content:" ▾";color:#94a3b8}.energyAssetDetails[open]>summary:after{content:" ▴"}.energyAssetDetailGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px;margin-top:7px}.energyAssetDetailGrid span{min-width:0;background:#f8fafc;border-radius:7px;padding:6px}.energyAssetDetailGrid span.wide{grid-column:1/-1}.energyAssetDetailGrid small,.energyAssetDetailGrid b{display:block}.energyAssetDetailGrid small{font-size:8px;color:#64748b}.energyAssetDetailGrid b{font-size:9.5px;line-height:1.3;overflow-wrap:anywhere}.energyAssetPropertyList{margin-top:8px;padding-top:8px;border-top:1px solid #edf1f6}.energyAssetPropertyTitle{display:block;margin-bottom:6px;font-size:8px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;font-weight:700}.energyAssetPropertyGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px}.energyAssetPropertyGrid span{min-width:0;background:#f8fafc;border-radius:7px;padding:6px}.energyAssetPropertyGrid small,.energyAssetPropertyGrid b{display:block}.energyAssetPropertyGrid small{font-size:8px;color:#64748b}.energyAssetPropertyGrid b{font-size:9.5px;line-height:1.3;overflow-wrap:anywhere}
        .gasContextGrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:10px}.gasContextGrid span{min-width:0;border:1px solid #e5ebf3;border-radius:10px;background:#f8fafc;padding:9px 10px}.gasContextGrid small,.gasContextGrid b{display:block}.gasContextGrid small{font-size:8.5px;color:#64748b}.gasContextGrid b{font-size:10.5px;line-height:1.3;margin-top:3px;overflow-wrap:anywhere}
        .solarProductionStrip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:10px 0 12px}.solarProductionStrip article{background:#fff;border:1px solid #e5ebf3;border-radius:12px;padding:10px 12px}.solarProductionStrip small,.solarProductionStrip b{display:block}.solarProductionStrip small{font-size:9px;color:#64748b}.solarProductionStrip b{font-size:15px;margin-top:3px}.managedAssetIdentity,.strategyAssetIdentity,.meteringAssetIdentity,.effectivePolicyIdentity{display:flex;align-items:center;gap:8px;min-width:0}.managedAssetIdentity>div,.strategyAssetIdentity>div,.meteringAssetIdentity>span{min-width:0}.meteringAssetIdentity b,.meteringAssetIdentity small{display:block}.effectivePolicyIdentity b{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.solarHardwareExperience{display:grid;gap:12px;margin:12px 0}.solarHardwareSection{margin:0}.solarHardwareSectionHead{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin-bottom:12px}.solarHardwareSectionHead h2{margin:0 0 4px}.solarHardwareSectionHead p{margin:0;color:#64748b;font-size:11px}.solarHardwareSectionHead>span,.solarAggregateCount{font-size:10px;font-weight:700;color:#64748b;background:#f8fafc;border:1px solid #e5ebf3;border-radius:999px;padding:6px 9px;white-space:nowrap}.solarAggregateCard{border:1px solid #e5ebf3;border-radius:14px;padding:12px;background:#fff}.solarAggregateCard+.solarAggregateCard{margin-top:10px}.solarAggregateHead{display:grid;grid-template-columns:116px minmax(0,1fr) auto;gap:12px;align-items:center}.solarAggregateVisual{height:104px;display:flex;align-items:center;justify-content:center;background:#f8fafc;border-radius:11px;overflow:hidden}.solarAggregateVisual .assetVisual{width:100%;height:100%;display:flex;align-items:center;justify-content:center}.solarAggregateVisual .assetVisual img{width:100%;height:100%;object-fit:contain;object-position:center;padding:6px;box-sizing:border-box}.solarAggregateCopy small,.solarSystemSummary small{font-size:9px;font-weight:750;color:#64748b;letter-spacing:.08em}.solarAggregateCopy h3,.solarSystemSummary h3{margin:3px 0 5px;font-size:15px}.solarAggregateCopy p,.solarSystemSummary p{margin:0;color:#64748b;font-size:10.5px;line-height:1.4}.solarAggregateFacts{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.solarAggregateFacts span{min-width:96px;background:#f8fafc;border-radius:8px;padding:7px 8px}.solarAggregateFacts small,.solarAggregateFacts b{display:block}.solarAggregateFacts small{font-size:8px;color:#64748b}.solarAggregateFacts b{font-size:10px;margin-top:2px}.solarChildGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:10px}.solarModuleGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:12px}.solarModuleCard{display:grid;grid-template-columns:96px minmax(0,1fr);gap:10px;border:1px solid #e5ebf3;border-radius:12px;padding:10px;background:#fbfdff}.solarModuleVisual{height:96px;display:flex;align-items:center;justify-content:center;background:#fff;border-radius:9px;overflow:hidden}.solarModuleVisual .assetVisual,.solarModuleVisual img{width:100%;height:100%;object-fit:contain}.solarModuleHead{display:flex;justify-content:space-between;gap:8px}.solarModuleHead small,.solarModuleHead span{display:block;font-size:8px;color:#64748b}.solarModuleHead h4{margin:2px 0;font-size:11px}.solarModuleHead>b{font-size:8.5px;color:#476487;white-space:nowrap}.solarModuleFacts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:5px;margin-top:7px}.solarModuleFacts span{padding:5px 6px;border-radius:7px;background:#fff}.solarModuleFacts small,.solarModuleFacts b{display:block}.solarModuleFacts small{font-size:7.5px;color:#64748b}.solarModuleFacts b{font-size:9px}.solarOptimizerRelation{display:block;margin-top:7px;padding:6px 7px;border-radius:7px;background:#fff}.solarOptimizerRelation small,.solarOptimizerRelation b{display:block}.solarOptimizerRelation small{font-size:7.5px;color:#64748b}.solarOptimizerRelation b{font-size:9px;margin-top:2px}.solarOptimizerHint{display:block;margin-top:7px;color:#64748b;font-size:8.5px;line-height:1.35}.consumerPrimarySummary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.consumerPrimarySummary>span{padding:10px 12px;border:1px solid var(--line);border-radius:11px;background:#fff}.consumerPrimarySummary small,.consumerPrimarySummary b{display:block}.consumerPrimarySummary small{font-size:8.5px;color:var(--muted)}.consumerPrimarySummary b{margin-top:3px;font-size:13px}.managedAssetRelationship{margin-top:7px;padding:7px 8px;border-radius:8px;background:#f8fafc}.managedAssetRelationship small,.managedAssetRelationship b{display:block}.managedAssetRelationship small{font-size:8px;color:#64748b}.managedAssetRelationship b{font-size:9.5px;margin-top:2px}.solarSystemSummary{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;align-items:start}.solarUnassignedPanels{margin-top:12px}.solarUnassignedPanels h3{font-size:12px;margin:0 0 6px}.solarUnassignedPanels p{font-size:10px;color:#64748b;margin:0 0 7px}.solarTopologyDetails{margin-top:9px;border-top:1px solid #edf1f6;padding-top:7px}.solarTopologyDetails>summary{cursor:pointer;color:#355D96;font-size:10px;font-weight:650}
                .solarStoryHead{align-items:center}.solarStoryHead small{font-size:9px;text-transform:uppercase;letter-spacing:.1em;color:#d97706;font-weight:750}.solarStoryHead h2{margin:3px 0}.solarStoryRoute{display:flex;align-items:center;gap:7px;flex-wrap:wrap;justify-content:flex-end}.solarStoryRoute span{font-size:10px;font-weight:700;padding:6px 9px;border-radius:999px;background:#fff7ed;border:1px solid #fed7aa}.solarStoryRoute i{font-style:normal;color:#94a3b8}.solarAnswerGrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.solarAnswerGrid article{background:#f8fafc;border:1px solid #edf1f6;border-radius:10px;padding:10px}.solarAnswerGrid small{display:block;color:#64748b;font-size:9px;margin-bottom:4px}.solarAnswerGrid b{font-size:11px;line-height:1.4;font-weight:650}.solarWhereAnswer{margin-top:8px;background:#fff7ed;border:1px solid #fed7aa;border-radius:10px;padding:11px 12px}.solarWhereAnswer span{display:block;color:#9a5b17;font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.08em}.solarWhereAnswer b{display:block;margin-top:3px;font-size:11.5px;line-height:1.4}
        @media(max-width:1100px){.energyDeviceGrid{grid-template-columns:repeat(2,minmax(0,1fr))}.energyDeviceCard{grid-template-columns:112px minmax(0,1fr)}.energyDeviceVisual{height:128px}.solarAnswerGrid{grid-template-columns:repeat(2,minmax(0,1fr))}.solarChildGrid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:720px){.energyDeviceGrid{grid-template-columns:1fr}.energyDeviceCard{grid-template-columns:96px minmax(0,1fr);gap:10px;padding:10px;min-height:142px}.energyDeviceVisual{height:112px}.energyDeviceFacts{grid-template-columns:repeat(2,minmax(0,1fr))}.energyAssetQuickActions>div{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.energyAssetQuickActions .hiAction{width:100%;min-width:0}.solarStoryHead{display:block}.solarStoryRoute{justify-content:flex-start;margin-top:10px}.solarAnswerGrid{grid-template-columns:1fr}.solarChildGrid{grid-template-columns:1fr}.solarAggregateHead{grid-template-columns:92px minmax(0,1fr)}.solarAggregateCount{grid-column:2}.solarAggregateVisual{height:88px}.solarSystemSummary{grid-template-columns:1fr}}
        @media(max-width:720px){.solarProductionStrip{grid-template-columns:repeat(2,minmax(0,1fr))}.solarModuleGrid,.consumerPrimarySummary{grid-template-columns:1fr}.solarModuleCard{grid-template-columns:76px minmax(0,1fr)}.solarModuleVisual{height:78px}}
        /* 4.3.28 target-HA phone closure: product cards must flow vertically.
           No desktop two-up composition or visual/fact overlay survives below 720px. */
        @media(max-width:720px){
          .batteryGrid.batteryGridTwoUp{display:grid;grid-template-columns:1fr;gap:10px}
          .batteryGrid.batteryGridTwoUp>.panel{width:100%;min-width:0;box-sizing:border-box}
          .batteryContributorCard{grid-template-columns:88px minmax(0,1fr);min-height:0}
          .batteryContributorVisual{min-width:0;padding:8px}
          .batteryContributorVisual .assetVisual{width:72px;height:90px;max-width:72px;max-height:90px}
          .batteryContributorBody{padding:10px;min-width:0}
          .batteryContributorHeader{align-items:flex-start}
          .batteryContributorFacts{grid-template-columns:repeat(2,minmax(0,1fr))}
          .energyDeviceCard.rhiEnergyCoreAssetCard{display:grid;grid-template-columns:1fr;gap:8px;min-height:0;padding:10px}
          .gasMeterPanel .energyDeviceCard,.gasMeterPanel .energyDeviceGrid{max-width:none;width:100%;grid-template-columns:1fr}
          .energyAssetQuickActions>div{grid-template-columns:1fr}
          .energyAssetQuickActions .hiAction{min-height:42px}
          .solarValueFlow{overflow:visible;grid-template-columns:repeat(2,minmax(0,1fr));justify-content:stretch;padding-bottom:0}
          .solarValueFlow button,.solarFlowNode{min-width:0}
        }
      `;
    }

    solar(rt) {
      const pageVm = this.buildPageViewModel(rt, 'solar');
      return `${this.tabExperienceHeader(rt,'solar',pageVm)}<div class="solarPage solarHardwarePage">
        ${this.solarEnergyStory(rt)}
        ${this.solarHardwareExperience(rt)}
        ${this.energyHistorySection(rt,'solar')}
      </div>`;
    }

    operationalPlanning(rt) {
      const pageVm = this.buildPageViewModel(rt, 'operational-planning');
      const d = rt.decision();
      const recommendation = firstDefined(d.recommendation, d.advice, rt.rawText('energy_intelligence.recommendation', null), 'Observe');
      const targetId = firstDefined(d.recommended_target_asset_id, rt.value('energy_intelligence.recommended_target_asset_id', null), '');
      const assetDomain = this.flexibleAssetDomain(rt);
      const loads = assetDomain.consumerFacing().map(vm => vm.raw);
      const participating = loads.filter(load => assetDomain.byId(load.asset_id)?.isParticipating && load.planning_input_ready === true);
      const unassessed = loads.filter(load => !assetDomain.byId(load.asset_id)?.isDisabled && !(assetDomain.byId(load.asset_id)?.isParticipating && load.planning_input_ready === true));
      const disabled = loads.filter(load => assetDomain.byId(load.asset_id)?.isDisabled);
      const cards = participating.map(load => this.operationalLoadCard(rt, load, recommendation, targetId)).join('');
      const unassessedCards = unassessed.map(load => this.consumerExplorerCard(rt,load)).join('');
      const disabledCards = disabled.map(load => this.disabledFlexibleAssetCard(rt, load, load.energy_planning || rt.planningOutcomeFor(load.asset_id) || {})).join('');
      const active = participating.filter(load => (asNumber(load.power_kw) || 0) > 0.05 || /running|charging|executing/i.test(String(load.operating_state || load.current_status || ''))).length;
      const planned = participating.filter(load => {
        const p = load.energy_planning || rt.planningOutcomeFor(load.asset_id) || {};
        return /planned|scheduled|expected today|done today/i.test(String(firstDefined(p.state,p.status,p.today_status,p.expected,'')));
      }).length;
      const waiting = participating.filter(load => {
        const p = load.energy_planning || rt.planningOutcomeFor(load.asset_id) || {};
        return /waiting|blocked|uncertain|not eligible/i.test(String(firstDefined(p.state,p.status,p.today_status,p.expected,'')));
      }).length;
      const executionPolicy = this.automationExecutionPolicy(rt);
      const executePlan = rt.commands().find(command => rt.commandRole(command) === 'execute_plan') || null;
      const policyTitle = executionPolicy.configuredMode === 'automatic'
        ? 'Automatic · Home Intelligence may execute the current plan'
        : executionPolicy.configuredMode === 'advice'
          ? 'Advice · plan waits for your approval'
          : 'Disabled · planning is informational only';
      const policyWhy = executionPolicy.configuredMode === 'automatic'
        ? 'Only the current plan can be executed, and each device must confirm the change.'
        : executionPolicy.configuredMode === 'advice'
          ? 'Home Intelligence calculates the same plan but cannot dispatch it autonomously.'
          : 'Home Intelligence keeps calculating planning insight but managed plan execution is blocked.';
      const effectivePlanAvailable = rt.nativePlanningHorizon('D0')?.available === true;
      const executeAction = effectivePlanAvailable && executePlan && rt.commandVisible(executePlan)
        ? this.componentActionButton(executePlan, executePlan.label || (executionPolicy.configuredMode === 'advice' ? 'Apply current plan' : 'Run current plan now'), 'energy')
        : '';
      const authorityCard = this.productStoryCard({
        eyebrow:rhiEnergyT(this._hass,'automation.authority',{},'Automation authority'),
        title:policyTitle,
        why:policyWhy,
        recommendation:executionPolicy.configuredMode === 'advice'
          ? 'Review the plan and apply it when you agree.'
          : executionPolicy.configuredMode === 'automatic'
            ? 'Home Intelligence manages the current plan within your configured strategies.'
            : 'Change Automation mode to Advice or Automatic to allow managed plan execution.',
        actions:executeAction,
        tone:executionPolicy.configuredMode === 'automatic' ? 'green' : executionPolicy.configuredMode === 'advice' ? 'blue' : 'orange'
      });
      return `${this.tabExperienceHeader(rt,'operational-planning',pageVm)}${this.bodyContextBar(rt,'operational-planning','operational-planning-body')}<div id="operational-planning-body" class="operationalPlanningPage">${authorityCard}
        <section class="panel operationalPlanningLoads"><div class="energySectionHead"><div><h2>${escapeHtml(rhiEnergyT(this._hass,'section.flexible_loads',{},'Flexible loads'))}</h2><p>${escapeHtml(rhiEnergyT(this._hass,'section.flexible_loads_desc',{},'Current execution, next action, requested power and operational reason. Hardware configuration is not shown here.'))}</p></div></div><div class="flexLoadList">${cards || '<div class="empty"><b>No participating flexible loads</b><span>No controllable load currently participates in operational planning.</span></div>'}</div></section>
        ${unassessedCards ? `<section class="panel operationalPlanningLoads"><div class="energySectionHead"><div><h2>Not plan-ready</h2><p>Published flexible loads without confirmed planning participation or complete inputs. No schedule or command readiness is inferred.</p></div></div><div class="flexLoadList">${unassessedCards}</div></section>` : ''}
        ${disabledCards ? `<details class="panel compactDisclosure"><summary>${escapeHtml(rhiEnergyT(this._hass,"asset.other",{},"Other assets"))} (${disabled.length})</summary><p>${escapeHtml(rhiEnergyT(this._hass,"asset.excluded_planning",{},"These assets are excluded from operational planning."))}</p><div class="disabledAssetList">${disabledCards}</div></details>` : ''}
      </div>`;
    }
    outlook(rt) {
      const pageVm = this.buildPageViewModel(rt, 'outlook');
      const horizons = rt.outlookHorizons();
      if (!horizons.length) return `${this.tabExperienceHeader(rt,'outlook',pageVm)}<div class="outlookPage">${this.contractGap('Outlook unavailable','The canonical Outlook contract is not published.')}</div>`;
      const horizon = this.selectedHorizon(horizons, this.selectedOutlookHorizonId);
      if (!horizon) return `${this.tabExperienceHeader(rt,'outlook',pageVm)}<div class="outlookPage">${this.contractGap('Selected horizon temporarily unavailable', `The requested ${this.selectedOutlookHorizonId || 'D0'} horizon is not currently published. Your selection is preserved.`)}</div>`;
      const isTomorrow = this.isFutureHorizon(horizon);
      const supply = objectFrom(horizon.summary?.supply || {});
      const demand = objectFrom(horizon.summary?.demand || {});
      const balanceGroup = objectFrom(horizon.summary?.balance || {});
      // A verified solar/home-only projection is useful, but it is not the
      // complete site plan when flexible vehicle demand is unknown.
      const knownLoads = objectFrom(horizon.summary?.known_demand_projection || {});
      const knownLoadsPartial = knownLoads.excluded_unknown_loads === true;
      const knownLoadValue = (fullValue, partialValue) => fullValue !== null
        ? fullValue : asNumber(partialValue);
      const quality = objectFrom(horizon.summary?.quality || {});
      const mode = objectFrom(horizon.summary?.mode || {});
      const solarForecast = asNumber(firstDefined(supply.solar_forecast_kwh,supply.solar_today_kwh));
      const solarRemaining = asNumber(supply.solar_remaining_kwh);
      const batteryAboveReserve = asNumber(firstDefined(supply.battery_available_above_reserve_kwh,supply.available_above_reserve_kwh));
      const batteryReserve = asNumber(firstDefined(supply.battery_reserve_kwh,supply.protected_reserve_kwh));
      const batterySupport = asNumber(supply.battery_support_kwh);
      const totalAvailable = knownLoadValue(asNumber(supply.total_usable_supply_kwh), knownLoads.total_usable_supply_kwh);
      const homeConsumption = asNumber(firstDefined(demand.home_consumption_forecast_kwh,demand.base_load_forecast_kwh,demand.home_load_forecast_kwh));
      const knownNeed = asNumber(firstDefined(demand.flexible_known_need_kwh,demand.known_flexible_need_kwh));
      const scheduledFlexible = asNumber(firstDefined(demand.flexible_scheduled_kwh,demand.scheduled_flexible_load_kwh));
      const flexibleTotal = scheduledFlexible !== null ? scheduledFlexible : knownNeed;
      const flexibleLabelKey = scheduledFlexible !== null ? 'forecast.flexible_scheduled' : knownNeed !== null ? 'forecast.flexible_known' : 'forecast.flexible_unknown';
      const totalDemand = asNumber(firstDefined(demand.total_expected_demand_kwh,demand.expected_demand_kwh));
      const gridImport = knownLoadValue(asNumber(firstDefined(balanceGroup.expected_grid_import_kwh,balanceGroup.grid_import_kwh)), knownLoads.expected_grid_import_kwh);
      const gridExport = knownLoadValue(asNumber(firstDefined(balanceGroup.expected_grid_export_kwh,balanceGroup.grid_export_kwh)), knownLoads.expected_grid_export_kwh);
      const gridBalance = knownLoadValue(asNumber(balanceGroup.grid_balance_kwh), knownLoads.grid_balance_kwh);
      const confidence = human(firstDefined(quality.confidence,horizon.confidence,'Not available'));
      const basis = human(firstDefined(supply.solar_basis,supply.forecast_basis,isTomorrow?'Full day forecast':'Remaining forecast'));
      const planningRows = this.flexibleAssetDomain(rt).consumerFacing().map(vm => {
        const load=vm.raw||{}; const id=load.asset_id||load.flexible_asset_id||''; const planning=load.energy_planning||rt.planningOutcomeFor(id)||{};
        // D0 and D1 are separate backend-owned periods; never report today's
        // allocation as a tomorrow allocation.
        const planned=asNumber(isTomorrow
          ? firstDefined(planning.planned_tomorrow_kwh,planning.scheduled_tomorrow_kwh)
          : firstDefined(planning.planned_today_kwh,planning.scheduled_today_kwh,planning.scheduled_kwh));
        const needed=asNumber(firstDefined(planning.known_need_kwh,planning.energy_to_target_kwh,load.energy_to_target_kwh,load.required_energy_kwh));
        const amount=planned!==null?planned:needed;
        // Inventory remains visible when need is unknown; unknown is not zero.
        const demandText = amount===null ? '—' : fmtKwh(amount);
        const evidenceLabel=planned!==null
          ? rhiEnergyT(this._hass,'forecast.row_planned',{},'Planned')
          : needed!==null ? rhiEnergyT(this._hass,'forecast.row_needed',{},'Needed, not scheduled') : 'Need unavailable';
        return `<div class="outlookChildRow">${this.assetVisual(load,{size:'xs',fallbackIcon:this.flexibleAssetIcon(load)})}<b>${escapeHtml(load.display_name||rt.assetName(id)||human(id))}</b><strong>${escapeHtml(demandText)}<small>${escapeHtml(evidenceLabel)}</small></strong></div>`;
      }).filter(Boolean).join('');
      const storageDemand = asNumber(firstDefined(demand.home_battery_charge_kwh,demand.battery_charge_kwh));
      const incompleteForecast = knownLoadsPartial || [totalAvailable,totalDemand,gridBalance].some(value=>value===null);
      const outlookBasisNote = knownLoadsPartial
        ? '<section class="panel outlookEvidenceNotice"><b>Known home and solar baseline only</b><p>Grid import, export and supply shown here exclude vehicles with unknown charging needs and do not include battery dispatch. This is not the complete site forecast or an executable plan.</p></section>'
        : '';
      const actualNow=this.currentEnergyModel(rt);
      // Actual now is kW; future D0/D1 projections are kWh. Never add them.
      const actualStrip=`<section class="outlookActualPower outlookSummaryStrip" aria-label="Actual energy power now"><div><small>Actual solar production now</small><b>${escapeHtml(fmtKw(actualNow.solar.powerKw,'—'))}</b></div><div><small>Actual site consumption now</small><b>${escapeHtml(fmtKw(actualNow.consumption.siteConsumptionKw,'—'))}</b></div><div><small>Actual home consumption now</small><b>${escapeHtml(fmtKw(actualNow.consumption.homeConsumptionKw,'—'))}</b></div></section>`;
      const totalRow=(label,value,formatter=fmtKwh)=>`<div class="outlookTotalRow"><span>${escapeHtml(label)}</span><b>${escapeHtml(formatter(value,'—'))}</b></div>`;
      return `${this.tabExperienceHeader(rt,'outlook',pageVm)}${this.bodyContextBar(rt,'outlook','outlook-body')}<div class="outlookPage outlookPageV2" id="outlook-body">${actualStrip}${outlookBasisNote}${incompleteForecast?`<section class="panel outlookEvidenceNotice"><b>${escapeHtml(rhiEnergyT(this._hass,'forecast.incomplete_title',{},'Forecast is incomplete'))}</b><p>${escapeHtml(rhiEnergyT(this._hass,'forecast.incomplete_desc',{},'Some supply, demand or grid totals are not published. The available values do not form a complete energy balance.'))}</p></section>`:''}<div class="outlookThreeGrid">
        <section class="panel outlookBalanceCard"><h2>${escapeHtml(rhiEnergyT(this._hass,'section.supply',{},'Supply'))}</h2><p>${escapeHtml(rhiEnergyT(this._hass,'section.supply_desc',{},'Expected usable energy for the selected horizon.'))}</p>${isTomorrow?this.kv('Solar forecast',fmtKwh(solarForecast)):this.kv('Solar remaining',fmtKwh(solarRemaining))}${batteryAboveReserve!==null?this.kv('Home Battery above reserve',fmtKwh(batteryAboveReserve)):''}${batterySupport!==null?this.kv('Battery support',fmtKwh(batterySupport)):''}${batteryReserve!==null?this.kv('Protected reserve',fmtKwh(batteryReserve)):''}${totalRow('Total usable supply',totalAvailable)}</section>
        <section class="panel outlookBalanceCard"><h2>${escapeHtml(rhiEnergyT(this._hass,'section.demand',{},'Demand'))}</h2><p>${escapeHtml(rhiEnergyT(this._hass,'section.demand_desc',{},'Expected Home Consumption, Flexible Loads and storage charging.'))}</p>${this.kv('Home Consumption forecast',fmtKwh(homeConsumption))}<div class="outlookAggregateRow"><span>${escapeHtml(rhiEnergyT(this._hass,flexibleLabelKey,{},'Flexible load demand'))}</span><b>${escapeHtml(fmtKwh(flexibleTotal,'—'))}</b></div><div class="outlookChildren">${planningRows||`<span class="muted">${escapeHtml(rhiEnergyT(this._hass,'forecast.per_asset_missing',{},'Individual charging needs are not published for this horizon.'))}</span>`}</div>${storageDemand!==null?this.kv('Home Battery',fmtKwh(storageDemand)):''}${totalRow('Total expected demand',totalDemand)}</section>
        <section class="panel outlookBalanceCard"><h2>${escapeHtml(rhiEnergyT(this._hass,'section.grid_impact',{},'Grid impact'))}</h2><p>${escapeHtml(rhiEnergyT(this._hass,'section.grid_impact_desc',{},'Expected grid exchange for the selected horizon.'))}</p>${this.kv('Expected Grid Import',fmtKwh(gridImport,'—'))}${this.kv('Expected Grid Export',fmtKwh(gridExport,'—'))}${totalRow('Grid Balance',gridBalance,v=>v===null?'—':`${v.toFixed(1)} kWh`)}<small class="outlookBalanceMeaning">${gridBalance===null?escapeHtml(rhiEnergyT(this._hass,'forecast.grid_unavailable',{},'Grid balance requires both import and export forecasts.')):gridBalance<0?`${Math.abs(gridBalance).toFixed(1)} kWh net export`:gridBalance>0?`${gridBalance.toFixed(1)} kWh net import`:'Balanced'}</small></section>
      </div></div>`;
    }
    flowNode(icon, title, value, subtitle, cls = '') {
      return `<div class="flowNode ${cls}"><div class="flowIcon">${escapeHtml(icon)}</div><div><span>${escapeHtml(title)}</span><b>${escapeHtml(value)}</b><small>${escapeHtml(subtitle)}</small></div></div>`;
    }
    flowLine(label, value, cls = '') {
      return `<div class="flowLine ${cls}"><i></i><span>${escapeHtml(label)}</span><b>${escapeHtml(value)}</b></div>`;
    }
    connectorCard(rt, charger) {
      const id = charger.asset_id || charger.connection_asset_id || '';
      const consumerId = String(charger.connected_consumer_id || '');
      const connectionState = String(charger.connection_state || '');
      const operatingState = String(charger.operating_state || '');
      const power = asNumber(charger.physical_power_kw);
      const powerText = power === null ? '—' : fmtKw(power);
      const consumerName = consumerId ? String(rt.assetName(consumerId) || '').trim() : '';
      const relationLabel = consumerName || (consumerId ? 'Connected vehicle' : 'No vehicle connected');
      const statusLabel = operatingState ? human(operatingState) : connectionState && !/asset[_\s-]?connected/i.test(connectionState) ? human(connectionState) : '';
      const context = [relationLabel, statusLabel].filter(Boolean).join(' · ');
      const visual = rt.resolveVisualRef(charger.visual_ref, 'card');
      const art = `<div class="flowAssetVisual">${visual?.url ? `<img src="${escapeHtml(visual.url)}" alt="" style="filter:${escapeHtml(visual.filter || 'none')}">` : ''}</div>`;
      return `<div class="flowConnectionCard">${art}<div><b>${escapeHtml(charger.display_name || rt.assetName(id) || human(id))}</b><span>${escapeHtml(context || 'Connection state unavailable')}</span></div><strong>${escapeHtml(powerText)}</strong></div>`;
    }
    consumerCard(rt, consumer) {
      const id = consumer.asset_id;
      const power = asNumber(firstDefined(consumer.physical_power_kw, consumer.power_kw, consumer.current_power_kw, consumer.actual_power_kw));
      const powerText = power === null ? '—' : fmtKw(power);
      const operating = firstDefined(consumer.operating_state, consumer.state, rt.value(`${id}.operating_state`, null));
      const active = asBool(firstDefined(consumer.active, rt.value(`${id}.active`, false)));
      const charging = asBool(firstDefined(consumer.charging, rt.value(`${id}.charging`, false))) || /charging/i.test(String(operating || ''));
      const connectionState = String(firstDefined(consumer.connection_state, '') || '').trim().toLowerCase();
      const connected = asBool(firstDefined(consumer.connected, rt.value(`${id}.connected`, false)))
        || ['connected','asset_connected'].includes(connectionState);
      const available = !/unavailable|offline|disconnected/i.test(String(firstDefined(consumer.availability_state, '')));
      const charger = firstDefined(
        consumer.effective_charger,
        consumer.effective_connection_id,
        consumer.assigned_connection_id,
        consumer.physical_connection_id,
        consumer.charger_asset_id,
        consumer.connection_asset_id,
        consumer.execution_target_asset_id,
        ''
      );
      const requested = asNumber(firstDefined(consumer.requested_power_kw_effective, consumer.requested_power_kw));
      const state = charging ? 'Charging' : active || (power !== null && power > 0.05) ? 'Active' : connected ? 'Connected' : available ? 'Available' : 'Unavailable';
      const chargerDisplay = String(firstDefined(
        consumer.effective_charger_display_name,
        consumer.charger_display_name,
        consumer.connection_display_name,
        consumer.physical_connection_display_name,
        charger ? rt.assetName(charger) : '',
        ''
      ) || '').trim();
      const relation = charger ? this.userRelationshipLabel(chargerDisplay, 'Assigned charger') : '';
      const visual = rt.resolveVisualRef(consumer.visual_ref, 'card');
      const art = `<div class="flowAssetVisual">${visual?.url ? `<img src="${escapeHtml(visual.url)}" alt="" style="filter:${escapeHtml(visual.filter || 'none')}">` : ''}</div>`;
      const energyNeed = this.targetEnergyForAsset(id, consumer);
      const display = escapeHtml(consumer.display_name || rt.assetName(id) || human(id));
      const chargerId = String(charger || '').trim();
      const chargerPath = chargerId ? (rhiUxResolveDomainAssetNavigation('rhi_mobility',chargerId) || rhiUxResolveDomainAssetNavigation('mobility',chargerId)) : '';
      const sourceKind = String(firstDefined(consumer.source_asset_kind,consumer.asset_type,'') || '').toLowerCase();
      const consumerPath = rt.sourceAssetNavigation(consumer) || (/vehicle|car/.test(sourceKind)
        ? (rhiUxResolveDomainAssetNavigation('rhi_mobility',id) || rhiUxResolveDomainAssetNavigation('mobility',id)) : '');
      const connection = chargerId ? (chargerPath
        ? `<button type="button" class="rhiFlowLinkedAsset" data-source-asset-nav="${escapeHtml(chargerPath)}" aria-label="Open charger details">${escapeHtml(chargerDisplay || rt.assetName(chargerId) || 'Charger')} <span aria-hidden="true">›</span></button>`
        : `<span>${escapeHtml(chargerDisplay || rt.assetName(chargerId) || 'Charger')}</span>`)
        : '<span>No charger identified</span>';
      return `<article class="flowPhysicalConsumerCard rhiFlowConsumerCard">
        <div class="rhiFlowConsumerIdentity">${art}<div><b>${display}</b><small>${escapeHtml(state)}</small></div></div>
        <div class="rhiFlowConsumerFacts">
          <span><small>Energy needed</small><b>${escapeHtml(energyNeed === null ? '—' : fmtKwh(energyNeed))}</b></span>
          <span><small>Power now</small><b>${escapeHtml(powerText)}</b></span>
          <span><small>Requested power</small><b>${escapeHtml(requested === null ? '—' : fmtKw(requested))}</b></span>
        </div>
        <div class="rhiFlowConsumerRelation"><small>Charging via</small>${connection}</div>
        ${consumerPath ? `<button type="button" class="rhiFlowConsumerDetails" data-source-asset-nav="${escapeHtml(consumerPath)}">Details <span aria-hidden="true">›</span></button>` : ''}
      </article>`;
    }
    flowConsumers(rt, connectionSnapshot = { rows:[] }) {
      const domain = this.flexibleAssetDomain(rt);
      const snapshotRows = asArray(connectionSnapshot?.rows);
      const chargerIds = new Set(
        snapshotRows
          .map(row => String(firstDefined(row.connection_asset_id, row.asset_id, row.charger_id, '') || '').trim())
          .filter(Boolean)
      );
      const connectedConsumerIds = new Set(
        snapshotRows
          .map(row => String(firstDefined(row.connected_consumer_id, row.connected_asset_id, row.target_asset_id, '') || '').trim())
          .filter(Boolean)
      );
      const isChargerRow = row => {
        const id = String(firstDefined(row?.asset_id, row?.connection_asset_id, '') || '').trim();
        const types = [row?.asset_type,row?.object_class,row?.source_asset_kind,row?.energy_asset_role,row?.ux_asset_type,row?.participation_state].map(v=>String(v || '').trim().toLowerCase());
        return row?.infrastructure_only === true || chargerIds.has(id)
          || types.some(type=>/(^|_)(charger|charging_point|charge_point|infrastructure_only)(_|$)/.test(type));
      };
      const byId = new Map();

      const addConsumer = row => {
        if (!row || typeof row !== 'object') return;
        const id = String(firstDefined(row.asset_id, row.flexible_asset_id, row.target_asset_id, '') || '').trim();
        if (!id || isChargerRow({...row,asset_id:id})) return;
        const vm = domain.byId(id);
        if (vm?.isDisabled || vm?.isStorage || vm?.isInfrastructure) return;
        const materialized = vm?.raw ? { ...row, ...vm.raw, asset_id:id } : { ...row, asset_id:id };
        byId.set(id, { ...(byId.get(id) || {}), ...materialized });
      };

      // The physical charging chain is directional:
      // connection.asset_id (charger infrastructure) -> connected_consumer_id (vehicle/load).
      // A charger can never become the Physical consumers row when a target exists.
      for (const connection of snapshotRows) {
        const consumerId = String(firstDefined(
          connection.connected_consumer_id,
          connection.connected_asset_id,
          connection.target_asset_id,
          ''
        ) || '').trim();
        if (!consumerId) continue;
        const vm = domain.byId(consumerId);
        const asset = vm?.raw || rt.asset(consumerId) || {};
        addConsumer({
          ...asset,
          asset_id:consumerId,
          connection_state:firstDefined(asset.connection_state, connection.connection_state, ''),
          effective_connection_id:firstDefined(asset.effective_connection_id, connection.connection_asset_id, connection.asset_id, ''),
          physical_connection_id:firstDefined(asset.physical_connection_id, connection.connection_asset_id, connection.asset_id, ''),
          visual_ref:firstDefined(asset.visual_ref, connection.connected_consumer_visual_ref, ''),
          // A charger power measurement is not vehicle power without physical identity proof.
          // Keep charger telemetry in the connection diagnostics; this consumer
          // row may show only its own canonical asset-scoped power evidence.
          physical_power_kw:firstDefined(asset.physical_power_kw, asset.power_kw, asset.current_power_kw, asset.actual_power_kw)
        });
      }

      // Preserve other genuine non-charger flexible loads (pool, thermal loads, etc.)
      // while excluding Mobility's unassigned-charger fallback from this UX section.
      domain.physicalFlowParticipants().forEach(vm => addConsumer(vm.raw));

      const explicit = rt.assets().filter(a => {
        const id = String(a.asset_id || '');
        if (!id || isChargerRow(a)) return false;
        const vm = domain.byId(id);
        if (vm?.isDisabled || vm?.isStorage) return false;
        return String(a.asset_type || '').toLowerCase() === 'consumer'
          && String(a.parent_asset_id || '').toLowerCase() === 'consumer';
      });
      explicit.forEach(addConsumer);

      // When an explicit charger->consumer target exists it is the physical chain
      // authority. This also ensures assigned vehicles remain visible while idle.
      connectedConsumerIds.forEach(id => {
        if (byId.has(id)) return;
        const vm = domain.byId(id);
        const asset = vm?.raw || rt.asset(id) || {};
        addConsumer({ ...asset, asset_id:id });
      });

      return [...byId.values()];
    }
    canonicalConnectionSnapshot(rt) {
      // Connection materialization is projection-only: consume explicit public
      // V2 asset links/relationships and asset-scoped measurements. Do not infer
      // charger assignments from names and do not recalculate Energy aggregates.
      const rows = new Map();
      const assetType = asset => String(firstDefined(asset?.asset_type, asset?.object_class, '') || '').trim().toLowerCase();
      const isCharger = asset => /(^|_)(charger|charging_point|charge_point)(_|$)/.test(assetType(asset));
      const materialize = (chargerId, consumerId = '', relationship = {}) => {
        const chargerKey = String(chargerId || '').trim();
        const consumerKey = String(consumerId || '').trim();
        if (!chargerKey || rows.has(chargerKey)) return;
        // One physical charger is one connection row. The producer/public row is
        // materialized first and remains authoritative over Energy-local fallbacks.
        const charger = { ...objectFrom(rt.asset(chargerKey) || {}), ...objectFrom(relationship) };
        const consumer = consumerKey
          ? (rt.asset(consumerKey) || this.flexibleAssetDomain(rt).byId(consumerKey)?.raw || {})
          : {};
        const power = asNumber(firstDefined(
          charger.actual_power_kw,
          charger.current_power_kw,
          charger.power_kw,
          rt.number(`${chargerKey}.actual_power_kw`),
          rt.number(`${chargerKey}.current_power_kw`),
          rt.number(`${chargerKey}.power_kw`)
        ));
        const row = {
          ...charger,
          asset_id:chargerKey,
          connection_asset_id:chargerKey,
          connected_consumer_id:consumerKey,
          connected_consumer_visual_ref:String(firstDefined(consumer.visual_ref, '') || ''),
          connection_state:String(firstDefined(
            relationship.connection_state,
            relationship.state,
            charger.connection_state,
            consumer.connection_state,
            consumer.connected === true ? 'connected' : ''
          ) || ''),
          operating_state:String(firstDefined(
            charger.operating_state,
            charger.operation_state,
            consumer.operating_state,
            consumer.operation_state,
            ''
          ) || ''),
          physical_power_kw:power,
          // Preserve producer-owned visual identity from the canonical connection
          // row; Energy-local projections may only fill it when the producer omitted it.
          visual_ref:String(firstDefined(relationship.visual_ref, charger.visual_ref, '') || ''),
          source_relationship_id:String(firstDefined(relationship.relationship_id, relationship.id, '') || '')
        };
        rows.set(chargerKey, row);
      };

      // Prefer the exact producer-owned connection rows published by Energy V2.
      // This is the canonical cross-domain topology boundary and remains visible
      // even at 0 kW / idle.
      asArray(rt.canonicalProduct().connections).forEach(connection => {
        materialize(
          firstDefined(connection.asset_id, connection.connection_asset_id, ''),
          firstDefined(connection.connected_asset_id, connection.connected_consumer_id, ''),
          connection
        );
      });

      // Flexible assets may publish their exact execution/charger target directly.
      this.flexibleAssetDomain(rt).all()
        .filter(vm => !vm.isDisabled && !vm.isStorage)
        .forEach(vm => {
          const asset = vm.raw || {};
          const chargerId = firstDefined(
            asset.effective_charger,
            asset.effective_connection_id,
            asset.assigned_connection_id,
            asset.physical_connection_id,
            asset.charger_asset_id,
            asset.connection_asset_id,
            asset.execution_target_asset_id,
            ''
          );
          if (chargerId) materialize(chargerId, vm.id, { connection_state:asset.connection_state });
        });

      // Public connected_to relationships remain authoritative when present.
      rt.connectedRelationships().forEach(relationship => {
        const fromId = String(firstDefined(relationship.from_asset_id, relationship.source_asset_id, '') || '');
        const toId = String(firstDefined(relationship.to_asset_id, relationship.target_asset_id, '') || '');
        if (!fromId || !toId) return;
        const from = rt.asset(fromId) || {};
        const to = rt.asset(toId) || {};
        if (isCharger(from)) materialize(fromId, toId, relationship);
        else if (isCharger(to)) materialize(toId, fromId, relationship);
      });

      // Topology is not the same as active power flow: keep published chargers
      // visible when idle or currently unassigned.
      rt.assets().filter(isCharger).forEach(charger => {
        const id=String(charger.asset_id || '');
        if (!id) return;
        if (!rows.has(id)) materialize(id, '', charger);
      });

      const projected = Object.freeze([...rows.values()].map(row => Object.freeze(row)));
      const observedAt = projected.map(row => String(firstDefined(row.observed_at, row.updated_at, '') || '')).filter(Boolean).sort().pop() || '';
      return Object.freeze({
        available:rt.canonicalProduct().available === true,
        rows:projected,
        // Deliberately not derived from row power: Energy aggregate truth stays backend-owned.
        totalPowerKw:null,
        observedAt,
        reason:projected.length ? '' : 'No charging connection is currently available.',
        source:'RHI_ENERGY_CANONICAL_PROPERTY_V2'
      });
    }
    // HACS cannot enforce dashboard-card dependencies at download time.
    // Check the actual browser registration on first render and whenever Flow is opened.
    nativeFlowDiagram(current, physicalFlow) {
      // First-party visual flow: Energy's verified directions/values only.
      // Edges represent a bus boundary, not inferred per-device allocation.
      const measured = value => {
        const n = asNumber(value);
        return n !== null && n >= 0 ? n : null;
      };
      const node = (label, power, tone = '', detail = '') => {
        const value = measured(power);
        return `<div class="rhiNativeFlowNode ${escapeHtml(tone)}">
          <div><b>${escapeHtml(label)}</b>${detail ? `<small>${escapeHtml(detail)}</small>` : ''}</div>
          <strong>${escapeHtml(value === null ? 'Unavailable' : fmtKw(value))}</strong>
        </div>`;
      };
      const sources = [];
      const demand = [];
      const solar = measured(current?.solar?.powerKw);
      const gridImport = current?.grid?.direction === 'importing'
        ? measured(current?.grid?.importPowerKw) : null;
      const gridExport = current?.grid?.direction === 'exporting'
        ? measured(current?.grid?.exportPowerKw) : null;
      const battery = current?.battery || {};
      const discharge = battery.direction === 'out_of_storage'
        ? measured(battery.dischargePowerKw) : null;
      const charge = battery.direction === 'into_storage'
        ? measured(battery.chargePowerKw) : null;
      if (solar !== null) sources.push(node('Solar production',solar,'solar'));
      if (gridImport !== null) sources.push(node('Grid import',gridImport,'grid'));
      if (discharge !== null) sources.push(node('Home Battery discharge',discharge,'battery'));
      const home = measured(physicalFlow?.homeConsumptionKw);
      const flexible = measured(physicalFlow?.flexibleLoadsKw);
      if (home !== null) demand.push(node('Home consumption',home,'home'));
      if (flexible !== null && flexible > 0.05) demand.push(node('Flexible loads',flexible,'flexible'));
      if (charge !== null && charge > 0.05) demand.push(node('Home Battery charging',charge,'battery','Separate storage demand'));
      if (gridExport !== null && gridExport > 0.05) demand.push(node('Grid export',gridExport,'grid'));
      const site = measured(physicalFlow?.siteConsumptionKw);
      return `<section class="rhiNativeFlowDiagram" data-rhi-native-flow-diagram
        aria-label="Measured live energy flow">
        <div class="rhiNativeFlowStage">
          <div class="rhiNativeFlowLane"><h3>Supply</h3>
            ${sources.join('') || '<p class="muted">Supply measurements unavailable</p>'}</div>
          <div class="rhiNativeFlowBus"><span aria-hidden="true">→</span>
            <div class="rhiNativeFlowHub"><small>Measured site demand</small>
              <strong>${escapeHtml(site === null ? 'Unavailable' : fmtKw(site))}</strong>
              <small>Home energy bus</small></div>
            <span aria-hidden="true">→</span></div>
          <div class="rhiNativeFlowLane"><h3>Consumption & export</h3>
            ${demand.join('') || '<p class="muted">Demand measurements unavailable</p>'}</div>
        </div>
        <p class="rhiNativeFlowDisclaimer">Shown power and directions are reported by Energy.
          No individual source-to-consumer allocation is inferred.</p>
      </section>`;
    }
    nativeFlowEvidence(current, physicalFlow) {
      // Native fallback consumes already projected, canonical measured values.
      // Never calculate physical balance, invent a missing direction or sum
      // the charger's power again with the vehicle's flexible consumption.
      const labels = [
        [rhiEnergyT(this._hass,'flow.native_solar',{},'Solar production'), current?.solar?.powerKw],
        [rhiEnergyT(this._hass,'flow.native_grid_import',{},'Grid import'), current?.grid?.importPowerKw],
        [rhiEnergyT(this._hass,'flow.native_grid_export',{},'Grid export'), current?.grid?.exportPowerKw],
        [rhiEnergyT(this._hass,'flow.native_site',{},'Site consumption'), physicalFlow?.siteConsumptionKw],
        [rhiEnergyT(this._hass,'flow.native_home',{},'Home consumption'), physicalFlow?.homeConsumptionKw],
        [rhiEnergyT(this._hass,'flow.native_flexible',{},'Flexible loads'), physicalFlow?.flexibleLoadsKw],
        [rhiEnergyT(this._hass,'flow.native_battery',{},'Battery power'), current?.battery?.valueAvailable === true ? current.battery.displayPowerKw : null]
      ];
      const rows = labels.map(([label, raw]) => {
        const value = asNumber(raw);
        return `<div class="meteringCleanRow"><div><b>${escapeHtml(label)}</b></div>
          <strong>${escapeHtml(value === null ? rhiEnergyT(this._hass,'common.not_available',{},'Not available') : fmtKw(value))}</strong></div>`;
      }).join('');
      return `<div class="rhiFlowNativeEvidence" data-rhi-native-flow role="group" aria-label="${escapeHtml(rhiEnergyT(this._hass,'flow.native_title',{},'Measured energy flow'))}">
        <div class="flowHeader"><div><h3>${escapeHtml(rhiEnergyT(this._hass,'flow.native_title',{},'Measured energy flow'))}</h3><p>${escapeHtml(rhiEnergyT(this._hass,'flow.native_desc',{},'Direct measured values; unavailable directions remain unavailable.'))}</p></div></div>
        <div class="meteringCleanRows">${rows}</div>
      </div>`;
    }
    powerFlowDependencyStatus() {
      const tag = 'power-flow-card-plus';
      if (typeof customElements === 'undefined') return 'checking';
      return customElements.get(tag) ? 'ready' : (this._powerFlowProbeSettled ? 'missing' : 'checking');
    }
    powerFlowDependencyNotice() {
      const status = this.powerFlowDependencyStatus();
      if (status === 'ready') return '';
      const docs = 'https://github.com/flixlix/power-flow-card-plus';
      return `<section class="panel rhiFlowDependencyNotice" role="status" aria-live="polite">
        <strong>Power Flow Card Plus · ${status==='checking'?'Checking':'Not loaded'}</strong>
        <p>${status==='checking'
          ? 'Checking whether the installed card has registered with Home Assistant.'
          : 'The Power Flow Card Plus frontend resource is missing or has not loaded in this browser. The existing energy information remains available.'}</p>
        <p>In HACS, verify <b>Power Flow Card Plus</b> is installed under Dashboard and that its JavaScript resource is loaded. Then refresh this dashboard.</p>
        <a href="${docs}" target="_blank" rel="noopener noreferrer">Dependency and installation instructions</a>
      </section>`;
    }

    async mountPowerFlowCard() {
      if (this.view !== 'flow' || this.powerFlowDependencyStatus() !== 'ready') return;
      const host = this.shadowRoot?.querySelector('[data-rhi-power-flow-host]');
      if (!host || (host.firstElementChild && !host.firstElementChild.hasAttribute('data-rhi-native-flow')) || host.dataset.loading === 'true') return;
      const config = buildRhiPowerFlowCardConfig(this.runtime());
      if (!config) {
        // The native measurements remain visible when optional third-party
        // card mapping is absent or ambiguous. No synthetic entity IDs.
        return;
      }
      host.dataset.loading='true';
      try {
        if (typeof window.loadCardHelpers !== 'function') throw new Error('Home Assistant card helpers unavailable');
        const helpers = await window.loadCardHelpers();
        if (!host.isConnected || this.view !== 'flow') return;
        const card = await helpers.createCardElement(config);
        card.hass = this._hass;
        host.replaceChildren(card);
      } catch (error) {
        if (host.isConnected) {
          host.dataset.powerFlowError = String(error?.message || 'card_unavailable');
          // Keep native source-backed Flow rather than replacing it with an
          // empty failure message when the optional HACS card throws.
        }
      } finally {
        delete host.dataset.loading;
      }
    }

    flow(rt) {
      // The native measured flow must survive faults in optional diagrams,
      // detailed consumers, relationships or third-party card adapters.
      this._flowRenderFailure = '';
      try {
        return this.renderFlowContent(rt);
      } catch (error) {
        this._flowRenderFailure = String(error?.message || error || 'unknown_flow_error');
        console.error('[RHI Energy UX] Flow detail renderer failed', error);
        const current = this.currentEnergyModel(rt);
        const consumption = readLiveConsumptionContract(rt.contractGateway());
        const page = this.buildPageViewModel(rt, 'flow');
        return this.tabExperienceHeader(rt, 'flow', page) +
          '<div class="flowPage"><section class="panel rhiFlowRenderWarning" role="alert">' +
          '<h2>Some flow details are unavailable</h2><p>Measured energy values remain available. ' +
          'The detail renderer reported an error; check browser diagnostics.</p></section>' +
          this.nativeFlowDiagram(current, consumption) +
          this.nativeFlowEvidence(current, consumption) + '</div>';
      }
    }
    renderFlowContent(rt) {
      const pageVm = this.buildPageViewModel(rt, 'flow');
      const current = this.currentEnergyModel(rt);
      const solar = current.solar.powerKw;
      const gridImport = current.grid.importPowerKw;
      const gridExport = current.grid.exportPowerKw;
      const battery = current.battery;
      // Only a validated charge/discharge pair may draw a directional battery
      // flow arrow. The battery itself must never disappear from Flow.
      const batteryFlowIntegrated = Boolean(buildRhiPowerFlowCardConfig(rt)?.entities?.battery);
      const connectionSnapshot = this.canonicalConnectionSnapshot(rt);
      const consumerInventory = new Map(this.flexibleAssetDomain(rt).consumerFacing().map(vm=>[vm.id,vm.raw || {}]));
      // Merge canonical consumer inventory and physical connection evidence by real consumer ID.
      // Charging infrastructure is never an additional consumer or summed power.
      this.flowConsumers(rt, connectionSnapshot).forEach(row => {
        const id = String(row.asset_id || '');
        if (id) consumerInventory.set(id,{...(consumerInventory.get(id)||{}),...row});
      });
      const rawConsumers = [...consumerInventory.values()];
      const rawChargers = connectionSnapshot.rows;
      const physicalFlow = buildPhysicalFlowViewModel(rt, rt.contractGateway(), rawConsumers, rawChargers, connectionSnapshot);
      const siteConsumption = physicalFlow.siteConsumptionKw;
      const homeConsumption = physicalFlow.homeConsumptionKw;
      const flexibleLoadsPower = physicalFlow.flexibleLoadsKw;
      const consumers = physicalFlow.consumers;
      const chargers = physicalFlow.connections;
      const connectionPower = physicalFlow.connectionPowerKw;
      const homeBus = rt.asset('home_bus') || { display_name: 'Home Bus' };
      const switchboard = rt.asset('main_switchboard') || { display_name: 'Main Switchboard' };
      return `${this.tabExperienceHeader(rt,'flow',pageVm)}<div class="flowPage">\n        <section class="panel rhiPowerFlowPanel">
          <div class="flowHeader"><div><h2>Live power flow</h2><p>Native measured energy flow. Missing values and directions are never estimated.</p></div></div>
          ${this.nativeFlowDiagram(current, physicalFlow)}
          <details class="rhiOptionalPowerFlow"><summary>Optional detailed Power Flow Card Plus</summary>
            ${this.powerFlowDependencyNotice()}
            <div class="rhiPowerFlowHost rhiUxChartViewport" data-rhi-power-flow-host role="region" aria-label="Optional external energy flow diagram">${this.nativeFlowEvidence(current, physicalFlow)}</div>
          </details>
          <div class="rhiFlowBatteryPresence" aria-label="Home Battery on energy flow">
            <div class="rhiFlowBatteryIdentity"><span class="rhiFlowBatteryIcon" aria-hidden="true">▣</span><div><b>Home Battery</b><small>${escapeHtml(battery.health === 'OK' ? battery.label : 'Measurement unavailable')}</small></div></div>
            <div class="rhiFlowBatteryFacts"><span><small>Power now</small><b>${escapeHtml(battery.valueAvailable ? fmtKw(battery.displayPowerKw) : '—')}</b></span><span><small>State of charge</small><b>${escapeHtml(battery.socPct === null ? '—' : fmtPct(battery.socPct))}</b></span></div>
            <span class="rhiFlowBatteryProof">${batteryFlowIntegrated ? 'Direction measured · shown in flow above' : 'Direction not proven · no animated battery flow'}</span>
            <button type="button" data-tab-target="battery" class="rhiFlowBatteryDetails">Battery details <span aria-hidden="true">›</span></button>
          </div>
          <p class="rhiFlowMeasurementNote">Only direction-compatible battery sensors are allowed to animate. Charger and vehicle power are never added together.</p>
        </section>
        <div class="rhiFlowHistoryGrid" aria-label="Measured energy history">
          ${['grid_import','grid_export','home','flexible'].map(kind => this.energyHistorySection(rt,kind)).join('')}
        </div>
        <section class="panel rhiFlowAllLoads">
          <div class="flowHeader"><div><h2>Flexible consumers</h2><p>Real consumers only. Need, actual power and requested power are separate; a charger is a connection, not an extra load.</p></div></div>
          <div class="rhiFlowConsumerList">${consumers.map(consumer => this.consumerCard(rt,consumer)).join('') || '<div class="empty compact"><b>No flexible consumers published</b><span>No verified flexible-load consumer is available.</span></div>'}</div>
        </section>
        <details class="panel rhiFlowConnectionDiagnostics">
          <summary>Charging connection diagnostics</summary>
          <p>Physical charger interfaces and published assignments. They are not additional consumers.</p>
          ${chargers.map(charger=>this.connectorCard(rt,charger)).join('') || '<div class="empty compact"><b>No charging connection evidence</b><span>Connection information is currently unavailable.</span></div>'}
        </details>
      </div>`;
    }
    propertyRow(row, label = null, formatter = null) {
      const title = label || row.display_name || human(row.key || row.property_key || row.asset_id || 'Property');
      const value = formatter ? formatter(rowValue(row, null), row) : rowDisplayValue(row);
      const state = rowState(row);
      return `<div class="propertyRow ${escapeHtml(state)}"><div><b>${escapeHtml(title)}</b></div><strong>${escapeHtml(value)}</strong><small class="qs ${escapeHtml(state)}">${escapeHtml(rowStatusLabel(row))}</small></div>`;
    }
    commandRow(rt, command) {
      const state = rt.commandState(command);
      const reason = rt.commandReasonObject(command);
      const label = this.userSafeProductText(command.label || human(command.role || ''),'Action');
      const message = this.userSafeReason(reason.message || reason.code,'Action is available');
      return `<div class="commandRow ${escapeHtml(state)}"><div><b>${escapeHtml(label)}</b></div><strong>${escapeHtml(this.productStateLabel(state,human(state)))}</strong><small>${escapeHtml(message)}</small></div>`;
    }
    visibleProfileValue(...values) {
      const value = firstDefined(...values);
      if (value === undefined || value === null || value === '') return '';
      const text = String(value).trim();
      if (!text || /^not[_\s-]?published$/i.test(text) || /^unknown$/i.test(text)) return '';
      return human(value);
    }
    policyLine(label, value) {
      const display = this.visibleProfileValue(value);
      if (!display) return '';
      return `<div class="profilePolicyLine"><span>${escapeHtml(label)}</span><b>${escapeHtml(display)}</b></div>`;
    }
    profileKind(profile = {}) {
      return String(profile.profile_id || profile.strategy_profile_id || profile.profile_type || profile.asset_type || '').toLowerCase();
    }
    profileSettingsTopic(profile = {}) {
      return String(firstDefined(profile.topic_label, profile.display_name, profile.profile_label, '') || '').trim()
        || this.profileUserLabel(profile);
    }
    profileUserLabel(profile = {}) {
      const explicit = firstDefined(profile.user_label, profile.profile_user_label, profile.display_label, profile.profile_label, profile.display_name, profile.name, profile.label, '');
      if (explicit) return human(explicit);
      const key = this.profileKind(profile);
      const map = {
        vehicle: 'Vehicle charging',
        home_battery: 'Home battery reserve',
        battery: 'Home battery reserve',
        generic_flexible_load: 'Generic flexible loads',
        thermal_flexible_load: 'Thermal loads',
        outdoor_flexible_load: 'Outdoor loads',
        solar_surplus: 'Solar surplus allocation',
        resilience: 'Resilience'
      };
      return map[key] || human(key || 'Energy strategy');
    }
    profileUserDescription(profile = {}) {
      const explicit = firstDefined(profile.user_description, profile.description, profile.summary, profile.user_summary_label, '');
      if (explicit) return human(explicit);
      const key = this.profileKind(profile);
      const map = {
        vehicle: 'Targets, deadline and energy source rules for vehicle charging.',
        home_battery: 'Reserve, charge policy and support rules for home storage.',
        battery: 'Reserve, charge policy and support rules for home storage.',
        generic_flexible_load: 'Default policy for Energy-controllable flexible loads.',
        thermal_flexible_load: 'Policy for flexible thermal loads such as heating or jacuzzi.',
        outdoor_flexible_load: 'Policy for flexible outdoor loads such as pool or irrigation.',
        solar_surplus: 'How excess solar should be allocated before export.',
        resilience: 'How Energy protects essential goals and reserve during resilience mode.'
      };
      return map[key] || 'Type-level Energy policy. Planning decides the actual outcome.';
    }
    profileTargetSummary(profile = {}) {
      const unit = this.visibleProfileValue(profile.target_unit || profile.unit || '');
      const min = firstDefined(profile.minimum_target_value, profile.minimum_target, profile.minimum);
      const preferred = firstDefined(profile.preferred_target_value, profile.preferred_target, profile.preferred);
      const max = firstDefined(profile.maximum_useful_value, profile.maximum_target, profile.maximum);
      const parts = [];
      if (min !== undefined && min !== null && min !== '') parts.push(`minimum ${min}${unit}`);
      if (preferred !== undefined && preferred !== null && preferred !== '') parts.push(`preferred ${preferred}${unit}`);
      if (max !== undefined && max !== null && max !== '') parts.push(`maximum ${max}${unit}`);
      return parts.join(' · ');
    }
    profileFieldLabel(row = {}) {
      const explicit = firstDefined(row.user_label, row.display_name, row.label, row.title, '');
      if (explicit) return human(explicit);
      const key = String(row.field_key || row.key || row.property_key || '').split('.').pop().toLowerCase();
      const labels = {
        minimum_target_value: 'Minimum target', minimum_target: 'Minimum target',
        preferred_target_value: 'Preferred target', preferred_target: 'Preferred target',
        maximum_useful_value: 'Maximum useful', maximum_target: 'Maximum useful',
        deadline_time: 'Default deadline', deadline: 'Default deadline',
        grid_policy: 'Grid use', grid_use_policy: 'Grid use',
        solar_policy: 'Solar use', surplus_policy: 'Solar surplus', battery_policy: 'Battery support',
        confidence_policy: 'Confidence', confidence: 'Confidence',
        minimum_run_minutes: 'Minimum run time', minimum_off_minutes: 'Minimum off time', adjust_deadband_kw: 'Deadband',
        temporary_import_allowed: 'Temporary import', temporary_import_limit_kw: 'Temporary import limit',
        reserve_target_pct: 'Reserve target', protected_reserve_pct: 'Protected reserve', essentiality_level: 'Essentiality', shed_allowed: 'Can be shed',
        mode: 'Mode', energy_control_mode: 'Mode', objective_mode: 'Objective'
      };
      return labels[key] || human(key || 'Setting');
    }
    profileFieldCategory(row = {}) {
      const key = String(row.field_key || row.key || row.property_key || row.display_name || '').toLowerCase();
      if (/minimum|preferred|maximum|target|deadline|objective|mode/.test(key)) return 'goal';
      if (/grid|solar|surplus|battery|source/.test(key)) return 'source';
      if (/confidence|stability|run|off|deadband|import/.test(key)) return 'stability';
      if (/reserve|essential|shed|resilience/.test(key)) return 'resilience';
      return 'other';
    }
    profileControlForRow(row) {
      const label = this.profileFieldLabel(row);
      const editor = String(row.editor || row.ui_control || row.control || row.value_type || '').toLowerCase();
      if (editor.includes('toggle') || editor.includes('boolean') || editor === 'bool') return this.editableToggleControl(row, label);
      if (editor.includes('time')) return this.editableTimeControl(row, label);
      if (editor.includes('select') || editor.includes('enum') || allowedValuesForRow(row).length) return this.editableSelectControl(row, label);
      if (editor.includes('slider') || editor.includes('range')) return this.editableRangeControl(row, label);
      return this.editableNumberControl(row, label);
    }
    profileEditableRows(rt, profile = {}) {
      const unique = [];
      rt.strategyProfileEditableFieldRows(profile).forEach(row => {
        const key = this.propertyKeyFor(row);
        if (key && !unique.some(existing => this.propertyKeyFor(existing) === key)) unique.push(row);
      });
      return unique.slice(0, 24);
    }
    strategyReferenceForRow(row = {}) {
      const recommended = firstDefined(row.recommended_value, row.recommendation_value, row.preferred_value, row.suggested_value, null);
      const reason = firstDefined(row.recommendation_reason, row.guidance, row.user_guidance, row.description, row.help_text, '');
      const defaultValue = firstDefined(row.default_value, row.default, null);
      if (recommended !== null && recommended !== undefined && recommended !== '') {
        return { value: row.unit ? `${recommended} ${row.unit}` : human(recommended), text: reason ? String(reason) : 'Recommended by Energy.' };
      }
      if (defaultValue !== null && defaultValue !== undefined && defaultValue !== '') {
        return { value: row.unit ? `${defaultValue} ${row.unit}` : human(defaultValue), text: reason ? String(reason) : 'Default value.' };
      }
      return reason ? { value: '', text: String(reason) } : null;
    }
    strategyValueForRow(row = {}) {
      const value = Object.prototype.hasOwnProperty.call(this.editDrafts, String(row.key || row.property_key || row.field_key || ''))
        ? this.editDrafts[String(row.key || row.property_key || row.field_key || '')]
        : rowValue(row, null);
      if (value === null || value === undefined || value === '') return '—';
      if (typeof value === 'boolean') return value ? 'Yes' : 'No';
      return `${human(value)}${row.unit ? ` ${row.unit}` : ''}`;
    }
    strategyTable(rt, profile = {}, options = {}) {
      const id = String(profile.profile_id || options.profileId || 'strategy_profile');
      const rows = this.profileEditableRows(rt, profile);
      const editing = options.alwaysEditable === true || this.strategyEditProfileId === id;
      const changed = rows.filter(row => Object.prototype.hasOwnProperty.call(this.editDrafts, String(row.key || row.property_key || row.field_key || '')));
      const title = options.title || this.profileUserLabel(profile);
      const description = options.description || this.profileUserDescription(profile);
      const rowHtml = rows.map(row => {
        const key = String(row.key || row.property_key || row.field_key || '');
        const label = this.profileFieldLabel(row);
        const ref = this.strategyReferenceForRow(row);
        const changedClass = Object.prototype.hasOwnProperty.call(this.editDrafts, key) ? ' changed' : '';
        const value = editing ? this.profileControlForRow({ ...row, __strategyProfileField: true, profile_id: row.profile_id || id }) : `<span class="strategyReadValue">${escapeHtml(this.strategyValueForRow(row))}</span>`;
        const guidance = ref ? `<div class="strategyGuidance"><i>${escapeHtml(ref.value ? `${ref.value}${ref.text ? ` · ${ref.text}` : ''}` : ref.text)}</i></div>` : '';
        return `<div class="strategyTableRow${changedClass}"><div class="strategyPrimaryRow"><span class="strategySetting">${escapeHtml(label)}</span><div class="strategyValue">${value}</div></div>${guidance}</div>`;
      }).join('');
      const actions = editing
        ? `<span class="strategyChangeCount">${changed.length ? `${changed.length} changed` : 'No changes'}</span><button class="strategyTextAction" data-strategy-cancel="${escapeHtml(id)}">Discard</button><button class="strategySaveAction" data-strategy-save="${escapeHtml(id)}"${changed.length ? '' : ' disabled'}>Save</button>`
        : `<button class="strategyTextAction" data-strategy-edit="${escapeHtml(id)}"${rows.length ? '' : ' disabled'}>Edit</button>`;
      return `<section class="panel strategyTablePanel"><div class="strategyTableHead"><div><h2>${escapeHtml(title)}</h2>${description ? `<p>${escapeHtml(description)}</p>` : ''}</div><div class="strategySetActions">${actions}</div></div><div class="strategyTable"><div class="strategyColumnHead"><span>Setting</span><span>Value</span></div>${rowHtml || `<div class="profileNoControls">No adjustable strategy settings are available.</div>`}</div>${options.details || ''}</section>`;
    }
    strategyProfileForDomain(rt, domain) {
      const wanted = String(domain || '').toLowerCase();
      return rt.strategyProfileRows().find(profile => `${profile.profile_id || ''} ${profile.profile_type || ''} ${profile.asset_type || ''} ${profile.display_name || ''}`.toLowerCase().includes(wanted)) || null;
    }
    profileGroup(title, rows = [], staticLines = '') {
      const controls = rows.map(row => this.profileControlForRow(row)).join('');
      const content = `${staticLines || ''}${controls || ''}`;
      if (!content) return '';
      return `<section class="profileSettingGroup"><h3>${escapeHtml(title)}</h3><div class="profileSettingGrid">${content}</div></section>`;
    }
    strategyProfileCard(rt, profile = {}) {
      const id = profile.profile_id || 'strategy_profile';
      const details = this.componentDetailsBlock(`strategy-profile-${id}-details`, 'Diagnostics', `${this.kv('Profile id', id)}${this.kv('Raw profile type', profile.profile_type || profile.asset_type || '—')}${this.kv('Editable fields published', String(this.profileEditableRows(rt, profile).length))}${this.kv('Contract role', profile.contract_role || 'editable_strategy_profile')}${this.kv('Planning outcome source', 'RHI_ENERGY_CANONICAL_PROPERTY_V2.planning')}${this.kv('Command source', 'RHI_ENERGY_CANONICAL_PROPERTY_V2.commands')}${this.kv('Engineer reason', human(profile.engineer_reason || '—'))}`);
      return this.strategyTable(rt, profile, { details, alwaysEditable:true });
    }
    effectivePolicyPreviewCard(rt, strategy = {}) {
      const assetId = strategy.asset_id || strategy.target_asset_id || '';
      const planning = rt.planningOutcomeFor(assetId) || {};
      const profileId = strategy.profile_id || strategy.strategy_profile_id || strategy.profile_type || strategy.asset_type || '';
      const planLabel = planning.user_summary_label || planning.state || 'No plan';
      const mode = human(strategy.mode || strategy.energy_control_mode || '—');
      const asset = assetId ? this.energyAssetContext(rt, rt.asset(assetId) || { ...strategy, asset_id:assetId }) : null;
      const identity = asset ? `<span class="effectivePolicyIdentity">${this.assetVisual(asset,{size:'xs',fallbackIcon:this.flexibleAssetIcon(asset)})}<b>${escapeHtml(rt.assetName(assetId) || human(assetId))}</b></span>` : `<b>${escapeHtml(human(strategy.strategy_id || 'Asset'))}</b>`;
      return `<div class="effectivePolicyRow compact">${identity}<span>${escapeHtml(human(profileId || strategy.policy_profile || 'Not available'))}</span><strong>${escapeHtml(human(planLabel))}</strong>${mode !== '—' ? `<small>${escapeHtml(mode)}</small>` : ''}</div>`;
    }
    strategyIntentCard(rt, intent) {
      const state = intent.state || intent.intent_state || 'observed';
      const power = asNumber(intent.available_power_kw);
      const required = asNumber(intent.required_power_kw);
      const target = intent.target_asset_id ? rt.assetName(intent.target_asset_id) : human(intent.strategy_family || 'Energy');
      const command = intent.recommended_action_id || '';
      return `<div class="intentCard"><div><small>${escapeHtml(human(intent.strategy_family || intent.intent_type || 'Strategy'))}</small><h3>${escapeHtml(human(state))}</h3><p>${escapeHtml(intent.reason || intent.blocked_reason || 'No additional explanation is available.')}</p></div><div class="intentFacts">${this.kv('Target', target)}${this.kv('Available', power === null ? '—' : fmtKw(power))}${this.kv('Required', required === null ? '—' : fmtKw(required))}${this.kv('Command', command ? human(command) : 'No command')}</div></div>`;
    }
    batteryHeroImagePath(assetId, name = '') {
      const key = `${assetId || ''} ${name || ''}`.toLowerCase();
      if (/solaredge|48v|9\.2/.test(key)) return hbEnergyAssetUrl('energy/solaredge_home_battery_48v_9_6.webp');
      if (/byd|lvs|20\.0/.test(key)) return hbEnergyAssetUrl('energy/byd_lvs_20.webp');
      return hbEnergyAssetUrl('heroes/battery-hero.webp');
    }
    batteryChildCard(rt, assetId) {
      const name = rt.assetName(assetId);
      const soc = rt.assetNumber(assetId, 'battery.soc_pct');
      const power = rt.assetNumber(assetId, 'battery.power_kw');
      const available = rt.assetNumber(assetId, 'battery.available_kwh');
      const capacity = rt.assetNumber(assetId, 'battery.capacity_kwh');
      const state = String(rt.assetText(assetId, 'battery.state', '') || '').toLowerCase();
      const published = rt.asset(assetId) || {};
      const projection = rt.assetProjection(assetId);
      const health = firstDefined(projection?.lifecycle?.state, published.health, published.status, 'UNKNOWN');
      const asset = this.energyAssetContext(rt, published.asset_id ? published : { asset_id:assetId, display_name:name, asset_type:'battery' });
      const area = this.energyAssetAreaLabel(asset);
      const explicitlyUnavailable = /unavailable|offline|disconnected|failed/i.test(String(firstDefined(published.availability_state,published.connection_state,health,'')));
      const stateLabel = explicitlyUnavailable ? 'Unavailable'
        : state === 'charging' ? 'Charging'
        : state === 'discharging' ? 'Discharging'
        : state === 'idle' ? 'Idle'
        : power === null ? 'Measurements limited'
        : Math.abs(power) <= 0.05 ? 'Idle'
        : power < 0 ? 'Charging' : 'Discharging';
      const stateDetail = stateLabel === 'Charging' ? 'Absorbing energy from the Home Bus'
        : stateLabel === 'Discharging' ? 'Supplying energy to the Home Bus'
        : stateLabel === 'Idle' ? 'No active battery flow'
        : stateLabel === 'Measurements limited' ? 'Battery is available; per-battery power is not available'
        : 'Battery is currently unavailable';
      const quickFacts = [
        ['Power now',fmtKw(power,'—')],
        ['Available',available === null ? '' : fmtKwh(available)],
        ['Capacity',capacity === null ? '' : fmtKwh(capacity)]
      ].filter(([,value])=>value);
      const actions = this.assetQuickActions(rt,assetId,3,stateLabel);
      return `<article class="batteryContributorCard"><div class="batteryContributorVisual">${this.assetVisual(asset,{size:'lg',fallbackIcon:'▣',decorative:false})}</div><div class="batteryContributorBody"><div class="batteryContributorHeader"><div><b>${escapeHtml(name)}</b>${area ? `<small class="batteryContributorArea">${escapeHtml(area)}</small>` : ''}<span class="batteryHealth">${escapeHtml(this.userStateText(health,'Available'))}</span></div><strong>${fmtPct(soc)}</strong></div><div class="batteryContributorFacts">${quickFacts.map(([label,value])=>`<span><small>${escapeHtml(label)}</small><b>${escapeHtml(value)}</b></span>`).join('')}</div><div class="batteryContributorState"><span>${escapeHtml(stateLabel)}</span><small>${escapeHtml(stateDetail)}</small></div><div class="bar"><i style="width:${escapeHtml(this.progress(soc,100))}%"></i></div>${actions}${this.energyAssetDetailDisclosure(rt,asset)}</div></article>`;
    }
    gas(rt) {
      const pageVm = this.buildPageViewModel(rt, 'gas');
      const gas = this.gasModel(rt);
      const hasMeter = !!gas.asset;
      const meter = hasMeter ? this.energyDeviceStatusCard(rt, gas.asset, 'Gas meter') : '';
      const historyAvailable = !!gas.totalEntityId;
      const gasHorizons = [['week','Week'],['month','Month'],['quarter','Quarter'],['year','Year']];
      const gasHorizonLabel = gasHorizons.find(([id])=>id===this.selectedGasHorizonId)?.[1] || 'Month';
      const gasHorizonSelector = `<div class="scopeSelector gasHorizonSelector" aria-label="Gas history horizon">${gasHorizons.map(([id,label])=>`<button type="button" class="scopeOption ${this.selectedGasHorizonId===id?'active':''}" data-gas-horizon="${id}">${label}</button>`).join('')}</div>`;
      const graph = historyAvailable
        ? `<section class="panel gasHistoryPanel rhiUxChartPanel" id="gas-history"><div class="rhiUxSectionHead"><div><h2>${escapeHtml(rhiEnergyT(this._hass,'gas.history',{},'Gas usage history'))}</h2><p>Daily measured gas use from Home Assistant history.</p></div><div class="gasHistoryControls"><span>${escapeHtml(gasHorizonLabel)}</span>${gasHorizonSelector}</div></div><div class="gasStatisticsHost rhiUxChartViewport" data-gas-statistics-host data-entity-id="${escapeHtml(gas.totalEntityId)}"></div></section>`
        : `<section class="panel gasHistoryPanel rhiUxChartPanel" id="gas-history"><div class="rhiUxSectionHead"><div><h2>${escapeHtml(rhiEnergyT(this._hass,'gas.history',{},'Gas usage history'))}</h2><p>${hasMeter ? 'The current meter reading is available; historical statistics are separate.' : 'Daily gas consumption will appear here when a configured gas meter is available.'}</p></div></div><div class="empty"><b>${hasMeter ? 'Historical statistics not available yet' : 'No measured gas history yet'}</b><span>${hasMeter ? 'The meter is connected and reporting a current total, but Home Assistant history is not available for this source yet.' : 'Connect a supported gas meter to enable Home Assistant history. Missing consumption is never estimated.'}</span></div></section>`;
      const setupOrMeter = hasMeter
        ? `<section class="panel gasMeterPanel" id="gas-meter"><div class="rhiUxSectionHead"><div><h2>${escapeHtml(rhiEnergyT(this._hass,'gas.meter',{},'Gas meter'))}</h2><p>${escapeHtml(rhiEnergyT(this._hass,'gas.meter_desc',{},'Current meter state and measured values.'))}</p></div></div>${meter}</section>`
        : `<section class="panel gasSetupPanel" id="gas-meter"><div class="rhiUxSectionHead"><div><h2>${escapeHtml(rhiEnergyT(this._hass,'gas.connect',{},'Connect your gas meter'))}</h2><p>${escapeHtml(rhiEnergyT(this._hass,'gas.connect_desc',{},'Connect a gas meter before consumption history can be shown.'))}</p></div></div><div class="gasSetupFacts"><div><small>Required</small><b>Total gas meter</b><span>A cumulative total-increasing reading in m³.</span></div><div><small>Optional</small><b>Live gas flow</b><span>An instantaneous m³/h reading when available.</span></div><div><small>History</small><b>Home Assistant statistics</b><span>Daily changes are shown without estimating missing data.</span></div></div></section>`;
      return `${this.tabExperienceHeader(rt,'gas',pageVm)}<div class="gasPage">
        ${setupOrMeter}
        ${graph}
      </div>`;
    }

    battery(rt) {
      const pageVm = this.buildPageViewModel(rt, 'battery');
      const batteryVm = this.currentEnergyModel(rt).battery;
      const soc = batteryVm.socPct;
      const capacity = batteryVm.capacityKwh;
      const available = batteryVm.availableKwh;
      const power = batteryVm.displayPowerKw;
      const state = batteryVm.label;
      const reserve = batteryVm.reserveTargetPct;
      const batterySystem = rt.assets().find(asset => ['battery_system','home_battery_system'].includes(String(asset.asset_type || asset.object_class || '').toLowerCase())) || rt.asset('battery_system');
      const children = batterySystem
        ? rt.childrenOfType(String(batterySystem.asset_id || 'battery_system'), 'battery')
        : rt.assets().filter(asset => String(asset.asset_type || asset.object_class || '').toLowerCase() === 'battery').map(asset => String(asset.asset_id || '')).filter(Boolean);
      const systemDetails = batterySystem ? this.energyAssetDetailDisclosure(rt,this.energyAssetContext(rt,batterySystem)) : '';
      return `${this.tabExperienceHeader(rt,'battery',pageVm)}<div class="batteryPage">
        <div class="batteryGrid batteryGridTwoUp">
          <section class="panel batteryHero"><h2>${escapeHtml(rhiEnergyT(this._hass,'battery.state',{},'Home Battery state'))}</h2><p>${escapeHtml(rhiEnergyT(this._hass,'battery.state_desc',{},'Combined operational truth for the Home Battery system.'))}</p><div class="batteryGauge"><b>${escapeHtml(fmtPct(soc))}</b><span>${escapeHtml(fmtKwh(available))} / ${escapeHtml(fmtKwh(capacity))}</span><div class="bar"><i style="width:${escapeHtml(this.progress(soc,100))}%"></i></div></div>${this.kv('State', human(state))}${this.kv('Power now', fmtKw(power,'—'))}${this.kv('Available energy', fmtKwh(available))}${this.kv('Capacity', fmtKwh(capacity))}${reserve === null ? '' : this.kv('Reserve',fmtPct(reserve))}${this.kv('Health', human(batteryVm.health))}${systemDetails}</section>
          <section class="panel" id="battery-contributors"><h2>${escapeHtml(rhiEnergyT(this._hass,'battery.contributors',{},'Home Battery contributors'))}</h2><p>${escapeHtml(rhiEnergyT(this._hass,'battery.contributors_desc',{},'Physical batteries contributing to the aggregate.'))}</p><div class="batteryContributorList">${children.map(id => this.batteryChildCard(rt, id)).join('') || `<div class="empty"><b>No Home Battery units available</b><span>Home Battery aggregate only.</span></div>`}</div></section>
        </div>
        ${this.energyHistorySection(rt,'battery')}
      </div>`;
    }
    consumerSortOptions() {
      return [
        ['power','Current power'],['energy','Energy today'],['need','Known need'],['cost','Cost today'],['name','Name']
      ];
    }
    consumerFilterOptions() {
      return [
        ['all','All'],['flexible','Flexible'],['fixed','Fixed'],['vehicles','Vehicles'],['heating','Heating'],['storage','Storage'],['outdoor','Outdoor']
      ];
    }

    consumerMixBar(row = {}) {
      const solar = asNumber(row.solar_share_pct);
      const battery = asNumber(row.battery_share_pct);
      const lowGrid = asNumber(row.low_cost_grid_share_pct);
      let grid = asNumber(row.grid_share_pct);
      if (grid === null && row.grid_supplied_kwh !== null && row.energy_today_kwh) grid = Math.max(0, row.grid_supplied_kwh / row.energy_today_kwh * 100);
      const otherGrid = grid === null ? null : Math.max(0, grid - (lowGrid || 0));
      const values = [solar || 0, battery || 0, lowGrid || 0, otherGrid || 0];
      const total = values.reduce((a,b)=>a+b,0);
      if (!total) return `<div class="consumerMixUnavailable">Energy source unavailable</div>`;
      return `<div class="consumerMixBar" aria-label="Energy source mix"><span class="solar" style="width:${Math.max(0,values[0])}%"></span><span class="battery" style="width:${Math.max(0,values[1])}%"></span><span class="lowGrid" style="width:${Math.max(0,values[2])}%"></span><span class="grid" style="width:${Math.max(0,values[3])}%"></span></div><div class="consumerMixLegend"><span>Solar ${fmtPct(solar)}</span><span>Battery ${fmtPct(battery)}</span><span>Low-cost grid ${fmtPct(lowGrid)}</span><span>Other grid ${fmtPct(otherGrid)}</span></div>`;
    }
    consumerExplorerCard(rt, row = {}) {
      const id = row.asset_id || row.consumer_id || row.id || 'consumer';
      const vm = this.flexibleAssetDomain(rt).byId(id);
      if (vm?.isDisabled) return this.disabledFlexibleAssetCard(rt,vm.raw || row,vm.planning || {});
      const planning = vm?.planning || rt.planningOutcomeFor(id) || {};
      const raw = vm?.raw || row;
      const producerVisualRef = String(firstDefined(vm?.visualRef, raw.visual_ref, row.visual_ref, '') || '').trim();
      const asset = this.energyAssetContext(rt,{...raw,...row,visual_ref:producerVisualRef});
      const stateRaw = firstDefined(planning.product_state,planning.status,planning.state,asset.operating_state,'unknown');
      const state = this.userStateText(stateRaw);
      const currentPower = asNumber(firstDefined(row.current_power_kw,row.actual_power_kw,row.power_kw,raw.current_power_kw,raw.actual_power_kw,raw.power_kw,null));
      const energyNeed = asNumber(firstDefined(
        planning.energy_to_target_kwh,planning.energy_needed_kwh,planning.remaining_energy_kwh,planning.energy_need_kwh,
        row.energy_to_target_kwh,row.energy_needed_kwh,row.remaining_energy_kwh,row.energy_need_kwh,
        raw.energy_to_target_kwh,raw.energy_needed_kwh,raw.remaining_energy_kwh,raw.energy_need_kwh
      ));
      const plannedToday = asNumber(firstDefined(planning.planned_today_kwh,row.planned_today_kwh,raw.planned_today_kwh,null));
      const stillToPlan = asNumber(firstDefined(planning.still_to_plan_kwh,planning.remaining_need_kwh,row.still_to_plan_kwh,raw.still_to_plan_kwh,null));
      const readyBy = String(firstDefined(planning.ready_by,planning.deadline_time,row.ready_by,raw.ready_by,'') || '').trim();
      const chargerId = String(firstDefined(asset.effective_charger,asset.charger_asset_id,asset.connection_asset_id,asset.execution_target_asset_id,'') || '');
      const chargerDisplay = String(firstDefined(
        asset.effective_charger_display_name,
        asset.charger_display_name,
        asset.connection_display_name,
        asset.physical_connection_display_name,
        ''
      ) || '').trim();
      const relation = chargerId ? this.userRelationshipLabel(chargerDisplay, 'Assigned charger') : '';
      const requestedRow = this.flexiblePropertyRow(rt,id,['requested_charge_power_kw','requested_power_kw','energy_control_requested_power_kw','target_power_kw','setpoint_power_kw','charge_power_setpoint_kw']);
      const requested = rowValue(requestedRow,null) ?? row.requested_power_kw ?? raw.requested_power_kw ?? null;
      const requestedControl = requestedRow && !requestedRow.missing && this.isWritableRow(requestedRow)
        ? this.editablePropertyControl(requestedRow,{title:rhiEnergyT(this._hass,'control.requested_charge_power',{},'Requested charge power'),description:rhiEnergyT(this._hass,'control.requested_charge_power_desc',{},'Charging power requested from this asset.'),type:'range',fallbackValue:requested,immediateWrite:true})
        : '';
      const actions = this.coherentCommandModels(
        rt.commandActionModelsForAsset(id).filter(action=>['start','stop','pause','resume'].includes(action.role)),
        [stateRaw, asset.operating_state, asset.execution_state, currentPower !== null && currentPower > 0.05 ? 'active' : ''].filter(Boolean).join(' ')
      );
      const readiness = raw.planning_input_ready === true ? 'Plan-ready' : raw.planning_input_ready === false ? 'Planning blocked' : 'Planning not evaluated';
      const readinessReason = String(raw.planning_input_reason || '');
      const configuration = requestedControl
        ? `<details class="energyAssetDisclosure energyAssetConfiguration"><summary>Configuration</summary><div class="energyAssetFoldBody">${requestedControl}</div></details>`
        : '';
      const detailRows = [
        energyNeed !== null ? ['Planning',readiness] : null,
        readinessReason ? ['Reason',this.userSafeReason(readinessReason,'Not specified')] : null,
        readyBy ? ['Ready by',human(readyBy)] : null,
        requested !== null ? ['Requested power',fmtKw(requested,'—')] : null,
        plannedToday !== null ? ['Planned today',fmtKwh(plannedToday)] : null,
        stillToPlan !== null ? ['Still to plan',fmtKwh(stillToPlan)] : null
      ].filter(Boolean);
      const details = detailRows.length
        ? `<details class="energyAssetDisclosure energyAssetDetails"><summary>Details</summary><div class="energyAssetFoldBody energyAssetDetailGrid">${detailRows.map(([label,value])=>`<span><small>${escapeHtml(label)}</small><b>${escapeHtml(value)}</b></span>`).join('')}</div></details>`
        : '';
      const diagnostics = `<details class="energyAssetDisclosure energyAssetDiagnostics"><summary>Diagnostics</summary><div class="energyAssetFoldBody energyAssetDiagnosticGrid"><span><small>Asset id</small><b>${escapeHtml(id)}</b></span><span><small>Health</small><b>${escapeHtml(human(firstDefined(asset.health,asset.lifecycle_state,asset.status,'Unknown')))}</b></span>${requestedControl ? '' : `<span><small>Requested charge power</small><b>${escapeHtml(requestedRow && !requestedRow.missing ? (this.userSafeReason(requestedRow.editable_reason,'Read-only')) : 'Not available')}</b></span>`}</div></details>`;
      const chargerTarget = chargerId
        ? (rhiUxResolveDomainAssetNavigation('rhi_mobility',chargerId) || rhiUxResolveDomainAssetNavigation('mobility',chargerId))
        : '';
      const headline = rhiUxCompactAssetRow({
        visualHtml:this.assetVisual(asset,{size:'sm',fallbackIcon:this.flexibleAssetIcon(asset)}),
        name:row.display_name || rt.assetName(id) || human(id),
        context:energyNeed !== null ? `Energy needed ${fmtKwh(energyNeed)}` : readiness,
        power:fmtKw(currentPower,'—'),
        state,
        relationshipLabel:relation,
        relationshipTarget:chargerTarget
      });
      return `<article class="managedAssetCard compactManagedAsset rhiEnergyCompactAssetCard">${headline}
        ${actions.length ? `<div class="energyAssetQuickActions"><small>${escapeHtml(rhiEnergyT(this._hass,"common.quick_actions",{},"Quick actions"))}</small><div>${actions.map(action=>this.componentActionModelButton(action)).join('')}</div></div>` : ''}
        <div class="energyAssetFoldStack">${configuration}${details}${diagnostics}</div>
      </article>`;
    }

    filterAndSortConsumers(rows = []) {
      const filter = this.consumerFilter || 'all';
      let filtered = rows.filter(row => {
        const text = `${row.category || ''} ${row.asset_type || ''} ${row.display_name || ''}`.toLowerCase();
        if (filter === 'flexible') return asBool(row.flexible, false) || String(row.controllability || '').toLowerCase() === 'flexible';
        if (filter === 'fixed') return !asBool(row.flexible, false) && String(row.controllability || '').toLowerCase() !== 'flexible';
        if (filter === 'vehicles') return /vehicle|car|mobility/.test(text);
        if (filter === 'heating') return /heat|thermal|boiler|hvac/.test(text);
        if (filter === 'storage') return asBool(row.storage, false) || /battery|storage/.test(text);
        if (filter === 'outdoor') return /outdoor|pool|jacuzzi|irrigation/.test(text);
        return true;
      });
      const value = (row, key) => asNumber(row[key]) ?? -Infinity;
      const sort = this.consumerSort || 'cost';
      return filtered.sort((a,b) => {
        if (sort === 'name') return String(a.display_name || '').localeCompare(String(b.display_name || ''));
        if (sort === 'status') return String(a.status || '').localeCompare(String(b.status || ''));
        if (sort === 'energy') return value(b,'energy_today_kwh') - value(a,'energy_today_kwh');
        if (sort === 'power') return value(b,'current_power_kw') - value(a,'current_power_kw');
        if (sort === 'grid') return value(b,'grid_supplied_kwh') - value(a,'grid_supplied_kwh');
        if (sort === 'low-grid') return value(b,'low_cost_grid_kwh') - value(a,'low_cost_grid_kwh');
        if (sort === 'solar') return value(b,'solar_supplied_kwh') - value(a,'solar_supplied_kwh');
        if (sort === 'battery') return value(b,'battery_supplied_kwh') - value(a,'battery_supplied_kwh');
        if (sort === 'need') return value(b,'expected_energy_kwh') - value(a,'expected_energy_kwh');
        return value(b,'cost_today_eur') - value(a,'cost_today_eur');
      });
    }
    consumers(rt) {
      const pageVm = this.buildPageViewModel(rt, 'consumers');
      const publishedRows = rt.consumerMixRows();
      const summary = rt.consumerMixSummary();
      const domain = this.flexibleAssetDomain(rt);
      const publishedById = new Map(publishedRows.map(row => [String(row.asset_id||row.consumer_id||row.id||''), row]));
      const canonicalRows = domain.consumerFacing().map(vm => {
        const raw = vm.raw || {};
        const published = publishedById.get(vm.id) || {};
        return {
          ...raw,
          ...published,
          asset_id:vm.id,
          visual_ref:firstDefined(vm.visualRef, raw.visual_ref, published.visual_ref, ''),
          charger_asset_id:firstDefined(raw.charger_asset_id, raw.effective_charger, raw.connection_asset_id, published.charger_asset_id, published.effective_charger, published.connection_asset_id, ''),
          connection_state:firstDefined(raw.connection_state, published.connection_state, ''),
          participation_state:vm.participation,
          operational_state:vm.operation
        };
      });
      const canonicalIds = new Set(canonicalRows.map(row => String(row.asset_id||row.consumer_id||row.id||'')));
      const rows = canonicalRows.concat(publishedRows.filter(row => {
        const id = String(row.asset_id||row.consumer_id||row.id||'');
        if (canonicalIds.has(id)) return false;
        const vm = domain.byId(id);
        if (vm) return !vm.isInfrastructure && !vm.isStorage;
        const kind = String(firstDefined(row.source_asset_kind,row.asset_type,row.object_class,row.energy_asset_role,'') || '').toLowerCase();
        return !/(^|_)(charger|connection|charging_point)(_|$)/.test(kind);
      }));
      const visibleRows = this.filterAndSortConsumers(rows);
      const participating = visibleRows.filter(row => { const vm=domain.byId(row.asset_id||row.consumer_id||row.id); return !vm || !vm.isDisabled; });
      const disabled = visibleRows.filter(row => domain.byId(row.asset_id||row.consumer_id||row.id)?.isDisabled);
      const totalPower = asNumber(summary.current_power_kw);
      const cards = participating.map(row=>this.consumerExplorerCard(rt,row)).join('');
      const disabledRows = disabled.map(row=>{ const vm=domain.byId(row.asset_id||row.consumer_id||row.id); return this.disabledFlexibleAssetCard(rt,vm?.raw||row,vm?.planning||{}); }).join('');
      return `${this.tabExperienceHeader(rt,'consumers',pageVm)}${this.bodyContextBar(rt,'consumers','consumer-list')}<div class="consumersPage productPortalPage">
        <section class="panel consumerExplorer" id="consumer-list"><div class="consumerExplorerHeader"><div><h2>${escapeHtml(rhiEnergyT(this._hass,'consumer.managed',{},'Flexible loads'))}</h2><p>Primary cards show current power and energy need. Details contain additional user information; technical evidence stays in Diagnostics.</p></div><strong>${fmtKw(totalPower,'—')}</strong></div><div class="consumerExplorerList">${cards || `<div class="empty"><b>No flexible loads published</b><span>Energy has not published a canonical flexible-load inventory.</span></div>`}</div></section>
        ${disabledRows ? `<details class="panel compactDisclosure"><summary>${escapeHtml(rhiEnergyT(this._hass,"asset.other",{},"Other assets"))} (${disabled.length})</summary><p>${escapeHtml(rhiEnergyT(this._hass,"asset.not_managed",{},"These assets are not managed by Home Intelligence."))}</p><div class="disabledAssetList">${disabledRows}</div></details>` : ''}
      </div>`;
    }
    strategies(rt) {
      const pageVm = this.buildPageViewModel(rt, 'strategies');
      const d = rt.decision();
      const profiles = rt.strategyProfileRows();
      const effectiveStrategies = rt.effectiveStrategyRows();
      const fallbackProfile = profiles[0] || null;
      let selected = this.selectedStrategyProfileId
        ? (rt.strategyProfileFor(this.selectedStrategyProfileId) || null)
        : fallbackProfile;
      if (!selected && fallbackProfile) selected = fallbackProfile;
      if (selected && this.selectedStrategyProfileId !== selected.profile_id) this.selectedStrategyProfileId = selected.profile_id;
      const selectedId = selected?.profile_id || '';
      const selectedTopic = selected ? this.profileSettingsTopic(selected) : '';

      const topicGroups = new Map();
      profiles.forEach(profile => {
        const topic = this.profileSettingsTopic(profile);
        if (!topicGroups.has(topic)) topicGroups.set(topic, []);
        topicGroups.get(topic).push(profile);
      });
      const topicOrder = ['Home & priorities','Battery','EV charging','Solar','Grid & tariffs','Home & resilience'];
      const topics = [...topicGroups.entries()].sort(([left],[right]) => {
        const li=topicOrder.indexOf(left), ri=topicOrder.indexOf(right);
        if(li>=0 || ri>=0) return (li<0?99:li)-(ri<0?99:ri);
        return left.localeCompare(right);
      });
      const topicButtons = topics.map(([topic,rows]) => {
        const target = rows[0];
        const active = topic === selectedTopic;
        return `<button type="button" class="settingsTopicButton${active?' active':''}" data-settings-topic-profile="${escapeHtml(target.profile_id || '')}" aria-pressed="${active?'true':'false'}"><b>${escapeHtml(topic)}</b><span>${escapeHtml(this.profileUserDescription(target))}</span></button>`;
      }).join('');
      const selectedGroup = selectedTopic ? (topicGroups.get(selectedTopic) || []) : [];
      const variantSelect = selectedGroup.length > 1
        ? `<label class="settingsVariantSelect"><span>Policy set</span><select data-strategy-profile-select>${selectedGroup.map(profile=>`<option value="${escapeHtml(profile.profile_id)}"${String(profile.profile_id)===String(selectedId)?' selected':''}>${escapeHtml(this.profileUserLabel(profile))}</option>`).join('')}</select></label>`
        : '';

      const automationRow = rt.editableProperty('energy.operating_mode') || rt.row('energy.operating_mode');
      const automationMode = rowValue(automationRow, this.energyAutomationMode(rt,d) || 'advice');
      const automationOptions = allowedValuesForRow(automationRow).length
        ? allowedValuesForRow(automationRow).map(value => ({ value, label:this.productStateLabel(value,human(value)), attrs:{'data-mode-value':value,'data-property-key':'energy.operating_mode'} }))
        : ['automatic','advice','disabled'].map(value => ({ value, label:this.productStateLabel(value,human(value)), attrs:{'data-mode-value':value,'data-property-key':'energy.automation_mode'} }));
      const automationControl = this.isWritableRow(automationRow)
        ? this.componentSegmentedControl(automationOptions, automationMode, 'automationModeControl')
        : `<div class="profileNoControls">Automation mode cannot be changed right now.</div>`;

      const effectiveRowsForProfile = selectedId
        ? effectiveStrategies.filter(strategy => {
            const text = `${strategy.profile_id || ''} ${strategy.strategy_profile_id || ''} ${strategy.profile_type || ''} ${strategy.asset_type || ''} ${strategy.policy_profile || ''}`.toLowerCase();
            const wanted = String(selectedId).toLowerCase();
            return text.includes(wanted) || text.includes(String(selected?.profile_type || '').toLowerCase()) || text.includes(String(selected?.asset_type || '').toLowerCase());
          })
        : effectiveStrategies;
      const effectiveRows = (effectiveRowsForProfile.length ? effectiveRowsForProfile : effectiveStrategies).map(strategy => this.effectivePolicyPreviewCard(rt,strategy)).join('');
      const participation = rt.settingsParticipationRows().map(parent => {
        const parentAsset=rt.asset(parent.asset_id) || parent;
        const children=asArray(parent.children);
        return `<article class="settingsParticipationRoot"><div class="settingsParticipationRootHead">${this.assetVisual(parentAsset,{size:'sm',fallbackIcon:this.flexibleAssetIcon(parentAsset)})}<div><b>${escapeHtml(parent.display_name || rt.assetName(parent.asset_id) || human(parent.asset_id))}</b><span>${escapeHtml(human(parent.participation_role || parent.asset_type || 'Participating'))}</span></div></div><div class="settingsParticipationChildren">${children.map(child=>{const childAsset=rt.asset(child.asset_id)||child;return `<div class="settingsParticipationChild">${this.assetVisual(childAsset,{size:'xs',fallbackIcon:this.flexibleAssetIcon(childAsset)})}<div><b>${escapeHtml(child.display_name || rt.assetName(child.asset_id) || human(child.asset_id))}</b><span>${escapeHtml(human(child.relationship_type || child.asset_type || 'Member'))}</span></div></div>`;}).join('')}</div></article>`;
      }).join('');

      return `${this.tabExperienceHeader(rt,'strategies',pageVm)}<div class="strategiesPage settingsTopicPage">
        <section class="panel strategyAutomationMode compactSettingsBlock"><div><h2>${escapeHtml(rhiEnergyT(this._hass,'settings.automation',{},'Automation'))}</h2><p>${escapeHtml(rhiEnergyT(this._hass,'settings.automation_desc',{},'Choose how much Home Intelligence may act for you.'))}</p></div>${automationControl}${this.editablePropertyFeedback(automationRow)}</section>
        <section class="panel settingsTopicChooser"><div class="settingsTopicHead"><h2>${escapeHtml(rhiEnergyT(this._hass,'settings.adjust',{},'What do you want to adjust?'))}</h2><p>${escapeHtml(rhiEnergyT(this._hass,'settings.adjust_desc',{},'Settings are grouped by the part of your energy system you want to influence.'))}</p></div><div class="settingsTopicGrid">${topicButtons || '<div class="empty"><b>No settings topics available</b><span>No adjustable Energy settings are currently available.</span></div>'}</div></section>
        ${selected ? `<section class="settingsSelectedTopic"><div class="settingsSelectedTopicHead"><div><small>${escapeHtml(rhiEnergyT(this._hass,"nav.settings",{},"Settings").toUpperCase())}</small><h2>${escapeHtml(selectedTopic)}</h2></div>${variantSelect}</div>${this.strategyProfileCard(rt,selected)}</section>` : ''}
        <details class="panel settingsAdvancedDisclosure"><summary>Advanced</summary><div class="settingsAdvancedBody">
          <section><h3>${escapeHtml(rhiEnergyT(this._hass,'settings.effective',{},'Effective behavior'))}</h3><div class="effectivePolicyList">${effectiveRows || '<div class="empty compact"><b>No effective behavior available</b></div>'}</div></section>
          ${participation ? `<section><h3>${escapeHtml(rhiEnergyT(this._hass,'settings.participants',{},'Participating assets'))}</h3><div class="settingsParticipationTree">${participation}</div></section>` : ''}
        </div></details>
      </div>`;
    }

    meteringPeriodRow(title, todayKey, monthKey, yearKey, totalKey) {
      const rt = this.runtime();
      const today = rt.number(todayKey);
      const month = rt.number(monthKey);
      const year = rt.number(yearKey);
      const total = rt.number(totalKey);
      return `<div class="meteringRow"><div><b>${escapeHtml(title)}</b><span>${escapeHtml(todayKey)}</span></div><strong>${fmtKwh(today)}</strong><small>${escapeHtml(rhiEnergyT(this._hass,"common.month_label",{},"Month"))} ${escapeHtml(fmtKwh(month))} · ${escapeHtml(rhiEnergyT(this._hass,"common.year_label",{},"Year"))} ${escapeHtml(fmtKwh(year))} · ${escapeHtml(rhiEnergyT(this._hass,"common.total",{},"Total"))} ${escapeHtml(fmtKwh(total))}</small></div>`;
    }
    defaultMeteringPeriods() {
      return [
        { period_id: 'hour', label: rhiEnergyT(this._hass,'common.this_hour',{},'This hour'), selector_order: 0 },
        { period_id: 'today', label: rhiEnergyT(this._hass,'common.today',{},'Today'), selector_order: 1 },
        { period_id: 'week', label: rhiEnergyT(this._hass,'common.week',{},'Week'), selector_order: 2 },
        { period_id: 'month', label: rhiEnergyT(this._hass,'common.month',{},'Month'), selector_order: 3 },
        { period_id: 'year', label: rhiEnergyT(this._hass,'common.year',{},'Year'), selector_order: 4 }
      ];
    }
    meteringSortOptions() {
      return [
        { value: 'default', label: rhiEnergyT(this._hass,'common.default',{},'Default') },
        { value: 'name', label: rhiEnergyT(this._hass,'common.name',{},'Name') },
        { value: 'value_desc', label: rhiEnergyT(this._hass,'common.highest_value',{},'Highest value') },
        { value: 'value_asc', label: rhiEnergyT(this._hass,'common.lowest_value',{},'Lowest value') },
        { value: 'status', label: rhiEnergyT(this._hass,'common.status',{},'Status') }
      ];
    }
    componentMeteringSort() {
      const active = this.meteringSort || 'default';
      const options = this.meteringSortOptions();
      const buttons = options.map(option => `<button type="button" class="scopeOption ${option.value === active ? 'active' : ''}" data-metering-sort="${escapeHtml(option.value)}">${escapeHtml(option.label)}</button>`).join('');
      const select = `<select data-metering-sort-select>${options.map(option => `<option value="${escapeHtml(option.value)}" ${option.value === active ? 'selected' : ''}>${escapeHtml(option.label)}</option>`).join('')}</select>`;
      const activeLabel = options.find(option => option.value === active)?.label || 'Default';
      return `<div class="scopeSelector meteringSortSelector"><div class="scopeSelectorTitle"><span>${escapeHtml(rhiEnergyT(this._hass,"common.sort",{},"Sort"))}</span><b>${escapeHtml(activeLabel)}</b></div><div class="scopeButtons">${buttons}</div>${select}</div>`;
    }
    sortMeteringRows(rows = []) {
      const sort = this.meteringSort || 'default';
      const statusRank = { fail: 0, warn: 1, missing: 2, 'not-measured': 3, unknown: 4, ok: 5 };
      const list = [...rows];
      if (sort === 'name') list.sort((a, b) => String(a.label || '').localeCompare(String(b.label || '')));
      if (sort === 'value_desc') list.sort((a, b) => (asNumber(b.value) ?? -Infinity) - (asNumber(a.value) ?? -Infinity));
      if (sort === 'value_asc') list.sort((a, b) => (asNumber(a.value) ?? Infinity) - (asNumber(b.value) ?? Infinity));
      if (sort === 'status') list.sort((a, b) => (statusRank[rowState({ health: a.status, missing: a.value === null })] ?? 9) - (statusRank[rowState({ health: b.status, missing: b.value === null })] ?? 9));
      return list;
    }
    meteringDisplayValue(row) {
      if (!row || row.value === null || row.value === undefined || row.value === '') return 'Not available';
      const unit = String(row.unit || 'kWh');
      if (/eur|€/.test(unit.toLowerCase())) {
        const n = asNumber(row.value);
        return n === null ? String(row.value) : `€${n.toFixed(2)}`;
      }
      if (/kwh/i.test(unit)) return fmtKwh(row.value, 'Not available');
      if (/kw/i.test(unit)) return fmtKw(row.value, 'Not available');
      const n = asNumber(row.value);
      return n === null ? String(row.value) : `${n.toFixed(1)}${unit ? ` ${unit}` : ''}`;
    }
    meteringStatus(row) { return row?.status || 'unknown'; }
    meteringClusterCard(title, rows = [], description = '') {
      const sorted = this.sortMeteringRows(rows);
      const body = sorted.length ? sorted.map(row => `<div class="meteringCleanRow ${escapeHtml(rowState({ health: this.meteringStatus(row), missing: row.value === null }))}"><div><b>${escapeHtml(row.label)}</b>${row.sub ? `<span>${escapeHtml(row.sub)}</span>` : ''}</div><strong>${escapeHtml(this.meteringDisplayValue(row))}</strong>${['unknown','unavailable',''].includes(String(this.meteringStatus(row)||'').toLowerCase()) ? '' : this.componentQualityChip(this.meteringStatus(row))}</div>`).join('') : `<div class="empty"><b>No values available</b><span>No measurements are available for the selected period.</span></div>`;
      return `<section class="panel meteringCleanCard"><div class="meteringCardHead"><div><h2>${escapeHtml(title)}</h2>${description ? `<p>${escapeHtml(description)}</p>` : ''}</div></div><div class="meteringCleanRows">${body}</div></section>`;
    }
    meteringRawRowsDetails(rows = [], id = 'metering-raw-rows') {
      const sorted = this.sortMeteringRows(rows);
      const body = sorted.length ? sorted.map(row => `<div class="meteringCleanRow raw"><div><b>${escapeHtml(row.label || row.key || 'Metering row')}</b><span>${escapeHtml(row.key || row.source_key || '')}</span></div><strong>${escapeHtml(this.meteringDisplayValue(row))}</strong>${this.componentQualityChip(row.status || row.health || '')}</div>`).join('') : `<div class="empty"><b>No raw rows</b><span>No metering rows were published.</span></div>`;
      return ''; // Engineering rows remain outside the end-user portal.
    }
    meteringRemediationCard(period = {}, remediations = []) {
      if (!remediations.length) return '';
      const runtime = this.runtime();
      const items = remediations.map(remediation => {
        const advice = objectFrom(remediation.advice || {});
        const problem = objectFrom(remediation.problem || {});
        const action = objectFrom(remediation.action || {});
        const id = String(remediation.remediation_id || remediation.problem_id || 'metering_remediation');
        const command = runtime.meteringResetCommandFor(remediation, period?.period_id || remediation.period_id || '');
        const enabled = command ? runtime.commandEnabled(command) : false;
        const reason = command ? runtime.commandReason(command) : 'Reset is not available right now';
        const feedback = this.remediationFeedback[id] || null;
        const affected = asArray(remediation.affected_keys || problem.affected_keys || action.affected_keys);
        const title = firstDefined(advice.title, remediation.title, problem.title, 'Metering baseline reset required');
        const message = firstDefined(advice.message, remediation.message, problem.message, 'This period cannot be trusted until the period baseline is reset and verified.');
        const impact = firstDefined(advice.consequence_if_ignored, advice.impact, remediation.impact, 'Period values may stay hidden or excluded from evidence until this is fixed.');
        const scope = firstDefined(action.reset_scope, remediation.reset_scope, command?.readback?.reset_scope, 'period_baseline_only');
        const button = command
          ? `<button type="button" class="hiAction remediationAction ${enabled ? 'enabled' : 'disabled'}" ${enabled ? '' : 'disabled'} data-metering-remediation-command-row-id="${escapeHtml(command.command_instance_id || command.command_row_id || '')}" data-remediation-id="${escapeHtml(id)}" title="${escapeHtml(reason)}">Reset baseline</button>`
          : `<button type="button" class="hiAction disabled" disabled title="${escapeHtml(rhiEnergyT(this._hass,"metering.reset_unavailable",{},"Reset is not available right now"))}">${escapeHtml(rhiEnergyT(this._hass,"metering.reset_baseline",{},"Reset baseline"))}</button>`;
        const diagnostics = this.config?.show_diagnostics === true
          ? this.componentDetailsBlock(
              `metering-remediation-details-${escapeHtml(id)}`,
              'Remediation details',
              `${this.kv('Problem id', remediation.problem_id || problem.problem_id || id)}${this.kv('Selected period', this.periodLabel(period))}${this.kv('Affected counters', affected.length ? affected.join(', ') : 'Not available')}${this.kv('Reset scope', human(scope))}${this.kv('Source totals', 'Not changed')}${this.kv('Statistics', 'Not changed')}${this.kv('Command key', command?.command_id || remediation.command_ref || 'Not available')}${this.kv('Command state', command ? (enabled ? 'Ready' : humanReason(reason, 'Not ready')) : 'Not available')}`
            )
          : '';
        return `<div class="meteringRemediationItem"><div class="meteringRemediationText"><h3>${escapeHtml(title)}</h3><p>${escapeHtml(message)}</p><div class="remediationImpact"><b>Impact</b><span>${escapeHtml(impact)}</span></div>${feedback ? `<div class="writeFeedback ${escapeHtml(feedback.state)}">${escapeHtml(this.userSafeReason(feedback.reason || feedback.state,'Update status unavailable'))}</div>` : ''}</div><div class="meteringRemediationAction">${button}<small>${escapeHtml(enabled ? 'Manual confirmation required' : this.userSafeReason(reason,'Action is not ready'))}</small></div>${diagnostics}</div>`;
      }).join('');
      return `<section class="panel wide meteringRemediationPanel"><div class="meteringCardHead"><div><h2>${escapeHtml(rhiEnergyT(this._hass,'metering.attention',{},'Metering attention'))}</h2><p>${escapeHtml(rhiEnergyT(this._hass,'metering.attention_desc',{},'Resolve the selected period before relying on its totals.'))}</p></div></div>${items}</section>`;
    }
    meteringRowFromRuntime(rt, label, key, group = '', fallbackUnit = 'kWh', metricKey = '') {
      const row = rt.row(key);
      const value = row?.missing ? null : asNumber(rowValue(row, null));
      return {
        label, key, metric_key:metricKey, group, value, unit:row.unit || fallbackUnit,
        status:String(firstDefined(row.measurement_state,row.status,row.health,row.quality,rt.statusForKeys(key),'UNAVAILABLE')),
        measurement_state:String(firstDefined(row.measurement_state,row.status,'UNAVAILABLE')),
        attribution_state:String(firstDefined(row.attribution_state,'')),
        trust_state:String(firstDefined(row.trust_state,'')),
        availability:String(firstDefined(row.availability,'')),
        status_label:String(firstDefined(row.status_label,'')),
        user_action_required:asBool(row.user_action_required,false),
        sub:row?.missing ? 'Not available' : ''
      };
    }
    flexibleLoadMeteringRows(rt, periodId = 'today') {
      const period=rt.meteringPeriods().find(row=>row.period_id===String(periodId || 'today'));
      const attributed=period?.flexible_assets_kwh;
      if(!attributed || typeof attributed !== 'object' || Array.isArray(attributed)) return [];
      const quality=String(period?.field_quality?.flexible_loads_energy_in_kwh || 'UNKNOWN').toUpperCase();
      return Object.entries(attributed).filter(([id,value])=>
        !!String(id || '').trim() && value !== null && value !== undefined &&
        Number.isFinite(Number(value)) && Number(value)>=0
      ).map(([asset_id,value])=>({
        asset_id,label:rt.assetName(asset_id) || asset_id,value:Number(value),unit:'kWh',
        measurement_state:quality,status:quality,
        status_label:quality==='OK'?'Measured':'Measurement needs verification',
        metric_key:'flexible_assets_kwh',
        source:'RHI_ENERGY_METERING_PERIOD_V1',ux_visible:true
      }));
    }

    meteringRowsFromRecords(_rt, periodId = 'today') {
      const wanted=String(periodId || 'today').toLowerCase() === 'day' ? 'today' : String(periodId || 'today').toLowerCase();
      return this.meteringRowsFromPeriod({
        period_id:wanted,
        measurement_state:'UNAVAILABLE',
        summary:{ measured:{}, quality:{ period:'UNAVAILABLE' } }
      });
    }

    meteringRowsFromPeriod(period) {
      const measured = objectFrom(period?.summary?.measured || {});
      const quality = objectFrom(period?.summary?.quality || {});
      const status = String(firstDefined(quality.measurement_state,quality.health,quality.status,period?.measurement_state,period?.health,'UNAVAILABLE'));
      const statusLabel = String(firstDefined(quality.status_label,period?.status_label,''));
      const sourceFields={
        solar_production_kwh:'solar_kwh',grid_import_kwh:'grid_import_kwh',
        grid_export_kwh:'grid_export_kwh',site_consumption_kwh:'site_consumption_kwh',
        home_consumption_kwh:'home_consumption_kwh',
        flexible_loads_energy_in_kwh:'flexible_loads_energy_in_kwh',
        battery_charge_kwh:'battery_charge_kwh',
        battery_discharge_kwh:'battery_discharge_kwh'
      };
      const fieldQuality=objectFrom(quality.field_quality || period?.field_quality || {});
      const row = (label, metricKey) => {
        const value=asNumber(valueAtPath(measured,metricKey));
        const fieldState=String(fieldQuality[sourceFields[metricKey]] || 'UNKNOWN').toUpperCase();
        return {label,metric_key:metricKey,value,unit:'kWh',
          status:fieldState,measurement_state:fieldState,
          status_label:fieldState==='OK'?'Measured':fieldState==='PARTIAL'?'Incomplete measurement':'Unknown measurement quality',
          user_action_required:asBool(firstDefined(quality.user_action_required,period?.user_action_required,false),false)};
      };
      return {
        supply:[row('Solar production','solar_production_kwh'),row('Grid import','grid_import_kwh'),row('Home Battery discharge','battery_discharge_kwh')],
        demand:[row('Site Consumption','site_consumption_kwh'),row('Home Consumption','home_consumption_kwh'),row('Flexible Loads','flexible_loads_energy_in_kwh'),row('Home Battery charge','battery_charge_kwh')],
        grid:[row('Grid import','grid_import_kwh'),row('Grid export','grid_export_kwh')],
        battery:[row('Home Battery charge','battery_charge_kwh'),row('Home Battery discharge','battery_discharge_kwh')]
      };
    }
    meteringFallbackRows(rt, periodId = 'today') {
      const period = String(periodId || 'today').toLowerCase() === 'day' ? 'today' : String(periodId || 'today').toLowerCase();
      const exact = (label,key,group,metricKey) => this.meteringRowFromRuntime(rt,label,key,group,'kWh',metricKey);
      return {
        supply:[
          exact('Solar production',`metering.solar_energy_${period}_kwh`,'supply','solar_production_kwh'),
          exact('Grid import',`metering.grid_import_${period}_kwh`,'supply','grid_import_kwh'),
          exact('Home Battery discharge',`metering.battery_discharge_${period}_kwh`,'supply','battery_discharge_kwh')
        ],
        demand:[
          exact('Site Consumption',`metering.site_consumption_${period}_kwh`,'demand','site_consumption_kwh'),
          exact('Home Consumption',`metering.home_consumption_${period}_kwh`,'demand','home_consumption_kwh'),
          exact('Flexible Loads',`metering.flexible_loads_energy_in_${period}_kwh`,'demand','flexible_loads_energy_in_kwh'),
          exact('Home Battery charge',`metering.battery_charge_${period}_kwh`,'demand','battery_charge_kwh')
        ],
        grid:[
          exact('Grid import',`metering.grid_import_${period}_kwh`,'grid','grid_import_kwh'),
          exact('Grid export',`metering.grid_export_${period}_kwh`,'grid','grid_export_kwh')
        ],
        battery:[
          exact('Home Battery charge',`metering.battery_charge_${period}_kwh`,'battery','battery_charge_kwh'),
          exact('Home Battery discharge',`metering.battery_discharge_${period}_kwh`,'battery','battery_discharge_kwh')
        ]
      };
    }
    meteringPeriodRowsAvailable(rows) {
      return Object.values(rows || {}).flat().some(row => row && row.value !== null && row.value !== undefined);
    }
    meteringQualityFromRows(rows = {}) {
      const all = Object.values(rows).flat().filter(Boolean);
      const states = all.map(row => String(row.status || '').toUpperCase());
      if (states.some(state => /UNAVAILABLE|FAIL|ERROR/.test(state))) return { health:'unavailable' };
      if (states.some(state => /CONFIGURATION_REQUIRED/.test(state))) return { health:'configuration_required' };
      if (states.some(state => /RESET_REQUIRED|UNTRUSTED|BASELINE/.test(state))) return { health:'reset_required', baseline_reset_required:true };
      if (states.some(state => /PENDING|VERIFY/.test(state))) return { health:'pending', pending_baseline:true };
      if (states.some(state => /PARTIAL|ESTIMATED/.test(state))) return { health:'partial' };
      return { health:'trusted' };
    }
    flexibleLoadMeteringTable(rt, rows = [], periodLabel = '') {
      const visibleRows = rows.map(row => ({ row, ux:createMeteringStatusModel(row) })).filter(item => item.ux.visible);
      const details = visibleRows.filter(item => !item.row.is_total);
      const totals = visibleRows.filter(item => item.row.is_total);
      const renderRow = ({ row, ux }, total = false) => {
        const label = ux.unattributed ? 'Unassigned charging energy' : (total ? 'Total Flexible Loads' : row.label);
        const displayValue = ux.measured ? this.meteringDisplayValue(row) : ux.label;
        const statusText = row.status_label || ux.label;
        const assetId = String(firstDefined(row.asset_id,row.flexible_asset_id,row.consumer_id,row.source_asset_id,'') || '');
        const asset = !total && !ux.unattributed && assetId ? this.energyAssetContext(rt, rt.asset(assetId) || { ...row, asset_id:assetId }) : null;
        const identity = asset ? `<span class="meteringAssetIdentity">${this.assetVisual(asset,{size:'xs',fallbackIcon:this.flexibleAssetIcon(asset)})}<span><b>${escapeHtml(label)}</b>${row.source_label ? `<small>${escapeHtml(row.source_label)}</small>` : ''}</span></span>` : `<span><b>${escapeHtml(label)}</b>${row.source_label && !ux.unattributed ? `<small>${escapeHtml(row.source_label)}</small>` : ''}</span>`;
        return `<tr class="${total ? 'meteringTotalRow' : ''}"><td>${identity}</td><td class="numeric">${escapeHtml(displayValue)}</td><td>${this.componentQualityChip(statusText)}</td></tr>`;
      };
      const bodyRows = [...details.map(item => renderRow(item,false)), ...totals.map(item => renderRow(item,true))];
      const body = bodyRows.length ? bodyRows.join('') : `<tr><td colspan="3"><div class="empty"><b>${escapeHtml(rhiEnergyT(this._hass,"metering.no_flexible",{},"No Flexible Load measurements available"))}</b><span>${escapeHtml(rhiEnergyT(this._hass,"metering.no_flexible_desc",{},"Measurements appear when Energy publishes a visible period record."))}</span></div></td></tr>`;
      return `<section class="panel wide flexibleMeteringPanel"><div class="meteringCardHead"><div><h2>${escapeHtml(rhiEnergyT(this._hass,'metering.flexible_loads',{},'Flexible Loads'))}</h2><p>Measured consumption per Flexible Load for ${escapeHtml(String(periodLabel || 'the selected period').toLowerCase())}. Home Battery is reported separately as Flexible Storage.</p></div></div><div class="tableWrap"><table class="flexibleMeteringTable"><thead><tr><th>Flexible Load</th><th class="numeric">Measured energy</th><th>Status</th></tr></thead><tbody>${body}</tbody></table></div></section>`;
    }
    meteringCleanPage(vm) {
      const { label, rows, conclusion, command, flexibleLoadRows = [] } = vm;
      const action = command ? this.componentActionButton(command, `Reset ${label.toLowerCase()} totals`, 'metering') : '';
      const group = (title, values) => this.meteringClusterCard(title, values || [], title==='Supply'?'Energy received during this period.':title==='Demand'?'Energy used during this period.':title==='Grid'?'Energy exchanged with the grid.':'Home Battery energy during this period.');
      const selector = this.componentPeriodSelector(vm.periods, vm.periodId, 'metering-period');
      return `<div id="metering-body" class="meteringPage productPortalPage"><section class="panel compact meteringPeriodControl"><div><h2>${escapeHtml(rhiEnergyT(this._hass,'metering.period',{},'Measurement period'))}</h2><p>Select the period used for Metering and persist it as the Energy metering context.</p></div>${selector}${this.editablePropertyFeedback(this.runtime().row('metering.selected_period'))}</section>${this.productStoryCard({ eyebrow:`${label} measurements`, title:conclusion.title, why:conclusion.why, recommendation:conclusion.recommendation, actions:action, details:'', tone:conclusion.tone })}<div class="meteringGrid productMeteringGrid">${group('Supply',rows.supply)}${group('Demand',rows.demand)}${group('Grid',rows.grid)}${group('Home Battery',rows.battery)}</div>${this.flexibleLoadMeteringTable(this.runtime(), flexibleLoadRows, label)}</div>`;
    }
    meteringNotPublishedPeriod(periods, remediation = null) {
      const selected = this.selectedPeriod(periods, this.selectedMeteringPeriodId) || { period_id:this.selectedMeteringPeriodId || 'week', label:human(this.selectedMeteringPeriodId || 'Period') };
      const label = this.periodLabel(selected);
      const command = remediation?.command || null;
      const action = command ? this.componentActionButton(command, `Reset ${label.toLowerCase()} totals`, 'metering') : '';
      const title = remediation ? `${label} totals need a one-time reset` : `${label} period measurements not published`;
      const why = remediation ? `Home Intelligence found measurements for ${label.toLowerCase()}, but the starting point cannot yet be trusted.` : `Energy has not published a canonical metering period with measurements and quality for ${label.toLowerCase()}. Diagnostic storage values are not public UX evidence.`;
      const recommendation = remediation ? `Reset once. Home Intelligence will confirm the new baseline while keeping the measured values visible.` : `Waiting for the backend-owned metering period publication. No baseline reset is assumed necessary.`;
      const selector = this.componentPeriodSelector(periods, selected.period_id || this.selectedMeteringPeriodId || 'today', 'metering-period');
      return `<div class="meteringPage productPortalPage"><section class="panel compact meteringPeriodControl"><div><h2>${escapeHtml(rhiEnergyT(this._hass,'metering.period',{},'Measurement period'))}</h2><p>Select the period even while totals are still being prepared.</p></div>${selector}${this.editablePropertyFeedback(this.runtime().row('metering.selected_period'))}</section>${this.productStoryCard({ eyebrow:`${label} measurements`, title, why, recommendation, actions:action, tone:remediation?'orange':'blue' })}</div>`;
    }
    metering(rt) {
      const pageVm = this.buildPageViewModel(rt, 'metering');
      const vm = this.buildMeteringPeriodViewModel(rt);
      if (!vm.available && !vm.summaryHasData) {
        const requiredRemediation = vm.quality?.user_action_required === true && vm.command
          ? { command:vm.command }
          : null;
        return this.tabExperienceHeader(rt,'metering',pageVm) + this.meteringNotPublishedPeriod(vm.periods, requiredRemediation);
      }
      return this.tabExperienceHeader(rt,'metering',pageVm) + this.meteringCleanPage(vm);
    }
    retrospectiveState() {
      const retrospective=objectFrom(this.runtime().canonicalProduct().retrospective || {});
      if (!Object.keys(retrospective).length) return null;
      return {
        state:String(firstDefined(retrospective.status,'COLLECTING_EVIDENCE')),
        attributes:retrospective
      };
    }
    retrospectiveParsed(value, fallback) {
      if (value === null || value === undefined || value === '') return fallback;
      if (Array.isArray(value) || (typeof value === 'object' && value !== null)) return value;
      try { return JSON.parse(value); } catch (_) { return fallback; }
    }
    retrospectiveRows(names = []) {
      const st = this.retrospectiveState();
      if (!st) return [];
      const attrs = st.attributes || {};
      for (const name of [...names,'rows','items','entries','data','results']) {
        const parsed = this.retrospectiveParsed(attrs[name], null);
        if (Array.isArray(parsed)) return parsed.filter(x=>x && typeof x==='object');
        if (parsed && typeof parsed==='object') return Object.values(parsed).filter(x=>x && typeof x==='object');
      }
      return [];
    }
    retrospectivePrerequisites(attrs = {}, productStatus = {}) {
      const raw = firstDefined(
        attrs.prerequisites_json,
        attrs.prerequisites,
        attrs.evidence_prerequisites_json,
        attrs.pending_prerequisites_json,
        productStatus.prerequisites_json,
        productStatus.prerequisites,
        []
      );
      const parsed = this.retrospectiveParsed(raw, raw);
      const rows = Array.isArray(parsed) ? parsed : (parsed && typeof parsed === 'object' ? Object.values(parsed) : []);
      const normalize = (row, index) => {
        const value = row && typeof row === 'object' ? row : { prerequisite_id:String(row || `step_${index+1}`) };
        const id = String(firstDefined(value.prerequisite_id,value.id,value.key,`step_${index+1}`));
        const state = String(firstDefined(value.state,value.status,value.health,'PENDING')).toUpperCase();
        const labels = {
          planning_outcome:'Planning outcomes', planning_results:'Planning outcomes',
          execution_evidence:'Execution results', execution_results:'Execution results',
          completed_metering:'Measured energy', metering_evidence:'Measured energy',
          value_evidence:'Value evidence', accounting_evidence:'Value evidence',
          closed_evaluation_period:'Closed evaluation period', evaluation_period:'Closed evaluation period'
        };
        return {
          id,
          label: firstDefined(value.label,value.display_name,labels[id],human(id)),
          state,
          reason: humanReason(firstDefined(value.reason,value.reason_label,value.message,''),''),
          ready: /READY|COMPLETE|OK|AVAILABLE/.test(state)
        };
      };
      if (rows.length) return rows.map(normalize);
      const reason = String(firstDefined(productStatus.reason_code,productStatus.reason,attrs.reason_code,attrs.health_reason,'')).toLowerCase();
      const inferred = [];
      if (/planning/.test(reason)) inferred.push({ prerequisite_id:'planning_outcome', state:'PENDING' });
      if (/execution/.test(reason)) inferred.push({ prerequisite_id:'execution_evidence', state:'PENDING' });
      if (/meter|measure/.test(reason)) inferred.push({ prerequisite_id:'completed_metering', state:'PENDING' });
      if (/value|account/.test(reason)) inferred.push({ prerequisite_id:'value_evidence', state:'PENDING' });
      return inferred.map(normalize);
    }
    retrospectiveModel() {
      const overallState=this.retrospectiveState();
      const attrs=overallState?.attributes || {};
      const productStatus=this.retrospectiveParsed(firstDefined(attrs.product_status_json,attrs.product_status),{});
      const evidenceSummary=this.retrospectiveParsed(firstDefined(attrs.evidence_summary_json,attrs.evidence_summary),{});
      const score=asNumber(firstDefined(attrs.score,attrs.overall_score,attrs.score_pct,productStatus.score,overallState?.state));
      const coverage=asNumber(firstDefined(attrs.evidence_coverage_pct,evidenceSummary.coverage_pct,attrs.coverage_pct));
      const rating=human(firstDefined(productStatus.label,attrs.rating,attrs.performance_rating,score!==null?(score>=90?'Excellent':score>=80?'Very good':score>=65?'Good':score>=45?'Learning':'Needs attention'):'Waiting for evidence'));
      const confidence=human(firstDefined(attrs.confidence,productStatus.confidence,'Not available'));
      const explanation=humanReason(firstDefined(attrs.explanation,attrs.summary,attrs.health_reason,productStatus.reason),'Home Intelligence is waiting for the evidence required to complete this retrospective.');
      const trendRaw=firstDefined(attrs.trend,attrs.trend_delta,attrs.score_delta);
      const trend=asNumber(trendRaw);
      const objectives=this.retrospectiveRows(['objectives_json','objectives']);
      const strengths=this.retrospectiveRows(['strengths_json','strengths']);
      const barriers=this.retrospectiveRows(['barriers_json','barriers']);
      const opportunities=this.retrospectiveRows(['opportunities_json','opportunities']);
      const recommendations=this.retrospectiveRows(['strategy_recommendations_json','recommendations_json','recommendations']);
      const deviations=this.retrospectiveRows(['deviations_json','deviations']);
      const deductions=[...barriers,...opportunities,...deviations];
      const state=String(firstDefined(productStatus.state,overallState?.state,'')).toUpperCase();
      const prerequisites=this.retrospectivePrerequisites(attrs, productStatus);
      const collecting=/COLLECTING|WAITING|PENDING|PREREQUISITE/.test(state);
      const hasEvidence=score!==null || objectives.length>0 || strengths.length>0 || deductions.length>0 || recommendations.length>0 || coverage!==null;
      const available=hasEvidence;
      const chainAssessment=objectFrom(this.retrospectiveParsed(firstDefined(attrs.chain_assessment_json,attrs.chain_assessment),{}));
      const executionKpis=objectFrom(this.retrospectiveParsed(firstDefined(attrs.execution_kpis_json,attrs.execution_kpis),{}));
      const tacticalKpis=objectFrom(this.retrospectiveParsed(firstDefined(attrs.tactical_planning_kpis_json,attrs.tactical_planning_kpis),{}));
      const operationalKpis=objectFrom(this.retrospectiveParsed(firstDefined(attrs.operational_planning_kpis_json,attrs.operational_planning_kpis),{}));
      return { available, collecting, hasEvidence, state, prerequisites, score, scoreText:score===null?'—':`${Math.round(score)}`, coverage, coverageText:coverage===null?'Not available':`${Math.round(coverage)}%`, rating, confidence, explanation, trend, trendText:trend===null?human(firstDefined(trendRaw,'Not available')):`${trend>=0?'▲ +':'▼ '}${Math.abs(trend).toFixed(0)}`, kpis:objectives, strengths, deductions, recommendations, chainAssessment, executionKpis, tacticalKpis, operationalKpis, attrs };
    }
    retrospective(rt) {
      const review=this.retrospectiveModel();
      const vm=this.buildPageViewModel(rt,'retrospective');
      if (!review.available) {
        const steps=(review.prerequisites.length ? review.prerequisites : [
          {label:rhiEnergyT(this._hass,'retro.planning_outcomes',{},'Planning outcomes'),state:'PENDING',ready:false},
          {label:rhiEnergyT(this._hass,'retro.execution_results',{},'Execution results'),state:'PENDING',ready:false},
          {label:rhiEnergyT(this._hass,'retro.measured_energy',{},'Measured energy'),state:'PENDING',ready:false}
        ]).map(step=>`<span><b>${escapeHtml(step.label)}</b><em>${escapeHtml(step.ready?'Ready':human(step.state || 'Pending'))}</em>${step.reason?`<small>${escapeHtml(step.reason)}</small>`:''}</span>`).join('');
        return `${this.tabExperienceHeader(rt,'retrospective',vm)}<div class="retrospectivePage"><section class="panel retroCollectingState"><div class="retroCollectingIcon">↺</div><div><small>${escapeHtml(rhiEnergyT(this._hass,"retro.prerequisites",{},"REVIEW PREREQUISITES"))}</small><h2>${escapeHtml(review.rating || 'Waiting for evidence')}</h2><p>${escapeHtml(review.explanation)}</p><div class="retroEvidenceSteps">${steps}</div><div class="productNotice"><b>Review awaiting evidence</b><span>Planning outcomes, execution and measured consumption must be published before a reliable retrospective can be presented. Check the missing prerequisites above.</span></div></div></section></div>`;
      }
      const scoreOf=row=>asNumber(firstDefined(row.score,row.score_pct,row.value,row.achieved_score));
      const weightOf=row=>asNumber(firstDefined(row.weight,row.weight_pct));
      const statusOf=row=>human(firstDefined(row.status,row.rating,row.state,scoreOf(row)!==null?(scoreOf(row)>=90?'Excellent':scoreOf(row)>=75?'Good':'Improving'):'Collecting evidence'));
      const titleOf=(row,fallback)=>human(firstDefined(row.label,row.title,row.name,row.kpi_name,row.objective,row.recommendation,row.recommendation_title,fallback));
      const explanationOf=row=>humanReason(firstDefined(row.explanation,row.reason,row.summary,row.reasoning,row.description),'No additional explanation is available.');
      const kpis=review.kpis.map((row,i)=>{const score=scoreOf(row);const weight=weightOf(row);return `<article class="retroKpiCard"><div class="retroKpiHead"><span>${escapeHtml(firstDefined(row.icon,'◎'))}</span><div><h3>${escapeHtml(titleOf(row,`Objective ${i+1}`))}</h3><p>${escapeHtml(explanationOf(row))}</p></div><strong>${score===null?'—':Math.round(score)}</strong></div><div class="retroProgress"><i style="width:${Math.max(0,Math.min(100,score||0))}%"></i></div><footer><span>${escapeHtml(statusOf(row))}</span><span>${weight===null?'Measured objective':`${Math.round(weight)}% weight`}</span></footer></article>`;}).join('');
      const deductions=review.deductions.slice(0,4).map((row,i)=>{const points=Math.abs(asNumber(firstDefined(row.points_lost,row.deduction_points,row.score_impact,row.points))||0);return `<article class="retroOpportunity"><span class="retroOpportunityIcon">${escapeHtml(firstDefined(row.icon,'↗'))}</span><div><h3>${escapeHtml(titleOf(row,`Opportunity ${i+1}`))}</h3><p>${escapeHtml(explanationOf(row))}</p></div><strong>${points?`+${Math.round(points)} potential`:'Review'}</strong></article>`;}).join('');
      const rec=review.recommendations[0]||null;
      const expected=rec?asNumber(firstDefined(rec.expected_score_gain,rec.score_gain,rec.expected_gain_points,rec.impact_points)):null;
      const confidence=rec?human(firstDefined(rec.confidence,review.confidence)):'Not available';
      const risk=rec?human(firstDefined(rec.risk,'Low')):'Not available';
      const lessons=review.kpis.filter(r=>{const v=scoreOf(r);return v!==null&&v>=80;}).slice(0,3).map(r=>`<div class="retroLesson"><span>✓</span><div><b>${escapeHtml(titleOf(r,'Objective'))}</b><p>${escapeHtml(explanationOf(r))}</p></div></div>`).join('');
      const empty=`<div class="empty"><b>${escapeHtml(rhiEnergyT(this._hass,"retro.collecting",{},"Collecting evidence"))}</b><span>${escapeHtml(rhiEnergyT(this._hass,"retro.collecting_desc",{},"This section appears when Energy Intelligence publishes enough measurable evidence."))}</span></div>`;
      const chainRows = Object.entries(review.chainAssessment || {}).filter(([key])=>key!=='overall').map(([key,value])=>`<div class="goalRow"><span>${escapeHtml(human(key))}</span><b>${escapeHtml(human(value))}</b></div>`).join('');
      const executionSummary = review.executionKpis && Object.keys(review.executionKpis).length ? `<div class="goalGrid"><div class="goalRow"><span>Execution results</span><b>${escapeHtml(String(firstDefined(review.executionKpis.result_count,'—')))}</b></div><div class="goalRow"><span>Confirmed successes</span><b>${escapeHtml(String(firstDefined(review.executionKpis.success_count,'—')))}</b></div><div class="goalRow"><span>Failures</span><b>${escapeHtml(String(firstDefined(review.executionKpis.failure_count,'—')))}</b></div><div class="goalRow"><span>Pending</span><b>${escapeHtml(String(firstDefined(review.executionKpis.pending_count,'—')))}</b></div></div>` : '';
      const introText = review.collecting ? 'This period is still open. Available objective and execution evidence is shown now; the final score and trend remain unavailable until the period closes.' : review.explanation;
      return `${this.tabExperienceHeader(rt,'retrospective',vm)}<div class="retrospectivePage"><section class="retroIntro"><div><small>${review.collecting?rhiEnergyT(this._hass,'retro.open_period',{},'Open period review'):rhiEnergyT(this._hass,'retro.weekly',{},'Weekly review')}</small><h2>${escapeHtml(review.rating)}</h2><p>${escapeHtml(introText)}</p></div><div class="retroScoreRing"><strong>${escapeHtml(review.scoreText)}</strong><span>${review.score===null?'score pending':'out of 100'}</span></div></section><section class="panel" id="retrospective-details"><div class="portalSectionHeader"><div><small>Current evidence</small><h2>What the system can already conclude</h2><p>Published planning, execution and goal evidence is shown even while the period is still open.</p></div><strong>${escapeHtml(review.coverageText)} covered</strong></div>${chainRows?`<div class="goalGrid">${chainRows}</div>`:''}${executionSummary}</section><section class="panel" id="retrospective-objectives"><div class="portalSectionHeader"><div><small>Objectives</small><h2>How well did Energy Intelligence perform?</h2><p>Each objective shows its currently published evidence status.</p></div><strong>${escapeHtml(review.coverageText)} covered</strong></div><div class="retroKpiGrid">${kpis||empty}</div></section><section class="panel" id="retrospective-opportunities"><div class="portalSectionHeader"><div><small>Issues and opportunities</small><h2>What needs attention?</h2><p>Published deviations and opportunities explain where the chain did not deliver as intended.</p></div></div><div class="retroOpportunityList">${deductions||empty}</div></section><section class="panel retroLessons"><div class="portalSectionHeader"><div><small>What went well</small><h2>Strengths from this period</h2></div></div>${lessons||empty}</section><section class="panel retroBestNext"><small>Next best improvement</small><h2>${escapeHtml(rec?titleOf(rec,'Recommended improvement'):(review.collecting?'Waiting for closed evidence':'Still learning'))}</h2><p>${escapeHtml(rec?explanationOf(rec):(review.collecting?'A final recommendation is published when the review period closes and sufficient objective evidence is available.':'Home Intelligence will prioritise one improvement when sufficient evidence is available.'))}</p><div class="retroImpact"><div><span>Expected gain</span><strong>${expected===null?'—':`+${Math.round(expected)} points`}</strong></div><div><span>Confidence</span><strong>${escapeHtml(confidence)}</strong></div><div><span>Risk</span><strong>${escapeHtml(risk)}</strong></div></div></section></div>`;
    }
    intelligence(rt) {
      const pageVm = this.buildPageViewModel(rt, 'intelligence');
      const d = rt.decision();
      const planningRows = this.flexibleAssetDomain(rt).planningRows();
      const policies = rt.effectiveStrategyRows();
      const mode = this.automationModeValue(rt, firstDefined(d.mode, d.automation_mode, 'Advice'));
      const state = this.userStateText(firstDefined(d.product_state,d.status,d.state,rt.value('energy_intelligence.system_state','Monitoring')),'Monitoring');
      const reasonObj = objectFrom(d.reason || {});
      const why = humanReason(firstDefined(reasonObj.message,d.user_reason_label,d.reason_label,reasonObj.code,rt.rawText('energy_intelligence.reason',null)),'Home Intelligence is monitoring current energy conditions.');
      const recommendation = human(firstDefined(d.advice,d.recommendation,rt.value('energy_intelligence.recommendation',null),rt.rawText('energy_intelligence.recommended_action','Keep monitoring')));
      const actionId = firstDefined(d.recommended_action_id,rt.value('energy_intelligence.recommended_action_id',null),null);
      const command = actionId ? rt.commands().find(c=>String(c.command_instance_id||c.command_id||'')===String(actionId)) : null;
      const actions = command ? this.componentActionButton(command,human(rt.commandRole(command)||command.command_id),command.target_asset_id) : '';
      const assetRows = planningRows.slice(0,8).map(row=>{ const id=row.asset_id; const s=this.userStateText(firstDefined(row.product_state,row.status,row.state,row.active?'active':row.waiting?'waiting':row.planned?'planned':'available')); const r=humanReason(firstDefined(row.user_reason_label,row.waiting_reason,row.reason,row.reason_code),'Home Intelligence is monitoring this asset.'); return `<div class="portalStatusRow"><div><b>${escapeHtml(rt.assetName(id)||human(id))}</b><span>${escapeHtml(r)}</span></div><strong>${escapeHtml(s)}</strong></div>`; }).join('');
      const policySummary = policies.filter(p=>/active|waiting|constraining|enabled/i.test(String(firstDefined(p.influence_state,p.effective_state,'')))).slice(0,3).map(p=>`<span>${escapeHtml(human(firstDefined(p.label,p.policy_id,p.strategy_id,p.asset_id)))}</span>`).join('');
      return `${this.tabExperienceHeader(rt,'intelligence',pageVm)}<div class="intelligencePage productPortalPage intelligenceControlCenter">${this.productStoryCard({ eyebrow:rhiEnergyT(this._hass,'intelligence.current_situation',{},'Current situation'), title:state, why, recommendation:recommendation||'', actions, tone:'purple' })}<section class="panel intelligenceManagedPanel"><div class="portalSectionHeader"><div><small>Managed energy</small><h2>Assets Home Intelligence is watching</h2><p>Only assets that currently participate in planning are shown.</p></div>${policySummary ? `<div class="policyInfluenceChips">${policySummary}</div>` : ''}</div><div class="portalStatusList">${assetRows || `<div class="empty"><b>No active planning</b><span>Home Intelligence is monitoring the home.</span></div>`}</div></section></div>`;
    }
    valueAssetIdentity(rt, item = {}) {
      const row = objectFrom(item);
      const candidateIds = [
        row.asset_id, row.consumer_id, row.consumer, row.source_asset_id,
        row.producer_asset_id, row.flexible_asset_id, row.target_asset_id
      ].map(v=>String(v||'').trim()).filter(Boolean);
      const flexible = this.flexibleAssetDomain(rt).consumerFacing().map(vm=>vm.raw || {});
      const mix = rt.consumerMixRows?.() || [];
      const aliases = (asset)=>[
        asset.asset_id, asset.consumer_id, asset.consumer, asset.source_asset_id,
        asset.producer_asset_id, asset.flexible_asset_id, asset.target_asset_id
      ].map(v=>String(v||'').trim()).filter(Boolean);
      const match = [...flexible, ...mix].find(asset => {
        const ids = aliases(asset);
        return candidateIds.some(id => ids.includes(id));
      }) || {};
      const canonicalId = String(firstDefined(match.asset_id, match.flexible_asset_id, match.source_asset_id, row.asset_id, row.source_asset_id, row.consumer_id, row.consumer, '') || '');
      const merged = { ...row, ...match, asset_id: canonicalId || row.asset_id || '' };
      const name = firstDefined(match.display_name, row.display_name, canonicalId ? rt.assetName(canonicalId) : '', '');
      return { asset:merged, id:canonicalId, name:String(name || (candidateIds.length ? human(candidateIds[0]) : 'Consumer')) };
    }

    value(rt) {
      const pageVm = this.buildPageViewModel(rt, 'value');
      const v = this.valuePeriodContext(rt);
      const money = (x) => this.valueMoney(x, v.currency, v.state, '—');
      const hasFinancialValue = [v.net,v.importCost,v.exportRevenue,v.netEnergyCost].some(value => asNumber(value) !== null);
      const pricingEditing = this.strategyEditProfileId === 'pricing_settings';
      const tariffRows = (v.tariffs || []).map(item => {
        const unit = item.row?.unit || (item.id === 'vat' ? '%' : '€/kWh');
        const valueText = item.configured ? `${fmtNumber(item.value, item.id === 'vat' ? 1 : 3, '—')} ${unit}` : '—';
        const editor = pricingEditing && item.row && item.writable ? this.editableNumberControl({ ...item.row, profile_id: 'pricing_settings' }, item.label) : `<span class="strategyReadValue">${escapeHtml(valueText)}</span>`;
        const guidance = item.configured ? (item.writable ? 'Configured value. Edit the set to change it.' : 'Supplied automatically by Pricing.') : 'This value still needs configuration.';
        return `<div class="strategyTableRow pricingStrategyRow ${item.configured ? 'configured' : 'missing'}"><div class="strategyPrimaryRow"><div class="strategySetting">${escapeHtml(item.label)}</div><div class="strategyValue">${editor}</div><div class="strategyGuidance"><i>${escapeHtml(guidance)}</i></div></div></div>`;
      }).join('');
      const pricingChanged = Object.keys(this.editDrafts || {}).filter(key => String(key).startsWith('pricing.')).length;
      const pricingActions = pricingEditing
        ? `<span class="strategyChangeCount">${pricingChanged ? `${pricingChanged} changed` : 'No changes'}</span><button class="strategyTextAction" data-strategy-cancel="pricing_settings">Cancel</button><button class="strategySaveAction" data-strategy-save="pricing_settings"${pricingChanged ? '' : ' disabled'}>Save</button>`
        : `<button class="strategyTextAction" data-strategy-edit="pricing_settings">Edit</button>`;
      const missingRequired = (v.tariffs || []).filter(item => item.required && !item.configured);
      const configurationBlocked = missingRequired.length > 0;
      const consumers = v.consumers.map(row => {
        const item=objectFrom(row);
        const identity=this.valueAssetIdentity(rt,item);
        const vm=identity.id ? this.flexibleAssetDomain(rt).byId(identity.id) : null;
        const kind=String(firstDefined(item.source_asset_kind,item.asset_type,item.object_class,item.energy_asset_role,'') || '').toLowerCase();
        if (vm?.isInfrastructure || /(^|_)(charger|connection|charging_point)(_|$)/.test(kind)) return '';
        const meta=`${human(firstDefined(item.attribution_quality,'Not available'))} · ${fmtKwh(firstDefined(item.attributed_kwh,item.energy_kwh), 'Unavailable')}`;
        return `<div class="propertyRow valueConsumerRow"><div class="valueAssetIdentity">${this.assetVisual(identity.asset,{size:'sm',fallbackIcon:'🚗'})}<span><b>${escapeHtml(identity.name)}</b><small>${escapeHtml(meta)}</small></span></div><strong>${escapeHtml(money(firstDefined(item.attributed_value,item.attributed_eur)))}</strong></div>`;
      }).filter(Boolean).join('');
      const optional = [['Savings',v.savings],['Avoided grid cost',v.avoided],['Self-consumption value',v.selfConsumption]].filter(([,value])=>asNumber(value)!==null).map(([label,value])=>this.kv(label,money(value))).join('');
      const financialBody = configurationBlocked
        ? `<section class="panel wide valueConfigurationState"><h2>${escapeHtml(rhiEnergyT(this._hass,'value.financial_result',{},'Financial result'))}</h2><div class="valueStateHeadline"><b>${escapeHtml(v.stateLabel)}</b><span>${escapeHtml(v.attention)}</span></div><p>Complete the Pricing inputs still needed for ${escapeHtml(v.label.toLowerCase())}.</p><div class="valueConfigurationChecklist">${missingRequired.map(item=>`<div><span>${item.configured?'✓':'□'}</span><b>${escapeHtml(item.label)}</b><em>${escapeHtml(item.configured?'Configured':'Setup needed')}</em></div>`).join('')}</div></section>`
        : !v.accountingReady && !hasFinancialValue
          ? `<section class="panel wide valueEvidenceState"><h2>${escapeHtml(rhiEnergyT(this._hass,'value.financial_result',{},'Financial result'))}</h2><div class="valueStateHeadline"><b>Waiting for measured evidence</b><span>${escapeHtml(v.attention)}</span></div><p>Pricing is usable. The financial result will appear when the selected Metering period contains sufficient measured import/export evidence.</p></section>`
          : `<section class="panel wide"><h2>${escapeHtml(v.label)} ${escapeHtml(rhiEnergyT(this._hass,"value.financial_result",{},"financial result").toLowerCase())}</h2><p>${escapeHtml(rhiEnergyT(this._hass,"value.period_result_desc",{},"Accumulated measured value for the Metering-selected period. No future value is predicted."))}</p><div class="r3280Balance"><span>${escapeHtml(rhiEnergyT(this._hass,"value.net_financial_result",{},"Net financial result"))}</span><b>${escapeHtml(money(v.net))}</b><p>${escapeHtml(v.interpretation)}</p></div><div class="goalGrid"><div class="goalRow"><span>Import cost</span><b>${escapeHtml(money(v.importCost))}</b></div><div class="goalRow"><span>Export revenue</span><b>${escapeHtml(money(v.exportRevenue))}</b></div><div class="goalRow"><span>Net energy cost</span><b>${escapeHtml(money(v.netEnergyCost))}</b></div><div class="goalRow"><span>Result completeness</span><b>${escapeHtml(v.resultCompletenessLabel)}</b><small>${escapeHtml(v.resultScopeLabel)}</small></div></div>${optional ? `<div class="softBox">${optional}</div>` : ''}</section>`;
      const allocationById = new Map(v.consumers.map(row => { const item=objectFrom(row); return [String(firstDefined(item.consumer_id,item.asset_id,item.consumer,'')), item]; }));
      const flexibleRows = this.flexibleAssetDomain(rt).participating().map(vm => { const asset = vm.raw;
        const id = String(firstDefined(asset.asset_id,asset.flexible_asset_id,asset.target_asset_id,''));
        const allocation = allocationById.get(id) || {};
        const power = firstDefined(asset.power_kw,asset.current_power_kw,asset.actual_power_kw);
        const attributed = firstDefined(allocation.attributed_value,allocation.attributed_eur);
        return `<div class="flexPricingRow"><div class="valueAssetIdentity">${this.assetVisual(asset,{size:'sm',fallbackIcon:this.flexibleAssetIcon(asset)})}<span><b>${escapeHtml(rt.assetName(id) || asset.display_name || human(id) || 'Flexible load')}</b><small>${escapeHtml(fmtKw(power,'Inactive'))} now</small></span></div><strong>${asNumber(attributed)!==null ? escapeHtml(money(attributed)) : 'Attribution unavailable'}</strong></div>`;
      }).join('');
      return `${this.tabExperienceHeader(rt,'value',pageVm)}${this.bodyContextBar(rt,'value','value-body')}<div id="value-body" class="valuePage r363ValuePage">
        <div class="valueGrid">${financialBody}
        <section class="panel wide strategyTablePanel pricingStrategyPanel" id="value-pricing-settings"><div class="strategyTableHead"><div><h2>${escapeHtml(rhiEnergyT(this._hass,'value.pricing_settings',{},'Pricing settings'))}</h2><p>${missingRequired.length ? `${missingRequired.length} value${missingRequired.length===1?'':'s'} still need configuration.` : 'Tariff configuration is complete.'}</p></div><div class="strategySetActions">${pricingActions}</div></div><div class="strategyTable"><div class="strategyColumnHead"><span>Setting</span><span>Value</span></div>${tariffRows}</div></section>
        <section class="panel" id="value-flexible-pricing"><h2>${escapeHtml(rhiEnergyT(this._hass,'value.flexible_pricing',{},'Pricing of flexible loads'))}</h2><p>Financial attribution is shown only when Value publishes it. The UX does not estimate costs.</p><div class="flexPricingList">${flexibleRows || `<div class="empty"><b>No controllable loads available</b><span>No controllable Energy assets are currently available.</span></div>`}</div></section>
        <section class="panel" id="value-consumers"><h2>${escapeHtml(rhiEnergyT(this._hass,'value.consumer_allocation',{},'Consumer allocation'))}</h2><p>Financial attribution by consumer for ${escapeHtml(v.label.toLowerCase())}.</p>${consumers || `<div class="empty"><b>Consumer allocation is not yet available for the selected period.</b><span>Consumer value allocation is not available yet.</span></div>`}</section>
        </div>
      </div>`;
    }

    planningAssetIcon(asset = {}) {
      const text = `${asset.asset_type || ''} ${asset.flexible_role || ''} ${asset.name || asset.display_name || ''}`.toLowerCase();
      if (/battery|storage/.test(text)) return '🔋';
      if (/car|vehicle|ev/.test(text)) return '🚘';
      if (/charger|wallbox|sideway/.test(text)) return '⚡';
      return '◆';
    }
    planningAssetTone(asset = {}) {
      const text = `${asset.asset_type || ''} ${asset.flexible_role || ''} ${asset.name || asset.display_name || ''}`.toLowerCase();
      if (/battery|storage/.test(text)) return 'green';
      if (/charger|wallbox|sideway/.test(text)) return 'orange';
      if (/car|vehicle|ev/.test(text)) return 'purple';
      return 'blue';
    }
    planningIconBadge(icon, tone = 'blue', extra = '') {
      return `<span class="planningIconBadge ${escapeHtml(tone)} ${escapeHtml(extra)}" aria-hidden="true">${escapeHtml(icon)}</span>`;
    }
    planningAssetName(asset = {}) {
      return firstDefined(asset.display_name, asset.name, asset.friendly_name, asset.label, asset.asset_id, 'Flexible asset');
    }
    assetVisual(asset = {}, { size = 'md', fallbackIcon = '◆', decorative = true } = {}) {
      // assetVisual is called from many page/card helpers that receive rt themselves.
      // Never depend on a free-scoped `rt`; resolve the current HA runtime explicitly.
      const rt = this.runtime();
      const assetId = String(firstDefined(asset.asset_id, asset.id, '') || '').trim();
      const hasPendingAppearance = Object.prototype.hasOwnProperty.call(this.pendingAppearanceByAsset || {}, assetId);
      const pendingVisualRef = hasPendingAppearance ? String(this.pendingAppearanceByAsset[assetId] || '') : '';
      const visualRef = hasPendingAppearance ? pendingVisualRef : String(firstDefined(asset.visual_ref, asset.visualRef, asset.raw?.visual_ref, '') || '').trim();
      const visualAsset = hasPendingAppearance ? { ...asset, visual_ref:pendingVisualRef } : asset;
      const resolved = typeof resolveEnergyAssetVisual === 'function'
        ? resolveEnergyAssetVisual(visualAsset, rt.visualRegistry(), size === 'lg' ? 'detail' : 'card')
        : (visualRef ? rt.resolveVisualRef(visualRef, size === 'lg' ? 'detail' : 'card') : null);
      const label = this.planningAssetName(asset);
      const assetType = String(firstDefined(asset.asset_type, asset.object_class, '') || '').trim().toLowerCase();
      const pickerChoices = typeof rhiEnergyVisualCatalogForType === 'function' ? rhiEnergyVisualCatalogForType(assetType) : [];
      const registeredOwner = visualRef ? String(rt.visualRegistry()?.entry?.(visualRef)?.owner_domain || '').trim() : '';
      const externallyOwned = !!registeredOwner && !['rhi_energy','rhi_energy_ux'].includes(registeredOwner);
      const appearance = objectFrom(asset.appearance || {});
      const appearanceProperty = assetId ? rt.editableProperty(`appearance:${assetId}:visual_ref`) : null;
      const canPick = !!assetId
        && !externallyOwned
        && appearance.editable === true
        && pickerChoices.length > 0
        && this.isWritableRow(appearanceProperty);
      const pickerAttrs = canPick
        ? ` data-energy-visual-open="${escapeHtml(assetId)}" role="button" tabindex="0" title="Choose representative image"`
        : '';
      if (resolved?.url) {
        const alt = decorative ? '' : label;
        return `<span class="assetVisual assetVisual-${escapeHtml(size)}"${pickerAttrs}><img src="${escapeHtml(resolved.url)}" alt="${escapeHtml(alt)}" style="filter:${escapeHtml(resolved.filter || 'none')}">${canPick ? '<span class="assetVisualAppearance">Appearance</span>' : ''}</span>`;
      }
      return `<span class="assetVisual assetVisual-${escapeHtml(size)} assetVisualFallback"${pickerAttrs} aria-hidden="${canPick ? 'false' : 'true'}">${escapeHtml(fallbackIcon)}${canPick ? '<span class="assetVisualAppearance">Appearance</span>' : ''}</span>`;
    }
    energyVisualPickerOverlay(rt) {
      const assetId = String(this.energyVisualPickerAssetId || '').trim();
      if (!assetId) return '';
      const asset = typeof rt.asset === 'function'
        ? rt.asset(assetId)
        : (typeof rt.assets === 'function' ? rt.assets().find(row => String(row?.asset_id || '') === assetId) : null);
      if (!asset) return '';
      const type = String(firstDefined(asset.asset_type, asset.object_class, '') || '').trim().toLowerCase();
      const choices = typeof rhiEnergyVisualCatalogForType === 'function' ? rhiEnergyVisualCatalogForType(type) : [];
      if (!choices.length) return '';
      const selected = String(firstDefined(
        asset.appearance?.configured_visual_ref,
        asset.appearance?.effective_visual_ref,
        asset.visual_ref,
        ''
      ) || '');
      const fallbackEntry = typeof rhiEnergyDefaultVisualEntry === 'function' ? rhiEnergyDefaultVisualEntry(asset) : null;
      const current = selected || (fallbackEntry && typeof rhiEnergyVisualRef === 'function' ? rhiEnergyVisualRef(fallbackEntry) : '');
      const picker = new HomeBrainEnergyVisualPicker();
      return picker.render(asset, current, {
        draftRef: this.energyVisualPickerDraftRef || current,
        brand: this.energyVisualPickerBrand || 'all'
      });
    }
    assetIdentityChip(asset = {}, meta = '') {
      return `<span class="assetIdentityChip">${this.assetVisual(asset,{size:'xs',fallbackIcon:this.planningAssetIcon(asset)})}<span><b>${escapeHtml(this.planningAssetName(asset))}</b>${meta ? `<small>${escapeHtml(meta)}</small>` : ''}</span></span>`;
    }
    planningEnergyNeed(asset = {}) {
      return asNumber(firstDefined(asset.energy_to_target_kwh, asset.energy_needed_kwh, asset.remaining_energy_kwh, asset.energy_need_kwh));
    }
    planningBucketHour(bucket = {}) {
      const raw = firstDefined(bucket.start, bucket.start_time, bucket.bucket_start, bucket.local_start, bucket.hour, bucket.label, '');
      if (typeof raw === 'number') return Math.max(0, Math.min(23, Math.floor(raw)));
      const text = String(raw || '');
      const iso = text.match(/T(\d{2}):/); if (iso) return Number(iso[1]);
      const hm = text.match(/(?:^|\s)(\d{1,2})(?::\d{2})?/); return hm ? Math.max(0, Math.min(23, Number(hm[1]))) : null;
    }
    planningAllocations(bucket = {}) {
      let rows = parseMaybeJson(bucket.asset_allocations_json, null)
        || parseMaybeJson(bucket.asset_allocations, null)
        || parseMaybeJson(bucket.allocations_json, null)
        || parseMaybeJson(bucket.allocations, null)
        || parseMaybeJson(bucket.asset_allocation, null)
        || [];
      if (!Array.isArray(rows) && rows && typeof rows === 'object') rows = Object.entries(rows).map(([asset_id, value]) => ({ asset_id, ...objectFrom(value) }));
      return Array.isArray(rows) ? rows : [];
    }
    buildPlanningViewModel(rt) {
      const horizonId = this.selectedPlanningHorizonId || 'D0';
      const domainAssets = this.flexibleAssetDomain(rt).all();
      // Tactical Planning keeps every real managed consumer visible. Eligibility
      // controls allocation, not visibility; infrastructure-only charger fallbacks
      // stay outside this product view.
      const assets = this.flexibleAssetDomain(rt).consumerFacing().map(vm => vm.raw);
      const storage = domainAssets.find(vm => vm.isStorage && !vm.isDisabled)?.raw || null;
      return createPlanningViewModel({ runtime: rt, horizonId, flexibleAssets: assets, storage });
    }

    planningParticipant(row, lane, participantId) {
      return (row?.[lane] || []).find(item => String(item.participantId) === String(participantId)) || null;
    }
    planningTimeLabel(value) {
      const text = String(value || '');
      const match = text.match(/T(\d{2}:\d{2})/);
      return match ? match[1] : (text || '—');
    }
    planningLaneCell(participant, { advisory = false, signed = false } = {}) {
      if (!participant || participant.energyKwh === null) return `<span class="planningUnavailable">—</span>`;
      const value = participant.energyKwh;
      return `<span class="planningPowerValue ${signed ? 'planningImport' : ''} ${value <= 0.001 ? 'planningIdle' : ''}">${value.toFixed(1)}</span>`;
    }
    planningProviderControls(rt) {
      const states=rt.hass?.states || {};
      const source=(contract)=>Object.entries(states).filter(([id,state])=>
        id.startsWith('select.') && state?.attributes?.canonical_contract===contract &&
        state?.attributes?.write_authority==='rhi_energy.config_entry.options');
      const control=(contract,kind,label)=>{
        const matches=source(contract);
        if(matches.length!==1) return `<span class="planningControlUnavailable">${escapeHtml(label)}: Not available</span>`;
        const [entityId,state]=matches[0];
        const options=asArray(state.attributes?.options).filter(x=>typeof x==='string');
        const selected=String(state.state || '');
        return `<label class="settingsVariantSelect"><span>${escapeHtml(label)}</span><select data-planning-select="${kind}" data-planning-entity="${escapeHtml(entityId)}"${options.length?'':' disabled'}>${options.map(option=>`<option value="${escapeHtml(option)}"${option===selected?' selected':''}>${escapeHtml(kind==='resolution'?option+' min':human(option))}</option>`).join('')}</select></label>`;
      };
      const provider=source('RHI_ENERGY_PLANNER_PROVIDER_CATALOG_V1');
      const attrs=provider.length===1?provider[0][1].attributes || {}:{};
      const effective=String(attrs.effective_provider || '');
      const reason=String(attrs.selection_reason || '');
      const modeRow=rt.row('energy.operating_mode');
      const mode=String(rowValue(modeRow,'advice') || 'advice');
      return `<section class="panel compact planningConfiguration"><div class="meteringCardHead"><div><h2>Planning & automation</h2><p>One Energy planning contract for RHI and external planners.</p></div></div><div class="planningAggregateTotals">
      ${control('RHI_ENERGY_PLANNER_PROVIDER_CATALOG_V1','provider','Planner')}
      ${control('RHI_ENERGY_PLANNING_RESOLUTION_V1','resolution','Resolution')}
      <div class="planningModeControl">${this.modeSelector(rt,mode)}<small>Off: observe only · Advice: recommend and await approval · Automatic: act only within strategy and physical safety gates.</small></div>
      <span><small>Effective planner</small><b>${escapeHtml(effective?human(effective):'On hold')}</b><small>${escapeHtml(!effective?humanReason(reason,'Missing source evidence'):'Energy-owned validated planning')}</small></span>
      </div></section>`;
    }
    planning(rt) {
      const vm = this.buildPlanningViewModel(rt);
      const horizonLabel = vm.horizonId === 'D2'
        ? rhiEnergyT(this._hass,'planning.day_after_tomorrow',{},'Day after tomorrow')
        : vm.horizonId === 'D1' ? 'Tomorrow' : 'Today';
      const assetKey = asset => String(asset.asset_id || asset.id || '');
      const totals = vm.laneTotals;
      const canonicalAssetsById = vm.planningAssetsById || {};
      const assetTotalsById = totals.flexibleAssetsById;
      const plannedForAsset = assetId => {
        const raw = assetTotalsById[assetId];
        if (raw === undefined || raw === null) return null;
        if (typeof raw === 'number') return asNumber(raw);
        const row = objectFrom(raw);
        return asNumber(firstDefined(row.energy_kwh, row.planned_energy_kwh, row.total_kwh, row.value));
      };
      const allAssetTotals = vm.assets.map(asset => {
        const canonical = objectFrom(canonicalAssetsById[assetKey(asset)] || vm.planningAssets.find(row => String(row.asset_id || '') === assetKey(asset)) || {});
        const published = objectFrom(assetTotalsById[assetKey(asset)]);
        return {
          asset,
          canonical,
          need: asNumber(firstDefined(canonical.energy_need_kwh,canonical.need_kwh,published.energy_need_kwh,asset.energy_to_target_kwh)),
          plannedEnergy: vm.horizonId === 'D2' ? asNumber(canonical.planned_day_after_tomorrow_kwh)
            : vm.horizonId === 'D1' ? asNumber(canonical.planned_tomorrow_kwh)
            : asNumber(canonical.planned_today_kwh),
          // "Still after today" is not "Still after tomorrow". In particular
          // D2 may be a rolling partial EMHASS horizon with NO per-asset
          // residual; never reuse a D1 residual or infer it from buckets.
          remainingNeed: vm.horizonId === 'D2'
            ? asNumber(canonical.still_after_day_after_tomorrow_kwh)
            : vm.horizonId === 'D1'
            ? asNumber(canonical.still_to_plan_kwh)
            : asNumber(canonical.still_after_today_kwh)
        };
      });
      const hourlyAssetEnergy = assetId => vm.rows.reduce((sum,row) => {
        const value = this.planningParticipant(row,'consumers',assetId)?.energyKwh;
        return sum + (value === null || value === undefined ? 0 : Math.max(0,Number(value) || 0));
      }, 0);
      // Tactical Planning shows every real planning participant. Zero/no-plan is
      // a valid state and must not make a vehicle disappear from the horizon.
      const assetTotals = allAssetTotals;

      const solarTotal = totals.solarKwh;
      const batteryOutTotal = totals.homeBatteryOutKwh;
      const gridInTotal = totals.gridInKwh;
      const homeTotal = totals.homeKwh;
      const flexibleLoadsTotal = totals.flexibleLoadsKwh;
      const batteryInTotal = totals.homeBatteryInKwh;
      const gridOutTotal = totals.gridOutKwh;
      const sourceTotal = totals.sourceTotalKwh;
      const useTotal = totals.useTotalKwh;
      const balanceDelta = totals.balanceDeltaKwh;
      const batteryNeed = totals.homeBatteryNeedKwh;
      const showLane = value => value === null || Math.abs(value) > 0.001;
      const systemLanes = [
        {id:'solar',group:'sources',label:rhiEnergyT(this._hass,'planning.solar',{},'Solar'),icon:'☀',tone:'orange',total:solarTotal,participantLane:'sources',participantId:'solar'},
        {id:'batteryOut',group:'sources',label:rhiEnergyT(this._hass,'planning.battery_out',{},'Home Battery out'),icon:'▣',tone:'green',total:batteryOutTotal,participantLane:'sources',participantId:'battery'},
        {id:'gridIn',group:'sources',label:rhiEnergyT(this._hass,'planning.grid_in',{},'Grid in'),icon:'↘',tone:'slate',total:gridInTotal,participantLane:'sources',participantId:'grid',signed:true},
        {id:'home',group:'consumers',label:rhiEnergyT(this._hass,'planning.home',{},'Home'),icon:'⌂',tone:'blue',total:homeTotal,participantLane:'consumers',participantId:'home'},
        {id:'batteryIn',group:'consumers',label:rhiEnergyT(this._hass,'planning.battery_in',{},'Home Battery in'),icon:'▣',tone:'green',total:batteryInTotal,participantLane:'consumers',participantId:'battery',advisory:true},
        // Grid out is the fixed boundary lane and must remain the final column.
        // Flexible Loads is not a system lane: individual flexible assets are rendered as columns.
        {id:'gridOut',group:'boundary',label:rhiEnergyT(this._hass,'planning.grid_out',{},'Grid out'),icon:'↗',tone:'slate',total:gridOutTotal,boundary:true,alwaysVisible:true}
      ].filter(lane => lane.alwaysVisible || showLane(lane.total));

      const sourceLaneCount = systemLanes.filter(l => l.group === 'sources').length;
      const consumerLaneCount = systemLanes.filter(l => l.group === 'consumers').length + assetTotals.length;
      const boundaryLaneCount = systemLanes.filter(l => l.group === 'boundary').length;
      const systemHeaders = systemLanes.filter(l => l.group !== 'boundary').map(lane => `<th><span class="planningColumnHead">${this.planningIconBadge(lane.icon,lane.tone,'system')}<b>${escapeHtml(lane.label)}</b><small>kWh</small></span></th>`).join('');
      const assetHeaders = assetTotals.map(item => `<th><span class="planningAssetHead">${this.assetVisual(item.asset,{size:'xs',fallbackIcon:this.planningAssetIcon(item.asset)})}<span><b>${escapeHtml(this.planningAssetName(item.asset))}</b><small class="planningHeaderNeed">${item.need===null?'Need —':`Need ${item.need.toFixed(1)} kWh`}</small></span></span><small class="planningUnit">kWh</small></th>`).join('');
      const boundaryHeaders = systemLanes.filter(l => l.group === 'boundary').map(lane => `<th><span class="planningColumnHead">${this.planningIconBadge(lane.icon,lane.tone,'system')}<b>${escapeHtml(lane.label)}</b><small>kWh</small></span></th>`).join('');
      const laneCell = (row,lane) => {
        if (lane.aggregateOnly) {
          const value = row.consumers.filter(item => assetTotals.some(a => assetKey(a.asset) === String(item.participantId))).reduce((sum,item) => sum + (item.energyKwh || 0),0);
          return value <= 0.001 ? '' : value.toFixed(1);
        }
        if (lane.boundary) {
          const value = row.boundary.gridExportKwh;
          return value === null ? '<span class="planningUnavailable">—</span>' : (value <= 0.001 ? '' : `<span class="planningExport">${value.toFixed(1)}</span>`);
        }
        const participant = this.planningParticipant(row,lane.participantLane,lane.participantId);
        if (!participant || participant.energyKwh === null) return '<span class="planningUnavailable">—</span>';
        return participant.energyKwh <= 0.001 ? '' : `<span class="planningPowerValue ${lane.signed?'planningImport':''}">${participant.energyKwh.toFixed(1)}</span>`;
      };
      const rows = vm.rows.map(row => {
        const current = vm.horizonId === 'D0' && row.id === vm.currentBucketId;
        const fixedCells = systemLanes.filter(l => l.group !== 'boundary').map(lane => `<td>${laneCell(row,lane)}</td>`).join('');
        const assetCells = assetTotals.map(item => `<td>${laneCell(row,{participantLane:'consumers',participantId:assetKey(item.asset)})}</td>`).join('');
        const boundaryCells = systemLanes.filter(l => l.group === 'boundary').map(lane => `<td>${laneCell(row,lane)}</td>`).join('');
        return `<tr class="${current?'planningCurrent':''}"><td><span class="planningTime">${current?'<em>NOW</em>':''}${escapeHtml(this.planningTimeLabel(row.startTime))}</span></td>${fixedCells}${assetCells}${boundaryCells}</tr>`;
      }).join('');
      const totalCell = (value,small='Planning total',{showZero=false}={}) => `<td><b>${value===null?'—':(Math.abs(value) <= 0.001 ? (showZero?'0.0 kWh':'') : value.toFixed(1)+' kWh')}</b><small>${value!==null && Math.abs(value) <= 0.001 && !showZero ? '' : escapeHtml(small)}</small></td>`;
      const fixedTotalCells = systemLanes.filter(l => l.group !== 'boundary').map(lane => totalCell(lane.total,lane.id==='batteryIn'&&batteryNeed!==null?`${batteryNeed.toFixed(1)} kWh target need`:'Planning total')).join('');
      const assetTotalCells = assetTotals.map(item => `<td class="planningTotalAsset"><b>${item.plannedEnergy===null?'—':item.plannedEnergy.toFixed(1)+' kWh'}</b><small>${item.need===null?'Need unavailable':`of ${item.need.toFixed(1)} kWh needed`}</small></td>`).join('');
      const boundaryTotalCells = systemLanes.filter(l => l.group === 'boundary').map(lane => totalCell(lane.total,'Planning total',{showZero:true})).join('');

      const canonicalTotals = vm.horizonId === 'D0'
        ? objectFrom(vm.todayTotals)
        : vm.horizonId === 'D1' ? objectFrom(vm.tomorrowTotals)
        : objectFrom(vm.dayAfterTotals);
      const totalNeed = asNumber(canonicalTotals.flexible_required_kwh);
      const totalPlanned = asNumber(canonicalTotals.flexible_planned_kwh);
      const remainingNeed = asNumber(canonicalTotals.flexible_still_to_plan_kwh);
      const displayNeed = vm.complete ? totalNeed : null;
      const displayPlanned = vm.complete ? totalPlanned : null;
      const displayRemaining = vm.complete ? remainingNeed : null;
      const planStatus = String(firstDefined(vm.currentActionIntent.action_state, vm.currentActionIntent.state, vm.summary.plan_status, vm.horizon.status, vm.horizon.state, vm.complete?'available':'unavailable'));
      const confidence = firstDefined(vm.quality.confidence, vm.horizon.confidence, 'Limited');
      const statusLabel = vm.previewOnly ? 'Preview only · No execution' :
        /at.?risk/i.test(planStatus) ? 'At risk' : this.productStateLabel(planStatus, vm.complete?'Forecast plan':'Plan unavailable');
      const plannedTotals = assetTotals.map(item => `<span class="planningFooterAsset">${this.assetVisual(item.asset,{size:'xs',fallbackIcon:this.planningAssetIcon(item.asset)})}<b>${escapeHtml(this.planningAssetName(item.asset))}</b> ${item.plannedEnergy===null?'—':item.plannedEnergy.toFixed(1)+' kWh'}</span>`).join('');
      const summaryItems = vm.horizonId === 'D2'
        ? [[rhiEnergyT(this._hass,'planning.d2_need',{},'Need entering day after tomorrow'),displayNeed],
           [rhiEnergyT(this._hass,'planning.d2_planned',{},'Planned day after tomorrow'),displayPlanned],
           [rhiEnergyT(this._hass,'planning.d2_remaining',{},'Still after day after tomorrow'),displayRemaining]]
        : vm.horizonId === 'D1'
        ? [['Need entering tomorrow',displayNeed],['Planned tomorrow',displayPlanned],['Still after tomorrow',displayRemaining]]
        : [['Need entering today',displayNeed],['Planned today',displayPlanned],['Still after today',displayRemaining]];
      const summaryTotals = `<div class="planningAggregateTotals">${summaryItems.map(([label,value])=>`<span><small>${label}</small><b>${value===null?'—':value.toFixed(1)+' kWh'}</b></span>`).join('')}</div>`;
      const disclosure = firstDefined(vm.rows.find(row=>row.disclosure)?.disclosure, vm.quality.basis ? `Planning basis: ${human(vm.quality.basis)}. Actual execution follows the current operational intent.` : 'Future buckets are advisory. Actual execution follows the current operational intent.');
      const balanceLabel = sourceTotal===null || useTotal===null ? 'Planning balance unavailable' : `${sourceTotal.toFixed(1)} kWh source · ${useTotal.toFixed(1)} kWh use${balanceDelta===null?'':` · Δ ${balanceDelta.toFixed(2)} kWh`}`;
      const heroValue = displayPlanned===null ? '—' : displayPlanned.toFixed(1)+' kWh';
      const planningHeader = {
        image:hbEnergyHeroAsset('solar-generation'),
        icon:'▣',
        eyebrow:rhiEnergyT(this._hass,'planning.tactical',{},'Tactical planning'),
        title:`${horizonLabel} plan`,
        value:heroValue,
        unit:displayNeed===null?'planned flexible energy':`of ${displayNeed.toFixed(1)} kWh flexible need`,
        explanation:displayRemaining===null?'Remaining need is unavailable.':`${displayRemaining.toFixed(1)} kWh still needs a suitable opportunity.`,
        tone:'purple',
        badgeText:vm.contractSupported ? statusLabel : 'Unavailable',
        badgeTone:vm.contractSupported && vm.complete ? 'ok' : 'attention',
        metrics:[
          ['◎',summaryItems[0][0],fmtKwh(displayNeed,'—'),horizonLabel],
          ['▣',summaryItems[1][0],fmtKwh(displayPlanned,'—'),horizonLabel],
          ['◷',summaryItems[2][0],fmtKwh(displayRemaining,'—'),'Horizon-local residual'],
          ['✓','Confidence',this.productStateLabel(confidence,'Limited'),'Planning confidence']
        ]
      };
      if (!vm.contractSupported) {
        const status=objectFrom(rt.canonicalProduct()?.planning?.provider_status || {});
        const requested=String(status.requested_provider || 'Selected planner');
        const observed=String(status.requested_runtime_reason || status.selection_reason || 'No complete effective provider output');
        const alternative=status.baseline_available === true
          ? 'A deterministic baseline is available, but it is not the selected effective plan. No automatic fallback or physical execution is permitted.'
          : 'No provider-owned baseline is currently published.';
        const reason=status.requested_provider
          ? `Planner ${requested} is on hold: ${observed}. ${alternative}`
          : 'No effective planning provider is currently published. Check the Energy planner configuration and source completeness.';
        return `${this.tabExperienceHeader(rt,'planning',planningHeader)}${this.planningProviderControls(rt)}${this.contractGap('Tactical planning unavailable',reason)}`;
      }
      const participatingCount = assetTotals.length;
      const nextLines = assetTotals.map(item => this.assetIdentityChip(item.asset,fmtKw(firstDefined(item.asset.requested_power_kw,item.asset.requested_charge_power_kw,item.asset.requested_power_kw_effective),'—'))).join('');
      const planningLoadRows = assetTotals.map(item => {
        const canonical=item.canonical||{};
        const nextRaw=String(firstDefined(canonical.what_text,canonical.next_action_label,canonical.next_action,canonical.today_label,'') || '').trim();
        const next=nextRaw && !/^(wait|none)$/i.test(nextRaw) ? human(nextRaw) : '';
        const whyRaw=String(firstDefined(canonical.why_text,canonical.reason_label,canonical.reason,'') || '').trim();
        const why=whyRaw && !/^(none|no explanation available\.?|no explanation published\.?)$/i.test(whyRaw) ? humanReason(whyRaw,'') : '';
        const eligibility = canonical.planning_eligible === true ? 'Planning ready' : String(firstDefined(canonical.user_status,item.asset.user_status,'Incomplete'));
        const planStatus = firstDefined(canonical.planning_status,canonical.plan_conformance_label,canonical.exception_label,canonical.risk_label,eligibility);
        const facts=[
          ['Energy needed',fmtKwh(item.need,'—')],
          ['Planned today',fmtKwh(asNumber(canonical.planned_today_kwh),'—')],
          ['Planned tomorrow',fmtKwh(asNumber(canonical.planned_tomorrow_kwh),'—')],
          ['Still to plan',fmtKwh(item.remainingNeed,'—')],
          ['Requested power',fmtKw(firstDefined(item.asset.requested_power_kw_effective,item.asset.requested_power_kw,item.asset.requested_charge_power_kw),'—')],
          next ? ['Next action',next] : null,
          why ? ['Reason',why] : null
        ].filter(Boolean);
        return `<article class="planningLoadRow compactPlanningLoad"><div class="planningLoadIdentity">${this.assetVisual(item.asset,{size:'sm',fallbackIcon:this.planningAssetIcon(item.asset)})}<div><b>${escapeHtml(this.planningAssetName(item.asset))}</b><small>${escapeHtml(eligibility)}</small></div></div><div class="compactPlanningFacts">${facts.map(([label,value])=>`<span><small>${escapeHtml(label)}</small><b>${escapeHtml(value)}</b></span>`).join('')}</div><b class="planStatusBadge ${/at.?risk|blocked|failed|incomplete/i.test(String(planStatus))?'exception':'unknown'}">${escapeHtml(planStatus)}</b></article>`;
      }).join('');
      const incompletePlanningRows = asArray(vm.assets).filter(asset => asset && asset.planning_input_ready === false).map(asset => { const blockers=asArray(asset.planning_blockers); const userReason=blockers.includes('target_soc_not_configured')?'Set a target charge level.':blockers.includes('ready_by_not_configured')?'Set a ready-by time.':blockers.includes('charger_not_assigned')?'Assign a charger.':'Charging information is incomplete.'; return `<article class="planningLoadRow planningInputIncomplete"><div class="planningLoadIdentity">${this.assetVisual(asset,{size:'sm',fallbackIcon:this.planningAssetIcon(asset)})}<div><div class="planningLoadName"><b>${escapeHtml(this.planningAssetName(asset))}</b></div><small>${escapeHtml(userReason)}</small></div></div><div><small>Current charge</small><b>${fmtPct(asset.current_soc_pct)}</b></div><div><small>${escapeHtml(rhiEnergyT(this._hass,"planning.target",{},"Target"))}</small><b>${fmtPct(asset.target_soc_pct)}</b></div><div><small>Ready by</small><b>${escapeHtml(asset.ready_by || 'Not set')}</b></div><div><small>Charging power</small><b>${fmtKw(asset.max_power_kw,'—')}</b></div><div><small>Status</small><b class="planStatusBadge exception">Needs setup</b></div></article>`; }).join('');
      return `${this.tabExperienceHeader(rt,'planning',planningHeader)}
      ${this.planningProviderControls(rt)}
      ${vm.previewOnly ? '<section class="panel compact"><b>Read-only deterministic preview</b><p>Provider held or input evidence incomplete. No automatic execution is authorized.</p></section>' : ''}
      ${this.bodyContextBar(rt,'planning','planning-body')}
      <div id="planning-body" class="planningPage"><section class="panel planningMatrixPanel"><div class="planningMatrixHead"><div><h2>${horizonLabel} energy allocations</h2><p>${escapeHtml(rhiEnergyT(this._hass,'planning.hourly_desc',{},'Hourly view of expected production, consumption, storage and grid exchange.'))}</p></div><span>Energy per interval (kWh)</span></div><div class="planningTableWrap"><table class="planningTable planningLaneTable"><thead><tr class="planningLaneGroups"><th rowspan="2"><span class="planningSystemHead">${this.planningIconBadge('◷','blue','system')}<b>Time</b></span></th>${sourceLaneCount?`<th colspan="${sourceLaneCount}">Sources</th>`:''}${consumerLaneCount?`<th colspan="${consumerLaneCount}">Consumers</th>`:''}${boundaryLaneCount?`<th colspan="${boundaryLaneCount}">Boundary</th>`:''}</tr><tr>${systemHeaders}${assetHeaders}${boundaryHeaders}</tr></thead><tbody>${rows}<tr class="planningTotalSpacer" aria-hidden="true"><td colspan="${1+sourceLaneCount+consumerLaneCount+boundaryLaneCount}"></td></tr><tr class="planningTotalRow"><th><b>TOTAL</b><small>for this period</small></th>${fixedTotalCells}${assetTotalCells}${boundaryTotalCells}</tr></tbody></table></div><div class="planningFooter"><div><small>Planned flexible energy (${horizonLabel.toLowerCase()})</small><div>${plannedTotals || '<span>—</span>'}</div>${summaryTotals}</div><div><small>Planning balance</small><b>${escapeHtml(balanceLabel)}</b></div><div><small>Confidence</small><b>${escapeHtml(this.productStateLabel(confidence,'Limited'))}</b></div><div><small>Operational rule</small><b>${escapeHtml(disclosure)}</b></div></div></section></div><section class="panel plannedFlexibleLoads" id="planning-flexible-loads"><div class="energySectionHead"><div><h2>Planned flexible loads</h2><p>Loads Home Intelligence is currently planning for this period.</p></div></div><div class="planningLoadList">${planningLoadRows || incompletePlanningRows || '<div class="empty"><b>No flexible loads currently need planning</b></div>'}</div></section>`;
    }

    strategicPlanning(rt) {
      const base = this.buildPageViewModel(rt, 'strategies');
      const topics = rt.strategyBehaviorTopics();
      const valueText = row => {
        const value = firstDefined(row.effective_value,row.value,row.configured_value,row.selected_value,row.current_value,null);
        if (value === null || value === undefined || value === '') return 'Not available';
        return this.genericValueWithUnit(value, firstDefined(row.unit,row.native_unit,''));
      };
      const topicCards = topics.map(topic => {
        const properties = asArray(topic.properties);
        const lines = properties.slice(0,8).map(row => {
          const label = this.profileFieldLabel(row);
          return `<div class="strategicBehaviorRow"><span>${escapeHtml(label)}</span><b>${escapeHtml(valueText(row))}</b></div>`;
        }).join('');
        return `<section class="panel strategicBehaviorCard"><h2>${escapeHtml(topic.topic_label || human(topic.topic_id))}</h2><div class="strategicBehaviorRows">${lines || `<div class="empty compact"><span>${escapeHtml(rhiEnergyT(this._hass,'planning.no_effective',{},'No effective values available.'))}</span></div>`}</div></section>`;
      }).join('');

      const allProperties = topics.flatMap(topic => asArray(topic.properties));
      const automationRow = allProperties.find(row => String(firstDefined(row.property_id,row.property_key,row.key,'') || '') === 'energy.automation_mode') || null;
      const objectiveRow = allProperties.find(row => ['home.primary_objective','strategy.home.primary_objective'].includes(String(firstDefined(row.property_id,row.property_key,row.key,'') || ''))) || null;
      const mode = automationRow ? valueText(automationRow) : this.productStateLabel(rt.value('energy_intelligence.automation_mode','advice'),'Advice');
      const objective = objectiveRow ? valueText(objectiveRow) : '';
      const posture = [mode,objective].filter(value=>value && value!=='Not available').join(' · ');
      const model = {
        ...base,
        image:hbEnergyHeroAsset('strategic-planning'),
        title:rhiEnergyT(this._hass,'planning.strategic',{},'Strategic Planning'),
        explanation:'What your current Energy settings mean for longer-term behavior.',
        metrics:[
          ['◎','Strategy',posture || 'Not available','Current longer-term posture'],
          ['◇','Topics',String(topics.length),'Policy areas influencing your strategy'],
          ['↗','Tactical horizon','D0 / D1','Today and tomorrow remain in Tactical Planning']
        ]
      };
      return `${this.tabExperienceHeader(rt,'strategic-planning',model)}
        ${this.bodyContextBar(rt,'strategic-planning','strategic-planning-body')}
        <div id="strategic-planning-body" class="strategicPlanningPage strategicBehaviorPage">
          <section class="panel strategicPlanningIntro compactStrategicIntro"><small>LONGER-TERM BEHAVIOR</small><h2>${escapeHtml(posture || rhiEnergyT(this._hass,'planning.not_available',{},'Strategy not available'))}</h2><p>This view explains how your current settings influence longer-term energy behavior. Today and tomorrow remain visible in Planning.</p></section>
          <div class="strategicBehaviorGrid">${topicCards || `<section class="panel"><div class="empty"><b>${escapeHtml(rhiEnergyT(this._hass,'planning.no_long_term',{},'No long-term strategy available'))}</b><span>${escapeHtml(rhiEnergyT(this._hass,'planning.no_long_term_desc',{},'Long-term strategy details are not available yet.'))}</span></div></section>`}</div>
        </div>`;
    }

    navigationPlaceholder(rt, view) {
      if (view === 'solar-generation') {
        const p = this.buildPageViewModel(rt, 'solar');
        const model = { ...p, title:rhiEnergyT(this._hass,'planning.solar_generation',{},'Solar generation'), badgeText:'Structure ready', badgeTone:'neutral' };
        return `${this.tabExperienceHeader(rt,'solar-generation',model)}<section class="panel navigationPlaceholder"><small>ENERGY DOMAIN</small><h2>${escapeHtml(rhiEnergyT(this._hass,'planning.solar_unavailable',{},'Solar generation details are not available yet'))}</h2><p>${escapeHtml(rhiEnergyT(this._hass,'common.information_missing',{},'This information is not available yet.'))}</p></section>`;
      }
      return `<section class="panel navigationPlaceholder"><h2>${escapeHtml(human(view))}</h2><p>${escapeHtml(rhiEnergyT(this._hass,'planning.no_renderer',{},'This navigation target has no dedicated renderer.'))}</p></section>`;
    }
    placeholder(rt) {
      return `<section class="panel cleanPlaceholder"><h2>${escapeHtml(this.title())}</h2><p>${escapeHtml(rhiEnergyT(this._hass,'common.information_missing',{},'This information is not available yet.'))}</p></section>`;
    }
    renderMainWarning(footer) {
      // R3.45.5: backend trust is a footer concern only.
      // Hard-gate failures must stay visible, but not as a main screen banner.
      return '';
    }
    diagnosticSpec(_tab) {
      // Core UI trust is determined by the canonical property index.
      // A disabled diagnostic release sensor must not create a false issue.
      return [];
    }
    diagnosticEntity(rt, entityId, label, purpose) {
      const raw = rt.rawState(entityId);
      const allowed = rt.isAllowed(entityId);
      const state = String(raw?.state ?? '').trim();
      const unavailable = !raw || ['unknown','unavailable',''].includes(state.toLowerCase());
      return { entityId, label, purpose, raw, allowed, state,
        working: !!raw && allowed && !unavailable,
        reason: unavailable ? 'Unavailable' : '' };
    }
    releaseIssueModel(rt, tab, footer) {
      const issues = [];
      if (!footer.runtimeTrusted) issues.push('Canonical Energy property contract is unavailable or incompatible.');
      if (this._flowRenderFailure && tab === 'flow') issues.push('Flow detail rendering error: ' + this._flowRenderFailure);
      if (!issues.length) return null;
      return {severity:'error',label:issues.length + ' issue' + (issues.length===1?'':'s'),tooltip:issues.join('\\n')};
    }
    diagnosticsPanel() {
      // Release/diagnostic details stay silent while healthy and live in the compact footer tooltip on issues.
      return '';
    }
    renderFooter(rt, tab, footer) {
      // Release identity and health are always visible; only expanded diagnostic details are optional.
      const backend = footer.backendVersion || 'Unknown';
      const contract = footer.contractVersion || 'Unknown';
      const issue = this.releaseIssueModel(rt, tab, footer);
      const status = issue ? (issue.severity === 'error' ? 'Attention' : 'Degraded') : (footer.runtimeTrusted === false ? 'Attention' : 'Ready');
      return rhiUxTechnicalFooter({
        product:'RHI Energy',
        uxVersion:footer.uxVersion || UX_VERSION,
        backendVersion:backend,
        issue:issue ? `${issue.label} · contract ${contract}` : `Status ${status}`,
        severity:issue?.severity || ''
      });
    }
    renderError(view, error) {
      const message = error && error.message ? error.message : String(error || 'Unknown render error');
      const stack = error && error.stack ? String(error.stack).split('\n').slice(0, 4).join('\n') : '';
      const diagnostics = this.config?.show_diagnostics === true
        ? `<div class="softBox"><b>${escapeHtml(rhiEnergyT(this._hass,"common.error",{},"Error"))}</b><span>${escapeHtml(message)}</span></div>${stack ? `<pre class="decisionDump">${escapeHtml(stack)}</pre>` : ''}`
        : '';
      return `<section class="panel"><h2>${escapeHtml(human(view))} unavailable</h2><p>${escapeHtml(rhiEnergyT(this._hass,'common.information_missing',{},'This information is not available yet.'))}</p>${diagnostics}</section>`;
    }
    viewContent(rt) {
      const body = this.view === 'overview' ? this.overview(rt) : this.view === 'outlook' ? this.outlook(rt) : this.view === 'flow' ? this.flow(rt) : this.view === 'solar' ? this.solar(rt) : this.view === 'operational-planning' ? this.operationalPlanning(rt) : this.view === 'battery' ? this.battery(rt) : this.view === 'consumers' ? this.consumers(rt) : this.view === 'gas' ? this.gas(rt) : this.view === 'strategies' ? this.strategies(rt) : this.view === 'metering' ? this.metering(rt) : this.view === 'intelligence' ? this.intelligence(rt) : this.view === 'retrospective' ? this.retrospective(rt) : this.view === 'value' ? this.value(rt) : this.view === 'planning' ? this.planning(rt) : this.view === 'strategic-planning' ? this.strategicPlanning(rt) : this.placeholder(rt);
      const marker = '</section>';
      const headerEnd = body.indexOf(marker);
      if (headerEnd < 0) return body;
      const split = headerEnd + marker.length;
      return `${body.slice(0, split)}<div id="hi-body-${escapeHtml(this.view)}">${body.slice(split)}</div>`;
    }
    patchDomNode(current, next) {
      if (!current || !next) return;
      if (current.nodeType !== next.nodeType || current.nodeName !== next.nodeName) {
        current.replaceWith(next.cloneNode(true));
        return;
      }
      if (current.nodeType === Node.TEXT_NODE || current.nodeType === Node.COMMENT_NODE) {
        if (current.nodeValue !== next.nodeValue) current.nodeValue = next.nodeValue;
        return;
      }
      const currentAttributes = [...current.attributes];
      currentAttributes.forEach(attribute => {
        if (!next.hasAttribute(attribute.name)) current.removeAttribute(attribute.name);
      });
      [...next.attributes].forEach(attribute => {
        if (current.getAttribute(attribute.name) !== attribute.value) current.setAttribute(attribute.name, attribute.value);
      });
      if (current.nodeName === 'STYLE' && current.textContent === next.textContent) return;
      const currentChildren = [...current.childNodes];
      const nextChildren = [...next.childNodes];
      const shared = Math.min(currentChildren.length, nextChildren.length);
      for (let index = 0; index < shared; index += 1) this.patchDomNode(currentChildren[index], nextChildren[index]);
      for (let index = currentChildren.length - 1; index >= nextChildren.length; index -= 1) currentChildren[index].remove();
      for (let index = shared; index < nextChildren.length; index += 1) current.appendChild(nextChildren[index].cloneNode(true));
    }
    patchMarkup(markup) {
      const template = document.createElement('template');
      template.innerHTML = markup;
      const currentNodes = [...this.shadowRoot.childNodes];
      const nextNodes = [...template.content.childNodes];
      const shared = Math.min(currentNodes.length, nextNodes.length);
      for (let index = 0; index < shared; index += 1) this.patchDomNode(currentNodes[index], nextNodes[index]);
      for (let index = currentNodes.length - 1; index >= nextNodes.length; index -= 1) currentNodes[index].remove();
      for (let index = shared; index < nextNodes.length; index += 1) this.shadowRoot.appendChild(nextNodes[index].cloneNode(true));
    }
    render() {
      if (!this._hass) return;
      const preserveViewport = this._preserveViewportOnRender === true && this._renderedView === this.view;
      const viewport = preserveViewport ? { x: window.scrollX || 0, y: window.scrollY || 0 } : null;
      this._preserveViewportOnRender = false;
      const signature = this.runtimeSignature();
      if (!this._forceRender && signature === this._lastRuntimeSignature) return;
      this._lastRuntimeSignature = signature;
      this._forceRender = false;
      const previousPlanningWrap = this.shadowRoot?.querySelector('.planningTableWrap');
      if (previousPlanningWrap) {
        this.planningScrollLeft = previousPlanningWrap.scrollLeft;
        this.planningScrollTop = previousPlanningWrap.scrollTop;
      }
      if (this.editSession) { this.pendingRuntimeRender = true; return; }
      const rt = this.runtime();
      const footer = rt.footerModel();
      let content = '';
      try {
        content = this.viewContent(rt);
      } catch (error) {
        console.error(`[HomeBrain Energy ${UX_VERSION}] ${this.view} render failed`, error);
        content = this.renderError(this.view, error);
      }
      const markup = `<style>${this.styles()}${hbEnergyPresentationStyles()}${this.energyHardwareStyles()}${this.flowDependencyStyles()}${this.powerFlowCardStyles()}${typeof rhiUxVisualPickerStyles === 'function' ? rhiUxVisualPickerStyles() : ''}${typeof rhiEnergyVisualPickerStyles === 'function' ? rhiEnergyVisualPickerStyles() : ''}

      /* R3.62.0 canonical component framework and adaptive convergence */
      :host{--hi-space-1:4px;--hi-space-2:8px;--hi-space-3:12px;--hi-space-4:16px;--hi-radius-sm:8px;--hi-radius-md:12px;--hi-break-tablet:980px;--hi-break-phone:700px}











      .scopeSelector{display:flex;align-items:center;gap:6px;min-width:0;flex-wrap:wrap}.scopeSelectorTitle{display:none}.scopeButtons{display:flex;gap:4px;flex-wrap:wrap}.scopeSelector>select{display:none}
      .hiConclusionFooter{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:12px;margin:8px 0 0;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:linear-gradient(135deg,rgba(255,255,255,.98),rgba(247,250,252,.96))}
      .hiConclusionMain{display:grid;grid-template-columns:28px minmax(0,1fr);gap:8px;align-items:start}.hiConclusionIcon{width:28px;height:28px;border-radius:8px;display:grid;place-items:center;background:rgba(3,169,244,.08)}.hiConclusionFooter small{font-size:8.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}.hiConclusionFooter h2{font-size:13px;line-height:1.2;margin:1px 0 2px}.hiConclusionFooter p{font-size:10px;line-height:1.3;margin:0;color:var(--muted)}.hiConclusionFooter details{margin:0;min-width:128px}
      .hiTechnicalFooter{margin:8px 0 0;border-top:1px solid rgba(148,163,184,.24);padding-top:6px;color:#94a3b8;font-size:9px}.hiTechnicalFooter>summary{display:flex;justify-content:space-between;gap:10px;align-items:center;cursor:pointer;list-style:none;padding:4px 2px}.hiTechnicalFooter>summary::-webkit-details-marker{display:none}.hiTechnicalFooter>summary span{font-weight:600}.hiTechnicalFooter>summary b{font-weight:500;color:#94a3b8}.hiTechnicalInterfaceList{display:grid;gap:2px;padding:5px 2px 2px}.hiTechnicalInterfaceRow{display:grid;grid-template-columns:8px minmax(150px,.8fr) minmax(220px,1.2fr) auto;gap:7px;align-items:center;padding:3px 0;border-top:1px solid rgba(148,163,184,.12)}.hiTechnicalInterfaceRow div{display:grid}.hiTechnicalInterfaceRow b{font-size:9px;color:#64748b}.hiTechnicalInterfaceRow small{font-size:8px;color:#94a3b8}.hiTechnicalInterfaceRow code{font-size:8px;color:#94a3b8;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.hiTechnicalInterfaceRow em{font-size:8px;font-style:normal;color:#94a3b8}.hiTechnicalDot{width:5px;height:5px;border-radius:50%;background:#cbd5e1}.hiTechnicalDot.ok{background:#86b99a}.hiTechnicalDot.warn{background:#d6a75c}.hiRuntimeFooter{display:flex;justify-content:center;flex-wrap:wrap;gap:4px 9px;margin:3px 0 0;padding:3px 2px 0;border:0;background:transparent;color:#94a3b8;font-size:8.5px;line-height:1.2;opacity:.82}.hiRuntimeFooter span+span:before{content:"·";margin-right:9px;color:#cbd5e1}.hiRuntimeFooter .hiReleaseIssue{font-weight:650}.hiRuntimeFooter .hiReleaseIssue.warning{color:#b7791f}.hiRuntimeFooter .hiReleaseIssue.error{color:#b42318}
      #hi-body-overview>.summaryRow:first-child,#hi-body-consumers .consumerMixKpis,#hi-body-intelligence>.intelligencePage>.summaryRow:first-child{display:none}
      .r362ValuePage .valueGrid{align-items:start}
      @media(max-width:980px){.hiConclusionFooter{grid-template-columns:1fr}.hiConclusionFooter details{min-width:0}}
      @media(max-width:700px){.scopeSelector{display:contents}.scopeButtons{display:contents}.hiConclusionFooter{padding:9px 10px}.hiConclusionMain{grid-template-columns:24px minmax(0,1fr)}.hiConclusionIcon{width:24px;height:24px}}

      /* R3.45.8: accumulated Solar interaction and full-width details fixes. */
      .solarV3457 .loadEditCommandRow{grid-template-columns:1.25fr 1fr auto;align-items:end}
      .solarV3457 .loadDetailsFull{padding:0 12px 10px;border-top:0}
      .solarV3457 .loadDetailsFull .hiDetails{margin:0;width:100%}
      .solarV3457 .loadDetailsFull .hiDetails summary{width:100%;box-sizing:border-box;text-align:left;background:#fff}
      .solarV3457 .loadDetailsFull .hiDetails[open] .softBox{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:10px}
      .solarV3457 .loadDetailsFull .softBox .kv{background:#fff;border:1px solid #e5ebf3;border-radius:8px;padding:7px 8px;min-height:36px}
      .solarV3457 .loadActions .hiAction{min-width:52px}
      .solarV3457 .loadActions .hiAction.enabled{pointer-events:auto}
      .solarV3457 .sliderField input[type=range]:not(:disabled),.solarV3457 .selectField select:not(:disabled){cursor:pointer;background:#fff;color:#0f172a}
      .solarV3457 .sliderField input[type=range]:disabled,.solarV3457 .selectField select:disabled{opacity:.65;cursor:not-allowed}


      /* R3.46.10 Metering clean period fallback, clustering and sortable rows */
      .meteringPage{max-width:1500px;margin:0 auto;display:grid;gap:var(--hi-gap)}.meteringHeader{display:grid;grid-template-columns:minmax(0,1fr) minmax(360px,.75fr);gap:12px;align-items:start;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}.meteringHeader h2{margin:0 0 4px;font-size:20px}.meteringHeader p{margin:0;color:var(--muted)}.meteringSelectorStack{display:grid;gap:8px}.meteringContractNote{padding:12px 14px;display:block;border-color:#f2d79b;background:#fffdf7}.meteringContractNote b{display:block;font-size:13px}.meteringContractNote span{display:block;color:var(--muted);font-size:12px;margin-top:2px}.meteringGrid{grid-template-columns:repeat(2,minmax(0,1fr));align-items:start}.meteringGrid .meteringQualityCard{grid-column:1/-1}.meteringCleanCard h2,.meteringQualityCard h2{font-size:18px;margin-bottom:4px}.meteringCleanCard p{font-size:12px;margin-bottom:10px}.meteringCleanRows{display:grid;gap:7px}.meteringCleanRow{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:10px;align-items:center;border:1px solid #e5ebf3;background:#fff;border-radius:12px;padding:10px 12px}.meteringCleanRow b{font-size:13px}.meteringCleanRow span{display:block;color:var(--muted);font-size:11px;margin-top:2px}.meteringCleanRow strong{font-size:14px;text-align:right}.meteringCleanRow.raw{background:#f8fafc}.meteringSortSelector .scopeButtons{justify-content:flex-start}.meteringSortSelector select{display:none;width:100%;min-height:40px;border:1px solid var(--line);border-radius:10px;background:#fff;padding:8px 10px;font:inherit}.meteringKpis{margin-bottom:0}
      @media(max-width:1180px){.meteringHeader{grid-template-columns:1fr}.meteringGrid{grid-template-columns:1fr 1fr}.meteringGrid .meteringQualityCard{grid-column:1/-1}}
      @media(max-width:700px){.meteringHeader,.meteringGrid,.meteringKpis{grid-template-columns:1fr}.meteringSortSelector .scopeButtons{display:none}.meteringSortSelector select{display:block}.meteringCleanRow{grid-template-columns:1fr auto}.meteringCleanRow .qs{grid-column:1/-1;justify-self:start}.meteringContractNote{padding:12px}}





      .flowPage>.summaryRow.four:first-child{display:none}
      @media(max-width:900px){}
      @media(max-width:420px){}
      .hiUnderstandingFooter{display:grid;grid-template-columns:minmax(0,1fr) minmax(260px,.75fr) auto;gap:12px;align-items:start;margin:10px 0 4px;padding:14px 16px;background:linear-gradient(180deg,#fff,#f8fafc);border:1px solid var(--line);border-radius:14px}
      .hiUnderstandingFooter small{display:block;font-size:9px;font-weight:750;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-bottom:4px}.hiUnderstandingFooter h2{font-size:16px;margin:0 0 4px}.hiUnderstandingFooter p{font-size:11.5px;line-height:1.4;color:var(--muted);margin:0}.hiUnderstandingConclusion{border-left:1px solid var(--line);padding-left:12px}.hiUnderstandingConclusion b{font-size:11.5px;line-height:1.4;font-weight:600}.hiUnderstandingFooter details{min-width:150px;margin:0}
      [id^="hi-body-"]{scroll-margin-top:12px}
      @media(min-width:1101px){}
      @media(min-width:701px) and (max-width:1100px){.hiUnderstandingFooter{grid-template-columns:1fr 1fr}.hiUnderstandingFooter details{grid-column:1/-1}}
      @media(max-width:700px){.hiUnderstandingFooter{grid-template-columns:1fr;padding:12px;margin-top:8px}.hiUnderstandingConclusion{border-left:0;border-top:1px solid var(--line);padding:10px 0 0}.hiUnderstandingFooter details{min-width:0}}

    
      /* R3.62.0 — actual density, action-fit and duplicate-removal closure */
      :host{--hi-status-desktop-h:48px;--hi-status-phone-h:42px}















      /* Header owns summary/status/actions. Remove old duplicated summary/action surfaces in bodies. */
      #hi-body-overview>.summaryRow,#hi-body-outlook>.summaryRow,#hi-body-flow>.summaryRow,#hi-body-solar .summaryRow:first-child,#hi-body-battery>.summaryRow,#hi-body-consumers .consumerMixKpis,#hi-body-strategies>.summaryRow,#hi-body-metering>.summaryRow,#hi-body-intelligence .summaryRow:first-child,#hi-body-value>.summaryRow{display:none}
      #hi-body-outlook .outlookHeader,#hi-body-metering .meteringHeader{display:none}
      .hiUnderstandingFooter{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(220px,.9fr) auto;align-items:center;gap:14px;margin:10px 0 4px;padding:10px 12px;min-height:66px;border-radius:12px;background:linear-gradient(135deg,#fff 0%,#f7fafc 100%)}
      .hiFooterLead{display:flex;align-items:center;gap:10px;min-width:0}.hiFooterIcon{width:30px;height:30px;border-radius:9px;display:grid;place-items:center;background:#f3efff;color:#6d28d9;font-size:14px;flex:0 0 auto}.hiFooterLead>div{min-width:0}
      .hiUnderstandingFooter small{font-size:8px;letter-spacing:.1em;margin:0 0 2px}.hiUnderstandingFooter h2{font-size:14px;line-height:1.2;margin:0;white-space:normal}.hiFooterAttention{min-width:0;border-left:1px solid var(--line);padding-left:14px}.hiFooterAttention p{font-size:10.5px;line-height:1.3;margin:0;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.hiUnderstandingFooter>details{min-width:92px;margin:0}.hiUnderstandingFooter>details>summary{height:34px;min-height:34px;padding:6px 10px;border-radius:9px;font-size:10px;white-space:nowrap}
      @media(min-width:701px) and (max-width:1100px){.hiUnderstandingFooter{grid-template-columns:minmax(0,1.15fr) minmax(200px,.85fr) auto}}
      @media(max-width:700px){.hiUnderstandingFooter{grid-template-columns:1fr auto;gap:8px;padding:9px 10px;min-height:60px}.hiFooterAttention{grid-column:1/-1;border-left:0;border-top:1px solid var(--line);padding:6px 0 0}.hiFooterIcon{width:26px;height:26px}.hiUnderstandingFooter h2{font-size:12.5px}.hiFooterAttention p{font-size:9.5px;-webkit-line-clamp:1}.hiUnderstandingFooter>details{grid-column:2;grid-row:1}.hiUnderstandingFooter>details[open]{grid-column:1/-1;grid-row:auto}}

      /* R3.64.0 public intent, authoritative readback and mobile draft-save transition */
      [data-property-key].dirty{border-color:#f59e0b;background:#fffdf7}.propertyDraftBar{position:sticky;bottom:max(8px,env(safe-area-inset-bottom));z-index:20;display:flex;align-items:center;justify-content:space-between;gap:16px;margin:12px auto 4px;padding:10px 12px;max-width:720px;border:1px solid #cbd5e1;border-radius:14px;background:rgba(255,255,255,.96);box-shadow:0 12px 34px rgba(15,23,42,.16);backdrop-filter:blur(14px)}.propertyDraftBar>div:first-child{display:grid;gap:2px}.propertyDraftBar b{font-size:12px}.propertyDraftBar span{font-size:10px;color:var(--muted)}.propertyDraftBar>div:last-child{display:flex;gap:8px}.propertyDraftBar button{min-height:38px;border:1px solid var(--line);border-radius:10px;background:#fff;padding:7px 14px;font:inherit;font-size:11px;font-weight:650}.propertyDraftBar button.primary{background:#0f172a;color:#fff;border-color:#0f172a}.writeState.pending,.writeState.verifying{color:#b45309}.writeState.accepted{color:#15803d}.writeState.rejected,.writeState.timed_out{color:#b91c1c}@media(max-width:700px){.propertyDraftBar{position:fixed;left:10px;right:10px;bottom:max(10px,env(safe-area-inset-bottom));margin:0;max-width:none;padding:9px 10px}.propertyDraftBar span{display:none}.propertyDraftBar button{min-width:84px;min-height:44px}.energy{padding-bottom:92px}}

      /* R3.63.2 explicit persistence, correct requirement count and stable pricing facts */
      main.editing{scroll-behavior:auto}.pricingSettingsList{display:grid;border:1px solid var(--line);border-radius:14px;overflow:hidden}.pricingSettingRow{display:grid;grid-template-columns:minmax(220px,.8fr) minmax(280px,1.2fr);gap:16px;align-items:center;padding:10px 12px;background:#fff;border-bottom:1px solid var(--line)}.pricingSettingRow:last-child{border-bottom:0}.pricingSettingIdentity{display:flex;align-items:center;gap:10px;min-width:0}.pricingSettingIdentity>div{display:grid;gap:2px}.pricingSettingIdentity small{color:var(--muted);font-size:11px}.pricingSettingEditor{min-width:0}.pricingSettingEditor>.editField{margin:0}.pricingSettingEditor>span{display:block;text-align:right;color:var(--muted);font-size:11px}.pricingSettingsHeader{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.pricingSettingsHeader>b{border-radius:999px;padding:6px 10px;background:#fff7ed;color:#9a3412;font-size:11px;white-space:nowrap}.flexPricingList{display:grid;gap:7px}.flexPricingRow{display:flex;align-items:center;justify-content:space-between;gap:14px;border:1px solid var(--line);border-radius:11px;padding:10px 12px;background:#fff}.flexPricingRow>div{min-width:0}.flexPricingRow b,.flexPricingRow span{display:block}.flexPricingRow span{font-size:11px;color:var(--muted);margin-top:2px}.flexPricingRow strong{font-size:12px;text-align:right}.editing input,.editing select,.editing textarea{user-select:text;-webkit-user-select:text}.editing [data-property-key]:focus{outline:2px solid rgba(37,99,235,.35);outline-offset:2px}@media(max-width:700px){.pricingSettingRow{grid-template-columns:1fr;gap:8px}.pricingSettingEditor>span{text-align:left}.pricingSettingsHeader{display:grid}.flexPricingRow{align-items:flex-start}.flexPricingRow strong{max-width:45%}}
      .valueTariffList{display:grid;gap:10px;margin-top:14px}.valueTariffRow{border:1px solid var(--line,#e3e7ec);border-radius:14px;padding:12px;display:grid;gap:10px}.valueTariffEvidence{display:flex;align-items:center;gap:10px}.valueTariffEvidence>div{display:grid;gap:2px}.valueTariffEvidence span{font-size:12px;color:var(--muted,#697386)}.valueTariffMark{font-size:18px;font-weight:800;color:var(--green,#21875b)}.valueTariffRow.missing .valueTariffMark{color:var(--orange,#a86300)}.valueTariffRow .editField{margin:0}.valueConfigurationState{display:grid;gap:14px}.valueStateHeadline{display:grid;gap:5px;padding:16px;border-radius:16px;background:var(--soft,#f4f6f8)}.valueStateHeadline b{font-size:24px}.valueStateHeadline span{color:var(--muted,#697386)}.valueConfigurationChecklist{display:grid;gap:8px}.valueConfigurationChecklist>div{display:grid;grid-template-columns:24px 1fr auto;align-items:center;gap:8px;padding:10px 0;border-bottom:1px solid var(--line,#e3e7ec)}.valueConfigurationChecklist em{font-style:normal;color:var(--muted,#697386);font-size:12px}@media(max-width:700px){.valueConfigurationChecklist>div{grid-template-columns:24px 1fr}.valueConfigurationChecklist em{grid-column:2}.valueTariffRow{padding:10px}}

      /* R3.68.0 Solar mobile-first responsive redesign */
      .solarOperationalExecutionPanel{display:grid;gap:12px}.solarExecutionSummary{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}.solarExecutionSummary span{border:1px solid var(--line);background:#f8fafc;border-radius:999px;padding:4px 8px;font-size:9.5px;color:#475569}.solarExecutionList{display:grid;gap:7px}.solarExecutionRow{display:grid;grid-template-columns:1.2fr .9fr .82fr .72fr .9fr 1.35fr;gap:10px;align-items:center;border:1px solid #e3eaf2;border-radius:12px;padding:10px 12px;background:#fff}.solarExecutionConsumer{display:grid;grid-template-columns:34px minmax(0,1fr);gap:9px;align-items:center;min-width:0}.solarExecutionIcon{display:grid;place-items:center;width:34px;height:34px;border-radius:50%;background:#eef6ff}.solarExecutionConsumer b,.solarExecutionCell b,.solarExecutionWhy b{display:block;font-size:11px;line-height:1.25}.solarExecutionConsumer small,.solarExecutionCell small,.solarExecutionWhy small{display:block;font-size:8.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:3px}.solarExecutionConsumer small{margin:2px 0 0;text-transform:none;letter-spacing:0}.solarExecutionCell span{display:block;font-size:9.5px;color:var(--muted);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.solarExecutionWhy{min-width:0}.solarExecutionWhy b{font-weight:620;color:#334155}.solarExecutionState{display:inline-flex;width:max-content;border-radius:999px;padding:3px 7px;background:#f1f5f9;color:#475569}.solarExecutionState.active{background:#dcfce7;color:#15803d}.solarExecutionState.waiting{background:#fff7ed;color:#c2410c}.solarExecutionState.blocked{background:#fee2e2;color:#b91c1c}
      @media(max-width:1100px){.solarExecutionRow{grid-template-columns:1.25fr 1fr 1fr}.solarExecutionWhy{grid-column:1/-1;padding-top:7px;border-top:1px solid #edf2f7}}
      @media(max-width:700px){.solarOperationalExecutionPanel .energySectionHead{display:grid;gap:8px}.solarExecutionSummary{justify-content:flex-start}.solarExecutionRow{grid-template-columns:1fr 1fr;padding:9px}.solarExecutionConsumer,.solarExecutionWhy{grid-column:1/-1}.solarExecutionWhy{padding-top:7px}.solarExecutionCell span{white-space:normal}.solarExecutionCell b{font-size:10.5px}}
      .solarOperationalCompact{display:grid;gap:8px;padding:10px 12px}.solarOperationalCompactHead{display:flex;align-items:center;justify-content:space-between;gap:12px}.solarOperationalCompactHead h2{margin:0;font-size:15px;line-height:1.2}.solarOperationalCompactHead p{margin:2px 0 0;font-size:9.5px;color:var(--muted)}.solarOperationalCounts{display:flex;gap:5px;flex-wrap:wrap;justify-content:flex-end}.solarOperationalCounts span{padding:3px 7px;border:1px solid var(--line);border-radius:999px;background:#f8fafc;font-size:9px;font-weight:650;color:#475569}.solarCompactConsumerList{display:grid;gap:6px}.solarCompactConsumer{display:grid;grid-template-columns:minmax(150px,.95fr) minmax(100px,.55fr) minmax(0,3.2fr);align-items:center;gap:10px;border:1px solid #e3eaf2;border-radius:10px;background:#fff;padding:8px 10px}.solarCompactIdentity{display:grid;grid-template-columns:30px minmax(0,1fr);align-items:center;gap:8px;min-width:0}.solarCompactIcon{display:grid;place-items:center;width:30px;height:30px;border-radius:50%;background:#eef6ff}.solarCompactIdentity b{display:block;font-size:11.5px;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.solarCompactIdentity small{display:block;margin-top:2px;font-size:9px;color:var(--muted)}.solarCompactPlan{display:grid;gap:3px;align-content:center}.solarCompactPlan>span:last-child{font-size:9px;color:var(--muted)}.solarCompactFacts{display:grid;grid-template-columns:.72fr .72fr .82fr .82fr 1.15fr minmax(150px,1.55fr);align-items:center;min-width:0}.solarCompactItem{min-width:0;padding:0 9px;border-left:1px solid #edf1f5}.solarCompactItem:first-child{border-left:0}.solarCompactItem small{display:block;margin-bottom:2px;font-size:7.8px;font-weight:700;letter-spacing:.055em;text-transform:uppercase;color:#64748b}.solarCompactItem b{display:block;font-size:10.5px;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.solarCompactItem span:not(.solarCompactStatus){display:block;margin-top:2px;font-size:8.5px;line-height:1.2;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.solarCompactItem.wide b{white-space:normal;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}.solarCompactStatus{display:inline-flex;align-items:center;width:max-content;max-width:100%;padding:3px 6px;border:1px solid;border-radius:999px;font-size:8.8px;font-weight:700;line-height:1.05;white-space:nowrap}.solarCompactStatus.active{background:#dcfce7;color:#166534;border-color:#bbf7d0}.solarCompactStatus.waiting{background:#fff7ed;color:#9a3412;border-color:#fed7aa}.solarCompactStatus.blocked{background:#fef2f2;color:#b91c1c;border-color:#fecaca}.solarCompactStatus.planned{background:#eef2ff;color:#4338ca;border-color:#c7d2fe}.solarCompactStatus.neutral{background:#f8fafc;color:#475569;border-color:#e2e8f0}
      @media(max-width:1050px){.solarCompactConsumer{grid-template-columns:minmax(150px,.8fr) minmax(100px,.5fr) minmax(0,2.7fr)}.solarCompactFacts{grid-template-columns:repeat(5,minmax(70px,1fr))}.solarCompactItem.wide{grid-column:1/-1;border-left:0;border-top:1px solid #edf1f5;padding-top:5px;margin-top:4px}.solarCompactItem.wide b{-webkit-line-clamp:1}}
      @media(max-width:700px){.solarOperationalCompactHead{align-items:flex-start}.solarOperationalCounts{justify-content:flex-start}.solarCompactConsumer{grid-template-columns:minmax(0,1fr) auto;gap:7px;padding:8px}.solarCompactFacts{grid-column:1/-1;grid-template-columns:repeat(3,minmax(0,1fr));border-top:1px solid #edf1f5;padding-top:7px}.solarCompactItem{padding:0 6px}.solarCompactItem:nth-child(4){border-left:0}.solarCompactItem.wide{grid-column:1/-1}.solarCompactPlan{justify-items:end}}
      .solarPlanResponsive{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(330px,.85fr);gap:14px;align-items:stretch}.solarPlanStatus,.solarPlanAutomation{min-width:0;display:grid;align-content:start;gap:10px}.solarPlanAutomation{border-left:1px solid var(--line);padding-left:14px}.solarPlanHeading{display:flex;align-items:center;justify-content:space-between;gap:10px}.solarPlanHeading h2{margin:0;font-size:18px}.solarPlanHeading>span{font-size:10.5px;color:var(--muted)}.solarPlanState{display:inline-flex;align-items:center;gap:6px}.solarPlanMessage{border:1px solid #e3ecf5;background:#f8fbfe;border-radius:12px;padding:12px}.solarPlanMessage small{display:block;text-transform:uppercase;letter-spacing:.08em;font-size:9px;color:var(--muted);font-weight:700}.solarPlanMessage h3{font-size:15px;line-height:1.3;margin:5px 0 3px}.solarPlanMessage p{margin:0;font-size:11px;color:var(--muted);line-height:1.35}.solarPlanStats{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}.solarPlanStats span{border:1px solid var(--line);background:#fff;border-radius:999px;padding:4px 8px;font-size:9.5px;color:#475569}.solarPlanAutomation .modeControl,.solarPlanAutomation .segmented{width:100%;max-width:none}.automationCompactInfo{display:grid;grid-template-columns:1fr;gap:2px;padding:8px 10px;border:1px solid var(--line);border-radius:10px;background:#fafbfd}.automationCompactInfo b{font-size:11px}.automationCompactInfo span{font-size:10px;color:var(--muted)}.compactFlexibleLoads{width:100%}.compactFlexibleLoads .flexLoadList{display:grid;grid-template-columns:1fr;gap:7px}.compactFlexibleLoads .decisionLoadCard{margin:0}.compactFlexibleLoads .decisionMainRow{min-height:0;padding:9px 11px;gap:8px}.compactFlexibleLoads .r164GoalContext{padding:0 11px 6px}.compactFlexibleLoads .decisionControlRow{padding:8px 11px;gap:8px}.compactFlexibleLoads .loadDetailsFull{padding:0 11px 8px}.solarCompactSummaryRow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.solarCompactFact{display:flex;align-items:center;justify-content:space-between;gap:8px;background:#fff;border:1px solid var(--line);border-radius:11px;padding:9px 11px}.solarCompactFact span{font-size:10px;color:var(--muted)}.solarCompactFact b{font-size:12px;white-space:nowrap}
      @media(max-width:900px){.solarPlanResponsive{grid-template-columns:1fr 1fr}.solarPlanAutomation{padding-left:12px}.solarCompactSummaryRow{grid-template-columns:1fr 1fr}}
      @media(max-width:700px){.solarPlanResponsive{grid-template-columns:1fr 1fr;gap:8px;padding:10px}.solarPlanStatus,.solarPlanAutomation{gap:7px}.solarPlanAutomation{padding-left:8px}.solarPlanHeading{display:grid;gap:2px}.solarPlanHeading h2{font-size:14px}.solarPlanHeading>span{font-size:9px}.solarPlanMessage{padding:8px;border-radius:9px}.solarPlanMessage h3{font-size:12px;line-height:1.25;margin:3px 0}.solarPlanMessage p{font-size:9.5px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.solarPlanStats{gap:4px;margin-top:6px}.solarPlanStats span{font-size:8.5px;padding:3px 6px}.solarPlanAutomation .segmented button{min-width:0;padding:8px 5px;font-size:9px}.automationCompactInfo{padding:6px 7px}.automationCompactInfo b{font-size:9.5px}.automationCompactInfo span{font-size:9px}.solarPlanAutomation .hiDetails summary{padding:6px 0;font-size:9px}.compactFlexibleLoads{padding:10px}.compactFlexibleLoads .energySectionHead{display:grid;grid-template-columns:1fr;gap:7px}.compactFlexibleLoads .energySectionHead h2{font-size:16px}.compactFlexibleLoads .energySectionHead p{font-size:10px;margin:2px 0 0}.compactFlexibleLoads .sortControl{display:grid;grid-template-columns:auto 1fr;gap:6px}.compactFlexibleLoads .sortControl .segmented{overflow-x:auto}.compactFlexibleLoads .sortControl button{padding:6px 8px;font-size:9px}.compactFlexibleLoads .decisionMainRow{grid-template-columns:minmax(0,1.4fr) minmax(80px,.6fr);padding:8px;gap:6px}.compactFlexibleLoads .decisionIdentity{grid-column:1}.compactFlexibleLoads .decisionPlan{grid-column:2}.compactFlexibleLoads .decisionMetric,.compactFlexibleLoads .decisionExpected,.compactFlexibleLoads .r164GoalContext{display:none}.compactFlexibleLoads .decisionControlRow{grid-template-columns:1fr;padding:7px 8px}.compactFlexibleLoads .decisionActions{grid-template-columns:repeat(3,1fr)}.compactFlexibleLoads .decisionActions .hiAction{min-height:34px;font-size:10px;padding:5px}.compactFlexibleLoads .automationMini{display:none}.solarCompactSummaryRow{grid-template-columns:1fr 1fr;gap:6px}.solarCompactFact{padding:7px 8px}.solarCompactFact span{font-size:9px}.solarCompactFact b{font-size:10.5px}}

      /* R3.67.0 product cleanup and central tab diagnostics */
      
      .hiConclusionFooter>details{display:none}
      .hiTabDiagnostics{margin:8px 0 16px;border:1px solid var(--line);border-radius:14px;background:#fff;overflow:hidden}
      .hiTabDiagnostics>summary{list-style:none;cursor:pointer;display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 14px;min-height:48px;background:#f8fafc}
      .hiTabDiagnostics>summary::-webkit-details-marker{display:none}.hiTabDiagnostics>summary span{display:grid;gap:2px}.hiTabDiagnostics>summary b{font-size:12px}.hiTabDiagnostics>summary small{font-size:10px;color:var(--muted)}.hiTabDiagnostics>summary>strong{font-size:10px;border-radius:999px;padding:5px 9px;background:#e8f5ec;color:#166534}.hiTabDiagnostics[open]>summary>strong{background:#eef2ff;color:#3730a3}
      .hiDiagnosticsBody{display:grid;gap:12px;padding:12px 14px 14px}.hiDiagnosticImpact,.hiDiagnosticSection{border:1px solid var(--line);border-radius:12px;padding:12px;background:#fff}.hiDiagnosticImpact{background:#f8fafc}.hiDiagnosticImpact h3,.hiDiagnosticSection h4{margin:0 0 7px;font-size:12px}.hiDiagnosticImpact p,.hiDiagnosticSection>p{margin:0;color:var(--muted);font-size:11px;line-height:1.45}
      .hiDiagnosticRow{display:grid;grid-template-columns:22px minmax(0,1fr) auto;gap:8px;align-items:start;padding:9px 0;border-top:1px solid var(--line)}.hiDiagnosticRow:first-of-type{border-top:0}.hiDiagnosticState{width:20px;height:20px;border-radius:999px;display:grid;place-items:center;background:#e8f5ec;color:#166534;font-weight:800}.hiDiagnosticRow.issue .hiDiagnosticState{background:#fff1df;color:#9a3412}.hiDiagnosticRow>div{display:grid;gap:2px;min-width:0}.hiDiagnosticRow b{font-size:11px}.hiDiagnosticRow small{font-size:10px;color:var(--muted)}.hiDiagnosticRow code,.hiDiagnosticIssue code,.hiEngineeringRow code{font-size:9px;overflow-wrap:anywhere;color:#475569}.hiDiagnosticRow>strong{font-size:10px}.hiDiagnosticRow>p{grid-column:2/-1;margin:2px 0 0;font-size:10px;color:#9a3412}
      .hiDiagnosticIssue{display:grid;gap:4px;padding:9px 0;border-top:1px solid var(--line)}.hiDiagnosticIssue:first-of-type{border-top:0}.hiDiagnosticIssue b{font-size:11px}.hiDiagnosticIssue span{font-size:10px;color:var(--muted)}.hiDiagnosticEmpty{font-size:10px;color:var(--muted);padding:6px 0}.hiEngineeringRow{display:flex;justify-content:space-between;gap:12px;padding:6px 0;border-top:1px solid var(--line)}.hiEngineeringRow:first-of-type{border-top:0}.hiEngineeringRow b{font-size:10px}.hiDiagnosticMeta{font-size:9px;color:var(--muted);text-align:right}
      @media(max-width:700px){.hiTabDiagnostics>summary{padding:11px 12px}.hiDiagnosticsBody{padding:10px}.hiDiagnosticRow{grid-template-columns:22px minmax(0,1fr)}.hiDiagnosticRow>strong{grid-column:2}.hiDiagnosticRow>p{grid-column:2}.hiDiagnosticMeta{text-align:left}}


      /* R3.71.0 Solar phone convergence and user-controlled tab navigation */
      @media(max-width:700px){
        /* The user owns horizontal navigation position. No grid conversion, snapping or automatic centering. */
        .tabs{display:flex;grid-template-columns:none;flex-wrap:nowrap;overflow-x:auto;overflow-y:hidden;white-space:nowrap;gap:4px;padding:4px;scroll-snap-type:none;-webkit-overflow-scrolling:touch;overscroll-behavior-inline:contain;touch-action:pan-x}
        .tab{flex:0 0 auto;width:auto;min-width:104px;min-height:44px;padding:8px 14px;font-size:12px;line-height:1.1;white-space:nowrap;text-align:center;scroll-snap-align:none}

        /* Solar is genuinely phone-first: status first, automation second, never squeezed side by side. */
        .solarPlanResponsive{grid-template-columns:1fr;gap:10px;padding:11px}
        .solarPlanStatus,.solarPlanAutomation{width:100%;min-width:0;gap:7px}
        .solarPlanAutomation{border-left:0;border-top:1px solid var(--line);padding:10px 0 0}
        .solarPlanHeading{display:flex;align-items:center;justify-content:space-between;gap:8px}
        .solarPlanHeading h2{font-size:16px}
        .solarPlanHeading>span{font-size:10px;text-align:right}
        .solarPlanMessage{padding:9px 10px}
        .solarPlanMessage small{font-size:8.5px}
        .solarPlanMessage h3{font-size:13px;line-height:1.28;margin:4px 0 2px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
        .solarPlanMessage p{font-size:10px;line-height:1.3;-webkit-line-clamp:1}
        .solarPlanStats{display:none}
        .solarPlanAutomation .modeControl,.solarPlanAutomation .segmented{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));width:100%;overflow:hidden}
        .solarPlanAutomation .segmented button{width:100%;min-width:0;padding:9px 4px;font-size:10px;white-space:nowrap}
        .automationCompactInfo{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:7px 9px}
        .automationCompactInfo b{font-size:10.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
        .automationCompactInfo span{font-size:9.5px;white-space:nowrap}
        .solarPlanAutomation .hiDetails summary{min-height:38px;padding:7px 8px;font-size:10px}

        /* Flexible loads remain the primary full-width content and are compact rather than paired with duplicated solar facts. */
        .compactFlexibleLoads{width:100%;padding:10px}
        .compactFlexibleLoads .flexLoadList{grid-template-columns:1fr;gap:7px}
        .compactFlexibleLoads .decisionLoadCard{width:100%;overflow:hidden}
        .compactFlexibleLoads .decisionMainRow{grid-template-columns:minmax(0,1fr) auto;padding:8px 9px}
        .compactFlexibleLoads .decisionControlRow{padding:7px 9px;gap:7px}
        .compactFlexibleLoads .decisionActions{grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}
        .compactFlexibleLoads .decisionActions .hiAction{min-width:0;min-height:38px;padding:6px 4px;font-size:10px}
        .compactFlexibleLoads .sortControl .segmented{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));overflow:hidden;width:100%}
        .compactFlexibleLoads .sortControl button{min-width:0;width:100%;padding:7px 4px;font-size:9.5px}
      }

      /* R3.73.0 lean strategy set editing */
      .strategyTablePanel{padding:14px}.strategyTableHead{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:7px}.strategyTableHead h2{margin:0;font-size:16px;font-weight:600}.strategyTableHead p{margin:2px 0 0;font-size:10.5px;line-height:1.25}.strategySetActions{display:flex;align-items:center;gap:7px;flex:0 0 auto}.strategyTextAction,.strategySaveAction{min-height:30px;padding:5px 9px;border-radius:8px;font-size:11px;font-weight:600;cursor:pointer}.strategyTextAction{border:0;background:transparent;color:#526178}.strategySaveAction{border:1px solid #d7e5fb;background:#eef5ff;color:#1d4ed8}.strategyTextAction:disabled,.strategySaveAction:disabled{opacity:.4;cursor:default}.strategyChangeCount{font-size:9.5px;color:var(--muted)}.strategyTable{border-top:1px solid #edf1f6}.strategyColumnHead,.strategyPrimaryRow{display:grid;grid-template-columns:minmax(0,1fr) minmax(120px,42%);gap:12px;align-items:center}.strategyColumnHead{padding:5px 2px 4px;color:#8a96a8;font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:.08em}.strategyColumnHead span:last-child{text-align:right}.strategyTableRow{border-top:1px solid #f0f3f7;padding:7px 2px 6px;transition:background .15s ease,border-color .15s ease}.strategyTableRow.changed{background:rgba(37,99,235,.035);border-left:2px solid rgba(37,99,235,.35);padding-left:7px}.strategySetting{font-size:11.5px;color:#526178}.strategyValue{text-align:right;min-width:0}.strategyReadValue{font-size:11.5px;font-weight:560;color:#172033}.strategyGuidance{grid-column:1/-1;margin-top:2px;padding-right:2px;color:#8a96a8;font-size:9.5px;line-height:1.2}.strategyGuidance i{font-style:italic}.strategyValue .editField,.strategyValue .selectField,.strategyValue .sliderField,.strategyValue .toggleField{margin:0;padding:0;background:transparent;border:0;display:block}.strategyValue .editField>span,.strategyValue .selectField>span,.strategyValue .sliderField>div>span,.strategyValue .toggleField>span{display:none}.strategyValue input,.strategyValue select{width:min(220px,100%);min-height:34px;padding:5px 7px;font-size:11px;margin-left:auto}.strategyValue .sliderField input[type=range]{width:100%}.strategyValue .toggleField{justify-content:flex-end}.strategiesPage .strategyProfilePicker{margin-bottom:10px}.strategiesPage .effectivePolicyPreview{margin-top:10px}.batteryGrid .strategyTablePanel{grid-column:1/-1}.compactFlexibleLoads>.strategyTablePanel{margin-top:10px}
      @media(max-width:700px){.strategyTablePanel{padding:11px}.strategyTableHead{align-items:center}.strategyTableHead p{display:none}.strategyColumnHead,.strategyPrimaryRow{grid-template-columns:minmax(0,1fr) minmax(112px,44%);gap:8px}.strategyColumnHead{font-size:8.5px}.strategySetting,.strategyReadValue{font-size:11px}.strategyGuidance{font-size:9px;white-space:normal}.strategySetActions{gap:4px}.strategyTextAction,.strategySaveAction{padding:5px 7px}.strategyChangeCount{display:none}.strategyValue input,.strategyValue select{min-height:36px}}

      /* R3.74.0 product clarity and mobile compaction */
      .r3280OutlookSummary{display:none}
      .outlookHeroFacts small{display:block;margin-top:2px;color:var(--muted);font-size:10px;font-weight:500}
      .consumerExplorerCard.compact{padding:9px 11px}.consumerExplorerCard.compact .consumerExplorerHead{align-items:center}.consumerExplorerCard.compact .consumerExplorerPrimary span{font-size:10px}.consumerExplorerCard.compact .consumerReason{display:block;margin-top:3px;color:var(--muted);font-size:9.5px;font-style:italic}.consumerExplorerCard.compact>.hiDetails{margin-top:6px}.consumerExplorerCard.compact>.hiDetails summary{min-height:30px;padding:5px 7px}
      .consumerQuickFilters{display:none}.consumerToolbar{grid-template-columns:1fr 1fr}.consumerExplorerHeader{grid-template-columns:minmax(0,1fr) minmax(260px,.55fr)}
      .effectivePolicyList{display:grid;border-top:1px solid #edf1f6}.effectivePolicyRow.compact{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(0,1fr) auto;gap:8px;align-items:center;padding:8px 2px;border:0;border-bottom:1px solid #f0f3f7;border-radius:0;background:transparent}.effectivePolicyRow.compact b,.effectivePolicyRow.compact span,.effectivePolicyRow.compact strong{font-size:11px}.effectivePolicyRow.compact span{color:var(--muted)}.effectivePolicyRow.compact strong{text-align:right}.effectivePolicyRow.compact small{grid-column:1/-1;color:var(--muted);font-size:9px;font-style:italic}
      .pricingStrategyPanel .strategyGuidance{padding-top:1px}.pricingStrategyPanel .editField{margin:0}.pricingStrategyPanel input{min-height:34px}
      .meteringRemediationPanel{padding:11px}.meteringRemediationItem{grid-template-columns:minmax(0,1fr) auto;padding:9px;margin-top:7px}.remediationImpact{display:none}
      .hiTabDiagnostics{margin-top:10px;margin-bottom:5px}.hiRuntimeFooter{font-size:9px;color:#8a96a8;padding:3px 2px;margin:0;display:block;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      @media(max-width:700px){.consumerExplorerHeader{grid-template-columns:1fr}.consumerToolbar{grid-template-columns:1fr 1fr}.effectivePolicyRow.compact{grid-template-columns:minmax(0,1fr) minmax(0,.9fr) auto}.outlookGrid{gap:8px}.meteringRemediationItem{grid-template-columns:1fr}.meteringRemediationAction{align-items:flex-start}.pricingStrategyPanel{padding:11px}.hiRuntimeFooter{font-size:8.5px}}

      .periodUnavailableCard{max-width:760px;margin:0 auto;text-align:left}.periodAvailabilityHint{display:flex;justify-content:space-between;gap:12px;padding:10px 12px;border-radius:10px;background:#f7f9fc;border:1px solid var(--line)}.periodAvailabilityHint span{color:var(--muted)}.productNotice{display:flex;align-items:center;gap:10px;padding:10px 12px}.productNotice b{white-space:nowrap}.productNotice span{color:var(--muted)}.disabledAssetsSection .consumerExplorerCard{min-height:0}.disabledAssetsSection .consumerExplorerHead{min-height:38px}.disabledAssetsSection .consumerExplorerCard>.hiDetails{display:none}

      /* R3.82.3 end-user portal communication standard */
      .productPortalPage{display:grid;gap:12px}
      .productStory{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:16px;align-items:center;padding:18px;border-left:4px solid #3b82f6}
      .productStory.orange{border-left-color:#f59e0b}.productStory.green{border-left-color:#22c55e}.productStory.purple{border-left-color:#8b5cf6}
      .productStoryCopy small{display:block;text-transform:uppercase;letter-spacing:.12em;font-size:9px;color:var(--muted);margin-bottom:6px}
      .productStoryCopy h2{font-size:20px;line-height:1.2;margin:0 0 6px;letter-spacing:-.02em}
      .productStoryCopy>p{font-size:12px;line-height:1.45;margin:0;max-width:760px}
      .productStoryRecommendation{margin-top:12px;padding:10px 12px;border-radius:10px;background:#f8fafc;display:grid;gap:3px}
      .productStoryRecommendation span{font-size:9px;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}.productStoryRecommendation b{font-size:12px;line-height:1.35}
      .productStoryActions{display:flex;gap:8px;align-items:center;justify-content:flex-end;flex-wrap:wrap}.productStory>.hiDetails{grid-column:1/-1}
      .managedAssetCard{border:1px solid var(--line);border-radius:12px;padding:14px;background:#fff;display:grid;gap:10px}
      .managedAssetHeader{display:flex;justify-content:space-between;gap:12px;align-items:start}.managedAssetHeader h3{margin:0 0 3px;font-size:14px}.managedAssetHeader span{font-size:11px;color:var(--muted)}.managedAssetHeader>b{font-size:14px}
      .managedAssetStory{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:10px}.managedAssetStory>p,.managedAssetStory>div{margin:0;padding:10px 12px;background:#f8fafc;border-radius:9px;font-size:11px;line-height:1.4}.managedAssetStory small{display:block;text-transform:uppercase;letter-spacing:.08em;font-size:8.5px;color:var(--muted);margin-bottom:3px}.managedAssetStory b{font-size:11px}
      .managedAssetFacts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.managedAssetFacts span{min-width:0;padding:7px 8px;border-radius:8px;background:#f8fafc}.managedAssetFacts small,.managedAssetFacts b{display:block}.managedAssetFacts small{font-size:8px;color:var(--muted)}.managedAssetFacts b{font-size:10.5px;line-height:1.3;overflow-wrap:anywhere}.managedAssetActions{display:flex;gap:8px;flex-wrap:wrap}.managedAssetCard>.hiDetails{margin:0}
      .compactDisclosure{padding:0;overflow:hidden}.compactDisclosure>summary{padding:12px 14px;font-weight:640;cursor:pointer}.compactDisclosure>p{padding:0 14px}.disabledAssetList{display:grid;gap:4px;padding:8px 12px 12px}.disabledAssetCompact{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:8px 10px;border:1px solid var(--line);border-radius:9px;background:#fbfcfd}.disabledAssetCompact b{display:block;font-size:11px}.disabledAssetCompact span{font-size:9.5px;color:var(--muted)}.disabledAssetCompact>.hiDetails{margin:0}.disabledAssetCompact>.hiDetails summary{padding:6px 8px}
      .portalStatusList{display:grid;gap:5px;margin-top:8px}.portalStatusRow{display:flex;justify-content:space-between;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)}.portalStatusRow:last-child{border-bottom:0}.portalStatusRow b{display:block;font-size:12px}.portalStatusRow span{font-size:10px;color:var(--muted)}.portalStatusRow strong{font-size:11px;white-space:nowrap}
      .productMeteringGrid{grid-template-columns:repeat(2,minmax(0,1fr))}
      @media(max-width:700px){.productStory{grid-template-columns:1fr;padding:13px}.productStoryActions{justify-content:flex-start}.managedAssetStory{grid-template-columns:1fr}.managedAssetFacts{grid-template-columns:1fr 1fr}.productMeteringGrid{grid-template-columns:1fr}}


      .sliderField.commandEditable{background:linear-gradient(120deg,#f8fbff,#fff);border:1px solid #dbeafe;border-radius:10px;padding:8px 10px}.sliderField.commandEditable input[type=range]:not(:disabled){cursor:pointer;accent-color:#2563eb}.sliderField.commandEditable .commandReadback{display:block;margin-top:3px;font-size:9px;color:#64748b;font-weight:560}.automationQuickAction .hiSegmented{width:100%}.automationQuickAction .hiSegment{min-height:34px}.solarPlanAutomation .automationQuickAction{width:100%}
      /* R3.85.4 end-user Planning presentation */
      .planningMatrixPanel{padding:16px}.planningMatrixHead{margin-bottom:12px}.planningMatrixHead h2{font-size:19px}.planningMatrixHead p,.planningMatrixHead>span{display:none}.planningTable{table-layout:fixed;min-width:900px}.planningTable th,.planningTable td{width:auto;min-width:0;height:48px;padding:10px 8px;font-size:12px}.planningTable th:first-child,.planningTable td:first-child{width:92px;min-width:92px}.planningTable thead th{height:66px}.planningTable .planningLaneGroups th{height:38px;font-size:11px;color:#64748b}.planningTable td{font-weight:400}.planningTable td b{font-size:13px}.planningTable td small{display:none}.planningHeaderNeed{display:block;color:#6d28d9;font-size:10px;font-weight:600;margin-top:4px}.planningPowerValue{font-size:13px;font-weight:450}.planningIdle{font-size:15px;font-weight:400;color:#cbd5e1}.planningTotalRow th,.planningTotalRow td{height:58px;font-weight:650}.planningTotalRow small{display:none}.planningFooter{grid-template-columns:1fr;margin-top:12px}.planningFooter>div{border:0}.planningFooter>div:nth-child(2),.planningFooter>div:nth-child(3){display:none}.planningFooter>div:first-child>small{font-size:11px}.planningFooterAsset{font-size:12px}.planningAggregateTotals b{font-size:14px}.planningAggregateTotals small{display:block;font-size:10px}
      /* Planning visual language convergence */
      .planningHero{position:relative;min-height:150px;border:1px solid var(--line);border-radius:15px;padding:20px 26px;margin-bottom:8px;overflow:hidden;background:linear-gradient(90deg,rgba(255,255,255,.98),rgba(255,255,255,.78)),url('/rhi_energy/frontend/assets/heroes/solar-hero.webp') center/cover;display:flex;justify-content:space-between;gap:20px}.planningHero small{font-size:9px;letter-spacing:.14em;color:#526178;font-weight:700}.planningHero h2{font-size:24px;margin:5px 0 2px}.planningHeroValue{font-size:38px;font-weight:650;letter-spacing:-.03em}.planningHeroValue span{font-size:11px;font-weight:500;color:var(--muted);margin-left:8px}.planningHero p{font-size:11px;color:var(--muted);margin:5px 0 0}.planningStatus{align-self:flex-start;padding:6px 10px;border-radius:999px;font-size:10px;font-weight:650;background:#f4f6f8}.planningStatus.ok{background:#eef8f2;color:#2f6d4b}.planningStatus.warn{background:#fff7e6;color:#946200}.planningPage{max-width:1500px;margin:0 auto}.planningMatrixPanel{padding:10px}.planningMatrixHead{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:7px}.planningMatrixHead h2{margin:0;font-size:16px}.planningMatrixHead p,.planningMatrixHead>span{font-size:9.5px;color:var(--muted);margin:2px 0 0}.planningTableWrap{max-height:430px;overflow:auto;border:1px solid var(--line);border-radius:11px;scroll-padding-top:76px;scroll-padding-bottom:52px;isolation:isolate}.planningTable{border-collapse:separate;border-spacing:0;width:100%;min-width:980px;background:#fff}.planningTable th,.planningTable td{border-right:1px solid #edf1f6;border-bottom:1px solid #edf1f6;padding:7px 9px;text-align:center;font-size:10.5px;line-height:1.15;height:38px;box-sizing:border-box}.planningTable th:first-child,.planningTable td:first-child{position:sticky;left:0;background:#fff;z-index:3;text-align:left;min-width:88px}.planningTable thead th{position:sticky;background:#f8fafc;font-weight:650}.planningTable thead .planningLaneGroups th{top:0;z-index:6;height:28px}.planningTable thead tr:nth-child(2) th{top:28px;z-index:5;height:48px}.planningTable thead th[rowspan="2"]{top:0;z-index:8;height:76px;background:#f8fafc}.planningTable thead th:first-child{left:0;background:#f8fafc}.planningTable th small{display:block;color:var(--muted);font-weight:450;margin-top:2px}.planningAssetHead{display:flex;align-items:center;justify-content:center;gap:7px}.planningAssetHead>span:last-child{display:flex;flex-direction:column;align-items:flex-start;min-width:0}.planningAssetHead b{max-width:150px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.planningSystemHead{display:flex;align-items:center;justify-content:center;gap:6px}.planningColumnHead{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;width:100%;text-align:center}.planningColumnHead b,.planningColumnHead small{display:block;text-align:center;margin:0}.planningIconBadge{display:inline-flex;align-items:center;justify-content:center;flex:0 0 auto;border-radius:9px;width:29px;height:29px;font-size:16px;line-height:1;background:#eef5ff;color:#2563eb;box-shadow:inset 0 0 0 1px rgba(37,99,235,.10)}.planningIconBadge.purple{background:#f2edff;color:#7137d8;box-shadow:inset 0 0 0 1px rgba(113,55,216,.12)}.planningIconBadge.green{background:#eaf8ef;color:#239551;box-shadow:inset 0 0 0 1px rgba(35,149,81,.12)}.planningIconBadge.orange{background:#fff5df;color:#e59a00;box-shadow:inset 0 0 0 1px rgba(229,154,0,.14)}.planningIconBadge.slate{background:#f1f4f8;color:#64748b;box-shadow:inset 0 0 0 1px rgba(100,116,139,.12)}.planningIconBadge.system{width:25px;height:25px;font-size:14px;border-radius:8px}.planningIconBadge.mini{width:22px;height:22px;font-size:12px;border-radius:7px;margin-right:5px}.planningIconBadge.hero{width:45px;height:45px;font-size:23px;border-radius:13px}.planningHeroLead{display:flex;align-items:flex-start;gap:13px}.planningFooterAsset{display:inline-flex;align-items:center}.planningUnit{margin-top:3px}.planningTime{display:flex;align-items:center;gap:5px;font-weight:600}.planningTime em{font-style:normal;font-size:7px;padding:2px 4px;border-radius:5px;background:#ede9fe;color:#7c3aed}.planningCurrent td{background:#fcfbff}.planningCurrent td:first-child{background:#fcfbff}.planningTable td small{display:block;color:var(--muted);font-size:8.5px;margin-top:2px;max-width:130px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.planningWait{display:inline-flex;align-items:center;justify-content:center;gap:5px;color:#b7791f;font-weight:650}.planningCellState{display:flex;align-items:center;justify-content:center;gap:4px}.planningStateDot{display:inline-block;width:6px;height:6px;border-radius:50%}.planningStateDot.active{background:#f59e0b}.planningStateDot.wait{background:#cbd5e1}.planningPowerValue{font-size:11px}.planningIdle,.planningUnavailable{color:#94a3b8}.planningExport{color:#15803d}.planningImport{color:#dc2626}.planningFooter{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(120px,.45fr) minmax(0,1fr);gap:0;margin-top:8px;border:1px solid var(--line);border-radius:10px;overflow:hidden}.planningFooter>div{padding:9px 12px;border-right:1px solid var(--line)}.planningFooter>div:last-child{border-right:0}.planningFooter small{display:block;color:var(--muted);font-size:9px;margin-bottom:5px}.planningFooter>div>div{display:flex;gap:14px;flex-wrap:wrap}.planningFooter span{font-size:10.5px}.planningFooter span i{margin-right:4px}.planningFooter b{font-size:11px}.planningHeaderNeed{color:#6d28d9;font-weight:600;font-size:9px;margin-top:3px}.planningTotalSpacer td{height:52px;padding:0;border:0;background:#fff}.planningTotalSpacer td:first-child{position:static}.planningTotalRow th,.planningTotalRow td{position:sticky;bottom:0;background:#fbfcfe;z-index:7;height:52px;border-top:1px solid #dfe5ed;font-weight:600;box-shadow:0 -1px 0 #dfe5ed}.planningTotalRow th:first-child{left:0;z-index:9;background:#fbfcfe}.planningTotalRow td small,.planningTotalRow th small{display:block;margin-top:3px;color:var(--muted);font-weight:450}.planningTotalAsset b{color:#6d28d9}.planningAggregateTotals{display:grid;grid-template-columns:repeat(3,minmax(110px,1fr));gap:0;margin-top:8px;border-top:1px solid var(--line)}.planningAggregateTotals>span{padding:8px 12px 0;border-right:1px solid var(--line)}.planningAggregateTotals>span:last-child{border-right:0}.planningAggregateTotals small{margin-bottom:3px}.planningAggregateTotals b{font-size:11px}.planningAggregateTotals>span:last-child b{color:#6d28d9}@media(max-width:700px){.planningHero{min-height:120px;padding:15px}.planningHero h2{font-size:20px}.planningHeroValue{font-size:30px}.planningMatrixPanel{padding:7px}.planningTableWrap{max-height:390px}.planningFooter{grid-template-columns:1fr}.planningFooter>div{border-right:0;border-bottom:1px solid var(--line)}.planningFooter>div:last-child{border-bottom:0}}

.retroCollectingState{display:grid;grid-template-columns:64px minmax(0,1fr);gap:18px;align-items:start;padding:28px}.retroCollectingIcon{width:56px;height:56px;border-radius:18px;display:grid;place-items:center;background:#f5f3ff;color:#6d28d9;font-size:28px}.retroCollectingState small{display:block;color:#7c3aed;font-weight:800;letter-spacing:.12em}.retroCollectingState h2{margin:5px 0 8px;font-size:24px}.retroEvidenceSteps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:18px 0}.retroEvidenceSteps span{display:grid;gap:4px;padding:12px;border:1px solid #e5e7eb;border-radius:12px;background:#fafafa}.retroEvidenceSteps b{font-size:12px}.retroEvidenceSteps em{font-size:11px;color:#64748b;font-style:normal}@media(max-width:700px){.retroCollectingState{grid-template-columns:1fr}.retroEvidenceSteps{grid-template-columns:1fr}}
      .flexibleMeteringPanel{margin-top:12px}.flexibleMeteringPanel .tableWrap{overflow:auto;border:1px solid var(--divider-color,#e5e7eb);border-radius:12px}.flexibleMeteringTable{width:100%;border-collapse:collapse;min-width:560px}.flexibleMeteringTable th,.flexibleMeteringTable td{padding:12px 14px;text-align:left;border-bottom:1px solid var(--divider-color,#e5e7eb);vertical-align:middle}.flexibleMeteringTable th{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--secondary-text-color)}.flexibleMeteringTable tr:last-child td{border-bottom:0}.flexibleMeteringTable td.numeric,.flexibleMeteringTable th.numeric{text-align:right}.flexibleMeteringTable td small{display:block;color:var(--secondary-text-color);font-weight:400;margin-top:3px}.quickAutomation{display:inline-flex;align-items:center;gap:10px;padding:6px 10px;border:1px solid #dbe6f3;border-radius:11px;background:#fff}.quickAutomationLabel{font-size:12px;font-weight:700;color:#111827;white-space:nowrap}.quickAutomation .hiSegmented{margin:0;width:auto}.quickAutomation .hiSegment{min-height:34px;min-width:90px;padding:7px 11px;font-size:12px;font-weight:650}
      .operationalOverview,.planningOverview{padding:12px 14px}.operationalOverviewHead h2,.planningOverview h2{margin:0;font-size:16px}.operationalOverviewHead p{margin:3px 0 10px;font-size:11px;color:#64748b;line-height:1.4}.operationalSummaryGrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.operationalSummaryCard{display:grid;grid-template-columns:42px 1fr;align-items:center;gap:10px;min-height:72px;padding:11px 13px;border:1px solid #e4eaf2;border-radius:12px;background:#fff}.operationalSummaryCard.charging{background:#f7fcf8;border-color:#d8efdf}.operationalSummaryCard.next{background:#f7faff;border-color:#d8e6fb}.operationalSummaryCard.planned{background:#fbf9ff;border-color:#eadffc}.operationalSummaryCard.exceptional{background:#fffaf7;border-color:#f8dfcf}.summaryIcon{display:grid;place-items:center;width:36px;height:36px;border-radius:10px;background:#fff;font-size:20px}.operationalSummaryCard small{display:block;font-size:10px;font-weight:700;letter-spacing:.02em}.operationalSummaryCard b{display:block;font-size:19px;line-height:1.1;margin-top:2px}.operationalSummaryCard p{margin:4px 0 0;font-size:11px;line-height:1.4;color:#64748b}
      .solarLoadRow{padding:0;overflow:hidden;border:1px solid #e3eaf2;border-radius:13px;background:#fff}.solarLoadSummary{display:grid;grid-template-columns:1.45fr .85fr .9fr .8fr .85fr 1.25fr .9fr;align-items:center;gap:12px;padding:12px 14px}.solarLoadIdentity{display:grid;grid-template-columns:34px minmax(0,1fr);align-items:center;gap:9px}.solarLoadIcon{display:grid;place-items:center;width:34px;height:34px;border-radius:10px;background:#f5f3ff}.solarLoadName{display:flex;align-items:center;gap:7px}.solarLoadName h3{margin:0;font-size:13px;line-height:1.3}.priorityBadge{display:inline-flex;padding:3px 7px;border-radius:999px;background:#eef5ff;color:#475569;font-size:9.5px;font-weight:700;white-space:nowrap}.solarLoadIdentity small,.planningLoadIdentity small{display:flex;align-items:center;gap:4px;margin-top:3px;font-size:10.5px;color:#64748b}.solarLoadFact{min-width:0}.solarLoadFact small,.planningLoadRow>div>small{display:block;margin-bottom:4px;font-size:9px;font-weight:750;letter-spacing:.05em;text-transform:uppercase;color:#64748b}.solarLoadFact b,.planningLoadRow>div>b{display:block;font-size:12px;line-height:1.3}.solarLoadFact span{display:block;margin-top:2px;font-size:10.5px;color:#64748b}.nextActionBadge{display:inline-flex;width:max-content;max-width:100%;padding:4px 7px;border-radius:7px;background:#eef5ff;color:#2563eb;font-size:11px;font-weight:700}.planStatusBadge{display:inline-flex;width:max-content;padding:5px 8px;border-radius:8px;font-size:10px;font-weight:700}.planStatusBadge.ok{background:#eafaf0;color:#15803d}.planStatusBadge.exception{background:#fff1f2;color:#be123c}.solarLoadControls{display:grid;grid-template-columns:minmax(0,2.2fr) minmax(260px,.9fr);gap:18px;align-items:center;padding:10px 14px;border-top:1px solid #edf1f5;background:#fbfdff}.solarLoadControls .requestedSlot{display:grid;grid-template-columns:150px minmax(0,1fr);align-items:center;gap:12px}.controlTitle{font-size:10px;font-weight:700;color:#475569}.solarLoadControls .loadActions{display:flex;align-items:center;justify-content:flex-start;gap:9px;border-left:1px solid #e5eaf0;padding-left:18px}.solarLoadControls .loadActions>span{margin-right:8px;font-size:10px;color:#64748b}.solarLoadRow .loadDetailsFull{display:none}
      .valueAssetIdentity{display:flex;align-items:center;gap:10px;min-width:0}.valueAssetIdentity>span{min-width:0}.valueAssetIdentity b{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.valueAssetIdentity small{display:block;margin-top:3px;font-size:10px;color:#64748b}.valueConsumerRow{align-items:center;min-height:72px}.flexPricingRow>div.valueAssetIdentity{display:flex}
      .assetVisual{position:relative;display:inline-flex;align-items:center;justify-content:center;flex:0 0 auto;border-radius:10px;background:#f5f7fa;overflow:hidden;border:1px solid #e8edf3}.assetVisual img{display:block;width:100%;height:100%;object-fit:contain}.assetVisualAppearance{position:absolute;left:5px;bottom:5px;padding:3px 5px;border:1px solid rgba(148,163,184,.75);border-radius:6px;background:rgba(255,255,255,.94);color:#355D96;font-size:7.5px;font-weight:750;line-height:1;pointer-events:none}.assetVisual-xs{width:38px;height:30px;padding:2px}.assetVisual-sm{width:54px;height:42px;padding:3px}.assetVisual-md{width:72px;height:54px;padding:4px}.assetVisualFallback{font-size:18px;color:#52657f}.assetIdentityChip{display:inline-flex;align-items:center;gap:7px;margin:2px 8px 2px 0;vertical-align:middle}.assetIdentityChip>span:last-child{min-width:0}.assetIdentityChip b{display:block;font-size:11px;line-height:1.2}.assetIdentityChip small{display:block;margin-top:2px;font-size:9.5px;color:#64748b}.operationalSummaryCard p{display:flex;align-items:center;flex-wrap:wrap;gap:2px}.solarLoadIdentity{grid-template-columns:54px minmax(0,1fr)}.planningLoadIdentity{grid-template-columns:54px minmax(0,1fr)}.planningAssetHead{display:flex;align-items:center;gap:7px}.planningFooterAsset{display:inline-flex;align-items:center;gap:6px}.outlookChildRow{display:grid;grid-template-columns:38px minmax(0,1fr) auto;align-items:center;gap:8px}
      .planningKpiStrip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin:8px 0;border:1px solid #e3eaf2;border-radius:13px;background:#fff;overflow:hidden}.planningKpiStrip article{padding:14px 18px;border-left:1px solid #edf1f5}.planningKpiStrip article:first-child{border-left:0}.planningKpiStrip small{display:block;font-size:10px;color:#64748b}.planningKpiStrip b{display:block;margin-top:3px;font-size:17px}.planningOverview{margin:8px 0}.plannedFlexibleLoads{margin-top:8px}.planningLoadList{display:grid;gap:0;border:1px solid #e4eaf2;border-radius:11px;overflow:hidden}.planningLoadRow{display:grid;grid-template-columns:1.45fr 1fr .8fr .85fr 1.2fr .9fr;align-items:center;gap:12px;padding:11px 13px;border-top:1px solid #edf1f5}.planningLoadRow:first-child{border-top:0}.planningLoadIdentity{display:grid;grid-template-columns:32px minmax(0,1fr);align-items:center;gap:8px}.planningLoadName{display:flex;align-items:center;gap:7px}.planningLoadName b{font-size:12px;line-height:1.3}
      @media(max-width:900px){.operationalSummaryGrid{grid-template-columns:repeat(2,minmax(0,1fr))}.solarLoadSummary{grid-template-columns:1.4fr repeat(3,minmax(0,1fr))}.solarLoadWhy{grid-column:2/4}.solarLoadControls{grid-template-columns:1fr}.solarLoadControls .loadActions{border-left:0;padding-left:0}.planningLoadRow{grid-template-columns:1.4fr repeat(2,minmax(0,1fr))}.planningLoadRow>div:nth-child(n+5){margin-top:6px}}
      @media(max-width:650px){.quickAutomation{width:100%;justify-content:space-between;flex-wrap:wrap}.quickAutomationLabel{font-size:11px}.quickAutomation .hiSegmented{width:100%}.quickAutomation .hiSegment{min-width:0;flex:1 1 0;padding:7px 8px;font-size:11px}.operationalSummaryGrid,.planningKpiStrip{grid-template-columns:1fr 1fr}.solarLoadSummary{grid-template-columns:1fr 1fr}.solarLoadIdentity,.solarLoadWhy{grid-column:1/-1}.solarLoadControls .requestedSlot{grid-template-columns:1fr}.planningLoadRow{grid-template-columns:1fr 1fr}.planningLoadIdentity{grid-column:1/-1}}

.flexibleMeteringTable .meteringTotalRow td{border-top:2px solid var(--line);background:#f8fafc;font-weight:700}.flexibleMeteringTable .meteringTotalRow td:first-child b{font-size:12px}
























      @media(max-width:1024px){




      }
      @media(max-width:760px){








      }
      @media(max-width:430px){







      }


      /* 4.3.22 UX-only literal product grammar: compact, predictable, no whitespace-led hierarchy. */
      .energyAssetFoldStack{display:grid;gap:0;margin-top:6px;border-top:1px solid #edf1f5}
      .energyAssetDisclosure{margin:0;border:0;border-bottom:1px solid #edf1f5;background:transparent;border-radius:0}
      .energyAssetDisclosure:last-child{border-bottom:0}
      .energyAssetDisclosure>summary{min-height:42px;box-sizing:border-box;display:flex;align-items:center;justify-content:space-between;padding:8px 4px;cursor:pointer;list-style:none;font-size:11px;font-weight:700;color:#42526a}
      .energyAssetDisclosure>summary::-webkit-details-marker{display:none}.energyAssetDisclosure>summary:after{content:"›";font-size:17px;color:#94a3b8;transform:rotate(0deg)}.energyAssetDisclosure[open]>summary:after{transform:rotate(90deg)}
      .energyAssetFoldBody{padding:2px 4px 9px}.energyAssetDetailGrid,.energyAssetDiagnosticGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px}
      .energyAssetDetailGrid>span,.energyAssetDiagnosticGrid>span{min-height:34px;padding:6px 8px;border-radius:8px;background:#f8fafc;box-sizing:border-box}.energyAssetDetailGrid small,.energyAssetDiagnosticGrid small{display:block;font-size:8px;color:#64748b}.energyAssetDetailGrid b,.energyAssetDiagnosticGrid b{display:block;margin-top:1px;font-size:10px;line-height:1.25;overflow-wrap:anywhere}
      .energyAssetChildrenBody{padding-top:4px}.energyAssetQuickActions{display:flex;align-items:center;gap:8px;margin:5px 0}.energyAssetQuickActions>small{font-size:8px;font-weight:750;letter-spacing:.08em;text-transform:uppercase;color:#64748b}.energyAssetQuickActions>div{display:flex;gap:6px;flex-wrap:wrap}
      .energyDeviceCard{grid-template-columns:112px minmax(0,1fr);gap:10px;padding:10px;border-radius:13px}.energyDeviceVisual{height:106px}.energyDeviceTop h3{font-size:16px;margin:1px 0}.energyDeviceTop small{font-size:8px}.energyDeviceState{padding:3px 7px;font-size:9px}.energyDeviceFacts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin:5px 0}.energyDeviceFacts>span{min-height:36px;padding:6px 8px;border-radius:8px}.energyDeviceFacts small{font-size:8px}.energyDeviceFacts b{font-size:10.5px;margin-top:1px}
      .solarProductionObject{display:grid;grid-template-columns:150px minmax(0,1fr);gap:12px;padding:10px;border:1px solid #e3eaf2;border-radius:13px;background:#fff}.solarProductionRepresentativeWrap{display:grid;place-items:center;min-height:112px}.solarProductionRepresentative{width:100%;height:112px}.solarProductionRepresentative img{width:100%;height:100%;object-fit:contain}.solarProductionObjectHead{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.solarProductionObjectHead h3{margin:1px 0;font-size:17px}.solarProductionObjectHead small{font-size:8px;color:#64748b}.solarProductionObjectHead>b{font-size:10px;padding:4px 8px;border-radius:999px;background:#eef9f2;color:#237346}
      .solarStringLink{padding:9px;border-radius:11px}.solarStringSummary{gap:8px}.solarModuleGrid{gap:7px}.solarInverterGrid{gap:8px}.solarInverterStrings{margin:0;padding:0;border:0}
      .compactManagedAsset,.compactOperationalLoad{padding:9px 11px;border-radius:12px;margin:0;border:1px solid #e4eaf2;background:#fff}.managedAssetHeader{display:flex;justify-content:space-between;align-items:center;gap:10px}.managedAssetIdentity{display:flex;align-items:center;gap:9px;min-width:0}.managedAssetIdentity h3{margin:0;font-size:13px}.managedAssetIdentity span{display:block;margin-top:2px;font-size:9.5px;color:#64748b}.managedAssetHeader>b{font-size:13px;white-space:nowrap}.managedAssetFacts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px;margin:6px 0}.managedAssetFacts>span{padding:5px 7px;border-radius:8px;background:#f8fafc}.managedAssetFacts small{display:block;font-size:8px;color:#64748b}.managedAssetFacts b{display:block;font-size:10px;margin-top:1px}.consumerExplorerList,.flexLoadList{display:grid;gap:7px}
      .operationalPlanningPage .productStory{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:10px;padding:10px 12px;margin-bottom:7px}.operationalPlanningPage .productStoryCopy>small{font-size:8px}.operationalPlanningPage .productStoryCopy h2{font-size:14px;margin:1px 0}.operationalPlanningPage .productStoryCopy p{font-size:10px;margin:2px 0}.operationalPlanningPage .productStoryRecommendation{display:none}.operationalPlanningPage .productStoryActions{align-self:center}
      .settingsTopicPage{display:grid;gap:8px}.compactSettingsBlock{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:10px;padding:11px 14px}.compactSettingsBlock h2{font-size:16px;margin:0}.compactSettingsBlock p{font-size:10px;margin:2px 0 0}.settingsTopicChooser{padding:12px 14px}.settingsTopicHead h2{font-size:16px;margin:0}.settingsTopicHead p{font-size:10px;margin:2px 0 8px}.settingsTopicGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.settingsTopicButton{min-height:62px;text-align:left;padding:9px 10px;border:1px solid #dfe7f0;border-radius:10px;background:#fff;color:#23324a}.settingsTopicButton.active{border-color:#93c5fd;background:#f5f9ff;box-shadow:inset 0 0 0 1px #bfdbfe}.settingsTopicButton b{display:block;font-size:11px}.settingsTopicButton span{display:block;margin-top:3px;font-size:8.5px;line-height:1.25;color:#64748b;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
      .settingsSelectedTopicHead{display:flex;align-items:end;justify-content:space-between;gap:10px;padding:3px 2px}.settingsSelectedTopicHead small{font-size:8px;color:#64748b}.settingsSelectedTopicHead h2{font-size:17px;margin:1px 0}.settingsVariantSelect{display:flex;align-items:center;gap:6px}.settingsVariantSelect span{font-size:9px;color:#64748b}.settingsVariantSelect select{height:34px;border:1px solid #dbe3ee;border-radius:8px;background:#fff;padding:0 8px}.settingsSelectedTopic .strategyTablePanel{margin:0;padding:11px 14px;border-radius:12px}.settingsSelectedTopic .strategyTableHead h2{font-size:15px}.settingsSelectedTopic .strategyTableHead p{font-size:9.5px;margin:2px 0}.settingsSelectedTopic .strategyTableRow{padding:7px 0}.settingsSelectedTopic .strategyColumnHead{display:none}.settingsAdvancedDisclosure{padding:0 12px;margin:0}.settingsAdvancedDisclosure>summary{height:42px;display:flex;align-items:center;font-size:11px;font-weight:700;cursor:pointer}.settingsAdvancedBody{display:grid;gap:8px;padding:0 0 10px}.settingsAdvancedBody h3{font-size:12px;margin:0 0 5px}
      .strategicBehaviorPage{display:grid;gap:8px}.compactStrategicIntro{padding:11px 14px}.compactStrategicIntro small{font-size:8px;color:#64748b}.compactStrategicIntro h2{font-size:16px;margin:2px 0}.compactStrategicIntro p{font-size:10px;line-height:1.35;margin:2px 0}.strategicBehaviorGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.strategicBehaviorCard{padding:11px 13px}.strategicBehaviorCard h2{font-size:14px;margin:0 0 5px}.strategicBehaviorRows{display:grid}.strategicBehaviorRow{display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:32px;border-top:1px solid #edf1f5}.strategicBehaviorRow:first-child{border-top:0}.strategicBehaviorRow span{font-size:9.5px;color:#52637a}.strategicBehaviorRow b{font-size:10px;text-align:right}
      .compactPlanningLoad{grid-template-columns:minmax(190px,1.15fr) minmax(0,2fr) auto;padding:8px 10px;gap:9px}.compactPlanningFacts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:5px}.compactPlanningFacts>span{min-width:0}.compactPlanningFacts small{display:block;font-size:8px;color:#64748b}.compactPlanningFacts b{display:block;font-size:10px;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      @media(max-width:900px){.energyAssetDetailGrid,.energyAssetDiagnosticGrid{grid-template-columns:repeat(2,minmax(0,1fr))}.energyDeviceFacts,.managedAssetFacts,.compactPlanningFacts{grid-template-columns:repeat(2,minmax(0,1fr))}.settingsTopicGrid{grid-template-columns:repeat(2,minmax(0,1fr))}.compactPlanningLoad{grid-template-columns:1fr auto}.compactPlanningFacts{grid-column:1/-1}}
      @media(max-width:620px){.energyDeviceCard,.solarProductionObject{grid-template-columns:88px minmax(0,1fr)}.energyDeviceVisual,.solarProductionRepresentative{height:78px}.solarProductionRepresentativeWrap{min-height:78px}.energyAssetDetailGrid,.energyAssetDiagnosticGrid{grid-template-columns:1fr 1fr}.settingsTopicGrid,.strategicBehaviorGrid{grid-template-columns:1fr}.compactSettingsBlock{grid-template-columns:1fr}.managedAssetFacts{grid-template-columns:1fr 1fr}}



      /* 4.3.25: semantic hierarchy is vertical; child expansion never creates a nested visual container. */
      .energyAssetNode{display:grid;gap:0;min-width:0;width:100%}
      .energyAssetChildrenSibling{margin:0;width:100%;min-width:0;border:0;border-radius:0;background:transparent;overflow:visible}
      .energyAssetChildrenSibling>summary{min-height:40px;display:flex;align-items:center;justify-content:space-between;padding:7px 4px;box-sizing:border-box;cursor:pointer;list-style:none;font-size:10px;font-weight:750;color:#42526a;background:transparent;border-top:1px solid #edf1f5}
      .energyAssetChildrenSibling>summary::-webkit-details-marker{display:none}
      .energyAssetChildrenSibling>summary:after{content:"›";font-size:16px;color:#94a3b8}
      .energyAssetChildrenSibling[open]>summary:after{transform:rotate(90deg)}
      .energyAssetChildrenStack{display:grid;gap:7px;padding:7px 0 0;width:100%;min-width:0;box-sizing:border-box}
      .energyAssetChildrenStack>.solarInverterCard,.energyAssetChildrenStack>.energyAssetNode,.solarProductionChildren,.solarInverterGrid{width:100%;min-width:0;margin:0}
      .energyAssetChildrenStack .energyAssetChildrenSibling{margin:0}
      .solarProductionChildren{display:grid;gap:7px}
      .solarInverterGrid{display:grid;grid-template-columns:1fr;gap:7px}
      .solarInverterCard{margin:0;padding:0;border:0;background:transparent;min-width:0}
      .solarStringNode{width:100%;min-width:0}
      .solarStringLink{width:100%;min-width:0;box-sizing:border-box;border:1px solid #e5ebf3;border-radius:11px;padding:9px}
      .solarModuleGrid{grid-template-columns:repeat(auto-fit,minmax(220px,1fr));width:100%;min-width:0}
      .solarProductionNode{width:100%;min-width:0}
      .solarHardwareSection#solar-production-detail{margin:12px 0}
      .solarHardwareSection#solar-production-detail>.solarProductionNode{width:100%}
      .compactManagedAsset .assetVisual img{width:100%;height:100%;object-fit:contain}
</style><style>
.navigationShell{--nav-active-bg:#edf5ff;--nav-active-border:#cfdef1;--nav-active-text:#0f4ca4;--rhi-company-area-min:250px;--rhi-company-area-max:320px;--rhi-company-logo-max-width:286px;--rhi-company-logo-max-height:116px;--rhi-company-logo-padding:10px 16px;--rhi-company-divider:rgba(226,232,240,.82);position:relative;display:grid;grid-template-columns:minmax(0,1fr) minmax(var(--rhi-company-area-min),var(--rhi-company-area-max));gap:0;margin:0 0 12px;background:linear-gradient(180deg,rgba(255,255,255,.96),rgba(249,251,254,.91));border:1px solid rgba(207,217,230,.86);border-radius:22px;box-shadow:0 12px 30px rgba(15,23,42,.045);overflow:hidden;backdrop-filter:blur(16px)}.navigationShell.nav-intelligence{--nav-active-bg:#f1edff;--nav-active-border:#dfd5fb;--nav-active-text:#5a38b3}.navigationShell.nav-insights{--nav-active-bg:#e7f7f4;--nav-active-border:#cdebe6;--nav-active-text:#176e67}
.navProductArea{min-width:0}.navPrimaryRow{min-height:78px;display:grid;grid-template-columns:minmax(270px,.72fr) minmax(430px,1.28fr);align-items:center;gap:24px;padding:10px 22px 9px}.navBrand{display:flex;align-items:center;min-width:0;min-height:56px;padding:2px 0 0 4px}.navBrandCopy{display:grid;align-content:center;gap:2px;min-width:0}.navBrandCopy b{font-size:15px;line-height:1.1;font-weight:520;letter-spacing:-.01em;color:#58708f;white-space:nowrap}.navBrandCopy small{font-size:24px;line-height:1.02;letter-spacing:.055em;font-weight:790;color:#0b467f;white-space:nowrap}
.navSections,.navItems{display:flex;align-items:center;overflow-x:auto;overflow-y:hidden;white-space:nowrap;scrollbar-width:none;-webkit-overflow-scrolling:touch;overscroll-behavior-inline:contain}.navSections::-webkit-scrollbar,.navItems::-webkit-scrollbar{display:none}
.navSections{justify-content:flex-start;gap:14px;padding:0;background:transparent;border:0;border-radius:0;max-width:100%}.navSectionTab{min-height:50px;border:0;border-radius:15px;background:transparent;padding:10px 20px;font:inherit;font-size:13px;font-weight:660;color:#53647d;cursor:pointer;white-space:nowrap;display:flex;align-items:center;gap:10px;transition:background .15s ease,color .15s ease,box-shadow .15s ease}.navSectionTab:hover{background:#f8fafc;color:#2f3f56}.navSectionTab.active{background:var(--nav-active-bg);color:var(--nav-active-text);box-shadow:inset 0 0 0 1px var(--nav-active-border),0 6px 16px rgba(15,23,42,.035)}.navSectionIcon{width:22px;height:22px;display:grid;place-items:center;flex:0 0 22px}.navSectionIcon svg{width:100%;height:100%;fill:none;stroke:currentColor;stroke-width:1.9;stroke-linecap:round;stroke-linejoin:round}.navSectionTab[data-nav-section="energy"] .navSectionIcon svg path{fill:none}
.navItems.tabs{margin:0;padding:7px 22px 9px;gap:10px;border:0;border-top:1px solid rgba(226,232,240,.82);border-radius:0;background:rgba(255,255,255,.52);box-shadow:none;backdrop-filter:none;min-height:52px}.navItemTab{flex:0 0 auto;min-height:34px;border:0;border-radius:11px;background:transparent;padding:7px 12px;font:inherit;font-size:11px;font-weight:600;color:#5f6d80;cursor:pointer;white-space:nowrap;display:flex;align-items:center;gap:6px;transition:background .15s ease,color .15s ease,box-shadow .15s ease}.navItemIcon{width:13px;height:13px;display:grid;place-items:center;flex:0 0 13px;color:#7a8798}.navItemIcon svg{width:100%;height:100%;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}.navItemTab:hover{background:#f8fafc;color:#425269}.navItemTab:hover .navItemIcon{color:#66758a}.navItemTab.active{background:var(--nav-active-bg);color:var(--nav-active-text);box-shadow:inset 0 0 0 1px var(--nav-active-border)}.navItemTab.active .navItemIcon{color:#718096}
.navCompany{min-width:0;border-left:1px solid var(--rhi-company-divider);display:grid;place-items:center;padding:var(--rhi-company-logo-padding);background:linear-gradient(180deg,rgba(252,254,255,.78),rgba(247,250,253,.58))}.navCompanyLogo{display:block;width:min(100%,var(--rhi-company-logo-max-width));height:auto;max-height:var(--rhi-company-logo-max-height);object-fit:contain;object-position:center;}
.hiTabExperienceHeader{margin-top:0}.hiTabPurpose{font-size:11.5px;line-height:1.35;color:#64748b;margin:0 0 12px;max-width:620px}.hiTabLiveLine{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}.hiTabLiveLine strong{font-size:11px;color:#334155}.hiTabLiveLine>span{font-size:10px;color:#64748b}.navigationPlaceholder{max-width:780px;margin:0 auto}.navigationPlaceholder>small{display:block;font-size:9px;letter-spacing:.13em;font-weight:750;color:#64748b;margin-bottom:6px}
@media(max-width:1180px){.navigationShell{--rhi-company-area-min:220px;--rhi-company-area-max:250px;--rhi-company-logo-max-width:220px;--rhi-company-logo-max-height:94px;--rhi-company-logo-padding:8px 12px}.navPrimaryRow{grid-template-columns:minmax(225px,.62fr) minmax(0,1.38fr);gap:14px;padding-inline:16px}.navSections{gap:6px}.navSectionTab{padding:9px 14px;font-size:11.5px}.navBrandCopy b{font-size:13.5px}.navBrandCopy small{font-size:21px}.navItems.tabs{gap:7px;padding-inline:16px}.navItemTab{padding:7px 13px;font-size:11px}.navCompany{padding-inline:12px}}
@media(max-width:820px){.navigationShell{--rhi-company-logo-max-width:126px;--rhi-company-logo-max-height:48px;display:block;border-radius:18px}.navProductArea{min-width:0}.navCompany{position:absolute;top:8px;right:10px;width:126px;height:48px;padding:0;border:0;background:transparent;pointer-events:none}.navCompanyLogo{max-height:var(--rhi-company-logo-max-height)}.navPrimaryRow{display:grid;grid-template-columns:1fr;gap:7px;min-height:0;padding:10px 8px 7px}.navBrand{min-height:48px;padding:1px 138px 0 6px}.navBrandCopy b{font-size:12.5px}.navBrandCopy small{font-size:19px}.navSections{width:100%;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px}.navSectionTab{min-width:0;min-height:41px;justify-content:center;padding:7px 5px;font-size:10.5px;gap:6px}.navSectionIcon{width:17px;height:17px;flex-basis:17px}.navItems.tabs{display:flex;overflow-x:auto;white-space:nowrap;padding:5px 8px 7px;gap:4px;min-height:48px}.navItemTab{min-height:35px;padding:6px 11px;font-size:10.5px}.hiTabPurpose{font-size:10px;margin-bottom:8px;display:block;-webkit-line-clamp:unset}.hiTabLiveLine strong{font-size:9.5px}}
@media(max-width:430px){.navigationShell{--rhi-company-logo-max-width:102px;--rhi-company-logo-max-height:42px}.navCompany{width:102px;right:8px}.navBrand{padding-right:112px}.navBrandCopy small{font-size:17px}.navSectionTab{font-size:10px}.navItemTab{padding:6px 9px;font-size:10px}.hiTabPurpose{max-width:48ch}}}

/* R3.95.3 TERMINAL top-level visual contract — MUST remain last in cascade. */
.hiTabExperienceHeader{display:grid;grid-template-columns:minmax(0,1fr);grid-auto-flow:row;align-items:stretch;width:100%;gap:8px;margin:0}





.hiTabPurpose{display:block;max-width:510px;margin:0;font-size:clamp(12px,1.15vw,16px);line-height:1.42;color:#536A91;font-weight:500;-webkit-line-clamp:unset;overflow:visible}





.hiTabStatusItem{min-width:0;min-height:94px;height:auto;display:grid;grid-template-columns:52px minmax(0,1fr);gap:11px;align-items:center;padding:12px 14px;border:1px solid #DBE6F3;border-radius:15px;background:rgba(255,255,255,.97);box-shadow:0 8px 22px rgba(21,61,115,.045)}
.hiTabStatusIcon{width:46px;height:46px;min-width:46px;border-radius:14px;display:flex;align-items:center;justify-content:center;background:#EEF5FF;border:0;font-size:24px}
.hiTabStatusCopy{min-width:0;display:block}
.hiTabStatusCopy small{display:block;margin:0 0 3px;color:#31558E;font-size:10px;font-weight:650}
.hiTabStatusCopy b{display:block;margin:0 0 3px;color:#0B173D;font-size:clamp(14px,1.25vw,18px);font-weight:720;line-height:1.08;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.hiTabStatusCopy em{display:block;margin-top:2px;color:#55709B;font-size:10px;font-style:normal;font-weight:500;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}


.hiQuickActionItems{display:flex;align-items:center;gap:8px;flex-wrap:wrap;min-width:0;overflow:visible}
.hiQuickAction{height:40px;min-height:40px;border:1px solid #D8E4F1;border-radius:10px;background:#fff;color:#075FD8;box-shadow:none;font-size:11px;font-weight:660;padding:0 13px;display:inline-flex;align-items:center;gap:7px;cursor:pointer;white-space:nowrap}
.hiQuickAction:first-child{background:#0B66F6;border-color:#0B66F6;color:#fff}
@media(max-width:1024px){.hiTabStatusItem{grid-template-columns:42px minmax(0,1fr);padding:10px;min-height:88px}.hiTabStatusIcon{width:40px;height:40px;min-width:40px}}
@media(max-width:760px){.hiTabPurpose{font-size:12px}.hiQuickActionItems{flex-wrap:nowrap}.hiQuickAction{flex:0 0 auto}}
@media(max-width:430px){.hiTabPurpose{font-size:10px;line-height:1.3}.hiTabStatusItem{grid-template-columns:34px minmax(0,1fr);min-height:76px;padding:8px;gap:7px}.hiTabStatusIcon{width:32px;height:32px;min-width:32px;border-radius:10px;font-size:18px}}
</style><main class="energy rhiUxDomainBody rhi-ux-root">${this.nav()}${this.renderMainWarning(footer)}<section>${content}</section>${this.propertyDraftBar()}${this.energyVisualPickerOverlay(rt)}${this.renderFooter(rt,this.view,footer)}</main>`;
      if (markup === this._lastMarkup) { this.persistInteractionContext(); return; }
      this._lastMarkup = markup;
      this.persistInteractionContext();
      const canPatch = this._renderedView === this.view && this._renderedNavSection === this.navSection && this._renderedNavItem === this.navItem && !!this.shadowRoot.querySelector('main');
      if (canPatch) {
        this.patchMarkup(markup);
        this.restoreInteractionState();
        this.mountGasStatisticsGraph();
        this.mountEnergyHistoryGraphs();
        this.mountPowerFlowCard();
        if (viewport) queueMicrotask(() => window.scrollTo(viewport.x, viewport.y));
        return;
      }
      const nextMarkup = document.createElement('template');
      nextMarkup.innerHTML = markup;
      this.shadowRoot.replaceChildren(nextMarkup.content.cloneNode(true));
      this._renderedView = this.view;
      this._renderedNavSection = this.navSection;
      this._renderedNavItem = this.navItem;
      this.restoreInteractionState();
      this.mountGasStatisticsGraph();
      this.mountEnergyHistoryGraphs();
      this.mountPowerFlowCard();
      const tabs = this.shadowRoot.querySelector('.navItems');
      if (tabs) {
        tabs.scrollLeft = this.navScrollLeft || 0;
        tabs.addEventListener('scroll', () => { this.navScrollLeft = tabs.scrollLeft; this.persistInteractionContext(); }, { passive: true });
      }
      const main = this.shadowRoot.querySelector('main');
      main?.addEventListener('click', this.onClick.bind(this));
      const planningWrap = this.shadowRoot.querySelector('.planningTableWrap');
      if (planningWrap) {
        planningWrap.scrollLeft = this.planningScrollLeft || 0;
        planningWrap.scrollTop = this.planningScrollTop || 0;
        planningWrap.addEventListener('scroll', () => {
          this.planningScrollLeft = planningWrap.scrollLeft;
          this.planningScrollTop = planningWrap.scrollTop;
          this.persistInteractionContext();
        }, { passive: true });
      }
      main?.addEventListener('input', this.onInput.bind(this));
      main?.addEventListener('change', this.onChange.bind(this));
      main?.addEventListener('keydown', this.onKeyDown.bind(this));
      main?.addEventListener('focusin', this.onFocusIn.bind(this));
      main?.addEventListener('focusout', this.onFocusOut.bind(this));
      main?.addEventListener('toggle', this.onToggle.bind(this), true);
    }
    styles() { return `:host{display:block;color:#0f172a;--bg:#f7f9fc;--card:#fff;--line:#e5ebf3;--muted:#66758d;--green:#16a34a;--orange:#f59e0b;--purple:#7c3aed;--blue:#2563eb;user-select:text;-webkit-user-select:text}.energy{background:radial-gradient(circle at 50% 0%,#ffffff 0,#fbfcff 42%,#f4f7fb 100%);padding:24px 32px 38px;border-radius:30px;min-height:calc(100vh - 70px)}.top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:22px}.eyebrow{font-size:12px;letter-spacing:.16em;font-weight:800;color:#64748b}.top h1{font-size:42px;line-height:1.05;letter-spacing:-.04em;margin:8px 0 6px}.top p{margin:0;color:#6a7488;font-size:17px}.topRight{text-align:right}.releaseLine,.uxLine{font-size:11px;color:#8795ad;font-weight:700}.topPills{display:flex;gap:12px;align-items:center;justify-content:flex-end;margin:10px 0}.pill{background:#fff;border:1px solid var(--line);border-radius:999px;padding:12px 18px;font-weight:800;box-shadow:0 10px 25px rgba(15,23,42,.04)}.live{color:#0f7a3a}.quick{border:0;background:#101827;color:#fff;border-radius:16px;padding:14px 22px;font-weight:900;box-shadow:0 14px 30px rgba(15,23,42,.15)}.tabs{display:flex;gap:8px;background:rgba(255,255,255,.82);backdrop-filter:blur(16px);border:1px solid var(--line);border-radius:20px;padding:8px;margin:8px 0 22px;box-shadow:0 18px 40px rgba(15,23,42,.04)}.tab{border:0;background:transparent;border-radius:13px;padding:11px 22px;font-size:14px;font-weight:900;color:#43516a;cursor:pointer}.tab.active{background:#eef5ff;color:#0f172a;box-shadow:inset 0 0 0 1px #d6e6ff,0 8px 18px rgba(37,99,235,.05)}.summaryRow{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:18px;margin-bottom:20px}.summaryRow.four{grid-template-columns:repeat(4,minmax(0,1fr))}.metric,.panel,.heroPanel{background:linear-gradient(180deg,rgba(255,255,255,.96),rgba(255,255,255,.84));border:1px solid #e6edf7;border-radius:30px;box-shadow:0 24px 55px rgba(15,23,42,.065)}.metric{min-height:112px;padding:22px 24px;display:flex;gap:18px;align-items:center}.metric .mi{width:56px;height:56px;border-radius:50%;background:#f8fafc;display:grid;place-items:center;font-size:28px}.metric.orange .mi{background:#fff7ed;color:#ea580c}.metric.green .mi{background:#ecfdf5;color:#16a34a}.metric.purple .mi{background:#f5f3ff;color:#7c3aed}.metric.blue .mi{background:#eff6ff;color:#2563eb}.ml{font-size:13px;text-transform:none;color:#6b7890}.mv{font-size:28px;font-weight:950;letter-spacing:-.035em;margin:4px 0}.ms{font-size:13px;color:var(--muted);line-height:1.35;max-width:360px}.landing{display:grid;grid-template-columns:.96fr 1.92fr .96fr;gap:20px}.panel{padding:28px}.panel h2,.heroPanel h2{margin:0 0 8px;font-size:25px;letter-spacing:-.03em}.panel p,.heroPanel p{margin:0 0 18px;color:var(--muted);font-size:15px}.assetRow{display:flex;align-items:center;gap:14px;background:#fff;border:1px solid var(--line);border-radius:20px;padding:16px;margin:12px 0}.round{width:48px;height:48px;border-radius:16px;background:#ecfdf5;display:grid;place-items:center;font-size:23px}.grow{flex:1;min-width:0}.grow b{display:block;font-size:16px}.grow span{display:block;color:var(--muted);font-size:13px;margin-top:2px}.assetRow strong{font-size:17px}.bar{height:5px;background:#e8eef6;border-radius:10px;margin-top:10px;overflow:hidden}.bar i{display:block;height:100%;background:linear-gradient(90deg,#10b981,#22c55e)}.total{border-top:1px solid var(--line);margin-top:18px;padding-top:18px}.total span{color:var(--muted);display:block}.total b{font-size:30px}.heroPanel{padding:30px;text-align:center;position:relative;overflow:hidden;min-height:560px}.rec{max-width:560px;margin:20px auto -54px;background:#f0fdf4;border:1px solid #b7e4c7;border-radius:24px;text-align:left;padding:22px;display:grid;grid-template-columns:40px 1fr 42px;gap:16px;align-items:start;position:relative;z-index:3;box-shadow:0 20px 50px rgba(22,163,74,.13);backdrop-filter:blur(10px)}.rec small{font-weight:900;letter-spacing:.12em;color:#64748b}.rec h2{font-size:24px;color:#15803d;margin:5px 0}.rec p{margin:0;color:#516175}.recIcon{font-size:26px;color:#16a34a}.check{width:42px;height:42px;border-radius:50%;border:2px solid #86d39a;color:#16a34a;display:grid;place-items:center;font-weight:900}.recMeta{display:flex;gap:30px;margin-top:18px;border-top:1px solid #d7eedb;padding-top:14px}.recMeta span{font-size:13px;color:#6b7890}.energyScene{position:relative;height:360px;margin:0 auto;border-radius:30px;max-width:840px;background:linear-gradient(135deg,#fff7ed,#eef7ff 50%,#ecfdf5);box-shadow:0 24px 60px rgba(15,23,42,.10);overflow:hidden}.sceneTitle{position:absolute;top:34px;left:70px;text-align:left}.sceneTitle b{display:block;font-size:31px;letter-spacing:-.04em}.sceneTitle span{display:block;color:#64748b}.house{position:absolute;left:50%;top:48%;width:170px;height:105px;transform:translate(-50%,-10%);background:#f3eadb;border:10px solid #0f172a;border-radius:8px}.roof{position:absolute;left:-24px;right:-24px;top:-58px;height:72px;background:#0f172a;clip-path:polygon(50% 0,100% 100%,0 100%)}.wall i{display:inline-block;width:22px;height:25px;background:#fde68a;border-radius:3px;margin:38px 5px 0}.panels{position:absolute;top:-45px;left:32px}.panels i{display:inline-block;width:17px;height:18px;background:#1d4ed8;border:1px solid rgba(255,255,255,.4)}.car{position:absolute;right:245px;bottom:74px;width:76px;height:42px;background:#fff;border-radius:12px}.car:before,.car:after{content:"";position:absolute;bottom:-11px;width:14px;height:14px;border-radius:50%;background:#0f172a}.car:before{left:10px}.car:after{right:10px}.solarPath,.batteryPath,.gridPath{position:absolute;height:6px;border-radius:999px}.solarPath{left:205px;top:172px;width:210px;background:#f59e0b;transform:rotate(16deg)}.batteryPath{left:210px;bottom:142px;width:220px;background:#16a34a;transform:rotate(-13deg)}.gridPath{right:170px;top:203px;width:210px;background:#7c3aed}.float{position:absolute;background:rgba(255,255,255,.94);border:1px solid #e5ebf3;border-radius:18px;padding:12px 16px;text-align:left;box-shadow:0 18px 38px rgba(15,23,42,.13);z-index:2}.float span,.float small{display:block;color:#64748b;font-size:11px}.float b{display:block;font-size:20px}.float.solar{left:80px;top:110px}.float.battery{left:86px;bottom:82px}.float.grid{right:70px;top:175px}.float.export{left:105px;top:74px;border-radius:999px;color:#ea580c;font-weight:900}.chips{display:flex;gap:10px;justify-content:center;margin-top:16px}.chips span{background:#fff;border:1px solid var(--line);border-radius:999px;padding:9px 14px;font-weight:800}.bottomInsights{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:18px}.insight{background:#fff;border:1px solid var(--line);border-radius:20px;padding:18px;text-align:left}.insight span{display:block;color:#64748b}.insight b{font-size:24px;display:block;margin:4px 0}.insight small{color:var(--muted)}.empty{border:1px dashed #cbd5e1;border-radius:18px;padding:16px;margin-top:14px;background:#fff;text-align:center}.empty b{display:block}.empty span{display:block;color:var(--muted);font-size:13px;margin-top:4px}.sectionLabel{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#64748b;font-weight:900;margin:16px 0 6px}.solarOperationsPage{max-width:1600px;margin:0 auto}.solarKpis{margin-bottom:20px}.solarHomeIntelligence{display:grid;grid-template-columns:.8fr 1fr 1fr 1fr;gap:28px;align-items:center;margin-bottom:22px}.solarIntelligenceIntro{text-align:left}.r3230Illustration{height:120px;border-radius:50%;background:#eaf6ff;display:flex;align-items:center;justify-content:center;gap:26px;font-size:28px;margin-top:16px}.solarPolicySegment small,.solarDecisionArea small,.solarNextArea small{display:block;text-transform:uppercase;letter-spacing:.14em;font-size:11px;color:#64748b;font-weight:900;margin-bottom:8px}.energySegmentButtons{display:flex;flex-wrap:wrap;border:1px solid #dbe3ef;border-radius:14px;overflow:hidden;background:#f8fafc}.energySegment{border:0;background:transparent;padding:12px 18px;font-weight:900}.energySegment.selected{background:#fff}.solarDecisionArea{border-left:1px solid #e5ebf3;padding-left:24px}.solarDecisionArea h3{margin:0 0 8px}.dot{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:8px}.green{background:#22c55e}.solarNextArea{border-left:4px solid #f59e0b;padding-left:20px}.solarNextArea b,.solarDecisionArea b{font-size:20px;display:block}.solarMainGrid{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:22px}.energySectionHead{display:flex;justify-content:space-between;gap:14px;align-items:start;border-bottom:1px solid #e5ebf3;padding-bottom:14px;margin-bottom:14px}.solarLegend{display:flex;gap:14px;color:#64748b}.solarLegend i{width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:6px}.solarLegend .blue{background:#2563eb}.solarLegend .green{background:#22c55e}.solarLegend .orange{background:#f59e0b}.solarLegend .gray{background:#cbd5e1}.solarLoadCard{display:grid;grid-template-columns:1.5fr 1fr 1fr 1fr;gap:12px;align-items:center;border:1px solid #e5ebf3;background:#fff;border-radius:18px;padding:14px;margin:10px 0}.solarLoadCard b{display:block}.solarLoadCard span{display:block;color:#64748b;font-size:12px}.solarSideCard{margin-bottom:22px}.solarTodayPrimary{font-size:28px;font-weight:950;color:#16a34a;margin:10px 0}.solarTodayRows>div{display:flex;justify-content:space-between;border-bottom:1px solid #e5ebf3;padding:10px 0}.advanced summary{border:1px solid #e5ebf3;border-radius:12px;padding:8px 10px;font-weight:900;cursor:pointer}.miniChart{margin-top:22px}.miniChart svg{width:100%;height:120px}.r3230ChartLabels{display:flex;justify-content:space-between;color:#64748b;font-size:12px}.r3280OutlookGrid{display:grid;grid-template-columns:1.2fr .9fr .9fr .9fr;gap:18px;align-items:start}.r3280Balance{border:1px solid #dbeafe;border-radius:20px;background:#eff6ff;padding:28px;margin:20px 0}.r3280Balance b{font-size:30px;display:block}.goalGrid{display:grid;grid-template-columns:1fr 1fr;gap:10px}.goalRow{background:#f8fafc;border:1px solid #e7eef7;border-radius:14px;padding:12px}.goalRow span{display:block;color:#64748b;font-size:12px}.goalRow b{display:block;margin-top:4px}.kv{display:flex;justify-content:space-between;border-bottom:1px solid var(--line);padding:14px 0;gap:20px}.kv span{color:var(--muted)}.kv b{text-align:right}.softBox{margin-top:18px;background:#f5f3ff;border-radius:18px;padding:18px}.softBox b,.softBox span{display:block}.flowPage{max-width:1660px;margin:0 auto}.physicalFlowHero{margin-bottom:22px}.flowHeader{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;margin-bottom:20px}.flowBadge{background:#eef5ff;border:1px solid #d6e6ff;border-radius:999px;padding:10px 14px;font-weight:900;color:#1d4ed8}.flowCanvas{display:grid;grid-template-columns:310px minmax(360px,1fr) 340px;gap:28px;align-items:stretch}.flowColumn{background:linear-gradient(180deg,#fff,#f8fafc);border:1px solid #e6edf7;border-radius:26px;padding:20px}.flowColumn h3{margin:0 0 16px;font-size:18px}.flowNode{border:1px solid #e5ebf3;background:#fff;border-radius:20px;padding:16px;margin:12px 0;display:grid;grid-template-columns:50px 1fr;gap:14px;align-items:center;box-shadow:0 14px 30px rgba(15,23,42,.04)}.flowIcon{width:50px;height:50px;border-radius:16px;display:grid;place-items:center;background:#f8fafc;font-size:24px}.flowNode span,.flowNode small{display:block;color:#64748b}.flowNode b{display:block;font-size:22px;letter-spacing:-.03em}.solarNode .flowIcon{background:#fff7ed}.batteryNode .flowIcon{background:#ecfdf5}.gridNode .flowIcon{background:#f5f3ff}.homeNode .flowIcon,.consumerNode .flowIcon,.chargerNode .flowIcon{background:#eff6ff}.flowCenter{position:relative;background:radial-gradient(circle at 50% 38%,#fff 0,#eef7ff 45%,#ecfdf5 100%);border:1px solid #e5ebf3;border-radius:30px;padding:26px;display:grid;grid-template-columns:1fr 1fr;gap:22px;align-items:center;min-height:410px}.busStack{display:grid;gap:18px}.switchboardNode,.homeBusNode{background:#fff;border:1px solid #dbe5f0;border-radius:24px;padding:22px;text-align:center;box-shadow:0 20px 45px rgba(15,23,42,.08)}.switchboardNode span,.homeBusNode span,.homeBusNode small{display:block;color:#64748b}.switchboardNode b,.homeBusNode b{display:block;font-size:25px;letter-spacing:-.035em;margin:6px 0}.homeBusNode{border-color:#bfdbfe;background:linear-gradient(180deg,#fff,#eff6ff)}.flowLines{display:grid;gap:14px}.flowLine{background:rgba(255,255,255,.9);border:1px solid #e5ebf3;border-radius:999px;padding:12px 14px;display:grid;grid-template-columns:46px 1fr auto;gap:12px;align-items:center}.flowLine i{display:block;height:7px;border-radius:999px;background:#94a3b8}.flowLine.solar i{background:#f59e0b}.flowLine.battery i{background:#16a34a}.flowLine.grid i{background:#7c3aed}.flowLine.export i{background:#ef4444}.flowLine span{color:#64748b}.flowLine b{font-size:16px}.flowDetailsGrid{display:grid;grid-template-columns:1fr 1fr 1.15fr;gap:18px}.topologyList{max-height:430px;overflow:auto;padding-right:4px}.batteryGrid,.consumerGrid,.strategyGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.batteryGrid .wide,.consumerGrid .wide,.strategyGrid .wide{grid-column:1/-1}.batteryGauge{background:linear-gradient(180deg,#ecfdf5,#fff);border:1px solid #bbf7d0;border-radius:24px;padding:22px;margin:16px 0}.batteryGauge b{display:block;font-size:48px;letter-spacing:-.06em;color:#15803d}.batteryGauge span{display:block;color:#64748b;margin-bottom:14px}.batteryChild,.propertyRow,.commandRow,.intentCard,.consumerFullCard{border:1px solid #e5ebf3;background:#fff;border-radius:18px;padding:16px;margin:12px 0;box-shadow:0 10px 24px rgba(15,23,42,.035)}.batteryChild{display:grid;grid-template-columns:1fr auto;gap:8px}.batteryChild strong{font-size:24px}.batteryChild small,.propertyRow span,.commandRow span,.consumerFullCard span,.intentCard small{display:block;color:#64748b;font-size:12px}.batteryChild .bar{grid-column:1/-1}.propertyRow,.commandRow{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center}.propertyRow small,.commandRow small{grid-column:1/-1;color:#64748b}.commandRow.disabled strong{color:#f59e0b}.commandRow.enabled strong{color:#16a34a}.commandRow.hidden{display:none}.consumerFullCard{display:block}.consumerHead{display:flex;justify-content:space-between;gap:14px;align-items:start}.consumerHead strong{font-size:22px}.consumerFlags{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0}.consumerFlags span{border-radius:999px;padding:7px 10px;font-size:12px;font-weight:900;border:1px solid #e5ebf3;background:#f8fafc}.consumerFlags span.on{background:#ecfdf5;color:#15803d;border-color:#bbf7d0}.consumerFlags span.off{background:#f8fafc;color:#64748b}.intentCard{display:grid;grid-template-columns:1fr minmax(190px,.8fr);gap:16px}.intentCard h3{margin:4px 0 8px;font-size:21px}.intentCard p{margin:0;color:#64748b}.intentFacts .kv{padding:8px 0}.meteringGrid,.intelligenceGrid,.valueGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.meteringGrid .wide,.intelligenceGrid .wide,.valueGrid .wide{grid-column:1/-1}.meteringPage,.intelligencePage,.valuePage{max-width:1660px;margin:0 auto}.meteringRow,.activityRow{border:1px solid #e5ebf3;background:#fff;border-radius:18px;padding:16px;margin:12px 0;display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;box-shadow:0 10px 24px rgba(15,23,42,.035)}.meteringRow span,.meteringRow small,.activityRow span{display:block;color:#64748b;font-size:12px}.meteringRow small{grid-column:1/-1}.decisionDump{white-space:pre-wrap;background:#0f172a;color:#e2e8f0;border-radius:18px;padding:18px;overflow:auto;max-height:420px;font-size:12px;line-height:1.5}.strategiesPage,.batteryPage,.consumersPage{max-width:1660px;margin:0 auto}.cleanPlaceholder{max-width:720px}.backendWarning{margin:0 0 10px;padding:10px 12px;border:1px solid #f4c7b3;background:#fff7f2;border-radius:10px;color:#5f2d1f;display:grid;gap:3px}.backendWarning b{font-size:12px;font-weight:650}.backendWarning span{font-size:11px}.hiRuntimeFooter{display:flex;flex-wrap:wrap;gap:7px;align-items:center;border-top:1px solid #dbe5f0;margin:18px 6px 0;padding:10px 0 0;color:#5f6f86;font-size:11.5px;font-weight:650;line-height:1.35}.hiRuntimeFooter b{color:#0f172a}:host{color:var(--primary-text-color,#1f2937);--bg:var(--lovelace-background,#f5f7fa);--card:var(--ha-card-background,#fff);--line:var(--divider-color,#dfe6ef);--muted:var(--secondary-text-color,#64748b);--green:#5f9f7a;--orange:#d8a15d;--purple:#8b7bb8;--blue:#6f91bd}.energy{background:var(--bg);padding:14px 16px 22px;border-radius:0;min-height:calc(100vh - 64px)}.top{margin-bottom:12px}.eyebrow{font-size:10px;letter-spacing:.14em;font-weight:600;color:var(--muted)}.top h1{font-size:26px;line-height:1.15;letter-spacing:-.015em;font-weight:600;margin:5px 0 3px}.top p{font-size:14px;color:var(--muted)}.topRight,.topPills,.releaseLine,.uxLine,.quick,.pill{display:none}.tabs{gap:4px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:4px;margin:8px 0 14px;box-shadow:none}.tab{border-radius:8px;padding:8px 14px;font-size:12px;font-weight:600;color:var(--primary-text-color,#334155)}.tab.active{background:rgba(3,169,244,.08);box-shadow:inset 0 0 0 1px rgba(3,169,244,.18);font-weight:650}.summaryRow{gap:10px;margin-bottom:10px}.metric,.panel,.heroPanel{background:var(--card);border:1px solid var(--line);border-radius:12px;box-shadow:none}.metric{min-height:74px;padding:12px 14px;gap:10px}.metric .mi{width:36px;height:36px;font-size:18px;border-radius:10px;background:#f3f6fa}.metric.orange .mi{background:#fff4e4;color:#b77935}.metric.green .mi{background:#eef7f1;color:#4f8d69}.metric.purple .mi{background:#f3f0fb;color:#7965a9}.metric.blue .mi{background:#eef5fb;color:#5b7fae}.ml{font-size:11px;color:var(--muted)}.mv{font-size:20px;font-weight:650;letter-spacing:-.015em;margin:2px 0}.ms{font-size:11.5px;line-height:1.3;color:var(--muted)}.landing{gap:10px}.panel{padding:14px}.panel h2,.heroPanel h2{font-size:18px;font-weight:600;letter-spacing:-.01em;margin:0 0 6px}.panel p,.heroPanel p{font-size:12.5px;margin:0 0 10px}.round{width:34px;height:34px;border-radius:9px;font-size:16px}.grow b{font-size:13px;font-weight:600}.grow span,.assetRow span,.propertyRow span,.commandRow span,.consumerFullCard span,.intentCard small,.meteringRow span,.meteringRow small,.activityRow span{font-size:11px}.bar{height:4px}.total{margin-top:10px;padding-top:10px}.total b{font-size:21px;font-weight:650}.heroPanel{padding:16px;min-height:0}.rec{max-width:480px;margin:12px auto -36px;padding:14px;border-radius:12px;grid-template-columns:28px 1fr 30px;gap:10px;box-shadow:none;background:#f4fbf6;border-color:#c9e7d1}.rec small{font-weight:600;font-size:9px}.rec h2{font-size:16px;font-weight:650;margin:3px 0;color:#3f7f5a}.rec p{font-size:11.5px}.recIcon{font-size:17px}.check{width:28px;height:28px}.recMeta{gap:14px;margin-top:10px;padding-top:8px}.recMeta span{font-size:10.5px}.energyScene{height:245px;border-radius:14px;box-shadow:none}.sceneTitle{top:22px;left:40px}.sceneTitle b{font-size:20px;font-weight:600}.sceneTitle span{font-size:11px}.house{width:126px;height:78px;border-width:7px}.roof{top:-43px;height:54px}.wall i{width:15px;height:17px;margin:29px 3px 0}.panels{top:-33px;left:24px}.panels i{width:12px;height:13px}.car{right:170px;bottom:52px;transform:scale(.72);transform-origin:right bottom}.solarPath,.batteryPath,.gridPath{height:4px}.float{border-radius:10px;padding:8px 10px;box-shadow:none}.float b{font-size:14px;font-weight:650}.float span,.float small{font-size:9px}.chips span{padding:6px 9px;font-weight:600;font-size:11px}.bottomInsights{gap:8px;margin-top:8px}.insight{border-radius:10px;padding:10px}.insight b{font-size:17px;font-weight:650}.sectionLabel{font-size:10px;font-weight:650;margin:10px 0 4px}.solarOperationsPage,.flowPage,.meteringPage,.intelligencePage,.valuePage,.strategiesPage,.batteryPage,.consumersPage{max-width:1180px}.solarKpis{margin-bottom:10px}.solarHomeIntelligence{gap:12px;margin-bottom:12px}.r3230Illustration{height:82px;margin-top:8px;font-size:20px}.solarPolicySegment small,.solarDecisionArea small,.solarNextArea small{font-weight:650;font-size:9px;margin-bottom:4px}.energySegmentButtons{border-radius:9px}.energySegment{padding:8px 11px;font-weight:600;font-size:11.5px}.solarDecisionArea{padding-left:12px}.solarNextArea{padding-left:12px;border-left-width:2px}.solarNextArea b,.solarDecisionArea b{font-size:14px;font-weight:650}.solarMainGrid{grid-template-columns:minmax(0,1fr) 280px;gap:10px}.energySectionHead{padding-bottom:8px;margin-bottom:8px}.solarLegend{gap:8px;font-size:11px}.solarLoadCard{border-radius:9px;padding:9px;margin:6px 0}.solarTodayPrimary{font-size:20px;font-weight:650;margin:5px 0}.solarTodayRows>div{padding:7px 0}.advanced summary{border-radius:8px;font-weight:600}.miniChart{margin-top:12px}.r3280OutlookGrid{gap:10px}.r3280Balance{border-radius:10px;padding:18px;margin:10px 0}.r3280Balance b{font-size:22px;font-weight:650}.goalGrid{gap:6px}.goalRow{border-radius:8px;padding:8px}.kv{padding:8px 0}.kv b{font-weight:600}.softBox{margin-top:10px;border-radius:10px;padding:10px}.flowHeader{margin-bottom:10px}.flowBadge{border-radius:999px;padding:6px 9px;font-weight:600;font-size:11px}.flowCanvas{grid-template-columns:220px minmax(320px,1fr) 240px;gap:10px}.flowColumn{border-radius:12px;padding:12px}.flowColumn h3{font-size:14px;font-weight:600;margin:0 0 8px}.flowIcon{width:34px;height:34px;border-radius:9px;font-size:17px}.flowNode{grid-template-columns:34px 1fr;gap:9px}.flowNode b{font-size:15px;font-weight:650}.flowCenter{border-radius:14px;padding:14px;gap:12px;min-height:285px}.switchboardNode,.homeBusNode{border-radius:12px;padding:14px;box-shadow:none}.switchboardNode b,.homeBusNode b{font-size:16px;font-weight:650}.flowLine{padding:8px 9px;grid-template-columns:30px 1fr auto;gap:8px}.flowLine i{height:4px}.flowLine b{font-size:12.5px}.flowDetailsGrid{gap:10px}.topologyList{max-height:310px}.batteryGrid,.consumerGrid,.strategyGrid,.meteringGrid,.intelligenceGrid,.valueGrid{gap:10px}.batteryGauge{border-radius:12px;padding:12px;margin:8px 0}.batteryGauge b{font-size:32px;font-weight:650}.batteryChild strong{font-size:17px}.consumerHead strong{font-size:16px;font-weight:650}.consumerFlags{gap:5px;margin:8px 0}.consumerFlags span{padding:4px 7px;font-size:10.5px;font-weight:600}.intentCard h3{font-size:16px;font-weight:650}.decisionDump{border-radius:10px;padding:12px;font-size:11px}.hiRuntimeFooter{margin:10px 4px 0;padding:8px 0 0;font-size:10px;font-weight:500;color:var(--muted)}.energy{padding:10px 12px 18px;min-height:calc(100vh - 54px)}.top{margin-bottom:8px}.eyebrow{font-size:9px;letter-spacing:.12em;font-weight:600}.top h1{font-size:23px;line-height:1.1;font-weight:560;letter-spacing:-.012em;margin:3px 0 2px}.top p{font-size:12.5px;margin:0}.tabs{border-radius:8px;padding:3px;margin:7px 0 10px;gap:3px}.tab{border-radius:6px;padding:6px 11px;font-size:11.5px;font-weight:560}.tab.active{font-weight:600;background:rgba(3,169,244,.065);box-shadow:inset 0 0 0 1px rgba(3,169,244,.14)}.summaryRow{gap:8px;margin-bottom:8px}.metric,.panel,.heroPanel{border-radius:10px}.metric{min-height:54px;padding:8px 10px;gap:8px}.metric.green{background:var(--card)}.metric .mi{width:30px;height:30px;font-size:15px;border-radius:8px}.ml{font-size:10.5px}.mv{font-size:17px;font-weight:590;letter-spacing:-.01em;margin:1px 0}.ms{font-size:10.5px;line-height:1.22}.panel{padding:10px}.panel h2,.heroPanel h2{font-size:16px;font-weight:580;margin:0 0 4px;letter-spacing:-.005em}.panel p,.heroPanel p{font-size:11.5px;line-height:1.28;margin:0 0 7px}.round{width:28px;height:28px;border-radius:8px;font-size:14px}.grow b{font-size:12.5px;font-weight:560}.grow span,.assetRow span,.propertyRow span,.commandRow span,.consumerFullCard span,.intentCard small,.meteringRow span,.meteringRow small,.activityRow span{font-size:10.5px}.bar{height:3px;margin-top:6px}.total{margin-top:7px;padding-top:7px}.total b{font-size:18px;font-weight:590}.landing{gap:8px}.heroPanel{padding:11px}.rec{max-width:420px;margin:8px auto -28px;padding:10px;border-radius:10px;grid-template-columns:22px 1fr 24px;gap:8px}.rec small{font-size:8.5px;font-weight:560}.rec h2{font-size:14px;font-weight:590;margin:2px 0;color:#356f4f}.rec p{font-size:10.5px;line-height:1.25}.recIcon{font-size:14px}.check{width:24px;height:24px;border-width:1px}.recMeta{gap:10px;margin-top:7px;padding-top:6px}.recMeta span{font-size:9.5px}.energyScene{height:205px;border-radius:10px;max-width:700px}.sceneTitle{top:15px;left:28px}.sceneTitle b{font-size:17px;font-weight:560}.sceneTitle span{font-size:10px}.house{width:104px;height:64px;border-width:6px}.roof{top:-35px;height:45px}.wall i{width:12px;height:14px;margin:24px 2px 0}.panels{top:-27px;left:20px}.panels i{width:10px;height:11px}.car{right:138px;bottom:42px;transform:scale(.62);transform-origin:right bottom}.solarPath,.batteryPath,.gridPath{height:3px}.float{border-radius:8px;padding:6px 8px}.float b{font-size:12.5px;font-weight:590}.float span,.float small{font-size:8.5px}.chips{gap:6px;margin-top:8px}.chips span{padding:4px 7px;font-weight:560;font-size:10px}.bottomInsights{gap:6px;margin-top:6px}.insight{border-radius:8px;padding:8px}.insight b{font-size:15px;font-weight:590}.sectionLabel{font-size:9px;font-weight:560;margin:6px 0 3px}.solarOperationsPage,.flowPage,.meteringPage,.intelligencePage,.valuePage,.strategiesPage,.batteryPage,.consumersPage{max-width:1560px;margin:0 auto}.solarKpis{margin-bottom:8px}.solarHomeIntelligence{gap:8px;margin-bottom:8px}.r3230Illustration{height:64px;margin-top:6px;font-size:16px}.solarPolicySegment small,.solarDecisionArea small,.solarNextArea small{font-size:8.5px;font-weight:560;margin-bottom:3px}.energySegment{padding:6px 9px;font-weight:560;font-size:10.5px}.solarDecisionArea{padding-left:8px}.solarNextArea{padding-left:8px}.solarNextArea b,.solarDecisionArea b{font-size:12.5px;font-weight:590}.solarMainGrid{grid-template-columns:minmax(0,1fr) 245px;gap:8px}.energySectionHead{padding-bottom:6px;margin-bottom:6px}.solarLegend{gap:6px;font-size:10px}.solarLoadCard{border-radius:8px;padding:7px;margin:5px 0}.solarTodayPrimary{font-size:17px;font-weight:590;margin:3px 0}.solarTodayRows>div{padding:5px 0}.advanced summary{font-weight:560}.r3280OutlookGrid{gap:8px}.r3280Balance{border-radius:8px;padding:12px;margin:7px 0}.r3280Balance b{font-size:18px;font-weight:590}.goalGrid{gap:5px}.goalRow{border-radius:8px;padding:7px}.kv{padding:6px 0}.kv b{font-weight:560}.softBox{margin-top:7px;border-radius:8px;padding:8px}.flowHeader{margin-bottom:7px}.flowBadge{padding:5px 8px;font-weight:560;font-size:10px}.flowCanvas{grid-template-columns:200px minmax(300px,1fr) 220px;gap:8px}.flowColumn{border-radius:10px;padding:9px}.flowColumn h3{font-size:12.5px;font-weight:560;margin:0 0 6px}.flowIcon{width:28px;height:28px;border-radius:8px;font-size:14px}.flowNode{grid-template-columns:28px 1fr;gap:7px}.flowNode b{font-size:13px;font-weight:580}.flowCenter{border-radius:10px;padding:10px;gap:8px;min-height:230px}.switchboardNode,.homeBusNode{border-radius:9px;padding:10px}.switchboardNode b,.homeBusNode b{font-size:14px;font-weight:580}.flowLine{padding:6px 7px;grid-template-columns:26px 1fr auto;gap:6px}.flowLine i{height:3px}.flowLine b{font-size:11px;font-weight:560}.flowDetailsGrid{gap:8px}.topologyList{max-height:260px}.batteryGrid,.consumerGrid,.strategyGrid,.meteringGrid,.intelligenceGrid,.valueGrid{gap:8px}.batteryGauge{border-radius:10px;padding:10px;margin:6px 0}.batteryGauge b{font-size:26px;font-weight:590}.batteryChild strong{font-size:15px}.consumerHead strong{font-size:14px;font-weight:580}.consumerFlags{gap:4px;margin:6px 0}.consumerFlags span{padding:3px 6px;font-size:9.5px;font-weight:560}.intentCard{grid-template-columns:1fr minmax(160px,.75fr);gap:10px}.intentCard h3{font-size:14px;font-weight:590;margin:2px 0 5px}.decisionDump{border-radius:8px;padding:9px;font-size:10px;line-height:1.35;max-height:330px}.hiRuntimeFooter{margin:7px 3px 0;padding:6px 0 0;font-size:9.5px;font-weight:450}.dot.green,.solarLegend .green{background:#5f9f7a}:host{
        --hi-space-page-x:14px;
        --hi-space-page-y:10px;
        --hi-gap:8px;
        --hi-radius:10px;
        --hi-radius-sm:8px;
        --hi-card-pad:10px;
        --hi-kpi-h:62px;
        --hi-icon:30px;
        --hi-title:24px;
        --hi-section-title:16px;
        --hi-kpi:18px;
        --hi-body:12px;
        --hi-meta:10.5px;
        --hi-w-strong:560;
        --hi-w-title:570;
        --hi-accent-ok:#eaf6ef;
        --hi-accent-ok-text:#256a42;
      }.energy{padding:var(--hi-space-page-y) var(--hi-space-page-x) 16px;background:var(--bg);border-radius:0}.top{margin:0 0 8px}.eyebrow{font-size:9px;line-height:1.2;font-weight:600;letter-spacing:.13em;color:var(--muted)}.top h1{font-size:var(--hi-title);line-height:1.08;font-weight:var(--hi-w-title);letter-spacing:-.015em;margin:4px 0 2px}.top p{font-size:12.5px;line-height:1.25;margin:0;color:var(--muted)}.tabs{height:42px;min-height:42px;box-sizing:border-box;align-items:center;padding:3px;margin:8px 0 10px;border-radius:var(--hi-radius);gap:3px;box-shadow:none}.tab{height:32px;min-height:32px;box-sizing:border-box;display:inline-flex;align-items:center;justify-content:center;padding:0 12px;border-radius:var(--hi-radius-sm);font-size:11.5px;line-height:1;font-weight:560;letter-spacing:0}.tab.active{font-weight:590;background:rgba(3,169,244,.065);box-shadow:inset 0 0 0 1px rgba(3,169,244,.14)}.summaryRow,.summaryRow.four{display:grid;gap:var(--hi-gap);margin:0 0 10px;align-items:start}.summaryRow{grid-template-columns:repeat(5,minmax(0,1fr))}.summaryRow.four{grid-template-columns:repeat(4,minmax(0,1fr))}.metric{height:var(--hi-kpi-h);min-height:var(--hi-kpi-h);max-height:var(--hi-kpi-h);box-sizing:border-box;padding:8px 10px;gap:8px;align-items:center;overflow:hidden;border-radius:var(--hi-radius);background:var(--card);box-shadow:none}.metric.green,.metric.orange,.metric.purple,.metric.blue{background:var(--card)}.green:not(.dot):not(i):not(.solarLegend *){background:var(--card)}.metric .mi{width:var(--hi-icon);height:var(--hi-icon);min-width:var(--hi-icon);border-radius:8px;font-size:14px}.metric.green .mi{background:var(--hi-accent-ok);color:var(--hi-accent-ok-text)}.metric.orange .mi{background:#fff7ed;color:#b77935}.metric.purple .mi{background:#f5f3ff;color:#6f5aa7}.metric.blue .mi{background:#eef5fb;color:#5b7fae}.metric>div:not(.mi){min-width:0}.ml{font-size:var(--hi-meta);line-height:1.15;font-weight:450;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.mv{font-size:var(--hi-kpi);line-height:1.08;font-weight:570;letter-spacing:-.01em;margin:1px 0;color:var(--primary-text-color,#111827);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.ms{font-size:var(--hi-meta);line-height:1.18;font-weight:400;color:var(--muted);display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}.panel,.heroPanel{border-radius:var(--hi-radius);padding:var(--hi-card-pad);box-shadow:none}.panel h2,.heroPanel h2{font-size:var(--hi-section-title);line-height:1.15;font-weight:var(--hi-w-title);letter-spacing:-.005em;margin:0 0 5px}.panel p,.heroPanel p{font-size:var(--hi-body);line-height:1.28;margin:0 0 8px;color:var(--muted)}.landing,.batteryGrid,.consumerGrid,.strategyGrid,.meteringGrid,.intelligenceGrid,.valueGrid,.flowDetailsGrid,.r3280OutlookGrid{gap:var(--hi-gap)}.solarKpis{margin-bottom:10px}.solarMainGrid,.solarHomeIntelligence{gap:var(--hi-gap);margin-bottom:10px}.solarOperationsPage,.flowPage,.meteringPage,.intelligencePage,.valuePage,.strategiesPage,.batteryPage,.consumersPage{max-width:1500px;margin:0 auto}.heroPanel{min-height:0}.rec{margin:8px auto -24px;max-width:430px;padding:10px;border-radius:var(--hi-radius);grid-template-columns:22px 1fr 24px;gap:8px;box-shadow:none;background:#f3faf5;border-color:#cbe8d4}.rec h2{font-size:14px;line-height:1.15;font-weight:570;margin:2px 0;color:var(--hi-accent-ok-text);white-space:normal}.rec p{font-size:10.5px;line-height:1.22;margin:0}.rec small{font-size:8.5px;font-weight:560;letter-spacing:.11em}.check{width:24px;height:24px}.energyScene{height:190px;max-width:660px;border-radius:var(--hi-radius);box-shadow:none}.bottomInsights{gap:var(--hi-gap);margin-top:8px}.insight{padding:8px;border-radius:var(--hi-radius-sm)}.insight b{font-size:15px;font-weight:560}.round,.flowIcon{width:28px;height:28px;min-width:28px;border-radius:8px;font-size:13px}.grow b,.flowNode b,.consumerHead strong,.intentCard h3{font-size:12.5px;line-height:1.2;font-weight:560}.total{margin-top:7px;padding-top:7px}.total b{font-size:17px;font-weight:560}.kv{padding:5px 0}.sectionLabel{font-size:9px;line-height:1.15;font-weight:560;margin:6px 0 3px;letter-spacing:.11em}.flowCanvas{gap:var(--hi-gap)}.flowColumn{padding:8px;border-radius:var(--hi-radius)}.flowCenter{min-height:220px;padding:10px;border-radius:var(--hi-radius);gap:var(--hi-gap)}.switchboardNode,.homeBusNode{padding:10px;border-radius:var(--hi-radius-sm)}.switchboardNode b,.homeBusNode b{font-size:13px;font-weight:560}.flowLine{padding:6px 7px}.batteryGauge{padding:10px;margin:6px 0;border-radius:var(--hi-radius)}.batteryGauge b{font-size:24px;font-weight:560}.consumerFlags span{padding:3px 6px;font-size:9.5px;font-weight:520}.r3280Balance{padding:10px;border-radius:var(--hi-radius)}.r3280Balance b{font-size:17px;font-weight:560}.decisionDump{padding:9px;border-radius:var(--hi-radius-sm);font-size:10px;line-height:1.32}.hiRuntimeFooter{margin:7px 3px 0;padding:6px 0 0;font-size:9.5px;font-weight:420;color:var(--muted)}.hiRuntimeFooter b{font-weight:560}.backendWarning{display:none}.hiRuntimeFooter.runtimeTrusted .runtimeStatus{color:#15803d;font-weight:650}.hiRuntimeFooter.runtimeNotTrusted .runtimeStatus{color:#b45309;font-weight:700}.hiRuntimeFooter.runtimeNotTrusted{border-top:1px solid rgba(180,83,9,.18);color:var(--muted)}.qs{display:inline-flex;align-items:center;justify-content:center;min-width:34px;max-width:88px;height:16px;padding:0 6px;border-radius:999px;font-size:8.5px;line-height:1;font-weight:560;letter-spacing:.015em;white-space:nowrap;text-transform:uppercase;box-sizing:border-box;background:#eef2f7;color:#667085;border:1px solid rgba(15,23,42,.06)}.qs.ok{background:#eef8f2;color:#2f6d4b;border-color:#d7eadf}.qs.warn{background:#fff7e6;color:#946200;border-color:#f2d79b}.qs.fail{background:#fff1f1;color:#9b1c1c;border-color:#f3c2c2}.qs.missing,.qs.not-measured,.qs.unknown{background:#f4f6f8;color:#7a8493;border-color:#e6e9ee}.metric{position:relative}.metric>.qs{position:absolute;right:7px;top:6px;opacity:.72}.propertyRow{grid-template-columns:minmax(0,1fr) auto auto;align-items:center}.propertyRow strong{min-width:78px;text-align:right}.propertyControl{min-width:130px;max-width:190px;border:1px solid var(--line);border-radius:8px;background:#fff;padding:5px 7px;font:inherit;font-size:11px}.propertyControl:disabled{background:#f8fafc;color:#94a3b8}.propertyRow>.qs{margin-left:6px}.propertyRow.warn,.meteringRow.warn{border-color:#f2d79b}.propertyRow.fail,.meteringRow.fail{border-color:#f3c2c2}.propertyRow.missing,.propertyRow.not-measured{opacity:.82}.empty b{font-weight:560}.empty span{font-size:10.5px;color:var(--muted)}.solarIntelligencePanel{display:grid;grid-template-columns:1.1fr 1.2fr 1.2fr 1.3fr;gap:var(--hi-gap);align-items:center}.solarIntro h2,.flexibleLoadsPanel h2{margin-bottom:6px}.solarIntro p{max-width:260px}.solarControls{display:grid;gap:8px}.controlBlock small,.solarStatus small,.solarRecommendation small{display:block;text-transform:uppercase;letter-spacing:.12em;font-size:9px;color:var(--muted);font-weight:650;margin-bottom:4px}.controlBlock>span,.solarStatus>span,.solarRecommendation>span{display:block;font-size:11px;line-height:1.3;color:var(--muted)}.hiSegmented{display:inline-flex;align-items:center;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#f8fafc;min-height:30px}.hiSegment{appearance:none;border:0;border-right:1px solid var(--line);background:transparent;padding:7px 13px;font:inherit;font-size:11px;font-weight:590;color:#334155;cursor:pointer;line-height:1}.hiSegment:last-child{border-right:0}.hiSegment.active{background:#eef6ff;color:#0f172a;box-shadow:inset 0 0 0 1px rgba(37,99,235,.08)}.hiSegment:disabled{cursor:not-allowed;color:#94a3b8}.execState{border:1px solid var(--line);background:#f8fafc;border-radius:10px;padding:8px 12px;font-size:11.5px;font-weight:590;color:#64748b}.solarStatus{border-left:1px solid var(--line);padding-left:16px}.solarStatus h3{font-size:13px;line-height:1.25;font-weight:600;margin:0 0 5px}.solarStatus b{display:block;font-size:13px;font-weight:600;margin-bottom:3px}.solarRecommendation{border-left:3px solid #f59e0b;padding-left:16px}.solarRecommendation h3{font-size:15px;line-height:1.25;font-weight:610;margin:0 0 5px;max-width:300px}.sortControl{display:flex;align-items:center;gap:8px}.sortControl>span{font-size:10.5px;color:var(--muted);font-weight:560}.flexLoadList{display:grid;gap:8px}.flexLoadCard{border:1px solid var(--line);border-radius:var(--hi-radius-sm);background:#fff;padding:10px 12px}.flexLoadCard.recommended{border-color:#c8d6ea;background:#fcfdff}.loadMain{display:grid;grid-template-columns:1.4fr .85fr .85fr 1.1fr;gap:10px;align-items:center}.loadMain h3{font-size:12px;line-height:1.2;margin:0 0 2px;font-weight:620}.loadMain p,.loadMain span{font-size:10.5px;line-height:1.25;color:var(--muted);margin:0}.loadMain b{font-size:12px;line-height:1.2;font-weight:610}.loadRecommendation b{display:block}.loadEnergy{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:8px;padding-top:8px;border-top:1px solid var(--line)}.loadEnergy>div{background:#f8fafc;border:1px solid #edf2f7;border-radius:9px;padding:7px 9px}.loadEnergy span{display:block;font-size:10px;line-height:1.2;color:var(--muted);margin-bottom:3px}.loadEnergy b{font-size:11.5px;font-weight:610;line-height:1.2}.priorityChip{display:inline-flex;align-items:center;border:1px solid #cfe7d6;background:#f0fbf4;color:#166534;border-radius:999px;padding:4px 9px;font-size:11px;font-weight:650;line-height:1}.loadReason{margin-top:7px;color:#64748b;font-size:10.5px;line-height:1.3}.loadReason span{display:inline-block;background:#fff7ed;border:1px solid #fed7aa;border-radius:999px;padding:4px 8px;color:#9a3412}.editGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:8px;padding-top:8px;border-top:1px solid var(--line)}.editField{display:grid;grid-template-columns:1fr 80px auto;gap:6px;align-items:center;background:#f8fafc;border:1px solid #edf2f7;border-radius:9px;padding:6px 8px}.editField span,.editField em{font-size:10px;color:var(--muted);font-style:normal}.editField input{width:100%;box-sizing:border-box;border:1px solid var(--line);border-radius:7px;background:#fff;padding:5px 6px;font:inherit;font-size:11px}.editField input:disabled{background:#f1f5f9;color:#94a3b8}.loadActions{display:flex;align-items:center;gap:7px;margin-top:8px}.loadActions>span{font-size:10px;color:var(--muted);margin-right:4px}.hiAction{appearance:none;border:1px solid var(--line);background:#fff;color:#0f172a;border-radius:9px;padding:6px 13px;font:inherit;font-size:11px;font-weight:590;line-height:1}.hiAction.enabled{border-color:#b7d6c2;background:#f0fbf4;color:#166534;cursor:pointer}.hiAction.disabled{background:#f8fafc;color:#94a3b8;cursor:not-allowed}.hiDetails{margin-top:8px}.hiDetails summary{list-style:none;border:1px solid var(--line);border-radius:9px;padding:7px 10px;font-size:11px;font-weight:610;cursor:pointer;background:#fff}.hiDetails summary::-webkit-details-marker{display:none}.hiDetails summary:before{content:"▸";display:inline-block;margin-right:6px;font-size:10px}.hiDetails[open] summary:before{content:"▾"}.hiDetails .softBox{margin-top:8px}.softBox .kv{display:flex;justify-content:space-between;gap:12px}.softBox .kv span{font-size:10.5px;color:var(--muted)}.softBox .kv b{font-size:10.5px;font-weight:600;text-align:right}.rec{width:100%;max-width:none;box-sizing:border-box;margin:10px 0 14px;position:relative;z-index:1;box-shadow:none;align-self:stretch}.heroPanel>.rec,.panel>.rec,.wide>.rec{margin:10px 0 14px}.recMeta{flex-wrap:wrap}.heroPanel .energyScene{margin-top:8px}.strategyGrid .wide .rec,.intelligenceGrid .wide .rec{margin:10px 0 16px}.solarV3445 .solarIntelligencePanel{display:grid;grid-template-columns:minmax(250px,.9fr) minmax(250px,1fr) minmax(280px,1.05fr) minmax(300px,1.15fr);gap:10px;align-items:center}.solarV3445 .hiSegmented,.solarV3445 .hiAction,.solarV3445 .editField input,.solarV3445 .hiDetails summary{}.solarV3445 .loadMain{display:grid;grid-template-columns:minmax(220px,1.3fr) minmax(150px,.75fr) minmax(170px,.75fr) minmax(260px,1.15fr);gap:14px;align-items:center}.solarV3445 .loadMain>div{display:flex;flex-direction:column;gap:3px;min-width:0}.solarV3445 .loadMain b{display:block;white-space:normal}.solarV3445 .loadMain span,.solarV3445 .loadMain p{display:block;white-space:normal}.solarV3445 .editGrid{grid-template-columns:repeat(3,minmax(170px,1fr))}.solarV3445 .loadEnergy{grid-template-columns:repeat(4,minmax(120px,1fr))}.solarV3445 .solarMainGrid{align-items:start}.solarV3445 .solarSideCard{margin-bottom:10px}@media(max-width:1100px){.solarV3445 .solarIntelligencePanel,.solarV3445 .loadMain{grid-template-columns:1fr}.solarV3445 .editGrid,.solarV3445 .loadEnergy{grid-template-columns:1fr}}.solarV3457 .solarIntelligencePanel{grid-template-columns:1.15fr 1.55fr 1.2fr;align-items:stretch}.solarV3457 .solarControls{align-self:center}.solarV3457 .solarControls .controlBlock{display:grid;grid-template-columns:92px minmax(220px,1fr);align-items:center;gap:8px 12px;margin:0 0 8px}.solarV3457 .solarControls .controlBlock small{grid-column:1;margin:0}.solarV3457 .solarControls .controlBlock .hiSegmented,.solarV3457 .solarControls .controlBlock .execState{grid-column:2}.solarV3457 .solarControls .controlBlock span{grid-column:2}.solarV3457 .solarStatus{border-left:0;padding-left:0;display:grid;grid-template-columns:92px minmax(220px,1fr);align-items:start;gap:4px 12px;margin-top:0}.solarV3457 .solarStatus small{grid-column:1;margin-top:2px}.solarV3457 .solarStatus h3,.solarV3457 .solarStatus b,.solarV3457 .solarStatus span{grid-column:2}.solarV3457 .solarRecommendation{border-left:3px solid #f59e0b;padding-left:16px;align-self:stretch}.solarV3457 .flexLoadCard{padding:0;overflow:hidden}.solarV3457 .loadSummaryGrid{display:grid;grid-template-columns:1.45fr .85fr 1fr .9fr .9fr .95fr;gap:10px;align-items:center;padding:10px 12px;border-bottom:1px solid var(--line)}.solarV3457 .loadIdentity{display:flex;align-items:center;gap:10px;min-width:0}.solarV3457 .loadIcon{width:32px;height:32px;border-radius:10px;background:#ecfdf5;display:grid;place-items:center;font-size:15px}.solarV3457 .loadIdentity h3{font-size:12px;font-weight:620;margin:0 0 2px;line-height:1.2}.solarV3457 .loadIdentity p{font-size:10.5px;color:var(--muted);margin:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.solarV3457 .loadFact span{display:block;font-size:10px;color:var(--muted);line-height:1.2;margin-bottom:3px}.solarV3457 .loadFact b{font-size:12px;font-weight:620;line-height:1.2}.stateChip{display:inline-flex;align-items:center;border-radius:999px;background:#eef6ff;color:#1d4ed8;padding:4px 9px;font-size:10.5px;font-weight:650}.solarV3457 .loadEditCommandRow{display:grid;grid-template-columns:1.35fr auto;gap:14px;align-items:end;padding:10px 12px}.sliderField{display:block}.sliderField>div{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}.sliderField span,.selectField span{display:block;font-size:10.5px;color:var(--muted);font-weight:560}.sliderField b{font-size:12px;font-weight:620}.sliderField input[type=range]{width:100%;accent-color:#2563eb}.selectField select{min-width:190px;width:100%;border:1px solid var(--line);border-radius:9px;background:#fff;padding:7px 10px;font:inherit;font-size:11px;color:#0f172a}.detailsButtonSlot{min-width:120px}.detailsButtonSlot .hiDetails{margin-top:0}.detailsButtonSlot .hiDetails summary{padding:8px 12px;text-align:center}.solarV3457 .hiDetails[open]{grid-column:1 / -1;margin-top:8px}.solarV3457 .hiDetails[open] .softBox{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;background:#f8fafc}.strategySettingsRow{margin-top:10px;border:1px solid var(--line);border-radius:var(--hi-radius-sm);background:#fff;padding:10px 12px;display:grid;grid-template-columns:1.25fr 3fr;gap:14px;align-items:center}.strategySettingsIntro b{display:block;font-size:12px;font-weight:620;margin-bottom:3px}.strategySettingsIntro span,.noStrategySettings{font-size:10.5px;color:var(--muted)}.strategySettingsControls{display:grid;grid-template-columns:repeat(6,minmax(90px,1fr));gap:8px;align-items:end}.strategySettingsControls .editField{grid-template-columns:1fr;background:#f8fafc}.strategySettingsControls .selectField select{min-width:0}.strategySettingsControls .editField em{display:none}.solarV3457 .solarIntelligencePanel{
        grid-template-columns:minmax(280px,1.05fr) minmax(340px,1.4fr) minmax(320px,1.05fr);
        grid-template-areas:"intro controls rec" "intro status rec";
        gap:12px 18px;
        align-items:stretch;
        padding:14px 16px;
      }.solarV3457 .solarIntro{grid-area:intro;align-self:stretch;display:grid;grid-template-rows:auto auto 1fr;align-content:start;gap:6px;border-right:1px solid var(--line);padding-right:16px}.solarV3457 .solarIntro h2{font-size:15px;margin:0;font-weight:640;line-height:1.2}.solarV3457 .solarIntro p{font-size:11.5px;line-height:1.35;max-width:260px;margin:0;color:var(--muted)}.solarV3457 .solarIntro .r3230Illustration{height:92px;margin-top:6px;max-width:320px;align-self:end}.solarV3457 .solarControls{grid-area:controls;align-self:start;display:grid;gap:8px;padding-top:2px}.solarV3457 .solarControls .controlBlock{grid-template-columns:82px minmax(220px,1fr);gap:6px 10px;margin:0;align-items:center}.solarV3457 .solarControls .controlBlock small{font-size:9px;letter-spacing:.13em}.solarV3457 .solarControls .controlBlock>span{font-size:10.5px;line-height:1.25}.solarV3457 .solarControls .hiSegmented{min-height:28px;border-radius:9px}.solarV3457 .solarControls .hiSegment{padding:6px 14px;font-size:10.5px}.solarV3457 .solarControls .execState{padding:7px 11px;border-radius:9px;font-size:11px}.solarV3457 .solarStatus{grid-area:status;border-left:0;padding-left:0;display:grid;grid-template-columns:82px minmax(220px,1fr);gap:4px 10px;align-self:start;margin-top:0}.solarV3457 .solarStatus small{grid-column:1;font-size:9px;letter-spacing:.13em;margin:2px 0 0;color:var(--muted)}.solarV3457 .solarStatus h3{grid-column:2;font-size:12px;line-height:1.25;margin:0 0 3px;font-weight:620}.solarV3457 .solarStatus b{grid-column:2;font-size:12px;line-height:1.2;margin:0 0 2px;font-weight:620}.solarV3457 .solarStatus span:not(.dot){grid-column:2;font-size:10.5px;line-height:1.32;color:var(--muted);max-width:330px}.solarV3457 .solarRecommendation{grid-area:rec;align-self:stretch;border-left:3px solid #f59e0b;border-top:1px solid #fde6bd;border-right:1px solid #fde6bd;border-bottom:1px solid #fde6bd;border-radius:0 10px 10px 0;padding:12px 14px;background:#fffdf8;display:grid;align-content:start;gap:5px;min-height:0}.solarV3457 .solarRecommendation small{font-size:9px;letter-spacing:.13em;margin:0;color:var(--muted)}.solarV3457 .solarRecommendation h3{font-size:15px;margin:0 0 2px;line-height:1.22;font-weight:640;max-width:none}.solarV3457 .solarRecommendation span{font-size:10.5px;line-height:1.25;color:#475569}.solarV3457 .solarRecommendation .hiDetails{margin-top:5px}.solarV3457 .flexibleLoadsPanel{padding:14px}.solarV3457 .energySectionHead{margin-bottom:10px;padding-bottom:8px;border-bottom:1px solid var(--line)}.solarV3457 .flexLoadList{gap:8px}.solarV3457 .flexLoadCard{border-radius:11px;background:#fff;border-color:#dbe3ee;box-shadow:0 1px 0 rgba(15,23,42,.02)}.solarV3457 .loadSummaryGrid{grid-template-columns:1.55fr .78fr 1.05fr .95fr .98fr;gap:10px;padding:9px 11px;min-height:44px}.solarV3457 .loadIdentity{gap:9px}.solarV3457 .loadIcon{width:30px;height:30px;border-radius:9px}.solarV3457 .loadIdentity h3{font-size:11.5px;font-weight:640}.solarV3457 .loadIdentity p{font-size:10px}.solarV3457 .loadFact span{font-size:9.5px;margin-bottom:2px}.solarV3457 .loadFact b{display:inline-flex;align-items:center;width:auto;max-width:max-content;font-size:11.5px}.solarV3457 .priorityChip{padding:3px 10px;min-width:24px;justify-content:center;font-size:10.5px;background:#eefcf3;border-color:#cdebd7;color:#15803d}.solarV3457 .stateChip{display:inline-flex;width:auto;max-width:max-content;padding:3px 10px;font-size:10px;background:#eef6ff;color:#1d4ed8;border:1px solid #dbeafe}.solarV3457 .loadEditCommandRow{grid-template-columns:minmax(270px,1.25fr) minmax(230px,.85fr) minmax(180px,auto) minmax(118px,auto);gap:12px;padding:9px 11px;align-items:end}.solarV3457 .sliderField>div{margin-bottom:4px}.solarV3457 .sliderField span,.solarV3457 .selectField span{font-size:10px}.solarV3457 .sliderField b{font-size:11.5px}.solarV3457 .sliderField input[type=range]{height:18px}.solarV3457 .selectField select{min-height:30px;padding:6px 9px;border-radius:9px;font-size:11px}.solarV3457 .loadActions{margin:0;gap:7px;align-items:center}.solarV3457 .loadActions>span{font-size:10px;color:var(--muted)}.solarV3457 .loadActions .hiAction{padding:7px 13px;border-radius:9px;min-width:54px;text-align:center}.solarV3457 .detailsButtonSlot{min-width:110px}.solarV3457 .detailsButtonSlot .hiDetails summary{padding:8px 11px;border-radius:9px;background:#fff}.solarV3457 .loadEditCommandRow>.hiDetails[open],.solarV3457 .detailsButtonSlot .hiDetails[open]{grid-column:1 / -1;width:100%}.solarV3457 .detailsButtonSlot .hiDetails[open] .softBox{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;background:#f8fafc;border-color:#e2e8f0}.solarV3457 .strategySettingsRow{margin-top:10px;border-radius:11px;padding:10px 12px;background:#fff;grid-template-columns:1.15fr 3fr;gap:12px}.solarV3457 .strategySettingsIntro b{font-size:12px}.solarV3457 .strategySettingsIntro span,.solarV3457 .noStrategySettings{font-size:10.5px;line-height:1.3}.solarV3457 .noStrategySettings{display:inline-flex;align-items:center;min-height:30px;background:#f8fafc;border:1px solid var(--line);border-radius:9px;padding:0 10px;color:var(--muted)}.solarV3457 .strategySettingsControls{grid-template-columns:repeat(4,minmax(120px,1fr)) auto;gap:8px}@media(max-width:1100px){.solarV3457 .solarIntelligencePanel{grid-template-columns:1fr}.solarV3457 .loadSummaryGrid,.solarV3457 .loadEditCommandRow,.strategySettingsRow,.strategySettingsControls{grid-template-columns:1fr}}.solarDecisionUx .summaryRow.four{grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.solarDecisionUx .metric{min-height:76px;border-radius:12px;padding:13px 16px;gap:12px;box-shadow:0 6px 18px rgba(15,23,42,.035)}.solarDecisionUx .metric .mi{width:44px;height:44px;border-radius:15px;font-size:22px}.solarDecisionUx .metric .mv{font-size:20px}.solarDecisionUx .metric .ml,.solarDecisionUx .metric .ms{font-size:11px}.solarDecisionUx .panel{border-radius:13px;box-shadow:0 8px 22px rgba(15,23,42,.035)}.solarDecisionUx .solarMainGrid{grid-template-columns:minmax(0,1fr) 260px;gap:14px}.solarDecisionUx .solarIntelligencePanel{grid-template-columns:1.1fr 1.1fr .9fr 1.45fr;gap:16px;padding:16px;border-radius:13px}.solarDecisionUx .solarIntro{border-right:1px solid var(--line)}.solarDecisionUx .solarIntro .r3230Illustration{height:116px;max-width:300px;background:radial-gradient(ellipse at center,#eaf7ff 0,#edf8ff 58%,transparent 60%)}.solarDecisionUx .solarRecommendation{background:linear-gradient(180deg,#f8fbff,#fff);border:1px solid #dbeafe;border-left:0;border-radius:12px;padding:14px 16px}.solarDecisionUx .solarRecommendation h3{text-transform:none;font-size:14px}.solarDecisionUx .solarRecommendation .recSplit{display:grid;grid-template-columns:1fr 1fr;gap:12px;border-top:1px solid #e5ebf3;margin-top:8px;padding-top:9px}.solarDecisionUx .solarRecommendation .recSplit b{display:block;font-size:15px}.solarDecisionUx .solarRecommendation .recSplit span{font-size:10.5px;color:var(--muted)}.solarDecisionUx .decisionLoadsPanel{padding:16px}.solarDecisionUx .energySectionHead{border-bottom:0;margin-bottom:8px;padding-bottom:0}.solarDecisionUx .energySectionHead h2{font-size:16px}.solarDecisionUx .energySectionHead p{font-size:11.5px;margin-top:2px}.solarDecisionUx .sortControl{gap:8px}.solarDecisionUx .insightButton,.solarDecisionUx .sideLink{border:1px solid #dbeafe;background:#fff;color:#2563eb;border-radius:9px;padding:8px 12px;font-weight:700;font-size:11px}.solarDecisionUx .flexLoadList{gap:9px}.solarDecisionUx .decisionLoadCard{border:1px solid #e1e8f2;border-radius:13px;background:#fff;overflow:hidden;box-shadow:0 2px 8px rgba(15,23,42,.025)}.solarDecisionUx .decisionMainRow{display:grid;grid-template-columns:1.55fr .95fr .76fr .76fr .72fr 1fr .95fr;gap:12px;align-items:start;padding:12px 14px;border-bottom:1px solid #edf2f7}.solarDecisionUx .decisionIdentity{display:grid;grid-template-columns:42px minmax(0,1fr);gap:11px;align-items:center}.solarDecisionUx .decisionIdentity .loadIcon{width:42px;height:42px;border-radius:50%;background:#ecfdf5;color:#15803d}.solarDecisionUx .decisionLoadCard.wait .loadIcon{background:#fff7ed;color:#ea580c}.solarDecisionUx .decisionLoadCard.warn .loadIcon{background:#f5f3ff;color:#7c3aed}.solarDecisionUx .decisionLoadCard.info .loadIcon{background:#eef6ff;color:#2563eb}.solarDecisionUx .decisionIdentity h3{font-size:13px;font-weight:760;margin:0}.solarDecisionUx .decisionIdentity p{font-size:11px;color:#475569;margin:2px 0 5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.solarDecisionUx .connectionPill{display:inline-flex;border-radius:999px;padding:3px 8px;font-size:10px;font-weight:750;background:#eef2f7;color:#475569}.solarDecisionUx .connectionPill.ok{background:#dcfce7;color:#15803d}.solarDecisionUx .connectionPill.warn{background:#fff7ed;color:#c2410c}.solarDecisionUx .connectionPill.off{background:#f1f5f9;color:#64748b}.solarDecisionUx .decisionPlan small,.solarDecisionUx .decisionMetric small,.solarDecisionUx .decisionExpected small{display:block;text-transform:none;font-size:10px;color:#64748b;margin-bottom:4px;font-weight:720}.solarDecisionUx .decisionPlan b,.solarDecisionUx .decisionMetric b,.solarDecisionUx .decisionExpected b{font-size:13px;line-height:1.2;color:#0f172a}.solarDecisionUx .decisionPlan span,.solarDecisionUx .decisionMetric span,.solarDecisionUx .decisionExpected span{display:block;font-size:10.5px;color:#334155;line-height:1.25;margin-top:4px}.solarDecisionUx .planningBadge,.solarDecisionUx .expectedBadge{display:inline-flex;border-radius:7px;padding:4px 8px;font-size:11px;font-weight:800}.solarDecisionUx .planningBadge.ok,.solarDecisionUx .expectedBadge.ok{background:#dcfce7;color:#15803d}.solarDecisionUx .planningBadge.wait,.solarDecisionUx .expectedBadge.wait{background:#ffedd5;color:#c2410c}.solarDecisionUx .planningBadge.warn,.solarDecisionUx .expectedBadge.warn{background:#f1f5f9;color:#475569}.solarDecisionUx .planningBadge.off,.solarDecisionUx .expectedBadge.off{background:#f1f5f9;color:#64748b}.solarDecisionUx .planningBadge.info,.solarDecisionUx .expectedBadge.info{background:#dbeafe;color:#1d4ed8}.solarDecisionUx .whyCell b{font-size:12px}.solarDecisionUx .decisionExpected b{white-space:nowrap}.solarDecisionUx .decisionControlRow{display:grid;grid-template-columns:110px minmax(260px,1fr) 140px minmax(260px,auto);gap:14px;align-items:end;padding:10px 14px 9px}.solarDecisionUx .readOnlyPriority{display:grid;gap:4px}.solarDecisionUx .readOnlyPriority span,.solarDecisionUx .automationMini span{font-size:10px;color:#64748b;font-weight:720}.solarDecisionUx .readOnlyPriority b{border:1px solid #dbeafe;background:#eff6ff;border-radius:8px;min-height:30px;display:inline-flex;align-items:center;justify-content:center;padding:0 12px;font-size:11px}.solarDecisionUx .requestedSlot{position:relative;display:grid;grid-template-columns:1fr auto;align-items:end;gap:8px}.solarDecisionUx .requestedSlot .sliderField{grid-column:1}.solarDecisionUx .requestedSlot .sliderField>div{grid-template-columns:auto auto;justify-content:start;gap:10px;margin-bottom:4px}.solarDecisionUx .requestedSlot .sliderField span{font-size:10.5px;font-weight:720;color:#475569}.solarDecisionUx .requestedSlot .sliderField b{font-size:11.5px}.solarDecisionUx .requestedSlot input[type=range]{height:22px}.solarDecisionUx .maxPowerHint{grid-column:2;font-size:10.5px;color:#0f172a;font-style:normal;padding-bottom:1px}.solarDecisionUx .automationMini{display:grid;gap:3px;border-left:1px solid #e5ebf3;padding-left:12px}.solarDecisionUx .automationMini b{width:max-content;border-radius:999px;padding:3px 8px;font-size:10.5px;background:#dcfce7;color:#15803d}.solarDecisionUx .automationMini b.off{background:#f1f5f9;color:#64748b}.solarDecisionUx .automationMini em{font-size:10px;color:#64748b;font-style:normal}.solarDecisionUx .decisionActions{display:grid;grid-template-columns:1fr 90px 78px;gap:8px;align-items:center;margin:0}.solarDecisionUx .decisionActions>span{font-size:10.5px;color:#64748b;white-space:nowrap}.solarDecisionUx .decisionActions .hiAction{min-width:0;border-radius:8px;padding:8px 11px;font-size:11px;font-weight:760}.solarDecisionUx .decisionActions .hiAction.enabled:first-of-type{background:#ecfdf5;border-color:#bbf7d0;color:#15803d}.solarDecisionUx .decisionActions .hiAction.enabled:nth-of-type(2){background:#fff1f2;border-color:#fecdd3;color:#dc2626}.solarDecisionUx .decisionLoadCard{border-radius:12px;margin:0}.solarDecisionUx .decisionMainRow{grid-template-columns:1.42fr .9fr .7fr .7fr .68fr .92fr .88fr;gap:9px;padding:9px 12px;align-items:center}.solarDecisionUx .decisionIdentity{grid-template-columns:34px minmax(0,1fr);gap:9px}.solarDecisionUx .decisionIdentity .loadIcon{width:34px;height:34px;font-size:14px}.solarDecisionUx .decisionIdentity h3{font-size:12.5px;line-height:1.1}.solarDecisionUx .decisionIdentity p{font-size:10px;margin:1px 0 3px}.solarDecisionUx .connectionPill{padding:2px 7px;font-size:9.5px}.solarDecisionUx .decisionPlan small,.solarDecisionUx .decisionMetric small,.solarDecisionUx .decisionExpected small{font-size:9.5px;margin-bottom:2px}.solarDecisionUx .decisionPlan b,.solarDecisionUx .decisionMetric b,.solarDecisionUx .decisionExpected b{font-size:12.2px}.solarDecisionUx .decisionPlan span,.solarDecisionUx .decisionMetric span,.solarDecisionUx .decisionExpected span{font-size:9.6px;margin-top:2px;line-height:1.15}.solarDecisionUx .planningBadge,.solarDecisionUx .expectedBadge{padding:3px 7px;font-size:10px;border-radius:7px}.solarDecisionUx .decisionControlRow{grid-template-columns:86px minmax(240px,1fr) 112px minmax(300px,auto);gap:10px;padding:7px 12px;align-items:center}.solarDecisionUx .readOnlyPriority span,.solarDecisionUx .automationMini span{font-size:9.5px}.solarDecisionUx .readOnlyPriority b{min-height:26px;padding:0 10px;font-size:10px}.solarDecisionUx .requestedSlot .sliderField>div{margin-bottom:2px}.solarDecisionUx .requestedSlot input[type=range]{height:18px}.solarDecisionUx .automationMini{gap:2px;padding-left:9px}.solarDecisionUx .automationMini b{font-size:9.5px;padding:2px 7px}.solarDecisionUx .automationMini em{font-size:9px;line-height:1.1}.solarDecisionUx .decisionActions{grid-template-columns:auto 82px 72px 72px;gap:7px}.solarDecisionUx .decisionActions>span{font-size:9.5px;max-width:92px;overflow:hidden;text-overflow:ellipsis}.solarDecisionUx .decisionActions .hiAction{padding:7px 9px;font-size:10.5px}.solarDecisionUx .decisionActions .hiAction.enabled:nth-of-type(3){background:#fefce8;border-color:#fde68a;color:#a16207}.solarDecisionUx .loadNotice{margin:0 12px 6px;padding:6px 8px;font-size:10px;border-radius:8px}.solarDecisionUx .loadNotice em{font-size:10px}.solarDecisionUx .loadDetailsFull{padding:0 12px 8px}.solarDecisionUx .loadDetailsFull .hiDetails summary{padding:7px 9px;font-size:11px}.solarDecisionUx .loadDetailsFull .softBox{padding:8px}.solarDecisionUx .flexLoadList{gap:7px}.solarDecisionUx .decisionLoadsPanel{padding:13px}.solarDecisionUx .energySectionHead{margin-bottom:6px}.solarDecisionUx .solarMainGrid{gap:12px}.solarDecisionUx .loadNotice{display:grid;grid-template-columns:auto auto 1fr;gap:8px;align-items:center;margin:0 14px 8px;background:#f8fafc;border:1px solid #e5ebf3;border-radius:8px;padding:7px 10px;color:#475569}.solarDecisionUx .loadNotice b{font-size:11px}.solarDecisionUx .loadNotice em{font-size:11px;font-style:normal;color:#64748b}.solarDecisionUx .loadDetailsFull{padding:0 14px 10px}.solarDecisionUx .loadDetailsFull .hiDetails summary{border:0;background:#fff;padding:8px 0;font-size:11.5px;font-weight:720}.solarDecisionUx .loadDetailsFull .hiDetails[open] .softBox{grid-template-columns:repeat(4,minmax(0,1fr));background:#f8fafc;border:1px solid #e5ebf3;border-radius:10px;margin-top:4px;padding:10px}.solarDecisionUx .strategySettingsRow{display:none}.solarDecisionUx .solarSideCard{padding:18px}.solarDecisionUx .solarSideCard h2{font-size:16px}.solarDecisionUx .solarTodayPrimary{font-size:20px}.solarDecisionUx .solarStateDecision .sideLink,.solarDecisionUx .planningCheck .sideLink{width:100%;margin-top:12px}.solarDecisionUx .planningCheckIcon{width:28px;height:28px;border-radius:50%;border:1px solid #bbf7d0;color:#16a34a;display:grid;place-items:center;font-weight:900;margin:10px 0}.solarDecisionUx .planningCheck>b{display:block;font-size:13px;line-height:1.35;margin-bottom:8px}.solarDecisionUx .planningMiniStats{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:10px}.solarDecisionUx .planningMiniStats span{font-size:10px;background:#f8fafc;border:1px solid #e5ebf3;border-radius:7px;padding:5px 6px;color:#475569}.r164GoalContext{display:grid;grid-template-columns:1.05fr 1.35fr .9fr 1.1fr .9fr;gap:8px;padding:7px 12px;border-top:1px solid #eef2f7;background:#fbfdff}.r164GoalContext>div{min-width:0;border:1px solid #e5ebf3;background:#fff;border-radius:8px;padding:6px 8px}.r164GoalContext small{display:block;font-size:9px;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:.02em;margin-bottom:2px}.r164GoalContext b{display:block;font-size:10.5px;line-height:1.2;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.r164GoalContext span{display:block;font-size:9.5px;color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.effectiveStrategyGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.effectiveStrategyCard{border:1px solid #e5ebf3;background:#fff;border-radius:12px;padding:12px}.effectiveStrategyCard>div:first-child{display:flex;justify-content:space-between;gap:10px;margin-bottom:8px}.effectiveStrategyCard b{font-size:13px}.effectiveStrategyCard span{font-size:10px;color:#64748b}.effectiveStrategyFacts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}@media(max-width:1180px){.solarDecisionUx .decisionMainRow{grid-template-columns:1fr 1fr}.solarDecisionUx .decisionControlRow{grid-template-columns:1fr 1fr}.r164GoalContext{grid-template-columns:1fr 1fr}.effectiveStrategyGrid{grid-template-columns:1fr}.effectiveStrategyFacts{grid-template-columns:1fr 1fr}}.solarDecisionUx .compactSolarPlan{display:grid;grid-template-columns:1.1fr 1fr 1.4fr 1fr;gap:16px;align-items:start}.solarDecisionUx .compactSolarPlan .r3230Illustration,.solarDecisionUx .compactSolarPlan .recSplit{display:none}.solarDecisionUx .compactSolarPlan .solarRecommendation{min-height:0}.solarDecisionUx .compactSolarPlan .hiDetails summary{padding:7px 0;border:0;background:#fff}.solarDecisionUx .decisionLoadCard.noWhy .decisionMainRow{grid-template-columns:1.42fr .9fr .7fr .7fr .68fr}.solarDecisionUx .decisionLoadCard.noEta.noWhy .decisionMainRow{grid-template-columns:1.42fr .9fr .7fr .7fr}.solarDecisionUx .decisionLoadCard.noExpected.noEta.noWhy .decisionMainRow{grid-template-columns:1.42fr .9fr .7fr .7fr}.solarDecisionUx .decisionLoadCard.noExpected .decisionExpected,.solarDecisionUx .decisionLoadCard.noEta .readyCell,.solarDecisionUx .decisionLoadCard.noWhy .whyCell{display:none}.solarDecisionUx .r164GoalContext{grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}.solarDecisionUx .r164GoalContext:empty{display:none}.solarDecisionUx .mergedPlanningSummary .hiDetails summary{padding:8px 0;border:0;background:#fff}.solarDecisionUx .sortControl .insightButton{display:none}@media(max-width:1180px){.solarDecisionUx .compactSolarPlan{grid-template-columns:1fr 1fr}.solarDecisionUx .decisionLoadCard.noWhy .decisionMainRow,.solarDecisionUx .decisionLoadCard.noEta.noWhy .decisionMainRow,.solarDecisionUx .decisionLoadCard.noExpected.noEta.noWhy .decisionMainRow{grid-template-columns:1fr 1fr}}.strategyProfileUx .strategyProfilePicker{display:grid;grid-template-columns:minmax(260px,.9fr) minmax(220px,280px);gap:12px;align-items:start}.strategyProfileUx .strategyProfilePicker select{width:100%;min-height:38px;border:1px solid var(--line);border-radius:10px;background:#fff;padding:8px 10px;font:inherit}.strategyProfileUx .profilePickCards{grid-column:1/-1;display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:8px}.strategyProfileUx .profilePickCard{border:1px solid var(--line);border-radius:12px;background:#fff;text-align:left;padding:10px 12px;cursor:pointer;color:#0f172a}.strategyProfileUx .profilePickCard.active{border-color:#bae6fd;background:#f0f9ff;box-shadow:inset 0 0 0 1px #bae6fd}.strategyProfileUx .profilePickCard b{display:block;font-size:12px;font-weight:650;margin-bottom:3px}.strategyProfileUx .profilePickCard span{display:block;font-size:10.5px;color:#64748b;line-height:1.3}.strategyProfileUx .strategyProfileWorkspace{display:grid;grid-template-columns:minmax(0,1fr) 285px;gap:10px;align-items:start}.strategyProfileUx .strategyProfileCard.selectedOnly{padding:12px}.strategyProfileUx .profileSettingGroup{border:1px solid var(--line);background:#fff;border-radius:12px;padding:10px;margin-top:9px}.strategyProfileUx .profileSettingGroup h3{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#64748b;font-weight:800;margin:0 0 8px}.strategyProfileUx .profileSettingGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.strategyProfileUx .profileSettingGrid .profilePolicyLine{background:#f8fafc;border:1px solid #edf2f7;border-radius:9px;padding:8px 10px}.strategyProfileUx .profileNoControls{margin-top:9px}.writeState{display:block;grid-column:1/-1;font-size:9.5px;color:#64748b;margin-top:3px}.writeState.pending{color:#92400e}.writeState.sent{color:#166534}.writeState.failed,.writeState.blocked{color:#991b1b}.selectField.noOptions em{display:block;font-size:9.5px;color:#94a3b8;font-style:normal;margin-top:3px}.strategyProfilesPage{display:grid;gap:var(--hi-gap)}.strategyProfileSummary{margin-bottom:0}.strategyBoundaryCard{display:grid;grid-template-columns:minmax(280px,1fr) 2fr;gap:14px;align-items:center}.strategyBoundaryGrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}.strategyBoundaryGrid span{display:block;background:#f8fafc;border:1px solid var(--line);border-radius:10px;padding:9px 10px;font-size:10.5px;color:var(--muted)}.strategyBoundaryGrid b{display:block;margin-top:3px;font-size:12px;color:#0f172a}.strategyProfilesLayout{display:grid;grid-template-columns:minmax(190px,.7fr) minmax(0,2.35fr) minmax(220px,.85fr);gap:var(--hi-gap);align-items:start}.profileNav,.profileExplain{position:sticky;top:10px}.profileChips{display:grid;gap:7px}.profileChips span,.profileBadge{display:inline-flex;align-items:center;border:1px solid #dce8f6;background:#f8fbff;border-radius:999px;padding:7px 10px;font-size:10.5px;font-weight:650;color:#334155}.profileEditorColumn{display:grid;gap:var(--hi-gap)}.strategyProfileCard{display:grid;gap:10px}.profileCardHead{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.profileCardHead small{display:block;text-transform:uppercase;letter-spacing:.12em;font-size:9px;font-weight:700;color:var(--muted);margin-bottom:3px}.profileCardHead h2{margin:0 0 4px}.profileCardHead p{margin:0}.profileGroups{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.profileGroup{background:#f8fafc;border:1px solid #e7edf6;border-radius:12px;padding:10px}.profileGroup h3,.profileControls h3{font-size:11px;line-height:1.2;text-transform:uppercase;letter-spacing:.1em;color:#64748b;margin:0 0 7px}.profilePolicyLine{display:flex;justify-content:space-between;gap:10px;border-top:1px solid #edf2f7;padding:6px 0}.profilePolicyLine:first-of-type{border-top:0;padding-top:0}.profilePolicyLine span{font-size:10.5px;color:var(--muted)}.profilePolicyLine b{font-size:11px;font-weight:620;text-align:right}.profileControls{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;background:#fff;border:1px solid var(--line);border-radius:12px;padding:10px}.profileControls h3{grid-column:1/-1}.profileNoControls{font-size:10.5px;color:#64748b;background:#f8fafc;border:1px solid var(--line);border-radius:10px;padding:8px 10px}.effectivePolicyPreview{display:grid;gap:8px}.effectivePolicyList{display:grid;gap:8px}.effectivePolicyRow{display:grid;grid-template-columns:1.5fr 1fr .8fr 1fr 1fr;gap:10px;align-items:center;border:1px solid var(--line);background:#fff;border-radius:12px;padding:10px 12px}.effectivePolicyRow span{display:block;font-size:10px;color:var(--muted)}.effectivePolicyRow b{font-size:11.5px;font-weight:620}.strategyDiagnosticsPanel .hiDetails .softBox{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.empty.compact{margin-top:0;padding:10px;border-radius:10px}.empty.compact b{font-size:11px}.empty.compact span{font-size:10px}.profileControls .toggleField{display:grid;grid-template-columns:1fr auto auto;gap:8px;align-items:center;background:#f8fafc;border:1px solid #edf2f7;border-radius:9px;padding:8px 10px}.profileControls .toggleField span{font-size:10.5px;color:var(--muted)}.profileControls .toggleField b{font-size:11px;color:#334155}.profileControls .toggleField input{width:18px;height:18px}.profileControls .editField,.profileControls .selectField,.profileControls .sliderField,.profileControls .toggleField{min-width:0}.profileControls .sliderField{background:#f8fafc;border:1px solid #edf2f7;border-radius:9px;padding:8px 10px}.profileControls .sliderField div{display:flex;justify-content:space-between;gap:8px}.profileControls .sliderField span{font-size:10.5px;color:var(--muted)}.profileControls .sliderField b{font-size:11px;color:#0f172a}.profileControls .sliderField input[type=range]{width:100%;margin-top:8px}.profileControls .selectField{display:grid;gap:5px;background:#f8fafc;border:1px solid #edf2f7;border-radius:9px;padding:8px 10px}.profileControls .selectField span{font-size:10.5px;color:var(--muted)}.profileControls .selectField select{width:100%;border:1px solid var(--line);border-radius:7px;background:#fff;padding:6px;font:inherit;font-size:11px}.profileControls input:disabled,.profileControls select:disabled{background:#f1f5f9;color:#94a3b8;cursor:not-allowed}@media(max-width:1180px){.strategyBoundaryCard,.strategyProfilesLayout{grid-template-columns:1fr}.profileNav,.profileExplain{position:static}.profileChips{display:flex;overflow-x:auto;gap:8px;padding-bottom:2px}.profileGroups{grid-template-columns:1fr 1fr}.effectivePolicyRow{grid-template-columns:1fr 1fr}.effectivePolicyRow>div:first-child{grid-column:1/-1}.profileControls{grid-template-columns:1fr 1fr}}@media(max-width:700px){.strategyProfilesPage .summaryRow.four.strategyProfileSummary{grid-template-columns:1fr 1fr}.strategyBoundaryCard{padding:14px}.strategyBoundaryGrid{grid-template-columns:1fr}.strategyProfilesLayout{gap:12px}.profileCardHead{display:grid;grid-template-columns:1fr}.profileBadge{justify-self:start}.profileGroups,.profileControls,.effectivePolicyRow,.strategyDiagnosticsPanel .hiDetails .softBox{grid-template-columns:1fr}.strategyProfileCard,.profileNav,.profileExplain,.effectivePolicyPreview,.strategyDiagnosticsPanel{padding:14px}.profilePolicyLine{align-items:flex-start}.profilePolicyLine b{text-align:left}.effectivePolicyRow{padding:10px}.profileControls .editField,.profileControls .selectField{width:100%}.profileControls input,.profileControls select{min-height:40px}.profileChips span{white-space:nowrap}}:host{--hi-intelligence:#7c3aed;--hi-metering:#4f46e5;--hi-solar:#f59e0b;--hi-battery:#059669;--hi-consumers:#2563eb;--hi-value:#0f766e}.hiTabExperienceHeader.orange{--tab-accent:var(--hi-solar)}.hiTabExperienceHeader.green{--tab-accent:var(--hi-battery)}.hiTabExperienceHeader.blue{--tab-accent:var(--hi-consumers)}.hiTabExperienceHeader.purple{--tab-accent:var(--hi-intelligence)}.hiTabExperienceHeader .hiTabStatusIcon{color:var(--tab-accent,#2563eb);background:color-mix(in srgb,var(--tab-accent,#2563eb) 8%,white)}.productStory{border-left:4px solid var(--tab-accent,#2563eb);background:linear-gradient(110deg,color-mix(in srgb,var(--tab-accent,#2563eb) 5%,white),#fff 55%)}.productStory.orange{--tab-accent:#f59e0b}.productStory.green{--tab-accent:#059669}.productStory.blue{--tab-accent:#2563eb}.productStory.purple{--tab-accent:#7c3aed}.productStoryRecommendation{background:color-mix(in srgb,var(--tab-accent,#2563eb) 6%,white);border:1px solid color-mix(in srgb,var(--tab-accent,#2563eb) 14%,white)}.editableProperty{display:grid;grid-template-columns:minmax(150px,.75fr) minmax(220px,1.25fr);gap:12px;align-items:center;width:100%;min-width:0}.editablePropertyCopy{display:grid;gap:3px}.editablePropertyCopy>span{font-weight:750;color:var(--ink)}.editablePropertyCopy>small,.editablePropertyDisabled,.editablePropertyReadback{font-size:10px;color:#64748b;font-style:normal}.editablePropertyEditor{display:grid;gap:4px;min-width:0}.editableProperty.readonly{opacity:.78}.editableProperty .sliderField,.editableProperty .selectField,.editableProperty .toggleField,.editableProperty .editField{margin:0}.automationQuickAction .editableProperty{grid-template-columns:1fr}.automationQuickAction .editablePropertyCopy{display:none}@media(max-width:760px){.editableProperty{grid-template-columns:1fr}}.automationQuickAction{display:grid;grid-template-columns:minmax(220px,.8fr) minmax(360px,1.2fr);align-items:center;gap:18px;border:1px solid #eadfff;border-left:4px solid var(--hi-intelligence);border-radius:14px;background:linear-gradient(120deg,#faf7ff,#fff 62%);padding:12px 14px;box-shadow:none}.automationQuickAction.solar,.automationQuickAction.intelligence{margin:0}.automationQuickAction.solar{grid-template-columns:minmax(180px,.75fr) minmax(260px,1.25fr)}.automationQuickCopy small,.portalSectionHeader small{text-transform:uppercase;letter-spacing:.12em;font-size:9px;font-weight:750;color:#7c3aed}.automationQuickCopy h2,.portalSectionHeader h2{margin:3px 0 4px}.automationQuickCopy p,.portalSectionHeader p{margin:0;color:var(--muted)}.automationQuickControl{display:grid;gap:6px;min-width:0}.automationQuickControl .segmented{justify-self:start}.automationQuickControl>span{font-size:10.5px;color:#64748b}.automationWriteState{font-weight:700;color:#6d28d9}.automationWriteState.rejected{color:#b91c1c}.automationModeSummary{display:grid;grid-template-columns:auto auto;gap:2px 10px;align-items:center;padding:11px 12px;border:1px solid #ece6f8;border-radius:13px;background:#faf8ff}.automationModeSummary span{font-size:9px;text-transform:uppercase;letter-spacing:.1em;color:#7c3aed;font-weight:750}.automationModeSummary b{justify-self:end;font-size:12px}.automationModeSummary em{grid-column:1/-1;font-style:normal;font-size:10.5px;color:#64748b}@media(max-width:760px){.automationQuickAction{grid-template-columns:1fr}.automationQuickControl .segmented{width:100%}}.intelligenceControlCenter{display:grid;gap:12px}.portalSectionHeader{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.policyInfluenceChips{display:flex;flex-wrap:wrap;gap:6px;justify-content:flex-end}.policyInfluenceChips span{border-radius:999px;padding:5px 8px;background:#f5f3ff;color:#6d28d9;font-size:9.5px;font-weight:650}.intelligenceManagedPanel{border-top:3px solid #ede9fe}.managedAssetCard{border-left:3px solid #dbeafe;background:linear-gradient(110deg,#f8fbff,#fff 48%)}.managedAssetCard .hiDetails,.productPortalPage .hiDetails,.productStory>.hiDetails{display:none}.hiTabSimpleBadge.ok{opacity:.72}.hiTabSimpleBadge.ok:before{background:var(--tab-accent,#22c55e)}@media(max-width:700px){.automationControlHeader,.portalSectionHeader{display:grid}.automationModePill{justify-self:start}.policyInfluenceChips{justify-content:flex-start}}.decisionTransparencyPage{max-width:1500px;margin:0 auto;display:grid;grid-template-columns:1.2fr 1fr;gap:12px}.decisionReferenceCard{grid-column:1/-1}.decisionReferenceHead{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.decisionReferenceHead small{font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);font-weight:700}.decisionReferenceHead h2{margin:4px 0 4px}.decisionReferenceHead p{margin:0;color:var(--muted)}.decisionStateBadge{border:1px solid var(--line);border-radius:999px;padding:6px 10px;font-size:11px;font-weight:700;white-space:nowrap}.decisionReferenceGrid,.decisionMiniGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px;margin-top:12px}.decisionReferenceGrid>div,.decisionMiniGrid>div{border:1px solid #e7edf3;border-radius:10px;padding:8px 9px;background:#fafcfe}.decisionReferenceGrid span,.decisionMiniGrid span{display:block;font-size:9.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}.decisionReferenceGrid b,.decisionMiniGrid b{display:block;font-size:12px;line-height:1.25;margin-top:3px}.policyStatusRow{display:grid;grid-template-columns:minmax(220px,1fr) repeat(3,minmax(90px,.35fr));gap:8px;align-items:center;padding:9px 0;border-top:1px solid #edf1f5}.policyStatusRow:first-of-type{border-top:0}.policyStatusRow>div:first-child span{display:block;color:var(--muted);font-size:10.5px;margin-top:2px}.policyStatusRow small{display:block;font-size:9px;color:var(--muted)}.policyStatusRow strong{display:block;font-size:11px;margin-top:2px}.planningTransparencyRow{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;padding:9px 0;border-top:1px solid #edf1f5}.planningTransparencyRow:first-of-type{border-top:0}.planningTransparencyRow span,.planningTransparencyRow small{display:block;color:var(--muted);font-size:10.5px;margin-top:2px}.planningTransparencyRow strong{font-size:11px;white-space:nowrap}.outlookAssetPlans{grid-column:span 2}.batteryPolicyInfluence{min-height:0}@media(max-width:700px){.decisionTransparencyPage{grid-template-columns:1fr}.decisionReferenceGrid,.decisionMiniGrid{grid-template-columns:1fr 1fr}.policyStatusRow{grid-template-columns:1fr 1fr}.policyStatusRow>div:first-child{grid-column:1/-1}.outlookAssetPlans{grid-column:auto}.decisionReferenceHead{flex-direction:column}.decisionStateBadge{align-self:flex-start}}.horizonPage{max-width:1500px;margin:0 auto;display:grid;gap:var(--hi-gap)}.horizonSelector{display:grid;grid-template-columns:minmax(160px,220px) 1fr;gap:10px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px}.horizonSelector>div:first-child span{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);font-weight:700}.horizonSelector>div:first-child b{display:block;font-size:14px;font-weight:650}.horizonSelector select{display:none;width:100%;min-height:40px;border:1px solid var(--line);border-radius:10px;background:#fff;padding:8px 10px;font:inherit}.horizonButtons{justify-content:flex-start}.horizonGrid{align-items:start}.warningChips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.warningChips span{border:1px solid #f2d79b;background:#fff7e6;color:#946200;border-radius:999px;padding:4px 8px;font-size:10px;font-weight:650}.meteringHorizon .heroPanel{text-align:left;min-height:0}.meteringHorizon .meteringGrid{grid-template-columns:repeat(3,minmax(0,1fr))}.meteringHorizon .meteringGrid .heroPanel,.meteringHorizon .meteringGrid section:last-child{grid-column:1/-1}@media(max-width:1180px){.strategyProfileUx .strategyProfileWorkspace,.strategyProfileUx .strategyProfilePicker{grid-template-columns:1fr}.strategyProfileUx .profileExplain{position:static}.strategyProfileUx .profileSettingGrid{grid-template-columns:1fr 1fr}}@media(max-width:700px){.strategyProfileUx .profilePickCards{display:none}.strategyProfileUx .strategyProfilePicker{grid-template-columns:1fr}.strategyProfileUx .strategyProfilePicker select{display:block}.strategyProfileUx .strategyProfileWorkspace{grid-template-columns:1fr}.strategyProfileUx .profileSettingGrid{grid-template-columns:1fr}.strategyProfileUx .profileCardHead{grid-template-columns:1fr}.strategyProfileUx .profileBadge{justify-self:start}.strategyProfileUx .profileSettingGroup{padding:9px}.strategyProfileUx input,.strategyProfileUx select{min-height:42px}.strategyProfileUx .profileExplain{display:block}}.outlookPageV2{gap:12px}.outlookHeader{display:grid;grid-template-columns:minmax(220px,360px) 1fr;gap:12px;align-items:center}.outlookHeader h2{font-size:18px;line-height:1.15;margin:0 0 3px;font-weight:650}.outlookHeader p{font-size:12px;line-height:1.25;color:var(--muted);margin:0}.outlookHeader .horizonSelector{padding:8px;grid-template-columns:0 1fr;gap:0}.outlookHeader .horizonSelector>div:first-child{display:none}.outlookKpis{margin-bottom:2px}.outlookGrid{display:grid;grid-template-columns:1.15fr 1fr 1fr;gap:10px;align-items:start}.outlookHero{grid-column:1/-1;display:grid;grid-template-columns:1.2fr 1fr 1.15fr;gap:10px;align-items:stretch;min-height:0;text-align:left}.outlookHero h2{font-size:18px;margin:0 0 4px}.outlookHero p{margin:0}.outlookHeroBalance{border:1px solid #d9e8fb;background:#f3f8ff;border-radius:12px;padding:12px;display:grid;align-content:center;gap:5px}.outlookHeroBalance b{font-size:16px;font-weight:650}.outlookHeroBalance span{font-size:12px;color:var(--muted)}.outlookHeroFacts{display:grid;grid-template-columns:1fr 1fr;gap:8px}.outlookHeroFacts>div{border:1px solid var(--line);background:#fff;border-radius:12px;padding:10px}.outlookHeroFacts span{display:block;font-size:11px;color:var(--muted);margin-bottom:5px}.outlookHeroFacts b{display:block;font-size:13px;font-weight:650}.outlookLimitNotice{grid-column:1/-1;border:1px solid #f2d79b;background:#fff8e8;color:#7a5200;border-radius:10px;padding:8px 10px;font-size:11px;font-weight:600}.outlookCard,.outlookQualityCard{min-height:0}.outlookCard .empty,.outlookQualityCard .empty{margin-top:8px;border:1px dashed var(--line);background:#fbfdff;border-radius:12px;padding:12px}.outlookQualityCard .hiDetails{margin-top:8px}.outlookQualityCard .warningChips{margin:0 0 8px}.outlookQualityCard{grid-column:auto}.r3470ConsumersPage{max-width:1500px;margin:0 auto;display:grid;gap:var(--hi-gap)}.consumerMixKpis{margin-bottom:0}.consumerMixSecondary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;padding:10px 12px}.consumerMixSecondary>div{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:7px 9px;border:1px solid var(--line);border-radius:10px;background:#fff}.consumerMixSecondary span{font-size:10.5px;color:var(--muted)}.consumerMixSecondary b{font-size:13px}.consumerMixGap{display:block;background:#fffdf7;border-color:#f2d79b;padding:10px 12px}.consumerMixGap b,.consumerMixGap span{display:block}.consumerMixGap span{font-size:11px;color:var(--muted);margin-top:3px}.consumerExplorerHeader{display:grid;grid-template-columns:minmax(0,1fr) minmax(360px,.9fr);gap:12px;align-items:start}.consumerToolbar{display:grid;grid-template-columns:1fr 1fr;gap:8px}.consumerToolbar label{font-size:10px;color:var(--muted);display:grid;gap:4px}.consumerToolbar select{min-height:38px;border:1px solid var(--line);border-radius:10px;background:#fff;padding:7px 9px;font:inherit}.consumerQuickFilters{grid-column:1/-1;display:flex;gap:5px;flex-wrap:wrap}.consumerQuickFilters button{border:1px solid var(--line);background:#fff;border-radius:999px;padding:5px 9px;font-size:10px}.consumerQuickFilters button.active{background:#eef7fd;border-color:#b8def4;color:#175f88}.consumerExplorerList{display:grid;gap:8px;margin-top:10px}.consumerExplorerCard{border:1px solid var(--line);border-radius:13px;background:#fff;padding:11px 12px}.consumerExplorerHead{display:flex;justify-content:space-between;gap:12px;align-items:start}.consumerExplorerHead h3{margin:0;font-size:15px}.consumerExplorerHead p{margin:3px 0 0;font-size:10.5px}.consumerExplorerPrimary{text-align:right}.consumerExplorerPrimary b,.consumerExplorerPrimary span{display:block}.consumerExplorerPrimary b{font-size:16px}.consumerExplorerPrimary span{font-size:10.5px;color:var(--muted);margin-top:2px}.consumerExplorerMetrics{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:6px;margin:9px 0}.consumerExplorerMetrics>div{border:1px solid #e8edf3;border-radius:9px;padding:7px 8px;background:#f9fbfd}.consumerExplorerMetrics span,.consumerExplorerStatus span{display:block;font-size:9.5px;color:var(--muted)}.consumerExplorerMetrics b,.consumerExplorerStatus b{display:block;font-size:12px;margin-top:2px}.consumerMixBar{height:8px;border-radius:999px;overflow:hidden;display:flex;background:#eef2f6;margin:8px 0 5px}.consumerMixBar .solar{background:#f2b84b}.consumerMixBar .battery{background:#65a982}.consumerMixBar .lowGrid{background:#7aa9d8}.consumerMixBar .grid{background:#b8c2cc}.consumerMixLegend{display:flex;gap:10px;flex-wrap:wrap;color:var(--muted);font-size:9.5px}.consumerMixUnavailable{border:1px dashed #d9e1ea;border-radius:9px;padding:7px 9px;color:var(--muted);font-size:10px;margin:8px 0}.consumerExplorerStatus{display:grid;grid-template-columns:2fr 1fr 1fr;gap:6px;margin-top:9px}.consumerExplorerStatus>div{padding:7px 8px;border-top:1px solid #edf1f5}.consumerExplorerStatus small{display:block;color:var(--muted);font-size:9.5px;margin-top:2px}@media(max-width:1180px){.consumerExplorerHeader{grid-template-columns:1fr}.consumerExplorerMetrics{grid-template-columns:repeat(3,minmax(0,1fr))}.consumerMixSecondary{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:700px){.consumerMixSecondary,.consumerExplorerMetrics,.consumerExplorerStatus{grid-template-columns:1fr}.consumerExplorerHead{align-items:start}.consumerToolbar{grid-template-columns:1fr}.consumerQuickFilters{display:none}.consumerExplorerPrimary b{font-size:14px}.consumerExplorerCard{padding:10px}.consumerMixLegend{display:grid;grid-template-columns:1fr 1fr;gap:4px 8px}.summaryRow.four.solarKpis{grid-template-columns:1fr 1fr}.summaryRow.four.solarKpis .metric{min-width:0;padding:12px}.solarDecisionUx .compactSolarPlan{grid-template-columns:1fr;padding:14px}.solarDecisionUx .compactSolarPlan .solarIntro p{margin-bottom:0}.solarDecisionUx .solarControls{grid-template-columns:1fr}.solarDecisionUx .decisionLoadsPanel{padding:12px}.solarDecisionUx .energySectionHead{gap:10px}.solarDecisionUx .sortControl{width:100%;justify-content:space-between}.solarDecisionUx .sortControl .segmented{max-width:100%;overflow-x:auto}.solarDecisionUx .decisionMainRow,.solarDecisionUx .decisionLoadCard.noWhy .decisionMainRow,.solarDecisionUx .decisionLoadCard.noEta.noWhy .decisionMainRow,.solarDecisionUx .decisionLoadCard.noExpected.noEta.noWhy .decisionMainRow{grid-template-columns:1fr 1fr;padding:12px;gap:10px}.solarDecisionUx .decisionIdentity{grid-column:1/-1}.solarDecisionUx .decisionPlan{grid-column:1/-1}.solarDecisionUx .decisionMetric,.solarDecisionUx .decisionExpected{min-width:0}.solarDecisionUx .r164GoalContext{grid-template-columns:1fr;padding:0 12px 8px;background:#fff;border-top:0}.solarDecisionUx .r164GoalContext>div{padding:7px 9px}.solarDecisionUx .decisionControlRow{grid-template-columns:1fr;padding:10px 12px;gap:12px}.solarDecisionUx .requestedSlot input[type=range]{width:100%;height:28px}.solarDecisionUx .requestedSlot .sliderField{width:100%}.solarDecisionUx .automationMini{padding-left:0;border-left:0;display:grid;grid-template-columns:1fr auto;align-items:center}.solarDecisionUx .automationMini em{grid-column:1/-1}.solarDecisionUx .decisionActions{grid-template-columns:1fr 1fr}.solarDecisionUx .decisionActions>span{display:none}.solarDecisionUx .decisionActions .hiAction{min-height:40px;font-size:12px}.solarDecisionUx .loadDetailsFull{padding:0 12px 10px}.solarDecisionUx aside{display:grid;grid-template-columns:1fr;gap:12px}.solarDecisionUx .solarSideCard{padding:14px}.solarDecisionUx .planningMiniStats{grid-template-columns:1fr 1fr}.solarDecisionUx .solarStateDecision{display:none}.panel{border-radius:12px}}@media(max-width:700px){.summaryRow,.summaryRow.four,.landing,.solarHomeIntelligence,.solarMainGrid,.r3280OutlookGrid,.bottomInsights,.batteryGrid,.consumerGrid,.strategyGrid,.flowDetailsGrid{grid-template-columns:1fr}.tabs{overflow-x:auto}.solarDecisionUx .decisionMainRow,.solarDecisionUx .decisionControlRow,.r164GoalContext{grid-template-columns:1fr}.solarDecisionUx .decisionActions{grid-template-columns:1fr 1fr}.solarDecisionUx .decisionActions>span{grid-column:1/-1}.requestedSlot{grid-template-columns:1fr}.effectiveStrategyFacts{grid-template-columns:1fr}.top{gap:10px}.panel{padding:14px}.horizonSelector{grid-template-columns:1fr}.horizonSelector .horizonButtons{display:none}.horizonSelector select{display:block}.horizonGrid,.meteringHorizon .meteringGrid{grid-template-columns:1fr}.horizonPage .heroPanel{text-align:left}.warningChips span{font-size:9.5px}.horizonPage .goalGrid{grid-template-columns:1fr}}@media(max-width:1300px){.summaryRow,.summaryRow.four,.landing,.solarHomeIntelligence,.solarMainGrid,.r3280OutlookGrid,.bottomInsights{grid-template-columns:1fr}.top{flex-direction:column}.topRight{text-align:left}.topPills{justify-content:flex-start}.tabs{overflow:auto}.heroPanel{min-height:auto}.energyScene{height:340px}.solarLoadCard{grid-template-columns:1fr}.energySectionHead{flex-direction:column}}@media(max-width:700px){.outlookHeader{grid-template-columns:1fr}.outlookHeader .horizonSelector{grid-template-columns:1fr}.outlookGrid{grid-template-columns:1fr}.outlookHero{grid-template-columns:1fr}.outlookHeroFacts{grid-template-columns:1fr}.outlookKpis{grid-template-columns:1fr}.outlookHeader .horizonSelector .horizonButtons{display:none}.outlookHeader .horizonSelector select{display:block}.outlookPageV2 .panel,.outlookPageV2 .heroPanel{padding:12px}}@media(min-width:701px) and (max-width:1180px){.outlookHeader{grid-template-columns:1fr}.outlookGrid{grid-template-columns:1fr 1fr}.outlookHero{grid-template-columns:1fr}.outlookQualityCard{grid-column:1/-1}}.scopeSelector{display:grid;grid-template-columns:minmax(140px,220px) 1fr;gap:10px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:9px 10px;min-height:44px}.scopeSelectorTitle span{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);font-weight:700}.scopeSelectorTitle b{display:block;font-size:14px;font-weight:650}.scopeButtons{display:inline-flex;align-items:center;justify-content:flex-start;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#f8fafc;min-height:30px;width:max-content;max-width:100%}.scopeOption{appearance:none;border:0;border-right:1px solid var(--line);background:transparent;padding:8px 14px;font:inherit;font-size:11px;font-weight:600;color:#334155;cursor:pointer;line-height:1;white-space:nowrap}.scopeOption:last-child{border-right:0}.scopeOption.active{background:#eef6ff;color:#0f172a;box-shadow:inset 0 0 0 1px rgba(37,99,235,.10)}.scopeSelector select{display:none;width:100%;min-height:42px;border:1px solid var(--line);border-radius:10px;background:#fff;padding:8px 10px;font:inherit}.outlookHeader .scopeSelector{grid-template-columns:1fr}.outlookHeader .scopeSelectorTitle{display:none}.periodMeteringHeader{display:grid;grid-template-columns:minmax(220px,360px) 1fr;gap:12px;align-items:center}.periodMeteringHeader h2{font-size:18px;line-height:1.15;margin:0 0 3px;font-weight:650}.periodMeteringHeader p{font-size:12px;line-height:1.25;color:var(--muted);margin:0}.periodMeteringHeader .scopeSelector{grid-template-columns:1fr}.periodMeteringHeader .scopeSelectorTitle{display:none}.periodMeteringPage{max-width:1500px;margin:0 auto;display:grid;gap:12px}.periodMeteringGrid{display:grid;grid-template-columns:1.05fr 1fr 1fr;gap:10px;align-items:start}.periodMeteringHero{grid-column:1/-1;min-height:0;text-align:left}.periodWarningNotice{margin-top:8px;border:1px solid #f2d79b;background:#fff8e8;color:#7a5200;border-radius:10px;padding:8px 10px;font-size:11px;font-weight:600}.periodQualityCard .hiDetails{margin-top:8px}@media(max-width:700px){.scopeSelector{grid-template-columns:1fr}.scopeButtons{display:none}.scopeSelector select{display:block}.outlookHeader .scopeSelectorTitle,.periodMeteringHeader .scopeSelectorTitle{display:block}.periodMeteringHeader{grid-template-columns:1fr}.periodMeteringGrid{grid-template-columns:1fr}.periodMeteringKpis{grid-template-columns:1fr}.periodMeteringPage .panel,.periodMeteringPage .heroPanel{padding:12px}}@media(min-width:701px) and (max-width:1180px){.periodMeteringHeader{grid-template-columns:1fr}.periodMeteringGrid{grid-template-columns:1fr 1fr}.periodMeteringHero,.periodQualityCard{grid-column:1/-1}}.horizonPage{max-width:1500px;margin:0 auto;display:grid;gap:var(--hi-gap)}.horizonSelector{display:grid;grid-template-columns:minmax(160px,220px) 1fr;gap:10px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px 12px}.horizonSelector>div:first-child span{display:block;font-size:10px;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);font-weight:700}.horizonSelector>div:first-child b{display:block;font-size:14px;font-weight:650}.horizonSelector select{display:none;width:100%;min-height:40px;border:1px solid var(--line);border-radius:10px;background:#fff;padding:8px 10px;font:inherit}.horizonButtons{justify-content:flex-start}.horizonGrid{align-items:start}.warningChips{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.warningChips span{border:1px solid #f2d79b;background:#fff7e6;color:#946200;border-radius:999px;padding:4px 8px;font-size:10px;font-weight:650}.meteringHorizon .heroPanel{text-align:left;min-height:0}.meteringHorizon .meteringGrid{grid-template-columns:repeat(3,minmax(0,1fr))}.meteringHorizon .meteringGrid .heroPanel,.meteringHorizon .meteringGrid section:last-child{grid-column:1/-1}@media(max-width:1180px){.strategyProfileUx .strategyProfileWorkspace,.strategyProfileUx .strategyProfilePicker{grid-template-columns:1fr}.strategyProfileUx .profileExplain{position:static}.strategyProfileUx .profileSettingGrid{grid-template-columns:1fr 1fr}}@media(max-width:700px){.strategyProfileUx .profilePickCards{display:none}.strategyProfileUx .strategyProfilePicker{grid-template-columns:1fr}.strategyProfileUx .strategyProfilePicker select{display:block}.strategyProfileUx .strategyProfileWorkspace{grid-template-columns:1fr}.strategyProfileUx .profileSettingGrid{grid-template-columns:1fr}.strategyProfileUx .profileCardHead{grid-template-columns:1fr}.strategyProfileUx .profileBadge{justify-self:start}.strategyProfileUx .profileSettingGroup{padding:9px}.strategyProfileUx input,.strategyProfileUx select{min-height:42px}.strategyProfileUx .profileExplain{display:block}}.disabledAssetsSection{background:#fafbfd}.disabledAssetCard{padding:10px 12px;background:#fafbfd;border-style:solid}.disabledAssetMain{display:flex;align-items:center;justify-content:space-between;gap:14px}.disabledAssetState{text-align:right}.disabledAssetState b,.disabledAssetState span{display:block}.disabledAssetState b{font-size:12px;color:#475569}.disabledAssetState span,.disabledAssetReason{font-size:10.5px;color:var(--muted)}.disabledAssetReason{margin:7px 0 0;padding-top:7px;border-top:1px solid var(--line)}.controlAvailability{display:flex;flex-wrap:wrap;gap:5px 12px;padding:0 12px 9px;color:#9a3412;font-size:10px}.controlAvailability span{display:inline-block}.storageConsumersSection .decisionMiniGrid{display:none}@media(max-width:700px){.summaryRow.four.solarKpis{grid-template-columns:1fr 1fr}.solarDecisionUx .decisionMainRow,.solarDecisionUx .decisionLoadCard.noWhy .decisionMainRow,.solarDecisionUx .decisionLoadCard.noEta.noWhy .decisionMainRow,.solarDecisionUx .decisionLoadCard.noExpected.noEta.noWhy .decisionMainRow{grid-template-columns:1fr 1fr}.solarDecisionUx .decisionControlRow{grid-template-columns:1fr}.solarDecisionUx .r164GoalContext{grid-template-columns:1fr}.solarDecisionUx .compactSolarPlan{grid-template-columns:1fr}.solarDecisionUx .decisionActions>span{display:none}.solarDecisionUx .decisionActions .hiAction{min-height:40px}.solarDecisionUx .requestedSlot input[type=range]{width:100%}.solarDecisionUx aside{grid-template-columns:1fr}}.meteringRemediationPanel{border-color:#fed7aa;background:#fffaf5}.meteringRemediationItem{display:grid;grid-template-columns:minmax(0,1fr) minmax(180px,240px);gap:14px;align-items:start;border:1px solid #fde6c8;background:#fff;border-radius:12px;padding:12px;margin-top:10px}.meteringRemediationText h3{margin:0 0 6px;font-size:14px;font-weight:700;color:#7c2d12}.meteringRemediationText p{margin:0 0 8px;font-size:12px;color:#475569;line-height:1.35}.remediationImpact{display:grid;grid-template-columns:70px minmax(0,1fr);gap:8px;background:#fff7ed;border:1px solid #ffedd5;border-radius:9px;padding:8px;font-size:11px}.remediationImpact b{color:#9a3412}.meteringRemediationAction{display:flex;flex-direction:column;gap:6px;align-items:stretch}.meteringRemediationAction .hiAction{min-height:38px}.meteringRemediationAction small{font-size:10.5px;color:#64748b;text-align:center}.writeFeedback{margin-top:8px;border-radius:8px;border:1px solid #e2e8f0;background:#f8fafc;padding:6px 8px;font-size:11px;font-weight:650;color:#334155}.writeFeedback.pending,.writeFeedback.pending_verification{border-color:#fde68a;background:#fffbeb;color:#92400e}.writeFeedback.failed,.writeFeedback.blocked{border-color:#fecaca;background:#fff1f2;color:#991b1b}@media(max-width:700px){.meteringRemediationItem{grid-template-columns:1fr}.meteringRemediationAction small{text-align:left}.remediationImpact{grid-template-columns:1fr}}.tabs{overflow-x:auto;overflow-y:hidden;flex-wrap:nowrap;scrollbar-width:thin;-webkit-overflow-scrolling:touch}.tab{flex:0 0 auto;min-height:44px}.consumerToolbar select,.scopeSelector select,.horizonSelector select,.meteringSortSelector select{min-height:44px}.hiAction,button,select,input{touch-action:manipulation}.consumerExplorerMetrics{grid-template-columns:repeat(3,minmax(0,1fr))}.consumerExplorerCard{overflow:hidden}.consumerExplorerHead,.consumerExplorerStatus{min-width:0}.consumerExplorerHead>*,.consumerExplorerStatus>*{min-width:0}.consumerExplorerHead h3,.consumerExplorerHead p,.consumerExplorerStatus small{overflow-wrap:anywhere}.energy{overflow-x:hidden}.panel,.heroPanel,.metric{min-width:0}@media(max-width:700px){.energy{padding:8px 8px 16px;border-radius:0}.top{margin-bottom:6px}.top h1{font-size:22px}.top p{font-size:12px}.tabs{margin:6px 0 8px;padding:3px;border-radius:9px}.tab{padding:10px 13px;font-size:12px}.summaryRow,.summaryRow.four,.summaryRow.five,.consumerMixKpis{grid-template-columns:1fr 1fr}.metric{min-height:72px}.consumerExplorerHeader{display:grid;grid-template-columns:1fr}.consumerToolbar{display:grid;grid-template-columns:1fr 1fr;width:100%}.consumerQuickFilters{grid-column:1/-1;display:flex;overflow-x:auto;flex-wrap:nowrap;padding-bottom:2px}.consumerQuickFilters button{flex:0 0 auto;min-height:44px}.consumerExplorerHead{grid-template-columns:minmax(0,1fr) auto;gap:8px}.consumerExplorerMetrics{grid-template-columns:1fr 1fr}.consumerExplorerStatus{grid-template-columns:1fr}.consumerMixLegend{display:grid;grid-template-columns:1fr 1fr}.consumerExplorerCard .hiDetails summary{min-height:44px;display:flex;align-items:center}.batteryGrid,.consumerGrid,.strategyGrid,.meteringGrid,.intelligenceGrid,.valueGrid,.flowCanvas,.solarMainGrid{grid-template-columns:1fr}.flowColumn,.flowCenter{min-width:0}.hiRuntimeFooter{display:flex;flex-wrap:wrap;gap:4px 6px}.kv{grid-template-columns:minmax(0,1fr) auto}.propertyRow,.commandRow,.assetRow{min-width:0}}@media(max-width:420px){.summaryRow,.summaryRow.four,.summaryRow.five,.consumerMixKpis{grid-template-columns:1fr}.consumerExplorerMetrics{grid-template-columns:1fr}.consumerToolbar{grid-template-columns:1fr}.consumerQuickFilters{grid-column:1}.consumerExplorerHead{grid-template-columns:1fr}.consumerExplorerPrimary{text-align:left}.consumerMixLegend{grid-template-columns:1fr}}.hiTabExperienceHeader{display:grid;grid-template-columns:minmax(300px,.9fr) minmax(420px,1.35fr);gap:14px;margin:0 0 18px;align-items:stretch}.hiTabStatusItem{min-width:0;padding:13px 14px;border-radius:16px;background:#f8fafc;border:1px solid #edf1f6;display:grid;grid-template-columns:34px minmax(0,1fr);gap:10px;align-items:center}.hiTabStatusIcon{width:34px;height:34px;border-radius:11px;display:grid;place-items:center;background:#fff;border:1px solid #e6edf7;font-size:17px;line-height:1;color:#2563eb}.hiTabExperienceHeader.orange .hiTabStatusIcon{color:#ea580c;background:#fffaf3}.hiTabExperienceHeader.green .hiTabStatusIcon{color:#15803d;background:#f2fbf5}.hiTabExperienceHeader.purple .hiTabStatusIcon{color:#6d28d9;background:#faf7ff}.hiTabStatusItem small{font-size:11px;color:#64748b;line-height:1.2;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.hiTabStatusItem b{font-size:18px;line-height:1.15;margin-top:5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.hiTabExperienceHeader+.summaryRow{margin-top:0}@media(max-width:900px){.hiTabExperienceHeader{grid-template-columns:1fr}}@media(max-width:700px){.hiTabExperienceHeader{gap:8px;margin-bottom:10px}.hiTabStatusItem{padding:10px 11px;min-height:60px;grid-template-columns:30px minmax(0,1fr);gap:8px}.hiTabStatusIcon{width:30px;height:30px;border-radius:10px;font-size:15px}.hiTabStatusItem small{font-size:10px}.hiTabStatusItem b{font-size:16px}.hiTabExperienceHeader+.summaryRow{display:none}}@media(max-width:340px){}.hiTabExperienceHeader{display:block;margin:0 0 18px}.hiTabStatusItem{background:rgba(248,250,252,.9);min-height:70px}.hiTabExperienceHeader+.summaryRow,.solarOperationsPage>.summaryRow:first-child,.batteryPage>.summaryRow:first-child,.consumersPage>.summaryRow:first-child,.strategiesPage>.summaryRow:first-child,.intelligencePage>.summaryRow:first-child,.valuePage>.summaryRow:first-child{display:none}@media(max-width:900px){}@media(max-width:700px){.hiTabExperienceHeader{margin-bottom:10px}.hiTabStatusItem{min-height:64px}}@media(max-width:420px){}.hiTabSimpleBadge{display:inline-flex;align-items:center;gap:6px;width:max-content;max-width:220px;border-radius:999px;padding:6px 10px;background:rgba(255,255,255,.9);border:1px solid rgba(203,213,225,.9);box-shadow:0 5px 16px rgba(15,23,42,.06);font-size:11px;font-weight:700;white-space:nowrap}.hiTabSimpleBadge:before{content:"";width:7px;height:7px;border-radius:50%;background:#94a3b8;flex:0 0 auto}.hiTabSimpleBadge.ok:before{background:#22c55e}.hiTabSimpleBadge.attention:before{background:#f59e0b}.hiTabSimpleBadge.attention{color:#8a5700}.hiTabStatusItem{min-height:58px;padding:9px 11px;grid-template-columns:30px minmax(0,1fr);gap:8px}.hiTabStatusIcon{width:30px;height:30px;border-radius:9px;font-size:15px}.hiTabStatusItem small{font-size:10px}.hiTabStatusItem b{font-size:16px;margin-top:2px}.outlookSummaryStrip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:0 0 10px}.outlookSummaryStrip>div{background:#fff;border:1px solid var(--line);border-radius:11px;padding:10px 12px}.outlookSummaryStrip small{display:block;color:var(--muted);font-size:9px}.outlookSummaryStrip b{display:block;font-size:12px;margin-top:3px}.outlookThreeGrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;align-items:start}.outlookBalanceCard{min-height:0}.outlookAggregateRow{display:flex;justify-content:space-between;padding:8px 0;border-top:1px solid var(--line)}.outlookChildren{margin:0 0 5px 12px}.outlookChildRow{display:grid;grid-template-columns:25px minmax(0,1fr) auto;gap:7px;align-items:center;padding:6px 8px;border-left:2px solid #dbe7f3;background:#f8fbff;margin:3px 0}.outlookChildRow b{font-size:10.5px}.outlookChildRow strong{font-size:10.5px}.outlookTotalRow{display:flex;align-items:center;justify-content:space-between;border-top:2px solid #d9e2ee;margin-top:8px;padding-top:9px;font-weight:700}.outlookBalanceMeaning{display:block;margin-top:5px;color:var(--muted)}.flowProductCanvas{grid-template-columns:minmax(180px,.8fr) minmax(260px,1.1fr) minmax(220px,1fr)}.flowHomeCenter{display:flex;flex-direction:column;justify-content:center}.flowGroupNode{border:1px solid var(--line);background:#fff;border-radius:12px;padding:9px;margin-top:7px}.flowGroupHead{display:grid;grid-template-columns:30px minmax(0,1fr) auto;gap:8px;align-items:center}.flowGroupHead small{display:block;color:var(--muted);font-size:9px}.flowChildRow{display:grid;grid-template-columns:25px minmax(0,1fr) auto;gap:7px;align-items:center;margin:5px 0 0 20px;padding:6px 7px;border-left:2px solid #dce8f5;background:#f8fbff}.flowChildRow b,.flowChildRow strong{font-size:10.5px}.flowChildRow small{display:block;color:var(--muted);font-size:9px}.flowConnectionsPanel{margin-top:10px}.flowConnectionsPanel .flowChildRow{margin-left:0}@media(max-width:1050px){.outlookThreeGrid{grid-template-columns:1fr 1fr}.outlookThreeGrid>section:last-child{grid-column:1/-1}.flowProductCanvas{grid-template-columns:1fr 1fr}.flowHomeCenter{grid-column:1/-1;grid-row:1}}.flowDetailsGridTwoUp{grid-template-columns:repeat(2,minmax(0,1fr))}.batteryGridTwoUp{grid-template-columns:minmax(0,.95fr) minmax(0,1.05fr)}.disabledAssetLead{display:flex;align-items:center;gap:10px}.disabledAssetLead .solarLoadIcon{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;background:#f4f6f8;flex:0 0 auto}.disabledAssetLead .solarLoadIcon.disabled{background:#f1f5f9;color:#64748b}.disabledAssetLead small{display:block;color:var(--muted);font-size:9.5px;margin-top:2px}@media(max-width:700px){.flowDetailsGridTwoUp,.batteryGridTwoUp{grid-template-columns:1fr}}.empty.compact{padding:10px;margin-top:6px}@media(max-width:700px){.hiTabSimpleBadge{font-size:9px;padding:4px 7px;max-width:128px}.hiTabStatusItem{min-height:54px;padding:8px 9px}}:host{--hi-page-max:1500px;--hi-hero-h-desktop:184px;--hi-hero-h-tablet:170px;--hi-hero-h-phone:148px;--hi-status-h:58px;--hi-touch:44px}@media(max-width:700px){.tabs{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));overflow:visible;white-space:normal;gap:4px;padding:5px;scroll-snap-type:none;-webkit-overflow-scrolling:auto;overscroll-behavior:auto}.tab{width:100%;min-width:0;min-height:38px;padding:6px 3px;font-size:10px;line-height:1.05;white-space:normal;text-align:center;scroll-snap-align:none}}.energy{max-width:var(--hi-page-max);margin:0 auto;box-sizing:border-box}.tabs{overflow-x:auto;overflow-y:hidden;scrollbar-width:none;-webkit-overflow-scrolling:touch;overscroll-behavior-inline:contain;scroll-snap-type:none;white-space:nowrap}.tabs::-webkit-scrollbar{display:none}.tab{flex:0 0 auto;min-height:var(--hi-touch);scroll-snap-align:none}.hiTabStatusItem{min-height:var(--hi-status-h);height:var(--hi-status-h);box-sizing:border-box}.hiTabStatusItem b,.hiTabStatusItem small{min-width:0}.panel>h2+.goalGrid,.panel>p+.goalGrid{margin-top:6px}details.advanced>summary,.advanced summary{min-height:var(--hi-touch);display:flex;align-items:center;box-sizing:border-box}.hiRuntimeFooter{display:flex;flex-wrap:wrap;gap:4px 6px;line-height:1.35}/* Overview retains the agreed source → intelligence → demand model on normal tablet landscape and desktop. *//* Tablet: compact header, deliberate two-column content, no desktop overflow. */@media(min-width:701px) and (max-width:1100px){.energy{padding:16px 18px 28px}.top{margin-bottom:10px}.tabs{margin-bottom:12px}.hiTabStatusItem{padding:8px 9px}.hiTabStatusItem b{font-size:15px}.hiTabStatusItem small{font-size:9.5px}.panel{padding:13px}.flowCanvas{grid-template-columns:minmax(150px,.85fr) minmax(260px,1.2fr) minmax(150px,.85fr)}.solarMainGrid{grid-template-columns:minmax(0,1fr) minmax(250px,34%)}.valueGrid,.intelligenceGrid,.batteryGrid,.consumerGrid,.strategyGrid,.meteringGrid{grid-template-columns:repeat(2,minmax(0,1fr))}}/* Phone: one coherent page rhythm, compact 2×2 signals and safe controls. */@media(max-width:700px){.energy{padding:10px 10px 22px;border-radius:0}.top{margin-bottom:8px}.top h1{font-size:25px}.top p{font-size:12px}.tabs{gap:2px;padding:4px;margin:5px 0 10px;border-radius:14px}.tab{padding:9px 12px;font-size:12px}.hiTabStatusItem{height:56px;min-height:56px;padding:7px 8px}.hiTabStatusItem b{font-size:15px}.hiTabStatusItem small{font-size:9px}.panel{padding:11px}.panel h2{font-size:16px}.flowCanvas{grid-template-columns:1fr}.flowCenter{order:-1;min-height:180px}.flowColumn{min-width:0}.solarMainGrid,.valueGrid,.intelligenceGrid,.batteryGrid,.consumerGrid,.strategyGrid,.meteringGrid,.flowDetailsGrid{grid-template-columns:1fr}.goalGrid{grid-template-columns:1fr}.solarLoadCard{grid-template-columns:minmax(0,1fr) auto}.solarLoadCard>*:nth-child(n/**/+3){grid-column:1/-1}.editField input,.editField select,select,button{min-height:var(--hi-touch)}.hiRuntimeFooter .runtimeStatus{flex-basis:100%}}@media(max-width:390px){.hiTabStatusItem{grid-template-columns:27px minmax(0,1fr)}.hiTabStatusIcon{width:27px;height:27px}}:host{--hi-status-h:44px}.hiTabStatusItem{height:44px;min-height:44px;padding:5px 7px;grid-template-columns:24px minmax(0,1fr);gap:6px;border-radius:10px}.hiTabStatusIcon{width:24px;height:24px;border-radius:7px;font-size:12px}.hiTabStatusItem small{font-size:8.5px;line-height:1.05;margin:0}.hiTabStatusItem b{font-size:14px;line-height:1.05;margin:1px 0 0}.hiTabStatusItem span:not(.hiTabStatusIcon){font-size:8.5px;line-height:1.05;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.hiTabStatusItem .statusBadge,.hiTabStatusItem .qualityChip{font-size:7px;padding:2px 4px}.hiQuickActionItems{gap:6px}.hiQuickAction,.hiQuickSelect select,.hiQuickActionItems button{min-height:36px;height:36px;padding:6px 12px;border-radius:10px;font-size:11px}.hiUnderstandingFooter{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:12px;margin-top:10px;padding:12px 14px;border-radius:14px;min-height:0}.hiUnderstandingCopy{min-width:0}.hiUnderstandingFooter small{display:block;font-size:8.5px;letter-spacing:.1em;margin:0 0 3px}.hiUnderstandingFooter h2{font-size:15px;line-height:1.25;margin:0}.hiUnderstandingFooter p{font-size:10.5px;line-height:1.3;margin:3px 0 0;color:var(--muted)}.hiUnderstandingFooter>details{margin:0;min-width:150px}.hiUnderstandingFooter>details>summary{min-height:36px;padding:7px 10px;border-radius:10px;font-size:10.5px;white-space:nowrap}.hiUnderstandingFooter>details[open]{grid-column:1/-1;width:100%;margin-top:2px}@media(max-width:700px){:host{--hi-status-h:42px}.hiTabStatusItem{height:42px;min-height:42px;padding:4px 6px;grid-template-columns:22px minmax(0,1fr);gap:5px}.hiTabStatusIcon{width:22px;height:22px;font-size:11px}.hiTabStatusItem small,.hiTabStatusItem span:not(.hiTabStatusIcon){font-size:8px}.hiTabStatusItem b{font-size:13px}.hiQuickAction,.hiQuickSelect select,.hiQuickActionItems button{height:34px;min-height:34px;padding:5px 10px}.hiUnderstandingFooter{grid-template-columns:1fr auto;padding:10px 11px;gap:8px}.hiUnderstandingFooter h2{font-size:13.5px}.hiUnderstandingFooter p{font-size:9.5px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.hiUnderstandingFooter>details{min-width:0}.hiUnderstandingFooter>details>summary{height:34px;min-height:34px;padding:6px 8px;font-size:0}.hiUnderstandingFooter>details>summary:after{content:"Details ›";font-size:10px}.hiUnderstandingFooter>details[open]{grid-column:1/-1}}:host{
        --hi-type-display:clamp(26px,3vw,38px);
        --hi-type-hero:clamp(20px,2.1vw,29px);
        --hi-type-section:16px;
        --hi-type-card:13px;
        --hi-type-body:11.5px;
        --hi-type-caption:9.5px;
        --hi-type-footer:9px;
        --hi-leading-tight:1.18;
        --hi-leading-body:1.42;
        --hi-space-xs:4px;
        --hi-space-sm:8px;
        --hi-space-md:12px;
        --hi-space-lg:16px;
      }.panel>h2,.panel>div>h2,.consumerExplorerHeader h2,.strategyTableHead h2{font-size:var(--hi-type-section);line-height:1.22;font-weight:640;letter-spacing:-.01em}.panel p,.panel>div>p{font-size:var(--hi-type-body);line-height:var(--hi-leading-body)}.panel small,.panel em{font-size:var(--hi-type-caption);line-height:1.3}.hiRuntimeFooter{margin-top:7px;padding:4px 2px;border:0;background:transparent;justify-content:center;color:#94a3b8;font-size:var(--hi-type-footer);line-height:1.2;opacity:.82}.rhiUxFooter{display:flex;justify-content:center;align-items:center;flex-wrap:wrap;gap:5px 10px;margin:10px 3px 0;padding:7px 4px;border:0;background:transparent;color:#64748b;font-size:11px;font-weight:520;line-height:1.35;opacity:1;white-space:normal;overflow:visible;text-overflow:clip}.rhiUxFooter>span+span:before{content:"·";margin-right:10px;color:#cbd5e1}.rhiUxFooterDetails{position:relative;margin:0}.rhiUxFooterDetails>summary{list-style:none;cursor:pointer;display:inline-flex;align-items:center;gap:4px;white-space:nowrap}.rhiUxFooterDetails>summary::-webkit-details-marker{display:none}.rhiUxFooterDetails>summary:after{content:"▾";font-size:9px;color:currentColor}.rhiUxFooterDetails[open]>summary:after{content:"▴"}.rhiUxFooterIssue{font-weight:700}.rhiUxFooterIssue.warning{color:#9a6700}.rhiUxFooterIssue.error{color:#b42318}.rhiUxFooterPanel{flex-basis:100%;width:min(720px,calc(100vw - 48px));box-sizing:border-box;margin:7px auto 2px;padding:10px 12px;border:1px solid #dbe5f0;border-radius:10px;background:#fff;color:#334155;font-size:11px;line-height:1.4;box-shadow:0 8px 20px rgba(15,23,42,.06)}.rhiUxFooterPanelMeta{font-size:10px;font-weight:650;color:#64748b;margin-bottom:6px}.rhiUxFooterProblem{display:grid;grid-template-columns:8px minmax(0,1fr);gap:7px;align-items:start;padding:3px 0}.rhiUxFooterProblemDot{width:6px;height:6px;margin-top:5px;border-radius:50%;background:#d97706}.rhiUxFooterAction{margin-top:7px;padding-top:7px;border-top:1px solid #eef2f7;color:#475569;font-weight:600}@media(max-width:700px){.rhiUxFooter{font-size:10.5px;gap:4px 8px;padding:6px 3px}.rhiUxFooter>span+span:before{margin-right:8px}.rhiUxFooterPanel{width:min(100%,calc(100vw - 28px));font-size:10.5px}}
/* Consumers: one filter surface, compact rows, details on demand */.consumerExplorer{padding:10px}.consumerExplorerHeader{margin-bottom:6px}.consumerExplorerHeader p{margin:2px 0 0}.consumerExplorerList{display:grid;gap:5px}.consumerExplorerCard.compact{padding:0;border-radius:10px;overflow:hidden}.consumerExplorerHead{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:10px;padding:8px 10px;min-height:44px}.consumerExplorerHead h3{font-size:12px;line-height:1.2;margin:0 0 2px;font-weight:630}.consumerExplorerHead p{font-size:9.5px;line-height:1.25;margin:0;color:var(--muted)}.consumerReason{display:block;margin-top:3px;font-size:9px;color:#8a5b12;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.consumerExplorerPrimary{display:flex;align-items:baseline;gap:8px;text-align:right}.consumerExplorerPrimary b{font-size:13px;line-height:1}.consumerExplorerPrimary span{font-size:9.5px;color:var(--muted)}.consumerExplorerCard>.hiDetails{margin:0;border-top:1px solid var(--line)}.consumerExplorerCard>.hiDetails summary{border:0;border-radius:0;background:#fbfcfd;padding:6px 10px;font-size:9.5px}.consumerMixSecondary{padding:8px 10px;gap:8px}.consumerMixSecondary>div{padding:5px 7px}/* Strategies and Pricing: one compact set-level editor language */.strategyProfilePicker.compact{display:grid;grid-template-columns:minmax(0,1fr) minmax(190px,280px);gap:10px 16px;align-items:center;padding:11px 13px}.strategyProfilePicker.compact>small{grid-column:1/-1;margin-top:-5px;color:var(--muted);font-style:italic}.strategyProfileSelect{display:grid;grid-template-columns:auto minmax(0,1fr);gap:8px;align-items:center}.strategyProfileSelect>span{font-size:9.5px;color:var(--muted)}.strategyProfileSelect select{width:100%;min-height:36px;border:1px solid var(--line);border-radius:9px;background:#fff;padding:6px 9px;font:inherit;font-size:11px}.profilePickCards{display:none}.effectivePolicyList{display:grid;gap:5px}.effectivePolicyPreview{padding:10px}.effectivePolicyPreview>p{margin:2px 0 7px}.effectivePolicyList .propertyRow,.effectivePolicyList>article,.effectivePolicyList>div{min-height:0;padding:7px 9px;margin:0}.strategyTablePanel,.pricingStrategyPanel{padding:11px}.strategyTableRow{padding:0}.strategyPrimaryRow{grid-template-columns:minmax(130px,1fr) minmax(130px,.8fr);gap:8px 14px;padding:8px 4px}.strategyGuidance{grid-column:1/-1;color:#94a3b8;font-style:italic}/* Intelligence: fixed Risk → Recommendation → Opportunity → Readiness hierarchy */.intelligenceProductGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.intelligenceSignal{padding:14px;min-height:126px;display:flex;flex-direction:column;justify-content:flex-start}.intelligenceSignal>small{font-size:9px;letter-spacing:.11em;text-transform:uppercase;color:var(--muted);font-style:normal;margin-bottom:7px}.intelligenceSignal h2{font-size:17px;line-height:1.22;margin:0 0 6px;font-weight:650;letter-spacing:-.015em}.intelligenceSignal p{font-size:11px;line-height:1.42;margin:0;color:var(--muted)}.intelligenceSignal.recommendation{border-left:3px solid #22c55e}.intelligenceSignal.risk{border-left:3px solid #f59e0b}.intelligenceSignal.opportunity{border-left:3px solid #3b82f6}.intelligenceSignal.readiness{border-left:3px solid #8b5cf6}.intelligenceAssets{grid-column:1/-1;padding:11px}.intelligenceAssetList{display:grid;gap:5px;margin-top:7px}/* Outlook and Solar wording/content density */.outlookHeroFacts>div{padding:8px 10px}.solarPlanStats span{font-size:9.5px}.solarPlanMessage h3{font-size:15px;line-height:1.25}@media(max-width:700px){.intelligenceProductGrid{grid-template-columns:1fr;gap:7px}.intelligenceSignal{min-height:0;padding:11px}.intelligenceSignal h2{font-size:15px}.strategyProfilePicker.compact{grid-template-columns:1fr;padding:10px}.strategyProfilePicker.compact>small{grid-column:1;margin-top:0}.consumerExplorerHead{padding:7px 8px;min-height:40px}.consumerExplorerPrimary{display:grid;gap:2px}.strategyPrimaryRow{grid-template-columns:1fr}.strategyGuidance{grid-column:1}}.retrospectivePage{display:grid;gap:12px}.retroIntro{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:20px;align-items:center;padding:24px;border-radius:16px;background:linear-gradient(135deg,#172554,#312e81 58%,#6d28d9);color:#fff;box-shadow:0 16px 38px rgba(49,46,129,.22)}.retroIntro small,.retroBestNext small{text-transform:uppercase;letter-spacing:.14em;font-size:10px;font-weight:800;opacity:.74}.retroIntro h2{font-size:28px;margin:5px 0 6px}.retroIntro p{max-width:680px;margin:0;color:rgba(255,255,255,.82);line-height:1.5}.retroScoreRing{width:118px;height:118px;border-radius:50%;display:grid;place-content:center;text-align:center;border:9px solid rgba(255,255,255,.22);box-shadow:inset 0 0 0 1px rgba(255,255,255,.22);background:rgba(255,255,255,.08)}.retroScoreRing strong{font-size:38px;line-height:1}.retroScoreRing span{font-size:10px;margin-top:5px;opacity:.72}.retroKpiGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.retroKpiCard{border:1px solid var(--line);border-radius:12px;padding:14px;background:#fff}.retroKpiHead{display:grid;grid-template-columns:32px minmax(0,1fr) auto;gap:10px;align-items:start}.retroKpiHead>span{width:32px;height:32px;border-radius:9px;display:grid;place-items:center;background:#eef2ff}.retroKpiHead h3{font-size:13px;margin:0 0 3px}.retroKpiHead p{font-size:10px;line-height:1.35;margin:0;color:var(--muted)}.retroKpiHead>strong{font-size:25px;color:#312e81}.retroProgress{height:6px;border-radius:999px;background:#eef2f7;overflow:hidden;margin:12px 0 8px}.retroProgress i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#6366f1,#8b5cf6)}.retroKpiCard footer{display:flex;justify-content:space-between;gap:8px;font-size:9px;color:var(--muted)}.retroOpportunityList{display:grid;gap:8px}.retroOpportunity{display:grid;grid-template-columns:34px minmax(0,1fr) auto;gap:10px;align-items:center;border:1px solid var(--line);border-radius:11px;padding:11px 12px;background:#fff}.retroOpportunityIcon{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;background:#fff7ed}.retroOpportunity h3{font-size:12px;margin:0 0 2px}.retroOpportunity p{font-size:10px;margin:0;color:var(--muted)}.retroOpportunity>strong{font-size:11px;color:#7c3aed}.retroLesson{display:grid;grid-template-columns:28px minmax(0,1fr);gap:9px;padding:10px 0;border-bottom:1px solid var(--line)}.retroLesson:last-child{border-bottom:0}.retroLesson>span{width:28px;height:28px;border-radius:50%;display:grid;place-items:center;background:#ecfdf5;color:#047857}.retroLesson b{font-size:12px}.retroLesson p{font-size:10px;margin:2px 0 0;color:var(--muted)}.retroBestNext{padding:22px;background:linear-gradient(135deg,#faf5ff,#eef2ff);border-color:#ddd6fe}.retroBestNext h2{font-size:22px;margin:5px 0}.retroBestNext>p{max-width:760px;color:var(--muted);line-height:1.45}.retroImpact{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:16px}.retroImpact>div{padding:10px;border-radius:10px;background:rgba(255,255,255,.72);border:1px solid rgba(124,58,237,.12)}.retroImpact span{display:block;font-size:9px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}.retroImpact strong{display:block;font-size:14px;margin-top:3px}.retrospectivePage .portalSectionHeader>strong{font-size:12px;color:#5b21b6}@media(max-width:700px){.retroIntro{grid-template-columns:1fr;padding:18px}.retroScoreRing{width:94px;height:94px}.retroKpiGrid,.retroImpact{grid-template-columns:1fr}.retroOpportunity{grid-template-columns:32px minmax(0,1fr)}.retroOpportunity>strong{grid-column:2}.retroIntro h2{font-size:22px}}.outlookSummaryStrip{display:flex;gap:8px;flex-wrap:wrap;background:transparent;border:0;padding:0}.outlookSummaryStrip>div{flex:1 1 180px;min-height:0;padding:9px 12px;border:1px solid var(--line);border-radius:10px;background:#fff}.physicalFlowCanvas{grid-template-columns:minmax(190px,.8fr) minmax(330px,1.35fr) minmax(240px,1fr)}.physicalFlowCenter{background:linear-gradient(135deg,#eefbf6,#edf7ff);border:1px solid #d9e8e2;border-radius:14px;padding:14px}.flowArrow{text-align:center;color:#64748b;font-size:18px;line-height:1}.batteryHero{min-height:0}@media(max-width:1050px){.physicalFlowCanvas{grid-template-columns:1fr 1fr}.physicalFlowCenter{grid-column:1/-1;grid-row:1}}@media(max-width:700px){.physicalFlowCenter{grid-column:auto;grid-row:auto}}.batteryGrid.batteryGridTwoUp{grid-template-columns:minmax(0,.9fr) minmax(0,1.1fr)}.batteryPremium .x{}.batteryPage .summaryRow.four{margin-top:8px}.batteryGrid.batteryGridTwoUp{align-items:start}.batteryGrid.batteryGridTwoUp>.panel{min-height:0}.batteryHero{padding:18px}.batteryHero h2{font-size:18px}.batteryHero p{font-size:11px}.batteryGauge{padding:16px;border-radius:14px}.batteryGauge b{font-size:27px}.batteryGrid .kv{min-height:38px}.batteryGrid .kv span,.batteryGrid .kv b{font-size:12px}.batteryGrid .strategyTablePanel{margin-top:2px}.batteryGrid .strategyTablePanel .strategyTableRow{padding:6px 2px 5px}.batteryGrid .strategyTablePanel .strategySetting,.batteryGrid .strategyTablePanel .strategyReadValue{font-size:11px}@media(max-width:700px){}.flowProductCanvas.flowCanvas{grid-template-columns:minmax(180px,.8fr) minmax(260px,1.1fr) minmax(220px,1fr)}@media(min-width:701px) and (max-width:1050px){.outlookThreeGrid{grid-template-columns:1fr 1fr}.outlookThreeGrid>section:last-child{grid-column:1/-1}.flowProductCanvas.flowCanvas{grid-template-columns:1fr 1fr}.flowProductCanvas .flowHomeCenter{grid-column:1/-1;grid-row:1}}/* Overview Production / Consumption uniformity */

/* R3.94.7 canonical core-tab stylesheet. One selector owner per component. */
.overviewCoreGrid{display:grid;grid-template-columns:minmax(0,1fr) minmax(280px,.92fr) minmax(0,1fr);gap:10px;align-items:start}
.overviewCorePanel{padding:14px;min-height:0}
.overviewRightStack{display:grid;gap:10px;min-width:0;align-content:start}.overviewBatteryChargingPanel{padding:14px;min-width:0}.overviewBatteryChargingPanel .overviewEnergyRow{margin-bottom:0}.overviewRightStack>.panel{width:100%;box-sizing:border-box}
.overviewSectionTitle{display:flex;align-items:center;gap:10px;margin-bottom:9px}
.overviewSectionTitle h2{margin:0;font-size:16px;line-height:1.15;font-weight:570}
.overviewSectionTitle p{margin:2px 0 0;font-size:10.5px;line-height:1.25;color:var(--muted)}
.overviewSectionIcon{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;font-size:17px;flex:0 0 auto;background:#eff6ff;color:#2563eb}
.overviewSectionIcon.orange{background:#fff7ed;color:#ea580c}.overviewSectionIcon.blue{background:#eff6ff;color:#2563eb}
.overviewHouseHero{position:relative;overflow:hidden;height:250px;min-height:250px;padding:0}
.overviewHouseHeroImage{position:absolute;inset:0;background:linear-gradient(180deg,rgba(10,22,37,.08),rgba(10,22,37,.72)),url('/rhi_energy/frontend/assets/heroes/overview-hero.webp') center/cover no-repeat}
.overviewDecisionOverlay{position:absolute;inset:auto 0 0;padding:16px;color:#fff}
.overviewDecisionLabel{font-size:9px;font-weight:750;letter-spacing:.14em}.overviewDecisionOverlay h2{font-size:17px;line-height:1.2;margin:7px 0;color:#fff}.overviewDecisionOverlay p{font-size:10.5px;line-height:1.3;color:rgba(255,255,255,.88);margin:0 0 10px;max-width:42ch}
.overviewDecisionFacts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}.overviewDecisionFacts>div{background:rgba(255,255,255,.92);color:#172033;border-radius:9px;padding:7px}.overviewDecisionFacts small{display:block;color:#64748b;font-size:9px}.overviewDecisionFacts b{display:block;margin-top:2px;font-size:11px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.overviewEnergyRow{display:grid;grid-template-columns:30px minmax(0,1fr) 82px;gap:9px;align-items:center;min-height:48px;padding:8px 9px;margin:5px 0;border:1px solid var(--line);border-radius:10px;background:#fff}
.overviewEnergyIcon{width:28px;height:28px;border-radius:8px;display:grid;place-items:center;background:#eef6ff;font-size:13px}.overviewEnergyCopy{min-width:0}.overviewEnergyCopy b{display:block;font-size:11.5px;line-height:1.2;font-weight:650}.overviewEnergyCopy small{display:block;margin-top:2px;font-size:9.5px;line-height:1.2;color:var(--muted)}.overviewEnergyRow>strong{justify-self:end;min-width:82px;text-align:right;white-space:nowrap;font-size:12px;font-weight:650;font-variant-numeric:tabular-nums}
.overviewEnergyRow.child{margin-left:18px;border-left:2px solid #d9e7f5;background:#f8fbff}.overviewEnergyRow.aggregate{background:#fbfdff}.overviewEnergyRow.total,.overviewEnergyRow.boundary{border-width:0;border-radius:0;background:transparent}.overviewEnergyRow.total{border-top:2px solid #dbe4ef;padding-top:10px;margin-top:9px}.overviewEnergyRow.boundary{border-top:1px solid var(--line);margin-top:8px}.overviewEnergyRow.total .overviewEnergyIcon,.overviewEnergyRow.boundary .overviewEnergyIcon{visibility:hidden}.overviewEnergyRow.total .overviewEnergyCopy b,.overviewEnergyRow.total>strong{font-size:13px}.overviewEnergyRow.boundary .overviewEnergyCopy small{text-transform:uppercase;letter-spacing:.08em}
.overviewSupportFacts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:8px}
.chargingConnectionGrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.chargingConnectionGrid>.empty{grid-column:1/-1}
.flowDetailsGrid.flowDetailsGridTwoUp{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;align-items:stretch}.flowDetailsGrid.flowDetailsGridTwoUp>.panel{min-width:0;height:100%}
/* Battery remains discoverable when bidirectional flow evidence is missing. */
/* Planning controls: planner/provider selection separate from automation mode. */
.rhiPlannerControls{display:flex;flex-wrap:wrap;align-items:center;gap:10px 22px;justify-content:space-between;min-height:52px;padding:9px 12px;margin:6px 0 9px;background:#fff;border:1px solid var(--line);border-radius:10px}
.rhiPlannerControls>div:first-child{display:grid;gap:3px;min-width:0}
.rhiPlannerControls small{font-size:10px;color:var(--muted)}
.rhiPlannerSelect{display:inline-flex;align-items:center;gap:8px;font-size:11px}
.rhiPlannerSelect select{min-height:38px;min-width:140px;max-width:260px;padding:6px 9px;border:1px solid var(--line);border-radius:9px;background:#fff;color:#17305b;font:inherit}
.rhiPlanningBaselineNotice{display:flex;gap:8px;align-items:center;padding:10px 12px;margin:7px 0;border:1px solid #dce7f4;border-radius:10px;background:#f7fbff}
.rhiPlanningBaselineNotice b{font-size:11px;white-space:nowrap}
.rhiPlanningBaselineNotice span{font-size:10.5px;line-height:1.35;color:#53677e}
@media(max-width:700px){.rhiPlannerControls{align-items:stretch;flex-direction:column}.rhiPlannerSelect select{min-width:0;max-width:100%}.rhiPlanningBaselineNotice{flex-direction:column;align-items:flex-start}}
.rhiFlowBatteryPresence{display:flex;align-items:center;flex-wrap:wrap;gap:10px 20px;min-height:66px;padding:10px 12px;margin:8px 0 0;border:1px solid var(--line);border-radius:10px;background:#fbfcff}
.rhiFlowBatteryIdentity{display:flex;align-items:center;gap:9px;min-width:150px;flex:1 1 180px}
.rhiFlowBatteryIdentity b{display:block;font-size:12px;color:#14264a}
.rhiFlowBatteryIdentity small{display:block;font-size:10px;color:var(--muted);margin-top:3px}
.rhiFlowBatteryIcon{width:34px;height:34px;display:grid;place-items:center;border-radius:10px;background:#edf4ff;color:#1467f5;font-size:17px}
.rhiFlowBatteryFacts{display:grid;grid-template-columns:repeat(2,minmax(78px,1fr));gap:12px;flex:1 1 165px}
.rhiFlowBatteryFacts small{display:block;font-size:9.5px;color:var(--muted)}
.rhiFlowBatteryFacts b{display:block;font-size:12px;font-variant-numeric:tabular-nums;margin-top:3px}
.rhiFlowBatteryProof{font-size:10.5px;color:#64748b;flex:1 1 195px;min-width:0}
.rhiFlowBatteryDetails{display:inline-flex;align-items:center;gap:5px;margin-left:auto;height:38px;min-height:38px;padding:0 11px;border:1px solid #dce7f4;border-radius:10px;background:#fff;color:#075fd8;font:inherit;font-size:11px;font-weight:650;cursor:pointer;white-space:nowrap}
.rhiFlowBatteryDetails span{font-size:19px;line-height:1}
@media(max-width:700px){.rhiFlowBatteryPresence{gap:9px;padding:9px}.rhiFlowBatteryFacts{order:2;flex:1 1 100%}.rhiFlowBatteryProof{order:3;flex:1 1 100%}.rhiFlowBatteryDetails{order:4;margin-left:0}}
/* Flow: one Mobility-style consumer identity row with separate measured facts. */
.rhiFlowConsumerList{display:grid;gap:7px}
.rhiFlowConsumerList .rhiFlowConsumerCard{display:grid;grid-template-columns:minmax(175px,1.15fr) minmax(230px,1.3fr) minmax(125px,.8fr) auto;align-items:center;gap:12px;min-height:70px;margin:0;padding:9px 11px;border:1px solid var(--line);border-radius:11px;background:#fff;box-shadow:none}
.rhiFlowConsumerIdentity{display:flex;align-items:center;gap:9px;min-width:0}
.rhiFlowConsumerIdentity>div:last-child{min-width:0}
.rhiFlowConsumerIdentity b{display:block;font-size:12px;line-height:1.25;overflow-wrap:break-word}
.rhiFlowConsumerIdentity small{display:block;margin-top:3px;font-size:10px;color:var(--muted)}
.rhiFlowConsumerCard .flowAssetVisual{width:78px;height:54px;flex:0 0 78px}
.rhiFlowConsumerCard .flowAssetVisual img{max-width:74px;max-height:50px}
.rhiFlowConsumerFacts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;min-width:0}
.rhiFlowConsumerFacts>span{min-width:0;padding:6px 9px}
.rhiFlowConsumerFacts>span+span{border-left:1px solid #e5edf5}
.rhiFlowConsumerFacts small,.rhiFlowConsumerRelation>small{display:block;color:var(--muted);font-size:9px;line-height:1.2}
.rhiFlowConsumerFacts b{display:block;margin-top:4px;font-size:12px;font-weight:650;white-space:nowrap;font-variant-numeric:tabular-nums}
.rhiFlowConsumerRelation{min-width:0;font-size:11px}
.rhiFlowConsumerRelation span{font-size:11px}
.rhiFlowLinkedAsset,.rhiFlowConsumerDetails{display:inline-flex;align-items:center;gap:5px;padding:0;border:0;background:transparent;color:#075fd8;font:inherit;font-size:11px;font-weight:650;cursor:pointer;text-align:left;max-width:100%}
.rhiFlowLinkedAsset{margin-top:5px;white-space:normal;overflow-wrap:break-word}
.rhiFlowLinkedAsset span,.rhiFlowConsumerDetails span{font-size:17px;line-height:1}
.rhiFlowConsumerDetails{justify-self:end;white-space:nowrap;min-height:38px;padding:0 11px;border:1px solid #dce7f4;border-radius:10px;background:#fff}
.rhiFlowLinkedAsset:focus-visible,.rhiFlowConsumerDetails:focus-visible{outline:2px solid #1467f5;outline-offset:2px}
.rhiFlowConnectionDiagnostics{padding:10px 13px;min-width:0}
.rhiFlowConnectionDiagnostics summary{cursor:pointer;color:#526685;font-size:11px;font-weight:650;min-height:26px}
.rhiFlowConnectionDiagnostics>p{font-size:10.5px;color:var(--muted);margin:4px 0 9px}
@media(max-width:1050px){.rhiFlowConsumerList .rhiFlowConsumerCard{grid-template-columns:minmax(0,1fr) minmax(0,1.2fr)}.rhiFlowConsumerRelation{grid-column:1}.rhiFlowConsumerDetails{grid-column:2}.rhiFlowConsumerCard .flowAssetVisual{width:64px;height:48px;flex-basis:64px}.rhiFlowConsumerCard .flowAssetVisual img{max-width:62px;max-height:46px}}
@media(max-width:700px){.rhiFlowConsumerList .rhiFlowConsumerCard{grid-template-columns:1fr;gap:7px}.rhiFlowConsumerRelation,.rhiFlowConsumerDetails{grid-column:1}.rhiFlowConsumerDetails{justify-self:end}.rhiFlowConsumerCard .flowAssetVisual{width:78px;height:54px;flex-basis:78px}}
.flowConnectionCard,.flowPhysicalConsumerCard{display:grid;grid-template-columns:auto minmax(0,1fr) 76px;align-items:center;gap:10px;min-height:64px;padding:9px 10px;margin:6px 0;border:1px solid var(--line);border-radius:10px;background:#fff;box-sizing:border-box}.flowAssetVisual{width:54px;height:46px;display:flex;align-items:center;justify-content:center;border-radius:9px;background:#f5f7fa;overflow:hidden}.flowAssetVisual img{display:block;max-width:50px;max-height:42px;object-fit:contain}.flowConnectionCard>div,.flowPhysicalConsumerCard>div{min-width:0}.flowConnectionCard b,.flowPhysicalConsumerCard b{display:block;font-size:12.5px;line-height:1.2;font-weight:600}.flowConnectionCard span,.flowPhysicalConsumerCard span{display:block;margin-top:3px;font-size:10.5px;line-height:1.25;color:var(--muted);white-space:normal}.flowConnectionCard strong,.flowPhysicalConsumerCard strong{min-width:76px;text-align:right;font-size:12.5px;line-height:1.2;font-weight:600;font-variant-numeric:tabular-nums;white-space:nowrap}.flowConnectionCard small{display:block;margin-top:4px;font-size:9.5px;color:var(--muted)}
.batteryContributorList{display:grid;gap:10px}.batteryContributorCard{display:grid;grid-template-columns:112px minmax(0,1fr);align-items:stretch;min-height:148px;border:1px solid var(--line);border-radius:14px;background:linear-gradient(180deg,#fff,#fbfcfe);overflow:hidden}.batteryContributorVisual{display:flex;align-items:center;justify-content:center;padding:10px;background:linear-gradient(180deg,#f7f9fb,#eef2f5);overflow:hidden}.batteryContributorVisual .assetVisual{width:88px;height:108px;max-width:88px;max-height:108px;padding:5px;box-sizing:border-box;border:0;background:transparent;overflow:hidden}.batteryContributorVisual .assetVisual img{display:block;width:100%;height:100%;max-width:100%;max-height:100%;object-fit:contain;object-position:center center}.batteryContributorBody{min-width:0;padding:13px 14px;display:flex;flex-direction:column;justify-content:center;gap:7px}.batteryContributorHeader{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.batteryContributorHeader>div{min-width:0}.batteryContributorHeader b{display:block;font-size:14px;line-height:1.2;white-space:normal;overflow-wrap:anywhere}.batteryContributorHeader strong{flex:0 0 auto;font-size:22px;line-height:1;font-variant-numeric:tabular-nums}.batteryHealth{display:inline-flex;margin-top:5px;padding:3px 7px;border-radius:999px;background:#eef8f2;color:#2f6d4b;font-size:10px;font-weight:700}.batteryContributorMeta{display:flex;justify-content:space-between;gap:10px;font-size:11px;color:#526178}.batteryContributorMeta b{font-size:12px;color:#172033;font-variant-numeric:tabular-nums}.batteryContributorFacts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:5px}.batteryContributorFacts span{min-width:0;padding:6px 7px;border-radius:8px;background:#f8fafc}.batteryContributorFacts small,.batteryContributorFacts b{display:block}.batteryContributorFacts small{font-size:8px;color:#64748b}.batteryContributorFacts b{font-size:10.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.batteryContributorState{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:center;gap:8px;min-width:0}.batteryContributorState span{font-size:10.5px;font-weight:700;color:#265c3b;white-space:nowrap}.batteryContributorState small{min-width:0;font-size:10px;line-height:1.25;color:var(--muted);white-space:normal}.batteryContributorCard .bar{margin-top:2px}
@media(max-width:1050px){.overviewCoreGrid{grid-template-columns:1fr 1fr}.overviewDecisionPanel{grid-column:1/-1;grid-row:1}.chargingConnectionGrid{grid-template-columns:1fr}.batteryContributorCard{grid-template-columns:104px minmax(0,1fr)}.batteryContributorVisual .assetVisual{width:80px;height:102px;max-width:80px;max-height:102px}.batteryContributorFacts{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:700px){.overviewCoreGrid,.overviewSupportFacts{grid-template-columns:1fr}.overviewDecisionPanel{grid-column:auto;grid-row:auto}.overviewHouseHero{height:220px;min-height:220px}.overviewEnergyRow{grid-template-columns:28px minmax(0,1fr) 76px}.overviewEnergyRow>strong{min-width:76px}.overviewEnergyRow.child{margin-left:12px}.batteryContributorCard{grid-template-columns:88px minmax(0,1fr);min-height:126px}.batteryContributorVisual{padding:7px}.batteryContributorVisual .assetVisual{width:68px;height:88px;max-width:68px;max-height:88px;padding:3px}.batteryContributorBody{padding:11px 12px}.batteryContributorHeader b{font-size:13px}.batteryContributorHeader strong{font-size:20px}.batteryContributorState{grid-template-columns:1fr}.batteryContributorState small{font-size:9.5px}.batteryContributorFacts{grid-template-columns:repeat(2,minmax(0,1fr))}.batteryContributorFacts span:last-child:nth-child(odd){grid-column:1/-1}}

      @media(max-width:700px){.flowDetailsGrid.flowDetailsGridTwoUp,.chargingConnectionGrid{grid-template-columns:1fr}}


`;
    }
  }

  // Preserve both established card identities without patching another bundle's prototype.
  if (!customElements.get('homebrain-energy-card')) {
    customElements.define('homebrain-energy-card', HomeBrainEnergyCard);
  }
  if (!customElements.get('homebrain-energy-domain-card')) {
    customElements.define('homebrain-energy-domain-card', class extends HomeBrainEnergyCard {});
  }
  if (typeof window !== 'undefined') {
    window.customCards = window.customCards || [];
    if (!window.customCards.some(card => card.type === 'homebrain-energy-card')) {
      window.customCards.push({type: 'homebrain-energy-card', name: 'RHI Energy', description: 'RHI Energy dashboard', preview: false});
    }
  }
})();
