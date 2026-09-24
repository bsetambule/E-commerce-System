// =========================
// FLASH MESSAGES
// =========================
function initFlashMessages() {
    const flashes = document.querySelectorAll(".flash-message");

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
// SEARCH BIND HELPER (FIXED DRY)
// ===============================
function bindSearch(inputId, tableId, emptyId) {
    const input = document.getElementById(inputId);
    if (!input) return;

    input.addEventListener("input", () => {
        filterTable(inputId, tableId, emptyId);
    });
}


// ===============================
// SEARCH MODULES
// ===============================
function initActivitySearch() {
    bindSearch("storemanagerActivitySearch", "storemanagerActivityTable", "noActivityResultsMessage");
}

function initOrderSearch() {
    bindSearch("storemanagerOrderSearch", "storemanagerOrderTable", "noOrderResultsMessage");
}

function initDeliverySearch() {
    bindSearch("storemanagerDeliverySearch", "storemanagerDeliveryTable", "noDeliveryResultsMessage");
}

function initStoreSearch() {
    bindSearch("storemanagerStoreSearch", "storemanagerStoreTable", "noStoreResultsMessage");
}

function initUserSearch() {
    bindSearch("storemanagerUserSearch", "storemanagerUserTable", "noUserResultsMessage");
}

function initProductSearch() {
    bindSearch("storemanagerProductSearch", "storemanagerProductTable", "noProductResultsMessage");
}


// ===============================
// PHONE INPUT (FIXED SAFE VERSION)
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
// COORDINATES (FIXED VALIDATION)
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

        if (!latRaw && !lngRaw) {
            latInput.setCustomValidity("");
            lngInput.setCustomValidity("");
            return true;
        }

        let valid = true;

        const lat = parseFloat(latRaw);
        const lng = parseFloat(lngRaw);

        if (!lngRaw || !latRaw) {
            latInput.setCustomValidity("Both latitude and longitude are required together");
            lngInput.setCustomValidity("Both latitude and longitude are required together");
            return false;
        }

        if (isNaN(lat) || lat < -90 || lat > 90) {
            latInput.setCustomValidity("Latitude must be between -90 and 90");
            valid = false;
        } else {
            latInput.setCustomValidity("");
        }

        if (isNaN(lng) || lng < -180 || lng > 180) {
            lngInput.setCustomValidity("Longitude must be between -180 and 180");
            valid = false;
        } else {
            lngInput.setCustomValidity("");
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
// IMAGE PREVIEW
// ===============================
function initImagePreview() {
    const imageInput = document.getElementById("image");
    const preview = document.getElementById("previewImage");

    if (!imageInput || !preview) return;

    imageInput.addEventListener("change", function () {
        const file = this.files?.[0];

        if (!file) {
            preview.classList.add("hidden");
            preview.removeAttribute("src");
            return;
        }

        preview.src = URL.createObjectURL(file);
        preview.classList.remove("hidden");
    });
}


// ===============================
// ANALYTICS TABS
// ===============================
function switchTab(tabId, event) {
    document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(tab => tab.classList.remove("active"));

    event?.currentTarget?.classList.add("active");

    document.getElementById(tabId)?.classList.add("active");
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
            handleStoremanagerAction(pendingAction, pendingFormId);
        }

        pendingAction = null;
        pendingFormId = null;
    });
}


// ===============================
// ACTION HANDLER
// ===============================
function handleStoremanagerAction(action, formId) {
    switch (action) {

        case "submit-form":
            const form = document.getElementById(formId);
            if (!form) return;

            if (window.validatePhone && !window.validatePhone()) return;
            if (window.validateCoordinates && !window.validateCoordinates()) return;

            if (form.checkValidity()) form.submit();
            else form.reportValidity();
            break;

        default:
            console.log("Unknown action:", action);
    }
}


// ===============================
// INIT
// ===============================
function initStoremanager() {
    initFlashMessages();
    initSidebar();
    initActivitySearch();
    initOrderSearch();
    initDeliverySearch();
    initStoreSearch();
    initUserSearch();
    initProductSearch();
    initPhoneInput();
    initCoordinates();
    initConfirmModal();
    initImagePreview();
}

document.addEventListener("DOMContentLoaded", initStoremanager);