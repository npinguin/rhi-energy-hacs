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
