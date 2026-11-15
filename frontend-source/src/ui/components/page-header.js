// Energy domain adapter onto shared RHI UX Core presentation primitives.
// Page-level header owns Hero, Status and executable Quick Actions only.
// Body-scoped view/filter controls are rendered immediately above the content they govern.
function rhiEnergyPageHeader({
  sectionLabel = "",
  itemLabel = "",
  title = "",
  description = "",
  hero = "",
  metrics = [],
  commandActions = "",
  tone = ""
} = {}) {
  const eyebrow = [sectionLabel, itemLabel].filter(Boolean).join(" / ");
  const heroMarkup = rhiUxPageHero({ eyebrow, title, description, image:hero, imageAlt:"" });
  const statusMarkup = rhiUxStatusGrid((metrics || []).map(([icon,label,value,detail]) => ({
    icon:icon || "•", label:label || "", value:value ?? "—", detail:detail || ""
  })));
  const actionsMarkup = commandActions
    ? `<section class="rhiUxQuickActionBar" aria-label="${rhiUxEscape(rhiEnergyT(null,'common.quick_actions',{},'Quick actions'))}"><small>${rhiUxEscape(rhiEnergyT(null,'common.quick_actions',{},'Quick actions'))}</small><div class="rhiUxQuickActions">${commandActions}</div></section>`
    : "";
  return `<section class="rhiEnergyPageHeader rhiUxPageStack ${rhiUxEscape(tone)}">${heroMarkup}${statusMarkup}${actionsMarkup}</section>`;
}
