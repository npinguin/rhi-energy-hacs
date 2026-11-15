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
