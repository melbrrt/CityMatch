document.addEventListener('DOMContentLoaded', () => {

  // ================= HELPERS =================
  const normalize = s =>
    s ? s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase() : '';

  // ================= DOM =================
  const interestBar = document.getElementById('interest-bar');
  const preferencePanel = document.getElementById('preference-panel');
  const preferenceOptions = document.getElementById('preference-options');
  const whyCityPanel = document.getElementById('why-city-panel');

  const searchInput = document.getElementById('search-input');
  const searchButton = document.getElementById('search-button');
  const eventListContainer = document.getElementById('event-list-container');
  const cityResultsContainer = document.getElementById('city-results-container');
  const dateStartInput = document.getElementById('date-start');
  const dateEndInput = document.getElementById('date-end');
  const sortButton = document.getElementById('sort-date-button');
  const darkToggle = document.getElementById('dark-toggle');

  // ================= STATE =================
  let selectedInterests = [];
  let preferredInterest = null;
  let selectedCity = null;
  let sortByDate = false;
  let lastEvents = [];

  // ================= DARK MODE =================
  darkToggle.addEventListener('click', () => {
    document.body.classList.toggle('dark');
    darkToggle.textContent = document.body.classList.contains('dark')
      ? 'Mode clair ☀️'
      : 'Mode sombre 🌙';
  });

  // ================= TRI =================
  sortButton.addEventListener('click', () => {
    sortByDate = !sortByDate;
    sortButton.textContent = sortByDate ? 'Trier : Date ↑' : 'Trier';
    searchEvents();
  });

  // ================= INTÉRÊTS =================
  fetch('/api/categories')
    .then(res => res.json())
    .then(categories => {
      interestBar.innerHTML = '';

      categories.forEach(cat => {
        const btn = document.createElement('button');
        btn.className = 'interest-btn';
        btn.textContent = cat;
        btn.dataset.interest = normalize(cat);

        btn.addEventListener('click', () => {
          btn.classList.toggle('active');
          selectedCity = null;
          preferredInterest = null;

          selectedInterests = [...interestBar.querySelectorAll('.interest-btn.active')]
            .map(b => b.dataset.interest);

          updatePreferencePanel();
          searchEvents();
        });

        interestBar.appendChild(btn);
      });
    });

  // ================= PRÉFÉRENCE =================
  function updatePreferencePanel() {
    preferenceOptions.innerHTML = '';

    if (selectedInterests.length <= 1) {
      preferencePanel.classList.add('hidden');
      return;
    }

    preferencePanel.classList.remove('hidden');

    selectedInterests.forEach(interest => {
      const opt = document.createElement('div');
      opt.className = 'preference-option';
      opt.textContent = interest;

      if (interest === preferredInterest) opt.classList.add('active');

      opt.addEventListener('click', () => {
        preferredInterest = interest;
        updatePreferencePanel();
        searchEvents();
      });

      preferenceOptions.appendChild(opt);
    });
  }

  // ================= QUERY =================
  function buildQueryParams(includeCity = true) {
    const params = new URLSearchParams();

    const weighted = selectedInterests.map(i =>
      `${i}:${i === preferredInterest ? 2 : 1}`
    );

    if (weighted.length) params.set('interests', weighted.join(','));
    if (searchInput.value.trim()) params.set('q', searchInput.value.trim());
    if (dateStartInput.value) params.set('start_date', dateStartInput.value);
    if (dateEndInput.value) params.set('end_date', dateEndInput.value);
    if (sortByDate) params.set('sort', 'date');
    if (includeCity && selectedCity) params.set('city', selectedCity);

    return params.toString();
  }

  // ================= EVENT CARD =================
  function createEventCard(e) {
    const card = document.createElement('div');
    card.className = 'event-card';

    card.innerHTML = `
      <div class="meta">
        <div class="small">
          ${e.DateTime_start ? new Date(e.DateTime_start).toLocaleDateString('fr-FR') : 'N/A'}
        </div>
        <div class="small">${e.City || ''}</div>
      </div>

      <div style="flex:1">
        <h3>${e.EventName || 'Sans titre'}</h3>
        <p>${e.Description ? e.Description.slice(0, 180) + '…' : 'Pas de description.'}</p>

        ${e.Category ? `<div class="tags"><span class="tag">${e.Category}</span></div>` : ''}
        ${e.Link
          ? `<a class="small" href="${e.Link}" target="_blank">Voir la source ↗</a>`
          : e.Source ? `<div class="small muted">${e.Source}</div>` : ''}
      </div>
    `;

    return card;
  }

  // ================= WHY CITY (BARRES) =================
  function renderWhyCity(cityName) {
    const cityEvents = lastEvents.filter(e => e.City === cityName);

    if (!cityEvents.length) {
      whyCityPanel.innerHTML = '<div class="small">Aucune donnée.</div>';
      return;
    }

    const counts = {};
    selectedInterests.forEach(i => counts[i] = 0);

    cityEvents.forEach(e => {
      if (!e.Category) return;
      const cat = normalize(e.Category);
      selectedInterests.forEach(i => {
        if (cat.includes(i)) counts[i]++;
      });
    });

    const entries = Object.entries(counts).filter(([, v]) => v > 0);
    if (!entries.length) {
      whyCityPanel.innerHTML = '<div class="small">Aucun événement correspondant.</div>';
      return;
    }

    const max = Math.max(...entries.map(e => e[1]));

    let html = `<h4>🎯 Pourquoi ${cityName} ?</h4>`;
    entries.forEach(([k, v]) => {
      const pct = Math.round((v / max) * 100);
      html += `
        <div class="city-bar">
          <div class="city-bar-label">
            <span>${k}</span><span>${v}</span>
          </div>
          <div class="city-bar-track">
            <div class="city-bar-fill" style="width:${pct}%"></div>
          </div>
        </div>
      `;
    });

    whyCityPanel.innerHTML = html;
  }

  // ================= SEARCH =================
  function searchEvents() {
  // Fade-out des cartes existantes
  const existingCards = eventListContainer.querySelectorAll('.event-card');
  existingCards.forEach(card => card.classList.add('fade-out'));

  // Petit délai pour laisser l’animation se faire
  setTimeout(() => {
    eventListContainer.innerHTML = '<div class="small">Chargement…</div>';
    cityResultsContainer.innerHTML = '<div class="small">Chargement…</div>';

    fetch(`/api/smart-search?${buildQueryParams(true)}`)
      .then(res => res.json())
      .then(events => {
        lastEvents = events;
        eventListContainer.innerHTML = '';

        if (!events.length) {
          eventListContainer.innerHTML =
            '<div class="small">Aucun événement trouvé.</div>';
          return;
        }

        events.slice(0, 60).forEach(ev => {
          const card = createEventCard(ev);
          card.classList.add('fade-in');
          eventListContainer.appendChild(card);
        });
      });

    fetch(`/api/cities-by-llm?${buildQueryParams(false)}`)
      .then(res => res.json())
      .then(renderCities);

  }, 200);
}


  // ================= CITIES =================
  function renderCities(cities) {
  cityResultsContainer.innerHTML = '';

  if (!cities.length) {
    cityResultsContainer.innerHTML = '<div class="small">-</div>';
    return;
  }

  cities.slice(0, 8).forEach(c => {
    const div = document.createElement('div');
    div.className = 'city-pill';

    if (selectedCity === c.City) {
      div.classList.add('active');
    }

    div.innerHTML = `
      <span>${c.City}</span>
      <span class="small">${c.count}</span>
    `;

    div.addEventListener('click', () => {
      selectedCity = c.City;

      //  MET À JOUR LES COULEURS
      document.querySelectorAll('.city-pill').forEach(p =>
        p.classList.remove('active')
      );
      div.classList.add('active');

      renderWhyCity(c.City);
    });

    cityResultsContainer.appendChild(div);
  });
}

  // ================= INIT =================
  searchButton.addEventListener('click', searchEvents);
  searchInput.addEventListener('keydown', e => e.key === 'Enter' && searchEvents());
  searchEvents();
});
