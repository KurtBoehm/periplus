/** Navigate to a target URL without adding a new history entry.
 *  @param {string} target - Destination URL.
 */
function goto(target) {
  history.replaceState(null, "", target);
  window.location.href = target;
}

document.addEventListener("DOMContentLoaded", () => {
  // Arrow elements: click to navigate using goto()
  document.querySelectorAll(".arrow").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      goto(link.href);
    });
  });
});

document.addEventListener(
  "keydown",
  (event) => {
    // ESC: go back in history
    if (event.key === "Escape") history.back();
    // Left arrow: go to previous item (global `ante` URL)
    if (event.key === "ArrowLeft") goto(ante);
    // Right arrow: go to next item (global `post` URL)
    if (event.key === "ArrowRight") goto(post);
  },
  false
);
