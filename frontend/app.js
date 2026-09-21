// Point this at wherever the FastAPI backend is actually running.
const API_BASE_URL = window.API_BASE_URL || "http://localhost:8000";
const REQUEST_TIMEOUT_MS = 40000;

// A representative sample of neighborhoods actually present in the dataset
// (see scripts/inspect_dataset.py) -- just quick-fill shortcuts, not an
// exhaustive list.
const QUICK_LOCATIONS = [
  "Koramangala",
  "Indiranagar",
  "Whitefield",
  "HSR",
  "Jayanagar",
  "JP Nagar",
];

const els = {
  form: document.getElementById("filterForm"),
  locationInput: document.getElementById("locationInput"),
  locationError: document.getElementById("locationError"),
  cuisineInput: document.getElementById("cuisineInput"),
  ratingSlider: document.getElementById("ratingSlider"),
  ratingOutput: document.getElementById("ratingOutput"),
  extraPreferencesInput: document.getElementById("extraPreferencesInput"),
  extraPreferencesCount: document.getElementById("extraPreferencesCount"),
  budgetPills: document.getElementById("budgetPills"),
  resetFiltersBtn: document.getElementById("resetFiltersBtn"),
  submitBtn: document.getElementById("submitSearchBtn"),
  submitBtnLabel: document.getElementById("submitBtnLabel"),
  quickLocationChips: document.getElementById("quickLocationChips"),
  errorBanner: document.getElementById("errorBanner"),
  errorBannerText: document.getElementById("errorBannerText"),
  infoBanner: document.getElementById("infoBanner"),
  infoBannerText: document.getElementById("infoBannerText"),
  warningBanner: document.getElementById("warningBanner"),
  aiSummaryCard: document.getElementById("aiSummaryCard"),
  aiSummaryText: document.getElementById("aiSummaryText"),
  idleView: document.getElementById("idleView"),
  skeletonView: document.getElementById("skeletonView"),
  skeletonGrid: document.getElementById("skeletonGrid"),
  emptyStateView: document.getElementById("emptyStateView"),
  emptyStateTitle: document.getElementById("emptyStateTitle"),
  emptyStateText: document.getElementById("emptyStateText"),
  resultsSection: document.getElementById("resultsSection"),
  resultsMeta: document.getElementById("resultsMeta"),
  resultsGrid: document.getElementById("resultsGrid"),
  apiStatusDot: document.getElementById("apiStatusDot"),
  apiStatusText: document.getElementById("apiStatusText"),
};

let selectedBudget = "";

function initQuickLocationChips() {
  QUICK_LOCATIONS.forEach((name) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = name;
    btn.className =
      "font-label-sm text-label-sm px-2.5 py-1 rounded-full bg-surface-container-high hover:bg-surface-container-highest text-on-surface-variant hover:text-primary transition-colors";
    btn.addEventListener("click", () => {
      els.locationInput.value = name;
      els.locationInput.focus();
    });
    els.quickLocationChips.appendChild(btn);
  });
}

function initBudgetPills() {
  const pills = els.budgetPills.querySelectorAll(".budget-pill");
  pills.forEach((pill) => {
    pill.addEventListener("click", () => {
      pills.forEach((p) => {
        p.classList.remove(
          "bg-primary-container",
          "text-on-primary-container",
          "font-bold"
        );
        p.classList.add("text-outline");
      });
      pill.classList.remove("text-outline");
      pill.classList.add(
        "bg-primary-container",
        "text-on-primary-container",
        "font-bold"
      );
      selectedBudget = pill.dataset.budget;
    });
  });
}

function initRatingSlider() {
  els.ratingSlider.addEventListener("input", (e) => {
    const value = parseFloat(e.target.value);
    els.ratingOutput.textContent =
      value <= 0 ? "Any rating" : `${value.toFixed(1)} ★ and above`;
  });
}

function initExtraPreferences() {
  els.extraPreferencesInput.addEventListener("input", () => {
    els.extraPreferencesCount.textContent = `${els.extraPreferencesInput.value.length} / 500`;
  });

  document.querySelectorAll(".quick-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const current = els.extraPreferencesInput.value.trim();
      const text = chip.textContent.trim();
      els.extraPreferencesInput.value = current ? `${current}, ${text}` : text;
      els.extraPreferencesInput.dispatchEvent(new Event("input"));
    });
  });
}

