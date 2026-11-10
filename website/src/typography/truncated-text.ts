const labels = document.querySelectorAll<HTMLElement>('[data-truncate]');

if (labels.length > 0) {
  const tooltip = document.createElement('div');
  tooltip.id = 'truncated-text-tooltip';
  tooltip.className = 'text-tooltip';
  tooltip.setAttribute('role', 'tooltip');
  tooltip.hidden = true;
  document.body.append(tooltip);
  let active: HTMLElement | undefined;
  let described: HTMLElement | undefined;

  function hideTooltip(): void {
    tooltip.hidden = true;
    active = undefined;
    if (!described) return;
    const ids = described.getAttribute('aria-describedby')?.split(' ').filter((id) => id !== tooltip.id) ?? [];
    if (ids.length) described.setAttribute('aria-describedby', ids.join(' '));
    else described.removeAttribute('aria-describedby');
    described = undefined;
  }

  function showTooltip(element: HTMLElement): void {
    const text = element.textContent?.trim();
    if (!text || element.scrollWidth <= element.clientWidth) {
      hideTooltip();
      return;
    }
    hideTooltip();
    active = element;
    const control = element.closest('a, button, [tabindex]');
    described = control instanceof HTMLElement ? control : element;
    const ids = described.getAttribute('aria-describedby')?.split(' ') ?? [];
    described.setAttribute('aria-describedby', [...ids, tooltip.id].join(' '));
    tooltip.textContent = text;
    tooltip.hidden = false;
    const bounds = element.getBoundingClientRect();
    const halfWidth = tooltip.offsetWidth / 2;
    const center = Math.max(halfWidth + 8, Math.min(window.innerWidth - halfWidth - 8, bounds.left + bounds.width / 2));
    const top = bounds.bottom + 6 + tooltip.offsetHeight <= window.innerHeight
      ? bounds.bottom + 6
      : Math.max(8, bounds.top - tooltip.offsetHeight - 6);
    tooltip.style.left = `${center}px`;
    tooltip.style.top = `${top}px`;
  }

  function refreshTooltip(): void {
    if (active) showTooltip(active);
  }

  const resizeObserver = new ResizeObserver(refreshTooltip);
  const textObserver = new MutationObserver(refreshTooltip);
  for (const label of labels) {
    const control = label.closest('a, button, [tabindex]') ?? label;
    label.addEventListener('pointerenter', () => showTooltip(label));
    label.addEventListener('pointerleave', hideTooltip);
    control.addEventListener('focus', () => showTooltip(label));
    control.addEventListener('blur', hideTooltip);
    resizeObserver.observe(label);
    textObserver.observe(label, { childList: true, characterData: true, subtree: true });
  }
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') hideTooltip();
  });
  window.addEventListener('scroll', hideTooltip, true);
  window.addEventListener('resize', hideTooltip);
}
