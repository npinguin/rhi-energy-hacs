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