function resetForm() {
  els.locationInput.value = "";
  els.cuisineInput.value = "";
  els.extraPreferencesInput.value = "";
  els.extraPreferencesInput.dispatchEvent(new Event("input"));
  els.ratingSlider.value = 0;
  els.ratingSlider.dispatchEvent(new Event("input"));
  els.locationError.classList.add("hidden");

  const pills = els.budgetPills.querySelectorAll(".budget-pill");
  pills.forEach((p, idx) => {
    if (idx === 0) {
      p.classList.add("bg-primary-container", "text-on-primary-container", "font-bold");
      p.classList.remove("text-outline");
    } else {
      p.classList.remove("bg-primary-container", "text-on-primary-container", "font-bold");
      p.classList.add("text-outline");
    }
  });
  selectedBudget = "";

  hideAllResultViews();
  els.idleView.classList.remove("hidden");
}

function hideAllResultViews() {
  els.idleView.classList.add("hidden");
  els.skeletonView.classList.add("hidden");
  els.emptyStateView.classList.add("hidden");
  els.resultsSection.classList.add("hidden");
  els.aiSummaryCard.classList.add("hidden");
  els.errorBanner.classList.add("hidden");
  els.infoBanner.classList.add("hidden");
  els.warningBanner.classList.add("hidden");
}

function renderSkeleton() {
  els.skeletonGrid.innerHTML = "";
  for (let i = 0; i < 3; i++) {
    const card = document.createElement("div");
    card.className =
      "bg-surface-container rounded-2xl p-space-md flex flex-col gap-space-md animate-pulse";
    card.innerHTML = `
      <div class="h-5 w-2/3 bg-surface-container-highest rounded-md"></div>
      <div class="h-4 w-1/3 bg-surface-container-highest rounded-md"></div>
      <div class="space-y-2 pt-2">
        <div class="h-3 w-full bg-surface-container-highest rounded-md"></div>
        <div class="h-3 w-5/6 bg-surface-container-highest rounded-md"></div>
        <div class="h-3 w-4/6 bg-surface-container-highest rounded-md"></div>
      </div>
    `;
    els.skeletonGrid.appendChild(card);
  }
}

function buildPayload() {
  const payload = {
    location: els.locationInput.value.trim(),
    extra_preferences: els.extraPreferencesInput.value.trim(),
  };
  if (selectedBudget) payload.budget = selectedBudget;
  const cuisine = els.cuisineInput.value.trim();
  if (cuisine) payload.cuisine = cuisine;
  const minRating = parseFloat(els.ratingSlider.value);
  if (minRating > 0) payload.min_rating = minRating;
  return payload;
}

