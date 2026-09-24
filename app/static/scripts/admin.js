// =========================
// HELPERS
// =========================
const $$ = (selector, root = document) => root.querySelectorAll(selector);


// =========================
// FLASH MESSAGES
// =========================
function initFlashMessages() {
    const flashes = $$(".flash-message");

    flashes.forEach(flash => {

        const removeFlash = () => {
            flash.style.animation = "fadeOut 0.4s ease forwards";
            setTimeout(() => flash.remove(), 400);
        };

        setTimeout(removeFlash, 4000);

        flash.querySelector(".flash-close")?.addEventListener("click", removeFlash);
    });
}


// ===============================
// SIDEBAR TOGGLE
// ===============================
function initSidebar() {
    const menuToggle = document.getElementById("menuToggle");
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("overlay");

    if (!menuToggle || !sidebar || !overlay) return;

    const closeMenu = () => {
        sidebar.classList.remove("show");
        overlay.classList.remove("show");
        menuToggle.classList.remove("active");
    };

    menuToggle.addEventListener("click", () => {
        sidebar.classList.toggle("show");
        overlay.classList.toggle("show");
        menuToggle.classList.toggle("active");
    });

    overlay.addEventListener("click", closeMenu);

    document.querySelectorAll("#sidebar a").forEach(link => {
        link.addEventListener("click", closeMenu);
    });
}


// ===============================
// TABLE FILTER (OPTIMIZED)
// ===============================
function filterTable(inputId, tableId, noResultsId) {
    const input = document.getElementById(inputId);
    const table = document.getElementById(tableId);
    const noResults = document.getElementById(noResultsId);

    if (!input || !table) return;

    const filter = input.value.toLowerCase();
    const rows = table.querySelectorAll("tbody tr");

    let visible = 0;

    rows.forEach(row => {
        if (!row.dataset.search) {
            row.dataset.search = row.textContent.toLowerCase();
        }

        const match = row.dataset.search.includes(filter);
        row.style.display = match ? "" : "none";

        if (match) visible++;
    });

    if (noResults) {
        noResults.style.display = visible === 0 ? "block" : "none";
    }
}


// ===============================
// SEARCH INIT HELPERS
// ===============================
function bindSearch(inputId, tableId, emptyId) {
    const input = document.getElementById(inputId);
    if (!input) return;

    input.addEventListener("input", () => {
        filterTable(inputId, tableId, emptyId);
    });
}

function initActivitySearch() {
    bindSearch("adminActivitySearch", "adminActivityTable", "noActivityResultsMessage");
}

function initLogSearch() {
    bindSearch("adminLogSearch", "adminLogTable", "noLogResultsMessage");
}

function initOrderSearch() {
    bindSearch("adminOrderSearch", "adminOrderTable", "noOrderResultsMessage");
}

function initDeliverySearch() {
    bindSearch("adminDeliverySearch", "adminDeliveryTable", "noDeliveryResultsMessage");
}

function initStoreSearch() {
    bindSearch("adminStoreSearch", "adminStoreTable", "noStoreResultsMessage");
}

function initUserSearch() {
    bindSearch("adminUserSearch", "adminUserTable", "noUserResultsMessage");
}


// ===============================
// PHONE INPUT HANDLING (SAFE)
// ===============================
function initPhoneInput() {
    const phoneInput = document.getElementById("phoneInput");
    const countryCode = document.getElementById("countryCode");
    const fullPhone = document.getElementById("fullPhone");

    if (!phoneInput || !countryCode || !fullPhone) return;

    phoneInput.addEventListener("input", () => {
        phoneInput.value = phoneInput.value.replace(/\D/g, "");
    });

    function buildPhone() {
        const code = countryCode.value;
        const number = phoneInput.value.trim();

        if (!number) {
            fullPhone.value = "";
            return false;
        }

        if (number.length < 7 || number.length > 12) {
            phoneInput.setCustomValidity("Enter a valid phone number");
            return false;
        }

        phoneInput.setCustomValidity("");
        fullPhone.value = `${code}${number}`;
        return true;
    }

    phoneInput.addEventListener("blur", buildPhone);
    window.validatePhone = buildPhone;
}


