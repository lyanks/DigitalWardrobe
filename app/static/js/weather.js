// "Use today's weather" on the Suggest a look page.
//
// The browser asks Open-Meteo (free, no account, no key) for the weather
// where you are, then reloads the page with ?temp=..&rain=.. so the
// server can pick layers. The server never talks to Open-Meteo itself,
// so PythonAnywhere's list of allowed sites doesn't matter.
//
// Your position is kept only in this browser (localStorage), so next time
// the weather loads by itself. "Ignore the weather" forgets it.
(() => {
  const form = document.querySelector("[data-weather-form]");
  if (!form) return;
  const temp = form.querySelector("[data-weather-temp]");
  const rain = form.querySelector("[data-weather-rain]");
  const status = form.querySelector("[data-weather-status]");
  const KEY = "weatherPlace";

  const saved = () => {
    try { return JSON.parse(localStorage.getItem(KEY)); } catch { return null; }
  };
  const remember = (place) => {
    try { localStorage.setItem(KEY, JSON.stringify(place)); } catch { /* private mode */ }
  };
  const forget = () => {
    try { localStorage.removeItem(KEY); } catch { /* private mode */ }
  };

  async function load(place) {
    status.textContent = t("Checking the weather…");
    const url = "https://api.open-meteo.com/v1/forecast"
      + `?latitude=${place.lat.toFixed(2)}&longitude=${place.lon.toFixed(2)}`
      + "&current=apparent_temperature"
      + "&daily=precipitation_probability_max&forecast_days=1&timezone=auto";
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(response.status);
      const data = await response.json();
      temp.value = Math.round(data.current.apparent_temperature);
      rain.value = data.daily.precipitation_probability_max[0] ?? 0;
      form.submit();
    } catch {
      status.textContent = t("Couldn't get the weather. Try again later.");
    }
  }

  function locate() {
    if (!navigator.geolocation) {
      status.textContent = t("This browser can't share your location.");
      return;
    }
    status.textContent = t("Finding where you are…");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        // Two decimals is about 1 km: enough for weather, not your street.
        const place = {lat: position.coords.latitude, lon: position.coords.longitude};
        remember(place);
        load(place);
      },
      () => { status.textContent = t("No location, so no weather. Seasons still work."); },
      {timeout: 10000, maximumAge: 3600000},
    );
  }

  form.querySelector("[data-weather-on]")?.addEventListener("click", locate);
  form.querySelector("[data-weather-off]")?.addEventListener("click", () => {
    forget();
    temp.value = "";
    rain.value = "";
    form.submit();
  });

  // Weather used before, but not on this page yet: load it by itself.
  const place = saved();
  if (place && !temp.value) load(place);
})();
