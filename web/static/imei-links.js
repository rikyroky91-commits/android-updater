/* Only imei.info exposes a public URL that pre-fills the IMEI. Other
 * checkers use POST forms or CAPTCHA, so we copy the number before opening
 * their page instead of fabricating a query parameter that they ignore. */
(function () {
  "use strict";
  document.addEventListener("click", function (event) {
    const link = event.target.closest("a[data-copia-imei]");
    if (!link) return;
    const imei = String(link.dataset.copiaImei || "").replace(/\D/g, "");
    if (imei.length !== 15 || !navigator.clipboard || !navigator.clipboard.writeText) return;
    navigator.clipboard.writeText(imei).catch(function () {});
  });
}());
