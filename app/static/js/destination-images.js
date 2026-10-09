document.addEventListener("error", function (event) {
  const image = event.target;
  if (!(image instanceof HTMLImageElement) || !image.hasAttribute("data-image-fallback")) return;
  const picture = image.closest("picture");
  if (picture) {
    picture.classList.add("image-failed");
    picture.setAttribute("aria-hidden", "true");
    picture.remove();
  }
}, true);
