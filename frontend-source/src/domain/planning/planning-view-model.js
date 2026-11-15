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