// ===============================
// COORDINATES (SAFE + OPTIONAL)
// ===============================
function initCoordinates() {
    const latInput = document.getElementById("latitude");
    const lngInput = document.getElementById("longitude");

    if (!latInput || !lngInput) return;

    function sanitize(input) {
        input.value = input.value.replace(/[^0-9.\-]/g, "");

        const parts = input.value.split(".");
        if (parts.length > 2) {
            input.value = parts[0] + "." + parts.slice(1).join("");
        }

        if ((input.value.match(/-/g) || []).length > 1) {
            input.value = "-" + input.value.replace(/-/g, "");
        }
    }

    function validate() {
        const latRaw = latInput.value.trim();
        const lngRaw = lngInput.value.trim();

        // allow empty both
        if (!latRaw && !lngRaw) {
            latInput.setCustomValidity("");
            lngInput.setCustomValidity("");
            return true;
        }

        let valid = true;

        const lat = parseFloat(latRaw);
        const lng = parseFloat(lngRaw);

        if (!latRaw || isNaN(lat) || lat < -90 || lat > 90) {
            latInput.setCustomValidity("Latitude must be between -90 and 90");
            valid = false;
        } else {
            latInput.setCustomValidity("");
        }

        if (!lngRaw || isNaN(lng) || lng < -180 || lng > 180) {
            lngInput.setCustomValidity("Longitude must be between -180 and 180");
            valid = false;
        } else {
            lngInput.setCustomValidity("");
        }

        if ((latRaw && !lngRaw) || (!latRaw && lngRaw)) {
            latInput.setCustomValidity("Both latitude and longitude are required together");
            lngInput.setCustomValidity("Both latitude and longitude are required together");
            valid = false;
        }

        return valid;
    }

    latInput.addEventListener("input", () => {
        sanitize(latInput);
        validate();
    });

    lngInput.addEventListener("input", () => {
        sanitize(lngInput);
        validate();
    });

    window.validateCoordinates = validate;
}


// ===============================
// CONFIRM MODAL SYSTEM
// ===============================
let pendingAction = null;
let pendingFormId = null;

function initConfirmModal() {
    const modal = document.getElementById("confirmModal");
    const confirmText = document.getElementById("confirmText");
    const confirmYes = document.getElementById("confirmYes");
    const confirmNo = document.getElementById("confirmNo");

    if (!modal || !confirmText || !confirmYes || !confirmNo) return;

    document.querySelectorAll("[data-confirm]").forEach(btn => {
        btn.addEventListener("click", () => {

            const formId = btn.dataset.form;
            const form = formId ? document.getElementById(formId) : null;

            if (form) {
                if (window.validatePhone && !window.validatePhone()) return;

                if (window.validateCoordinates && !window.validateCoordinates()) {
                    form.reportValidity();
                    return;
                }

                if (!form.checkValidity()) {
                    form.reportValidity();
                    return;
                }
            }

            pendingAction = btn.dataset.action || null;
            pendingFormId = formId || null;

            confirmText.textContent = btn.dataset.message || "Are you sure?";
            modal.classList.remove("hidden");
        });
    });

    confirmNo.addEventListener("click", () => {
        modal.classList.add("hidden");
        pendingAction = null;
        pendingFormId = null;
    });

    confirmYes.addEventListener("click", () => {
        modal.classList.add("hidden");

        if (pendingAction) {
            handleAdminAction(pendingAction, pendingFormId);
        }

        pendingAction = null;
        pendingFormId = null;
    });
}


// ===============================
// ACTION HANDLER
// ===============================

let formSubmitting = false;

function handleAdminAction(action, formId) {

    switch (action) {

        case "submit-form":

            // STOP DOUBLE SUBMIT
            if (formSubmitting) {
                return;
            }

            const form = document.getElementById(formId);

            if (!form) return;

            if (
                window.validatePhone &&
                !window.validatePhone()
            ) {
                return;
            }

            if (
                window.validateCoordinates &&
                !window.validateCoordinates()
            ) {
                return;
            }

            if (!form.checkValidity()) {
                form.reportValidity();
                return;
            }

            formSubmitting = true;

            const submitBtn =
                document.getElementById("submitBtn");

            if (submitBtn) {

                submitBtn.disabled = true;

                submitBtn.innerText = "Creating...";
            }

            form.submit();

            break;

        default:
            console.log("Unknown action:", action);
    }
}

// ===============================
// TAB SWITCHING
// ===============================
function switchTab(tabId, event) {

    // Remove active from all buttons
    document.querySelectorAll(".tab-btn").forEach(btn => {
        btn.classList.remove("active");
    });

    // Remove active from all tab contents
    document.querySelectorAll(".tab-content").forEach(tab => {
        tab.classList.remove("active");
    });

    // Activate clicked button
    if (event && event.currentTarget) {
        event.currentTarget.classList.add("active");
    }

    // Activate selected tab
    const activeTab = document.getElementById(tabId);

    if (activeTab) {
        activeTab.classList.add("active");
    }
}

// ===============================
// INIT
// ===============================
function initAdmin() {
    initFlashMessages();
    initSidebar();
    initActivitySearch();
    initLogSearch();
    initOrderSearch();
    initDeliverySearch();
    initStoreSearch();
    initUserSearch();
    initPhoneInput();
    initCoordinates();
    initConfirmModal();
}

document.addEventListener("DOMContentLoaded", initAdmin);