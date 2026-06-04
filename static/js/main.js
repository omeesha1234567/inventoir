$(document).ready(function () {
    if ($('#dtVerticalScrollExample').length) {
        $('#dtVerticalScrollExample').DataTable({
            scrollY: "200px",
            scrollCollapse: true
        });

        $('.dataTables_length').addClass('bs-select');
    }
});

document.addEventListener("DOMContentLoaded", function () {
    const body = document.body;
    const sidebarToggleBtn = document.getElementById("sidebarToggleBtn");

    body.classList.add("sidebar-collapsed");

    if (sidebarToggleBtn) {
      
        sidebarToggleBtn.addEventListener("click", function () {
            body.classList.toggle("sidebar-collapsed");
        });
    }
});