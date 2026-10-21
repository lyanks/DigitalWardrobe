// Drag an outfit from the side panel onto a day of the calendar.
//
// When you drop it, we send {outfit_id, date} to the JSON API with fetch().
// Flask saves it and answers with the HTML of the new calendar entry,
// which we put into that day. No page reload.

const calendar = document.querySelector("[data-schedule-url]");

if (calendar) {
  const status = document.querySelector(".planner-status");
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

  // 1. Start dragging a chip: remember which outfit it is.
  document.querySelectorAll(".outfit-chip").forEach((chip) => {
    chip.addEventListener("dragstart", (event) => {
      event.dataTransfer.setData("text/plain", chip.dataset.outfitId);
      event.dataTransfer.effectAllowed = "copy";
    });
  });

  // 2. Moving over a day: say "you may drop here" and highlight it.
  //    One listener on the whole calendar handles every day ("event
  //    delegation"); closest(".day") finds which day the pointer is in.
  calendar.addEventListener("dragover", (event) => {
    const day = event.target.closest(".day");
    if (!day) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    day.classList.add("drop-target");
  });

  calendar.addEventListener("dragleave", (event) => {
    const day = event.target.closest(".day");
    // dragleave also fires when moving between children of the same day.
    if (day && !day.contains(event.relatedTarget)) day.classList.remove("drop-target");
  });

  // 3. Drop: ask Flask to save it, then show it.
  calendar.addEventListener("drop", async (event) => {
    const day = event.target.closest(".day");
    if (!day) return;
    event.preventDefault();
    day.classList.remove("drop-target");

    const outfitId = Number(event.dataTransfer.getData("text/plain"));
    if (!outfitId) return;

    status.textContent = t("Saving…");
    try {
      const response = await fetch(calendar.dataset.scheduleUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({ outfit_id: outfitId, date: day.dataset.date }),
      });
      const data = await response.json();
      if (!response.ok) {
        // 409 "already planned that day", 404, 400... the server says why.
        status.textContent = data.error || t("Couldn't save that.");
        return;
      }
      // 4. Update the page: add the entry Flask rendered for us.
      day.querySelector(".day-entries").insertAdjacentHTML("beforeend", data.html);
      status.textContent = t("Planned “%(name)s” for %(date)s.", { name: data.outfit.name, date: data.date_text });
      // Idea #1: the server noticed you wore the same combo that week.
      if (data.notice) status.textContent += " " + data.notice;
    } catch (error) {
      status.textContent = t("Couldn't reach the server. Try again.");
    }
  });
}
