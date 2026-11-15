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
