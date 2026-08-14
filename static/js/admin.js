/* =========================================================
   ADMIN PANEL JAVASCRIPT
   ========================================================= */

document.addEventListener("DOMContentLoaded", function () {

    console.log("Admin JS loaded successfully");

    /* =====================================================
       MOBILE SIDEBAR TOGGLE
       ===================================================== */

    const menuBtn = document.querySelector("#menuBtn");
    const sidebar = document.querySelector(".sidebar");
    const overlay = document.querySelector(".sidebar-overlay");

    if (menuBtn && sidebar) {
        menuBtn.addEventListener("click", function () {
            sidebar.classList.toggle("active");

            if (overlay) {
                overlay.classList.toggle("active");
            }
        });
    }

    if (overlay) {
        overlay.addEventListener("click", function () {
            sidebar.classList.remove("active");
            overlay.classList.remove("active");
        });
    }


    /* =====================================================
       SIDEBAR ACTIVE LINK
       ===================================================== */

    const currentPath = window.location.pathname;

    document.querySelectorAll(".sidebar a").forEach(function (link) {

        const href = link.getAttribute("href");

        if (!href) return;

        if (
            href === currentPath ||
            (href !== "/" && currentPath.startsWith(href))
        ) {
            link.classList.add("active");
        }
    });


    /* =====================================================
       FLASH MESSAGE AUTO HIDE
       ===================================================== */

    const flashMessages = document.querySelectorAll(
        ".alert, .flash-message, .flash"
    );

    flashMessages.forEach(function (message) {

        setTimeout(function () {

            message.style.opacity = "0";
            message.style.transform = "translateY(-10px)";

            setTimeout(function () {
                message.remove();
            }, 400);

        }, 4000);
    });


    /* =====================================================
       CONFIRM DELETE
       ===================================================== */

    document.querySelectorAll("[data-confirm-delete]").forEach(function (button) {

        button.addEventListener("click", function (event) {

            const message =
                button.getAttribute("data-confirm-delete") ||
                "Are you sure you want to delete this item?";

            if (!confirm(message)) {
                event.preventDefault();
            }
        });
    });


    /* =====================================================
       DELETE BUTTONS
       ===================================================== */

    document.querySelectorAll(".delete-btn").forEach(function (button) {

        button.addEventListener("click", function (event) {

            const confirmed = confirm(
                "Are you sure you want to delete this item?"
            );

            if (!confirmed) {
                event.preventDefault();
            }
        });
    });


    /* =====================================================
       LOGOUT CONFIRMATION
       ===================================================== */

    const logoutButtons = document.querySelectorAll(
        ".logout-btn, #logoutBtn"
    );

    logoutButtons.forEach(function (button) {

        button.addEventListener("click", function (event) {

            const confirmed = confirm(
                "Are you sure you want to logout?"
            );

            if (!confirmed) {
                event.preventDefault();
            }
        });
    });


    /* =====================================================
       SEARCH TABLE
       ===================================================== */

    const searchInput = document.querySelector("#tableSearch");

    if (searchInput) {

        searchInput.addEventListener("input", function () {

            const searchValue = this.value.toLowerCase().trim();

            const tableRows = document.querySelectorAll(
                "table tbody tr"
            );

            tableRows.forEach(function (row) {

                const rowText = row.textContent.toLowerCase();

                row.style.display =
                    rowText.includes(searchValue) ? "" : "none";
            });
        });
    }


    /* =====================================================
       SIDEBAR DROPDOWN
       ===================================================== */

    document.querySelectorAll(".dropdown-toggle").forEach(function (toggle) {

        toggle.addEventListener("click", function (event) {

            event.preventDefault();

            const dropdown = this.nextElementSibling;

            if (dropdown) {
                dropdown.classList.toggle("show");
            }

            this.classList.toggle("open");
        });
    });


    /* =====================================================
       MODAL OPEN
       ===================================================== */

    document.querySelectorAll("[data-modal]").forEach(function (button) {

        button.addEventListener("click", function () {

            const modalId = this.getAttribute("data-modal");
            const modal = document.getElementById(modalId);

            if (modal) {
                modal.classList.add("show");
            }
        });
    });


    /* =====================================================
       MODAL CLOSE
       ===================================================== */

    document.querySelectorAll(".modal-close").forEach(function (button) {

        button.addEventListener("click", function () {

            const modal = this.closest(".modal");

            if (modal) {
                modal.classList.remove("show");
            }
        });
    });


    /* =====================================================
       CLOSE MODAL WHEN CLICKING OUTSIDE
       ===================================================== */

    document.querySelectorAll(".modal").forEach(function (modal) {

        modal.addEventListener("click", function (event) {

            if (event.target === modal) {
                modal.classList.remove("show");
            }
        });
    });


    /* =====================================================
       PREVENT DOUBLE FORM SUBMISSION
       ===================================================== */

    document.querySelectorAll("form").forEach(function (form) {

        form.addEventListener("submit", function () {

            const submitButtons = form.querySelectorAll(
                'button[type="submit"], input[type="submit"]'
            );

            submitButtons.forEach(function (button) {

                button.disabled = true;

                const originalText = button.innerText;

                if (button.tagName === "BUTTON") {
                    button.innerText = "Processing...";
                }

                setTimeout(function () {
                    button.disabled = false;

                    if (button.tagName === "BUTTON") {
                        button.innerText = originalText;
                    }

                }, 5000);
            });
        });
    });


    /* =====================================================
       PASSWORD SHOW / HIDE
       ===================================================== */

    document.querySelectorAll(".toggle-password").forEach(function (button) {

        button.addEventListener("click", function () {

            const input = document.querySelector(
                this.getAttribute("data-target")
            );

            if (!input) return;

            if (input.type === "password") {
                input.type = "text";
                this.textContent = "Hide";
            } else {
                input.type = "password";
                this.textContent = "Show";
            }
        });
    });


    /* =====================================================
       SELECT ALL CHECKBOX
       ===================================================== */

    const selectAll = document.querySelector("#selectAll");

    if (selectAll) {

        selectAll.addEventListener("change", function () {

            document.querySelectorAll(
                'input[type="checkbox"][name="selected"]'
            ).forEach(function (checkbox) {

                checkbox.checked = selectAll.checked;

            });
        });
    }


    /* =====================================================
       CURRENT YEAR
       ===================================================== */

    document.querySelectorAll(".current-year").forEach(function (element) {
        element.textContent = new Date().getFullYear();
    });

});
