// When the meta_type select changes on the MetaInstance add/change form,
// reload the page with ?meta_type=<id> so the server-side form rebuilds the
// "data" widget with the structured-json schema for the chosen type.
(function () {
  function init() {
    var select = document.getElementById("id_meta_type");
    if (!select) return;
    select.addEventListener("change", function () {
      var url = new URL(window.location.href);
      if (select.value) {
        url.searchParams.set("meta_type", select.value);
      } else {
        url.searchParams.delete("meta_type");
      }
      window.location.href = url.toString();
    });
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
