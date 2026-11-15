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
