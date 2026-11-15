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
