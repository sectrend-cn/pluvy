const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
const header = document.querySelector<HTMLElement>('.page > .header');
const opening = document.querySelector<HTMLElement>('main .content-panel');
const sidebar = document.querySelector<HTMLElement>('#starlight__sidebar');
const headings = Array.from(document.querySelectorAll<HTMLElement>('.sl-markdown-content h2[id], .sl-markdown-content h3[id]'));
let headerMode: 'page' | 'entering' | 'floating' | 'exiting' = 'page';
let headerTimer = 0;
let frameRequested = false;

function updateHeader(): void {
  if (!header || !opening) return;
  const shouldFloat = opening.getBoundingClientRect().bottom <= 0;
  if (shouldFloat && headerMode === 'exiting') {
    window.clearTimeout(headerTimer);
    header.classList.remove('header--exiting');
    headerMode = 'floating';
    return;
  }
  if (shouldFloat && headerMode === 'page') {
    headerMode = 'entering';
    header.classList.add('header--floating', 'header--entering');
    headerTimer = window.setTimeout(() => {
      header.classList.remove('header--entering');
      headerMode = 'floating';
    }, 320);
  } else if (!shouldFloat && headerMode !== 'page') {
    window.clearTimeout(headerTimer);
    headerMode = 'exiting';
    header.classList.remove('header--entering');
    header.classList.add('header--exiting');
    headerTimer = window.setTimeout(() => {
      header.classList.remove('header--floating', 'header--exiting');
      headerMode = 'page';
    }, 120);
  }
}

function updateCurrentSection(): void {
  const line = window.innerHeight * 0.2;
  const current = headings.filter((heading) => heading.getBoundingClientRect().top <= line).at(-1) ?? headings[0];
  if (!current) return;
  document.querySelectorAll<HTMLAnchorElement>('[data-doc-heading]').forEach((link) => {
    if (link.dataset.docHeading === current.id) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  });
  document.querySelectorAll<HTMLAnchorElement>('.right-sidebar-panel a').forEach((link) => {
    if (link.getAttribute('href') === `#${current.id}`) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  });
  document.querySelectorAll<HTMLElement>('[data-current-section]').forEach((label) => {
    label.textContent = current.textContent;
  });
}

function updateSidebarEdges(): void {
  if (!sidebar) return;
  sidebar.toggleAttribute('data-more-above', sidebar.scrollTop > 0);
  sidebar.toggleAttribute('data-more-below', sidebar.scrollTop + sidebar.clientHeight < sidebar.scrollHeight - 1);
}

function update(): void {
  frameRequested = false;
  updateHeader();
  updateCurrentSection();
  updateSidebarEdges();
}

function requestUpdate(): void {
  if (frameRequested) return;
  frameRequested = true;
  requestAnimationFrame(update);
}

function createSidebarArrow(direction: 'above' | 'below'): HTMLButtonElement {
  const button = document.createElement('button');
  button.type = 'button';
  button.tabIndex = -1;
  button.className = `sidebar-scroll-arrow sidebar-scroll-arrow--${direction}`;
  button.setAttribute('aria-hidden', 'true');
  button.textContent = direction === 'above' ? '↑' : '↓';
  button.addEventListener('click', () => {
    if (!sidebar) return;
    sidebar.scrollBy({
      top: (direction === 'above' ? -1 : 1) * sidebar.clientHeight * 0.6,
      behavior: reducedMotion.matches ? 'auto' : 'smooth',
    });
  });
  return button;
}

function initializeSidebar(): void {
  if (!sidebar) return;
  sidebar.prepend(createSidebarArrow('above'));
  sidebar.append(createSidebarArrow('below'));
  sidebar.addEventListener('scroll', requestUpdate, { passive: true });
  try {
    const state = JSON.parse(sessionStorage.getItem('sl-sidebar-state') ?? '{}');
    if (!state.scroll) sidebar.querySelector('[aria-current="page"]')?.scrollIntoView({ block: 'center' });
  } catch {
    sidebar.querySelector('[aria-current="page"]')?.scrollIntoView({ block: 'center' });
  }
  updateSidebarEdges();
}

function initializeSearch(): void {
  document.addEventListener('keydown', (event) => {
    if (event.key !== '/' || event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.target instanceof HTMLElement && (event.target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(event.target.tagName))) return;
    const input = document.querySelector<HTMLInputElement>('.pagefind-ui__search-input');
    if (!input) return;
    event.preventDefault();
    input.focus();
  });
}

function initializeSheets(): void {
  document.querySelectorAll<HTMLButtonElement>('[data-docs-open]').forEach((button) => {
    button.addEventListener('click', () => {
      const dialog = document.getElementById(`docs-sheet-${button.dataset.docsOpen}`);
      if (!(dialog instanceof HTMLDialogElement)) return;
      dialog.showModal();
      requestAnimationFrame(() => dialog.querySelector('[aria-current]')?.scrollIntoView({ block: 'center' }));
    });
  });
  document.querySelectorAll<HTMLDialogElement>('[data-docs-sheet]').forEach((dialog) => {
    dialog.querySelector('[data-docs-close]')?.addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog) dialog.close();
      if (event.target instanceof Element && event.target.closest('a')) dialog.close();
    });
  });
}

window.addEventListener('scroll', requestUpdate, { passive: true });
window.addEventListener('resize', requestUpdate);
initializeSidebar();
initializeSearch();
initializeSheets();
update();
