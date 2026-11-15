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
