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
