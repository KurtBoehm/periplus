/** Handle file upload form submission.
 *  - Prevents the default submit
 *  - Appends file last-modified metadata
 *  - POSTs via fetch and reloads the page
 *  @param {SubmitEvent} event
 */
async function handleUploadSubmit(event) {
  event.preventDefault();
  try {
    const formData = new FormData(event.target);

    /** @type {HTMLFormElement} form - The submitted form element */
    const form = event.target;

    /** @type {HTMLInputElement[]} inputs - All INPUT elements in the form */
    const inputs = [...form.elements].filter((e) => e.tagName === "INPUT");
    if (inputs.length != 1)
      throw Error(`Unsupported number of inputs: ${inputs}`);

    /** @type {FileList} files - Files selected in the single input */
    const files = inputs[0].files;

    // Add each file’s lastModified timestamp to the form data
    [...files].forEach((f) => formData.append("last-modified", f.lastModified));

    // Submit via POST and hard-refresh current URL
    await fetch(event.target.action, { method: "POST", body: formData });
    history.replaceState(null, "", location.href);
    location.href = location.href;
  } catch (error) {
    console.error("Error:", error);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  // Make variant links navigate without creating new history entries
  document.querySelectorAll(".variant-link").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      const t = link.href;
      history.replaceState(null, "", t);
      location.href = t;
    });
  });

  // Action buttons: fire GET, then reload current page without a new history entry
  document.querySelectorAll(".action-button").forEach((link) => {
    link.addEventListener("click", async (event) => {
      event.preventDefault();
      try {
        await fetch(link.href);
        history.replaceState(null, "", location.href);
        location.href = location.href;
      } catch (error) {}
    });
  });

  /** @type {HTMLAnchorElement} dl - Download button */
  const dl = document.querySelector(".button.is-dl");
  /** @type {HTMLInputElement} headCb - Master “select all” checkbox */
  const headCb = document.querySelector('input[type="checkbox"].head-cb');
  /** @type {HTMLInputElement[]} fileCbs - Per-file selection checkboxes */
  const fileCbs = [
    ...document.querySelectorAll('input[type="checkbox"].file-cb'),
  ];

  // Toggle all file checkboxes when header checkbox is clicked
  headCb.addEventListener("click", (_event) => {
    const c = headCb.checked;
    fileCbs.forEach((i) => {
      i.checked = c;
    });
  });

  // Keep header checkbox in sync with individual file checkboxes
  fileCbs.forEach((c) => {
    c.addEventListener("click", (_event) => {
      headCb.checked = fileCbs.reduce(
        (prev, curr) => prev && curr.checked,
        true,
      );
    });
  });

  // Build download URL with selected file IDs as &s=<id> query parameters
  dl.addEventListener("click", (event) => {
    const c = fileCbs.filter((i) => i.checked).map((i) => i.id);
    if (c.length > 0) {
      event.preventDefault();
      location.href =
        dl.href + "?" + c.map((i) => `s=${encodeURIComponent(i)}`).join("&");
    }
  });
});