function renderRestaurantCard(restaurant) {
  const card = document.createElement("article");
  card.className =
    "flex flex-col bg-surface-container rounded-2xl overflow-hidden shadow-xl hover:shadow-[0_16px_36px_rgba(255,122,69,0.15)] transition-all duration-300 hover:-translate-y-1";

  const cuisineChips = restaurant.cuisine
    .split(",")
    .map((c) => c.trim())
    .filter(Boolean)
    .map(
      (c) =>
        `<span class="font-label-sm text-label-sm bg-surface-container-high text-on-surface-variant px-2 py-0.5 rounded-md">${escapeHtml(c)}</span>`
    )
    .join("");

  card.innerHTML = `
    <div class="relative w-full h-24 bg-gradient-to-br from-primary-container/25 to-secondary-container/15 flex items-center justify-center">
      <span class="material-symbols-outlined text-[36px] text-primary/70">restaurant</span>
      <div class="absolute top-3 right-3 bg-primary-container text-on-primary-container px-2.5 py-1 rounded-full flex items-center gap-1 shadow-md">
        <span class="material-symbols-outlined text-[14px]">star</span>
        <span class="font-label-sm text-label-sm font-bold">${restaurant.rating.toFixed(1)} ★</span>
      </div>
    </div>
    <div class="p-space-md flex flex-col flex-1 gap-space-sm">
      <h3 class="font-headline-sm text-headline-sm text-on-surface">${escapeHtml(restaurant.name)}</h3>
      <div class="flex flex-wrap gap-1">${cuisineChips}</div>
      <div class="font-label-md text-label-md text-secondary">₹${Math.round(restaurant.cost)} for two</div>
      <p class="font-body-md text-body-md text-on-surface-variant mt-1">${escapeHtml(restaurant.explanation)}</p>
    </div>
  `;
  return card;
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function renderResults(data, location) {
  if (!data.location_matched) {
    els.emptyStateTitle.textContent = "No restaurants for that location";
    els.emptyStateText.textContent =
      "This dataset only covers Bangalore neighborhoods (e.g. Koramangala, Indiranagar, Whitefield, HSR, Jayanagar) -- try one of those.";
    els.emptyStateView.classList.remove("hidden");
    return;
  }

  if (data.relaxed_filters && data.relaxed_filters.length > 0) {
    els.infoBannerText.innerHTML = `<span class="font-bold text-tertiary-fixed">Filters relaxed:</span> we couldn't find matches for all your filters, so we relaxed: <span class="text-primary font-semibold">${escapeHtml(data.relaxed_filters.join(", "))}</span>. Showing the closest matches instead.`;
    els.infoBanner.classList.remove("hidden");
  }

  if (data.source === "fallback") {
    els.warningBanner.classList.remove("hidden");
  }

  if (!data.recommendations || data.recommendations.length === 0) {
    els.emptyStateTitle.textContent = "No restaurants matched your preferences";
    els.emptyStateText.textContent = "Try broadening your budget, cuisine, or minimum rating.";
    els.emptyStateView.classList.remove("hidden");
    return;
  }

  if (data.summary) {
    els.aiSummaryText.textContent = data.summary;
    els.aiSummaryCard.classList.remove("hidden");
  }

  els.resultsMeta.textContent = `${data.recommendations.length} restaurant${data.recommendations.length === 1 ? "" : "s"} found near ${location}`;
  els.resultsGrid.innerHTML = "";
  data.recommendations.forEach((r) => els.resultsGrid.appendChild(renderRestaurantCard(r)));
  els.resultsSection.classList.remove("hidden");
}

async function handleSubmit(event) {
  event.preventDefault();

  const location = els.locationInput.value.trim();
  if (!location) {
    els.locationError.classList.remove("hidden");
    return;
  }
  els.locationError.classList.add("hidden");

  const payload = buildPayload();

  hideAllResultViews();
  renderSkeleton();
  els.skeletonView.classList.remove("hidden");
  els.submitBtn.disabled = true;
  els.submitBtn.classList.add("opacity-60", "cursor-not-allowed");
  els.submitBtnLabel.textContent = "Searching...";

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${API_BASE_URL}/recommendations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Request failed (${response.status}): ${text}`);
    }

    const data = await response.json();
    hideAllResultViews();
    renderResults(data, location);
  } catch (err) {
    hideAllResultViews();
    let message = `Request failed: ${err.message}`;
    if (err.name === "AbortError") {
      message = "The recommendation service took too long to respond. Please try again.";
    } else if (err instanceof TypeError) {
      message = `Couldn't reach the recommendation service at ${API_BASE_URL}. Make sure the API is running (\`uvicorn api.main:app\`).`;
    }
    els.errorBannerText.textContent = message;
    els.errorBanner.classList.remove("hidden");
    els.idleView.classList.remove("hidden");
  } finally {
    clearTimeout(timeoutId);
    els.submitBtn.disabled = false;
    els.submitBtn.classList.remove("opacity-60", "cursor-not-allowed");
    els.submitBtnLabel.textContent = "Find Restaurants";
  }
}

async function checkApiHealth() {
  try {
    const response = await fetch(`${API_BASE_URL}/health`, { signal: AbortSignal.timeout(5000) });
    if (response.ok) {
      els.apiStatusDot.className = "relative inline-flex rounded-full h-2 w-2 bg-tertiary";
      els.apiStatusText.textContent = "API Online";
      els.apiStatusText.className = "font-label-sm text-label-sm text-tertiary-fixed";
      return;
    }
  } catch (err) {
    // fall through to offline state below
  }
  els.apiStatusDot.className = "relative inline-flex rounded-full h-2 w-2 bg-error";
  els.apiStatusText.textContent = "API Offline";
  els.apiStatusText.className = "font-label-sm text-label-sm text-error";
}

function init() {
  initQuickLocationChips();
  initBudgetPills();
  initRatingSlider();
  initExtraPreferences();
  els.form.addEventListener("submit", handleSubmit);
  els.resetFiltersBtn.addEventListener("click", resetForm);
  checkApiHealth();
}

init();
