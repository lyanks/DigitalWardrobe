// The outfit board on the outfit form: lay your clothes out like a
// Pinterest collage.
//  - Ticking an item in the picker shows its piece on the board.
//  - Drag a piece to move it, pull its corner to resize it.
//  - "Bring to front" / "Send to back" change which piece covers which.
//  - Every change is written as JSON into the hidden "layout" field, and
//    the server saves it with the outfit (services/outfit_board.py).
//
// Positions are in % of the board, never in pixels, so the saved outfit
// looks the same on a phone and on a laptop.

const editor = document.querySelector("[data-board-editor]");

if (editor) {
  const board = editor.querySelector("[data-board]");
  const hint = board.querySelector(".board-hint");
  const layoutInput = editor.closest("form").querySelector('input[name="layout"]');
  const picker = document.querySelector("[data-check-url]");
  const frontButton = editor.querySelector("[data-board-front]");
  const backButton = editor.querySelector("[data-board-back]");
  // item id -> its piece on the board. A Map is a dict, like in Python.
  const pieces = new Map([...board.querySelectorAll(".board-piece")].map((piece) => [piece.dataset.itemId, piece]));
  let selected = null;

  const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
  const round = (value) => Math.round(value * 100) / 100;
  const shown = () => [...pieces.values()].filter((piece) => !piece.hidden);

  // A piece's position lives in its style: left/top/width in %, z-index.
  function read(piece) {
    return {
      x: parseFloat(piece.style.left),
      y: parseFloat(piece.style.top),
      width: parseFloat(piece.style.width),
      layer: Number(piece.style.zIndex),
    };
  }

  function write(piece, spot) {
    piece.style.left = round(clamp(spot.x, -50, 100)) + "%";
    piece.style.top = round(clamp(spot.y, -50, 100)) + "%";
    piece.style.width = round(clamp(spot.width, 5, 100)) + "%";
    piece.style.zIndex = spot.layer;
  }

  // The hidden field the server reads: {"12": {x, y, width, layer}, ...}
  function save() {
    const layout = {};
    for (const piece of shown()) layout[piece.dataset.itemId] = read(piece);
    layoutInput.value = JSON.stringify(layout);
  }

  function select(piece) {
    if (selected) selected.classList.remove("selected");
    selected = piece;
    if (piece) piece.classList.add("selected");
    frontButton.disabled = backButton.disabled = !piece;
  }

  // Show the pieces of the ticked items, hide the rest.
  function showTicked() {
    for (const box of picker.querySelectorAll('input[name="item_ids"]')) {
      const piece = pieces.get(box.value);
      if (piece) piece.hidden = !box.checked;
    }
    hint.hidden = shown().length > 0;
    if (selected && selected.hidden) select(null);
    save();
  }

  // ----- dragging and resizing -----
  // Pointer events work the same for a mouse, a finger and a pen.
  board.addEventListener("pointerdown", (event) => {
    const piece = event.target.closest(".board-piece");
    if (!piece) return select(null); // a click on the empty board
    event.preventDefault(); // no text selection, no image ghost
    select(piece);
    piece.focus();

    const resizing = event.target.classList.contains("board-handle");
    const size = board.getBoundingClientRect(); // the board in pixels, right now
    const start = read(piece);
    const startX = event.clientX;
    const startY = event.clientY;
    // "Capture": the piece keeps getting the moves even when the pointer
    // runs ahead of it, or off the board.
    piece.setPointerCapture(event.pointerId);

    function move(moveEvent) {
      // How far the pointer went, turned from pixels into % of the board.
      const dx = ((moveEvent.clientX - startX) / size.width) * 100;
      const dy = ((moveEvent.clientY - startY) / size.height) * 100;
      if (resizing) write(piece, { ...start, width: start.width + dx });
      else write(piece, { ...start, x: start.x + dx, y: start.y + dy });
    }

    function stop() {
      piece.removeEventListener("pointermove", move);
      piece.removeEventListener("pointerup", stop);
      piece.removeEventListener("pointercancel", stop);
      save();
    }

    piece.addEventListener("pointermove", move);
    piece.addEventListener("pointerup", stop);
    piece.addEventListener("pointercancel", stop);
  });

  // ----- the keyboard does the same, a step at a time -----
  board.addEventListener("keydown", (event) => {
    const piece = event.target.closest(".board-piece");
    if (!piece) return;
    const step = event.shiftKey ? 5 : 1;
    const spot = read(piece);
    const moves = {
      ArrowLeft: { x: spot.x - step },
      ArrowRight: { x: spot.x + step },
      ArrowUp: { y: spot.y - step },
      ArrowDown: { y: spot.y + step },
      "+": { width: spot.width + 2 },
      "=": { width: spot.width + 2 },
      "-": { width: spot.width - 2 },
    };
    if (!(event.key in moves)) return;
    event.preventDefault(); // arrows would scroll the page
    select(piece);
    write(piece, { ...spot, ...moves[event.key] });
    save();
  });
  board.addEventListener("focusin", (event) => {
    const piece = event.target.closest(".board-piece");
    if (piece) select(piece);
  });

  // ----- layers -----
  // Sort the shown pieces back to front, move the chosen one to an end,
  // then number them 1, 2, 3... (that number is the CSS z-index).
  function restack(piece, toFront) {
    const order = shown()
      .filter((other) => other !== piece)
      .sort((a, b) => read(a).layer - read(b).layer);
    if (toFront) order.push(piece);
    else order.unshift(piece);
    order.forEach((other, index) => (other.style.zIndex = index + 1));
    save();
  }

  frontButton.addEventListener("click", () => selected && restack(selected, true));
  backButton.addEventListener("click", () => selected && restack(selected, false));

  // Reset: every shown piece back to its first spot (from data-default,
  // which the server worked out by body slot).
  editor.querySelector("[data-board-reset]").addEventListener("click", () => {
    for (const piece of shown()) write(piece, JSON.parse(piece.dataset.default));
    select(null);
    save();
  });

  picker.addEventListener("change", (event) => {
    if (event.target.name === "item_ids") showTicked();
  });

  // Inspiration: the picked idea shows bigger under the strip, so you can
  // look at it while you arrange the board.
  const preview = editor.parentElement.querySelector(".inspiration-preview");
  function showIdea() {
    const picked = editor.parentElement.querySelector('input[name="idea_id"]:checked');
    const picture = picked && picked.closest("label").querySelector("img");
    preview.hidden = !picture;
    if (picture) {
      preview.referrerPolicy = "no-referrer"; // like the small picture (macros/idea.html)
      preview.src = picture.src;
    }
  }
  if (preview) {
    editor.parentElement.addEventListener("change", (event) => {
      if (event.target.name === "idea_id") showIdea();
    });
    showIdea();
  }
  showTicked(); // the edit page starts with some items ticked
}
