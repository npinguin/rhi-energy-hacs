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
